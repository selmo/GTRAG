"""
GTOne RAG System - Utils Package
공통 유틸리티 함수들과 헬퍼 클래스들
"""

# API 클라이언트
from .api_client import (
    APIClient,
    get_default_client,
    upload_document,
    search,
    generate_answer,
    health_check
)

# 세션 관리
from .session import (
    SessionManager,
    init_page_state,
    get_page_state,
    update_page_state,
    clear_page_state
)

# 헬퍼 함수들
from .helpers import (
    format_file_size,
    format_timestamp,
    truncate_text,
    highlight_text,
    validate_file,
    generate_file_hash,
    parse_search_query,
    create_progress_bar,
    show_toast,
    create_download_link,
    estimate_reading_time,
    sanitize_filename,
    get_file_icon,
    format_number,
    create_breadcrumb,
    calculate_similarity_color,
    create_metric_card,
    paginate_results,
    render_pagination_controls
)

# Streamlit 헬퍼
from .streamlit_helpers import rerun

__all__ = [
    # API 클라이언트
    "APIClient",
    "get_default_client",
    "upload_document",
    "search",
    "generate_answer",
    "health_check",

    # 세션 관리
    "SessionManager",
    "init_page_state",
    "get_page_state",
    "update_page_state",
    "clear_page_state",

    # 파일 및 텍스트 처리
    "format_file_size",
    "format_timestamp",
    "truncate_text",
    "highlight_text",
    "validate_file",
    "generate_file_hash",
    "sanitize_filename",
    "get_file_icon",

    # 검색 및 분석
    "parse_search_query",
    "calculate_similarity_color",
    "estimate_reading_time",

    # UI 헬퍼
    "create_progress_bar",
    "show_toast",
    "create_download_link",
    "format_number",
    "create_breadcrumb",
    "create_metric_card",
    "paginate_results",
    "render_pagination_controls",

    # Streamlit 헬퍼
    "rerun"
]

# 패키지 정보
__version__ = "1.0.0"
__author__ = "GTOne"
__description__ = "GTOne RAG System Utilities"