from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from app.core.config import get_settings


class EmbeddingInputError(ValueError):
    """Raised when embedding input is not usable text."""


class EmbeddingModelError(RuntimeError):
    """Raised when the local embedding model cannot be loaded or used."""


@dataclass(frozen=True)
class GeneratedEmbedding:
    chunk_id: int
    chunk_index: int
    vector: list[float]


class EmbeddingService:
    def __init__(
        self,
        model_name: str | None = None,
        model: Any | None = None,
        model_factory: Callable[[str], Any] | None = None,
        batch_size: int | None = None,
        normalize: bool | None = None,
    ) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.batch_size = batch_size or settings.embedding_batch_size
        self.normalize = settings.embedding_normalize if normalize is None else normalize
        self._model = model
        self._model_factory = model_factory or self._load_sentence_transformer
        if not self.model_name.strip():
            raise EmbeddingInputError("Embedding model name must not be empty.")
        if self.batch_size < 1:
            raise EmbeddingInputError("Embedding batch size must be positive.")

    @property
    def model(self) -> Any:
        if self._model is None:
            try:
                self._model = self._model_factory(self.model_name)
            except Exception as error:
                raise EmbeddingModelError("Embedding model could not be loaded.") from error
        return self._model

    @staticmethod
    def _load_sentence_transformer(model_name: str) -> Any:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(model_name)

    @staticmethod
    def _validate_text(text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            raise EmbeddingInputError("Embedding text must contain non-whitespace characters.")
        return text.strip()

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: Iterable[str]) -> list[list[float]]:
        validated = [self._validate_text(text) for text in texts]
        if not validated:
            return []
        model = self.model
        try:
            encoded = model.encode(
                validated,
                batch_size=self.batch_size,
                normalize_embeddings=self.normalize,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except Exception as error:
            raise EmbeddingModelError("Embedding generation failed.") from error
        vectors = encoded.tolist() if hasattr(encoded, "tolist") else encoded
        if len(vectors) != len(validated) or not vectors or any(not vector for vector in vectors):
            raise EmbeddingModelError("Embedding model returned an invalid result.")
        dimension = len(vectors[0])
        if any(len(vector) != dimension for vector in vectors):
            raise EmbeddingModelError("Embedding model returned inconsistent vector dimensions.")
        return [[float(value) for value in vector] for vector in vectors]

    def embed_chunks(self, chunks: Iterable[Any]) -> list[GeneratedEmbedding]:
        chunk_list = list(chunks)
        vectors = self.embed_texts([chunk.text for chunk in chunk_list])
        return [
            GeneratedEmbedding(chunk.id, chunk.chunk_index, vector)
            for chunk, vector in zip(chunk_list, vectors)
        ]

    @staticmethod
    def decode_vector(value: str | None) -> list[float] | None:
        if value is None:
            return None
        decoded = json.loads(value)
        return [float(item) for item in decoded]