"""
세션 상태 관리 유틸리티
Streamlit 세션 상태를 효율적으로 관리하기 위한 헬퍼 함수들
"""
import logging
import streamlit as st
from typing import Any, Dict, List
from datetime import datetime
import json


logger = logging.getLogger(__name__)

class SessionManager:
    """Streamlit 세션 상태 관리자"""

    @staticmethod
    def init_session_state():
        """세션 상태 초기화 - 타입 안전 처리 버전"""
        # 메시지 관련
        if 'messages' not in st.session_state:
            st.session_state.messages = []

        # 파일 업로드 관련 - 개선된 오류 처리
        if 'uploaded_files' not in st.session_state or not st.session_state.uploaded_files:
            try:
                # 순환 의존성 방지를 위해 지연 import
                from frontend.ui.utils.client_manager import ClientManager

                # API 호출 및 응답 검증
                api_response = ClientManager.get_client().list_documents()
                logging.info(f"API 응답 타입: {type(api_response)}")
                logging.info(f"API 응답 내용: {api_response}")

                # 🔧 API 응답 타입 검증 및 안전 처리
                docs = []

                if isinstance(api_response, dict):
                    # 새로운 API 형식: {"documents": [...], "total_documents": N}
                    if 'documents' in api_response:
                        potential_docs = api_response['documents']
                        if isinstance(potential_docs, list):
                            docs = potential_docs
                        else:
                            st.warning(f"API 응답의 'documents' 필드가 리스트가 아님: {type(potential_docs)}")
                            docs = []
                    else:
                        # 딕셔너리이지만 'documents' 키가 없는 경우
                        st.warning(f"API 응답에 'documents' 키가 없음. 사용 가능한 키: {list(api_response.keys())}")
                        docs = []

                elif isinstance(api_response, list):
                    # 레거시 API 형식: 직접 리스트 반환
                    docs = api_response

                else:
                    # 예상하지 못한 타입
                    st.warning(f"예상하지 못한 API 응답 타입: {type(api_response)}")
                    docs = []

                # 🔧 개별 문서 타입 검증 및 필드 보강
                processed_docs = []
                for i, d in enumerate(docs):
                    try:
                        if isinstance(d, dict):
                            # 딕셔너리인 경우에만 setdefault 호출
                            d.setdefault("time", "-")
                            d.setdefault("size", "-")
                            processed_docs.append(d)
                        elif isinstance(d, str):
                            # 문자열인 경우 기본 구조 생성
                            st.warning(f"문서 {i}: 문자열 형태 데이터 발견, 기본 구조로 변환")
                            processed_docs.append({
                                "name": d,
                                "time": "-",
                                "size": "-",
                                "chunks": 0,
                                "type": "unknown"
                            })
                        else:
                            # 기타 타입인 경우 경고 후 건너뜀
                            st.warning(f"문서 {i}: 예상하지 못한 타입 ({type(d)}), 건너뜀")
                            continue

                    except Exception as doc_error:
                        st.warning(f"문서 {i} 처리 중 오류: {doc_error}")
                        continue

                st.session_state.uploaded_files = processed_docs

                if processed_docs:
                    st.success(f"✅ 문서 목록 동기화 완료: {len(processed_docs)}개")
                else:
                    st.info("📋 현재 업로드된 문서가 없습니다")

            except Exception as e:
                # 전체 동기화 실패 시 빈 리스트로 초기화
                st.session_state.uploaded_files = []
                st.warning(f"⚠️ 문서 목록 동기화 실패: {e}")
                st.info("💡 빈 목록으로 초기화되었습니다. 문서를 새로 업로드해보세요.")

        # 검색 관련
        if 'search_history' not in st.session_state:
            st.session_state.search_history = []

        if 'search_query' not in st.session_state:
            st.session_state.search_query = ""

        # 기본값(최초 실행 시)
        if 'ai_settings' not in st.session_state:
            st.session_state.ai_settings = SessionManager.get_default_ai_settings()

        if 'advanced_settings' not in st.session_state:
            st.session_state.advanced_settings = SessionManager.get_default_advanced_settings()

        # 시스템 상태
        if 'health_checked' not in st.session_state:
            st.session_state.health_checked = False

        # 사용자 설정
        if 'user_preferences' not in st.session_state:
            st.session_state.user_preferences = SessionManager.get_default_user_preferences()
    
    @staticmethod
    def get_default_ai_settings() -> Dict:
        """기본 AI 설정 반환"""
        return {
            "llm": {
                "model": "gemma3n:latest",
                "temperature": 0.3,
                "max_tokens": 1000,
                "top_p": 0.9,
                "frequency_penalty": 0.0,
                "system_prompt": "당신은 문서 기반 질의응답 시스템입니다."
            },
            "rag": {
                "top_k": 5,
                "min_similarity": 0.1,
                "context_window": 3000,
                "chunk_size": 500,
                "chunk_overlap": 50,
                "embedding_model": "intfloat/multilingual-e5-large-instruct"
            }
        }
    
    @staticmethod
    def get_default_advanced_settings() -> Dict:
        """기본 고급 설정 반환"""
        return {
            "vector_db": {
                "host": "qdrant",
                "port": 6333,
                "collection": "chunks",
                "vector_size": 1024,
                "distance_metric": "Cosine",
                "index_threshold": 10000
            },
            "ocr": {
                "engine": "Tesseract",
                "languages": ["kor", "eng"]
            }
        }
    
    @staticmethod
    def get_default_user_preferences() -> Dict:
        """기본 사용자 설정 반환"""
        return {
            "theme": "light",
            "language": "ko",
            "notifications": True,
            "auto_save": True,
            "show_tooltips": True
        }
    
    @staticmethod
    def add_message(role: str, content: str, **kwargs):
        """메시지 추가"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        st.session_state.messages.append(message)
    
    @staticmethod
    def clear_messages():
        """메시지 초기화"""
        st.session_state.messages = []
    
    @staticmethod
    def add_uploaded_file(file_info: Dict):
        """업로드 파일 정보 추가"""
        st.session_state.uploaded_files.append({
            **file_info,
            "uploaded_at": datetime.now().isoformat()
        })
    
    @staticmethod
    def remove_uploaded_file(file_name: str):
        """업로드 파일 정보 제거"""
        st.session_state.uploaded_files = [
            f for f in st.session_state.uploaded_files 
            if f.get('name') != file_name
        ]
    
    @staticmethod
    def add_search_history(query: str, result_count: int):
        """검색 기록 추가"""
        st.session_state.search_history.append({
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "result_count": result_count
        })
        
        # 최대 100개까지만 유지
        if len(st.session_state.search_history) > 100:
            st.session_state.search_history = st.session_state.search_history[-100:]
    
    @staticmethod
    def get_recent_searches(limit: int = 10) -> List[Dict]:
        """최근 검색 기록 반환"""
        return st.session_state.search_history[-limit:][::-1]
    
    @staticmethod
    def update_setting(category: str, key: str, value: Any):
        """설정 업데이트"""
        if category == "ai":
            if key in st.session_state.ai_settings:
                st.session_state.ai_settings[key] = value
        elif category == "advanced":
            if key in st.session_state.advanced_settings:
                st.session_state.advanced_settings[key] = value
        elif category == "user":
            if key in st.session_state.user_preferences:
                st.session_state.user_preferences[key] = value
    
    @staticmethod
    def get_setting(category: str, key: str, default: Any = None) -> Any:
        """설정 값 조회"""
        if category == "ai":
            return st.session_state.ai_settings.get(key, default)
        elif category == "advanced":
            return st.session_state.advanced_settings.get(key, default)
        elif category == "user":
            return st.session_state.user_preferences.get(key, default)
        return default
    
    @staticmethod
    def export_session_data() -> str:
        """세션 데이터 내보내기"""
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "messages": st.session_state.get("messages", []),
            "uploaded_files": st.session_state.get("uploaded_files", []),
            "search_history": st.session_state.get("search_history", []),
            "settings": {
                "ai": st.session_state.get("ai_settings", {}),
                "advanced": st.session_state.get("advanced_settings", {}),
                "user": st.session_state.get("user_preferences", {})
            }
        }
        return json.dumps(export_data, ensure_ascii=False, indent=2)
    
    @staticmethod
    def import_session_data(data: str):
        """세션 데이터 가져오기"""
        try:
            import_data = json.loads(data)
            
            if "messages" in import_data:
                st.session_state.messages = import_data["messages"]
            
            if "uploaded_files" in import_data:
                st.session_state.uploaded_files = import_data["uploaded_files"]
            
            if "search_history" in import_data:
                st.session_state.search_history = import_data["search_history"]
            
            if "settings" in import_data:
                settings = import_data["settings"]
                if "ai" in settings:
                    st.session_state.ai_settings = settings["ai"]
                    SessionManager._hydrate_flat_keys_from_ai()  # ⭐ 추가
                if "advanced" in settings:
                    st.session_state.advanced_settings = settings["advanced"]
                if "user" in settings:
                    st.session_state.user_preferences = settings["user"]
            
            return True
        except Exception as e:
            st.error(f"데이터 가져오기 실패: {str(e)}")
            return False
    
    @staticmethod
    def get_session_stats() -> Dict:
        """세션 통계 반환"""
        return {
            "message_count": len(st.session_state.get("messages", [])),
            "uploaded_files_count": len(st.session_state.get("uploaded_files", [])),
            "search_history_count": len(st.session_state.get("search_history", [])),
            "session_duration": None,  # 구현 필요
            "total_queries": sum(1 for m in st.session_state.get("messages", []) if m.get("role") == "user")
        }

    @staticmethod
    def _hydrate_flat_keys_from_ai():
        """ai_settings → legacy 평면 키 동기화"""
        ai = st.session_state.get("ai_settings", {})
        llm = ai.get("llm", {})
        rag = ai.get("rag", {})
        api = ai.get("api", {})

        mapping = {
            # LLM
            ("selected_model", llm.get("model")),
            ("temperature", llm.get("temperature")),
            ("max_tokens", llm.get("max_tokens")),
            ("top_p", llm.get("top_p")),
            ("frequency_penalty", llm.get("frequency_penalty")),
            ("system_prompt", llm.get("system_prompt")),
            # RAG
            ("rag_top_k", rag.get("top_k")),
            ("min_similarity", rag.get("min_similarity")),
            ("context_window", rag.get("context_window")),
            ("chunk_size", rag.get("chunk_size")),
            ("chunk_overlap", rag.get("chunk_overlap")),
            ("embedding_model", rag.get("embedding_model")),
            # API
            ("api_timeout", api.get("timeout")),
            ("rag_timeout", api.get("rag_timeout")),
        }

        for key, val in mapping:
            if val is not None:
                st.session_state[key] = val


def init_page_state(page_name: str):
    """특정 페이지의 상태 초기화"""
    page_states = {
        "chat": {
            "input_text": "",
            "is_typing": False,
            "show_sources": True
        },
        "search": {
            "last_query": "",
            "filter_options": {},
            "sort_by": "relevance"
        },
        "documents": {
            "selected_files": [],
            "view_mode": "grid",
            "sort_order": "newest"
        },
        "settings": {
            "active_tab": "ai",
            "unsaved_changes": False
        }
    }
    
    if f"{page_name}_state" not in st.session_state:
        st.session_state[f"{page_name}_state"] = page_states.get(page_name, {})


def get_page_state(page_name: str) -> Dict:
    """특정 페이지의 상태 반환"""
    return st.session_state.get(f"{page_name}_state", {})


def update_page_state(page_name: str, key: str, value: Any):
    """특정 페이지의 상태 업데이트"""
    if f"{page_name}_state" not in st.session_state:
        init_page_state(page_name)
    
    st.session_state[f"{page_name}_state"][key] = value


def clear_page_state(page_name: str):
    """특정 페이지의 상태 초기화"""
    if f"{page_name}_state" in st.session_state:
        del st.session_state[f"{page_name}_state"]
    init_page_state(page_name)