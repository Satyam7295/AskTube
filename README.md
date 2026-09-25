# AskTube

AskTube is a monorepo foundation for a domain-agnostic conversational RAG application for YouTube playlists. It validates YouTube playlist URLs, retrieves playlist metadata and ordered videos through a FastAPI backend using the official YouTube Data API v3, and persists structured YouTube transcripts in PostgreSQL. Retrieval, AI generation, and chat are intentionally not implemented yet.

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

This sync layer is intentionally storage-only and does not implement search, retrieval, or LLM generation.

## Implementation Summary

AskTube validates YouTube playlist URLs locally, then retrieves playlist metadata and all ordered playlist videos through the backend. Pagination, API errors, loading, empty, and failure states are handled. Playlist and transcript database persistence are implemented. Transcript chunk embeddings use the local `sentence-transformers/all-MiniLM-L6-v2` model by default, with `EMBEDDING_MODEL`, `EMBEDDING_NORMALIZE`, and `EMBEDDING_BATCH_SIZE` configurable through the backend environment. The model produces 384-dimensional normalized vectors intended for later cosine-similarity use. Stored vectors remain in PostgreSQL metadata fields for persistence, and Qdrant stores corresponding vectors and payload metadata for future retrieval workflows. Retrieval, AI generation, and chat remain out of scope.
