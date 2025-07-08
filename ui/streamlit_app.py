import streamlit as st
import json
import time
from datetime import datetime
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

# 페이지 설정
st.set_page_config(
    page_title="GTOne RAG System",
    page_icon="📚",
    layout="wide"
)

# API 클라이언트 import
try:
    from ui.utils.api_client import APIClient

    api_client = APIClient()
except ImportError:
    # fallback: api_client.py가 없는 경우 직접 requests 사용
    import requests
    import os


    class SimpleAPIClient:
        def __init__(self):
            self.base_url = os.getenv("API_BASE_URL", "http://localhost:8000")

        def upload_document(self, file):
            files = {"file": (file.name, file, file.type)}
            response = requests.post(f"{self.base_url}/v1/documents", files=files)
            return response.json()

        def search(self, query, top_k=3):
            response = requests.get(f"{self.base_url}/v1/search", params={"q": query, "top_k": top_k})
            return response.json()

        def generate_answer(self, query, top_k=3, model=None):
            params = {"q": query, "top_k": top_k}
            if model:
                params["model"] = model
            response = requests.post(f"{self.base_url}/v1/rag/answer", params=params)
            return response.json()

        def health_check(self):
            response = requests.get(f"{self.base_url}/v1/health")
            return response.json()


    api_client = SimpleAPIClient()

# 세션 상태 초기화
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []

# 사이드바
with st.sidebar:
    st.title("📚 GTOne RAG System")

    # 시스템 상태 확인
    if st.button("🔄 시스템 상태 확인"):
        try:
            health_data = api_client.health_check()

            if health_data.get('status') == 'healthy':
                st.success("✅ 시스템 정상 작동 중")

                # Qdrant 상태
                qdrant_status = health_data['services']['qdrant']
                st.write(f"**Qdrant**: {qdrant_status['status']}")
                if qdrant_status['collections']:
                    st.write(f"컬렉션: {', '.join(qdrant_status['collections'])}")

                # Ollama 상태
                ollama_status = health_data['services']['ollama']
                st.write(f"**Ollama**: {ollama_status['status']}")
                if ollama_status['status'] == 'connected':
                    st.write(f"호스트: {ollama_status['host']}")
                    if ollama_status.get('models'):
                        st.write(f"모델: {', '.join(ollama_status['models'])}")
            else:
                st.error("❌ 시스템 연결 실패")

        except Exception as e:
            st.error(f"❌ 시스템 연결 실패: {str(e)}")

    st.divider()

    # 파일 업로드 섹션
    st.header("📄 문서 업로드")

    uploaded_file = st.file_uploader(
        "파일 선택",
        type=['pdf', 'txt', 'png', 'jpg', 'jpeg', 'docx'],
        help="PDF, 텍스트, 이미지 파일을 업로드할 수 있습니다."
    )

    if uploaded_file is not None:
        if st.button("📤 업로드", type="primary"):
            with st.spinner("문서 처리 중..."):
                try:
                    result = api_client.upload_document(uploaded_file)

                    if 'error' not in result:
                        st.success(f"✅ 성공! {result['uploaded']}개 청크로 분할되었습니다.")
                        st.session_state.uploaded_files.append({
                            'name': uploaded_file.name,
                            'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                            'chunks': result['uploaded']
                        })
                    else:
                        st.error(f"업로드 실패: {result['error']}")

                except Exception as e:
                    st.error(f"오류 발생: {str(e)}")

    # 업로드된 파일 목록
    if st.session_state.uploaded_files:
        st.divider()
        st.header("📁 업로드된 문서")
        for file in st.session_state.uploaded_files[-5:]:  # 최근 5개만 표시
            st.write(f"• {file['name']}")
            st.caption(f"  {file['time']} | {file['chunks']} chunks")

# 메인 영역
st.title("🤖 GTOne RAG Assistant")
st.markdown("문서를 업로드하고 질문해보세요!")

# 탭 생성
tab1, tab2, tab3 = st.tabs(["💬 채팅", "🔍 문서 검색", "⚙️ 설정"])

with tab1:
    # 채팅 히스토리 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # 소스 문서 표시
            if message["role"] == "assistant" and "sources" in message:
                with st.expander("📌 참조 문서"):
                    for idx, source in enumerate(message["sources"], 1):
                        st.write(f"**[문서 {idx}]** (유사도: {source['score']:.3f})")
                        st.text(source['content'])
                        st.divider()

    # 채팅 입력
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
                    result = api_client.generate_answer(prompt, top_k=3)

                    if 'error' not in result:
                        # 답변 표시
                        st.markdown(result['answer'])

                        # 메시지 저장
                        message_data = {
                            "role": "assistant",
                            "content": result['answer']
                        }

                        # 소스가 있으면 추가
                        if 'sources' in result and result['sources']:
                            message_data['sources'] = result['sources']

                            with st.expander("📌 참조 문서"):
                                for idx, source in enumerate(result['sources'], 1):
                                    st.write(f"**[문서 {idx}]** (유사도: {source['score']:.3f})")
                                    st.text(source['content'])
                                    st.divider()

                        st.session_state.messages.append(message_data)

                    else:
                        error_msg = f"답변 생성 실패: {result.get('error', '알 수 없는 오류')}"
                        st.error(error_msg)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": error_msg
                        })

                except Exception as e:
                    error_msg = f"오류: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })

with tab2:
    st.header("🔍 문서 검색")

    col1, col2 = st.columns([3, 1])

    with col1:
        search_query = st.text_input("검색어를 입력하세요", placeholder="예: 계약 조건")

    with col2:
        top_k = st.number_input("검색 결과 수", min_value=1, max_value=10, value=5)

    if st.button("🔍 검색", type="primary"):
        if search_query:
            with st.spinner("검색 중..."):
                try:
                    results = api_client.search(search_query, top_k)

                    if results:
                        st.success(f"{len(results)}개의 관련 문서를 찾았습니다.")

                        for idx, hit in enumerate(results, 1):
                            with st.container():
                                col1, col2 = st.columns([4, 1])

                                with col1:
                                    st.markdown(f"**검색 결과 {idx}**")

                                with col2:
                                    st.metric("유사도", f"{hit['score']:.3f}")

                                st.text_area(
                                    "내용",
                                    value=hit['content'],
                                    height=150,
                                    disabled=True,
                                    key=f"search_result_{idx}"
                                )

                                st.divider()
                    else:
                        st.warning("검색 결과가 없습니다.")

                except Exception as e:
                    st.error(f"검색 오류: {str(e)}")
        else:
            st.warning("검색어를 입력해주세요.")

with tab3:
    st.header("⚙️ 설정")

    # RAG 설정
    st.subheader("RAG 설정")

    col1, col2 = st.columns(2)

    with col1:
        rag_top_k = st.slider(
            "검색할 문서 수",
            min_value=1,
            max_value=10,
            value=3,
            help="답변 생성 시 참조할 문서의 개수"
        )

    with col2:
        temperature = st.slider(
            "답변 창의성 (Temperature)",
            min_value=0.0,
            max_value=1.0,
            value=0.3,
            step=0.1,
            help="낮을수록 일관된 답변, 높을수록 창의적인 답변"
        )

    # 모델 선택
    st.subheader("LLM 모델")

    available_models = ["llama3:8b-instruct", "llama3:70b-instruct", "mistral:7b-instruct"]
    selected_model = st.selectbox(
        "사용할 모델 선택",
        available_models,
        help="답변 생성에 사용할 LLM 모델"
    )

    if st.button("💾 설정 저장"):
        st.success("설정이 저장되었습니다!")

    # 대화 초기화
    st.divider()

    if st.button("🗑️ 대화 내역 초기화", type="secondary"):
        st.session_state.messages = []
        st.success("대화 내역이 초기화되었습니다.")
        st.experimental_rerun()

# 푸터
st.divider()
st.caption("GTOne RAG System - Powered by Qdrant + Ollama")