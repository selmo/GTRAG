"""
설정 페이지 - 개선된 버전
- Import 경로 통일
- 공통 컴포넌트 적용
- 설정 중앙화
- 에러 처리 표준화
"""
import streamlit as st
import sys
from pathlib import Path
import json
from datetime import datetime

from frontend.ui.utils.session import SessionManager

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent.parent))

# 통일된 import 경로
from frontend.ui.utils.streamlit_helpers import rerun
from frontend.ui.core.config import config, Constants
from frontend.ui.components.common import (
    StatusIndicator, MetricCard, ErrorDisplay, ActionButton, LoadingSpinner
)
from frontend.ui.utils.error_handler import (
    ErrorContext, GTRagError, ErrorType, ErrorSeverity
)

# 조건부 import (표준 패턴)
try:
    from frontend.ui.utils.client_manager import ClientManager
    HAS_API_CLIENT = True
except ImportError:
    APIClient = None
    HAS_API_CLIENT = False

try:
    from frontend.ui.utils.system_health import SystemHealthManager, SystemStatus, ServiceStatus
    HAS_SYSTEM_HEALTH = True
except ImportError:
    SystemHealthManager = None
    SystemStatus = None
    ServiceStatus = None
    HAS_SYSTEM_HEALTH = False

try:
    from frontend.ui.utils.model_manager import ModelManager
    HAS_MODEL_MANAGER = True
except ImportError:
    ModelManager = None
    HAS_MODEL_MANAGER = False


# ===============================
# 설정 관리 함수들 (import 이후, 페이지 설정 전에 추가)
# ===============================

# 1. 수정된 설정 동기화 함수 (모델명 동기화 추가)
def sync_backend_settings_to_session():
    """백엔드 설정을 세션 상태에 동기화하는 함수"""
    try:
        # 백엔드에서 설정 가져오기
        current_settings = api_client.get_settings()

        if current_settings:
            # Ollama 호스트 설정
            if 'ollama_host' in current_settings:
                st.session_state.backend_ollama_host = current_settings['ollama_host']

            # ★ 모델명 동기화 추가 ★
            if 'ollama_model' in current_settings:
                st.session_state.backend_selected_model = current_settings['ollama_model']

            # LLM 파라미터 동기화
            if 'llm' in current_settings:
                llm_settings = current_settings['llm']
                llm_params = ['model', 'temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'system_prompt']
                for param in llm_params:
                    if param in llm_settings:
                        st.session_state[f'backend_{param}'] = llm_settings[param]

                # LLM 설정의 model도 selected_model로 동기화
                if 'model' in llm_settings:
                    st.session_state.backend_selected_model = llm_settings['model']

            # RAG 파라미터 동기화
            if 'rag' in current_settings:
                rag_settings = current_settings['rag']
                rag_param_mapping = {
                    'top_k': 'rag_top_k',
                    'min_score': 'min_similarity',
                    'context_window': 'context_window',
                    'chunk_size': 'chunk_size',
                    'chunk_overlap': 'chunk_overlap',
                    'embed_model': 'embedding_model'
                }
                for backend_key, session_key in rag_param_mapping.items():
                    if backend_key in rag_settings:
                        st.session_state[f'backend_{session_key}'] = rag_settings[backend_key]

            # ONTOLOGY 파라미터 동기화
            if 'ontology' in current_settings:
                ontology_settings = current_settings['ontology']
                if 'keyword_method' in ontology_settings:
                    st.session_state.backend_keyword_method = ontology_settings['keyword_method']

            return current_settings, None
        else:
            return None, "저장된 설정이 없어 기본값을 사용합니다"

    except Exception as e:
        return None, f"설정 불러오기 실패: {str(e)}"


# 2. 수정된 모델 선택 섹션 렌더링 함수
def render_model_selection_section(available_models):
    """모델 선택 섹션을 렌더링하는 함수"""
    st.write("**모델 선택**")

    if available_models and len(available_models) > 0:
        # 현재 선택된 모델 가져오기 (우선순위 적용)
        current_selected_model = get_setting_value(
            key="selected_model",
            default_value=available_models[0],
            setting_path=["llm", "model"]  # 백엔드 경로
        )

        # 백엔드에서 직접 ollama_model도 확인
        try:
            backend_settings = api_client.get_settings()
            if 'ollama_model' in backend_settings and backend_settings['ollama_model']:
                if backend_settings['ollama_model'] in available_models:
                    current_selected_model = backend_settings['ollama_model']
        except:
            pass

        # 현재 모델이 사용 가능한 모델 목록에 있는지 확인
        if current_selected_model not in available_models:
            current_selected_model = available_models[0]
            st.warning(f"저장된 모델을 찾을 수 없어 기본 모델로 변경: {current_selected_model}")

        # 현재 인덱스 계산
        try:
            current_index = available_models.index(current_selected_model)
        except ValueError:
            current_index = 0
            current_selected_model = available_models[0]

        # selectbox 렌더링 (key 이름 변경)
        selected_model = st.selectbox(
            "사용할 모델",
            available_models,
            index=current_index,
            help="답변 생성에 사용할 LLM 모델",
            key="llm_model_selector"  # ← key 이름 변경
        )

        # 모델 변경 상태 표시
        if current_selected_model != selected_model:
            st.info(f"저장된 모델: `{current_selected_model}` → 변경됨: `{selected_model}`")
        else:
            st.success(f"현재 모델: `{current_selected_model}`")

        # 별도의 세션 상태 변수에 저장
        st.session_state.current_selected_model = selected_model

        return selected_model

    else:
        ErrorDisplay.render_error_with_suggestions(
            "사용 가능한 모델이 없습니다",
            [
                "Ollama 서버가 실행 중인지 확인",
                "모델이 설치되어 있는지 확인 (`ollama list`)",
                "네트워크 연결 상태 확인",
                "API 서버 로그 확인"
            ]
        )
        st.session_state.current_selected_model = None
        return None


# 3. 수정된 설정 저장 함수의 일부 (UI 값 수집 부분)
def get_ui_values_for_saving():
    """설정 저장을 위한 UI 값들을 수집하는 함수"""
    return {
        'ollama_host': st.session_state.get('ollama_host_input', '').strip(),
        'selected_model': st.session_state.get('current_selected_model'),  # ★ 수정된 변수명 ★
        'auto_refresh': st.session_state.get('auto_refresh_models', False),
        'api_timeout': st.session_state.get('api_timeout_slider', config.api.timeout),
        'rag_timeout': st.session_state.get('rag_timeout_slider', config.api.timeout),
        'temperature': st.session_state.get('temperature_slider', Constants.Defaults.TEMPERATURE),
        'max_tokens': st.session_state.get('max_tokens_input', Constants.Defaults.MAX_TOKENS),
        'top_p': st.session_state.get('top_p_slider', 0.9),
        'frequency_penalty': st.session_state.get('frequency_penalty_slider', 0.0),
        'system_prompt': st.session_state.get('system_prompt_area', Constants.Defaults.SYSTEM_PROMPT),
        'rag_top_k': st.session_state.get('rag_top_k_slider', Constants.Defaults.TOP_K),
        'min_similarity': st.session_state.get('min_similarity_slider', Constants.Defaults.MIN_SIMILARITY),
        'context_window': st.session_state.get('context_window_input', Constants.Defaults.CONTEXT_WINDOW),
        'chunk_size': st.session_state.get('chunk_size_input', Constants.Defaults.CHUNK_SIZE),
        'chunk_overlap': st.session_state.get('chunk_overlap_input', Constants.Defaults.CHUNK_OVERLAP),
        'embedding_model': st.session_state.get('embedding_model_select', Constants.Defaults.EMBEDDING_MODEL),
        'keyword_method': st.session_state.get('current_keyword_method', 'keybert')
    }


# 4. 수정된 설정 저장 후 세션 상태 업데이트 함수
def update_session_after_save(settings_data):
    """설정 저장 후 세션 상태를 업데이트하는 함수"""
    # LLM 설정 업데이트
    for key, value in settings_data["llm"].items():
        st.session_state[key] = value

    # RAG 설정 업데이트
    rag_mapping = {
        "top_k": "rag_top_k",
        "min_score": "min_similarity",
        "context_window": "context_window",
        "chunk_size": "chunk_size",
        "chunk_overlap": "chunk_overlap",
        "embed_model": "embedding_model"
    }
    for rag_key, session_key in rag_mapping.items():
        st.session_state[session_key] = settings_data["rag"][rag_key]

    # ★ 모델 및 Ontology 설정 업데이트 수정 ★
    st.session_state.current_selected_model = settings_data["ollama_model"]
    st.session_state.backend_selected_model = settings_data["ollama_model"]
    st.session_state.current_keyword_method = settings_data["ontology"]["keyword_method"]
    st.session_state.backend_keyword_method = settings_data["ontology"]["keyword_method"]

    # 기본 설정 업데이트
    st.session_state.ollama_host = settings_data["ollama_host"]


# 5. 개선된 기본값 획득 함수
def get_setting_value(key, default_value, setting_path=None):
    """설정 값을 우선순위에 따라 가져오는 함수

    우선순위:
    1. 세션 상태의 backend_ 값
    2. 현재 백엔드 설정
    3. 세션 상태 값
    4. 기본값
    """
    # 1. 세션 상태의 backend_ 값
    backend_key = f"backend_{key}"
    if backend_key in st.session_state:
        return st.session_state[backend_key]

    # 2. 현재 백엔드 설정 (실시간)
    try:
        backend_settings = api_client.get_settings()
        if setting_path and backend_settings:
            nested_value = backend_settings
            for path_key in setting_path:
                if isinstance(nested_value, dict) and path_key in nested_value:
                    nested_value = nested_value[path_key]
                else:
                    nested_value = None
                    break
            if nested_value is not None:
                return nested_value
    except:
        pass

    # 3. 세션 상태 값
    if key in st.session_state:
        return st.session_state[key]

    # 4. 기본값
    return default_value


# 6. 수정된 키워드 추출기 설정 함수
def render_keyword_extractor_settings():
    """키워드 추출기 설정 UI를 렌더링하는 함수"""
    st.subheader("🔍 키워드 추출기 설정")

    # 사용 가능한 옵션
    keyword_options = ["keybert", "llm", "keybert,llm"]

    # 현재 설정값 가져오기 (우선순위 적용)
    current_keyword_method = get_setting_value(
        key="keyword_method",
        default_value="keybert",
        setting_path=["ontology", "keyword_method"]
    )

    # 현재 값이 옵션 목록에 있는지 확인하고 인덱스 계산
    try:
        current_index = keyword_options.index(current_keyword_method)
    except ValueError:
        # 현재 값이 옵션에 없으면 기본값 사용
        current_index = 0
        current_keyword_method = keyword_options[0]

    # selectbox 렌더링 (key 이름 변경)
    selected_method = st.selectbox(
        "기본 키워드 추출 방식",
        keyword_options,
        index=current_index,
        help="온톨로지 추출 시 사용할 기본 키워드 추출 방식을 선택합니다.",
        key="keyword_method_selector"  # ← key 이름 변경
    )

    # 현재 설정 표시
    if current_keyword_method != selected_method:
        st.info(f"현재 저장된 설정: `{current_keyword_method}` → 변경됨: `{selected_method}`")
    else:
        st.success(f"현재 설정: `{current_keyword_method}`")

    # 별도의 세션 상태 변수에 저장
    st.session_state.current_keyword_method = selected_method

    # 설정 설명
    with st.expander("키워드 추출 방식 설명"):
        st.write("**keybert**: KeyBERT 모델 기반 키워드 추출 (빠름, 안정적)")
        st.write("**llm**: LLM 기반 키워드 추출 (정확함, 느림)")
        st.write("**keybert,llm**: 두 방식을 병합하여 사용 (가장 정확함, 가장 느림)")


# 7. 개선된 설정 저장 함수
def save_all_settings_optimized():
    """모든 설정을 서버에 저장하는 최적화된 함수"""
    try:
        ui_values = get_ui_values_for_saving()

        # Config.py 구조에 맞춘 설정 데이터 구성
        settings_data = {
            "ollama_host": ui_values['ollama_host'],
            "ollama_model": ui_values['selected_model'],
            "llm": {
                "model": ui_values['selected_model'],
                "auto_refresh": ui_values['auto_refresh'],
                "api_timeout": ui_values['api_timeout'],
                "rag_timeout": ui_values['rag_timeout'],
                "temperature": ui_values['temperature'],
                "max_tokens": ui_values['max_tokens'],
                "top_p": ui_values['top_p'],
                "frequency_penalty": ui_values['frequency_penalty'],
                "system_prompt": ui_values['system_prompt']
            },
            "rag": {
                "top_k": ui_values['rag_top_k'],
                "min_score": ui_values['min_similarity'],
                "context_window": ui_values['context_window'],
                "chunk_size": ui_values['chunk_size'],
                "chunk_overlap": ui_values['chunk_overlap'],
                "embed_model": ui_values['embedding_model']
            },
            "ontology": {  # ★ ontology 섹션 추가 ★
                "keyword_method": ui_values['keyword_method']
            }
        }

        # 서버에 설정 저장
        with st.spinner("설정을 저장하는 중..."):
            st.info("서버에 설정을 저장하는 중...")
            resp = api_client.update_settings(settings_data)

            if resp.get("status") == "ok":
                st.success("✅ 서버 설정이 저장되었습니다")

                # 로컬 세션 상태도 업데이트
                st.info("로컬 세션 상태를 업데이트하는 중...")

                # LLM 설정 업데이트
                update_session_after_save(settings_data)

                st.success("✅ 로컬 세션 상태도 업데이트되었습니다")
                return True, "설정이 성공적으로 저장되었습니다"

            elif resp.get("status") == "error":
                error_msg = f"서버 설정 저장 실패: {resp.get('message', '알 수 없는 오류')}"
                st.error(f"❌ {error_msg}")
                return False, error_msg
            else:
                warning_msg = f"예상과 다른 응답: {resp}"
                st.warning(f"⚠️ {warning_msg}")
                return False, warning_msg

    except Exception as e:
        error_msg = f"설정 저장 중 오류 발생: {str(e)}"
        st.error(f"❌ {error_msg}")
        return False, error_msg


# 8. 메인 설정 동기화 실행 함수 (페이지 로딩 시)
def initialize_settings_sync():
    """페이지 로딩 시 설정 동기화를 초기화하는 함수"""
    if 'settings_loaded' not in st.session_state:
        with st.spinner("저장된 설정을 불러오는 중..."):
            settings, error_msg = sync_backend_settings_to_session()

            if settings:
                st.success(f"✅ 저장된 설정을 불러왔습니다 ({len(settings)}개 카테고리)")

                # 디버그 정보 표시 (선택적)
                if st.checkbox("불러온 설정 상세보기", key="show_loaded_settings"):
                    with st.expander("불러온 설정 내용"):
                        st.json(settings)
            else:
                if error_msg:
                    st.warning(f"⚠️ {error_msg}")
                st.info("기본값을 사용합니다")

            # 로딩 완료 표시
            st.session_state.settings_loaded = True


# 페이지 설정
st.set_page_config(
    page_title=f"{config.ui.page_title} - 설정",
    page_icon=Constants.Icons.SETTINGS,
    layout=config.ui.layout
)

# API 클라이언트 초기화
if HAS_API_CLIENT:
    api_client = ClientManager.get_client()
else:
    st.error("API 클라이언트를 초기화할 수 없습니다")
    st.stop()

# 헤더
st.title(f"{Constants.Icons.SETTINGS} 시스템 설정")
st.markdown("GTOne RAG 시스템의 설정을 관리합니다.")

# 설정 탭
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    f"{Constants.Icons.AI} AI 설정",
    f"{Constants.Icons.STATUS_INFO} 시스템 상태",
    f"{Constants.Icons.SETTINGS} 고급 설정",
    f"{Constants.Icons.DOWNLOAD} 백업/복원",
    f"{Constants.Icons.STATUS_INFO} 정보"
])

# ===============================
# AI 설정 탭 - 통합된 LLM 설정
# ===============================
with tab1:
    st.header(f"AI 설정")

    # ===============================
    # 페이지 로딩 시 백엔드 설정 동기화
    # ===============================

    # 페이지 로딩 시 설정 동기화 - 개선된 버전
    initialize_settings_sync()

    # 설정 동기화 상태 표시
    with st.expander("🔄 설정 동기화 상태", expanded=False):
        col_sync1, col_sync2 = st.columns(2)

        with col_sync1:
            if st.button("🔄 설정 다시 불러오기", key="reload_settings_btn"):
                with st.spinner("설정을 다시 불러오는 중..."):
                    try:
                        current_settings = api_client.get_settings()
                        st.success(f"✅ 설정 재로딩 완료")

                        with st.expander("불러온 설정 내용"):
                            st.json(current_settings)

                        # 세션 상태 초기화 후 다시 로딩
                        st.session_state.settings_loaded = False
                        st.info("🔄 페이지를 새로고침하여 설정을 적용하세요")

                    except Exception as e:
                        st.error(f"❌ 설정 재로딩 실패: {str(e)}")

        with col_sync2:
            if st.button("🔍 설정 파일 상태", key="check_settings_file"):
                with st.spinner("설정 파일 상태 확인 중..."):
                    try:
                        import requests
                        import os

                        # 로컬 파일 상태 확인
                        settings_file = "./data/rag_settings.json"
                        file_exists = os.path.exists(settings_file)

                        st.write("**로컬 파일 상태:**")
                        st.write(f"- 파일 경로: `{settings_file}`")
                        st.write(f"- 파일 존재: {'✅' if file_exists else '❌'}")

                        if file_exists:
                            file_size = os.path.getsize(settings_file)
                            st.write(f"- 파일 크기: {file_size} bytes")

                            # 파일 내용 미리보기
                            try:
                                with open(settings_file, 'r', encoding='utf-8') as f:
                                    content = f.read()

                                with st.expander("파일 내용 미리보기"):
                                    st.code(content, language="json")

                            except Exception as e:
                                st.error(f"파일 읽기 실패: {str(e)}")

                        # 백엔드 API 확인
                        st.write("**백엔드 API 상태:**")
                        current_settings = api_client.get_settings()
                        st.success("✅ 백엔드 API 정상 작동")
                        st.write(f"반환된 설정 카테고리: {list(current_settings.keys())}")

                    except Exception as e:
                        st.error(f"❌ 상태 확인 실패: {str(e)}")

    # 연결 상태 확인 섹션
    st.subheader(f"{Constants.Icons.STATUS_OK} 연결 상태")

    # 연결 테스트 버튼
    if st.button(f"{Constants.Icons.REFRESH} 연결 테스트", key="connection_test_btn"):
        with st.spinner("연결 상태 확인 중..."):
            if HAS_SYSTEM_HEALTH:
                with ErrorContext("시스템 상태 확인") as ctx:
                    try:
                        health_report = SystemHealthManager.check_full_system_status(api_client, force_refresh=True)
                        st.session_state.connection_status = health_report
                        st.session_state.last_connection_check = datetime.now()
                    except Exception as e:
                        ctx.add_error(e)
            else:
                # Fallback: 기본 연결 테스트
                with ErrorContext("기본 연결 테스트") as ctx:
                    try:
                        response = api_client.health_check()
                        st.session_state.connection_status = response
                        st.session_state.last_connection_check = datetime.now()
                    except Exception as e:
                        ctx.add_error(e)

    # 연결 상태 표시
    if 'connection_status' in st.session_state:
        check_time = st.session_state.get('last_connection_check')

        if HAS_SYSTEM_HEALTH and hasattr(st.session_state.connection_status, 'overall_status'):
            health_report = st.session_state.connection_status
            emoji, message, _ = SystemHealthManager.get_status_display_info(health_report.overall_status)

            if health_report.overall_status == SystemStatus.HEALTHY:
                StatusIndicator.render_status("success", f"{message} ({check_time.strftime('%H:%M:%S')})")
            elif health_report.overall_status == SystemStatus.DEGRADED:
                StatusIndicator.render_status("warning", f"{message} ({check_time.strftime('%H:%M:%S')})")
            else:
                StatusIndicator.render_status("error", f"{message} ({check_time.strftime('%H:%M:%S')})")

            # 서비스 요약
            services_summary = []
            for service_name, service_info in list(health_report.services.items())[:3]:
                emoji_svc, status_text = SystemHealthManager.get_service_display_info(service_info.status)
                services_summary.append(f"{emoji_svc} {service_name}: {status_text}")

            if services_summary:
                st.caption(" | ".join(services_summary))

        else:
            # Fallback 상태 표시
            status = st.session_state.connection_status
            if status.get('status') == 'healthy':
                StatusIndicator.render_status("success", f"연결 성공 ({check_time.strftime('%H:%M:%S')})")
            else:
                StatusIndicator.render_status("error", f"연결 문제 ({check_time.strftime('%H:%M:%S')})")
    else:
        StatusIndicator.render_status("info", "연결 테스트를 수행하여 시스템 상태를 확인하세요")

    st.divider()

    # 키워드 추출기 설정 - 개선된 버전
    render_keyword_extractor_settings()

    # ===============================
    # 통합된 LLM 설정 섹션
    # ===============================
    st.subheader("LLM (언어 모델) 설정")

    # 현재 설정 가져오기 - 백엔드와 세션 상태 병합
    try:
        backend_settings = api_client.get_settings()
    except:
        backend_settings = {}

    col1, col2 = st.columns(2)

    with col1:
        # === 서버 설정 ===
        st.write("**서버 설정**")

        # 백엔드 설정 우선, 없으면 기본값
        default_ollama_host = (
                st.session_state.get("backend_ollama_host") or
                backend_settings.get("ollama_host") or
                "http://localhost:11434"
        )

        ollama_host = st.text_input(
            "Ollama Host",
            value=default_ollama_host,
            help="Ollama LLM 서버 주소",
            key="ollama_host_input"
        )

        # === 빠른 진단 섹션 ===
        st.write("**빠른 진단**")
        col_debug1, col_debug2, col_debug3 = st.columns(3)

        with col_debug1:
            if st.button("🔍 API 상태", key="quick_debug_api"):
                try:
                    import requests

                    response = requests.get(f"{api_client.base_url}/v1/models", timeout=10)

                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, list) and len(data) > 0:
                            st.success(f"✅ API 정상: {len(data)}개 모델")
                            st.write("모델:", ", ".join(data[:3]) + ("..." if len(data) > 3 else ""))
                        elif isinstance(data, list) and len(data) == 0:
                            st.warning("⚠️ API 정상이지만 모델 없음")
                        else:
                            st.info(f"📊 응답: {type(data)}")
                    else:
                        st.error(f"❌ API 오류: HTTP {response.status_code}")

                except Exception as e:
                    st.error(f"❌ API 연결 실패: {str(e)}")

        with col_debug2:
            if st.button("🤖 Ollama", key="quick_debug_ollama"):
                try:
                    import requests

                    response = requests.get("http://localhost:11434/api/tags", timeout=5)

                    if response.status_code == 200:
                        data = response.json()
                        models = data.get("models", [])
                        if models:
                            st.success(f"✅ Ollama: {len(models)}개 모델")
                            for model in models[:3]:
                                st.write(f"• {model.get('name', 'Unknown')}")
                            if len(models) > 3:
                                st.write(f"... 외 {len(models) - 3}개")
                        else:
                            st.warning("⚠️ Ollama 정상, 모델 없음")
                    else:
                        st.error(f"❌ Ollama 오류: HTTP {response.status_code}")

                except requests.exceptions.ConnectionError:
                    st.error("❌ Ollama 서버 미실행")
                    st.info("해결: `ollama serve`")
                except Exception as e:
                    st.error(f"❌ 연결 실패: {str(e)}")

        with col_debug3:
            if st.button("🔧 Backend", key="quick_debug_backend"):
                try:
                    settings = api_client.get_settings()
                    st.success("✅ Backend 정상")

                    models_resp = api_client.get_available_models()
                    if models_resp:
                        st.success(f"✅ {len(models_resp)}개 모델 감지")
                    else:
                        st.warning("⚠️ 모델 목록 비어있음")

                except Exception as e:
                    st.error(f"❌ Backend 오류: {str(e)}")

        st.divider()

        # === 모델 목록 새로고침 ===
        refresh_col, auto_col = st.columns([2, 1])

        with refresh_col:
            if st.button(f"{Constants.Icons.REFRESH} 모델 목록 새로고침",
                         help="서버에서 최신 모델 목록을 가져옵니다", key="refresh_models_btn"):
                with st.spinner("모델 목록 로딩 중..."):
                    with ErrorContext("모델 목록 로딩") as ctx:
                        try:
                            available_models = api_client.get_available_models()

                            if available_models:
                                st.session_state.available_models = available_models
                                st.session_state.models_last_updated = datetime.now()
                                st.success(f"{Constants.Icons.STATUS_OK} {len(available_models)}개 모델을 찾았습니다")
                            else:
                                StatusIndicator.render_status("error", "사용 가능한 모델이 없습니다",
                                                              "Ollama 서버를 확인하세요")
                                st.session_state.available_models = []

                        except Exception as e:
                            ctx.add_error(e)
                            st.session_state.available_models = []

        with auto_col:
            auto_refresh = st.checkbox("자동", help="페이지 로드 시 자동으로 모델 목록을 가져옵니다",
                                       key="auto_refresh_models")

        # 자동 로딩 처리
        if 'available_models' not in st.session_state or auto_refresh:
            if auto_refresh or 'available_models' not in st.session_state:
                with st.spinner("모델 목록 초기 로딩 중..."):
                    with ErrorContext("모델 목록 초기 로딩", show_errors=False) as ctx:
                        try:
                            available_models = api_client.get_available_models()
                            st.session_state.available_models = available_models
                            st.session_state.models_last_updated = datetime.now()

                            if not available_models:
                                StatusIndicator.render_status("warning", "사용 가능한 모델이 없습니다")

                        except Exception as e:
                            ctx.add_error(e)
                            st.session_state.available_models = []

        available_models = st.session_state.get('available_models', [])

        # 마지막 업데이트 시간 표시
        if 'models_last_updated' in st.session_state:
            last_updated = st.session_state.models_last_updated
            st.caption(f"마지막 업데이트: {last_updated.strftime('%H:%M:%S')}")

        selected_model = render_model_selection_section(available_models)

        st.divider()

        # === 연결 및 타임아웃 설정 ===
        st.write("**연결 및 타임아웃 설정**")

        # 백엔드 설정 우선 사용
        default_api_timeout = (
                backend_settings.get("llm", {}).get("api_timeout") or
                st.session_state.get('api_timeout') or
                config.api.timeout
        )

        default_rag_timeout = (
                backend_settings.get("llm", {}).get("rag_timeout") or
                st.session_state.get('rag_timeout') or
                config.api.timeout
        )

        api_timeout = st.slider(
            "API 타임아웃 (초)",
            min_value=30,
            max_value=600,
            value=int(default_api_timeout),
            step=30,
            help="API 요청의 최대 대기 시간",
            key="api_timeout_slider"
        )

        rag_timeout = st.slider(
            "RAG 생성 타임아웃 (초)",
            min_value=60,
            max_value=900,
            value=int(default_rag_timeout),
            step=30,
            help="답변 생성의 최대 대기 시간",
            key="rag_timeout_slider"
        )

        # 타임아웃 설정 적용
        st.session_state.api_timeout = api_timeout
        st.session_state.rag_timeout = rag_timeout
        api_client.set_timeout(api_timeout)

        st.divider()

        # === 모델 파라미터 설정 ===
        if selected_model:
            st.write("**모델 파라미터**")

            # 백엔드 설정과 세션 상태 병합하여 기본값 설정
            default_temperature = (
                    st.session_state.get("backend_temperature") or
                    backend_settings.get("llm", {}).get("temperature") or
                    st.session_state.get('temperature') or
                    Constants.Defaults.TEMPERATURE
            )

            default_max_tokens = (
                    st.session_state.get("backend_max_tokens") or
                    backend_settings.get("llm", {}).get("max_tokens") or
                    st.session_state.get('max_tokens') or
                    Constants.Defaults.MAX_TOKENS
            )

            temperature = st.slider(
                "Temperature (창의성)",
                min_value=Constants.Limits.MIN_TEMPERATURE,
                max_value=Constants.Limits.MAX_TEMPERATURE,
                value=float(default_temperature),
                step=0.1,
                help="낮을수록 일관된 답변, 높을수록 창의적인 답변",
                key="temperature_slider"
            )

            max_tokens = st.number_input(
                "최대 토큰 수",
                min_value=Constants.Limits.MIN_TOKENS,
                max_value=Constants.Limits.MAX_TOKENS,
                value=int(default_max_tokens),
                step=100,
                help="생성할 답변의 최대 길이",
                key="max_tokens_input"
            )
        else:
            StatusIndicator.render_status("warning", "모델을 선택해야 파라미터를 설정할 수 있습니다")

    with col2:
        # === 선택된 모델 정보 표시 ===
        if selected_model:
            with st.expander(f"{Constants.Icons.DOCUMENT} 모델 정보", expanded=True):
                with st.spinner("모델 정보 로딩 중..."):
                    with ErrorContext("모델 정보 로딩", show_errors=False) as ctx:
                        try:
                            model_info = api_client.get_model_info(selected_model)
                            if 'error' not in model_info:
                                st.write(f"**모델**: {model_info.get('name', selected_model)}")

                                # 모델 크기
                                if 'size' in model_info:
                                    size_bytes = model_info['size']
                                    if size_bytes > 0:
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
                            ctx.add_error(e)

        # === 추가 파라미터 ===
        if selected_model:
            st.write("**고급 파라미터**")

            # 백엔드 설정 우선 사용
            default_top_p = (
                    st.session_state.get("backend_top_p") or
                    backend_settings.get("llm", {}).get("top_p") or
                    st.session_state.get('top_p') or
                    0.9
            )

            default_frequency_penalty = (
                    st.session_state.get("backend_frequency_penalty") or
                    backend_settings.get("llm", {}).get("frequency_penalty") or
                    st.session_state.get('frequency_penalty') or
                    0.0
            )

            default_system_prompt = (
                    st.session_state.get("backend_system_prompt") or
                    backend_settings.get("llm", {}).get("system_prompt") or
                    st.session_state.get('system_prompt') or
                    Constants.Defaults.SYSTEM_PROMPT
            )

            top_p = st.slider(
                "Top P",
                min_value=0.0,
                max_value=1.0,
                value=float(default_top_p),
                step=0.05,
                help="확률 분포 상위 P%만 고려",
                key="top_p_slider"
            )

            frequency_penalty = st.slider(
                "Frequency Penalty",
                min_value=0.0,
                max_value=2.0,
                value=float(default_frequency_penalty),
                step=0.1,
                help="반복 단어 사용 억제",
                key="frequency_penalty_slider"
            )

            system_prompt = st.text_area(
                "시스템 프롬프트",
                value=str(default_system_prompt),
                height=150,
                help="AI의 기본 행동 지침",
                key="system_prompt_area"
            )
        else:
            StatusIndicator.render_status("info", "모델을 먼저 선택하세요")

    st.divider()

    # ===============================
    # RAG 설정 (모델이 있을 때만)
    # ===============================
    if selected_model:
        st.subheader("RAG (검색 증강 생성) 설정")

        col1, col2 = st.columns(2)

        with col1:
            # 백엔드 RAG 설정 사용
            rag_backend = backend_settings.get("rag", {})

            # 검색 문서 수
            default_rag_top_k = (
                    st.session_state.get("backend_rag_top_k") or
                    rag_backend.get("top_k") or
                    st.session_state.get('rag_top_k') or
                    Constants.Defaults.TOP_K
            )

            rag_top_k = st.slider(
                "검색할 문서 수",
                min_value=Constants.Limits.MIN_TOP_K,
                max_value=Constants.Limits.MAX_TOP_K,
                value=int(default_rag_top_k),
                help="답변 생성 시 참조할 문서의 개수",
                key="rag_top_k_slider"
            )

            # 최소 유사도
            default_min_similarity = (
                    st.session_state.get("backend_min_similarity") or
                    rag_backend.get("min_score") or
                    st.session_state.get('min_similarity') or
                    Constants.Defaults.MIN_SIMILARITY
            )

            min_similarity = st.slider(
                "최소 유사도 임계값",
                min_value=Constants.Limits.MIN_SIMILARITY,
                max_value=Constants.Limits.MAX_SIMILARITY,
                value=float(default_min_similarity),
                step=0.05,
                help="이 값 이상의 유사도를 가진 문서만 사용",
                key="min_similarity_slider"
            )

            # 컨텍스트 길이
            default_context_window = (
                    st.session_state.get("backend_context_window") or
                    rag_backend.get("context_window") or
                    st.session_state.get('context_window') or
                    Constants.Defaults.CONTEXT_WINDOW
            )

            context_window = st.number_input(
                "컨텍스트 윈도우 크기",
                min_value=500,
                max_value=8000,
                value=int(default_context_window),
                step=500,
                help="LLM에 제공할 최대 컨텍스트 길이",
                key="context_window_input"
            )

        with col2:
            # 청크 설정
            default_chunk_size = (
                    st.session_state.get("backend_chunk_size") or
                    rag_backend.get("chunk_size") or
                    st.session_state.get('chunk_size') or
                    Constants.Defaults.CHUNK_SIZE
            )

            default_chunk_overlap = (
                    st.session_state.get("backend_chunk_overlap") or
                    rag_backend.get("chunk_overlap") or
                    st.session_state.get('chunk_overlap') or
                    Constants.Defaults.CHUNK_OVERLAP
            )

            chunk_size = st.number_input(
                "청크 크기",
                min_value=100,
                max_value=2000,
                value=int(default_chunk_size),
                step=100,
                help="문서를 분할하는 기본 크기",
                key="chunk_size_input"
            )

            chunk_overlap = st.number_input(
                "청크 중첩",
                min_value=0,
                max_value=500,
                value=int(default_chunk_overlap),
                step=50,
                help="청크 간 중첩되는 텍스트 길이",
                key="chunk_overlap_input"
            )

            # 임베딩 모델
            embedding_options = ["intfloat/multilingual-e5-large-instruct", "intfloat/e5-large-v2"]
            default_embedding_model = (
                    st.session_state.get("backend_embedding_model") or
                    rag_backend.get("embed_model") or
                    st.session_state.get('embedding_model') or
                    Constants.Defaults.EMBEDDING_MODEL
            )

            try:
                embedding_index = embedding_options.index(default_embedding_model)
            except ValueError:
                embedding_index = 0

            embedding_model = st.selectbox(
                "임베딩 모델",
                embedding_options,
                index=embedding_index,
                help="문서 벡터화에 사용할 모델",
                key="embedding_model_select"
            )
    else:
        StatusIndicator.render_status("warning", "모델을 선택해야 RAG 설정을 할 수 있습니다")

    # ===============================
    # 통합된 설정 저장 버튼
    # ===============================
    col_save, col_reset, col_test = st.columns([2, 1, 1])

    with col_save:
        if selected_model:
            if st.button(f"{Constants.Icons.DOWNLOAD} 전체 설정 저장", type="primary", key="save_all_settings"):
                success, message = save_all_settings_optimized()

                if success:
                    st.success(f"{Constants.Icons.STATUS_OK} {message}")
                    st.info("💡 설정이 ./data/rag_settings.json 파일에 저장되었습니다")
                else:
                    st.error(f"❌ {message}")
        else:
            st.button(f"{Constants.Icons.DOWNLOAD} 전체 설정 저장", disabled=True,
                      help="모델을 먼저 선택하세요", key="save_all_settings_disabled")

    with col_reset:
        if st.button(f"{Constants.Icons.REFRESH} 기본값 복원", key="reset_all_settings"):
            if st.session_state.get('confirm_reset_all') != True:
                st.session_state.confirm_reset_all = True
                StatusIndicator.render_status("warning", "다시 클릭하면 모든 설정이 기본값으로 복원됩니다")
            else:
                # 기본값으로 복원
                defaults = {
                    "temperature": Constants.Defaults.TEMPERATURE,
                    "max_tokens": Constants.Defaults.MAX_TOKENS,
                    "top_p": 0.9,
                    "frequency_penalty": 0.0,
                    "system_prompt": Constants.Defaults.SYSTEM_PROMPT,
                    "rag_top_k": Constants.Defaults.TOP_K,
                    "min_similarity": Constants.Defaults.MIN_SIMILARITY,
                    "context_window": Constants.Defaults.CONTEXT_WINDOW,
                    "chunk_size": Constants.Defaults.CHUNK_SIZE,
                    "chunk_overlap": Constants.Defaults.CHUNK_OVERLAP,
                    "embedding_model": Constants.Defaults.EMBEDDING_MODEL,
                    "api_timeout": config.api.timeout,
                    "rag_timeout": config.api.timeout
                }

                for key, value in defaults.items():
                    st.session_state[key] = value

                # 백엔드 설정 캐시도 초기화
                for key in list(st.session_state.keys()):
                    if key.startswith('backend_'):
                        del st.session_state[key]

                del st.session_state.confirm_reset_all
                st.session_state.settings_loaded = False  # 다시 로딩하도록
                st.success(f"{Constants.Icons.STATUS_OK} 설정이 기본값으로 복원되었습니다")
                st.rerun()

    with col_test:
        if selected_model:
            if st.button(f"{Constants.Icons.AI} 모델 테스트", key="test_model"):
                with st.spinner("모델 테스트 중..."):
                    with ErrorContext("모델 테스트") as ctx:
                        try:
                            test_result = api_client.generate_answer(
                                query="안녕하세요",
                                top_k=1,
                                model=selected_model,
                                timeout=60
                            )

                            if 'error' not in test_result:
                                st.success(f"{Constants.Icons.STATUS_OK} 모델 테스트 성공")
                                st.info(f"사용된 모델: {selected_model}")

                                # 테스트 응답 표시
                                if 'answer' in test_result:
                                    with st.expander("테스트 응답 보기"):
                                        st.write(test_result['answer'])
                            else:
                                ErrorDisplay.render_error_with_suggestions(
                                    f"모델 테스트 실패: {test_result.get('error')}",
                                    ["모델 설정을 확인하세요", "Ollama 서버 상태를 확인하세요"]
                                )
                        except Exception as e:
                            ctx.add_error(e)
        else:
            st.button(f"{Constants.Icons.AI} 모델 테스트", disabled=True,
                      help="모델을 먼저 선택하세요", key="test_model_disabled")

# ===============================
# 시스템 상태 탭 - 개선된 버전
# ===============================
with tab2:
    st.header(f"{Constants.Icons.STATUS_INFO} 시스템 상태")

    # 상태 확인 버튼들
    actions = [
        {
            "label": f"{Constants.Icons.REFRESH} 상태 새로고침",
            "key": "refresh_status_main",
            "type": "primary"
        },
        {
            "label": "자동 새로고침",
            "key": "auto_refresh_toggle",
            "type": "secondary"
        },
        {
            "label": f"{Constants.Icons.DELETE} 캐시 초기화",
            "key": "clear_cache_main",
            "type": "secondary"
        }
    ]

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(actions[0]["label"], type=actions[0]["type"], key=actions[0]["key"]):
            with st.spinner("시스템 상태 확인 중..."):
                if HAS_SYSTEM_HEALTH:
                    with ErrorContext("시스템 상태 확인") as ctx:
                        try:
                            health_report = SystemHealthManager.check_full_system_status(api_client, force_refresh=True)
                            st.session_state.last_health_check = health_report
                            st.session_state.health_check_time = datetime.now()
                            st.success(f"{Constants.Icons.STATUS_OK} 상태 확인 완료")
                        except Exception as e:
                            ctx.add_error(e)

    with col2:
        auto_refresh = st.checkbox("자동 새로고침", help="30초마다 자동으로 상태를 확인합니다")

    with col3:
        if st.button(actions[2]["label"], key=actions[2]["key"]):
            if HAS_SYSTEM_HEALTH:
                SystemHealthManager.clear_cache()
            # 세션 캐시도 초기화
            cache_keys = ['system_health_cache', 'last_health_check', 'health_check_time']
            for key in cache_keys:
                if key in st.session_state:
                    del st.session_state[key]
            st.info("상태 캐시가 초기화되었습니다")

    # 현재 상태 표시
    if HAS_SYSTEM_HEALTH:
        cached_report = SystemHealthManager.get_cached_status()
        health_report = cached_report or st.session_state.get('last_health_check')

        if health_report and hasattr(health_report, 'overall_status'):
            check_time = health_report.last_updated if cached_report else st.session_state.get('health_check_time', datetime.now())
            st.caption(f"마지막 확인: {check_time.strftime('%Y-%m-%d %H:%M:%S')}")

            # 전체 상태
            emoji, message, _ = SystemHealthManager.get_status_display_info(health_report.overall_status)

            if health_report.overall_status == SystemStatus.HEALTHY:
                StatusIndicator.render_status("success", message)
            elif health_report.overall_status == SystemStatus.DEGRADED:
                StatusIndicator.render_status("warning", message)
            elif health_report.overall_status == SystemStatus.INITIALIZING:
                StatusIndicator.render_status("info", message)
            else:
                StatusIndicator.render_status("error", message)

            # 오류 메시지 표시
            if health_report.errors:
                st.subheader(f"{Constants.Icons.STATUS_WARNING} 감지된 문제")
                ErrorDisplay.render_validation_errors(health_report.errors)

            # 서비스별 상태 - 상세 표시
            st.divider()
            st.subheader(f"{Constants.Icons.SETTINGS} 서비스 상태")

            service_display_names = {
                'api_server': f'{Constants.Icons.STATUS_OK} API 서버',
                'qdrant': f'{Constants.Icons.STATUS_OK} Qdrant 벡터 DB',
                'ollama': f'{Constants.Icons.AI} Ollama LLM',
                'embedder': '🔤 임베딩 모델',
                'celery': '📨 Celery 작업 큐'
            }

            for service_key, display_name in service_display_names.items():
                if service_key in health_report.services:
                    service_info = health_report.services[service_key]
                    emoji, status_text = SystemHealthManager.get_service_display_info(service_info.status)

                    with st.expander(f"{emoji} {display_name}: {status_text}",
                                   expanded=(service_info.status != ServiceStatus.CONNECTED)):
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            st.write(f"**상태**: {service_info.status.value}")
                            if service_info.message:
                                st.write(f"**메시지**: {service_info.message}")
                            st.write(f"**확인 시간**: {service_info.last_check.strftime('%H:%M:%S')}")

                        with col2:
                            # 서비스별 세부 정보 표시
                            if service_info.details:
                                st.write("**세부 정보**:")
                                for key, value in service_info.details.items():
                                    if isinstance(value, list) and len(value) > 3:
                                        st.caption(f"• {key}: {len(value)}개 ({', '.join(value[:3])}...)")
                                    elif isinstance(value, (int, float)) and key.endswith('_ratio'):
                                        st.caption(f"• {key}: {value:.1%}")
                                    else:
                                        st.caption(f"• {key}: {value}")

            # 시스템 메트릭
            st.divider()
            st.subheader(f"{Constants.Icons.STATUS_INFO} 시스템 메트릭")

            metrics = []

            # Qdrant 컬렉션 수
            qdrant_info = health_report.services.get('qdrant')
            if qdrant_info and qdrant_info.details:
                collections = qdrant_info.details.get('collections', [])
                metrics.append({"title": "Qdrant 컬렉션", "value": len(collections)})
            else:
                metrics.append({"title": "Qdrant 컬렉션", "value": "N/A"})

            # Ollama 모델 수
            ollama_info = health_report.services.get('ollama')
            if ollama_info and ollama_info.details:
                total_models = ollama_info.details.get('total_models', 0)
                metrics.append({"title": "Ollama 모델", "value": total_models})
            else:
                metrics.append({"title": "Ollama 모델", "value": "N/A"})

            # 한국어 컨텐츠 비율
            if qdrant_info and qdrant_info.details:
                korean_ratio = qdrant_info.details.get('korean_content_ratio', 0)
                metrics.append({"title": "한국어 비율", "value": f"{korean_ratio:.1%}"})
            else:
                metrics.append({"title": "한국어 비율", "value": "N/A"})

            # 캐시 만료 시간
            if cached_report:
                expires_in = (cached_report.cache_expires - datetime.now()).total_seconds()
                if expires_in > 0:
                    metrics.append({"title": "캐시 만료", "value": f"{int(expires_in)}초 후"})
                else:
                    metrics.append({"title": "캐시 만료", "value": "만료됨"})
            else:
                metrics.append({"title": "캐시 만료", "value": "N/A"})

            MetricCard.render_metric_grid(metrics)

        else:
            StatusIndicator.render_status("info", "상태 새로고침 버튼을 클릭하여 시스템 상태를 확인하세요")

            if st.button("자동 상태 확인", key="auto_health_check"):
                with st.spinner("시스템 상태 자동 확인 중..."):
                    with ErrorContext("자동 상태 확인") as ctx:
                        try:
                            health_report = SystemHealthManager.check_full_system_status(api_client)
                            st.session_state.last_health_check = health_report
                            st.session_state.health_check_time = datetime.now()
                            st.rerun()
                        except Exception as e:
                            ctx.add_error(e)
    else:
        StatusIndicator.render_status("warning", "시스템 상태 관리자를 사용할 수 없습니다")

    # 자동 새로고침 처리
    if auto_refresh and HAS_SYSTEM_HEALTH:
        cached_report = SystemHealthManager.get_cached_status()
        if cached_report:
            expires_in = (cached_report.cache_expires - datetime.now()).total_seconds()
            if expires_in <= 0:
                st.rerun()

# ===============================
# 고급 설정 탭
# ===============================
with tab3:
    st.header(f"{Constants.Icons.SETTINGS} 고급 설정")

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

    # 파일 설정 - config 사용
    st.subheader("파일 업로드 설정")

    col1, col2 = st.columns(2)

    with col1:
        # 파일 크기 설정
        max_file_size = st.number_input(
            "최대 파일 크기 (MB)",
            min_value=1,
            max_value=200,
            value=config.file.max_file_size_mb,
            help="개별 파일의 최대 크기"
        )

        max_archive_size = st.number_input(
            "최대 압축 파일 크기 (MB)",
            min_value=1,
            max_value=500,
            value=config.file.max_archive_size_mb,
            help="압축 파일의 최대 크기"
        )

    with col2:
        # 지원 확장자
        st.write("**지원 파일 확장자**")

        # 문서 파일
        doc_extensions = st.multiselect(
            "문서 파일",
            ['pdf', 'txt', 'docx', 'doc', 'md', 'rtf'],
            default=['pdf', 'txt', 'docx', 'doc'],
            help="지원할 문서 파일 형식"
        )

        # 이미지 파일
        img_extensions = st.multiselect(
            "이미지 파일",
            ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff'],
            default=['png', 'jpg', 'jpeg'],
            help="지원할 이미지 파일 형식"
        )

    # 고급 설정 저장
    if st.button(f"{Constants.Icons.DOWNLOAD} 고급 설정 저장", type="primary"):
        advanced_settings = {
            "vector_db": {
                "host": qdrant_host,
                "port": qdrant_port,
                "collection": collection_name,
                "vector_size": vector_size,
                "distance_metric": distance_metric,
                "index_threshold": index_threshold
            },
            "file": {
                "max_file_size_mb": max_file_size,
                "max_archive_size_mb": max_archive_size,
                "allowed_extensions": doc_extensions + img_extensions
            }
        }

        st.session_state.advanced_settings = advanced_settings
        st.success(f"{Constants.Icons.STATUS_OK} 고급 설정이 저장되었습니다")

# ===============================
# 백업/복원 탭
# ===============================
with tab4:
    st.header(f"{Constants.Icons.DOWNLOAD} 백업 및 복원")

    # 백업
    st.subheader(f"{Constants.Icons.UPLOAD} 백업")

    backup_options = st.multiselect(
        "백업할 항목 선택",
        ["설정", "대화 기록", "검색 기록", "업로드 파일 목록"],
        default=["설정", "대화 기록"]
    )

    if st.button(f"{Constants.Icons.DOWNLOAD} 백업 생성", type="primary"):
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
            label=f"{Constants.Icons.DOWNLOAD} 백업 다운로드",
            data=json.dumps(backup_data, ensure_ascii=False, indent=2),
            file_name=f"gtone_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

    st.divider()

    # 복원
    st.subheader(f"{Constants.Icons.UPLOAD} 복원")

    uploaded_backup = st.file_uploader(
        "백업 파일 선택",
        type=["json"],
        help="이전에 생성한 백업 파일을 업로드하세요"
    )

    if uploaded_backup is not None:
        with ErrorContext("백업 파일 처리") as ctx:
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

                if st.button(f"{Constants.Icons.REFRESH} 복원 실행", type="secondary"):
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

                    st.success(f"{Constants.Icons.STATUS_OK} 복원이 완료되었습니다")
                    rerun()

            except Exception as e:
                ctx.add_error(e)

# ===============================
# 정보 탭
# ===============================
with tab5:
    st.header(f"{Constants.Icons.STATUS_INFO} 시스템 정보")

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

    # 설정 정보 - config 사용
    st.subheader("현재 설정")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**환경 설정**")
        st.write(f"• 환경: {config.environment.value}")
        st.write(f"• API URL: {config.api.base_url}")
        st.write(f"• API 타임아웃: {config.api.timeout}초")

    with col2:
        st.write("**파일 설정**")
        st.write(f"• 최대 파일 크기: {config.file.max_file_size_mb}MB")
        st.write(f"• 최대 압축 파일: {config.file.max_archive_size_mb}MB")
        st.write(f"• 지원 확장자: {len(config.file.allowed_extensions)}개")

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
        st.markdown(f"[{Constants.Icons.DOCUMENT} 사용자 가이드]({Constants.URLs.GITHUB}/wiki)")

    with col2:
        st.markdown(f"[{Constants.Icons.STATUS_ERROR} 버그 리포트]({Constants.URLs.GITHUB}/issues)")

    with col3:
        st.markdown(f"[{Constants.Icons.AI} 커뮤니티](https://discord.gg/selmo)")

    # 연락처 - 상수 사용
    st.divider()
    st.caption(f"문의: {Constants.URLs.SUPPORT_EMAIL} | 기술 지원: tech@gtone.com")

# 푸터
st.divider()
st.caption(f"{Constants.Icons.STATUS_INFO} 설정 변경 후에는 시스템을 재시작하거나 새로고침이 필요할 수 있습니다.")