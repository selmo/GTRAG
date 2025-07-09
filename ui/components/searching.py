"""
검색 컴포넌트
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
                0.0, 1.0, 0.5,
                help="이 값 이상의 유사도를 가진 문서만 표시"
            )
        
        with col3:
            show_preview = st.checkbox(
                "미리보기 표시",
                value=True,
                help="검색 결과의 전체 내용 표시"
            )
    
    # 검색 입력
    col1, col2, col3 = st.columns([5, 2, 1])
    
    with col1:
        search_query = st.text_input(
            "검색어를 입력하세요",
            placeholder="예: 계약 조건, 납품 기한, 품질 기준...",
            label_visibility="collapsed"
        )
    
    with col2:
        top_k = st.number_input(
            "검색 결과 수",
            min_value=1,
            max_value=20,
            value=5,
            label_visibility="collapsed"
        )
    
    with col3:
        search_button = st.button("🔍", type="primary", use_container_width=True)
    
    # 검색 실행
    if search_button or (search_query and st.session_state.get('auto_search', False)):
        perform_search(api_client, search_query, top_k, min_score, show_preview)
    
    # 검색 기록
    render_search_history()


def perform_search(api_client, query: str, top_k: int, min_score: float, show_preview: bool):
    """검색 실행"""
    if not query:
        st.warning("검색어를 입력해주세요.")
        return
    
    with st.spinner("검색 중..."):
        try:
            results = api_client.search(query, top_k)
            
            # 최소 점수 필터링
            filtered_results = [r for r in results if r.get('score', 0) >= min_score]
            
            if filtered_results:
                st.success(f"{len(filtered_results)}개의 관련 문서를 찾았습니다.")
                
                # 검색 기록 저장
                save_search_history(query, len(filtered_results))
                
                # 결과 표시
                render_search_results(filtered_results, show_preview)
                
                # 결과 분석
                show_result_analytics(filtered_results)
                
            else:
                st.warning("검색 결과가 없습니다. 다른 검색어를 시도해보세요.")
                
                # 검색 제안
                suggest_alternative_searches(query)
                
        except Exception as e:
            st.error(f"검색 오류: {str(e)}")


def render_search_results(results: List[Dict], show_preview: bool):
    """검색 결과 렌더링"""
    # 정렬 옵션
    sort_by = st.selectbox(
        "정렬 기준",
        ["유사도 높은 순", "유사도 낮은 순", "최신순"],
        label_visibility="collapsed"
    )
    
    # 결과 정렬
    if sort_by == "유사도 낮은 순":
        results = sorted(results, key=lambda x: x.get('score', 0))
    elif sort_by == "최신순":
        # timestamp가 있다면 사용
        results = sorted(results, key=lambda x: x.get('timestamp', ''), reverse=True)
    # 기본은 유사도 높은 순 (이미 정렬되어 있음)
    
    # 결과 표시
    for idx, hit in enumerate(results, 1):
        render_single_result(idx, hit, show_preview)


def render_single_result(idx: int, hit: Dict, show_preview: bool):
    """단일 검색 결과 렌더링"""
    with st.container():
        # 헤더
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"### 검색 결과 {idx}")
        
        with col2:
            score = hit.get('score', 0)
            if score >= 0.8:
                st.success(f"유사도: {score:.3f}")
            elif score >= 0.6:
                st.warning(f"유사도: {score:.3f}")
            else:
                st.info(f"유사도: {score:.3f}")
        
        with col3:
            # 액션 버튼
            if st.button("📋", key=f"copy_{idx}", help="복사"):
                st.write("복사됨!")  # 실제로는 클립보드 복사 구현 필요
        
        # 메타데이터
        metadata = hit.get('metadata', {})
        if metadata:
            cols = st.columns(4)
            if 'source' in metadata:
                cols[0].caption(f"📄 {metadata['source']}")
            if 'page' in metadata:
                cols[1].caption(f"📄 페이지 {metadata['page']}")
            if 'title' in metadata:
                cols[2].caption(f"📌 {metadata['title']}")
            if 'timestamp' in metadata:
                cols[3].caption(f"⏰ {metadata['timestamp']}")
        
        # 내용
        content = hit.get('content', '')
        
        if show_preview:
            # 전체 내용 표시
            st.text_area(
                "내용",
                value=content,
                height=150,
                disabled=True,
                key=f"content_{idx}",
                label_visibility="collapsed"
            )
        else:
            # 요약만 표시
            preview = content[:200] + "..." if len(content) > 200 else content
            st.write(preview)
            
            if len(content) > 200:
                if st.button("더 보기", key=f"more_{idx}"):
                    st.text_area(
                        "전체 내용",
                        value=content,
                        height=200,
                        disabled=True,
                        key=f"full_content_{idx}"
                    )
        
        # 관련 액션
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("💬 이 내용으로 질문", key=f"ask_{idx}"):
                st.session_state.search_context = content
                st.info("채팅 탭으로 이동하여 질문하세요.")
        
        with col2:
            if st.button("🔍 유사 문서 찾기", key=f"similar_{idx}"):
                # 이 문서와 유사한 문서 검색
                st.session_state.search_query = content[:50]
                st.experimental_rerun()
        
        st.divider()


def show_result_analytics(results: List[Dict]):
    """검색 결과 분석"""
    with st.expander("📊 검색 결과 분석"):
        # 점수 분포
        scores = [r.get('score', 0) for r in results]
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("평균 유사도", f"{sum(scores)/len(scores):.3f}")
        
        with col2:
            st.metric("최고 유사도", f"{max(scores):.3f}")
        
        with col3:
            st.metric("최저 유사도", f"{min(scores):.3f}")
        
        with col4:
            high_quality = sum(1 for s in scores if s >= 0.8)
            st.metric("고품질 결과", f"{high_quality}개")
        
        # 점수 분포 차트
        if len(results) > 3:
            import pandas as pd
            df = pd.DataFrame({
                '순위': range(1, len(scores) + 1),
                '유사도': scores
            })
            st.line_chart(df.set_index('순위'))


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
            
            for search in recent_searches:
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    if st.button(
                        f"🔍 {search['query']}",
                        key=f"history_{search['timestamp']}",
                        use_container_width=True
                    ):
                        st.session_state.search_query = search['query']
                        st.experimental_rerun()
                
                with col2:
                    st.caption(f"{search['result_count']}개")


def suggest_alternative_searches(query: str):
    """대체 검색어 제안"""
    st.info("💡 다음 검색어를 시도해보세요:")
    
    # 간단한 제안 로직 (실제로는 더 복잡한 로직 필요)
    suggestions = []
    
    # 띄어쓰기 제거
    if ' ' in query:
        suggestions.append(query.replace(' ', ''))
    
    # 단어 분리
    if len(query) > 4 and ' ' not in query:
        mid = len(query) // 2
        suggestions.append(f"{query[:mid]} {query[mid:]}")
    
    # 유사어 (하드코딩된 예시)
    synonyms = {
        '계약': ['계약서', '협약', '약정'],
        '납품': ['납기', '배송', '인도'],
        '품질': ['품질기준', 'QC', '검사']
    }
    
    for word, syns in synonyms.items():
        if word in query:
            for syn in syns:
                suggestions.append(query.replace(word, syn))
    
    # 제안 표시
    cols = st.columns(min(len(suggestions), 3))
    for idx, suggestion in enumerate(suggestions[:3]):
        with cols[idx]:
            if st.button(suggestion, key=f"suggest_{idx}"):
                st.session_state.search_query = suggestion
                st.experimental_rerun()
