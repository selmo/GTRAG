"""
GTOne RAG System - Frontend UI Package
사용자 인터페이스 컴포넌트들의 패키지 초기화
"""

__version__ = "1.0.0"
__author__ = "GTOne"
__description__ = "GTOne RAG System Frontend UI Components"

# 주요 컴포넌트들 import
from .utils.api_client import APIClient
from .utils.session import SessionManager
from .utils.helpers import (
    format_file_size,
    format_timestamp,
    truncate_text,
    highlight_text,
    validate_file
)

# 컴포넌트 모듈들
from . import components
from . import utils

__all__ = [
    # 클래스들
    "APIClient",
    "SessionManager",

    # 유틸리티 함수들
    "format_file_size",
    "format_timestamp",
    "truncate_text",
    "highlight_text",
    "validate_file",

    # 모듈들
    "components",
    "utils"
]