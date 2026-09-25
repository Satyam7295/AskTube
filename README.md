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

## Implementation Summary

AskTube validates YouTube playlist URLs locally, then retrieves playlist metadata and all ordered playlist videos through the backend. Pagination, API errors, loading, empty, and failure states are handled. Playlist and transcript database persistence are implemented. Transcript chunk embeddings use the local `sentence-transformers/all-MiniLM-L6-v2` model by default, with `EMBEDDING_MODEL`, `EMBEDDING_NORMALIZE`, and `EMBEDDING_BATCH_SIZE` configurable through the backend environment. The model produces 384-dimensional normalized vectors intended for later cosine-similarity use. Vectors are temporarily stored as JSON text on `transcript_chunks`; this is metadata persistence only, not PostgreSQL vector search. Retrieval, AI generation, and chat remain out of scope.
