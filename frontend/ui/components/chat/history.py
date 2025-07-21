"""Chat history services."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List

import streamlit as st

from frontend.ui.core.config import Constants
from frontend.ui.components.common import MetricCard  # stats

from .message_display import render_sources

__all__ = ["ChatHistory"]


class ChatHistory:
    """Thin wrapper around *st.session_state.messages* list for type safety."""

    _SS_KEY = "messages"

    # ---------------------------------------------------------------------
    # Session helpers
    # ---------------------------------------------------------------------
    @staticmethod
    def _ensure_list() -> List[Dict]:
        if ChatHistory._SS_KEY not in st.session_state:
            st.session_state[ChatHistory._SS_KEY] = []
        return st.session_state[ChatHistory._SS_KEY]

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def add(self, role: str, content: str, **extra):
        self._ensure_list().append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **extra,
        })

    def clear(self):
        if self._ensure_list():
            st.session_state[self._SS_KEY] = []
            st.success(f"{Constants.Icons.STATUS_OK} 대화 내역이 초기화되었습니다.")
        else:
            st.info("초기화할 대화 내역이 없습니다.")

    def export(self):
        messages = self._ensure_list()
        if not messages:
            st.info("내보낼 대화 내역이 없습니다.")
            return

        data = {
            "exported_at": datetime.now().isoformat(),
            "total_messages": len(messages),
            "messages": messages,
        }
        st.download_button(
            label=f"{Constants.Icons.DOWNLOAD} 대화 내역 다운로드",
            data=json.dumps(data, ensure_ascii=False, indent=2),
            file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )

    # ---------------------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------------------
    def render(self):
        for msg in self._ensure_list():
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg["role"] == "assistant" and "sources" in msg:
                    render_sources(msg["sources"])

    def render_stats(self):
        msgs = self._ensure_list()
        if not msgs:
            return
        total = len(msgs)
        user = sum(1 for m in msgs if m["role"] == "user")
        assistant = total - user
        errors = sum(1 for m in msgs if m.get("is_error"))

        MetricCard.render_metric_grid([
            {"title": "총 메시지", "value": total},
            {"title": "질문", "value": user},
            {"title": "답변", "value": assistant},
            {"title": "오류", "value": errors, "delta": "문제" if errors else None},
        ])
