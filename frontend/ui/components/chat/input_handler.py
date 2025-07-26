"""Handles user input & triggers RAG calls."""
from __future__ import annotations

import re  # 🔧 누락된 import 추가
import time  # 🔧 추가
from datetime import datetime
import logging
from typing import Any, Dict, List

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
        # 🔧 모델 가용성 체크 최적화 (캐시 활용)
        if 'model_check_cache' not in st.session_state:
            st.session_state.model_check_cache = {}

        cache_key = "model_availability_input"
        cache_data = st.session_state.model_check_cache.get(cache_key)

        current_time = time.time()
        if (cache_data and
            current_time - cache_data.get('timestamp', 0) < 10):
            ok, err_msg = cache_data['result']
        else:
            ok, err_msg = check_model_availability(self.api_client)
            st.session_state.model_check_cache[cache_key] = {
                'result': (ok, err_msg),
                'timestamp': current_time
            }

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

            # --- call backend (sync for now)
            with st.chat_message("assistant"):
                answer_placeholder = st.empty()
                status = st.empty()

                show_simple_loading(f"🤖 '{settings['model']}'으로 답변 생성 중...", status)

                with ErrorContext("RAG 답변 생성") as ctx:
                    try:
                        params = self._compose_enhanced_params(prompt, settings)
                        result = self.api_client.generate_answer(**params)  # type: ignore[arg-type]

                        clear_loading(status)

                        if "error" in result:
                            self._handle_error(result["error"], settings["model"], answer_placeholder)
                            return True

                        answer = result.get("answer", "응답을 생성할 수 없습니다.")
                        sources = result.get("sources", [])
                        search_info = result.get("search_info", {})

                        # 🔧 근거 메타데이터 강화 (enhanced_sources 정의)
                        enhanced_sources = self._enhance_source_metadata(sources, prompt)

                        # 🚀 인터랙티브 레퍼런스 시스템 적용
                        try:
                            from .reference_system import reference_system
                            HAS_REFERENCE_SYSTEM = True
                        except ImportError:
                            reference_system = None
                            HAS_REFERENCE_SYSTEM = False

                        if answer and answer.strip():
                            if HAS_REFERENCE_SYSTEM and reference_system and enhanced_sources:
                                # 🚀 CSS 전용 레퍼런스 시스템 사용 (호버 미리보기 포함)
                                message_id = f"msg_{datetime.now().timestamp()}"
                                referenced_answer = reference_system.render_interactive_answer(
                                    answer, enhanced_sources, message_id, answer_placeholder
                                )
                            else:
                                # 기본 렌더링 (레퍼런스 시스템 없음)
                                answer_placeholder.markdown(answer)
                        else:
                            answer_placeholder.warning("⚠️ 빈 응답이 반환되었습니다.")
                            answer = "죄송합니다. 응답을 생성할 수 없었습니다."

                        # 🔧 히스토리 추가 전 디버깅
                        logger.info(f"답변 길이: {len(answer)}, 근거 수: {len(enhanced_sources)}")

                        self.history.add(
                            "assistant",
                            answer,
                            model_used=settings["model"],
                            sources=enhanced_sources,
                            search_info=search_info,
                            query_metadata={
                                "original_query": prompt,
                                "query_length": len(prompt),
                                "query_language": self._detect_language(prompt),
                                "query_keywords": self._extract_keywords(prompt),
                                "response_time": search_info.get("processing_time", 0),
                                "total_sources_found": len(sources),
                                "high_confidence_sources": len([s for s in enhanced_sources
                                                               if s.get("confidence", 0) >= 0.7])
                            },
                            settings_used={
                                "temperature": settings["temperature"],
                                "top_k": settings["rag_top_k"],
                                "min_similarity": settings["min_similarity"],
                                "search_type": settings["search_type"],
                                "enhanced_metadata": True
                            },
                        )
                    except Exception as exc:
                        clear_loading(status)
                        answer_placeholder.empty()
                        ctx.add_error(exc)
                        model = settings.get('model', 'unknown')
                        self._handle_error(str(exc), model, answer_placeholder)

            rerun()  # immediate UI refresh so that new messages appear
            return True
        return False

    # --------------------------------------------------------------
    # Enhanced parameter composition
    # --------------------------------------------------------------
    def _compose_enhanced_params(self, prompt: str, settings: Dict[str, Any]) -> Dict:
        """상세한 근거 정보를 위한 매개변수 구성"""
        base_params = {
            "query": prompt,
            "model": settings["model"],
            "temperature": settings["temperature"],
            "system_prompt": settings["system_prompt"],
            "top_k": settings["rag_top_k"],
            "min_score": settings["min_similarity"],
            "search_type": settings["search_type"],
            "timeout": settings["rag_timeout"],

            # 강화된 근거 요청 매개변수
            "include_metadata": True,
            "include_citations": True,
            "include_confidence_scores": True,
            "extract_keywords": True,
            "highlight_relevant_text": True,
            "return_search_details": True,

            # 근거 품질 향상 옵션
            "deduplicate_sources": True,
            "rank_by_relevance": True,
            "min_content_length": 50,
            "max_content_length": 2000,

            # 메타데이터 요청
            "metadata_fields": [
                "title", "section", "page", "author",
                "created_date", "document_type", "file_path"
            ]
        }

        # 모델 매니저 적용
        if HAS_MODEL_MANAGER:
            return ModelManager.apply_to_api_request(base_params)

        return base_params

    def _enhance_source_metadata(self, sources: List[Dict], query: str) -> List[Dict]:
        """소스 메타데이터 강화"""
        enhanced_sources = []

        query_keywords = self._extract_keywords(query)

        for source in sources:
            enhanced_source = source.copy()
            content = source.get("content", "")

            # 키워드 매칭 정보 추가
            enhanced_source["keywords"] = query_keywords
            enhanced_source["keyword_matches"] = self._count_keyword_matches(content, query_keywords)

            # 콘텐츠 메트릭 추가
            enhanced_source["content_metrics"] = {
                "length": len(content),
                "sentences": len(content.split('. ')) if content else 0,
                "has_numbers": bool(re.search(r'\d+', content)),
                "has_korean": bool(re.search(r'[가-힣]', content)),
                "readability_score": self._calculate_readability(content)
            }

            # 시간 정보 추가
            enhanced_source["processed_at"] = datetime.now().isoformat()

            # 관련성 점수 계산
            enhanced_source["relevance_factors"] = {
                "base_score": source.get("score", 0),
                "keyword_bonus": min(0.1, enhanced_source["keyword_matches"] * 0.02),
                "length_factor": self._calculate_length_factor(len(content)),
                "metadata_bonus": 0.05 if source.get("metadata") else 0
            }

            enhanced_sources.append(enhanced_source)

        return enhanced_sources

    def _extract_keywords(self, text: str) -> List[str]:
        """텍스트에서 주요 키워드 추출"""
        # 한글, 영문 단어 추출
        words = re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', text)

        # 불용어 제거
        stopwords = {
            '그리고', '하지만', '그러나', '따라서', '그래서', '또한', '또는',
            'and', 'but', 'however', 'therefore', 'also', 'or', 'the', 'is', 'are'
        }

        keywords = [word for word in words if word.lower() not in stopwords]

        # 빈도수 기준으로 정렬하여 상위 키워드만 반환
        from collections import Counter
        keyword_counts = Counter(keywords)

        return [word for word, count in keyword_counts.most_common(10)]

    def _count_keyword_matches(self, content: str, keywords: List[str]) -> int:
        """콘텐츠에서 키워드 매칭 횟수 계산"""
        if not keywords or not content:
            return 0

        content_lower = content.lower()
        matches = 0

        for keyword in keywords:
            matches += content_lower.count(keyword.lower())

        return matches

    def _calculate_readability(self, text: str) -> float:
        """텍스트 가독성 점수 계산 (단순화된 버전)"""
        if not text:
            return 0.0

        # 단순 메트릭: 평균 문장 길이의 역수
        sentences = text.split('. ')
        if not sentences:
            return 0.0

        avg_sentence_length = len(text) / len(sentences)

        # 적절한 문장 길이(50-150자)일 때 높은 점수
        if 50 <= avg_sentence_length <= 150:
            return 1.0
        elif avg_sentence_length < 50:
            return avg_sentence_length / 50
        else:
            return max(0.3, 150 / avg_sentence_length)

    def _calculate_length_factor(self, length: int) -> float:
        """콘텐츠 길이에 따른 보정 팩터"""
        if length < 50:
            return -0.1  # 너무 짧음
        elif 100 <= length <= 500:
            return 0.1   # 적절한 길이
        elif 500 < length <= 1000:
            return 0.05  # 긴 편
        else:
            return 0.0   # 매우 긺

    def _detect_language(self, text: str) -> str:
        """텍스트 언어 감지"""
        korean_chars = len(re.findall(r'[가-힣]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))

        total_chars = korean_chars + english_chars
        if total_chars == 0:
            return "unknown"

        korean_ratio = korean_chars / total_chars

        if korean_ratio > 0.5:
            return "korean"
        elif korean_ratio < 0.1:
            return "english"
        else:
            return "mixed"

    # --------------------------------------------------------------
    # Existing methods (unchanged)
    # --------------------------------------------------------------
    def _compose_params(self, prompt: str, settings: Dict[str, Any]):
        """기존 매개변수 구성 (하위 호환성)"""
        return self._compose_enhanced_params(prompt, settings)

    def _handle_error(self, error_msg: str, model: str, placeholder):
        from frontend.ui.utils.error_handler import error_handler, GTRagError, ErrorType, ErrorSeverity

        placeholder.empty()

        # 에러 메시지로부터 Exception 객체 생성
        try:
            # 모델 관련 에러인지 확인
            if "model" in error_msg.lower() or model:
                error_exception = GTRagError(
                    f"모델 '{model}' 처리 중 오류: {error_msg}",
                    error_type=ErrorType.MODEL_CONFIG,
                    severity=ErrorSeverity.MEDIUM,
                    suggestions=[
                        "설정 페이지에서 모델을 다시 선택하세요",
                        "Ollama 서버가 실행 중인지 확인하세요",
                        "잠시 후 다시 시도해보세요"
                    ]
                )
            else:
                # 일반적인 API 오류
                error_exception = Exception(error_msg)

            # 통합 에러 핸들러 사용
            error_handler.handle_error(error_exception, f"모델 '{model}' API 호출")

        except Exception as e:
            # 에러 처리 중 오류가 발생한 경우 기본 표시
            st.error(f"❌ 오류: {error_msg}")
            if model:
                st.info(f"사용된 모델: {model}")
            st.info("잠시 후 다시 시도해보세요.")