"""
GTOne RAG System - 메인 애플리케이션
컴포넌트 기반으로 리팩토링된 Streamlit 앱
"""
import streamlit as st
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

# 컴포넌트 및 유틸리티 import
from ui.utils.api_client import APIClient
from ui.utils.session import SessionManager, init_page_state
from ui.components.sidebar import render_sidebar
from ui.components.chat import render_chat_history, handle_chat_input
from ui.components.search import render_search_interface
from ui.components.uploader import get_upload_summary

# 페이지 설정
st.set_page_config(
    page_title="GTOne RAG System",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/your-org/gtrag/wiki',
        'Report a bug': 'https://github.com/your-org/gtrag/issues',
        'About': """
        # GTOne RAG System

        문서 기반 질의응답 시스템 v1.0.0

        © 2024 GTOne. All rights reserved.
        """
    }
)

# 세션 상태 초기화
SessionManager.init_session_state()
init_page_state("main")


# API 클라이언트 초기화
@st.cache_resource
def get_api_client():
    return APIClient()


api_client = get_api_client()

# CSS 스타일 적용
st.markdown("""
<style>
    /* 메인 컨테이너 스타일 */
    .main-container {
        padding: 1rem;
    }

    /* 채팅 메시지 스타일 */
    .stChatMessage {
        background-color: var(--background-color);
        border-radius: 10px;
        margin: 0.5rem 0;
    }

    /* 버튼 스타일 */
    .stButton > button {
        border-radius: 5px;
        transition: all 0.3s;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 10px rgba(0,0,0,0.2);
    }

    /* 메트릭 카드 스타일 */
    [data-testid="metric-container"] {
        background-color: var(--secondary-background-color);
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }

    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1rem;
    }

    .stTabs [data-baseweb="tab"] {
        padding: 0.5rem 1rem;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# 사이드바 렌더링
render_sidebar(api_client)

# 메인 컨텐츠
st.title("🤖 GTOne RAG Assistant")

# 빠른 통계
col1, col2, col3, col4 = st.columns(4)

upload_stats = get_upload_summary()

with col1:
    st.metric(
        "📄 문서",
        upload_stats['total_files'],
        help="업로드된 총 문서 수"
    )

with col2:
    st.metric(
        "🧩 청크",
        upload_stats['total_chunks'],
        help="인덱싱된 총 청크 수"
    )

with col3:
    message_count = len(st.session_state.get('messages', []))
    st.metric(
        "💬 대화",
        message_count,
        help="현재 세션의 대화 수"
    )

with col4:
    search_count = len(st.session_state.get('search_history', []))
    st.metric(
        "🔍 검색",
        search_count,
        help="수행한 검색 수"
    )

st.divider()

# 메인 탭
tab1, tab2, tab3 = st.tabs(["💬 채팅", "🔍 문서 검색", "📚 빠른 가이드"])

with tab1:
    # 채팅 인터페이스
    chat_container = st.container()

    with chat_container:
        # 채팅 히스토리 렌더링
        render_chat_history()

        # 입력 처리
        settings = SessionManager.get_default_ai_settings()
        rag_settings = settings.get('rag', {})

        handle_chat_input(
            api_client,
            top_k=rag_settings.get('top_k', 3),
            model=settings.get('llm', {}).get('model')
        )

    # 채팅 도구
    with st.expander("🛠️ 채팅 도구", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🗑️ 대화 초기화", use_container_width=True):
                SessionManager.clear_messages()
                st.success("대화가 초기화되었습니다.")
                st.experimental_rerun()

        with col2:
            if st.button("💾 대화 저장", use_container_width=True):
                export_data = SessionManager.export_session_data()
                st.download_button(
                    label="다운로드",
                    data=export_data,
                    file_name="chat_export.json",
                    mime="application/json"
                )

        with col3:
            from ui.components.chat import export_chat_history

            export_chat_history()

with tab2:
    # 검색 인터페이스
    render_search_interface(api_client)

with tab3:
    # 빠른 가이드
    st.header("📚 빠른 사용 가이드")

    # 시작하기
    with st.expander("🚀 시작하기", expanded=True):
        st.markdown("""
        ### 1. 문서 업로드
        - 왼쪽 사이드바에서 문서를 업로드하세요
        - PDF, Word, 이미지 파일을 지원합니다
        - 문서는 자동으로 분석되고 인덱싱됩니다

        ### 2. 질문하기
        - 채팅 탭에서 자연어로 질문하세요
        - AI가 업로드된 문서를 기반으로 답변합니다
        - 답변과 함께 참조 문서를 확인할 수 있습니다

        ### 3. 검색하기
        - 검색 탭에서 키워드로 문서를 검색하세요
        - 유사도 기반으로 관련 문서를 찾습니다
        """)

    # 유용한 팁
    with st.expander("💡 유용한 팁"):
        st.markdown("""
        ### 효과적인 질문 방법
        - ✅ 구체적으로 질문하세요: "2024년 1분기 매출은 얼마인가요?"
        - ✅ 맥락을 포함하세요: "계약서에 명시된 납품 기한은 언제인가요?"
        - ❌ 너무 일반적인 질문은 피하세요: "정보 알려줘"

        ### 검색 팁
        - 여러 키워드를 조합하세요
        - 유사한 단어로도 검색해보세요
        - 검색 결과가 없다면 더 짧은 키워드로 시도하세요

        ### 문서 업로드 팁
        - 텍스트 기반 PDF가 가장 정확합니다
        - 이미지는 OCR을 통해 처리됩니다
        - 대용량 파일은 분할하여 업로드하세요
        """)

    # 단축키
    with st.expander("⌨️ 단축키"):
        st.markdown("""
        | 단축키 | 기능 |
        |--------|------|
        | `Ctrl/Cmd + Enter` | 메시지 전송 |
        | `Ctrl/Cmd + K` | 검색 포커스 |
        | `Esc` | 대화 상자 닫기 |
        """)

    # 자주 묻는 질문
    with st.expander("❓ 자주 묻는 질문"):
        st.markdown("""
        **Q: 어떤 파일 형식을 지원하나요?**
        A: PDF, Word (docx), 텍스트 (txt), 이미지 (PNG, JPG, JPEG) 파일을 지원합니다.

        **Q: 최대 파일 크기는 얼마인가요?**
        A: 파일당 최대 50MB까지 업로드할 수 있습니다.

        **Q: 여러 언어를 지원하나요?**
        A: 네, 한국어와 영어를 포함한 다국어를 지원합니다.

        **Q: 답변이 정확하지 않아요.**
        A: 더 구체적으로 질문하거나, 관련 문서가 업로드되었는지 확인하세요.

        **Q: 이전 대화 내용을 저장할 수 있나요?**
        A: 네, 채팅 도구에서 '대화 저장' 버튼을 사용하세요.
        """)

    # 문의
    st.divider()
    st.caption("💬 추가 도움이 필요하신가요? support@gtone.com으로 문의하세요.")

# 푸터
st.divider()

footer_col1, footer_col2, footer_col3 = st.columns(3)

with footer_col1:
    st.caption("GTOne RAG System v1.0.0")

with footer_col2:
    st.caption("Powered by Qdrant + Ollama")

with footer_col3:
    st.caption("© 2024 GTOne. All rights reserved.")

# JavaScript 추가 (선택사항)
st.markdown("""
<script>
// 자동 스크롤
function scrollToBottom() {
    const messages = document.querySelector('[data-testid="stChatMessageContainer"]');
    if (messages) {
        messages.scrollTop = messages.scrollHeight;
    }
}

// 페이지 로드 시 스크롤
window.addEventListener('load', scrollToBottom);

// 새 메시지 추가 시 스크롤
const observer = new MutationObserver(scrollToBottom);
const chatContainer = document.querySelector('[data-testid="stChatMessageContainer"]');
if (chatContainer) {
    observer.observe(chatContainer, { childList: true });
}
</script>
""", unsafe_allow_html=True)