from app.main import app


def test_cors_allows_dev_frontend_origins():
    cors_middleware = next(
        middleware for middleware in app.user_middleware if middleware.cls.__name__ == "CORSMiddleware"
    )

    origins = cors_middleware.kwargs.get("allow_origins", [])

    assert "http://localhost:3000" in origins
    assert "http://localhost:3015" in origins
