"""
GTOne RAG System - 홈 페이지
Streamlit 멀티페이지 앱의 메인 진입점
"""
import streamlit as st
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

from ui.utils.api_client import APIClient
from ui.utils.session import SessionManager
from ui.components.sidebar import render_sidebar
from ui.components.chat import render_chat_history, handle_chat_input
from ui.components.uploader import get_upload_summary

# 페이지 설정 - 가장 먼저 호출되어야 함
st.set_page_config(
    page_title="GTOne RAG System",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 세션 상태 초기화
SessionManager.init_session_state()


# API 클라이언트 초기화
@st.cache_resource
def get_api_client():
    return APIClient()


api_client = get_api_client()

# 사이드바 렌더링
render_sidebar(api_client)

# 메인 페이지 헤더
st.title("🏠 GTOne RAG System")
st.markdown("### 지능형 문서 기반 질의응답 시스템")

# 시스템 개요
st.markdown("""
업로드한 문서를 기반으로 자연어 질문에 답변하는 AI 시스템입니다.
PDF, 이미지, 텍스트 문서를 분석하여 정확한 정보를 제공합니다.
""")

st.divider()

# 대시보드
st.header("📊 대시보드")

# 통계 카드
col1, col2, col3, col4 = st.columns(4)

upload_stats = get_upload_summary()

with col1:
    st.metric(
        "📄 총 문서 수",
        upload_stats['total_files'],
        help="업로드된 총 문서 수"
    )

with col2:
    st.metric(
        "🧩 총 청크 수",
        upload_stats['total_chunks'],
        help="인덱싱된 총 청크 수"
    )

with col3:
    message_count = len(st.session_state.get('messages', []))
    user_messages = sum(1 for m in st.session_state.messages if m['role'] == 'user')
    st.metric(
        "💬 대화 수",
        message_count,
        f"+{user_messages} 질문",
        help="현재 세션의 대화 수"
    )

with col4:
    search_count = len(st.session_state.get('search_history', []))
    recent_searches = sum(1 for s in st.session_state.get('search_history', [])[-10:])
    st.metric(
        "🔍 검색 수",
        search_count,
        f"+{recent_searches} 최근",
        help="수행한 검색 수"
    )

st.divider()

# 빠른 시작
st.header("🚀 빠른 시작")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1️⃣ 문서 업로드")
    st.write("사이드바에서 PDF, 이미지, 텍스트 문서를 업로드하세요.")
    if st.button("📤 문서 업로드 페이지로", use_container_width=True):
        st.switch_page("pages/documents.py")

with col2:
    st.subheader("2️⃣ 검색하기")
    st.write("키워드로 업로드된 문서를 검색하세요.")
    if st.button("🔍 검색 페이지로", use_container_width=True):
        st.switch_page("pages/search.py")

with col3:
    st.subheader("3️⃣ 질문하기")
    st.write("AI와 대화하며 문서 내용을 탐색하세요.")
    if st.button("💬 채팅 시작하기", use_container_width=True):
        st.session_state.show_chat = True

st.divider()

# 채팅 인터페이스 (선택적 표시)
if st.session_state.get('show_chat', False):
    st.header("💬 AI 어시스턴트")

    # 채팅 컨테이너
    chat_container = st.container()

    with chat_container:
        # 채팅 히스토리
        render_chat_history()

        # 채팅 입력
        settings = SessionManager.get_default_ai_settings()
        rag_settings = settings.get('rag', {})

        handle_chat_input(
            api_client,
            top_k=rag_settings.get('top_k', 3),
            model=settings.get('llm', {}).get('model')
        )

    # 채팅 숨기기 버튼
    if st.button("채팅 숨기기"):
        st.session_state.show_chat = False
        st.experimental_rerun()

else:
    # 채팅이 숨겨진 경우 예시 질문 표시
    st.header("💡 예시 질문")

    example_questions = [
        "📋 계약서의 주요 조건은 무엇인가요?",
        "📅 프로젝트 일정이 어떻게 되나요?",
        "💰 예산 관련 내용을 요약해주세요.",
        "📊 성과 지표에 대해 설명해주세요.",
        "🔍 품질 기준은 무엇인가요?"
    ]

    cols = st.columns(3)
    for idx, question in enumerate(example_questions):
        with cols[idx % 3]:
            if st.button(question, key=f"example_{idx}", use_container_width=True):
                st.session_state.show_chat = True
                SessionManager.add_message("user", question.split(" ", 1)[1])
                st.experimental_rerun()

# 최근 활동
st.divider()
st.header("📜 최근 활동")

tab1, tab2, tab3 = st.tabs(["최근 업로드", "최근 검색", "최근 대화"])

with tab1:
    if 'uploaded_files' in st.session_state and st.session_state.uploaded_files:
        recent_files = st.session_state.uploaded_files[-5:][::-1]
        for file in recent_files:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"📄 {file['name']}")
            with col2:
                st.caption(file['time'])
            with col3:
                st.caption(f"{file['chunks']} chunks")
    else:
        st.info("아직 업로드된 파일이 없습니다.")

with tab2:
    if 'search_history' in st.session_state and st.session_state.search_history:
        recent_searches = st.session_state.search_history[-5:][::-1]
        for search in recent_searches:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"🔍 {search['query']}")
            with col2:
                st.caption(f"{search['result_count']} 결과")
    else:
        st.info("아직 검색 기록이 없습니다.")

with tab3:
    if 'messages' in st.session_state and st.session_state.messages:
        recent_messages = [m for m in st.session_state.messages if m['role'] == 'user'][-3:][::-1]
        for msg in recent_messages:
            st.write(f"💬 {msg['content'][:100]}...")
            if 'timestamp' in msg:
                from ui.utils.helpers import format_timestamp

                st.caption(format_timestamp(msg['timestamp']))
    else:
        st.info("아직 대화 기록이 없습니다.")

# 도움말
st.divider()
with st.expander("❓ 도움이 필요하신가요?"):
    st.markdown("""
    ### 🚀 시작하기
    1. **문서 업로드**: 왼쪽 사이드바 또는 문서 페이지에서 파일 업로드
    2. **검색**: 검색 페이지에서 키워드로 문서 검색
    3. **질문**: 이 페이지 또는 채팅으로 AI에게 질문

    ### 📌 지원 파일 형식
    - PDF 문서 (.pdf)
    - Word 문서 (.docx, .doc)
    - 텍스트 파일 (.txt)
    - 이미지 파일 (.png, .jpg, .jpeg)

    ### 💡 팁
    - 구체적으로 질문할수록 정확한 답변을 받을 수 있습니다
    - 여러 문서를 업로드하면 더 풍부한 정보를 얻을 수 있습니다
    - 검색 시 다양한 키워드를 시도해보세요

    ### 🆘 문제 해결
    - **파일 업로드 실패**: 파일 크기(50MB 이하) 및 형식 확인
    - **답변이 부정확함**: 관련 문서가 업로드되었는지 확인
    - **시스템 오류**: 페이지 새로고침 후 재시도

    추가 도움이 필요하시면 support@gtone.com으로 문의하세요.
    """)

# 푸터
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    st.caption("© 2024 GTOne. All rights reserved.")

with col2:
    st.caption("GTOne RAG System v1.0.0")

with col3:
    st.caption("Powered by Qdrant + Ollama")