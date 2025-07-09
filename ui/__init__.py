# ui/__init__.py
"""
GTOne RAG System UI Package
"""

__version__ = "1.0.0"
__author__ = "GTOne Team"

# ui/components/__init__.py
"""
UI 컴포넌트 모듈
재사용 가능한 Streamlit 컴포넌트들
"""

from .chat import render_chat_history, handle_chat_input, clear_chat_history
from .uploader import render_file_uploader, process_upload, get_upload_summary
from .search import render_search_interface, perform_search
from .sidebar import render_sidebar, render_system_status

__all__ = [
    'render_chat_history',
    'handle_chat_input',
    'clear_chat_history',
    'render_file_uploader',
    'process_upload',
    'get_upload_summary',
    'render_search_interface',
    'perform_search',
    'render_sidebar',
    'render_system_status'
]

# ui/utils/__init__.py
"""
UI 유틸리티 모듈
공통 기능 및 헬퍼 함수들
"""

from .api_client import APIClient
from .session import SessionManager, init_page_state, get_page_state
from .helpers import (
    format_file_size,
    format_timestamp,
    truncate_text,
    highlight_text,
    validate_file,
    get_file_icon,
    format_number
)

__all__ = [
    'APIClient',
    'SessionManager',
    'init_page_state',
    'get_page_state',
    'format_file_size',
    'format_timestamp',
    'truncate_text',
    'highlight_text',
    'validate_file',
    'get_file_icon',
    'format_number'
]

# ui/pages/__init__.py
"""
Streamlit 멀티페이지 앱 페이지들
"""
# 이 파일은 비어있어도 됩니다. Streamlit이 자동으로 pages 폴더를 인식합니다.