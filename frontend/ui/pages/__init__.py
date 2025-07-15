"""
GTOne RAG System - Pages Package  
Streamlit 멀티페이지 애플리케이션의 페이지들
"""

# 페이지 모듈들 - 직접 import하지 않고 문서화만
# (Streamlit은 pages/ 폴더의 .py 파일들을 자동으로 페이지로 인식)

PAGES = {
    "documents.py": {
        "title": "📄 문서 관리",
        "description": "문서 업로드, 관리 및 통계",
        "icon": "📄"
    },
    "search.py": {
        "title": "🔍 문서 검색", 
        "description": "벡터 기반 문서 검색",
        "icon": "🔍"
    },
    "settings.py": {
        "title": "⚙️ 시스템 설정",
        "description": "AI 모델 및 시스템 설정",
        "icon": "⚙️"
    }
}

def get_page_info(page_name: str) -> dict:
    """페이지 정보 조회"""
    return PAGES.get(page_name, {
        "title": page_name,
        "description": "페이지 설명 없음",
        "icon": "📄"
    })

def list_pages() -> list:
    """사용 가능한 페이지 목록 반환"""
    return list(PAGES.keys())

__all__ = [
    "PAGES",
    "get_page_info", 
    "list_pages"
]