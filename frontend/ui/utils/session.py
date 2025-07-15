"""
세션 상태 관리 유틸리티
Streamlit 세션 상태를 효율적으로 관리하기 위한 헬퍼 함수들
"""
import streamlit as st
from typing import Any, Dict, List
from datetime import datetime
import json


class SessionManager:
    """Streamlit 세션 상태 관리자"""
    
    @staticmethod
    def init_session_state():
        """세션 상태 초기화"""
        # 메시지 관련
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        
        # 파일 업로드 관련
        if 'uploaded_files' not in st.session_state or not st.session_state.uploaded_files:
            try:
                # 순환 의존성 방지를 위해 지연 import
                from frontend.ui.utils.api_client import APIClient
                docs = APIClient().list_documents()  # 백엔드에서 최신 목록 수집

                # 누락 필드 기본값 보강 (표시 오류 방지)
                for d in docs:
                    d.setdefault("time", "-")
                    d.setdefault("size", "-")
                    st.session_state.uploaded_files = docs
            except Exception as e:
                st.session_state.uploaded_files = []
                st.warning(f"문서 목록 동기화 실패: {e}")

        # 검색 관련
        if 'search_history' not in st.session_state:
            st.session_state.search_history = []
        
        if 'search_query' not in st.session_state:
            st.session_state.search_query = ""
        
        # 설정 관련
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
                "model": "gemma3:27b",
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