# AskTube

AskTube is a monorepo foundation for a domain-agnostic conversational RAG application for YouTube playlists. This initial step includes only the Next.js frontend shell and a FastAPI health endpoint. Playlist processing, transcription, retrieval, AI generation, and chat are intentionally not implemented yet.

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
