"""
채팅 인터페이스 컴포넌트
"""
import streamlit as st
from typing import Dict, List, Optional
from datetime import datetime
from frontend.ui.utils.streamlit_helpers import rerun

def render_chat_history():
    """채팅 히스토리 렌더링"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # 소스 문서 표시
            if message["role"] == "assistant" and "sources" in message:
                render_sources(message["sources"])


def render_sources(sources: List[Dict]):
    """참조 문서 렌더링"""
    with st.expander("📌 참조 문서"):
        for idx, source in enumerate(sources, 1):
            st.write(f"**[문서 {idx}]** (유사도: {source['score']:.3f})")
            st.text(source['content'])
            if idx < len(sources):
                st.divider()


def handle_chat_input(api_client, top_k: int = 3, model: Optional[str] = None):
    """채팅 입력 처리"""
    if prompt := st.chat_input("질문을 입력하세요..."):
        # 사용자 메시지 추가
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # AI 응답 생성
        with st.chat_message("assistant"):
            with st.spinner("답변 생성 중..."):
                try:
                    # RAG 답변 요청
                    result = api_client.generate_answer(prompt, top_k=top_k, model=model)
                    
                    if 'error' not in result:
                        # 답변 표시
                        st.markdown(result['answer'])
                        
                        # 메시지 저장
                        message_data = {
                            "role": "assistant",
                            "content": result['answer'],
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        # 소스가 있으면 추가
                        if 'sources' in result and result['sources']:
                            message_data['sources'] = result['sources']
                            render_sources(result['sources'])
                        
                        st.session_state.messages.append(message_data)
                        
                    else:
                        handle_error(result.get('error', '알 수 없는 오류'))
                        
                except Exception as e:
                    handle_error(str(e))


def handle_error(error_msg: str):
    """에러 처리"""
    error_text = f"죄송합니다. 오류가 발생했습니다: {error_msg}"
    st.error(error_text)
    st.session_state.messages.append({
        "role": "assistant",
        "content": error_text,
        "timestamp": datetime.now().isoformat()
    })


def clear_chat_history():
    """채팅 히스토리 초기화"""
    st.session_state.messages = []
    st.success("대화 내역이 초기화되었습니다.")
    rerun()


def export_chat_history():
    """채팅 히스토리 내보내기"""
    if st.session_state.messages:
        import json
        chat_data = {
            "exported_at": datetime.now().isoformat(),
            "messages": st.session_state.messages
        }
        
        st.download_button(
            label="💾 대화 내역 다운로드",
            data=json.dumps(chat_data, ensure_ascii=False, indent=2),
            file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
