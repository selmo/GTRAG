"""
GTOne RAG 백엔드 패키지
"""
from importlib import metadata as _metadata

__all__ = ["__version__"]

try:
    __version__ = _metadata.version("gtone_rag")
except _metadata.PackageNotFoundError:  # 로컬 실행
    __version__ = "0.0.0"
