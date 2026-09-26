AskTube

AskTube turns a YouTube playlist into a searchable, conversational knowledge base.

Instead of manually searching through long playlists, AskTube lets you provide a YouTube playlist URL, ask questions in natural language, and get grounded answers with relevant videos and timestamps.

🎥 Advertisement Video

Watch the AskTube project advertisement:
Advertisement Video — Google Drive https://drive.google.com/file/d/1mCa3-dMP50nsR5ZJSe0yUu7ndO4uORWd/view?usp=sharing

📑 Pitch Deck

View the AskTube presentation:
Pitch Deck — Slides https://canva.link/zh0b6bl4grzlsyx

✨ Why AskTube?

Finding one specific concept inside a long YouTube playlist can be frustrating.

AskTube solves this by connecting the entire learning flow:

YouTube Playlist → Videos → Transcripts → Chunks → Embeddings → Semantic Search → Grounded Answer

You can ask questions such as:

"Where is this concept explained?"

"Which video covers this topic?"

"Explain this using the content from the playlist."

AskTube retrieves the most relevant parts of the playlist and uses them as context for generating an answer.

🚀 Key Features

📥 Playlist Ingestion

Accepts a YouTube playlist URL.

Extracts playlist and video metadata.

Processes videos for searchable content.

📝 Transcript Processing

Retrieves video transcripts.

Caches transcript data to avoid unnecessary repeated processing.

Splits transcripts into timestamp-aware chunks.

🔎 Semantic Search

Converts transcript chunks into vector embeddings.

Stores embeddings in Qdrant.

Finds semantically relevant content instead of relying only on exact keyword matches.

🤖 Grounded AI Answers

Retrieves relevant context before generating an answer.

Uses Groq for answer generation.

Reduces unsupported responses by grounding the answer in retrieved playlist content.

Handles insufficient context instead of pretending an answer exists.

🎯 Source & Timestamp References

Answers can point back to the relevant:

Video

Timestamp

Retrieved content

This makes it easier to continue learning directly from the original YouTube material.

💬 Conversational Questions

Ask follow-up questions naturally instead of restarting the search every time.

🧠 How It Works

                    YouTube Playlist
                           │
                           ▼
                  ┌─────────────────┐
                  │ Playlist / Video│
                  │    Metadata     │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   Transcripts   │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Timestamp-aware │
                  │     Chunks      │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   Embeddings    │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Qdrant Vector DB│
                  └────────┬────────┘
                           │
                    User Question
                           │
                           ▼
                  ┌─────────────────┐
                  │Semantic Retrieval│
                  │ + Context Ranking│
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Groq LLM       │
                  │ Grounded Answer  │
                  └────────┬────────┘
                           │
                           ▼
                  Answer + Sources
                  + Video Timestamps

🏗️ Architecture

┌───────────────────────────────────────────────┐
│                 Frontend                      │
│        Next.js + React + TypeScript           │
│                  Tailwind                     │
└──────────────────────┬────────────────────────┘
                       │
                       │ HTTP API
                       ▼
┌───────────────────────────────────────────────┐
│                  Backend                      │
│              Python + FastAPI                 │
│        Pydantic + SQLAlchemy                  │
└───────────────┬───────────────┬───────────────┘
                │               │
                ▼               ▼
        ┌──────────────┐   ┌──────────────┐
        │ PostgreSQL   │   │    Qdrant    │
        │ Source of    │   │ Vector Search│
        │ Truth        │   │              │
        └──────────────┘   └──────┬───────┘
                                  │
                                  ▼
                         Semantic Retrieval
                                  │
                                  ▼
                            ┌───────────┐
                            │   Groq    │
                            │    LLM    │
                            └───────────┘

🧩 RAG Pipeline

AskTube follows a retrieval-augmented generation approach:

Ingest the YouTube playlist.

Extract video metadata.

Retrieve and cache transcripts.

Chunk transcript content while preserving timestamps.

Generate embeddings for each chunk.

Store vectors in Qdrant.

Embed the user's question.

Retrieve semantically relevant chunks.

Validate, deduplicate, rank, and bound the retrieved context.

Generate a grounded response using Groq.

Return the answer together with relevant video/timestamp references.

🛠️ Tech Stack

Layer

Technology

Frontend

Next.js, React, TypeScript, Tailwind CSS

Backend

Python, FastAPI

API Validation

Pydantic

ORM

SQLAlchemy

Relational Database

PostgreSQL

Vector Database

Qdrant

Video Source

YouTube

Embeddings

all-MiniLM-L6-v2

LLM

Groq

Architecture

Retrieval-Augmented Generation (RAG)

📁 Project Structure

AskTube/
│
├── frontend/
│   ├── app/
│   ├── components/
│   └── ...
│
├── backend/
│   ├── api/
│   ├── services/
│   ├── models/
│   ├── retrieval/
│   └── ...
│
├── docker-compose.yml
├── .env.example
└── README.md

⚙️ Getting Started

1. Clone the repository

git clone <YOUR_REPOSITORY_URL>
cd AskTube

2. Configure environment variables

Create the required environment files using the provided examples.

cp .env.example .env

Configure the required services and credentials, including the database, Qdrant, YouTube/transcript access, and Groq.

3. Start infrastructure

docker compose up -d

This starts the required local infrastructure such as PostgreSQL and Qdrant.

4. Start the backend

cd backend
# install dependencies according to the project configuration
# start the FastAPI application

5. Start the frontend

cd frontend
npm install
npm run dev

Open the local development URL shown by Next.js.

Note: Exact setup commands may evolve as the project develops. Check the project configuration files for the current dependency and startup commands.

🔐 Environment Variables

AskTube uses environment variables for external services and infrastructure configuration.

Typical configuration includes:

DATABASE_URL=

QDRANT_URL=

GROQ_API_KEY=
GROQ_MODEL=

YOUTUBE_API_KEY=

Never commit real API keys or secrets to the repository.

🧪 Testing & Verification

The project includes checks for important parts of the pipeline, including:

Backend health

Database connectivity

Qdrant connectivity

Embedding generation

Retrieval pipeline

LLM integration

API behavior

Context validation

For development, verify each service independently before testing the complete RAG flow.

📌 Current Status

AskTube is being developed incrementally, with the core foundation and major RAG components being implemented and verified feature by feature.

Current implemented areas include:

Playlist ingestion flow

Transcript processing/caching

Text chunking

Embedding generation

Qdrant vector storage

Semantic retrieval

Context validation and ranking

Groq-based answer generation

Source and timestamp-aware answers

Insufficient-context handling

Some integration and environment-dependent functionality may require local configuration and service availability.

🎯 Project Goal

The goal of AskTube is simple:

Turn passive YouTube playlists into interactive, searchable learning experiences.

Instead of asking:

"Which of these 50 videos contains what I need?"

AskTube lets you ask:

"Where is this explained?"

and navigate directly to the relevant content.

🔮 Future Improvements

Potential improvements include:

Better hybrid retrieval

Improved reranking

More accurate timestamp extraction

Conversation memory improvements

Faster playlist indexing

Streaming AI responses

Better source visualization

Improved error handling and observability

Support for larger playlists and more content sources

🤝 Contributing

Contributions, suggestions, and improvements are welcome.

Fork the repository.

Create a feature branch.

Make your changes.

Test your changes.

Open a pull request.

📄 License

Add the project's chosen license here.

👨‍💻 Built With

AskTube was built to explore how YouTube educational content can be transformed into a searchable and conversational knowledge base using RAG, semantic search, vector databases, and LLMs.
