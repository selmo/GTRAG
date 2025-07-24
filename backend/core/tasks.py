"""
Celery 애플리케이션 ‐ 중앙 싱글턴
"""
from __future__ import annotations

from celery import Celery
from backend.core.config import settings

celery_app = Celery(
    "gtragr",
    broker=settings.broker_url,
    backend=settings.result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# 간단한 연결-확인 태스크 (헬스체크용)
@celery_app.task(name="ping")
def ping() -> str:  # pragma: no cover
    return "pong"
