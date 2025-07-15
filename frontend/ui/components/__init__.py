"""
GTOne RAG System - UI Components Package
재사용 가능한 Streamlit UI 컴포넌트들
"""

# 컴포넌트 함수들 import
from .chatting import (
    render_chat_history,
    render_sources,
    handle_chat_input,
    clear_chat_history,
    export_chat_history
)

from .searching import (
    render_search_interface,
    perform_search,
    render_search_results_improved,
    highlight_search_terms,
    save_search_history,
    render_search_history
)

from .sidebar import (
    render_sidebar,
    render_system_status,
    check_system_health,
    render_service_status,
    show_system_stats
)

from .uploader import (
    render_file_uploader,
    process_upload,
    render_uploaded_files,
    get_upload_summary,
    test_api_connection
)

__all__ = [
    # 채팅 관련
    "render_chat_history",
    "render_sources",
    "handle_chat_input",
    "clear_chat_history",
    "export_chat_history",

    # 검색 관련
    "render_search_interface",
    "perform_search",
    "render_search_results_improved",
    "highlight_search_terms",
    "save_search_history",
    "render_search_history",

    # 사이드바 관련
    "render_sidebar",
    "render_system_status",
    "check_system_health",
    "render_service_status",
    "show_system_stats",

    # 업로더 관련
    "render_file_uploader",
    "process_upload",
    "render_uploaded_files",
    "get_upload_summary",
    "test_api_connection"
]