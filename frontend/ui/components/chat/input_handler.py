"""Handles user input & triggers RAG calls."""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Dict

import streamlit as st

from frontend.ui.core.config import Constants
from frontend.ui.utils.error_handler import ErrorContext
from frontend.ui.components.common import ErrorDisplay
from frontend.ui.utils.streamlit_helpers import rerun

from .history import ChatHistory
from .utils import get_model_settings, check_model_availability, show_simple_loading, clear_loading

try:
    from frontend.ui.utils.model_manager import ModelManager  # type: ignore
    HAS_MODEL_MANAGER = True
except ImportError:
    ModelManager = None  # type: ignore
    HAS_MODEL_MANAGER = False

logger = logging.getLogger(__name__)


class ChatInputHandler:
    """Encapsulates *handle_chat_input* logic for composability."""

    def __init__(self, api_client):
        self.api_client = api_client
        self.history = ChatHistory()

    # --------------------------------------------------------------
    # Public entry point
    # --------------------------------------------------------------
    def render_input(self) -> bool:
        """Render Streamlit chat‑input widget, returns *True* if interaction occurred."""
        ok, err_msg = check_model_availability(self.api_client)
        if not ok:
            ErrorDisplay.render_error_with_suggestions(
                err_msg,
                [
                    "설정 페이지에서 모델을 선택하세요",
                    "Ollama 서버가 실행 중인지 확인하세요",
                    "시스템 상태를 확인하세요",
                ],
            )
            return False

        if prompt := st.chat_input("질문을 입력하세요..."):
            # --- user message immediately added
            self.history.add("user", prompt)

            # --- obtain fresh settings
            with ErrorContext("모델 설정 조회") as ctx:
                try:
                    settings = get_model_settings()
                except Exception as exc:
                    ctx.add_error(exc)
                    return False

            # --- re‑check model availability just before API call
            re_ok, re_err = check_model_availability(self.api_client)
            if not re_ok:
                ErrorDisplay.render_error_with_suggestions(re_err, ["잠시 후 다시 시도해보세요"])
                return False

            # --- call backend (sync for now)
            with st.chat_message("assistant"):
                answer_placeholder = st.empty()
                status = st.empty()

                show_simple_loading(f"🤖 '{settings['model']}'으로 답변 생성 중...", status)

                with ErrorContext("RAG 답변 생성") as ctx:
                    try:
                        params = self._compose_params(prompt, settings)
                        result = self.api_client.generate_answer(**params)  # type: ignore[arg-type]

                        clear_loading(status)

                        if "error" in result:
                            self._handle_error(result["error"], settings["model"], answer_placeholder)
                            return True

                        answer = result.get("answer", "응답을 생성할 수 없습니다.")
                        answer_placeholder.markdown(answer)
                        self.history.add(
                            "assistant",
                            answer,
                            model_used=settings["model"],
                            sources=result.get("sources", []),
                            search_info=result.get("search_info", {}),
                            settings_used={
                                "temperature": settings["temperature"],
                                "top_k": settings["rag_top_k"],
                                "min_similarity": settings["min_similarity"],
                                "search_type": settings["search_type"],
                            },
                        )
                    except Exception as exc:
                        clear_loading(status)
                        answer_placeholder.empty()
                        ctx.add_error(exc)
                        self._handle_error(str(exc), settings["model"], answer_placeholder)

            rerun()  # immediate UI refresh so that new messages appear
            return True
        return False

    # --------------------------------------------------------------
    # Internals
    # --------------------------------------------------------------
    def _compose_params(self, prompt: str, settings: Dict[str, Any]):
        if HAS_MODEL_MANAGER:
            base = {"query": prompt}
            return ModelManager.apply_to_api_request(base)
        return {
            "query": prompt,
            "model": settings["model"],
            "temperature": settings["temperature"],
            "system_prompt": settings["system_prompt"],
            "top_k": settings["rag_top_k"],
            "min_score": settings["min_similarity"],
            "search_type": settings["search_type"],
            "timeout": settings["rag_timeout"],
        }

    def _handle_error(self, error_msg: str, model: str, placeholder):
        from frontend.ui.utils.error_handler import handle_api_error

        placeholder.empty()
        handle_api_error(error_msg, model_used=model)
