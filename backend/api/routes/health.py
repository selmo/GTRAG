import httpx
from fastapi import APIRouter, Depends
from backend.api.deps import qdrant_dep
from backend.core.tasks import celery_app
from backend.llm.ollama_client import get_ollama_client

router = APIRouter()


@router.get("/v1/health", summary="백엔드·서브시스템 헬스체크")
async def health(qdrant=Depends(qdrant_dep)):
    # Qdrant 체크
    try:
        async with httpx.AsyncClient() as client:
            from backend.core.config import settings
            r = await client.get(
                f"http://{settings.qdrant_host}:{settings.qdrant_port}/readyz",
                timeout=2,
            )
        qdrant_ok = r.status_code == 200
    except Exception:  # pragma: no cover – 에러만 bool 플래그로
        qdrant_ok = False

    # Ollama 체크
    try:
        get_ollama_client().list_models()
        ollama_ok = True
    except Exception:
        ollama_ok = False

    try:
        celery_ok = bool(celery_app.control.ping(timeout=1))
    except Exception:
        celery_ok = False

    return {
        "qdrant": qdrant_ok,
        "ollama": ollama_ok,
        "celery": celery_ok,
        "status": "healthy" if qdrant_ok and ollama_ok and celery_ok else "degraded",
    }
