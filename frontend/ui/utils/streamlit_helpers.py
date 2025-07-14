import streamlit as st

def rerun():
    """
    Streamlit 1.27+ 에서는 st.rerun() 사용,
    구버전 호환을 위해 fallback 제공
    """
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        rerun()
    else:
        raise RuntimeError("Streamlit 버전이 rerun 기능을 지원하지 않습니다.")
