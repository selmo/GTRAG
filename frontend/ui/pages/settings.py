"""
설정 페이지 - 개선된 버전
"""
import streamlit as st
import sys
from pathlib import Path
import json
from datetime import datetime
from frontend.ui.utils.streamlit_helpers import rerun

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent.parent))

from frontend.ui.utils.api_client import APIClient

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

# ===============================
# AI 설정 탭 - 개선된 버전
# ===============================
with tab1:
    st.header("🤖 AI 설정")

    # 연결 상태 확인 섹션
    st.subheader("🔗 연결 상태")

    # 연결 테스트 버튼
    col_test, col_info = st.columns([1, 3])

    with col_test:
        if st.button("🔍 연결 테스트", key="connection_test_btn"):
            with st.spinner("연결 상태 확인 중..."):
                # API 서버 연결 테스트
                try:
                    health_data = api_client.health_check()
                    st.session_state.connection_status = health_data
                    st.session_state.last_connection_check = datetime.now()
                except Exception as e:
                    st.session_state.connection_status = {"status": "error", "message": str(e)}
                    st.session_state.last_connection_check = datetime.now()

    with col_info:
        if 'connection_status' in st.session_state:
            status = st.session_state.connection_status
            check_time = st.session_state.get('last_connection_check')

            if status.get('status') == 'healthy':
                st.success(f"✅ 시스템 정상 연결됨 ({check_time.strftime('%H:%M:%S')})")
            elif status.get('status') == 'degraded':
                st.warning(f"⚠️ 일부 서비스 문제 ({check_time.strftime('%H:%M:%S')})")
            else:
                st.error(f"❌ 연결 실패 ({check_time.strftime('%H:%M:%S')})")
        else:
            st.info("연결 테스트를 수행하여 시스템 상태를 확인하세요.")

    st.divider()

    # LLM 설정
    st.subheader("LLM (언어 모델) 설정")

    col1, col2 = st.columns(2)

    with col1:
        # 모델 목록 새로고침
        refresh_col, auto_col = st.columns([2, 1])

        with refresh_col:
            if st.button("🔄 모델 목록 새로고침", help="서버에서 최신 모델 목록을 가져옵니다", key="refresh_models_btn"):
                with st.spinner("모델 목록 로딩 중..."):
                    try:
                        available_models = api_client.get_available_models()

                        if available_models:
                            st.session_state.available_models = available_models
                            st.session_state.models_last_updated = datetime.now()
                            st.success(f"✅ {len(available_models)}개 모델을 찾았습니다")
                        else:
                            st.error("❌ 사용 가능한 모델이 없습니다. Ollama 서버를 확인하세요.")
                            st.session_state.available_models = []

                    except Exception as e:
                        st.error(f"❌ 모델 목록 로딩 실패: {str(e)}")
                        st.session_state.available_models = []

        with auto_col:
            auto_refresh = st.checkbox("자동", help="페이지 로드 시 자동으로 모델 목록을 가져옵니다", key="auto_refresh_models")

        # 세션 상태에서 모델 목록 가져오기 (자동 로딩 또는 기존 데이터)
        if 'available_models' not in st.session_state or auto_refresh:
            if auto_refresh or 'available_models' not in st.session_state:
                with st.spinner("모델 목록 초기 로딩 중..."):
                    try:
                        available_models = api_client.get_available_models()
                        st.session_state.available_models = available_models
                        st.session_state.models_last_updated = datetime.now()

                        if not available_models:
                            st.warning("⚠️ 사용 가능한 모델이 없습니다.")

                    except Exception as e:
                        st.error(f"모델 목록 로딩 실패: {str(e)}")
                        st.session_state.available_models = []

        available_models = st.session_state.get('available_models', [])

        # 마지막 업데이트 시간 표시
        if 'models_last_updated' in st.session_state:
            last_updated = st.session_state.models_last_updated
            st.caption(f"마지막 업데이트: {last_updated.strftime('%H:%M:%S')}")

        # 모델 선택
        if available_models and len(available_models) > 0:
            current_model = st.session_state.get('selected_model')

            # 현재 선택된 모델이 목록에 없거나 없으면 첫 번째로 설정
            if not current_model or current_model not in available_models:
                current_model = available_models[0]
                st.session_state.selected_model = current_model

            selected_model = st.selectbox(
                "사용할 모델",
                available_models,
                index=available_models.index(current_model),
                help="답변 생성에 사용할 LLM 모델",
                key="model_select"
            )

            # 선택된 모델 세션에 저장
            st.session_state.selected_model = selected_model

        else:
            st.error("❌ 사용 가능한 모델이 없습니다.")
            st.markdown("""
            **해결 방법:**
            1. Ollama 서버가 실행 중인지 확인
            2. 모델이 설치되어 있는지 확인 (`ollama list`)
            3. 네트워크 연결 상태 확인
            4. API 서버 로그 확인
            """)
            selected_model = None
            st.session_state.selected_model = None

        st.divider()

        # 타임아웃 설정 추가
        st.write("**연결 및 타임아웃 설정**")

        # API 타임아웃
        api_timeout = st.slider(
            "API 타임아웃 (초)",
            min_value=30,
            max_value=600,
            value=st.session_state.get('api_timeout', 300),
            step=30,
            help="API 요청의 최대 대기 시간",
            key="api_timeout_slider"
        )

        # RAG 생성 타임아웃
        rag_timeout = st.slider(
            "RAG 생성 타임아웃 (초)",
            min_value=60,
            max_value=900,
            value=st.session_state.get('rag_timeout', 300),
            step=30,
            help="답변 생성의 최대 대기 시간",
            key="rag_timeout_slider"
        )

        # 타임아웃 설정 적용
        st.session_state.api_timeout = api_timeout
        st.session_state.rag_timeout = rag_timeout
        api_client.set_timeout(api_timeout)

        st.divider()

        # 모델 파라미터 설정 (모델이 있을 때만)
        if selected_model:
            st.write("**모델 파라미터**")

            # Temperature
            temperature = st.slider(
                "Temperature (창의성)",
                min_value=0.0,
                max_value=2.0,
                value=st.session_state.get('temperature', 0.3),
                step=0.1,
                help="낮을수록 일관된 답변, 높을수록 창의적인 답변",
                key="temperature_slider"
            )

            # Max tokens
            max_tokens = st.number_input(
                "최대 토큰 수",
                min_value=100,
                max_value=4000,
                value=st.session_state.get('max_tokens', 1000),
                step=100,
                help="생성할 답변의 최대 길이",
                key="max_tokens_input"
            )
        else:
            st.warning("⚠️ 모델을 선택해야 파라미터를 설정할 수 있습니다.")

    with col2:
        # 선택된 모델 정보 표시 (모델이 있을 때만)
        if selected_model:
            with st.expander("📋 모델 정보", expanded=True):
                with st.spinner("모델 정보 로딩 중..."):
                    try:
                        model_info = api_client.get_model_info(selected_model)
                        if 'error' not in model_info:
                            st.write(f"**모델**: {model_info.get('name', selected_model)}")

                            # 모델 크기
                            if 'size' in model_info:
                                size_bytes = model_info['size']
                                if size_bytes > 0:
                                    # 바이트를 읽기 좋은 형식으로 변환
                                    size_gb = size_bytes / (1024 ** 3)
                                    if size_gb >= 1:
                                        st.write(f"**크기**: {size_gb:.1f} GB")
                                    else:
                                        size_mb = size_bytes / (1024 ** 2)
                                        st.write(f"**크기**: {size_mb:.0f} MB")

                            # 수정일
                            if 'modified_at' in model_info:
                                modified_at = model_info['modified_at']
                                if modified_at:
                                    try:
                                        # ISO 날짜 파싱
                                        from datetime import datetime
                                        dt = datetime.fromisoformat(modified_at.replace('Z', '+00:00'))
                                        st.write(f"**수정일**: {dt.strftime('%Y-%m-%d %H:%M')}")
                                    except:
                                        st.write(f"**수정일**: {modified_at}")

                            # 상세 정보
                            if 'details' in model_info:
                                details = model_info['details']
                                if 'parameter_size' in details:
                                    st.write(f"**파라미터**: {details['parameter_size']}")
                                if 'quantization_level' in details:
                                    st.write(f"**양자화**: {details['quantization_level']}")

                            # 모델 패밀리 정보
                            if ':' in selected_model:
                                family, tag = selected_model.split(':', 1)
                                st.write(f"**패밀리**: {family}")
                                st.write(f"**태그**: {tag}")

                        else:
                            st.caption("모델 정보를 가져올 수 없습니다")
                            st.caption(f"오류: {model_info.get('error', '알 수 없는 오류')}")
                    except Exception as e:
                        st.caption(f"모델 정보 로딩 실패: {str(e)}")

        # 추가 파라미터 (모델이 있을 때만)
        if selected_model:
            st.write("**고급 파라미터**")

            # Top P
            top_p = st.slider(
                "Top P",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.get('top_p', 0.9),
                step=0.05,
                help="확률 분포 상위 P%만 고려",
                key="top_p_slider"
            )

            # Frequency penalty
            frequency_penalty = st.slider(
                "Frequency Penalty",
                min_value=0.0,
                max_value=2.0,
                value=st.session_state.get('frequency_penalty', 0.0),
                step=0.1,
                help="반복 단어 사용 억제",
                key="frequency_penalty_slider"
            )

            # System prompt
            system_prompt = st.text_area(
                "시스템 프롬프트",
                value=st.session_state.get('system_prompt',
                                           "당신은 문서 기반 질의응답 시스템입니다. 제공된 문서의 내용만을 바탕으로 정확하고 도움이 되는 답변을 제공하세요."),
                height=150,
                help="AI의 기본 행동 지침",
                key="system_prompt_area"
            )
        else:
            st.info("모델을 먼저 선택하세요.")

    st.divider()

    # RAG 설정 (모델이 있을 때만)
    if selected_model:
        st.subheader("RAG (검색 증강 생성) 설정")

        col1, col2 = st.columns(2)

        with col1:
            # 검색 문서 수
            rag_top_k = st.slider(
                "검색할 문서 수",
                min_value=1,
                max_value=20,
                value=st.session_state.get('rag_top_k', 3),
                help="답변 생성 시 참조할 문서의 개수",
                key="rag_top_k_slider"
            )

            # 최소 유사도
            min_similarity = st.slider(
                "최소 유사도 임계값",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.get('min_similarity', 0.5),
                step=0.05,
                help="이 값 이상의 유사도를 가진 문서만 사용",
                key="min_similarity_slider"
            )

            # 컨텍스트 길이
            context_window = st.number_input(
                "컨텍스트 윈도우 크기",
                min_value=500,
                max_value=8000,
                value=st.session_state.get('context_window', 3000),
                step=500,
                help="LLM에 제공할 최대 컨텍스트 길이",
                key="context_window_input"
            )

        with col2:
            # 청크 설정
            chunk_size = st.number_input(
                "청크 크기",
                min_value=100,
                max_value=2000,
                value=st.session_state.get('chunk_size', 500),
                step=100,
                help="문서를 분할하는 기본 크기",
                key="chunk_size_input"
            )

            chunk_overlap = st.number_input(
                "청크 중첩",
                min_value=0,
                max_value=500,
                value=st.session_state.get('chunk_overlap', 50),
                step=50,
                help="청크 간 중첩되는 텍스트 길이",
                key="chunk_overlap_input"
            )

            # 임베딩 모델
            embedding_model = st.selectbox(
                "임베딩 모델",
                ["intfloat/multilingual-e5-large-instruct", "intfloat/e5-large-v2"],
                index=0 if st.session_state.get('embedding_model',
                                                "intfloat/multilingual-e5-large-instruct") == "intfloat/multilingual-e5-large-instruct" else 1,
                help="문서 벡터화에 사용할 모델",
                key="embedding_model_select"
            )
    else:
        st.warning("⚠️ 모델을 선택해야 RAG 설정을 할 수 있습니다.")

    # 설정 저장 버튼
    col_save, col_reset, col_test = st.columns([2, 1, 1])

    with col_save:
        # 모델이 선택되었을 때만 저장 가능
        if selected_model:
            if st.button("💾 AI 설정 저장", type="primary", key="save_ai_settings"):
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
                    },
                    "api": {
                        "timeout": api_timeout,
                        "rag_timeout": rag_timeout
                    }
                }

                # 세션 상태에 각각 저장 (UI 상태 유지용)
                for key, value in settings["llm"].items():
                    st.session_state[key] = value
                for key, value in settings["rag"].items():
                    st.session_state[key] = value
                for key, value in settings["api"].items():
                    st.session_state[f"api_{key}"] = value

                # 통합 설정 저장
                st.session_state.ai_settings = settings

                # 서버에도 설정 전송 (선택적)
                try:
                    result = api_client.update_settings(settings)
                    if result.get('updated', True):
                        st.success("✅ AI 설정이 저장되었습니다.")
                        st.info(f"선택된 모델: {selected_model}")
                    else:
                        st.warning("⚠️ 로컬 설정은 저장되었으나 서버 업데이트에 실패했습니다.")
                except Exception as e:
                    st.warning(f"⚠️ 로컬 설정은 저장되었으나 서버 업데이트 실패: {str(e)}")
        else:
            st.button("💾 AI 설정 저장", disabled=True, help="모델을 먼저 선택하세요", key="save_ai_settings_disabled")

    with col_reset:
        if st.button("🔄 기본값 복원", key="reset_ai_settings"):
            # 확인 다이얼로그
            if st.session_state.get('confirm_reset_ai') != True:
                st.session_state.confirm_reset_ai = True
                st.warning("⚠️ 다시 클릭하면 모든 설정이 기본값으로 복원됩니다.")
            else:
                # 기본값으로 복원
                defaults = {
                    "temperature": 0.3,
                    "max_tokens": 1000,
                    "top_p": 0.9,
                    "frequency_penalty": 0.0,
                    "system_prompt": "당신은 문서 기반 질의응답 시스템입니다. 제공된 문서의 내용만을 바탕으로 정확하고 도움이 되는 답변을 제공하세요.",
                    "rag_top_k": 3,
                    "min_similarity": 0.5,
                    "context_window": 3000,
                    "chunk_size": 500,
                    "chunk_overlap": 50,
                    "embedding_model": "intfloat/multilingual-e5-large-instruct",
                    "api_timeout": 300,
                    "rag_timeout": 300
                }

                for key, value in defaults.items():
                    st.session_state[key] = value

                del st.session_state.confirm_reset_ai
                st.success("✅ 설정이 기본값으로 복원되었습니다.")
                st.rerun()

    with col_test:
        if selected_model:
            if st.button("🧪 모델 테스트", key="test_model"):
                with st.spinner("모델 테스트 중..."):
                    try:
                        # 간단한 테스트 질문으로 모델 동작 확인
                        test_result = api_client.generate_answer(
                            query="안녕하세요",
                            top_k=1,
                            model=selected_model,
                            timeout=60  # 테스트용 짧은 타임아웃
                        )

                        if 'error' not in test_result:
                            st.success("✅ 모델 테스트 성공")
                            st.info(f"사용된 모델: {selected_model}")
                        else:
                            st.error(f"❌ 모델 테스트 실패: {test_result.get('error')}")
                    except Exception as e:
                        st.error(f"❌ 모델 테스트 실패: {str(e)}")
        else:
            st.button("🧪 모델 테스트", disabled=True, help="모델을 먼저 선택하세요", key="test_model_disabled")

# ===============================
# 시스템 상태 탭 (기존 코드 유지)
# ===============================
with tab2:
    st.header("📊 시스템 상태")

    # 시스템 상태 확인
    if st.button("🔄 상태 새로고침", type="primary"):
        with st.spinner("시스템 상태 확인 중..."):
            try:
                health_data = api_client.health_check()
                st.session_state.last_health_check = health_data
                st.session_state.health_check_time = datetime.now()
                st.success("✅ 상태 확인 완료")
            except Exception as e:
                st.error(f"상태 확인 실패: {str(e)}")
                # 오류 시에도 기본 상태 설정
                st.session_state.last_health_check = {
                    "status": "error",
                    "services": {
                        "qdrant": {"status": "unknown"},
                        "ollama": {"status": "unknown"},
                        "celery": {"status": "unknown"}
                    }
                }
                st.session_state.health_check_time = datetime.now()

    # 상태 표시 - 안전한 접근 방식
    if 'last_health_check' in st.session_state and 'health_check_time' in st.session_state:
        health_data = st.session_state.last_health_check
        check_time = st.session_state.health_check_time

        st.caption(f"마지막 확인: {check_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 전체 상태
        overall_status = health_data.get('status', 'unknown')
        if overall_status == 'healthy':
            st.success("✅ 시스템 정상 작동 중")
        elif overall_status == 'error':
            st.error("❌ 시스템 문제 감지")
        else:
            st.warning("⚠️ 시스템 상태 불명")

        # 서비스별 상태
        services = health_data.get('services', {})

        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("🗄️ Qdrant")
            qdrant = services.get('qdrant', {})
            qdrant_status = qdrant.get('status', 'unknown')

            if qdrant_status == 'connected':
                st.success("연결됨")
                collections = qdrant.get('collections', [])
                st.write(f"컬렉션: {len(collections)}개")
                for coll in collections[:5]:  # 최대 5개만 표시
                    st.caption(f"• {coll}")
                if len(collections) > 5:
                    st.caption(f"... 외 {len(collections) - 5}개")

                # 한국어 컨텐츠 비율 표시
                korean_ratio = qdrant.get('korean_content_ratio', 0)
                if korean_ratio > 0:
                    st.caption(f"한국어 컨텐츠: {korean_ratio:.1%}")
            else:
                st.error("연결 실패")
                if 'error' in qdrant:
                    st.caption(f"오류: {qdrant['error']}")

        with col2:
            st.subheader("🤖 Ollama")
            ollama = services.get('ollama', {})
            ollama_status = ollama.get('status', 'unknown')

            if ollama_status == 'connected':
                st.success("연결됨")
                st.write(f"호스트: {ollama.get('host', 'N/A')}")

                models = ollama.get('models', [])
                total_models = ollama.get('total_models', len(models))
                st.write(f"모델: {total_models}개")

                # 처음 3개 모델만 표시
                for model in models[:3]:
                    st.caption(f"• {model}")
                if len(models) > 3:
                    st.caption(f"... 외 {len(models) - 3}개")
            else:
                st.error("연결 실패")
                if 'error' in ollama:
                    st.caption(f"오류: {ollama['error']}")

        with col3:
            st.subheader("📨 Celery")
            celery = services.get('celery', {})
            celery_status = celery.get('status', 'unknown')

            if celery_status == 'connected':
                st.success("연결됨")
                st.write("워커 활성")
            else:
                st.error("연결 실패")

        # 임베딩 모델 상태 (있으면 표시)
        if 'embedding' in services:
            st.divider()
            st.subheader("🔤 임베딩 모델")
            embedding = services['embedding']
            embedding_status = embedding.get('status', 'unknown')

            if embedding_status == 'ready':
                st.success("준비됨")
                embedding_info = embedding.get('info', {})
                if 'model_name' in embedding_info:
                    st.write(f"모델: {embedding_info['model_name']}")
                if 'dimension' in embedding_info:
                    st.write(f"차원: {embedding_info['dimension']}")
            else:
                st.error("오류")
                if 'info' in embedding and 'error' in embedding['info']:
                    st.caption(f"오류: {embedding['info']['error']}")

    else:
        # 상태 정보가 없는 경우
        st.info("🔄 상태 새로고침 버튼을 클릭하여 시스템 상태를 확인하세요.")

        # 자동으로 한번 로드해보기
        if st.button("자동 상태 확인", key="auto_health_check"):
            with st.spinner("시스템 상태 자동 확인 중..."):
                try:
                    health_data = api_client.health_check()
                    st.session_state.last_health_check = health_data
                    st.session_state.health_check_time = datetime.now()
                    st.rerun()
                except Exception as e:
                    st.error(f"자동 상태 확인 실패: {str(e)}")

# 기존 탭3, 탭4, 탭5는 그대로 유지...

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
                rerun()

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