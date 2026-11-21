🎥 **Watch the AskTube Project Advertisement**

[▶️ Watch Advertisement Video](https://drive.google.com/file/d/1mCa3-dMP50nsR5ZJSe0yUu7ndO4uORWd/view?usp=sharing)

🎬 **Demo Video**

[▶️ Watch AskTube Demo](https://drive.google.com/file/d/13acYani_Cd5Vlz9cUqko8msyD8NRzzpa/view?usp=sharing)

📑 **Pitch Deck**

[📊 View AskTube Pitch Deck](https://canva.link/zh0b6bl4grzlsyx)


<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/cf66edf5-20a9-4aad-a3df-a73bef831b1c" />
<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/effe4c70-032a-411b-888b-6f94f6541559" />
<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/b54617a3-9690-40ed-9238-14ca23b561a2" />
<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/6f9c2e4b-c2e5-436a-bd75-0f430b0027f3" />
<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/6f6a5a19-1fc8-4042-a73b-445cb67cab16" />
<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/afe9c7a2-8972-4a2b-bea5-cdaa1d3b10ab" />
<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/090f580f-9c24-40d9-86b8-d5953d647448" />
<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/92ee4066-f92a-41d1-a5a9-b7e24c90d47a" />
<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/1d8b4294-cb5d-43df-bd79-6531f10d60f2" />
<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/f5d74b9c-ace9-4768-93de-ab864b46a4d7" />
<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/2b6644d2-da6e-4739-b5fe-bdf602171f26" />
<img width="1672" height="941" alt="image" src="https://github.com/user-attachments/assets/aa58e60e-e322-4d4f-a357-36515b5577e9" />
<img width="1672" height="940" alt="image" src="https://github.com/user-attachments/assets/d366a483-3dfe-4910-b35e-cdd2b1c5b0c0" />
## Transcript provider configuration

Install the backend dependencies:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Transcript extraction does not require an API key or proxy. It uses `youtube-transcript-api` and supports both manually created and automatically generated captions. The backend accepts:

- An 11-character YouTube video ID, for example `dQw4w9WgXcQ`
- A standard URL such as `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- A shortened URL such as `https://youtu.be/dQw4w9WgXcQ`
- A Shorts URL such as `https://youtube.com/shorts/dQw4w9WgXcQ`
- Embed and live URLs

Copy `.env.example` to `.env` in the backend directory and configure these optional settings:

```env
YOUTUBE_PROXY_ENABLED=false
YOUTUBE_PROXY_USERNAME=
YOUTUBE_PROXY_PASSWORD=
TRANSCRIPT_PROXY_HTTP=
TRANSCRIPT_PROXY_HTTPS=
TRANSCRIPT_PROXY_USERNAME=
TRANSCRIPT_PROXY_PASSWORD=
TRANSCRIPT_RETRY_MAX_ATTEMPTS=3
TRANSCRIPT_RETRY_BASE_DELAY=2
TRANSCRIPT_PROVIDER_TIMEOUT=30
TRANSCRIPT_FALLBACK_URL=
TRANSCRIPT_FALLBACK_API_KEY=
TRANSCRIPT_CACHE_TTL_HOURS=168
TRANSCRIPT_CIRCUIT_FAILURE_THRESHOLD=3
TRANSCRIPT_CIRCUIT_COOLDOWN_SECONDS=300
```

When a requested language is unavailable, the provider falls back to English. Transcript segments and timestamps are stored and returned in the existing API format. Permanent failures, including missing transcripts, disabled captions, invalid IDs, unavailable/private videos, and unsupported languages, are not retried. Network failures and rate limits use exponential backoff.

Run the application:

```bash
# Backend
cd backend
.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (from another terminal)
cd frontend
npm install
npm run dev
```

Test the backend:

```bash
cd backend
.venv\\Scripts\\python.exe -m pytest -q
```

The backend uses `youtube-transcript-api` directly by default. A residential or approved proxy can be enabled with:

- `YOUTUBE_PROXY_ENABLED=true`
- `YOUTUBE_PROXY_USERNAME`
- `YOUTUBE_PROXY_PASSWORD`
- `TRANSCRIPT_PROXY_HTTP`
- `TRANSCRIPT_PROXY_HTTPS`

Proxy credentials are backend-only and must not be exposed through frontend `NEXT_PUBLIC_*` variables.

Retrieval retries are controlled by `TRANSCRIPT_RETRY_MAX_ATTEMPTS` and `TRANSCRIPT_RETRY_BASE_DELAY`. Permanent transcript, unavailable-video, IP-block, and disabled-caption failures are not retried.

