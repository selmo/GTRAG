"""Functions responsible solely for rendering message‑related UI bits."""
from __future__ import annotations

from typing import Dict, List
import streamlit as st

from frontend.ui.core.config import Constants, config

try:
    from frontend.ui.utils.file_utils import FileNameCleaner  # type: ignore

    HAS_FILE_UTILS = True
except ImportError:
    HAS_FILE_UTILS = False

__all__ = ["render_sources"]


def _score_to_emoji(score: float) -> str:
    if score >= 0.8:
        return "🟢"
    if score >= 0.6:
        return "🟡"
    return "🔴"


def render_sources(sources: List[Dict]):
    """Pretty‑print reference documents inside an expander."""
    if not sources:
        return

    with st.expander(f"{Constants.Icons.DOCUMENT} 참조 문서 ({len(sources)}개)", expanded=False):
        for idx, source in enumerate(sources, 1):
            score = source.get("score", 0)
            raw_name = source.get("source", "Unknown")
            name = FileNameCleaner.clean_display_name(raw_name) if HAS_FILE_UTILS else raw_name
            content = source.get("content", "")

            st.write(f"{_score_to_emoji(score)} **[문서 {idx}] {name}** (유사도: {score:.3f})")

            preview_len = min(config.ui.max_file_preview_length, 300)
            if len(content) > preview_len:
                preview = content[:preview_len] + "..."
                st.text(preview)
                if st.button("📖 전체 내용 보기", key=f"show_full_{idx}"):
                    st.text_area("전체 내용", content, height=240, key=f"content_{idx}")
            else:
                st.text(content)

            if idx < len(sources):
                st.divider()
