"""
LLM(Ollama) 헬퍼
"""
from __future__ import annotations
from .ollama_client import get_ollama_client, OllamaClient

__all__ = ["get_ollama_client", "OllamaClient"]

try:
    from .generator import generate_answer  # noqa: F401
except ImportError:                          # 경량 배포판
    def generate_answer(*_a, **_kw):  # type: ignore
        raise ImportError(
            "backend.llm.generator.generate_answer() 가 없습니다. "
            "generator.py 파일을 확인해 주세요."
        )
else:
    __all__.append("generate_answer")