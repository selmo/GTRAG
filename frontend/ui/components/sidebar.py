"""
사이드바 컴포넌트 - 개선된 버전
- Import 경로 통일
- 공통 컴포넌트 적용
- 설정 중앙화
- 에러 처리 표준화
"""
import streamlit as st
from datetime import datetime
from typing import Dict, Optional

# 통일된 import 경로
from frontend.ui.utils.streamlit_helpers import rerun
from frontend.ui.core.config import config, Constants
from frontend.ui.components.common import (
    StatusIndicator, MetricCard, ErrorDisplay, ActionButton
)
from frontend.ui.utils.error_handler import ErrorContext, GTRagError, ErrorType

# 조건부 import (표준 패턴)
try:
    from frontend.ui.utils.system_health import SystemHealthManager, SystemStatus, ServiceStatus
    HAS_SYSTEM_HEALTH = True
except ImportError:
    SystemHealthManager = None
    SystemStatus = None
    ServiceStatus = None
    HAS_SYSTEM_HEALTH = False

try:
    from frontend.ui.components.uploader import render_file_uploader, render_uploaded_files
    HAS_UPLOADER = True
except ImportError:
    HAS_UPLOADER = False


def render_sidebar(api_client):
    """사이드바 렌더링 - 개선된 버전"""
    with st.sidebar:
        # 시스템 정보
        render_system_info()


def _sync_uploaded_files(api_client):
    """업로드된 파일 목록 동기화"""
    if ("uploaded_files" not in st.session_state or
        not st.session_state.uploaded_files):

        with ErrorContext("파일 목록 동기화", show_errors=False) as ctx:
            try:
                server_files = api_client.list_documents()
                # 키 누락 시 UI 오류 방지용 기본값
                for f in server_files:
                    f.setdefault("time", "-")
                    f.setdefault("size", "-")
                st.session_state.uploaded_files = server_files
            except Exception as e:
                ctx.add_error(e)
                st.session_state.uploaded_files = []


def render_system_status(api_client):
    """시스템 상태 표시 - 공통 컴포넌트 사용"""
    st.header(f"{Constants.Icons.SETTINGS} 시스템 상태")

    # 액션 버튼들
    actions = [
        {
            "label": f"{Constants.Icons.REFRESH} 상태 확인",
            "key": "sidebar_status_check",
            "callback": lambda: check_system_health(api_client),
            "type": "secondary"
        },
        {
            "label": f"{Constants.Icons.STATUS_INFO} 통계",
            "key": "sidebar_stats",
            "callback": show_system_stats,
            "type": "secondary"
        }
    ]

    ActionButton.render_action_row(actions)

    # 현재 상태 표시
    display_current_status(api_client)

    # 자동 상태 확인 (세션 시작 시)
    if 'sidebar_health_checked' not in st.session_state:
        st.session_state.sidebar_health_checked = True
        if SystemHealthManager.get_cached_status() is None:  # 캐시 없을 때만
            check_system_health(api_client, silent=True)


def display_current_status(api_client):
    """현재 시스템 상태 간단 표시"""

    if not HAS_SYSTEM_HEALTH:
        # Fallback: 기본 상태 확인
        StatusIndicator.render_status("info", "상태를 확인하세요")
        return

    # 캐시된 상태 확인
    cached_status = SystemHealthManager.get_cached_status()

    if cached_status:
        # 전체 상태 표시
        emoji, message, _ = SystemHealthManager.get_status_display_info(cached_status.overall_status)

        # 공통 컴포넌트로 상태 표시
        if cached_status.overall_status == SystemStatus.HEALTHY:
            StatusIndicator.render_status("success", message)
        elif cached_status.overall_status == SystemStatus.DEGRADED:
            StatusIndicator.render_status("warning", message)
        elif cached_status.overall_status == SystemStatus.INITIALIZING:
            StatusIndicator.render_status("info", message)
        else:
            StatusIndicator.render_status("error", message)

        # 핵심 서비스 상태 요약 (컴팩트)
        core_services = ['qdrant', 'ollama', 'embedder']
        status_summary = []

        for service_name in core_services:
            service_info = cached_status.services.get(service_name)
            if service_info:
                emoji_svc, _ = SystemHealthManager.get_service_display_info(service_info.status)
                status_summary.append(f"{emoji_svc}")

        if status_summary:
            st.caption(" ".join(status_summary) + f" | {cached_status.last_updated.strftime('%H:%M')}")

        # 캐시 만료 임박 시 알림
        cache_remaining = (cached_status.cache_expires - datetime.now()).total_seconds()
        if cache_remaining < 10 and cache_remaining > 0:
            st.caption(f"{Constants.Icons.LOADING} {int(cache_remaining)}초 후 갱신")
    else:
        StatusIndicator.render_status("info", "상태를 확인하세요")


def check_system_health(api_client, silent=False):
    """시스템 건강 상태 확인 - 에러 처리 개선"""

    if not silent:
        with st.spinner("시스템 상태 확인 중..."):
            _perform_health_check(api_client, silent)
    else:
        _perform_health_check(api_client, silent)


def _perform_health_check(api_client, silent):
    """실제 상태 확인 수행"""
    # 기존 상태 초기화
    if 'last_health_check' in st.session_state and not hasattr(st.session_state.last_health_check, 'overall_status'):
        st.session_state.pop('last_health_check', None)
        st.session_state.pop('health_check_time', None)

    with ErrorContext("시스템 상태 확인", show_errors=not silent) as ctx:
        try:
            if HAS_SYSTEM_HEALTH:
                # 강제 새로고침으로 최신 상태 확인
                health_report = SystemHealthManager.check_full_system_status(
                    api_client,
                    force_refresh=not silent,  # UI에서 호출할 때만 신규 조회
                    quick_check=silent  # 사이드바 자동 호출은 빠른 체크
                )

                if not silent:
                    # 전체 상태에 따른 알림
                    emoji, message, _ = SystemHealthManager.get_status_display_info(health_report.overall_status)

                    if health_report.overall_status == SystemStatus.HEALTHY:
                        st.success(f"{emoji} {message}")
                    elif health_report.overall_status == SystemStatus.DEGRADED:
                        st.warning(f"{emoji} {message}")
                    else:
                        st.error(f"{emoji} {message}")

                    # 주요 서비스 상태 간단 표시
                    render_service_status_compact(health_report.services)

                    # 마지막 확인 정보 저장
                    st.session_state.last_health_check = health_report
                    st.session_state.health_check_time = datetime.now()

                fallback_needed = False
            else:
                fallback_needed = True

            if fallback_needed:
                # Fallback: 기본 API 호출
                if not silent:
                    response = api_client.health_check()

                    if isinstance(response, dict):
                        status = response.get("status", "").lower()
                    else:
                        status = str(response).lower()

                    if status == "healthy" or status == "ok":
                        StatusIndicator.render_status("success", "시스템 정상")
                    else:
                        StatusIndicator.render_status("warning", f"문제 감지: {status or '알 수 없음'}")

        except Exception as e:
            ctx.add_error(e)
            if not silent:
                ErrorDisplay.render_error_with_suggestions(
                    f"시스템 연결 실패: {str(e)}",
                    [
                        "API 서버가 실행 중인지 확인하세요",
                        "네트워크 연결을 확인하세요",
                        f"API URL을 확인하세요: {config.api.base_url}"
                    ]
                )


def render_service_status_compact(services: Dict):
    """개별 서비스 상태 컴팩트 렌더링 (사이드바용)"""

    if not HAS_SYSTEM_HEALTH:
        return

    # 핵심 서비스만 표시
    core_services = {
        'qdrant': f'{Constants.Icons.STATUS_OK} Qdrant',
        'ollama': f'{Constants.Icons.AI} Ollama',
        'embedder': '🔤 임베딩'
    }

    for service_key, display_name in core_services.items():
        if service_key in services:
            service_info = services[service_key]
            emoji, status_text = SystemHealthManager.get_service_display_info(service_info.status)

            StatusIndicator.render_service_card(
                display_name,
                {
                    "status": service_info.status.value,
                    "message": service_info.message,
                    "details": service_info.details or {}
                }
            )


def show_system_stats():
    """시스템 통계 표시 - 메트릭 카드 사용"""
    with st.expander(f"{Constants.Icons.STATUS_INFO} 시스템 통계", expanded=True):
        try:
            # 업로드 통계
            from frontend.ui.components.uploader import get_upload_summary
            stats = get_upload_summary()

            # 메트릭 그리드로 표시
            metrics = [
                {"title": "문서 수", "value": stats['total_files'], "help": "업로드된 총 문서 수"},
                {"title": "총 청크", "value": stats['total_chunks'], "help": "인덱싱된 총 청크 수"},
                {"title": "총 용량", "value": f"{stats['total_size']:.1f} MB", "help": "업로드된 총 용량"}
            ]

            # 세로로 배치 (사이드바용)
            for metric in metrics:
                MetricCard.render_single_metric(
                    metric["title"],
                    metric["value"],
                    help_text=metric["help"]
                )

        except ImportError:
            ErrorDisplay.render_error_with_suggestions(
                "업로드 통계를 불러올 수 없습니다",
                ["uploader 모듈을 확인하세요"]
            )

        st.divider()

        # 세션 통계
        if 'messages' in st.session_state:
            message_count = len(st.session_state.messages)
            user_messages = sum(1 for m in st.session_state.messages if m['role'] == 'user')

            MetricCard.render_single_metric("대화 수", message_count)
            MetricCard.render_single_metric("질문 수", user_messages)

        # 시스템 상태 통계
        if HAS_SYSTEM_HEALTH:
            cached_status = SystemHealthManager.get_cached_status()
            if cached_status:
                st.divider()

                # 서비스 상태 요약
                connected_count = sum(1 for service in cached_status.services.values()
                                    if service.status.value == "connected")
                total_services = len(cached_status.services)

                MetricCard.render_single_metric("정상 서비스", f"{connected_count}/{total_services}")

                # 마지막 확인 시간
                st.caption(f"마지막 확인: {cached_status.last_updated.strftime('%H:%M:%S')}")


def render_quick_actions():
    """빠른 작업 버튼들 - 공통 컴포넌트 사용"""
    st.header(f"{Constants.Icons.LOADING} 빠른 작업")

    # 액션 정의
    actions = [
        {
            "label": f"{Constants.Icons.DELETE} 대화 초기화",
            "key": "sidebar_clear_chat",
            "callback": _clear_chat_messages,
            "type": "secondary"
        },
        {
            "label": f"{Constants.Icons.REFRESH} 캐시 초기화",
            "key": "sidebar_clear_cache",
            "callback": _clear_system_cache,
            "type": "secondary"
        },
        {
            "label": f"{Constants.Icons.REFRESH} 페이지 새로고침",
            "key": "sidebar_refresh",
            "callback": lambda: rerun(),
            "type": "secondary"
        },
        {
            "label": f"{Constants.Icons.SETTINGS} 설정",
            "key": "sidebar_settings",
            "callback": lambda: st.switch_page("pages/99_Settings.py"),
            "type": "primary"
        }
    ]

    # 세로로 배치 (사이드바용)
    for action in actions:
        if st.button(
            action["label"],
            type=action["type"],
            use_container_width=True,
            key=action["key"]
        ):
            try:
                action["callback"]()
            except Exception as e:
                ErrorDisplay.render_error_with_suggestions(
                    f"작업 실행 실패: {str(e)}",
                    ["페이지를 새로고침해보세요"]
                )


def _clear_chat_messages():
    """대화 초기화"""
    if 'messages' in st.session_state and st.session_state.messages:
        st.session_state.messages = []
        st.success("대화가 초기화되었습니다.")
        rerun()
    else:
        st.info("초기화할 대화가 없습니다.")


def _clear_system_cache():
    """시스템 캐시 초기화"""
    cleared_count = 0

    if HAS_SYSTEM_HEALTH:
        SystemHealthManager.clear_cache()
        cleared_count += 1

    # 세션 캐시 초기화
    cache_keys = ['system_health_cache', 'model_list_cache', 'search_cache']
    for key in cache_keys:
        if key in st.session_state:
            del st.session_state[key]
            cleared_count += 1

    if cleared_count > 0:
        st.success("캐시가 초기화되었습니다.")
    else:
        st.info("초기화할 캐시가 없습니다.")

    rerun()


def render_system_info():
    """시스템 정보 표시 - 상수 사용"""
    st.header(f"{Constants.Icons.STATUS_INFO} 정보")

    with st.expander("시스템 정보"):
        st.write("**버전**: v0.7")
        st.write("**임베딩**: E5-large")
        st.write("**벡터 DB**: Qdrant")
        st.write("**LLM**: Ollama")

        # 현재 선택된 모델 표시
        selected_model = st.session_state.get('selected_model')
        if selected_model:
            st.write(f"**현재 모델**: {selected_model}")
        else:
            st.write("**현재 모델**: 미선택")

        st.divider()

        st.caption("**지원 문서 형식**")
        for ext in config.file.allowed_extensions[:4]:  # 처음 4개만 표시
            icon = Constants.Icons.FILE_ICONS.get(ext, Constants.Icons.FILE_ICONS['default'])
            st.caption(f"• {icon} {ext.upper()}")

    # with st.expander("단축키"):
    #     st.write("**Ctrl/Cmd + Enter**: 메시지 전송")
    #     st.write("**Ctrl/Cmd + K**: 검색 포커스")
    #     st.write("**Ctrl/Cmd + L**: 대화 초기화")
    #
    with st.expander("유용한 링크"):
        st.markdown(f"[{Constants.Icons.DOCUMENT} API 문서]({Constants.URLs.DOCS})")
        st.markdown(f"[{Constants.Icons.STATUS_OK} Qdrant UI]({Constants.URLs.QDRANT_UI})")
        st.markdown(f"[{Constants.Icons.DOCUMENT} 사용 가이드]({Constants.URLs.GITHUB})")

    # 시스템 상태 요약 (하단)
    if HAS_SYSTEM_HEALTH:
        cached_status = SystemHealthManager.get_cached_status()
        if cached_status:
            st.divider()
            st.caption(f"{Constants.Icons.SETTINGS} **시스템 상태**")

            emoji, _, _ = SystemHealthManager.get_status_display_info(cached_status.overall_status)
            status_text = {
                "healthy": "정상",
                "degraded": "일부 문제",
                "unhealthy": "문제 있음",
                "initializing": "초기화 중",
                "error": "오류"
            }.get(cached_status.overall_status.value, "알 수 없음")

            st.caption(f"{emoji} {status_text} | {cached_status.last_updated.strftime('%H:%M')}")

            # 문제가 있으면 설정 페이지 링크
            if cached_status.overall_status.value in ["unhealthy", "error"]:
                if st.button(f"{Constants.Icons.SETTINGS} 문제 해결",
                           key="sidebar_fix_issues", use_container_width=True):
                    st.switch_page("pages/99_Settings.py")


# 호환성을 위한 기존 함수명 유지
def render_service_status(service_name: str, status_data: Dict):
    StatusIndicator.render_service_card(service_name, status_data)