from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.playlists import router as playlists_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:3000"],
	allow_methods=["GET"],
	allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(playlists_router)
