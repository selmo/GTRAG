"""
FastAPI 애플리케이션 팩토리 – 라우터 모듈별 분리 버전
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import documents, health, search, models, settings, generate

__all__ = ["app"]


def create_app() -> FastAPI:
    """FastAPI 애플리케이션 생성 및 로깅 시스템 설정"""
    app = FastAPI(
        title="GTOne RAG API",
        version="2.0.0",
        description="모듈화된 RAG 백엔드 (고급 로깅 시스템 포함)",
    )

    # ───────────────────── 로깅 시스템 초기화 ─────────────────────
    from backend.core.logging import get_logger
    from backend.middleware.logging_middleware import LoggingMiddleware, DetailedLoggingMiddleware

    # 애플리케이션 로거 설정
    app_logger = get_logger("app")
    app_logger.info("FastAPI application starting", extra={
        "event_type": "app_startup",
        "app_name": "GTOne RAG API",
        "version": "2.0.0"
    })

    # ───────────────────── 미들웨어 (순서 중요!) ─────────────────────

    # 1. 상세 로깅 미들웨어 (개발 환경용)
    import os
    if os.getenv("ENVIRONMENT", "development") == "development":
        app.add_middleware(
            DetailedLoggingMiddleware,
            log_body=True,  # 요청/응답 바디 로깅
            max_body_size=2048  # 최대 2KB까지만 로깅
        )

    # 2. HTTP 요청/응답 로깅 미들웨어
    app.add_middleware(
        LoggingMiddleware,
        exclude_paths=["/docs", "/redoc", "/openapi.json", "/favicon.ico", "/v1/health"]
    )

    # 3. CORS 미들웨어
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

    # ───────────────────── 애플리케이션 이벤트 ──────────────────────
    @app.on_event("startup")
    async def startup_event():
        """애플리케이션 시작 이벤트"""
        app_logger.info("Application startup completed", extra={
            "event_type": "app_ready",
            "routers_count": len(app.routes),
            "middleware_count": len(app.user_middleware)
        })

    @app.on_event("shutdown")
    async def shutdown_event():
        """애플리케이션 종료 이벤트"""
        app_logger.info("Application shutdown initiated", extra={
            "event_type": "app_shutdown"
        })

    return app


app = create_app()
