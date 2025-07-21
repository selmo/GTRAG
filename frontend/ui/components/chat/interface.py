"""Main Chat UI orchestration."""
from __future__ import annotations

import streamlit as st

from frontend.ui.core.config import Constants
from frontend.ui.components.common import ActionButton, StatusIndicator
from frontend.ui.utils.streamlit_helpers import rerun

from .history import ChatHistory
from .input_handler import ChatInputHandler
from .utils import check_model_availability
from .message_display import render_sources  # exported for convenience

try:
    from frontend.ui.utils.system_health import SystemHealthManager  # type: ignore
    HAS_SYSTEM_HEALTH = True
except ImportError:
    SystemHealthManager = None  # type: ignore
    HAS_SYSTEM_HEALTH = False

__all__ = ["ChatInterface"]


class ChatInterface:
    """High‑level chat orchestration class imported by Home page."""

    def __init__(self, api_client):
        self.api_client = api_client
        self.history = ChatHistory()
        self.input_handler = ChatInputHandler(api_client)

    # --------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------
    def render(self):
        st.title(f"{Constants.Icons.AI} GTOne RAG Chat")

        self._render_header()
        self._render_action_row()

        # Chat history
        if not self.history._ensure_list():
            st.info(f"{Constants.Icons.AI} 질문을 입력하여 대화를 시작하세요.")
        else:
            self.history.render()

        # Input widget
        self.input_handler.render_input()

        # Footer stats
        if self.history._ensure_list():
            st.divider()
            self.history.render_stats()

    # --------------------------------------------------------------
    # Internals
    # --------------------------------------------------------------
    def _render_header(self):
        ok, err = check_model_availability(self.api_client)
        col1, col2 = st.columns([3, 1])
        with col1:
            if ok:
                model_name = st.session_state.get("selected_model", "Unknown")
                StatusIndicator.render_status("success", f"{model_name} 사용 준비 완료")
            else:
                StatusIndicator.render_status("error", "모델 사용 불가", err)

        with col2:
            if st.button(f"{Constants.Icons.SETTINGS} 설정", key="quick_settings"):
                st.switch_page("pages/99_Settings.py")

    def _render_action_row(self):
        actions = [
            {
                "label": f"{Constants.Icons.DELETE} 대화 초기화",
                "key": "clear_chat_main",
                "callback": self.history.clear,
                "type": "secondary",
            },
            {
                "label": f"{Constants.Icons.DOWNLOAD} 내보내기",
                "key": "export_chat_main",
                "callback": self.history.export,
                "type": "secondary",
            },
        ]
        ActionButton.render_action_row(actions)
