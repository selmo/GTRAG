"""
Streamlit 헬퍼 함수들
Streamlit 버전 호환성 및 공통 기능 제공
"""
import streamlit as st
import time


def rerun():
    """
    Streamlit 페이지 새로고침
    버전별 호환성 보장
    """
    # Streamlit 1.27+ 지원
    if hasattr(st, "rerun"):
        st.rerun()
    # Streamlit 1.18+ 지원  
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()
    # 구버전 fallback - 수동 새로고침 안내
    else:
        st.warning("⚠️ 페이지를 수동으로 새로고침해주세요 (F5 또는 Ctrl+R)")


def safe_rerun(delay: float = 0.1):
    """
    안전한 페이지 새로고침 (딜레이 포함)

    Args:
        delay: 새로고침 전 대기 시간 (초)
    """
    if delay > 0:
        time.sleep(delay)
    rerun()


def check_streamlit_version() -> str:
    """Streamlit 버전 확인"""
    try:
        return st.__version__
    except AttributeError:
        return "unknown"


def is_rerun_supported() -> bool:
    """rerun 기능 지원 여부 확인"""
    return hasattr(st, "rerun") or hasattr(st, "experimental_rerun")


def clear_cache():
    """Streamlit 캐시 초기화"""
    try:
        # Streamlit 1.18+
        if hasattr(st, "cache_data"):
            st.cache_data.clear()
        if hasattr(st, "cache_resource"):
            st.cache_resource.clear()

        # 구버전 지원
        if hasattr(st, "experimental_memo"):
            st.experimental_memo.clear()
        if hasattr(st, "experimental_singleton"):
            st.experimental_singleton.clear()

        return True
    except Exception as e:
        st.warning(f"캐시 초기화 실패: {e}")
        return False


def set_page_config_safe(**kwargs):
    """
    안전한 페이지 설정
    이미 설정된 경우 경고만 표시
    """
    try:
        st.set_page_config(**kwargs)
    except st.errors.StreamlitAPIException:
        # 이미 설정된 경우 무시
        pass


def get_query_params() -> dict:
    """URL 쿼리 파라미터 조회"""
    try:
        # Streamlit 1.18+
        if hasattr(st, "query_params"):
            return dict(st.query_params)
        # 구버전
        elif hasattr(st.experimental_get_query_params, "__call__"):
            return st.experimental_get_query_params()
        else:
            return {}
    except:
        return {}


def set_query_params(**params):
    """URL 쿼리 파라미터 설정"""
    try:
        # Streamlit 1.18+
        if hasattr(st, "query_params"):
            for key, value in params.items():
                st.query_params[key] = value
        # 구버전  
        elif hasattr(st.experimental_set_query_params, "__call__"):
            st.experimental_set_query_params(**params)
    except:
        pass


def create_download_button_safe(label: str, data, file_name: str,
                                mime: str = "text/plain", **kwargs):
    """
    안전한 다운로드 버튼 생성
    """
    try:
        return st.download_button(
            label=label,
            data=data,
            file_name=file_name,
            mime=mime,
            **kwargs
        )
    except Exception as e:
        st.error(f"다운로드 버튼 생성 실패: {e}")
        return False


def show_spinner_with_text(text: str = "처리 중..."):
    """텍스트가 포함된 스피너 컨텍스트 매니저"""
    return st.spinner(text)


def create_columns_responsive(*widths):
    """반응형 컬럼 생성"""
    try:
        return st.columns(widths)
    except:
        # fallback: 동일한 너비로 분할
        return st.columns(len(widths))


def display_metric_safe(label: str, value, delta=None, delta_color="normal"):
    """안전한 메트릭 표시"""
    try:
        st.metric(label, value, delta, delta_color=delta_color)
    except TypeError:
        # 구버전에서는 delta_color 미지원
        st.metric(label, value, delta)
    except:
        # 완전 fallback
        st.write(f"**{label}**: {value}")
        if delta:
            st.caption(f"변화: {delta}")


def create_tabs_safe(*tab_names):
    """안전한 탭 생성"""
    try:
        return st.tabs(tab_names)
    except:
        # fallback: selectbox 사용
        selected_tab = st.selectbox("탭 선택", tab_names, label_visibility="collapsed")
        return [st.container() if name == selected_tab else None for name in tab_names]


def render_markdown_safe(text: str, unsafe_allow_html: bool = False):
    """안전한 마크다운 렌더링"""
    try:
        st.markdown(text, unsafe_allow_html=unsafe_allow_html)
    except:
        # HTML 태그 제거 후 표시
        import re
        clean_text = re.sub(r'<[^>]+>', '', text)
        st.text(clean_text)


# 유틸리티 함수들
def wait_for_user_input(message: str = "계속하려면 Enter를 누르세요..."):
    """사용자 입력 대기 (개발/디버깅용)"""
    st.info(message)
    return st.button("계속")


def display_json_pretty(data: dict, expanded: bool = False):
    """JSON 데이터 예쁘게 표시"""
    import json

    with st.expander("JSON 데이터 보기", expanded=expanded):
        st.code(json.dumps(data, ensure_ascii=False, indent=2), language="json")


def create_info_box(title: str, content: str, type: str = "info"):
    """정보 박스 생성"""
    if type == "success":
        st.success(f"**{title}**\n\n{content}")
    elif type == "warning":
        st.warning(f"**{title}**\n\n{content}")
    elif type == "error":
        st.error(f"**{title}**\n\n{content}")
    else:
        st.info(f"**{title}**\n\n{content}")


def sidebar_spacer(height: int = 20):
    """사이드바 공백 추가"""
    with st.sidebar:
        st.markdown(f'<div style="height: {height}px;"></div>', unsafe_allow_html=True)


def main_spacer(height: int = 20):
    """메인 영역 공백 추가"""
    st.markdown(f'<div style="height: {height}px;"></div>', unsafe_allow_html=True)