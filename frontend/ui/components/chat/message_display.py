"""Functions responsible solely for rendering message‑related UI bits."""
from __future__ import annotations

from typing import Dict, List, Any, Optional
import streamlit as st
import re
from datetime import datetime

from frontend.ui.core.config import Constants, config

try:
    from frontend.ui.utils.file_utils import FileNameCleaner  # type: ignore
    HAS_FILE_UTILS = True
except ImportError:
    HAS_FILE_UTILS = False

# 🚀 인터랙티브 레퍼런스 시스템 적용
try:
    from .reference_system import reference_system

    HAS_REFERENCE_SYSTEM = True
except ImportError:
    reference_system = None
    HAS_REFERENCE_SYSTEM = False


__all__ = ["render_sources"]


def _calculate_confidence_score(source: Dict) -> float:
    """근거 신뢰도 점수 계산 - 수정된 버전"""
    base_score = source.get("score", 0.0)
    content = source.get("content", "")
    content_length = len(content)

    # 🔧 로깅 제거 (오류 방지)
    # 디버깅이 필요한 경우 print 사용 또는 별도 방법 활용

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
        length_factor = 0.9  # 10% 감소

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


def _get_confidence_color(confidence: float) -> str:
    """신뢰도에 따른 색상 반환"""
    if confidence >= 0.8:
        return "#22c55e"  # green
    elif confidence >= 0.6:
        return "#f59e0b"  # amber
    elif confidence >= 0.4:
        return "#ef4444"  # red
    else:
        return "#6b7280"  # gray


def _get_confidence_emoji(confidence: float) -> str:
    """신뢰도에 따른 이모지 반환"""
    if confidence >= 0.8:
        return "🟢"
    elif confidence >= 0.6:
        return "🟡"
    elif confidence >= 0.4:
        return "🔴"
    else:
        return "⚪"


def _extract_citation_snippet(content: str, max_length: int = 150) -> str:
    """인용할 핵심 구문 추출"""
    if not content:
        return ""

    # 문장 단위로 분할
    sentences = re.split(r'[.!?]\s+', content.strip())

    # 가장 적절한 문장 선택 (중간 길이의 첫 번째 문장)
    best_sentence = ""
    for sentence in sentences:
        if 20 <= len(sentence) <= max_length:
            best_sentence = sentence
            break

    # 적절한 문장이 없으면 첫 번째 문장 사용
    if not best_sentence and sentences:
        best_sentence = sentences[0]

    # 길이 제한
    if len(best_sentence) > max_length:
        best_sentence = best_sentence[:max_length-3] + "..."

    return best_sentence.strip()


def _highlight_keywords(text: str, keywords: List[str]) -> str:
    """텍스트에서 키워드 하이라이팅"""
    if not keywords:
        return text

    highlighted = text
    for keyword in keywords:
        if len(keyword) >= 2:
            # 대소문자 무시하고 하이라이팅
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            highlighted = pattern.sub(
                lambda m: f"**{m.group()}**",
                highlighted
            )

    return highlighted


def _render_confidence_bar(confidence: float) -> None:
    """신뢰도 진행률 바 렌더링"""
    color = _get_confidence_color(confidence)
    percentage = int(confidence * 100)

    st.markdown(f"""
    <div style="background-color: #e5e5e5; border-radius: 10px; height: 8px; margin: 5px 0;">
        <div style="background-color: {color}; width: {percentage}%; height: 100%; 
                    border-radius: 10px; transition: width 0.3s ease;"></div>
    </div>
    <small style="color: {color}; font-weight: bold;">신뢰도: {percentage}%</small>
    """, unsafe_allow_html=True)


def _render_source_metadata(metadata: Dict, confidence: float) -> None:
    """소스 메타데이터 표시"""
    if not metadata:
        return

    cols = st.columns([1, 1, 1])

    with cols[0]:
        if title := metadata.get("title"):
            st.caption(f"📄 **제목:** {title}")

    with cols[1]:
        if section := metadata.get("section"):
            st.caption(f"📍 **섹션:** {section}")

    with cols[2]:
        if page := metadata.get("page"):
            st.caption(f"📃 **페이지:** {page}")

    # 추가 메타데이터
    if author := metadata.get("author"):
        st.caption(f"✍️ **작성자:** {author}")

    if created_date := metadata.get("created_date"):
        st.caption(f"📅 **작성일:** {created_date}")


def _render_source_actions(source: Dict, idx: int) -> None:
    """소스별 액션 버튼"""
    cols = st.columns([1, 1, 1, 2])

    with cols[0]:
        if st.button("📋 복사", key=f"copy_{idx}", help="내용 복사"):
            st.code(source.get("content", ""), language=None)

    with cols[1]:
        if st.button("🔍 상세", key=f"detail_{idx}", help="상세 정보"):
            with st.expander("상세 정보", expanded=True):
                st.json(source)

    with cols[2]:
        if st.button("📤 인용", key=f"cite_{idx}", help="인용 형식"):
            citation = _generate_citation(source, idx)
            st.code(citation, language="text")


def _generate_citation(source: Dict, idx: int) -> str:
    """인용 형식 생성"""
    name = source.get("source", "Unknown")
    if HAS_FILE_UTILS:
        name = FileNameCleaner.clean_display_name(name)

    score = source.get("score", 0.0)
    content_snippet = _extract_citation_snippet(source.get("content", ""), 100)

    citation = f"[{idx}] {name} (유사도: {score:.3f})\n"
    citation += f"\"...{content_snippet}...\"\n"
    citation += f"참조일: {datetime.now().strftime('%Y-%m-%d')}"

    return citation


def render_sources(sources: List[Dict], search_info: Optional[Dict] = None):
    """최적화된 근거 표시 함수 - 인터랙티브 레퍼런스 지원"""
    if not sources:
        return

    # 🚀 새로운 인터랙티브 레퍼런스 시스템 사용
    if HAS_REFERENCE_SYSTEM and reference_system:
        # 검색 정보 표시
        if search_info:
            _render_search_summary(search_info)

        # 근거 처리 및 필터링
        processed_sources = []
        for source in sources:
            confidence = _calculate_confidence_score(source)
            processed_sources.append({
                **source,
                "confidence": confidence,
                "citation_snippet": _extract_citation_snippet(source.get("content", ""))
            })

        # 🚀 향상된 근거 표시 (인터랙티브 레퍼런스 포함)
        with st.expander(
                f"{Constants.Icons.DOCUMENT} **참조 근거** ({len(processed_sources)}개) - 클릭하여 본문 참조 확인",
                expanded=False
        ):
            # 사용법 안내
            st.info("💡 **사용법**: 본문의 [숫자] 클릭 → 해당 근거로 이동 | 근거의 ↑ 버튼 클릭 → 본문으로 돌아가기 | Ctrl+숫자키로 빠른 이동")

            # 근거 요약 정보
            avg_confidence = sum(s["confidence"] for s in processed_sources) / len(processed_sources)
            max_confidence = max(s["confidence"] for s in processed_sources)

            st.markdown(f"""
            **📊 근거 품질 요약**
            - 평균 신뢰도: {avg_confidence:.1%} | 최고 신뢰도: {max_confidence:.1%}
            - 필터링된 근거: {len(processed_sources)}/{len(sources)}개
            """)

            st.divider()

            # 인터랙티브 레퍼런스 시스템으로 렌더링
            reference_system.render_enhanced_sources(processed_sources, search_info)

        return

    # 🔧 폴백: 기존 시스템 (레퍼런스 시스템 없을 때)
    _render_sources_fallback(sources, search_info)


def _render_sources_fallback(sources: List[Dict], search_info: Optional[Dict] = None):
    """기존 근거 표시 시스템 (폴백) - Settings 연동 버전"""
    # 검색 정보 표시
    if search_info:
        _render_search_summary(search_info)

    # 🚀 Settings에서 설정값 가져오기 (사이드바 슬라이더 대신)
    try:
        from frontend.ui.core.config import Constants

        # Settings 페이지 설정값 사용
        confidence_threshold = (
                st.session_state.get('temp_min_similarity') or  # 임시 조정값 우선
                st.session_state.get('min_similarity') or  # 세션 설정값
                st.session_state.get('backend_min_similarity') or  # 백엔드 설정값
                Constants.Defaults.MIN_SIMILARITY  # 기본값
        )

        # 정렬 옵션도 Settings에서 가져오기 (기본값: 신뢰도 순)
        sort_option = st.session_state.get('source_sort_option', "신뢰도 순")

    except ImportError:
        # config를 불러올 수 없는 경우 기본값 사용
        confidence_threshold = 0.3
        sort_option = "신뢰도 순"

    # 🎯 설정 안내 및 제어 패널 (간단 버전)
    with st.container():
        st.markdown("---")
        st.markdown("#### 🔧 근거 필터링 설정 3")

        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.info("💡 **Settings 페이지**에서 기본 필터링 설정을 변경할 수 있습니다.")

            # 현재 적용 중인 설정 표시
            st.caption(f"현재 최소 유사도: **{confidence_threshold:.2f}** | 정렬: **{sort_option}**")

        with col2:
            # 임시 조정 옵션
            if st.button("🎛️ 임시 조정", key="fallback_temp_adjust", help="현재 세션에만 적용되는 임시 조정"):
                st.session_state.show_temp_controls = not st.session_state.get('show_temp_controls', False)

        with col3:
            # Settings 페이지로 이동
            if st.button("⚙️ Settings", key="fallback_goto_settings", help="영구 설정 변경"):
                st.switch_page("pages/99_Settings.py")

        # 임시 조정 컨트롤 (선택적 표시)
        if st.session_state.get('show_temp_controls', False):
            st.markdown("**임시 조정 (현재 세션에만 적용)**")

            temp_col1, temp_col2 = st.columns(2)

            with temp_col1:
                temp_threshold = st.slider(
                    "최소 유사도",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(confidence_threshold),
                    step=0.05,
                    key="fallback_temp_threshold",
                    help="이 값은 현재 세션에만 적용됩니다"
                )

                # 세션에 임시값 저장
                st.session_state.temp_min_similarity = temp_threshold
                confidence_threshold = temp_threshold

            with temp_col2:
                temp_sort = st.selectbox(
                    "정렬 방식",
                    ["신뢰도 순", "유사도 순", "길이 순"],
                    index=["신뢰도 순", "유사도 순", "길이 순"].index(sort_option),
                    key="fallback_temp_sort"
                )

                # 세션에 임시값 저장
                st.session_state.source_sort_option = temp_sort
                sort_option = temp_sort

            # 리셋 버튼
            if st.button("🔄 기본값 복원", key="fallback_reset_temp"):
                for key in ['temp_min_similarity', 'source_sort_option', 'show_temp_controls']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

    # 근거 처리 및 필터링
    processed_sources = []
    for source in sources:
        confidence = _calculate_confidence_score(source)
        if confidence >= confidence_threshold:
            processed_sources.append({
                **source,
                "confidence": confidence,
                "citation_snippet": _extract_citation_snippet(source.get("content", ""))
            })

    # 정렬 적용
    if sort_option == "신뢰도 순":
        processed_sources.sort(key=lambda x: x["confidence"], reverse=True)
    elif sort_option == "유사도 순":
        processed_sources.sort(key=lambda x: x.get("score", 0), reverse=True)
    elif sort_option == "길이 순":
        processed_sources.sort(key=lambda x: len(x.get("content", "")), reverse=True)

    # 필터링 결과 확인
    if not processed_sources:
        st.warning(f"⚠️ 신뢰도 {confidence_threshold:.1f} 이상의 근거가 없습니다.")
        st.info("💡 임시 조정에서 임계값을 낮춰보거나 Settings에서 기본값을 수정하세요.")
        return

    # 메인 근거 표시
    with st.expander(
            f"{Constants.Icons.DOCUMENT} **참조 근거** ({len(processed_sources)}개/{len(sources)}개 표시)",
            expanded=True
    ):
        # 근거 요약 정보
        avg_confidence = sum(s["confidence"] for s in processed_sources) / len(processed_sources)
        max_confidence = max(s["confidence"] for s in processed_sources)

        # 필터링 통계
        filtered_count = len(sources) - len(processed_sources)
        filter_rate = (len(processed_sources) / len(sources)) * 100 if sources else 0

        st.markdown(f"""
        **📊 근거 품질 요약**
        - 평균 신뢰도: **{avg_confidence:.1%}** | 최고 신뢰도: **{max_confidence:.1%}**
        - 표시 비율: **{filter_rate:.1f}%** ({len(processed_sources)}/{len(sources)}개)
        - 정렬 방식: **{sort_option}** | 임계값: **{confidence_threshold:.2f}**
        """)

        if filtered_count > 0:
            st.info(f"📋 {filtered_count}개 근거가 임계값({confidence_threshold:.2f}) 미만으로 숨겨졌습니다.")

        st.divider()

        # 개별 근거 표시
        for idx, source in enumerate(processed_sources, 1):
            _render_individual_source_enhanced(source, idx)

            if idx < len(processed_sources):
                st.divider()


def _render_individual_source_enhanced(source: Dict, idx: int) -> None:
    """개별 근거 항목 렌더링 - 향상된 버전"""
    score = source.get("score", 0)
    confidence = source.get("confidence", 0)
    raw_name = source.get("source", "Unknown")
    name = FileNameCleaner.clean_display_name(raw_name) if HAS_FILE_UTILS else raw_name
    content = source.get("content", "")
    citation_snippet = source.get("citation_snippet", "")

    # 🎯 개선된 헤더 섹션
    header_cols = st.columns([0.08, 0.02, 0.6, 0.3])

    with header_cols[0]:
        st.markdown(f"### {_get_confidence_emoji(confidence)}")

    with header_cols[1]:
        st.markdown(f"**[{idx}]**")

    with header_cols[2]:
        st.markdown(f"**{name}**")
        st.caption(f"유사도: {score:.3f} | 길이: {len(content):,}자")

    with header_cols[3]:
        _render_confidence_bar(confidence)

    # 인용문 하이라이팅 (개선된 버전)
    if citation_snippet:
        highlighted_snippet = _highlight_keywords(
            citation_snippet,
            source.get("keywords", [])
        )
        st.markdown(f"💬 **핵심 인용:** _{highlighted_snippet}_")

    # 메타데이터 표시
    _render_source_metadata(source.get("metadata", {}), confidence)

    # 🚀 향상된 내용 표시 (고유 키 보장)
    import time
    unique_suffix = f"{idx}_{int(time.time() * 1000000) % 1000000}"

    # 탭 기반 내용 표시
    if len(content) > 300:
        tab1, tab2, tab3 = st.tabs(["📄 요약", "📖 전체 내용", "🔧 액션"])

        with tab1:
            # 요약된 내용 (처음 300자)
            preview_content = content[:300]
            if len(content) > 300:
                preview_content += "..."

            highlighted_preview = _highlight_keywords(
                preview_content,
                source.get("keywords", [])
            )
            st.markdown(highlighted_preview)

            # 읽기 계속 버튼
            if st.button("📖 전체 내용 보기", key=f"read_more_{unique_suffix}"):
                st.info("→ **📖 전체 내용** 탭을 클릭하세요")

        with tab2:
            # 메타데이터 (상단)
            meta_col1, meta_col2, meta_col3 = st.columns(3)

            with meta_col1:
                st.caption(f"**유사도:** {score:.3f}")
            with meta_col2:
                st.caption(f"**신뢰도:** {confidence:.1%}")
            with meta_col3:
                st.caption(f"**길이:** {len(content):,}자")

            st.divider()

            # 전체 내용 (읽기 전용)
            st.markdown("**📄 전체 내용**")
            st.text_area(
                "전체 내용",
                content,
                height=200,
                key=f"content_full_{unique_suffix}",
                help="전체 내용을 확인할 수 있습니다",
                disabled=True,
                label_visibility="collapsed"
            )

        with tab3:
            # 액션 버튼들
            _render_source_actions(source, idx)

    else:
        # 짧은 내용의 경우 단순 표시
        tab1, tab2 = st.tabs(["📄 내용", "🔧 액션"])

        with tab1:
            highlighted_content = _highlight_keywords(
                content,
                source.get("keywords", [])
            )
            st.markdown(highlighted_content)
            st.success("✅ 전체 내용이 표시되었습니다.")

        with tab2:
            _render_source_actions(source, idx)


def _render_search_summary(search_info: Dict) -> None:
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


def _render_individual_source(source: Dict, idx: int) -> None:
    """개별 근거 항목 렌더링"""
    score = source.get("score", 0)
    confidence = source.get("confidence", 0)
    raw_name = source.get("source", "Unknown")
    name = FileNameCleaner.clean_display_name(raw_name) if HAS_FILE_UTILS else raw_name
    content = source.get("content", "")
    citation_snippet = source.get("citation_snippet", "")

    # 헤더 섹션
    header_cols = st.columns([0.1, 0.6, 0.3])

    with header_cols[0]:
        st.markdown(f"### {_get_confidence_emoji(confidence)}")

    with header_cols[1]:
        st.markdown(f"**[근거 {idx}] {name}**")
        st.caption(f"유사도: {score:.3f} | 길이: {len(content):,}자")

    with header_cols[2]:
        _render_confidence_bar(confidence)

    # 인용문 하이라이팅
    if citation_snippet:
        highlighted_snippet = _highlight_keywords(
            citation_snippet,
            source.get("keywords", [])
        )
        st.markdown(f"💬 **핵심 인용:** _{highlighted_snippet}_")

    # 메타데이터 표시
    _render_source_metadata(source.get("metadata", {}), confidence)

    # 내용 표시
    content_tabs = st.tabs(["📄 요약", "📖 전체 내용", "🔧 액션"])

    with content_tabs[0]:
        # 요약된 내용 (처음 300자)
        preview_len = min(300, len(content))
        preview_content = content[:preview_len]
        if len(content) > preview_len:
            preview_content += "..."

        highlighted_preview = _highlight_keywords(
            preview_content,
            source.get("keywords", [])
        )
        st.markdown(highlighted_preview)

    with content_tabs[1]:
        # 전체 내용
        if len(content) > 500:
            st.text_area(
                "전체 내용",
                content,
                height=200,
                key=f"content_full_{idx}",
                help="전체 내용을 확인할 수 있습니다"
            )
        else:
            highlighted_full = _highlight_keywords(
                content,
                source.get("keywords", [])
            )
            st.markdown(highlighted_full)

    with content_tabs[2]:
        # 액션 버튼들
        _render_source_actions(source, idx)


# 추가 유틸리티 함수들
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