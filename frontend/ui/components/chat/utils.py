"""Utility helpers formerly located in chatting.py.
This module purposefully keeps *no* Streamlit code except session‑state reads/writes,
so that it can be imported safely from anywhere (including background jobs).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Tuple

import logging
import streamlit as st

from frontend.ui.core.config import Constants, config
from frontend.ui.utils.error_handler import ErrorContext

# Optional managers — they may be stubbed in certain deployment variants
try:
    from frontend.ui.utils.model_manager import ModelManager  # type: ignore

    HAS_MODEL_MANAGER = True
except ImportError:  # pragma: no cover – shipped without ModelManager
    ModelManager = None  # type: ignore
    HAS_MODEL_MANAGER = False

try:
    from frontend.ui.utils.system_health import SystemHealthManager  # type: ignore

    HAS_SYSTEM_HEALTH = True
except ImportError:  # pragma: no cover – offline variant
    SystemHealthManager = None  # type: ignore
    HAS_SYSTEM_HEALTH = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model‑setting helpers
# ---------------------------------------------------------------------------

def get_model_settings() -> Dict[str, Any]:
    """Central place to obtain the *current, validated* model settings.

    Falls back to session‑state when ModelManager is unavailable.
    Mirrors the original logic in *chatting.py* but de‑globbed.
    """

    if HAS_MODEL_MANAGER:
        try:
            return ModelManager.get_settings_dict()
        except Exception as exc:  # pragma: no cover – validation error surfaced to caller
            logger.exception("ModelManager settings failure: %s", exc)

    # -------------------- fallback --------------------
    ss = st.session_state
    return {
        "model": ss.get("selected_model"),
        "temperature": ss.get("temperature", Constants.Defaults.TEMPERATURE),
        "system_prompt": ss.get("system_prompt", Constants.Defaults.SYSTEM_PROMPT),
        "rag_top_k": ss.get("rag_top_k", Constants.Defaults.TOP_K),
        "min_similarity": ss.get("min_similarity", Constants.Defaults.MIN_SIMILARITY),
        "rag_timeout": ss.get("rag_timeout", config.api.timeout),
        "api_timeout": ss.get("api_timeout", config.api.timeout),
        "max_tokens": ss.get("max_tokens", Constants.Defaults.MAX_TOKENS),
        "top_p": ss.get("top_p", 0.9),
        "frequency_penalty": ss.get("frequency_penalty", 0.0),
        "context_window": ss.get("context_window", Constants.Defaults.CONTEXT_WINDOW),
        "search_type": ss.get("search_type", Constants.Defaults.SEARCH_TYPE),
    }


def check_model_availability(api_client) -> Tuple[bool, str | None]:
    """Return (is_available, error_msg). Extracted from legacy *chatting.py*."""

    from frontend.ui.utils.error_handler import ErrorContext  # local import to avoid cycles

    with ErrorContext("모델 가용성 확인", show_errors=False) as ctx:
        try:
            # 1) Ask ModelManager first (fast)
            if HAS_MODEL_MANAGER:
                ready, msg = ModelManager.is_model_ready()  # type: ignore[arg-type]
                if not ready:
                    return False, msg

            # 2) System‑wide health check
            if HAS_SYSTEM_HEALTH:
                return SystemHealthManager.check_model_availability(api_client)

            # 3) Naïve check via API
            available = api_client.get_available_models()
            selected = st.session_state.get("selected_model")

            if not available:
                return False, "사용 가능한 모델이 없습니다. Ollama 서버를 확인하세요."
            if not selected:
                return False, "모델이 선택되지 않았습니다. 설정 페이지에서 모델을 선택하세요."
            if selected not in available:
                return False, f"선택된 모델 '{selected}'을(를) 찾을 수 없습니다."

            return True, None
        except Exception as exc:  # pragma: no cover – unexpected
            ctx.add_error(exc)
            return False, f"모델 상태 확인 실패: {exc}"


# Minimal loading helpers retained for convenience

def show_simple_loading(message: str, placeholder=None):
    if placeholder:
        with placeholder.container():
            st.info(f"⏳ {message}")
    else:
        st.info(f"⏳ {message}")


def clear_loading(placeholder):
    if placeholder:
        placeholder.empty()
