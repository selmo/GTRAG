"""
GTOne RAG System - 개선된 홈 페이지
통합된 시스템 상태 관리자를 사용하여 로딩 화면 또는 메인 화면 표시
"""
import streamlit as st
import sys
from pathlib import Path
import time
from frontend.ui.components.common import format_duration, StatusIndicator
from frontend.ui.utils.file_utils import FileNameCleaner


# 프로젝트 루트를 Python 경로에 추가 (GTRAG 루트에서 실행 고려)
current_file = Path(__file__).resolve()
ui_dir = current_file.parent
frontend_dir = ui_dir.parent
project_root = frontend_dir.parent

# Python path에 필요한 경로들 추가
for path in [str(frontend_dir), str(project_root)]:
    if path not in sys.path:
        sys.path.insert(0, path)

# 이제 import 가능
try:
    from frontend.ui.utils.client_manager import ClientManager
    from frontend.ui.utils.session import SessionManager
    # 조건부 import로 오류 방지
    try:
        from frontend.ui.utils.system_health import SystemHealthManager, SystemStatus, ServiceStatus
    except ImportError:
        # system_health 모듈을 찾을 수 없는 경우 기본 함수 사용
        SystemHealthManager = None
        SystemStatus = None
        ServiceStatus = None
        # 기존 함수 import
        from frontend.ui.utils.helpers import check_system_ready

    from frontend.ui.components.sidebar import render_sidebar
    from frontend.ui.components.uploader import get_upload_summary
    from frontend.ui.utils.streamlit_helpers import rerun
except ImportError as e:
    st.error(f"모듈 import 오류: {e}")
    st.error("현재 Python 경로:")
    for p in sys.path:
        st.write(f"  - {p}")
    st.stop()

# 페이지 설정 - 가장 먼저 호출되어야 함
st.set_page_config(
    page_title="GTOne RAG System",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)


def render_loading_screen(health_report):
    """시스템 로딩 화면 렌더링 - 개선된 버전"""

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

        if SystemHealthManager is not None:
            # 전체 상태 표시
            emoji, message, _ = SystemHealthManager.get_status_display_info(health_report.overall_status)
            st.info(f"{emoji} {message}")

            # 개별 서비스 상태
            services_to_show = [
                ("Qdrant 벡터 DB", "qdrant"),
                ("임베딩 모델", "embedder"),
                ("Ollama LLM", "ollama"),
                ("Celery 작업 큐", "celery")
            ]

            ready_count = 0
            total_count = len(services_to_show)

            for service_display_name, service_key in services_to_show:
                service_info = health_report.services.get(service_key)
                if service_info:
                    emoji, status_text = SystemHealthManager.get_service_display_info(service_info.status)

                    if service_info.status == ServiceStatus.CONNECTED:
                        st.success(f"{emoji} {service_display_name}: {status_text}")
                        ready_count += 1
                    elif service_info.status == ServiceStatus.DEGRADED:
                        st.warning(f"{emoji} {service_display_name}: {status_text}")
                        if service_info.message:
                            st.caption(f"   └ {service_info.message}")
                    elif service_info.status == ServiceStatus.DISCONNECTED:
                        st.error(f"{emoji} {service_display_name}: {status_text}")
                        if service_info.message:
                            st.caption(f"   └ {service_info.message}")
                    else:
                        st.info(f"{emoji} {service_display_name}: {status_text}")
                        if service_info.message:
                            st.caption(f"   └ {service_info.message}")

            # 진행률 표시
            progress = ready_count / total_count
            st.progress(progress)
            st.caption(f"진행률: {int(progress * 100)}% ({ready_count}/{total_count})")

            # 오류 메시지 표시
            if health_report.errors:
                st.divider()
                st.subheader("⚠️ 확인된 문제")
                for error in health_report.errors:
                    st.error(f"• {error}")

            # 추가 정보 및 해결 방안
            if health_report.overall_status == SystemStatus.ERROR:
                st.divider()
                st.subheader("🔧 해결 방안")
                st.markdown("""
                **일반적인 해결 방법:**
                1. **API 서버 확인**: `docker-compose up -d` 또는 서버 재시작
                2. **Ollama 상태 확인**: `ollama list` 명령으로 모델 확인
                3. **네트워크 연결**: 방화벽 및 포트 설정 확인
                4. **로그 확인**: 각 서비스의 로그에서 오류 메시지 확인
                """)
        else:
            # Fallback: 기본 로딩 표시
            st.info("🔄 시스템 상태를 확인하고 있습니다...")
            if hasattr(health_report, 'get'):
                if health_report.get('error'):
                    st.error(f"❌ {health_report['error']}")

    # 자동 새로고침 (5초 후)
    time.sleep(5)
    rerun()


def render_main_app():
    """메인 애플리케이션 렌더링 - 기존 코드 유지"""

    # 세션 상태 초기화
    SessionManager.init_session_state()

    # API 클라이언트 초기화
    api_client = ClientManager.get_client()

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
    st.header("📊 Dashboard")

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
    st.header("🚀 Quick Start")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("1️⃣ 문서 업로드")
        st.write("PDF, 이미지, 텍스트 문서를 업로드")
        if st.button("📤 문서 업로드 페이지로", use_container_width=True):
            st.switch_page("pages/10_Documents.py")

    with col2:
        st.subheader("2️⃣ 검색하기")
        st.write("키워드로 업로드된 문서 검색")
        if st.button("🔍 검색 페이지로", use_container_width=True):
            st.switch_page("pages/20_Search.py")

    with col3:
        st.subheader("3️⃣ 질문하기")
        st.write("AI와 대화하며 문서 내용을 탐색")
        if st.button("💬 채팅 시작하기", use_container_width=True):
            st.switch_page("pages/30_AI_Chat.py")

    st.divider()

    # 채팅 인터페이스 (선택적 표시)
    if st.session_state.get('show_chat', False):
        st.header("💬 AI 어시스턴트")

        # 모델 사용 가능 여부 확인 (새로운 시스템 상태 관리자 사용)
        if SystemHealthManager is not None:
            is_model_available, model_error = SystemHealthManager.check_model_availability(api_client)
        else:
            # Fallback: 기본 확인
            try:
                available_models = api_client.get_available_models()
                selected_model = st.session_state.get('selected_model')
                is_model_available = bool(available_models and selected_model and selected_model in available_models)
                model_error = "모델이 선택되지 않았거나 사용할 수 없습니다." if not is_model_available else None
            except Exception as e:
                is_model_available = False
                model_error = f"모델 상태 확인 실패: {str(e)}"

        if not is_model_available:
            st.error(f"🚫 {model_error}")
            st.info("💡 설정 페이지에서 모델을 선택한 후 사용해주세요.")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("⚙️ 설정 페이지로 이동"):
                    st.switch_page("pages/99_Settings.py")
            with col2:
                if st.button("채팅 숨기기"):
                    st.session_state.show_chat = False
                    rerun()
        else:
            # 채팅 컨테이너
            chat_container = st.container()

            with chat_container:
                from frontend.ui.components.chat import ChatInterface
                ChatInterface(api_client).render()

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
                    # 모델 사용 가능 여부 확인 후 채팅 시작
                    if SystemHealthManager is not None:
                        is_available, error_msg = SystemHealthManager.check_model_availability(api_client)
                    else:
                        # Fallback 확인
                        try:
                            available_models = api_client.get_available_models()
                            selected_model = st.session_state.get('selected_model')
                            is_available = bool(available_models and selected_model and selected_model in available_models)
                            error_msg = "모델이 설정되지 않았습니다." if not is_available else None
                        except:
                            is_available = False
                            error_msg = "모델 상태 확인 실패"

                    if is_available:
                        st.session_state.show_chat = True
                        SessionManager.add_message("user", question.split(" ", 1)[1])
                        rerun()
                    else:
                        st.error(f"🚫 {error_msg}")
                        st.info("💡 설정 페이지에서 모델을 선택한 후 사용해주세요.")

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
                    st.write(f"📄 {FileNameCleaner.clean_display_name(file['name'])}")
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
                    try:
                        st.caption(format_duration(msg['timestamp']))
                    except:
                        st.caption("시간 정보 없음")
        else:
            st.info("아직 대화 기록이 없습니다.")

    # 도움말
    st.divider()
    with st.expander("❓ 도움이 필요하신가요?"):
        st.markdown("""
        ### 🚀 시작하기
        1. **문서 업로드**: 왼쪽 사이드바 또는 문서 페이지에서 파일 업로드
        2. **모델 설정**: 설정 페이지에서 Ollama 모델 선택
        3. **검색**: 검색 페이지에서 키워드로 문서 검색
        4. **질문**: 이 페이지 또는 채팅으로 AI에게 질문

        ### 📌 지원 파일 형식
        - PDF 문서 (.pdf)
        - Word 문서 (.docx, .doc)
        - 텍스트 파일 (.txt)
        - 이미지 파일 (.png, .jpg, .jpeg)

        ### 💡 팁
        - 구체적으로 질문할수록 정확한 답변을 받을 수 있습니다
        - 여러 문서를 업로드하면 더 풍부한 정보를 얻을 수 있습니다
        - 검색 시 다양한 키워드를 시도해보세요
        - 설정 페이지에서 모델과 파라미터를 조정할 수 있습니다

        ### 🆘 문제 해결
        - **모델 선택 필요**: 설정 페이지에서 Ollama 모델을 선택하세요
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


def display_system_status_summary(api_client):
    """상단에 시스템 상태 요약 표시"""

    if SystemHealthManager is None:
        # Fallback: 간단한 상태 표시
        st.info("🔄 시스템 상태 확인 중...")
        return

    # 캐시된 상태 확인 (빈번한 새로고침 방지)
    cached_status = SystemHealthManager.get_cached_status()
    if cached_status:
        health_report = cached_status
    else:
        # 빠른 상태 확인 (타임아웃 단축)
        try:
            health_report = SystemHealthManager.check_full_system_status(api_client)
        except Exception as e:
            st.warning(f"⚠️ 시스템 상태 확인 실패: {e}")
            return

    # 상태에 따른 알림 표시
    emoji, message, style = SystemHealthManager.get_status_display_info(health_report.overall_status)

    if health_report.overall_status == SystemStatus.HEALTHY:
        st.success(f"{emoji} {message}")
    elif health_report.overall_status == SystemStatus.DEGRADED:
        st.warning(f"{emoji} {message}")

        # 문제가 있는 서비스 표시
        problem_services = []
        for service_name, service_info in health_report.services.items():
            if service_info.status in [ServiceStatus.DISCONNECTED, ServiceStatus.DEGRADED, ServiceStatus.ERROR]:
                problem_services.append(service_name)

        if problem_services:
            st.caption(f"⚠️ 문제 서비스: {', '.join(problem_services)}")

    elif health_report.overall_status in [SystemStatus.UNHEALTHY, SystemStatus.ERROR]:
        st.error(f"{emoji} {message}")

        col1, col2 = st.columns([3, 1])
        with col1:
            if health_report.errors:
                st.caption(f"주요 문제: {health_report.errors[0]}")
        with col2:
            if st.button("🔧 문제 해결", key="fix_issues"):
                st.switch_page("pages/99_Settings.py")

    # 상태 새로고침 버튼 (작은 버튼)
    col1, col2, col3 = st.columns([8, 1, 1])
    with col2:
        if st.button("🔄", help="상태 새로고침", key="refresh_status"):
            SystemHealthManager.clear_cache()
            rerun()

    with col3:
        # 마지막 확인 시간 표시
        last_check = health_report.last_updated.strftime("%H:%M:%S")
        st.caption(f"📅 {last_check}")


def main():
    """메인 함수 - 시스템 상태에 따라 화면 결정"""

    # API 클라이언트 초기화
    api_client = ClientManager.get_client()

    # 시스템 상태 확인 (통합 관리자 또는 기본 함수 사용)
    if SystemHealthManager is not None:
        is_ready, health_report = SystemHealthManager.is_system_ready(api_client)

        if is_ready:
            # 시스템 준비 완료 - 메인 앱 렌더링
            render_main_app()
        else:
            # 시스템 초기화 중 - 로딩 화면 표시
            render_loading_screen(health_report)
    else:
        # Fallback: 기존 함수 사용
        try:
            is_ready, status_dict = check_system_ready(api_client)
            if is_ready:
                render_main_app()
            else:
                # 기본 로딩 화면
                st.info("🔄 시스템 초기화 중입니다...")
                st.write("시스템 상태를 확인하고 있습니다. 잠시만 기다려주세요.")
                time.sleep(3)
                rerun()
        except Exception as e:
            st.error(f"시스템 상태 확인 실패: {e}")
            st.info("메인 화면으로 계속 진행합니다.")
            render_main_app()


if __name__ == "__main__":
    main()