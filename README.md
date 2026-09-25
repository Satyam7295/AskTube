# AskTube

AskTube is a monorepo foundation for a domain-agnostic conversational RAG application for YouTube playlists. It validates YouTube playlist URLs, retrieves playlist metadata and ordered videos through a FastAPI backend using the official YouTube Data API v3, persists structured YouTube transcripts in PostgreSQL, and retrieves semantically relevant transcript chunks from Qdrant. AI generation and chat are intentionally not implemented yet.

## Structure

- `frontend/`: Next.js, TypeScript, App Router, and Tailwind CSS frontend
- `backend/`: FastAPI backend with modular application boundaries

## Prerequisites

- Node.js 20+
- Python 3.11+

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

To create a production build:

```powershell
cd frontend
npm run build
```

## Backend

Create and activate a virtual environment, then install the dependencies:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Start the API:

```powershell
uvicorn app.main:app --reload --port 8000
```

Test the health endpoint:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

Expected response:

```json
{
  "status": "ok"
}
```

The backend starts without PostgreSQL or Qdrant configured. Future service configuration belongs in environment variables based on `.env.example`.

Set `YOUTUBE_API_KEY` in `backend/.env` before loading a playlist. The key is used only by the backend; the frontend calls `GET /api/playlists/{playlist_id}`.

## Qdrant Vector Storage

Qdrant is used as a storage layer for transcript chunk embeddings that will support future semantic retrieval. AskTube keeps PostgreSQL as the source of truth for transcript and chunk metadata, while Qdrant stores vectors and chunk payloads for later retrieval workflows.

### Environment variables

Add the following to `backend/.env`:

```env
DATABASE_URL=
YOUTUBE_API_KEY=
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=asktube_chunks
EMBEDDING_DIMENSION=384
```

- `QDRANT_URL` is required for local or cloud deployment.
- `QDRANT_API_KEY` is optional for local Qdrant and required for Qdrant Cloud.
- `QDRANT_COLLECTION_NAME` defaults to `asktube_chunks`.
- `EMBEDDING_DIMENSION` must stay aligned with the configured embedding model.

### Local setup

A local Qdrant instance can be started with Docker:

```powershell
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

The AskTube backend creates the collection automatically when a sync request is made.

### Collection configuration

The Qdrant collection uses the configured embedding dimension and cosine distance:

- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Dimension: `384`
- Distance: `COSINE`

The collection configuration is driven from backend settings rather than a hardcoded value so the embedding model can be changed safely later.

### Synchronization flow

Use the stored transcript chunk embeddings already persisted in PostgreSQL and synchronize them into Qdrant:

```http
POST /api/videos/{video_id}/vectors
```

Example flow:

1. Validate the video ID.
2. Load stored transcript chunks for that video.
3. Decode each saved embedding.
4. Validate vector dimensionality and metadata.
5. Upsert payloads into Qdrant with deterministic point IDs.
6. Return the number of chunks upserted and skipped.

This sync layer is storage-only. Semantic retrieval uses the existing embeddings and Qdrant payloads without loading all chunks from PostgreSQL.

## Semantic Retrieval

Search the indexed transcript chunks with the existing embedding model and Qdrant cosine similarity search:

```http
POST /api/search
Content-Type: application/json

{
  "query": "What is database normalization?",
  "top_k": 5,
  "video_id": "dQw4w9WgXcQ",
  "score_threshold": 0.5
}
```

`query` is required. `top_k` defaults to `RETRIEVAL_TOP_K` (5) and is capped by `RETRIEVAL_MAX_TOP_K` (100). `video_id` restricts search to one YouTube video, while `score_threshold` is optional and uses Qdrant's cosine score filtering. Omit either optional field for global search or unthresholded top-k results.

The response contains the normalized query, result count, and source metadata including chunk ID, video ID, similarity score, transcript text, timestamps, chunk index, language, and available segment/count metadata:

```json
{
  "query": "What is database normalization?",
  "result_count": 1,
  "results": [
    {
      "chunk_id": 42,
      "video_id": "dQw4w9WgXcQ",
      "score": 0.84,
      "text": "...",
      "start_time": 120.5,
      "end_time": 145.2,
      "chunk_index": 7,
      "language_code": "en"
    }
  ]
}
```

Retrieval does not generate answers yet. The LLM/RAG layer will consume these retrieved chunks in the next feature.

## RAG Context Builder

The internal context builder converts retrieval results into a deterministic, bounded `RAGContext` for a future LLM layer:

```text
Question
  ↓
Embedding
  ↓
Qdrant Retrieval
  ↓
Retrieved Chunks
  ↓
RAG Context Builder
  ↓
LLM (future)
```

It validates chunk metadata, removes duplicate chunk identities and exact repeated transcript text within a video, preserves source and timestamp metadata, and formats traceable plain text. Video groups are ordered by their best relevance score; chunks inside a group are chronological. Context is limited by `RAG_MAX_CONTEXT_CHARS` (default `12000`) and `RAG_MAX_SOURCES` (default `5`). The builder performs no database, Qdrant, embedding, network, or LLM calls and does not generate answers or citations.

## Implementation Summary

AskTube validates YouTube playlist URLs locally, then retrieves playlist metadata and all ordered playlist videos through the backend. Pagination, API errors, loading, empty, and failure states are handled. Playlist and transcript database persistence are implemented. Transcript chunk embeddings use the local `sentence-transformers/all-MiniLM-L6-v2` model by default, with `EMBEDDING_MODEL`, `EMBEDDING_NORMALIZE`, and `EMBEDDING_BATCH_SIZE` configurable through the backend environment. The model produces 384-dimensional normalized vectors for cosine-similarity retrieval. Stored vectors remain in PostgreSQL metadata fields for persistence, and Qdrant stores corresponding vectors and payload metadata for semantic retrieval. Retrieval returns source chunks only; AI generation and chat remain out of scope.
