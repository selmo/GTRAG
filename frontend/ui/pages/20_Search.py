"""
검색 페이지
"""
import streamlit as st
import sys
from pathlib import Path

from frontend.ui.utils.client_manager import ClientManager
from frontend.ui.utils.streamlit_helpers import rerun

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent.parent))

from frontend.ui.components.searching import render_search_interface

# 페이지 설정
st.set_page_config(
    page_title="문서 검색 - GTOne RAG",
    page_icon="🔍",
    layout="wide"
)

# CSS 스타일 추가 (이 부분을 추가)
st.markdown("""
<style>
/* 검색 결과 컨테이너 스타일 */
.search-result-container {
    background-color: var(--secondary-background-color);
    padding: 1rem;
    border-radius: 8px;
    margin: 0.5rem 0;
    border-left: 4px solid var(--primary-color);
}

/* 하이라이트된 텍스트 스타일 */
mark {
    background-color: #ffeb3b !important;
    color: #000 !important;
    padding: 2px 4px !important;
    border-radius: 3px !important;
    font-weight: 600 !important;
}

/* 검색 결과 텍스트 영역 */
.search-content {
    background-color: #f8f9fa;
    padding: 15px;
    border-radius: 8px;
    margin: 10px 0;
    border: 1px solid #e9ecef;
    font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
    line-height: 1.8;
    white-space: pre-wrap;
    word-wrap: break-word;
    font-size: 1rem;
}

/* 메타데이터 스타일 */
.search-metadata {
    font-size: 0.85rem;
    color: #6c757d;
    margin-bottom: 0.5rem;
}

/* 유사도 점수 스타일 */
.score-high {
    background-color: #d4edda;
    color: #155724;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: bold;
}

.score-medium {
    background-color: #fff3cd;
    color: #856404;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: bold;
}

.score-low {
    background-color: #d1ecf1;
    color: #0c5460;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: bold;
}

/* 버튼 스타일 개선 */
.stButton > button {
    border-radius: 6px;
    border: 1px solid #dee2e6;
    transition: all 0.2s;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
</style>
""", unsafe_allow_html=True)

# API 클라이언트 초기화
api_client = ClientManager.get_client()

# 헤더
st.title("🔍 문서 검색")
st.markdown("업로드된 문서에서 원하는 정보를 검색합니다.")

# 메인 검색 인터페이스
render_search_interface(api_client)

# 추가 기능
st.divider()

# 고급 검색 옵션
with st.expander("🔧 고급 검색", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("검색 필터")
        
        # 문서 필터
        if 'uploaded_files' in st.session_state and st.session_state.uploaded_files:
            file_names = [f['name'] for f in st.session_state.uploaded_files]
            selected_files = st.multiselect(
                "특정 문서에서만 검색",
                options=file_names,
                help="선택한 문서에서만 검색합니다"
            )
        
        # 날짜 범위
        date_range = st.date_input(
            "업로드 날짜 범위",
            value=[],
            help="이 기간에 업로드된 문서만 검색"
        )
        
        # 언어 필터
        language = st.selectbox(
            "언어",
            ["전체", "한국어", "영어"],
            help="특정 언어의 문서만 검색"
        )
    
    with col2:
        st.subheader("검색 설정")
        
        # 검색 알고리즘
        algorithm = st.radio(
            "검색 알고리즘",
            ["코사인 유사도", "유클리드 거리", "맨하탄 거리"],
            help="벡터 검색에 사용할 거리 측정 방법"
        )
        
        # 청크 크기
        chunk_overlap = st.slider(
            "컨텍스트 확장",
            0, 500, 100,
            help="검색된 청크 주변의 추가 텍스트 포함 (문자 수)"
        )
        
        # 재순위화
        rerank = st.checkbox(
            "결과 재순위화",
            help="추가 알고리즘으로 검색 결과를 재정렬"
        )

# 검색 템플릿
st.divider()
st.subheader("🎯 빠른 검색 템플릿")

templates = {
    "계약 조건": "계약 기간, 계약 금액, 지불 조건",
    "기술 사양": "제품 사양, 기술 요구사항, 성능 기준",
    "일정 관련": "납품 일정, 마일스톤, 프로젝트 일정",
    "품질 기준": "품질 보증, 검사 기준, 불량률",
    "법적 조항": "책임 제한, 보증, 분쟁 해결"
}

cols = st.columns(len(templates))
for idx, (name, query) in enumerate(templates.items()):
    with cols[idx]:
        if st.button(f"📝 {name}", use_container_width=True):
            st.session_state.search_query = query
            rerun()

# 검색 가이드
with st.expander("💡 검색 팁"):
    st.markdown("""
    ### 효과적인 검색 방법
    
    1. **구체적인 키워드 사용**
       - ❌ "정보"
       - ✅ "2024년 1분기 매출 정보"
    
    2. **여러 키워드 조합**
       - "계약 기간 연장 조건"
       - "품질 검사 불합격 처리"
    
    3. **유사어 활용**
       - 납품 = 배송 = 인도
       - 계약 = 협약 = 약정
    
    4. **검색 결과가 없을 때**
       - 더 짧은 키워드로 시도
       - 유사한 표현으로 변경
       - 영어/한국어 전환
    """)

# 검색 히스토리 관리
if st.button("🗑️ 검색 기록 삭제"):
    if 'search_history' in st.session_state:
        st.session_state.search_history = []
        st.success("검색 기록이 삭제되었습니다.")
        rerun()

# 푸터
st.divider()
st.caption("💡 검색 결과를 바탕으로 채팅 페이지에서 더 자세한 질문을 할 수 있습니다.")
