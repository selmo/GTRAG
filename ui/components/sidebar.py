"""
사이드바 컴포넌트
"""
import streamlit as st
from datetime import datetime
from typing import Dict, Optional


def render_sidebar(api_client):
    """사이드바 렌더링"""
    with st.sidebar:
        st.title("📚 GTOne RAG System")
        
        # 시스템 상태 섹션
        render_system_status(api_client)
        
        st.divider()
        
        # 파일 업로드 섹션
        from .uploader import render_file_uploader, render_uploaded_files
        render_file_uploader(api_client)
        render_uploaded_files()
        
        st.divider()
        
        # 시스템 정보
        render_system_info()


def render_system_status(api_client):
    """시스템 상태 표시"""
    st.header("🔧 시스템 상태")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 상태 확인", use_container_width=True):
            check_system_health(api_client)
    
    with col2:
        if st.button("📊 통계", use_container_width=True):
            show_system_stats()
    
    # 자동 상태 확인 (세션 시작 시)
    if 'health_checked' not in st.session_state:
        st.session_state.health_checked = True
        check_system_health(api_client)


def check_system_health(api_client):
    """시스템 건강 상태 확인"""
    with st.spinner("시스템 상태 확인 중..."):
        try:
            health_data = api_client.health_check()
            
            if health_data.get('status') == 'healthy':
                st.success("✅ 시스템 정상 작동 중")
                
                # 서비스별 상태 표시
                services = health_data.get('services', {})
                
                # Qdrant 상태
                render_service_status("Qdrant", services.get('qdrant', {}))
                
                # Ollama 상태
                render_service_status("Ollama", services.get('ollama', {}))
                
                # Celery 상태
                render_service_status("Celery", services.get('celery', {}))
                
                # 마지막 확인 시간 저장
                st.session_state.last_health_check = datetime.now()
                
            else:
                st.error("❌ 시스템 연결 실패")
                if 'message' in health_data:
                    st.error(health_data['message'])
                    
        except Exception as e:
            st.error(f"❌ 시스템 연결 실패: {str(e)}")
            
            # 개별 서비스 상태 추측
            st.info("💡 개별 서비스 확인이 필요합니다.")
            
            # 디버그 정보
            with st.expander("🐛 디버그 정보"):
                st.code(f"""
API URL: {api_client.base_url}
Error: {str(e)}
                """)


def render_service_status(service_name: str, status_data: Dict):
    """개별 서비스 상태 렌더링"""
    status = status_data.get('status', 'unknown')
    
    # 상태 아이콘
    status_icons = {
        'connected': '🟢',
        'disconnected': '🔴',
        'unknown': '🟡'
    }
    
    icon = status_icons.get(status, '🟡')
    
    with st.container():
        st.write(f"{icon} **{service_name}**: {status}")
        
        # 추가 정보
        if service_name == "Qdrant" and status == 'connected':
            collections = status_data.get('collections', [])
            if collections:
                st.caption(f"컬렉션: {', '.join(collections)}")
        
        elif service_name == "Ollama" and status == 'connected':
            host = status_data.get('host', 'N/A')
            models = status_data.get('models', [])
            st.caption(f"호스트: {host}")
            if models:
                st.caption(f"모델: {', '.join(models[:3])}")  # 최대 3개만 표시


def show_system_stats():
    """시스템 통계 표시"""
    with st.expander("📊 시스템 통계", expanded=True):
        # 업로드 통계
        from .uploader import get_upload_summary
        stats = get_upload_summary()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("문서 수", stats['total_files'])
        
        with col2:
            st.metric("총 청크", stats['total_chunks'])
        
        with col3:
            st.metric("총 용량", f"{stats['total_size']:.1f} MB")
        
        # 세션 통계
        st.divider()
        
        if 'messages' in st.session_state:
            message_count = len(st.session_state.messages)
            user_messages = sum(1 for m in st.session_state.messages if m['role'] == 'user')
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("대화 수", message_count)
            with col2:
                st.metric("질문 수", user_messages)
        
        # 마지막 활동
        if 'last_health_check' in st.session_state:
            st.caption(f"마지막 확인: {st.session_state.last_health_check.strftime('%H:%M:%S')}")


def render_system_info():
    """시스템 정보 표시"""
    st.header("ℹ️ 정보")
    
    with st.expander("시스템 정보"):
        st.write("**버전**: v1.0.0")
        st.write("**임베딩 모델**: E5-large")
        st.write("**벡터 DB**: Qdrant")
        st.write("**LLM**: Ollama (External)")
        
        st.divider()
        
        st.caption("**지원 문서 형식**")
        st.caption("• PDF, Word, 텍스트")
        st.caption("• PNG, JPEG (OCR)")
        
    with st.expander("단축키"):
        st.write("**Ctrl/Cmd + Enter**: 메시지 전송")
        st.write("**Ctrl/Cmd + K**: 검색 포커스")
        st.write("**Ctrl/Cmd + L**: 대화 초기화")
        
    with st.expander("유용한 링크"):
        st.markdown("[📚 API 문서](http://localhost:8000/docs)")
        st.markdown("[🗄️ Qdrant UI](http://localhost:6333/dashboard)")
        st.markdown("[📖 사용 가이드](https://github.com/your-org/gtrag)")


def render_quick_actions():
    """빠른 작업 버튼들"""
    st.header("⚡ 빠른 작업")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ 대화 초기화", use_container_width=True):
            if 'messages' in st.session_state:
                st.session_state.messages = []
                st.success("대화가 초기화되었습니다.")
                st.experimental_rerun()
    
    with col2:
        if st.button("🔄 새로고침", use_container_width=True):
            st.experimental_rerun()
