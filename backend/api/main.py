"""
FastAPI 애플리케이션 팩토리 – 라우터 모듈별 분리 버전
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import documents, health, search, models, settings, generate

__all__ = ["app"]


def create_app() -> FastAPI:
    app = FastAPI(
        title="GTOne RAG API",
        version="2.0.0",
        description="모듈화된 RAG 백엔드",
    )

    # ───────────────────── 미들웨어 ─────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ───────────────────── 라우터 ──────────────────────
    app.include_router(health.router, tags=["health"])
    app.include_router(documents.router, tags=["documents"])
    app.include_router(search.router, tags=["search"])
    app.include_router(models.router, tags=["models"])
    app.include_router(settings.router, tags=["settings"])
    app.include_router(generate.router, tags=["generate"])

    return app


app = create_app()
