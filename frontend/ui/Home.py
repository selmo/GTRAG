"""
GTOne RAG System - 개선된 홈 페이지
시스템 상태에 따라 로딩 화면 또는 메인 화면 표시
"""
import streamlit as st
import sys
from pathlib import Path
import time
import requests
from frontend.ui.utils.streamlit_helpers import rerun

# 프로젝트 루트를 Python 경로에 추가
# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from frontend.ui.utils.api_client import APIClient
from frontend.ui.utils.session import SessionManager
from frontend.ui.components.sidebar import render_sidebar
from frontend.ui.components.chatting import render_chat_history, handle_chat_input
from frontend.ui.components.uploader import get_upload_summary

# 페이지 설정 - 가장 먼저 호출되어야 함
st.set_page_config(
    page_title="GTOne RAG System",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

def check_system_ready() -> tuple[bool, dict]:
    """
    시스템 준비 상태 확인
    Returns: (is_ready, status_info)
    """
    try:
        # API 서버 기본 연결 확인
        response = requests.get("http://localhost:18000/docs", timeout=3)
        if response.status_code != 200:
            return False, {"error": "API server not responding"}

        # 헬스체크 확인
        health_response = requests.get("http://localhost:18000/v1/health", timeout=5)
        if health_response.status_code == 200:
            health_data = health_response.json()
            services = health_data.get("services", {})

            # 핵심 서비스 상태 확인
            qdrant_ok = services.get("qdrant", {}).get("status") == "connected"
            ollama_ok = services.get("ollama", {}).get("status") == "connected"

            # 임베딩 모델 테스트
            try:
                test_response = requests.get(
                    "http://localhost:18000/v1/search?q=test&top_k=1",
                    timeout=10
                )
                embedder_ok = test_response.status_code in [200, 404]  # 404도 OK (빈 컬렉션)
            except:
                embedder_ok = False

            all_ready = qdrant_ok and embedder_ok

            return all_ready, {
                "qdrant": qdrant_ok,
                "ollama": ollama_ok,
                "embedder": embedder_ok,
                "overall": all_ready
            }
        else:
            return False, {"error": "Health check failed"}

    except requests.exceptions.ConnectionError:
        return False, {"error": "Cannot connect to API server"}
    except requests.exceptions.Timeout:
        return False, {"error": "API server timeout"}
    except Exception as e:
        return False, {"error": f"System check failed: {str(e)}"}


def render_loading_screen(status_info: dict):
    """시스템 로딩 화면 렌더링"""

    # 로딩 스타일
    st.markdown("""
    <style>
    .loading-container {
        text-align: center;
        padding: 2rem;
    }
    .loading-spinner {
        display: inline-block;
        width: 40px;
        height: 40px;
        border: 3px solid #f3f3f3;
        border-top: 3px solid #ff6b6b;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 20px;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .status-box {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # 로딩 헤더
    st.markdown("""
    <div class="loading-container">
        <h1>🤖 GTOne RAG System</h1>
        <h3>시스템 초기화 중...</h3>
        <div class="loading-spinner"></div>
        <p>AI 모델을 준비하고 있습니다. 잠시만 기다려주세요.</p>
    </div>
    """, unsafe_allow_html=True)

    # 상태 정보 표시
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("📊 초기화 상태")

        if "error" in status_info:
            st.error(f"❌ {status_info['error']}")
            st.info("🔄 페이지를 새로고침하거나 잠시 후 다시 시도해보세요.")
        else:
            # 서비스별 상태
            services = [
                ("Qdrant 벡터 DB", status_info.get("qdrant", False)),
                ("임베딩 모델", status_info.get("embedder", False)),
                ("Ollama LLM", status_info.get("ollama", False))
            ]

            for service_name, is_ready in services:
                if is_ready:
                    st.success(f"✅ {service_name}: 준비 완료")
                else:
                    st.warning(f"⏳ {service_name}: 초기화 중...")

        # 진행률 표시
        if "error" not in status_info:
            ready_count = sum([
                status_info.get("qdrant", False),
                status_info.get("embedder", False),
                status_info.get("ollama", False)
            ])
            progress = ready_count / 3
            st.progress(progress)
            st.caption(f"진행률: {int(progress * 100)}%")

    # 자동 새로고침
    time.sleep(3)
    rerun()


def render_main_app():
    """메인 애플리케이션 렌더링"""

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
            rerun()

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
                    rerun()

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
                    from frontend.ui.utils.helpers import format_timestamp
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


def main():
    """메인 함수 - 시스템 상태에 따라 화면 결정"""

    # 시스템 상태 확인
    is_ready, status_info = check_system_ready()

    if is_ready:
        # 시스템 준비 완료 - 메인 앱 렌더링
        render_main_app()
    else:
        # 시스템 초기화 중 - 로딩 화면 표시
        render_loading_screen(status_info)


if __name__ == "__main__":
    main()