"""
설정 페이지
"""
import streamlit as st
import sys
from pathlib import Path
import json
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent.parent))

from ui.utils.api_client import APIClient

# 페이지 설정
st.set_page_config(
    page_title="설정 - GTOne RAG",
    page_icon="⚙️",
    layout="wide"
)

# API 클라이언트 초기화
api_client = APIClient()

# 헤더
st.title("⚙️ 시스템 설정")
st.markdown("GTOne RAG 시스템의 설정을 관리합니다.")

# 설정 탭
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🤖 AI 설정",
    "📊 시스템 상태",
    "🔧 고급 설정",
    "💾 백업/복원",
    "ℹ️ 정보"
])

with tab1:
    st.header("🤖 AI 설정")
    
    # LLM 설정
    st.subheader("LLM (언어 모델) 설정")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 모델 선택
        available_models = [
            "llama3:8b-instruct",
            "llama3:70b-instruct",
            "mistral:7b-instruct",
            "mixtral:8x7b-instruct",
            "phi:2.7b",
            "gemma:7b"
        ]
        
        selected_model = st.selectbox(
            "사용할 모델",
            available_models,
            index=0,
            help="답변 생성에 사용할 LLM 모델"
        )
        
        # Temperature
        temperature = st.slider(
            "Temperature (창의성)",
            min_value=0.0,
            max_value=2.0,
            value=0.3,
            step=0.1,
            help="낮을수록 일관된 답변, 높을수록 창의적인 답변"
        )
        
        # Max tokens
        max_tokens = st.number_input(
            "최대 토큰 수",
            min_value=100,
            max_value=4000,
            value=1000,
            step=100,
            help="생성할 답변의 최대 길이"
        )
    
    with col2:
        # Top P
        top_p = st.slider(
            "Top P",
            min_value=0.0,
            max_value=1.0,
            value=0.9,
            step=0.05,
            help="확률 분포 상위 P%만 고려"
        )
        
        # Frequency penalty
        frequency_penalty = st.slider(
            "Frequency Penalty",
            min_value=0.0,
            max_value=2.0,
            value=0.0,
            step=0.1,
            help="반복 단어 사용 억제"
        )
        
        # System prompt
        system_prompt = st.text_area(
            "시스템 프롬프트",
            value="당신은 문서 기반 질의응답 시스템입니다. 제공된 문서의 내용만을 바탕으로 정확하고 도움이 되는 답변을 제공하세요.",
            height=100,
            help="AI의 기본 행동 지침"
        )
    
    st.divider()
    
    # RAG 설정
    st.subheader("RAG (검색 증강 생성) 설정")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # 검색 문서 수
        rag_top_k = st.slider(
            "검색할 문서 수",
            min_value=1,
            max_value=20,
            value=3,
            help="답변 생성 시 참조할 문서의 개수"
        )
        
        # 최소 유사도
        min_similarity = st.slider(
            "최소 유사도 임계값",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.05,
            help="이 값 이상의 유사도를 가진 문서만 사용"
        )
        
        # 컨텍스트 길이
        context_window = st.number_input(
            "컨텍스트 윈도우 크기",
            min_value=500,
            max_value=8000,
            value=3000,
            step=500,
            help="LLM에 제공할 최대 컨텍스트 길이"
        )
    
    with col2:
        # 청크 설정
        chunk_size = st.number_input(
            "청크 크기",
            min_value=100,
            max_value=2000,
            value=500,
            step=100,
            help="문서를 분할하는 기본 크기"
        )
        
        chunk_overlap = st.number_input(
            "청크 중첩",
            min_value=0,
            max_value=500,
            value=50,
            step=50,
            help="청크 간 중첩되는 텍스트 길이"
        )
        
        # 임베딩 모델
        embedding_model = st.selectbox(
            "임베딩 모델",
            ["intfloat/multilingual-e5-large-instruct", "intfloat/e5-large-v2"],
            help="문서 벡터화에 사용할 모델"
        )
    
    # 설정 저장 버튼
    if st.button("💾 AI 설정 저장", type="primary"):
        settings = {
            "llm": {
                "model": selected_model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "frequency_penalty": frequency_penalty,
                "system_prompt": system_prompt
            },
            "rag": {
                "top_k": rag_top_k,
                "min_similarity": min_similarity,
                "context_window": context_window,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "embedding_model": embedding_model
            }
        }
        
        # 세션 상태에 저장
        st.session_state.ai_settings = settings
        st.success("✅ AI 설정이 저장되었습니다.")

with tab2:
    st.header("📊 시스템 상태")
    
    # 시스템 상태 확인
    if st.button("🔄 상태 새로고침", type="primary"):
        with st.spinner("시스템 상태 확인 중..."):
            try:
                health_data = api_client.health_check()
                st.session_state.last_health_check = health_data
                st.session_state.health_check_time = datetime.now()
            except Exception as e:
                st.error(f"상태 확인 실패: {str(e)}")
    
    # 상태 표시
    if 'last_health_check' in st.session_state:
        health_data = st.session_state.last_health_check
        check_time = st.session_state.health_check_time
        
        st.caption(f"마지막 확인: {check_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 전체 상태
        overall_status = health_data.get('status', 'unknown')
        if overall_status == 'healthy':
            st.success("✅ 시스템 정상 작동 중")
        else:
            st.error("❌ 시스템 문제 감지")
        
        # 서비스별 상태
        services = health_data.get('services', {})
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("🗄️ Qdrant")
            qdrant = services.get('qdrant', {})
            if qdrant.get('status') == 'connected':
                st.success("연결됨")
                collections = qdrant.get('collections', [])
                st.write(f"컬렉션: {len(collections)}개")
                for coll in collections:
                    st.caption(f"• {coll}")
            else:
                st.error("연결 실패")
        
        with col2:
            st.subheader("🤖 Ollama")
            ollama = services.get('ollama', {})
            if ollama.get('status') == 'connected':
                st.success("연결됨")
                st.write(f"호스트: {ollama.get('host', 'N/A')}")
                models = ollama.get('models', [])
                st.write(f"모델: {len(models)}개")
                for model in models[:3]:
                    st.caption(f"• {model}")
            else:
                st.error("연결 실패")
        
        with col3:
            st.subheader("📨 Celery")
            celery = services.get('celery', {})
            if celery.get('status') == 'connected':
                st.success("연결됨")
                st.write("워커 활성")
            else:
                st.error("연결 실패")
    
    # 리소스 사용량
    st.divider()
    st.subheader("💻 리소스 사용량")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 메모리 사용량 (더미 데이터)
        memory_usage = 45.2
        st.metric("메모리 사용률", f"{memory_usage}%", "2.1%")
        st.progress(memory_usage / 100)
    
    with col2:
        # CPU 사용량 (더미 데이터)
        cpu_usage = 23.5
        st.metric("CPU 사용률", f"{cpu_usage}%", "-5.2%")
        st.progress(cpu_usage / 100)
    
    with col3:
        # 디스크 사용량 (더미 데이터)
        disk_usage = 67.8
        st.metric("디스크 사용률", f"{disk_usage}%", "0.5%")
        st.progress(disk_usage / 100)

with tab3:
    st.header("🔧 고급 설정")
    
    # 벡터 DB 설정
    st.subheader("벡터 데이터베이스 설정")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Qdrant 설정
        qdrant_host = st.text_input(
            "Qdrant 호스트",
            value="qdrant",
            help="Qdrant 서버 주소"
        )
        
        qdrant_port = st.number_input(
            "Qdrant 포트",
            value=6333,
            help="Qdrant 서버 포트"
        )
        
        collection_name = st.text_input(
            "컬렉션 이름",
            value="chunks",
            help="문서를 저장할 컬렉션"
        )
    
    with col2:
        # 인덱싱 설정
        vector_size = st.number_input(
            "벡터 차원",
            value=1024,
            help="임베딩 벡터의 차원 수"
        )
        
        distance_metric = st.selectbox(
            "거리 측정 방법",
            ["Cosine", "Euclidean", "Dot Product"],
            help="벡터 간 유사도 계산 방법"
        )
        
        index_threshold = st.number_input(
            "인덱스 임계값",
            value=10000,
            help="인덱스 최적화 임계값"
        )
    
    st.divider()
    
    # OCR 설정
    st.subheader("OCR 설정")
    
    ocr_engine = st.selectbox(
        "OCR 엔진",
        ["Tesseract", "Azure Vision API"],
        help="이미지 텍스트 추출에 사용할 엔진"
    )
    
    if ocr_engine == "Azure Vision API":
        azure_key = st.text_input(
            "Azure API Key",
            type="password",
            help="Azure Cognitive Services API 키"
        )
        
        azure_endpoint = st.text_input(
            "Azure Endpoint",
            placeholder="https://your-resource.cognitiveservices.azure.com/",
            help="Azure 서비스 엔드포인트"
        )
    
    ocr_languages = st.multiselect(
        "OCR 언어",
        ["kor", "eng", "jpn", "chi_sim", "chi_tra"],
        default=["kor", "eng"],
        help="OCR에서 인식할 언어"
    )
    
    # 고급 설정 저장
    if st.button("💾 고급 설정 저장", type="primary"):
        advanced_settings = {
            "vector_db": {
                "host": qdrant_host,
                "port": qdrant_port,
                "collection": collection_name,
                "vector_size": vector_size,
                "distance_metric": distance_metric,
                "index_threshold": index_threshold
            },
            "ocr": {
                "engine": ocr_engine,
                "languages": ocr_languages
            }
        }
        
        if ocr_engine == "Azure Vision API":
            advanced_settings["ocr"]["azure_key"] = azure_key
            advanced_settings["ocr"]["azure_endpoint"] = azure_endpoint
        
        st.session_state.advanced_settings = advanced_settings
        st.success("✅ 고급 설정이 저장되었습니다.")

with tab4:
    st.header("💾 백업 및 복원")
    
    # 백업
    st.subheader("📤 백업")
    
    backup_options = st.multiselect(
        "백업할 항목 선택",
        ["설정", "대화 기록", "검색 기록", "업로드 파일 목록"],
        default=["설정", "대화 기록"]
    )
    
    if st.button("💾 백업 생성", type="primary"):
        backup_data = {
            "created_at": datetime.now().isoformat(),
            "version": "1.0.0"
        }
        
        if "설정" in backup_options:
            backup_data["settings"] = {
                "ai": st.session_state.get("ai_settings", {}),
                "advanced": st.session_state.get("advanced_settings", {})
            }
        
        if "대화 기록" in backup_options:
            backup_data["messages"] = st.session_state.get("messages", [])
        
        if "검색 기록" in backup_options:
            backup_data["search_history"] = st.session_state.get("search_history", [])
        
        if "업로드 파일 목록" in backup_options:
            backup_data["uploaded_files"] = st.session_state.get("uploaded_files", [])
        
        # 다운로드 버튼
        st.download_button(
            label="📥 백업 다운로드",
            data=json.dumps(backup_data, ensure_ascii=False, indent=2),
            file_name=f"gtone_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    st.divider()
    
    # 복원
    st.subheader("📥 복원")
    
    uploaded_backup = st.file_uploader(
        "백업 파일 선택",
        type=["json"],
        help="이전에 생성한 백업 파일을 업로드하세요"
    )
    
    if uploaded_backup is not None:
        try:
            backup_data = json.loads(uploaded_backup.read())
            
            st.info(f"백업 생성 시간: {backup_data.get('created_at', 'N/A')}")
            
            # 복원 가능한 항목 표시
            available_items = []
            if "settings" in backup_data:
                available_items.append("설정")
            if "messages" in backup_data:
                available_items.append(f"대화 기록 ({len(backup_data['messages'])}개)")
            if "search_history" in backup_data:
                available_items.append(f"검색 기록 ({len(backup_data['search_history'])}개)")
            if "uploaded_files" in backup_data:
                available_items.append(f"업로드 파일 목록 ({len(backup_data['uploaded_files'])}개)")
            
            restore_items = st.multiselect(
                "복원할 항목 선택",
                available_items,
                default=available_items
            )
            
            if st.button("♻️ 복원 실행", type="secondary"):
                # 복원 실행
                if "설정" in restore_items and "settings" in backup_data:
                    st.session_state.ai_settings = backup_data["settings"].get("ai", {})
                    st.session_state.advanced_settings = backup_data["settings"].get("advanced", {})
                
                if any("대화 기록" in item for item in restore_items) and "messages" in backup_data:
                    st.session_state.messages = backup_data["messages"]
                
                if any("검색 기록" in item for item in restore_items) and "search_history" in backup_data:
                    st.session_state.search_history = backup_data["search_history"]
                
                if any("업로드 파일 목록" in item for item in restore_items) and "uploaded_files" in backup_data:
                    st.session_state.uploaded_files = backup_data["uploaded_files"]
                
                st.success("✅ 복원이 완료되었습니다.")
                st.experimental_rerun()
                
        except Exception as e:
            st.error(f"백업 파일 읽기 실패: {str(e)}")

with tab5:
    st.header("ℹ️ 시스템 정보")
    
    # 시스템 정보
    st.subheader("시스템 정보")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**버전**")
        st.code("GTOne RAG System v1.0.0")
        
        st.write("**Python 버전**")
        st.code("Python 3.11+")
        
        st.write("**프레임워크**")
        st.code("FastAPI + Streamlit")
    
    with col2:
        st.write("**벡터 DB**")
        st.code("Qdrant v1.9.3")
        
        st.write("**임베딩 모델**")
        st.code("E5-large-instruct")
        
        st.write("**LLM 서버**")
        st.code("Ollama (External)")
    
    st.divider()
    
    # 라이선스
    st.subheader("라이선스")
    st.text("""
    MIT License
    
    Copyright (c) 2024 GTOne
    
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction...
    """)
    
    st.divider()
    
    # 도움말
    st.subheader("도움말 및 지원")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("📚 [사용자 가이드](https://github.com/selmo/gtrag/wiki)")
    
    with col2:
        st.markdown("🐛 [버그 리포트](https://github.com/selmo/gtrag/issues)")
    
    with col3:
        st.markdown("💬 [커뮤니티](https://discord.gg/selmo)")
    
    # 연락처
    st.divider()
    st.caption("문의: support@gtone.com | 기술 지원: tech@gtone.com")

# 푸터
st.divider()
st.caption("💡 설정 변경 후에는 시스템을 재시작하거나 새로고침이 필요할 수 있습니다.")
