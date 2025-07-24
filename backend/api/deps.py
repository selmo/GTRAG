"""FastAPI Depends 헬퍼 모듈"""
from backend.core.qdrant import get_qdrant_client


def qdrant_dep():
    """Router level depend-injector"""
    return get_qdrant_client()
