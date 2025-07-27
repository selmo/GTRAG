"""Main Chat UI orchestration."""
from __future__ import annotations

from typing import List

import streamlit as st
import time

from frontend.ui.core.config import Constants
from frontend.ui.components.common import ActionButton, StatusIndicator
from frontend.ui.utils.streamlit_helpers import rerun

from .history import ChatHistory
from .input_handler import ChatInputHandler
from .utils import check_model_availability
from .message_display import render_sources, calculate_overall_confidence  # exported for convenience

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
        self._render_enhanced_action_row()

        # Chat history
        if not self.history._ensure_list():
            st.info(f"{Constants.Icons.AI} 질문을 입력하여 대화를 시작하세요.")
            # self._render_feature_highlights()
        else:
            self.history.render()

        # Input widget
        self.input_handler.render_input()

        # Footer stats
        if self.history._ensure_list():
            st.divider()
            self.history.render_stats()

    # --------------------------------------------------------------
    # Enhanced internals
    # --------------------------------------------------------------
    def _render_header(self):
        """모델 가용성 체크 최적화"""
        # 🔧 세션 상태에 모델 상태 캐시
        if 'model_check_cache' not in st.session_state:
            st.session_state.model_check_cache = {}

        # 캐시된 결과가 있고 5초 이내라면 재사용
        cache_key = "model_availability"
        cache_data = st.session_state.model_check_cache.get(cache_key)

        current_time = time.time()
        if (cache_data and
                current_time - cache_data.get('timestamp', 0) < 5):
            ok, err = cache_data['result']
        else:
            # 새로 체크하고 캐시에 저장
            ok, err = check_model_availability(self.api_client)
            st.session_state.model_check_cache[cache_key] = {
                'result': (ok, err),
                'timestamp': current_time
            }

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


    def _render_enhanced_action_row(self):
        """강화된 액션 버튼 행"""
        actions = [
            {
                "label": f"{Constants.Icons.DELETE} 대화 초기화",
                "key": "clear_chat_main",
                "callback": self.history.clear,
                "type": "secondary",
            },
            {
                "label": f"{Constants.Icons.DOWNLOAD} 상세 내보내기",
                "key": "export_chat_main",
                "callback": self.history.export,
                "type": "secondary",
            },
        ]

        # 세션이 있는 경우 추가 액션
        if self.history._ensure_list():
            actions.extend([
                {
                    "label": "📊 세션 분석",
                    "key": "analyze_session",
                    "callback": self._show_session_analysis,
                    "type": "secondary",
                },
                {
                    "label": "🎯 근거 품질 검토",
                    "key": "review_sources",
                    "callback": self._review_source_quality,
                    "type": "secondary",
                }
            ])

        ActionButton.render_action_row(actions)

    def _render_feature_highlights(self):
        """새로운 기능 하이라이트"""
        st.markdown("### 🚀 강화된 기능")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("""
            **📊 구조화된 근거**
            - 신뢰도 점수 표시
            - 출처별 관련도 분석
            - 인용문 자동 추출
            """)

        with col2:
            st.markdown("""
            **🎯 인터랙티브 참조**
            - 클릭 가능한 출처
            - 확장/축소 가능한 상세 정보
            - 근거별 액션 버튼
            """)

        with col3:
            st.markdown("""
            **⚡ 스마트 필터링**
            - 신뢰도 기준 필터링
            - 관련도순 정렬
            - 품질 등급 분류
            """)

    def _show_session_analysis(self):
        """세션 분석 표시"""
        messages = self.history._ensure_list()
        assistant_msgs = [m for m in messages if m["role"] == "assistant" and m.get("sources")]

        if not assistant_msgs:
            st.info("분석할 근거가 있는 답변이 없습니다.")
            return

        st.success("📊 세션 분석을 시작합니다...")

        # 전체 근거 품질 분석
        all_sources = []
        for msg in assistant_msgs:
            all_sources.extend(msg.get("sources", []))

        if all_sources:
            overall_confidence = calculate_overall_confidence(all_sources)

            with st.expander("🎯 전체 근거 품질 분석", expanded=True):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("전체 근거 수", len(all_sources))
                    st.metric("평균 유사도", f"{sum(s.get('score', 0) for s in all_sources) / len(all_sources):.3f}")

                with col2:
                    st.metric("종합 신뢰도", f"{overall_confidence:.1%}")
                    high_quality = len([s for s in all_sources if calculate_overall_confidence([s]) >= 0.7])
                    st.metric("고품질 근거", f"{high_quality}/{len(all_sources)}")

                with col3:
                    unique_sources = len(set(s.get("source", "") for s in all_sources))
                    st.metric("고유 문서 수", unique_sources)
                    st.metric("문서 다양성", f"{unique_sources/len(all_sources):.1%}")

    def _review_source_quality(self):
        """근거 품질 검토"""
        messages = self.history._ensure_list()
        assistant_msgs = [m for m in messages if m["role"] == "assistant" and m.get("sources")]

        if not assistant_msgs:
            st.info("검토할 근거가 없습니다.")
            return

        st.success("🎯 근거 품질 검토를 시작합니다...")

        with st.expander("📋 답변별 근거 품질", expanded=True):
            for i, msg in enumerate(assistant_msgs, 1):
                sources = msg.get("sources", [])
                if not sources:
                    continue

                confidence = calculate_overall_confidence(sources)
                quality_info = msg.get("answer_quality", {})
                quality_grade = quality_info.get("overall_grade", "알 수 없음")

                # 품질에 따른 색상 표시
                if confidence >= 0.8:
                    st.success(f"**답변 {i}:** {quality_grade} (신뢰도: {confidence:.1%})")
                elif confidence >= 0.6:
                    st.info(f"**답변 {i}:** {quality_grade} (신뢰도: {confidence:.1%})")
                else:
                    st.warning(f"**답변 {i}:** {quality_grade} (신뢰도: {confidence:.1%})")

                # 개선 제안
                issues = quality_info.get("issues", [])
                if issues:
                    st.caption(f"개선 포인트: {', '.join(issues)}")

        # 전반적인 개선 권장사항
        self._provide_improvement_suggestions(assistant_msgs)

    def _provide_improvement_suggestions(self, assistant_msgs: List):
        """개선 권장사항 제공"""
        all_sources = []
        low_quality_count = 0

        for msg in assistant_msgs:
            sources = msg.get("sources", [])
            all_sources.extend(sources)

            confidence = calculate_overall_confidence(sources)
            if confidence < 0.6:
                low_quality_count += 1

        suggestions = []

        if low_quality_count > len(assistant_msgs) * 0.3:
            suggestions.append("📚 문서 품질을 개선하거나 더 관련성 높은 문서를 추가하세요")

        if all_sources:
            avg_score = sum(s.get("score", 0) for s in all_sources) / len(all_sources)
            if avg_score < 0.5:
                suggestions.append("🎯 검색 알고리즘 매개변수 조정을 고려하세요")

        unique_sources = len(set(s.get("source", "") for s in all_sources))
        if unique_sources < len(all_sources) * 0.5:
            suggestions.append("📈 문서 다양성을 높이기 위해 더 많은 출처를 확보하세요")

        if suggestions:
            with st.expander("💡 개선 권장사항", expanded=True):
                for suggestion in suggestions:
                    st.info(suggestion)