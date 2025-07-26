"""
고급 인터랙티브 레퍼런스 시스템 - 최종 완성 버전
- CSS 전용 호버 미리보기 (JavaScript 불필요)
- 스마트 레퍼런스 삽입
- 탭 기반 소스 카드 렌더링
- Streamlit 완전 호환
"""
import re
import json
from typing import Dict, List, Tuple, Optional
import streamlit as st
from datetime import datetime


class InteractiveReferenceSystem:
    """인터랙티브 레퍼런스 시스템 메인 클래스"""

    def __init__(self):
        self.reference_patterns = [
            # 인용 패턴들
            r'(따르면|의하면|에서는|에 따르면|문서에서|자료에서)',
            r'(보고서|문서|자료|연구|조사|분석)에서',
            r'(설명|언급|기술|서술|명시)된?(바와 같이|대로)',
            r'(참고|참조|확인)하면',
        ]

    def insert_smart_references(self, answer: str, sources: List[Dict]) -> str:
        """문맥에 맞는 스마트 레퍼런스 삽입"""
        if not sources or not answer:
            return answer

        # 문장 단위로 분할
        sentences = self._split_into_sentences(answer)

        # 각 문장에 대해 최적의 레퍼런스 찾기
        referenced_answer = ""
        used_references = set()

        for sentence in sentences:
            best_ref_idx = self._find_best_reference(sentence, sources, used_references)

            if best_ref_idx is not None:
                referenced_sentence = self._insert_reference(sentence, best_ref_idx + 1)
                used_references.add(best_ref_idx)
            else:
                referenced_sentence = sentence

            referenced_answer += referenced_sentence + " "

        return referenced_answer.strip()

    def _split_into_sentences(self, text: str) -> List[str]:
        """텍스트를 문장 단위로 분할"""
        # 한국어 문장 분할 패턴
        pattern = r'[.!?](?=\s|$)|[。！？](?=\s|$)'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]

    def _find_best_reference(self, sentence: str, sources: List[Dict], used_refs: set) -> Optional[int]:
        """문장에 가장 적합한 레퍼런스 찾기"""
        best_score = 0
        best_idx = None

        for idx, source in enumerate(sources):
            if idx in used_refs:
                continue

            score = self._calculate_relevance_score(sentence, source)

            if score > best_score and score > 0.3:  # 최소 임계값
                best_score = score
                best_idx = idx

        return best_idx

    def _calculate_relevance_score(self, sentence: str, source: Dict) -> float:
        """문장과 소스의 관련성 점수 계산"""
        content = source.get("content", "").lower()
        sentence_lower = sentence.lower()

        # 키워드 매칭 점수
        keyword_score = 0
        sentence_words = set(re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', sentence_lower))
        content_words = set(re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', content))

        if sentence_words and content_words:
            common_words = sentence_words.intersection(content_words)
            keyword_score = len(common_words) / len(sentence_words)

        # 패턴 매칭 점수 (인용 표현 포함 여부)
        pattern_score = 0
        for pattern in self.reference_patterns:
            if re.search(pattern, sentence_lower):
                pattern_score = 0.3
                break

        # 기본 소스 점수
        base_score = source.get("score", 0) * 0.3

        return keyword_score * 0.5 + pattern_score + base_score

    def _insert_reference(self, sentence: str, ref_num: int) -> str:
        """문장에 레퍼런스 삽입 - CSS 호환 버전"""
        # 임시 마커 사용 (나중에 CSS 버전으로 변환됨)
        ref_marker = f'[{ref_num}]'

        if sentence.endswith('.'):
            return f"{sentence[:-1]} {ref_marker}."
        else:
            return f"{sentence} {ref_marker}"

    def render_interactive_answer(self, answer: str, sources: List[Dict], message_id: str = None, placeholder=None):
        """CSS 전용 호버 미리보기 - Streamlit 호환 버전"""
        if not message_id:
            message_id = f"msg_{datetime.now().timestamp()}"

        # 스마트 레퍼런스 삽입
        referenced_answer = self.insert_smart_references(answer, sources)

        # CSS 전용 스타일 먼저 적용
        self._render_css_only_styles()

        # 레퍼런스를 CSS 호환 형태로 변환
        enhanced_answer = self._convert_to_css_references(referenced_answer, sources)

        # 답변 렌더링
        if placeholder:
            placeholder.markdown(enhanced_answer, unsafe_allow_html=True)
        else:
            st.markdown(enhanced_answer, unsafe_allow_html=True)

        return enhanced_answer

    def _render_css_only_styles(self):
        """CSS 전용 스타일 (JavaScript 불필요)"""
        st.markdown("""
        <style>
        /* 🎯 CSS 전용 참조 링크 with 호버 미리보기 */
        .css-ref-link {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            text-decoration: none !important;
            padding: 3px 8px !important;
            border-radius: 12px !important;
            font-size: 0.85em !important;
            font-weight: bold !important;
            margin: 0 3px !important;
            display: inline-block !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 2px 6px rgba(102, 126, 234, 0.4) !important;
            cursor: pointer !important;
            position: relative !important;
        }
        
        .css-ref-link:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 16px rgba(102, 126, 234, 0.6) !important;
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%) !important;
        }
        
        /* 🎨 CSS 전용 툴팁 - 호버시 표시 */
        .css-ref-link::before {
            content: attr(data-tooltip) !important;
            position: absolute !important;
            bottom: 100% !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            background: white !important;
            border: 2px solid #667eea !important;
            border-radius: 10px !important;
            padding: 15px !important;
            min-width: 280px !important;
            max-width: 400px !important;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2) !important;
            z-index: 9999 !important;
            opacity: 0 !important;
            visibility: hidden !important;
            transition: all 0.3s ease !important;
            margin-bottom: 10px !important;
            font-size: 0.9em !important;
            font-weight: normal !important;
            color: #333 !important;
            line-height: 1.6 !important;
            white-space: pre-line !important;
            text-align: left !important;
        }
        
        .css-ref-link:hover::before {
            opacity: 1 !important;
            visibility: visible !important;
        }
        
        /* 🔻 툴팁 화살표 */
        .css-ref-link::after {
            content: '' !important;
            position: absolute !important;
            bottom: 100% !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            border: 8px solid transparent !important;
            border-top: 8px solid #667eea !important;
            opacity: 0 !important;
            visibility: hidden !important;
            transition: all 0.3s ease !important;
            margin-bottom: 2px !important;
        }
        
        .css-ref-link:hover::after {
            opacity: 1 !important;
            visibility: visible !important;
        }
        
        /* 📱 반응형 디자인 */
        @media (max-width: 768px) {
            .css-ref-link::before {
                min-width: 250px !important;
                max-width: 320px !important;
                font-size: 0.85em !important;
                padding: 12px !important;
            }
        }
        </style>
        """, unsafe_allow_html=True)

    def _convert_to_css_references(self, answer: str, sources: List[Dict]) -> str:
        """참조 링크를 CSS 전용 버전으로 변환"""
        # 각 소스에 대해 CSS 참조 링크 생성
        for i, source in enumerate(sources, 1):
            # 툴팁 텍스트 생성
            tooltip_text = self._generate_tooltip_text(source, i)

            # HTML 이스케이프
            tooltip_escaped = tooltip_text.replace('"', '&quot;').replace('\n', '&#10;')

            # 기존 참조 패턴들을 CSS 버전으로 교체
            patterns = [
                f'<a href="#ref-{i}" class="reference-link" data-ref="{i}"[^>]*>\\[{i}\\]</a>',
                f'<span class="reference-link" data-ref="{i}"[^>]*>\\[{i}\\]</span>',
                f'\\[{i}\\]'  # 단순 텍스트 패턴
            ]

            css_link = f'<span class="css-ref-link" data-tooltip="{tooltip_escaped}" data-ref="{i}">[{i}]</span>'

            for pattern in patterns:
                answer = re.sub(pattern, css_link, answer)

        return answer

    def _generate_tooltip_text(self, source: Dict, ref_num: int) -> str:
        """툴팁 텍스트 생성"""
        title = source.get('source', f'문서 {ref_num}')
        content = source.get('content', '')
        score = source.get('score', 0)
        confidence = source.get('confidence', source.get('score', 0) * 0.9)  # 기본값 설정

        # 내용 요약 (120자 제한)
        if len(content) > 120:
            content_preview = content[:120] + "..."
        else:
            content_preview = content

        # 이모지와 함께 구조화된 툴팁
        tooltip = f"""📄 {title}

💬 내용:
{content_preview}

📊 품질 정보:
• 유사도: {score:.1%}
• 신뢰도: {int(confidence * 100)}%

💡 클릭하면 상세 내용으로 이동합니다"""

        return tooltip

    def render_enhanced_sources(self, sources: List[Dict], search_info: Optional[Dict] = None):
        """향상된 근거 표시 (탭 기반, expander 중첩 문제 해결)"""
        if not sources:
            return

        # 검색 정보 표시
        if search_info:
            self._render_search_summary(search_info)

        # 소스 카드들 렌더링
        self._render_source_cards(sources)

    def render_enhanced_sources_no_search_info(self, sources: List[Dict]):
        """검색 정보 없이 소스만 렌더링 (expander 중첩 방지)"""
        if not sources:
            return

        # 소스 카드들만 렌더링
        self._render_source_cards(sources)

    def _render_source_cards(self, sources: List[Dict]):
        """소스 카드들 렌더링 (공통 로직 분리)"""
        # 고유 ID를 가진 소스 카드들 렌더링
        for idx, source in enumerate(sources, 1):
            # 고유 ID 부여
            source_id = f"ref-{idx}"

            with st.container():
                # HTML anchor 추가
                st.markdown(f'<div id="{source_id}" class="source-card">', unsafe_allow_html=True)

                # 향상된 소스 카드 렌더링
                self._render_enhanced_source_card(source, idx)

                st.markdown('</div>', unsafe_allow_html=True)

                # 카드 간 간격
                if idx < len(sources):
                    st.divider()

    def _render_enhanced_source_card(self, source: Dict, ref_num: int):
        """개선된 소스 카드 렌더링 - 탭 사용, 메타데이터 분리"""
        score = source.get("score", 0)
        confidence = source.get("confidence", 0)
        name = source.get("source", "Unknown")
        content = source.get("content", "")

        # 🔧 간소화된 헤더 섹션 (참조 번호와 문서명만)
        col1, col2 = st.columns([0.1, 0.9])

        with col1:
            st.markdown(f"### [{ref_num}]")

        with col2:
            st.markdown(f"**{name}**")

        # 🚀 탭을 사용한 내용 표시
        preview_length = 150
        if len(content) > preview_length:
            preview = content[:preview_length] + "..."

            # 탭 생성
            tab1, tab2 = st.tabs(["📄 요약", "📖 전체 내용"])

            with tab1:
                # 요약 탭 - 내용만 깔끔하게
                st.markdown(f"**💬 요약:** {preview}")

            with tab2:
                # 전체 내용 탭 - 메타데이터 포함

                # 상단에 메타데이터 표시
                meta_col1, meta_col2, meta_col3 = st.columns(3)

                with meta_col1:
                    st.caption(f"**유사도:** {score:.3f}")

                with meta_col2:
                    st.caption(f"**길이:** {len(content):,}자")

                with meta_col3:
                    # 신뢰도 바와 수치
                    confidence_color = "#22c55e" if confidence >= 0.8 else "#f59e0b" if confidence >= 0.6 else "#ef4444"
                    st.markdown(f"""
                    <div style="background-color: #e5e5e5; border-radius: 10px; height: 8px; margin: 5px 0;">
                        <div style="background-color: {confidence_color}; width: {int(confidence * 100)}%; height: 100%; 
                                    border-radius: 10px; transition: width 0.3s ease;"></div>
                    </div>
                    <small style="color: {confidence_color}; font-weight: bold;">신뢰도: {int(confidence * 100)}%</small>
                    """, unsafe_allow_html=True)

                st.divider()

                # 추가 메타데이터 (있는 경우)
                metadata = source.get("metadata", {})
                if metadata:
                    st.caption("📋 **문서 정보**")
                    meta_info_cols = st.columns(2)

                    meta_items = [(k, v) for k, v in metadata.items() if v]
                    for i, (key, value) in enumerate(meta_items[:4]):  # 최대 4개까지
                        with meta_info_cols[i % 2]:
                            st.caption(f"**{key}:** {value}")

                    if meta_items:
                        st.divider()

                # 전체 내용
                st.markdown("**📄 전체 내용**")
                st.text_area(
                    "전체 내용",
                    content,
                    height=200,
                    key=f"content_full_{ref_num}",
                    disabled=True,
                    label_visibility="collapsed"
                )
        else:
            # 내용이 짧은 경우 - 단일 탭으로 표시
            tab1, tab2 = st.tabs(["📄 내용", "📊 상세 정보"])

            with tab1:
                st.markdown(f"**💬 내용:** {content}")
                st.caption("✅ 전체 내용이 표시되었습니다.")

            with tab2:
                # 메타데이터만 표시
                meta_col1, meta_col2, meta_col3 = st.columns(3)

                with meta_col1:
                    st.metric("유사도", f"{score:.3f}")

                with meta_col2:
                    st.metric("길이", f"{len(content):,}자")

                with meta_col3:
                    st.metric("신뢰도", f"{int(confidence * 100)}%")

                # 추가 메타데이터
                metadata = source.get("metadata", {})
                if metadata:
                    st.divider()
                    st.caption("📋 **문서 정보**")

                    for key, value in metadata.items():
                        if value:
                            st.caption(f"**{key}:** {value}")

    def _render_search_summary(self, search_info: Dict) -> None:
        """검색 요약 정보 표시 - expander 중첩 문제 해결"""
        if not search_info:
            return

        # 🔧 expander 대신 일반 컨테이너 사용 (중첩 문제 해결)
        st.markdown("#### 🔍 검색 정보")

        cols = st.columns([1, 1, 1, 1])

        with cols[0]:
            st.metric("검색 시간", f"{search_info.get('search_time', 0):.2f}초")

        with cols[1]:
            st.metric("검색 방식", search_info.get('search_type', 'hybrid'))

        with cols[2]:
            st.metric("총 후보", f"{search_info.get('total_candidates', 0)}개")

        with cols[3]:
            st.metric("필터링됨", f"{search_info.get('filtered_count', 0)}개")

        st.divider()


# 추가 유틸리티 함수들
def _calculate_confidence_score(source: Dict) -> float:
    """근거 신뢰도 점수 계산 - 수정된 버전"""
    base_score = source.get("score", 0.0)
    content = source.get("content", "")
    content_length = len(content)

    # 기본 점수가 이미 1.0 이상이면 정규화
    if base_score >= 1.0:
        confidence = base_score / max(base_score, 1.2)  # 최대 기준점으로 정규화
    else:
        confidence = base_score

    # 보정 팩터들 (곱셈 방식으로 변경)
    length_factor = 1.0
    if 100 <= content_length <= 1000:
        length_factor = 1.05  # 5% 증가
    elif content_length > 1000:
        length_factor = 1.02  # 2% 증가
    elif content_length < 50:
        length_factor = 0.9   # 10% 감소

    # 메타데이터 품질 팩터
    metadata_factor = 1.0
    metadata = source.get("metadata", {})
    if metadata.get("title"):
        metadata_factor *= 1.03  # 3% 증가
    if metadata.get("section"):
        metadata_factor *= 1.02  # 2% 증가

    # 최종 계산 (곱셈 방식)
    final_confidence = confidence * length_factor * metadata_factor

    # 상한선 적용 (0.95로 제한하여 100% 방지)
    result = min(final_confidence, 0.95)

    return result


def calculate_overall_confidence(sources: List[Dict]) -> float:
    """전체 근거의 종합 신뢰도 계산"""
    if not sources:
        return 0.0

    # 가중 평균 계산 (상위 근거에 더 높은 가중치)
    total_weight = 0
    weighted_sum = 0

    for i, source in enumerate(sources[:5]):  # 상위 5개만 고려
        confidence = _calculate_confidence_score(source)
        weight = 1.0 / (i + 1)  # 순위가 높을수록 높은 가중치

        weighted_sum += confidence * weight
        total_weight += weight

    return weighted_sum / total_weight if total_weight > 0 else 0.0


def get_source_quality_grade(confidence: float) -> str:
    """근거 품질 등급 반환"""
    if confidence >= 0.9:
        return "A+ (매우 높음)"
    elif confidence >= 0.8:
        return "A (높음)"
    elif confidence >= 0.7:
        return "B+ (양호)"
    elif confidence >= 0.6:
        return "B (보통)"
    elif confidence >= 0.5:
        return "C+ (낮음)"
    elif confidence >= 0.4:
        return "C (매우 낮음)"
    else:
        return "D (부적절)"


def filter_sources_by_quality(sources: List[Dict], min_confidence: float = 0.5) -> List[Dict]:
    """품질 기준으로 근거 필터링"""
    filtered = []
    for source in sources:
        confidence = _calculate_confidence_score(source)
        if confidence >= min_confidence:
            filtered.append({**source, "confidence": confidence})

    return sorted(filtered, key=lambda x: x["confidence"], reverse=True)


# 글로벌 인스턴스
reference_system = InteractiveReferenceSystem()