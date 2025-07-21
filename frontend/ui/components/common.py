"""
강화된 공통 UI 컴포넌트 - 중복 코드 제거 및 일관성 향상
기존 common.py를 개선하여 더 많은 UI 패턴 통합
"""
import streamlit as st
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from datetime import datetime
import json
from enum import Enum

# 설정 import (config가 있는 경우)
try:
    from frontend.ui.core.config import Constants
    HAS_CONSTANTS = True
except ImportError:
    HAS_CONSTANTS = False


class ComponentTheme(Enum):
    """컴포넌트 테마"""
    DEFAULT = "default"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


class StatusIndicator:
    """향상된 상태 표시 컴포넌트"""

    @staticmethod
    def render_status(status: str, message: str, details: Optional[str] = None,
                     show_timestamp: bool = False):
        """상태 표시 렌더링 (기존 + 타임스탬프 옵션)"""
        if status in ["healthy", "connected", "success"]:
            st.success(f"✅ {message}")
        elif status in ["degraded", "warning"]:
            st.warning(f"⚠️ {message}")
        elif status in ["error", "disconnected", "failed"]:
            st.error(f"❌ {message}")
        else:
            st.info(f"ℹ️ {message}")

        if details:
            st.caption(details)

        if show_timestamp:
            st.caption(f"확인 시간: {datetime.now().strftime('%H:%M:%S')}")

    @staticmethod
    def render_service_status_grid(services: Dict[str, Dict], columns: int = 3):
        """서비스 상태를 그리드로 표시"""
        service_items = list(services.items())

        for i in range(0, len(service_items), columns):
            cols = st.columns(columns)
            for j, (service_name, service_data) in enumerate(service_items[i:i+columns]):
                with cols[j]:
                    StatusIndicator.render_service_card(service_name, service_data)

    @staticmethod
    def render_service_card(service_name: str, service_data: Dict):
        """개별 서비스 카드 렌더링"""
        status = service_data.get('status', 'unknown')
        message = service_data.get('message', '')

        # 상태별 스타일
        if status == 'connected':
            st.success(f"🟢 **{service_name}**")
        elif status == 'degraded':
            st.warning(f"🟡 **{service_name}**")
        elif status == 'disconnected':
            st.error(f"🔴 **{service_name}**")
        else:
            st.info(f"⚪ **{service_name}**")

        if message:
            st.caption(message)

        # 추가 세부 정보
        details = service_data.get('details', {})
        if details:
            with st.expander("세부 정보", expanded=False):
                for key, value in details.items():
                    if isinstance(value, list) and len(value) > 3:
                        st.caption(f"• {key}: {len(value)}개")
                    else:
                        st.caption(f"• {key}: {value}")

    @staticmethod
    def render_system_overview(overview: Dict[str, Any]):
        """시스템 전체 개요 표시 (대시보드용)"""
        system_ready = overview.get('system_ready', False)
        critical_issues = overview.get('critical_issues', [])
        warnings = overview.get('warnings', [])

        # 전체 상태
        if system_ready:
            if warnings:
                st.warning("⚠️ 시스템이 작동 중이지만 일부 경고가 있습니다")
            else:
                st.success("✅ 시스템이 정상 작동 중입니다")
        else:
            st.error("❌ 시스템에 문제가 있습니다")

        # 문제점 표시
        if critical_issues:
            with st.expander("🚨 중요 문제", expanded=True):
                for issue in critical_issues:
                    st.error(f"• {issue}")

        if warnings:
            with st.expander("⚠️ 경고", expanded=False):
                for warning in warnings:
                    st.warning(f"• {warning}")

        # 추천 사항
        recommendations = overview.get('recommendations', [])
        if recommendations:
            with st.expander("💡 추천 사항", expanded=False):
                for rec in recommendations:
                    st.info(f"• {rec}")


class MetricCard:
    """향상된 메트릭 카드 컴포넌트"""

    @staticmethod
    def render_metric_grid(metrics: List[Dict[str, Any]], columns: int = 4):
        """메트릭 그리드 렌더링 (기존 유지)"""
        cols = st.columns(columns)

        for i, metric in enumerate(metrics):
            with cols[i % columns]:
                MetricCard.render_single_metric(
                    title=metric.get("title", ""),
                    value=metric.get("value", "N/A"),
                    delta=metric.get("delta"),
                    help_text=metric.get("help")
                )

    @staticmethod
    def render_single_metric(title: str, value: Any, delta: Any = None,
                           help_text: str = None, format_large_numbers: bool = True):
        """단일 메트릭 렌더링 (개선된 버전)"""
        # 큰 숫자 포맷팅
        if format_large_numbers and isinstance(value, (int, float)):
            if value >= 1000000:
                display_value = f"{value/1000000:.1f}M"
            elif value >= 1000:
                display_value = f"{value/1000:.1f}K"
            else:
                display_value = value
        else:
            display_value = value

        st.metric(
            label=title,
            value=display_value,
            delta=delta,
            help=help_text
        )

    @staticmethod
    def render_performance_metrics(performance: Dict[str, float]):
        """성능 메트릭 특화 표시"""
        cols = st.columns(len(performance))

        for i, (metric_name, value) in enumerate(performance.items()):
            with cols[i]:
                # 성능 지표별 색상 및 단위
                if 'time' in metric_name.lower() or 'duration' in metric_name.lower():
                    if value < 1:
                        delta_color = "normal"
                        unit = "초"
                    elif value < 3:
                        delta_color = "normal"
                        unit = "초"
                    else:
                        delta_color = "inverse"
                        unit = "초"

                    st.metric(
                        label=metric_name.replace('_', ' ').title(),
                        value=f"{value:.2f}{unit}",
                        delta=None
                    )
                else:
                    st.metric(
                        label=metric_name.replace('_', ' ').title(),
                        value=value
                    )

    @staticmethod
    def render_comparison_metrics(current: Dict, previous: Dict,
                                title: str = "성능 비교"):
        """이전 값과 비교하는 메트릭"""
        st.subheader(title)

        all_keys = set(current.keys()) | set(previous.keys())
        cols = st.columns(min(len(all_keys), 4))

        for i, key in enumerate(all_keys):
            with cols[i % 4]:
                current_val = current.get(key, 0)
                previous_val = previous.get(key, 0)

                if previous_val != 0:
                    delta = current_val - previous_val
                    delta_percent = (delta / previous_val) * 100
                    delta_text = f"{delta_percent:+.1f}%"
                else:
                    delta_text = None

                st.metric(
                    label=key.replace('_', ' ').title(),
                    value=current_val,
                    delta=delta_text
                )


class LoadingSpinner:
    """향상된 로딩 스피너 컴포넌트"""

    @staticmethod
    def render_loading_screen(title: str, message: str, progress: float = None,
                            show_steps: bool = False, steps: List[str] = None):
        """로딩 화면 렌더링 (개선된 버전)"""
        st.markdown(f"""
        <div style="text-align: center; padding: 2rem;">
            <h2>{title}</h2>
            <p>{message}</p>
            <div style="display: inline-block; width: 40px; height: 40px; 
                        border: 3px solid #f3f3f3; border-top: 3px solid #ff6b6b; 
                        border-radius: 50%; animation: spin 1s linear infinite;">
            </div>
        </div>
        <style>
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        </style>
        """, unsafe_allow_html=True)

        if progress is not None:
            st.progress(progress)
            st.caption(f"진행률: {int(progress * 100)}%")

        if show_steps and steps:
            LoadingSpinner.render_step_progress(steps, int((progress or 0) * len(steps)))

    @staticmethod
    def render_step_progress(steps: List[str], current_step: int = 0):
        """단계별 진행 상황 표시 (개선된 버전)"""
        for i, step_name in enumerate(steps):
            if i < current_step:
                st.success(f"✅ {step_name}")
            elif i == current_step:
                st.info(f"⏳ {step_name}")
            else:
                st.caption(f"⏸️ {step_name}")

        progress = current_step / len(steps) if steps else 0
        st.progress(progress)

    @staticmethod
    def render_inline_spinner(message: str, key: str = "spinner"):
        """인라인 스피너 (작은 크기)"""
        with st.container():
            col1, col2 = st.columns([1, 4])
            with col1:
                st.markdown("""
                <div style="display: inline-block; width: 20px; height: 20px; 
                            border: 2px solid #f3f3f3; border-top: 2px solid #ff6b6b; 
                            border-radius: 50%; animation: spin 1s linear infinite;">
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.write(message)


class ErrorDisplay:
    """향상된 에러 표시 컴포넌트"""

    @staticmethod
    def render_error_with_suggestions(error_msg: str, suggestions: List[str] = None,
                                    error_type: str = "error", show_details: bool = False,
                                    details: Dict = None):
        """에러와 해결 제안 표시 (개선된 버전)"""
        if error_type == "critical":
            st.error(f"🚨 치명적 오류: {error_msg}")
        elif error_type == "warning":
            st.warning(f"⚠️ 경고: {error_msg}")
        else:
            st.error(f"❌ {error_msg}")

        if suggestions:
            with st.expander("💡 해결 방안", expanded=(error_type == "critical")):
                for i, suggestion in enumerate(suggestions, 1):
                    st.write(f"{i}. {suggestion}")

        if show_details and details:
            with st.expander("🔧 기술 세부 정보", expanded=False):
                ErrorDisplay.render_error_details(details)

    @staticmethod
    def render_error_details(details: Dict):
        """에러 세부 정보 표시"""
        for key, value in details.items():
            if isinstance(value, dict):
                st.write(f"**{key}:**")
                st.json(value)
            elif isinstance(value, list):
                st.write(f"**{key}:** {len(value)}개 항목")
                for item in value[:3]:  # 처음 3개만
                    st.caption(f"• {item}")
                if len(value) > 3:
                    st.caption(f"... 외 {len(value) - 3}개")
            else:
                st.write(f"**{key}:** {value}")

    @staticmethod
    def render_validation_errors(errors: List[str], max_show: int = 5):
        """검증 오류 목록 표시 (기존 유지)"""
        if not errors:
            st.success("✅ 모든 검증 통과")
            return

        st.error(f"❌ {len(errors)}개의 문제가 발견되었습니다")

        with st.expander("오류 상세", expanded=True):
            for i, error in enumerate(errors[:max_show], 1):
                st.write(f"{i}. {error}")

            if len(errors) > max_show:
                st.caption(f"... 외 {len(errors) - max_show}개 문제")

    @staticmethod
    def render_error_summary(error_counts: Dict[str, int]):
        """에러 요약 통계"""
        total_errors = sum(error_counts.values())

        if total_errors == 0:
            st.success("✅ 오류가 없습니다")
            return

        st.error(f"❌ 총 {total_errors}개의 문제가 있습니다")

        cols = st.columns(len(error_counts))
        for i, (error_type, count) in enumerate(error_counts.items()):
            with cols[i]:
                if count > 0:
                    st.metric(error_type.title(), count)


class ActionButton:
    """향상된 액션 버튼 컴포넌트"""

    @staticmethod
    def render_action_row(actions: List[Dict[str, Any]], equal_width: bool = True):
        """액션 버튼 행 렌더링 (개선된 버전)"""
        if equal_width:
            cols = st.columns(len(actions))
        else:
            # 가중치가 있는 경우
            weights = [action.get("weight", 1) for action in actions]
            cols = st.columns(weights)

        for i, action in enumerate(actions):
            with cols[i]:
                ActionButton.render_single_action(action, use_container_width=equal_width)

    @staticmethod
    def render_single_action(action: Dict[str, Any], use_container_width: bool = True):
        """단일 액션 버튼 렌더링"""
        button_type = action.get("type", "secondary")
        disabled = action.get("disabled", False)
        help_text = action.get("help", "")

        if st.button(
            action.get("label", "Action"),
            type=button_type,
            disabled=disabled,
            use_container_width=use_container_width,
            help=help_text,
            key=action.get("key", f"action_{action.get('label', '')}")
        ):
            callback = action.get("callback")
            if callback and callable(callback):
                try:
                    callback()
                except Exception as e:
                    st.error(f"액션 실행 실패: {str(e)}")

    @staticmethod
    def render_confirmation_button(label: str, message: str, key: str,
                                 callback=None, type: str = "primary",
                                 confirm_label: str = "확인하려면 다시 클릭"):
        """확인 버튼 (두 번 클릭 필요, 개선된 버전)"""
        confirm_key = f"confirm_{key}"

        if st.button(label, type=type, key=key):
            if not st.session_state.get(confirm_key, False):
                st.session_state[confirm_key] = True
                st.warning(f"⚠️ {message}")
                st.info(confirm_label)
            else:
                if callback and callable(callback):
                    try:
                        callback()
                        # 성공 시 확인 상태 리셋
                        if confirm_key in st.session_state:
                            del st.session_state[confirm_key]
                    except Exception as e:
                        st.error(f"작업 실행 실패: {str(e)}")
                        # 실패 시에도 확인 상태 리셋
                        if confirm_key in st.session_state:
                            del st.session_state[confirm_key]

    @staticmethod
    def render_async_button(label: str, async_callback, key: str,
                          loading_message: str = "처리 중...",
                          success_message: str = "완료되었습니다"):
        """비동기 작업 버튼 (로딩 상태 표시)"""
        loading_key = f"loading_{key}"

        if st.session_state.get(loading_key, False):
            LoadingSpinner.render_inline_spinner(loading_message, key)
            return

        if st.button(label, key=key):
            st.session_state[loading_key] = True

            try:
                # 비동기 작업 시뮬레이션 (실제로는 async/await 사용)
                result = async_callback()
                st.success(success_message)

                if result:
                    st.write(result)

            except Exception as e:
                st.error(f"작업 실패: {str(e)}")
            finally:
                st.session_state[loading_key] = False
                st.rerun()


class FileDisplay:
    """향상된 파일 표시 컴포넌트"""

    @staticmethod
    def render_file_card(file_info: Dict[str, Any], actions: List[Dict] = None,
                        show_preview: bool = False):
        """파일 카드 렌더링 (개선된 버전)"""
        with st.container():
            col1, col2 = st.columns([3, 1])

            with col1:
                # 파일 아이콘 및 이름
                icon = FileDisplay._get_file_icon(file_info.get("name", ""))
                name = file_info.get("display_name", file_info.get("name", "Unknown"))

                # 파일 타입에 따른 스타일링
                if file_info.get("type") == "extracted":
                    st.write(f"{icon} **{name}** 📦")
                    st.caption(f"압축 파일에서 추출: {file_info.get('archive_path', '')}")
                else:
                    st.write(f"{icon} **{name}**")

                # 메타데이터 표시
                metadata = FileDisplay._format_file_metadata(file_info)
                if metadata:
                    st.caption(" | ".join(metadata))

            with col2:
                if actions:
                    for action in actions:
                        if st.button(
                            action.get("icon", "🔘"),
                            help=action.get("help", ""),
                            key=action.get("key", f"file_action_{action.get('label')}")
                        ):
                            callback = action.get("callback")
                            if callback and callable(callback):
                                callback(file_info)

        # 파일 미리보기
        if show_preview and file_info.get("content"):
            FileDisplay.render_file_preview(file_info)

    @staticmethod
    def render_file_preview(file_info: Dict[str, Any], max_length: int = 300):
        """파일 내용 미리보기"""
        content = file_info.get("content", "")
        if not content:
            return

        with st.expander("📄 파일 미리보기", expanded=False):
            if len(content) > max_length:
                preview = content[:max_length] + "..."
                st.text_area("미리보기", preview, height=150, disabled=True)

                if st.button("전체 내용 보기", key=f"full_content_{file_info.get('name')}"):
                    st.text_area("전체 내용", content, height=400, disabled=True)
            else:
                st.text_area("내용", content, height=150, disabled=True)

    @staticmethod
    def render_file_grid(files: List[Dict], columns: int = 3, actions: List[Dict] = None):
        """파일 그리드 표시"""
        for i in range(0, len(files), columns):
            cols = st.columns(columns)
            for j, file_info in enumerate(files[i:i+columns]):
                with cols[j]:
                    FileDisplay.render_file_card(file_info, actions)

    @staticmethod
    def _format_file_metadata(file_info: Dict) -> List[str]:
        """파일 메타데이터 포맷팅"""
        metadata = []

        if "size" in file_info:
            metadata.append(f"💾 {file_info['size']}")
        if "time" in file_info:
            metadata.append(f"⏰ {file_info['time']}")
        if "chunks" in file_info:
            chunks = file_info['chunks']
            if chunks > 0:
                metadata.append(f"🧩 {chunks} 청크")
            else:
                metadata.append("🚫 처리 실패")

        return metadata

    @staticmethod
    def _get_file_icon(filename: str) -> str:
        """파일 아이콘 반환 (설정 기반)"""
        if not filename:
            return "📎"

        ext = filename.lower().split('.')[-1] if '.' in filename else ''

        if HAS_CONSTANTS:
            return Constants.Icons.FILE_ICONS.get(ext, Constants.Icons.FILE_ICONS['default'])

        # Fallback 아이콘
        icons = {
            'pdf': '📄', 'doc': '📝', 'docx': '📝', 'txt': '📃',
            'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️',
            'zip': '📦', 'rar': '📦', '7z': '📦'
        }
        return icons.get(ext, '📎')


class SearchInterface:
    """향상된 검색 인터페이스 컴포넌트"""

    @staticmethod
    def render_search_bar(placeholder: str = "검색...", key: str = "search",
                         show_filters: bool = False, filters: Dict = None):
        """검색 바 렌더링 (개선된 버전)"""
        col1, col2 = st.columns([4, 1])

        with col1:
            query = st.text_input(
                "검색어",
                placeholder=placeholder,
                label_visibility="collapsed",
                key=f"{key}_input"
            )

        with col2:
            search_clicked = st.button("🔍", key=f"{key}_button", use_container_width=True)

        # 필터 표시
        filter_values = {}
        if show_filters and filters:
            filter_values = SearchInterface.render_search_filters(filters, key)

        if search_clicked and query.strip():
            return query.strip(), filter_values

        return None, filter_values

    @staticmethod
    def render_search_filters(filters: Dict[str, Any], key: str = "filters"):
        """검색 필터 렌더링 (기존 유지 + 개선)"""
        with st.expander("🔧 검색 필터"):
            filter_values = {}

            for filter_name, filter_config in filters.items():
                filter_type = filter_config.get("type", "text")

                if filter_type == "selectbox":
                    filter_values[filter_name] = st.selectbox(
                        filter_config.get("label", filter_name),
                        filter_config.get("options", []),
                        key=f"{key}_{filter_name}"
                    )
                elif filter_type == "multiselect":
                    filter_values[filter_name] = st.multiselect(
                        filter_config.get("label", filter_name),
                        filter_config.get("options", []),
                        key=f"{key}_{filter_name}"
                    )
                elif filter_type == "slider":
                    filter_values[filter_name] = st.slider(
                        filter_config.get("label", filter_name),
                        min_value=filter_config.get("min", 0),
                        max_value=filter_config.get("max", 100),
                        value=filter_config.get("default", 50),
                        key=f"{key}_{filter_name}"
                    )
                elif filter_type == "date_range":
                    filter_values[filter_name] = st.date_input(
                        filter_config.get("label", filter_name),
                        value=filter_config.get("default", []),
                        key=f"{key}_{filter_name}"
                    )

        return filter_values

    @staticmethod
    def render_search_suggestions(suggestions: List[str], key: str = "suggestions"):
        """검색 제안 표시"""
        if not suggestions:
            return

        st.write("💡 **검색 제안:**")
        cols = st.columns(min(len(suggestions), 3))

        for i, suggestion in enumerate(suggestions):
            with cols[i % 3]:
                if st.button(f"🔍 {suggestion}", key=f"{key}_{i}", use_container_width=True):
                    return suggestion

        return None


class NavigationHelper:
    """향상된 네비게이션 헬퍼"""

    @staticmethod
    def render_breadcrumb(items: List[str], separator: str = " > "):
        """브레드크럼 네비게이션 (개선된 버전)"""
        if len(items) > 1:
            breadcrumb_parts = []
            for i, item in enumerate(items):
                if i == len(items) - 1:
                    breadcrumb_parts.append(f"**{item}**")
                else:
                    breadcrumb_parts.append(item)

            breadcrumb = separator.join(breadcrumb_parts)
            st.markdown(breadcrumb)

    @staticmethod
    def render_page_navigation(pages: List[Dict[str, str]], current_page: str):
        """페이지 네비게이션 (기존 유지)"""
        col_count = min(len(pages), 5)
        cols = st.columns(col_count)

        for i, page in enumerate(pages[:col_count]):
            with cols[i]:
                is_current = page.get("key") == current_page
                button_type = "primary" if is_current else "secondary"

                if st.button(
                    page.get("label", "Page"),
                    type=button_type,
                    disabled=is_current,
                    use_container_width=True,
                    key=f"nav_{page.get('key')}"
                ):
                    if page.get("url"):
                        st.switch_page(page["url"])

    @staticmethod
    def render_quick_nav(nav_items: Dict[str, str], title: str = "빠른 이동"):
        """빠른 네비게이션 버튼들"""
        st.subheader(title)

        cols = st.columns(len(nav_items))
        for i, (label, url) in enumerate(nav_items.items()):
            with cols[i]:
                if st.button(label, key=f"quick_nav_{i}", use_container_width=True):
                    st.switch_page(url)


# 편의 함수들 (하위 호환성)
def show_status(status: str, message: str, details: str = None):
    """상태 표시 편의 함수"""
    StatusIndicator.render_status(status, message, details)


def show_loading(title: str, message: str, progress: float = None):
    """로딩 화면 편의 함수"""
    LoadingSpinner.render_loading_screen(title, message, progress)


def show_error_with_help(error: str, suggestions: List[str] = None):
    """에러와 도움말 표시 편의 함수"""
    ErrorDisplay.render_error_with_suggestions(error, suggestions)


def render_metric_dashboard(metrics: Dict[str, Any], title: str = "대시보드"):
    """메트릭 대시보드 렌더링"""
    st.header(title)

    # 주요 메트릭 (상단)
    main_metrics = metrics.get('main', [])
    if main_metrics:
        MetricCard.render_metric_grid(main_metrics)

    # 성능 메트릭 (하단)
    performance = metrics.get('performance', {})
    if performance:
        st.subheader("성능 지표")
        MetricCard.render_performance_metrics(performance)

    # 상태 개요 (있는 경우)
    status_overview = metrics.get('status_overview')
    if status_overview:
        st.divider()
        StatusIndicator.render_system_overview(status_overview)


class DataTable:
    """향상된 데이터 테이블 컴포넌트"""

    @staticmethod
    def render_sortable_table(data: List[Dict], columns: List[str],
                             sortable_columns: List[str] = None,
                             searchable: bool = True,
                             items_per_page: int = 10):
        """정렬 가능한 테이블 렌더링"""
        if not data:
            st.info("표시할 데이터가 없습니다.")
            return

        # 검색 기능
        filtered_data = data
        if searchable:
            search_term = st.text_input("🔍 테이블 검색", key="table_search")
            if search_term:
                filtered_data = [
                    row for row in data
                    if any(search_term.lower() in str(row.get(col, "")).lower()
                          for col in columns)
                ]

        # 정렬 기능
        if sortable_columns:
            col1, col2 = st.columns([2, 1])
            with col1:
                sort_column = st.selectbox("정렬 기준", sortable_columns)
            with col2:
                sort_order = st.selectbox("정렬 순서", ["오름차순", "내림차순"])

            if sort_column:
                reverse = sort_order == "내림차순"
                filtered_data = sorted(
                    filtered_data,
                    key=lambda x: x.get(sort_column, ""),
                    reverse=reverse
                )

        # 페이지네이션
        total_items = len(filtered_data)
        total_pages = (total_items + items_per_page - 1) // items_per_page

        if total_pages > 1:
            page = st.number_input(
                "페이지",
                min_value=1,
                max_value=total_pages,
                value=1
            ) - 1
        else:
            page = 0

        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, total_items)
        page_data = filtered_data[start_idx:end_idx]

        # 테이블 헤더
        header_cols = st.columns(len(columns))
        for i, col in enumerate(columns):
            with header_cols[i]:
                st.write(f"**{col}**")

        # 테이블 데이터
        for row in page_data:
            data_cols = st.columns(len(columns))
            for i, col in enumerate(columns):
                with data_cols[i]:
                    value = row.get(col, "")
                    st.write(str(value))

        # 페이지 정보
        if total_pages > 1:
            st.caption(f"페이지 {page + 1} / {total_pages} (총 {total_items}개 항목)")

    @staticmethod
    def render_data_grid(data: List[Dict], columns: int = 3,
                        card_renderer: Callable = None):
        """데이터를 카드 그리드로 표시"""
        if not data:
            st.info("표시할 데이터가 없습니다.")
            return

        for i in range(0, len(data), columns):
            cols = st.columns(columns)
            for j, item in enumerate(data[i:i+columns]):
                with cols[j]:
                    if card_renderer:
                        card_renderer(item)
                    else:
                        # 기본 카드 렌더링
                        with st.container():
                            for key, value in item.items():
                                if key != "id":  # ID는 숨김
                                    st.write(f"**{key}:** {value}")


class AdvancedUI:
    """고급 UI 컴포넌트"""

    @staticmethod
    def render_tabs_with_badges(tab_config: List[Dict]):
        """뱃지가 있는 탭 렌더링"""
        tab_labels = []
        for config in tab_config:
            label = config['label']
            badge = config.get('badge')
            if badge:
                label += f" ({badge})"
            tab_labels.append(label)

        tabs = st.tabs(tab_labels)

        for i, (tab, config) in enumerate(zip(tabs, tab_config)):
            with tab:
                content_func = config.get('content')
                if content_func and callable(content_func):
                    content_func()

    @staticmethod
    def render_collapsible_sections(sections: List[Dict]):
        """접을 수 있는 섹션들"""
        for section in sections:
            title = section.get('title', '섹션')
            expanded = section.get('expanded', False)
            content_func = section.get('content')

            with st.expander(title, expanded=expanded):
                if content_func and callable(content_func):
                    content_func()

    @staticmethod
    def render_sidebar_menu(menu_items: List[Dict], current_page: str = None):
        """사이드바 메뉴"""
        st.sidebar.markdown("### 📋 메뉴")

        for item in menu_items:
            label = item.get('label', '')
            icon = item.get('icon', '•')
            page = item.get('page', '')
            disabled = item.get('disabled', False)

            is_current = page == current_page

            if is_current:
                st.sidebar.markdown(f"**{icon} {label}** ← 현재 페이지")
            elif not disabled:
                if st.sidebar.button(f"{icon} {label}", key=f"menu_{page}"):
                    if page.endswith('.py'):
                        st.switch_page(page)
                    else:
                        st.session_state.current_page = page
                        st.rerun()
            else:
                st.sidebar.markdown(f"~~{icon} {label}~~ (비활성)")

    @staticmethod
    def render_progress_tracker(steps: List[Dict], current_step: int = 0):
        """진행 상황 추적기"""
        st.markdown("### 📊 진행 상황")

        cols = st.columns(len(steps))
        for i, (step, col) in enumerate(zip(steps, cols)):
            with col:
                step_name = step.get('name', f'단계 {i+1}')

                if i < current_step:
                    st.success(f"✅ {step_name}")
                elif i == current_step:
                    st.info(f"⏳ {step_name}")
                else:
                    st.write(f"⏸️ {step_name}")

                if step.get('description'):
                    st.caption(step['description'])

        # 전체 진행률
        progress = (current_step + 1) / len(steps) if steps else 0
        st.progress(min(progress, 1.0))
        st.caption(f"진행률: {int(progress * 100)}%")

    @staticmethod
    def render_notification_area():
        """알림 영역"""
        notifications = st.session_state.get('notifications', [])

        if notifications:
            st.markdown("### 🔔 알림")
            for i, notification in enumerate(notifications):
                notification_type = notification.get('type', 'info')
                message = notification.get('message', '')
                timestamp = notification.get('timestamp')

                col1, col2 = st.columns([4, 1])
                with col1:
                    if notification_type == 'success':
                        st.success(message)
                    elif notification_type == 'warning':
                        st.warning(message)
                    elif notification_type == 'error':
                        st.error(message)
                    else:
                        st.info(message)

                    if timestamp:
                        st.caption(f"시간: {timestamp}")

                with col2:
                    if st.button("✕", key=f"dismiss_{i}", help="알림 제거"):
                        notifications.pop(i)
                        st.session_state.notifications = notifications
                        st.rerun()


class ThemeManager:
    """테마 관리 컴포넌트"""

    @staticmethod
    def apply_custom_css():
        """커스텀 CSS 적용"""
        st.markdown("""
        <style>
        /* 개선된 버튼 스타일 */
        .stButton > button {
            border-radius: 6px;
            border: 1px solid #dee2e6;
            transition: all 0.2s ease;
        }
        
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* 메트릭 카드 스타일 */
        .metric-card {
            background: white;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12);
            border: 1px solid #e1e5e9;
        }
        
        /* 상태 표시기 스타일 */
        .status-indicator {
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.875rem;
            font-weight: 500;
        }
        
        .status-success {
            background-color: #d4edda;
            color: #155724;
        }
        
        .status-warning {
            background-color: #fff3cd;
            color: #856404;
        }
        
        .status-error {
            background-color: #f8d7da;
            color: #721c24;
        }
        
        /* 로딩 스피너 */
        .loading-spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid #f3f3f3;
            border-top: 2px solid #3498db;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        /* 테이블 개선 */
        .dataframe {
            border: 1px solid #dee2e6;
            border-radius: 6px;
        }
        
        /* 사이드바 스타일 */
        .css-1d391kg {
            padding-top: 1rem;
        }
        
        /* 알림 스타일 */
        .notification {
            padding: 0.75rem;
            margin: 0.5rem 0;
            border-radius: 6px;
            border-left: 4px solid;
        }
        
        .notification-info {
            background-color: #e7f3ff;
            border-left-color: #2196f3;
        }
        
        .notification-success {
            background-color: #e8f5e8;
            border-left-color: #4caf50;
        }
        
        .notification-warning {
            background-color: #fff8e1;
            border-left-color: #ff9800;
        }
        
        .notification-error {
            background-color: #ffebee;
            border-left-color: #f44336;
        }
        </style>
        """, unsafe_allow_html=True)

    @staticmethod
    def set_page_config_enhanced(page_title: str = "GTOne RAG System",
                                page_icon: str = "📚",
                                layout: str = "wide"):
        """향상된 페이지 설정"""
        st.set_page_config(
            page_title=page_title,
            page_icon=page_icon,
            layout=layout,
            initial_sidebar_state="expanded"
        )

        # 커스텀 CSS 적용
        ThemeManager.apply_custom_css()


# 유틸리티 함수
def add_notification(message: str, notification_type: str = "info",
                    auto_dismiss: bool = True, duration: int = 5):
    """알림 추가"""
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []

    notification = {
        'message': message,
        'type': notification_type,
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'auto_dismiss': auto_dismiss,
        'duration': duration
    }

    st.session_state.notifications.append(notification)

    # 자동 제거 (실제로는 JavaScript 필요)
    if auto_dismiss:
        # Streamlit 제한으로 인해 실제 자동 제거는 구현 어려움
        pass


def clear_notifications():
    """모든 알림 제거"""
    st.session_state.notifications = []


def format_bytes(bytes_value: int) -> str:
    """바이트를 읽기 쉬운 형식으로 변환"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def format_duration(seconds: float) -> str:
    """초를 읽기 쉬운 형식으로 변환"""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}초"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}분"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}시간"