"""
Qdrant 클라이언트 단일 진입점 (싱글턴)
"""
import logging
from functools import lru_cache

import qdrant_client
from backend.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_qdrant_client() -> qdrant_client.QdrantClient:  # noqa: D401
    """환경 변수 기반 Qdrant 인스턴스(싱글턴)를 반환합니다."""
    logger.info("Connecting to Qdrant → %s:%s", settings.qdrant_host, settings.qdrant_port)
    return qdrant_client.QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
