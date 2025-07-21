# pages/40_System_Status.py
import streamlit as st
from datetime import datetime

# 기존 컴포넌트·헬퍼 재사용
from frontend.ui.utils.client_manager import ClientManager
from frontend.ui.components.sidebar import (
    render_system_status,  # 전체 상태 블록
    render_quick_actions,
    render_system_info
)
from frontend.ui.utils.system_health import SystemHealthManager
from frontend.ui.components.common import StatusIndicator
from frontend.ui.core.config import Constants

st.set_page_config(page_title="System Status", page_icon="🩺", layout="wide")

api_client = ClientManager.get_client()

st.title("🩺 System Status Dashboard")

# ─────────────────────────────────────────────────────────────
# 1) 상단: 기존 사이드바 블록 그대로 사용
# ─────────────────────────────────────────────────────────────
render_system_status(api_client)

st.divider()

# ─────────────────────────────────────────────────────────────
# 2) 서비스별 상세 카드
# ─────────────────────────────────────────────────────────────
st.header("🔧 Service Details")

cached = SystemHealthManager.get_cached_status()
if cached:
    for svc_name, svc_info in cached.services.items():
        StatusIndicator.render_service_card(
            svc_name,
            {
                "status": svc_info.status.value,
                "message": svc_info.message,
                "details": svc_info.details or {}
            }
        )
    st.caption(f"마지막 갱신 • {cached.last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
else:
    st.info("캐시된 시스템 상태가 없습니다. 상단의 **상태 확인** 버튼을 눌러 갱신하세요.")

st.divider()

# ─────────────────────────────────────────────────────────────
# 3) 관리/정보 패널 (두 열 배치)
# ─────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1])
with col1:
    render_quick_actions()
with col2:
    render_system_info()
