from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.playlists import router as playlists_router
from app.core.config import get_settings
from app.db.database import DatabaseConfigurationError, init_db

settings = get_settings()
app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def startup_event() -> None:
    if not settings.database_url:
        raise DatabaseConfigurationError(
            "Database is not configured. Set DATABASE_URL in the backend environment before using PostgreSQL persistence."
        )
    init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(playlists_router)
