"""Chat history services."""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

import streamlit as st

from frontend.ui.core.config import Constants
from frontend.ui.components.common import MetricCard  # stats

from .message_display import render_sources, calculate_overall_confidence, get_source_quality_grade

# 🚀 인터랙티브 레퍼런스 시스템 적용
try:
    from .reference_system import reference_system

    HAS_REFERENCE_SYSTEM = True
except ImportError:
    reference_system = None
    HAS_REFERENCE_SYSTEM = False

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
    # Enhanced public helpers
    # ---------------------------------------------------------------------
    def add(self, role: str, content: str, **extra):
        """메시지 추가 (강화된 메타데이터 포함)"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "message_id": self._generate_message_id(),
            **extra,
        }

        # Assistant 메시지의 경우 추가 메타데이터 처리
        if role == "assistant":
            message = self._enhance_assistant_message(message)

        # User 메시지의 경우도 메타데이터 추가
        elif role == "user":
            message = self._enhance_user_message(message)

        self._ensure_list().append(message)

    def _generate_message_id(self) -> str:
        """고유한 메시지 ID 생성"""
        import uuid
        return str(uuid.uuid4())[:8]

    def _enhance_assistant_message(self, message: Dict) -> Dict:
        """Assistant 메시지 메타데이터 강화"""
        sources = message.get("sources", [])
        search_info = message.get("search_info", {})

        # 근거 품질 분석
        if sources:
            overall_confidence = calculate_overall_confidence(sources)
            quality_grade = get_source_quality_grade(overall_confidence)

            # 근거 통계
            source_stats = {
                "total_sources": len(sources),
                "avg_score": sum(s.get("score", 0) for s in sources) / len(sources),
                "max_score": max(s.get("score", 0) for s in sources),
                "min_score": min(s.get("score", 0) for s in sources),
                "overall_confidence": overall_confidence,
                "quality_grade": quality_grade,
                "high_confidence_count": len([s for s in sources if s.get("confidence", 0) >= 0.7]),
                "medium_confidence_count": len([s for s in sources if 0.4 <= s.get("confidence", 0) < 0.7]),
                "low_confidence_count": len([s for s in sources if s.get("confidence", 0) < 0.4])
            }

            # 소스 다양성 분석
            source_diversity = self._analyze_source_diversity(sources)

            message.update({
                "source_stats": source_stats,
                "source_diversity": source_diversity,
                "answer_quality": self._assess_answer_quality(message["content"], source_stats),
                "has_high_quality_sources": overall_confidence >= 0.7
            })

        # 검색 성능 메타데이터
        if search_info:
            message["search_performance"] = {
                "search_time": search_info.get("processing_time", 0),
                "search_efficiency": self._calculate_search_efficiency(search_info),
                "search_type_used": search_info.get("search_type", "unknown")
            }

        return message

    def _enhance_user_message(self, message: Dict) -> Dict:
        """User 메시지 메타데이터 강화"""
        content = message["content"]

        # 질문 분석
        question_analysis = {
            "length": len(content),
            "word_count": len(content.split()),
            "has_question_mark": "?" in content,
            "question_type": self._classify_question_type(content),
            "complexity_level": self._assess_question_complexity(content),
            "language": self._detect_content_language(content)
        }

        message["question_analysis"] = question_analysis
        return message

    def _analyze_source_diversity(self, sources: List[Dict]) -> Dict:
        """소스 다양성 분석"""
        if not sources:
            return {"diversity_score": 0, "unique_sources": 0, "source_types": []}

        # 고유한 소스 파일 수
        unique_sources = len(set(s.get("source", "") for s in sources))

        # 소스 타입 분석
        source_types = []
        for source in sources:
            metadata = source.get("metadata", {})
            doc_type = metadata.get("document_type", "unknown")
            if doc_type not in source_types:
                source_types.append(doc_type)

        # 다양성 점수 계산 (0~1)
        diversity_score = min(1.0, unique_sources / max(1, len(sources)))

        return {
            "diversity_score": diversity_score,
            "unique_sources": unique_sources,
            "total_sources": len(sources),
            "source_types": source_types,
            "type_diversity": len(source_types)
        }

    def _assess_answer_quality(self, answer: str, source_stats: Dict) -> Dict:
        """답변 품질 평가"""
        if not answer:
            return {"quality_score": 0, "issues": ["빈 답변"]}

        quality_factors = {
            "length_appropriate": 100 <= len(answer) <= 2000,
            "has_structure": any(marker in answer for marker in ["1.", "2.", "•", "-", "\n\n"]),
            "cites_sources": source_stats.get("total_sources", 0) > 0,
            "high_confidence_sources": source_stats.get("overall_confidence", 0) >= 0.6,
            "diverse_sources": source_stats.get("total_sources", 0) >= 2
        }

        quality_score = sum(quality_factors.values()) / len(quality_factors)

        # 품질 이슈 식별
        issues = []
        if not quality_factors["length_appropriate"]:
            if len(answer) < 100:
                issues.append("답변이 너무 짧음")
            else:
                issues.append("답변이 너무 길음")

        if not quality_factors["has_structure"]:
            issues.append("구조화되지 않은 답변")

        if not quality_factors["high_confidence_sources"]:
            issues.append("낮은 신뢰도의 근거")

        if not quality_factors["diverse_sources"]:
            issues.append("제한적인 근거 다양성")

        return {
            "quality_score": quality_score,
            "quality_factors": quality_factors,
            "issues": issues,
            "overall_grade": self._get_quality_grade(quality_score)
        }

    def _get_quality_grade(self, score: float) -> str:
        """품질 점수를 등급으로 변환"""
        if score >= 0.9:
            return "A+ (우수)"
        elif score >= 0.8:
            return "A (좋음)"
        elif score >= 0.7:
            return "B+ (양호)"
        elif score >= 0.6:
            return "B (보통)"
        elif score >= 0.5:
            return "C+ (미흡)"
        else:
            return "C (개선 필요)"

    def _calculate_search_efficiency(self, search_info: Dict) -> float:
        """검색 효율성 계산"""
        search_time = search_info.get("processing_time", 0)
        total_candidates = search_info.get("total_candidates", 0)

        if search_time == 0 or total_candidates == 0:
            return 0.0

        # 단위 시간당 처리된 후보 수 기준 효율성
        efficiency = min(1.0, total_candidates / (search_time * 100))
        return efficiency

    def _classify_question_type(self, content: str) -> str:
        """질문 유형 분류"""
        content_lower = content.lower()

        if any(word in content_lower for word in ["무엇", "what", "정의", "뜻"]):
            return "정의형"
        elif any(word in content_lower for word in ["어떻게", "how", "방법"]):
            return "방법형"
        elif any(word in content_lower for word in ["왜", "why", "이유", "원인"]):
            return "이유형"
        elif any(word in content_lower for word in ["언제", "when", "시기"]):
            return "시간형"
        elif any(word in content_lower for word in ["어디", "where", "장소"]):
            return "장소형"
        elif any(word in content_lower for word in ["누구", "who"]):
            return "인물형"
        elif content.endswith("?"):
            return "일반 질문"
        else:
            return "요청형"

    def _assess_question_complexity(self, content: str) -> str:
        """질문 복잡도 평가"""
        complexity_indicators = {
            "길이": len(content) > 100,
            "다중_주제": len(content.split("그리고")) > 1 or len(content.split("또한")) > 1,
            "조건부": any(word in content for word in ["만약", "경우", "상황", "조건"]),
            "비교": any(word in content for word in ["비교", "차이", "다른", "같은"]),
            "분석": any(word in content for word in ["분석", "평가", "검토", "판단"])
        }

        complexity_score = sum(complexity_indicators.values())

        if complexity_score >= 3:
            return "복잡"
        elif complexity_score >= 1:
            return "보통"
        else:
            return "단순"

    def _detect_content_language(self, content: str) -> str:
        """콘텐츠 언어 감지"""
        # 🔧 로컬 import 제거 (상단에서 이미 import됨)
        korean_chars = len(re.findall(r'[가-힣]', content))
        english_chars = len(re.findall(r'[a-zA-Z]', content))

        total_chars = korean_chars + english_chars
        if total_chars == 0:
            return "기타"

        korean_ratio = korean_chars / total_chars

        if korean_ratio > 0.7:
            return "한국어"
        elif korean_ratio < 0.3:
            return "영어"
        else:
            return "혼합"

    def clear(self):
        """대화 내역 초기화"""
        if self._ensure_list():
            # 삭제 전 통계 저장
            stats = self._calculate_session_stats()

            st.session_state[self._SS_KEY] = []
            st.success(f"{Constants.Icons.STATUS_OK} 대화 내역이 초기화되었습니다.")

            # 세션 통계 표시
            if stats["total_messages"] > 0:
                st.info(f"삭제된 세션 통계: {stats['summary_text']}")
        else:
            st.info("초기화할 대화 내역이 없습니다.")

    def export(self):
        """향상된 내보내기 기능"""
        messages = self._ensure_list()
        if not messages:
            st.info("내보낼 대화 내역이 없습니다.")
            return

        # 세션 통계 계산
        session_stats = self._calculate_session_stats()

        # 내보내기 데이터 구성
        export_data = {
            "export_metadata": {
                "exported_at": datetime.now().isoformat(),
                "export_version": "2.0",
                "total_messages": len(messages),
                "session_stats": session_stats
            },
            "messages": messages,
            "session_summary": self._generate_session_summary()
        }

        # JSON 형식으로 내보내기
        json_data = json.dumps(export_data, ensure_ascii=False, indent=2)

        st.download_button(
            label=f"{Constants.Icons.DOWNLOAD} 대화 내역 다운로드 (상세 버전)",
            data=json_data,
            file_name=f"gtone_chat_enhanced_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )

    def _calculate_session_stats(self) -> Dict:
        """세션 통계 계산"""
        messages = self._ensure_list()

        if not messages:
            return {"total_messages": 0, "summary_text": "메시지 없음"}

        total = len(messages)
        user_msgs = [m for m in messages if m["role"] == "user"]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]

        # 근거 통계
        total_sources = sum(len(m.get("sources", [])) for m in assistant_msgs)
        high_quality_responses = sum(1 for m in assistant_msgs
                                   if m.get("has_high_quality_sources", False))

        # 평균 응답 시간
        response_times = [m.get("search_performance", {}).get("search_time", 0)
                         for m in assistant_msgs]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        # 질문 복잡도 분석
        complex_questions = sum(1 for m in user_msgs
                              if m.get("question_analysis", {}).get("complexity_level") == "복잡")

        summary_text = (f"질문 {len(user_msgs)}개, 답변 {len(assistant_msgs)}개, "
                       f"고품질 답변 {high_quality_responses}개, "
                       f"평균 응답시간 {avg_response_time:.1f}초")

        return {
            "total_messages": total,
            "user_messages": len(user_msgs),
            "assistant_messages": len(assistant_msgs),
            "total_sources_used": total_sources,
            "high_quality_responses": high_quality_responses,
            "avg_response_time": avg_response_time,
            "complex_questions": complex_questions,
            "summary_text": summary_text
        }

    def _generate_session_summary(self) -> Dict:
        """세션 요약 생성"""
        messages = self._ensure_list()
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]

        if not assistant_msgs:
            return {"summary": "대화 없음"}

        # 주요 주제 추출
        all_keywords = []
        for msg in assistant_msgs:
            sources = msg.get("sources", [])
            for source in sources:
                keywords = source.get("keywords", [])
                all_keywords.extend(keywords)

        from collections import Counter
        top_keywords = Counter(all_keywords).most_common(10)

        # 품질 분포
        quality_grades = [m.get("answer_quality", {}).get("overall_grade", "알 수 없음")
                         for m in assistant_msgs]
        quality_distribution = Counter(quality_grades)

        return {
            "top_keywords": top_keywords,
            "quality_distribution": dict(quality_distribution),
            "conversation_flow": self._analyze_conversation_flow()
        }

    def _analyze_conversation_flow(self) -> Dict:
        """대화 흐름 분석"""
        messages = self._ensure_list()
        user_msgs = [m for m in messages if m["role"] == "user"]

        if not user_msgs:
            return {"flow_type": "없음"}

        # 질문 유형 분포
        question_types = [m.get("question_analysis", {}).get("question_type", "알 수 없음")
                         for m in user_msgs]

        from collections import Counter
        type_distribution = Counter(question_types)

        # 복잡도 변화
        complexities = [m.get("question_analysis", {}).get("complexity_level", "알 수 없음")
                       for m in user_msgs]

        return {
            "question_type_distribution": dict(type_distribution),
            "complexity_progression": complexities,
            "total_exchanges": len(user_msgs)
        }

    # ---------------------------------------------------------------------
    # Enhanced UI helpers
    # ---------------------------------------------------------------------
    def render(self):
        """강화된 메시지 렌더링 - 인터랙티브 레퍼런스 지원"""
        messages = self._ensure_list()

        for idx, msg in enumerate(messages):
            with st.chat_message(msg["role"]):
                if msg["role"] == "user":
                    # 사용자 메시지는 기본 렌더링
                    st.markdown(msg["content"])

                elif msg["role"] == "assistant":
                    # 🚀 Assistant 메시지에 인터랙티브 레퍼런스 적용
                    content = msg["content"]
                    sources = msg.get("sources", [])

                    if HAS_REFERENCE_SYSTEM and reference_system and sources:
                        # 레퍼런스가 포함된 답변 렌더링
                        message_id = msg.get("message_id", f"history_msg_{idx}")

                        # 이미 레퍼런스가 삽입된 내용인지 확인
                        if "[[" in content and "](#ref-" in content:
                            # 이미 레퍼런스가 있는 경우 그대로 렌더링
                            st.markdown(content, unsafe_allow_html=True)
                        else:
                            # 레퍼런스 시스템으로 처리
                            reference_system.render_interactive_answer(content, sources, message_id)
                    else:
                        # 레퍼런스 시스템 없거나 소스 없는 경우 기본 렌더링
                        st.markdown(content)

                    # Assistant 메시지의 추가 메타데이터 표시
                    self._render_assistant_metadata(msg)

                    # 근거 표시 (새로운 시스템 사용)
                    if "sources" in msg:
                        render_sources(
                            msg["sources"],
                            msg.get("search_info")
                        )

    def _render_assistant_metadata(self, msg: Dict):
        """Assistant 메시지 메타데이터 렌더링"""
        # 간단한 품질 지표 표시
        if quality_info := msg.get("answer_quality"):
            quality_grade = quality_info.get("overall_grade", "알 수 없음")
            quality_score = quality_info.get("quality_score", 0)

            if quality_score >= 0.7:
                st.success(f"✨ 답변 품질: {quality_grade}")
            elif quality_score >= 0.5:
                st.info(f"📊 답변 품질: {quality_grade}")
            else:
                st.warning(f"⚠️ 답변 품질: {quality_grade}")

    def render_stats(self):
        """강화된 통계 표시"""
        msgs = self._ensure_list()
        if not msgs:
            return

        # 기본 통계
        session_stats = self._calculate_session_stats()

        # 메트릭 카드 표시
        MetricCard.render_metric_grid([
            {"title": "총 메시지", "value": session_stats["total_messages"]},
            {"title": "질문", "value": session_stats["user_messages"]},
            {"title": "답변", "value": session_stats["assistant_messages"]},
            {"title": "고품질 답변", "value": session_stats["high_quality_responses"],
             "delta": f"{session_stats['high_quality_responses']}/{session_stats['assistant_messages']}"
             if session_stats["assistant_messages"] > 0 else None},
        ])

        # 상세 통계 (확장 가능)
        with st.expander("📈 상세 세션 통계", expanded=False):
            col1, col2 = st.columns(2)

            with col1:
                st.metric("전체 활용 근거", session_stats["total_sources_used"])
                st.metric("복잡한 질문", session_stats["complex_questions"])

            with col2:
                st.metric("평균 응답시간", f"{session_stats['avg_response_time']:.1f}초")

                # 품질 분포 차트
                if session_stats["assistant_messages"] > 0:
                    quality_rate = session_stats["high_quality_responses"] / session_stats["assistant_messages"]
                    st.metric("고품질 답변 비율", f"{quality_rate:.1%}")