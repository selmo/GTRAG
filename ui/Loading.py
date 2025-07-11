"""
GTOne RAG System - 로딩 상태 표시 페이지
시스템 초기화 중에 표시되는 대기 화면
"""
import streamlit as st
import time
import sys
from pathlib import Path
import requests
from typing import Dict, Any
from ui.utils.streamlit_helpers import rerun

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

# 페이지 설정
st.set_page_config(
    page_title="GTOne RAG - 시스템 로딩 중",
    page_icon="⏳",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS 스타일
st.markdown("""
<style>
    .main-container {
        text-align: center;
        padding: 2rem;
    }

    .loading-spinner {
        display: inline-block;
        width: 50px;
        height: 50px;
        border: 3px solid #f3f3f3;
        border-top: 3px solid #ff6b6b;
        border-radius: 50%;
        animation: spin 2s linear infinite;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    .progress-container {
        background-color: #f0f2f6;
        border-radius: 25px;
        padding: 3px;
        margin: 20px 0;
    }

    .progress-bar {
        background: linear-gradient(90deg, #ff6b6b, #ffa726);
        height: 20px;
        border-radius: 25px;
        transition: width 0.5s ease-in-out;
    }

    .status-item {
        padding: 10px;
        margin: 5px 0;
        border-radius: 5px;
        background-color: #f8f9fa;
    }

    .status-ok {
        background-color: #d4edda;
        color: #155724;
    }

    .status-loading {
        background-color: #fff3cd;
        color: #856404;
    }

    .status-error {
        background-color: #f8d7da;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)


def check_system_status() -> Dict[str, Any]:
    """시스템 상태 확인"""
    status = {
        "api_server": False,
        "embedder": False,
        "qdrant": False,
        "redis": False,
        "overall_ready": False,
        "error_message": None
    }

    try:
        # API 서버 상태 확인
        try:
            response = requests.get("http://localhost:18000/docs", timeout=5)
            status["api_server"] = response.status_code == 200
        except:
            pass

        # 헬스체크 API 호출
        try:
            response = requests.get("http://localhost:18000/v1/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                services = health_data.get("services", {})

                # 각 서비스 상태 확인
                status["qdrant"] = services.get("qdrant", {}).get("status") == "connected"
                status["redis"] = True  # 헬스체크가 성공했다면 Redis도 작동 중
                status["embedder"] = True  # API가 동작한다면 임베더도 로드됨

                # 전체 상태 확인
                status["overall_ready"] = all([
                    status["api_server"],
                    status["qdrant"],
                    status["redis"],
                    status["embedder"]
                ])
        except Exception as e:
            status["error_message"] = str(e)

    except Exception as e:
        status["error_message"] = f"System check failed: {str(e)}"

    return status


def render_loading_screen():
    """로딩 화면 렌더링"""

    # 헤더
    st.markdown("""
    <div class="main-container">
        <h1>🤖 GTOne RAG System</h1>
        <h3>시스템 초기화 중...</h3>
        <div class="loading-spinner"></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # 진행 상황 표시
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.subheader("📊 초기화 진행 상황")

        # 상태 체크
        status = check_system_status()

        # 진행률 계산
        completed_services = sum([
            status["api_server"],
            status["qdrant"],
            status["redis"],
            status["embedder"]
        ])
        total_services = 4
        progress = completed_services / total_services

        # 프로그레스 바
        st.progress(progress)
        st.write(f"진행률: {int(progress * 100)}% ({completed_services}/{total_services})")

        st.markdown("### 🔍 서비스 상태")

        # 각 서비스 상태 표시
        services = [
            ("API 서버", status["api_server"], "웹 API 서버 시작"),
            ("임베딩 모델", status["embedder"], "E5-large 모델 로딩"),
            ("Qdrant", status["qdrant"], "벡터 데이터베이스 연결"),
            ("Redis", status["redis"], "캐시 서버 연결")
        ]

        for name, is_ready, description in services:
            if is_ready:
                st.markdown(f"""
                <div class="status-item status-ok">
                    ✅ <strong>{name}</strong>: {description}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="status-item status-loading">
                    ⏳ <strong>{name}</strong>: {description} 중...
                </div>
                """, unsafe_allow_html=True)

        # 에러 메시지 표시
        if status["error_message"]:
            st.markdown(f"""
            <div class="status-item status-error">
                ❌ <strong>오류</strong>: {status["error_message"]}
            </div>
            """, unsafe_allow_html=True)

        # 완료 상태 확인
        if status["overall_ready"]:
            st.success("🎉 모든 서비스가 준비되었습니다!")

            # 자동 리다이렉트
            st.balloons()
            time.sleep(2)
            st.switch_page("Home.py")
        else:
            # 예상 시간 표시
            remaining_services = total_services - completed_services
            estimated_time = remaining_services * 30  # 서비스당 약 30초 추정

            if estimated_time > 0:
                st.info(f"⏱️ 예상 완료 시간: 약 {estimated_time}초")

            # 자동 새로고침
            time.sleep(3)
            rerun()


def render_tips_section():
    """팁 섹션 렌더링"""
    st.markdown("---")

    with st.expander("💡 초기화 중에 알아두면 좋은 정보", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            ### 🔄 초기화 과정
            1. **Redis 시작**: 캐시 서버 초기화
            2. **Qdrant 연결**: 벡터 DB 준비
            3. **API 서버**: 웹 API 시작  
            4. **임베딩 모델**: E5-large 모델 다운로드 및 로딩

            ### ⏰ 예상 시간
            - 첫 실행: 3-5분 (모델 다운로드)
            - 재시작: 30초-1분
            """)

        with col2:
            st.markdown("""
            ### 🚀 준비 완료 후 기능
            - 📄 **문서 업로드**: PDF, 이미지, 텍스트
            - 🔍 **벡터 검색**: 의미 기반 문서 검색
            - 💬 **AI 채팅**: 문서 기반 질의응답
            - 📊 **상태 모니터링**: 시스템 상태 확인

            ### 🛠️ 문제 해결
            로딩이 오래 걸리면 브라우저를 새로고침해보세요.
            """)


def main():
    """메인 함수"""
    # 시스템 상태 확인
    initial_status = check_system_status()

    if initial_status["overall_ready"]:
        # 이미 준비되었다면 홈으로 리다이렉트
        st.success("✅ 시스템이 이미 준비되어 있습니다. 홈페이지로 이동합니다...")
        time.sleep(1)
        st.switch_page("Home.py")
    else:
        # 로딩 화면 표시
        render_loading_screen()
        render_tips_section()

    # 푸터
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666;">
        <p>GTOne RAG System v1.0.0 | Powered by Qdrant + Ollama</p>
        <p>문의: support@gtone.com</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()