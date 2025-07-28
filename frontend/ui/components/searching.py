"""
검색 컴포넌트 (개선된 버전)
"""
import streamlit as st
from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime


def render_search_interface(api_client):
    """검색 인터페이스 렌더링"""
    st.header("🔍 문서 검색")

    # 검색 옵션
    with st.expander("⚙️ 검색 옵션", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            search_mode = st.selectbox(
                "검색 모드",
                ["유사도 검색", "키워드 검색", "하이브리드 검색"],
                help="검색 방식을 선택하세요"
            )

        with col2:
            min_score = st.slider(
                "최소 유사도",
                0.0, 1.0, 0.3,  # 기본값을 0.3으로 낮춤
                help="이 값 이상의 유사도를 가진 문서만 표시"
            )

        with col3:
            show_preview = st.checkbox(
                "전체 내용 표시",
                value=True,
                help="검색 결과의 전체 내용 표시"
            )

    # 검색 입력
    with st.form(key="search_form", clear_on_submit=False):
        col1, col2, col3 = st.columns([5, 2, 1])

        with col1:
            search_query = st.text_input(
                "검색어를 입력하세요",
                placeholder="예: 계약 조건, 납품 기한, 품질 기준...",
                label_visibility="collapsed",
                key="main_search_input",
            )

        with col2:
            top_k = st.number_input(
                "검색 결과 수",
                min_value=1,
                max_value=20,
                value=5,
                label_visibility="collapsed",
            )

        with col3:
            submitted = st.form_submit_button("🔍", type="primary", use_container_width=True)

    # Enter 키 또는 버튼 → submitted=True
    if submitted:
        perform_search(api_client, search_query, top_k, min_score, show_preview)

    # 검색 기록
    render_search_history()


def perform_search(api_client, query: str, top_k: int, min_score: float, show_preview: bool):
    """개선된 검색 실행 - 에러 처리 및 사용자 피드백 강화"""
    if not query:
        st.warning("검색어를 입력해주세요.")
        return

    with st.spinner("검색 중..."):
        try:
            # API 클라이언트 유효성 검사
            if not api_client:
                st.error("❌ 검색 서비스에 연결할 수 없습니다.")
                st.info("💡 설정 페이지에서 서버 연결 상태를 확인해주세요.")
                return

            # 검색 실행
            results_raw = api_client.search(query, top_k)

            # 결과 처리
            if isinstance(results_raw, dict):
                results = results_raw.get("results", results_raw.get("items", []))
            else:
                results = results_raw

            # 결과가 없는 경우 처리
            if not results:
                st.warning("🔍 검색 결과가 없습니다.")

                # 검색 개선 제안
                with st.expander("💡 검색 개선 제안", expanded=True):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**검색어 수정 제안:**")
                        st.markdown("- 더 짧은 키워드 사용")
                        st.markdown("- 유사한 단어로 변경")
                        st.markdown("- 한글/영어 전환")

                    with col2:
                        st.markdown("**설정 조정:**")
                        if min_score > 0.3:
                            st.markdown(f"- 최소 유사도를 낮춰보세요 (현재: {min_score})")
                        if top_k < 10:
                            st.markdown(f"- 검색 결과 수를 늘려보세요 (현재: {top_k}개)")
                        st.markdown("- 다른 검색 모드를 시도해보세요")

                # 대체 검색어 제안
                suggest_alternative_searches(query)
                return

            # 최소 점수 필터링
            filtered_results = [r for r in results if r.get('score', 0) >= min_score]

            if not filtered_results:
                st.warning(f"❌ 최소 유사도 {min_score} 이상인 결과가 없습니다.")

                # 유사도가 낮은 결과들 정보 제공
                low_score_results = [r for r in results if r.get('score', 0) < min_score]
                if low_score_results:
                    best_score = max(r.get('score', 0) for r in low_score_results)
                    st.info(f"💡 가장 높은 유사도: {best_score:.3f} (기준: {min_score})")

                    if st.button(f"🔍 유사도 {best_score:.1f} 이상 결과 보기", key="show_lower_score"):
                        render_search_results_improved(low_score_results, show_preview, query)
                        show_result_analytics(low_score_results)

                # 검색 개선 제안
                suggest_alternative_searches(query)
                return

            # 성공적인 검색 결과 처리
            success_msg = f"✅ {len(filtered_results)}개의 관련 문서를 찾았습니다."

            # 필터링된 결과 정보 추가
            if len(results) > len(filtered_results):
                success_msg += f" (전체 {len(results)}개 중 유사도 {min_score} 이상)"

            st.success(success_msg)

            # 검색 기록 저장
            save_search_history(query, len(filtered_results))

            # 결과 표시
            render_search_results_improved(filtered_results, show_preview, query)

            # 결과 분석
            show_result_analytics(filtered_results)

            # 문서 처리 상태 확인 및 알림
            check_and_notify_fallback_results(filtered_results)

        except ConnectionError:
            st.error("❌ 검색 서버에 연결할 수 없습니다.")
            st.info("💡 네트워크 연결 상태를 확인하거나 잠시 후 다시 시도해주세요.")

        except TimeoutError:
            st.error("❌ 검색 요청 시간이 초과되었습니다.")
            st.info("💡 더 간단한 검색어로 다시 시도해주세요.")

        except Exception as e:
            error_msg = str(e)
            st.error(f"❌ 검색 중 오류가 발생했습니다: {error_msg}")

            # 상세 오류 정보 (디버깅용)
            with st.expander("🔧 상세 오류 정보"):
                st.code(f"Error Type: {type(e).__name__}")
                st.code(f"Error Message: {error_msg}")
                st.code(f"Query: {query}")
                st.code(f"Parameters: top_k={top_k}, min_score={min_score}")

            # 문제 해결 제안
            st.markdown("**💡 해결 방법:**")
            st.markdown("- 페이지를 새로고침하여 다시 시도")
            st.markdown("- 더 간단한 검색어 사용")
            st.markdown("- 설정 페이지에서 서버 상태 확인")
            st.markdown("- 관리자에게 문의")


def check_and_notify_fallback_results(results):
    """fallback 결과 확인 및 사용자 알림"""
    fallback_results = [r for r in results if r.get('metadata', {}).get('type') == 'fallback']

    if fallback_results:
        with st.expander(f"⚠️ 처리 제한 문서 ({len(fallback_results)}개)", expanded=False):
            st.warning("일부 문서는 완전히 처리되지 않았습니다:")

            for result in fallback_results:
                metadata = result.get('metadata', {})
                filename = metadata.get('source', '알 수 없는 파일')
                error_type = metadata.get('original_error', '알 수 없는 오류')

                st.markdown(f"**📄 {filename}**")
                st.caption(f"문제: {error_type}")

                # 해결 제안
                suggestions = metadata.get('suggestions', [])
                if suggestions:
                    st.caption(f"제안: {', '.join(suggestions)}")

            st.info("💡 이런 문서들은 파일 형식을 변환하거나 관리자에게 문의하여 해결할 수 있습니다.")

def render_search_results_improved(results: List[Dict], show_preview: bool, query: str):
    """개선된 검색 결과 렌더링"""
    # 정렬 옵션
    col1, col2 = st.columns([2, 1])

    with col1:
        sort_by = st.selectbox(
            "정렬 기준",
            ["유사도 높은 순", "유사도 낮은 순", "최신순"],
            label_visibility="collapsed"
        )

    with col2:
        display_mode = st.radio(
            "표시 방식",
            ["카드형", "목록형"],
            horizontal=True,
            label_visibility="collapsed"
        )

    # 결과 정렬
    if sort_by == "유사도 낮은 순":
        results = sorted(results, key=lambda x: x.get('score', 0))
    elif sort_by == "최신순":
        results = sorted(results, key=lambda x: x.get('timestamp', ''), reverse=True)

    # 결과 표시
    if display_mode == "카드형":
        render_card_results(results, show_preview, query)
    else:
        render_list_results(results, show_preview, query)


def render_card_results(results: List[Dict], show_preview: bool, query: str):
    """카드형 결과 표시"""
    for idx, hit in enumerate(results, 1):
        with st.container():
            # 카드 스타일 박스
            with st.expander(f"📄 검색 결과 {idx} (유사도: {hit.get('score', 0):.3f})", expanded=True):
                render_single_result_content(idx, hit, show_preview, query)


def render_list_results(results: List[Dict], show_preview: bool, query: str):
    """목록형 결과 표시"""
    for idx, hit in enumerate(results, 1):
        st.divider()
        render_single_result_content(idx, hit, show_preview, query)


def render_single_result_content(idx: int, hit: Dict, show_preview: bool, query: str):
    """단일 검색 결과 내용 렌더링"""
    # 헤더 정보
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        # 메타데이터 표시
        metadata = hit.get('metadata', {})
        source_info = []

        if 'source' in metadata:
            source_info.append(f"📄 {metadata['source']}")
        if 'page' in metadata:
            source_info.append(f"📄 {metadata['page']}페이지")
        if 'chunk_index' in metadata:
            source_info.append(f"섹션 {metadata['chunk_index'] + 1}")

        if source_info:
            st.caption(" | ".join(source_info))

    with col2:
        score = hit.get('score', 0)
        if score >= 0.8:
            st.success(f"✅ {score:.3f}")
        elif score >= 0.6:
            st.warning(f"⚠️ {score:.3f}")
        else:
            st.info(f"ℹ️ {score:.3f}")

    with col3:
        # 액션 버튼
        if st.button("📋 복사", key=f"copy_{idx}", help="내용 복사"):
            st.info("내용이 복사되었습니다!")

    # 내용 표시
    content = hit.get('content', '')

    if show_preview:
        # 검색어 하이라이트
        highlighted_content = highlight_search_terms(content, query)

        # 전체 내용을 읽기 쉽게 표시
        st.markdown("**📝 내용:**")

        # 내용을 박스로 감싸서 표시
        content_container = st.container()
        with content_container:
            if len(content) > 1000:
                # 긴 내용은 접을 수 있게
                with st.expander("전체 내용 보기", expanded=False):
                    st.markdown(highlighted_content, unsafe_allow_html=True)

                # 처음 500자만 미리보기
                preview_text = content[:500] + "..." if len(content) > 500 else content
                preview_highlighted = highlight_search_terms(preview_text, query)
                st.markdown(f"**미리보기:** {preview_highlighted}", unsafe_allow_html=True)
            else:
                # 짧은 내용은 바로 표시
                st.markdown(highlighted_content, unsafe_allow_html=True)
    else:
        # 요약만 표시
        preview = content[:200] + "..." if len(content) > 200 else content
        preview_highlighted = highlight_search_terms(preview, query)
        st.markdown(f"**요약:** {preview_highlighted}", unsafe_allow_html=True)

        if len(content) > 200:
            if st.button("더 보기", key=f"more_{idx}"):
                full_highlighted = highlight_search_terms(content, query)
                st.markdown("**전체 내용:**")
                st.markdown(full_highlighted, unsafe_allow_html=True)

    # 관련 액션
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("💬 이 내용으로 질문", key=f"ask_{idx}", use_container_width=True):
            st.session_state.search_context = content
            st.info("💡 채팅 탭으로 이동하여 이 내용에 대해 질문하세요.")

    with col2:
        if st.button("🔍 유사 문서 찾기", key=f"similar_{idx}", use_container_width=True):
            # 이 문서와 유사한 문서 검색
            similar_query = content[:100]  # 처음 100자로 유사 검색
            st.session_state.auto_search = True
            st.session_state.main_search_input = similar_query
            st.experimental_rerun()

    with col3:
        if st.button("📊 문서 정보", key=f"info_{idx}", use_container_width=True):
            show_document_info(hit)


def highlight_search_terms(text: str, query: str) -> str:
    """검색어 하이라이트"""
    if not query or not text:
        return text

    import re

    # 여러 검색어 처리 (공백으로 분리)
    search_terms = [term.strip() for term in query.split() if term.strip()]

    highlighted_text = text

    for term in search_terms:
        if len(term) > 1:  # 한 글자 검색어는 제외
            # 대소문자 구분 없이 검색
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            highlighted_text = pattern.sub(
                lambda m: f'<mark style="background-color: yellow; padding: 1px 2px; border-radius: 2px;">{m.group()}</mark>',
                highlighted_text
            )

    return highlighted_text


def show_document_info(hit: Dict):
    """문서 정보 표시"""
    with st.expander("📊 문서 상세 정보", expanded=True):
        metadata = hit.get('metadata', {})

        info_data = {
            "청크 ID": hit.get('chunk_id', 'N/A'),
            "소스": metadata.get('source', 'N/A'),
            "페이지": metadata.get('page', 'N/A'),
            "청크 인덱스": metadata.get('chunk_index', 'N/A'),
            "문서 타입": metadata.get('type', 'N/A'),
            "언어": metadata.get('lang', 'N/A'),
            "유사도 점수": f"{hit.get('score', 0):.4f}",
            "내용 길이": f"{len(hit.get('content', ''))} 문자"
        }

        for key, value in info_data.items():
            if value != 'N/A':
                st.write(f"**{key}**: {value}")


def show_result_analytics(results: List[Dict]):
    """검색 결과 분석"""
    with st.expander("📊 검색 결과 분석"):
        scores = [r.get('score', 0) for r in results]

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("평균 유사도", f"{sum(scores)/len(scores):.3f}")

        with col2:
            st.metric("최고 유사도", f"{max(scores):.3f}")

        with col3:
            st.metric("최저 유사도", f"{min(scores):.3f}")

        with col4:
            high_quality = sum(1 for s in scores if s >= 0.7)
            st.metric("고품질 결과", f"{high_quality}개")

        # 점수 분포 차트
        if len(results) > 2:
            import pandas as pd
            df = pd.DataFrame({
                '순위': range(1, len(scores) + 1),
                '유사도': scores
            })
            st.line_chart(df.set_index('순위'))

        # 소스별 분포
        sources = {}
        for result in results:
            source = result.get('metadata', {}).get('source', 'Unknown')
            sources[source] = sources.get(source, 0) + 1

        if len(sources) > 1:
            st.write("**문서별 결과 분포:**")
            for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
                st.write(f"- {source}: {count}개")


def save_search_history(query: str, result_count: int):
    """검색 기록 저장"""
    if 'search_history' not in st.session_state:
        st.session_state.search_history = []

    st.session_state.search_history.append({
        'query': query,
        'timestamp': datetime.now(),
        'result_count': result_count
    })

    # 최대 50개까지만 유지
    if len(st.session_state.search_history) > 50:
        st.session_state.search_history = st.session_state.search_history[-50:]


def render_search_history():
    """검색 기록 표시"""
    if 'search_history' in st.session_state and st.session_state.search_history:
        with st.expander("🕒 최근 검색"):
            # 최근 5개만 표시
            recent_searches = st.session_state.search_history[-5:]
            recent_searches.reverse()

            for i, search in enumerate(recent_searches):
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    if st.button(
                        f"🔍 {search['query']}",
                        key=f"history_{i}_{search['timestamp']}",
                        use_container_width=True
                    ):
                        st.session_state.main_search_input = search['query']
                        st.experimental_rerun()

                with col2:
                    st.caption(f"{search['result_count']}개")

                with col3:
                    time_str = search['timestamp'].strftime('%H:%M')
                    st.caption(time_str)


def suggest_alternative_searches(query: str):
    """대체 검색어 제안"""
    st.info("💡 다음 검색어를 시도해보세요:")

    suggestions = []

    # 띄어쓰기 제거
    if ' ' in query:
        suggestions.append(query.replace(' ', ''))

    # 단어 분리
    if len(query) > 4 and ' ' not in query:
        mid = len(query) // 2
        suggestions.append(f"{query[:mid]} {query[mid:]}")

    # 유사어 (확장 가능)
    synonyms = {
        '계약': ['계약서', '협약', '약정', '계약조건'],
        '납품': ['납기', '배송', '인도', '납품기한'],
        '품질': ['품질기준', 'QC', '검사', '품질관리'],
        '가격': ['금액', '비용', '요금', '단가'],
        '기간': ['일정', '스케줄', '타임라인', '기한']
    }

    for word, syns in synonyms.items():
        if word in query:
            for syn in syns[:2]:  # 최대 2개씩만
                suggestion = query.replace(word, syn)
                if suggestion not in suggestions:
                    suggestions.append(suggestion)

    # 제안 표시 (최대 4개)
    if suggestions:
        cols = st.columns(min(len(suggestions), 4))
        for idx, suggestion in enumerate(suggestions[:4]):
            with cols[idx]:
                if st.button(f"🔍 {suggestion}", key=f"suggest_{idx}", use_container_width=True):
                    st.session_state.main_search_input = suggestion
                    st.experimental_rerun()

    # 추가 팁
    st.markdown("""
    **검색 팁:**
    - 더 짧은 키워드 사용
    - 유사한 단어로 시도
    - 한글/영어 전환
    - 최소 유사도를 낮춰보세요
    """)