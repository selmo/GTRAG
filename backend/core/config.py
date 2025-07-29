"""
백엔드 설정 관리 - 통합된 버전
- 기존 코드 호환성 유지
- 동적 설정 파일 지원
- 안정적인 import 구조
"""
from pathlib import Path
from typing import Any, Dict
import json
import os
import logging

logger = logging.getLogger(__name__)

# ===============================
# 1. 기존 코드 호환성을 위한 Settings 클래스
# ===============================

try:
    from pydantic import BaseSettings, Field

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False


    # Pydantic이 없는 경우 간단한 클래스로 대체
    class BaseSettings:
        def __init__(self):
            pass


class Settings:
    """기존 코드 호환성을 위한 Settings 클래스"""

    def __init__(self):
        # Vector DB
        self.qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))

        # LLM / Ollama
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "gemma3n:latest")

        # Celery
        self.broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        self.result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")


# 전역 settings 객체 생성 (기존 코드 호환성)
settings = Settings()

# ===============================
# 2. 동적 설정 파일 시스템
# ===============================

# 설정 파일 경로들 (우선순위 순)
SETTINGS_PATHS = [
    "./data/rag_settings.json",  # 새로운 구조화된 설정 파일
    "./data/settings.json"  # 기존 단순 설정 파일
]

# 기본 설정 템플릿
_DEFAULTS = {
    "ollama_host": "http://localhost:11434",
    "ollama_model": "gemma3n:latest",
    "llm": {
        "model": "",
        "auto_refresh": False,
        "api_timeout": 300,
        "rag_timeout": 600,
        "temperature": 0.3,
        "max_tokens": 4000,
        "top_p": 0.9,
        "frequency_penalty": 0.0,
        "system_prompt": "당신은 도움이 되는 AI 어시스턴트입니다."
    },
    "rag": {
        "top_k": 3,
        "min_score": 0.5,
        "context_window": 3000,
        "chunk_size": 500,
        "chunk_overlap": 50,
        "embed_model": "intfloat/multilingual-e5-large-instruct"
    },
    "qdrant": {
        "host": "qdrant",
        "port": 6333,
        "collection": "chunks",
        "vector_dim": 1024,
        "distance": "Cosine",
        "index_threshold": 10000
    },
    "upload": {
        "max_file_size": 50,
        "max_zip_size": 100,
        "allowed_doc_exts": ["pdf", "txt", "docx", "doc"],
        "allowed_image_exts": ["png", "jpg", "jpeg"]
    }
}


def _find_settings_file() -> str:
    """사용 가능한 설정 파일 경로 찾기"""
    for path in SETTINGS_PATHS:
        if os.path.exists(path):
            logger.info(f"Found settings file: {path}")
            return path

    # 파일이 없으면 첫 번째 경로를 기본값으로 사용
    default_path = SETTINGS_PATHS[0]
    logger.info(f"No settings file found, will use: {default_path}")
    return default_path


def _load_settings() -> Dict[str, Any]:
    """
    설정 파일에서 설정을 로드합니다.

    Returns:
        설정 딕셔너리
    """
    settings_path = _find_settings_file()

    try:
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                user_settings = json.load(f)

            # 기본 설정과 병합
            merged_settings = deep_merge(_DEFAULTS.copy(), user_settings)
            logger.info(f"Settings loaded from {settings_path}: {len(merged_settings)} categories")
            return merged_settings
        else:
            logger.info(f"Settings file not found at {settings_path}, using defaults")
            return _DEFAULTS.copy()

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in settings file {settings_path}: {e}")
        logger.info("Using default settings due to JSON error")
        return _DEFAULTS.copy()

    except Exception as e:
        logger.error(f"Error loading settings from {settings_path}: {e}")
        logger.info("Using default settings due to loading error")
        return _DEFAULTS.copy()


def save_settings(new_settings: Dict[str, Any]) -> None:
    """
    설정을 파일에 저장합니다.

    Args:
        new_settings: 저장할 설정 딕셔너리
    """
    settings_path = SETTINGS_PATHS[0]  # 항상 첫 번째 경로에 저장

    try:
        # 디렉토리가 없으면 생성
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)

        # 기존 설정 로드
        current_settings = _load_settings()

        # 새 설정과 병합
        updated_settings = deep_merge(current_settings, new_settings)

        # 파일에 저장
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(updated_settings, f, indent=2, ensure_ascii=False)

        logger.info(f"Settings saved successfully to {settings_path}")
        logger.info(f"Updated categories: {list(new_settings.keys())}")

    except Exception as e:
        logger.error(f"Error saving settings to {settings_path}: {e}")
        raise


def get_default_keyword_methods() -> str:
    """설정에서 기본 키워드 추출 방식 가져오기"""
    try:
        dynamic = _load_settings()
        return dynamic.get("ontology", {}).get("keyword_method", "keybert")
    except:
        return "keybert"


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    두 딕셔너리를 재귀적으로 병합합니다.

    Args:
        base: 기본 딕셔너리
        override: 덮어쓸 딕셔너리

    Returns:
        병합된 딕셔너리
    """
    result = base.copy()

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            result[key] = deep_merge(base[key], value)
        else:
            result[key] = value

    return result


# ===============================
# 3. 디버깅 및 정보 조회 함수들
# ===============================

def get_settings_file_info() -> Dict[str, Any]:
    """설정 파일 정보 반환 (디버깅용)"""
    current_path = _find_settings_file()

    try:
        return {
            "settings_file_path": current_path,
            "file_exists": os.path.exists(current_path),
            "file_size": os.path.getsize(current_path) if os.path.exists(current_path) else 0,
            "file_mtime": os.path.getmtime(current_path) if os.path.exists(current_path) else None,
            "directory_exists": os.path.exists(os.path.dirname(current_path)),
            "directory_writable": os.access(os.path.dirname(current_path), os.W_OK) if os.path.exists(
                os.path.dirname(current_path)) else False,
            "all_searched_paths": SETTINGS_PATHS
        }
    except Exception as e:
        logger.error(f"Error getting settings file info: {e}")
        return {
            "settings_file_path": current_path,
            "error": str(e)
        }


def validate_settings_file() -> Dict[str, Any]:
    """설정 파일 유효성 검사"""
    info = get_settings_file_info()
    validation = {
        "valid": True,
        "issues": [],
        "file_info": info
    }

    if "error" in info:
        validation["issues"].append(f"파일 정보 조회 오류: {info['error']}")
        validation["valid"] = False
        return validation

    if not info["file_exists"]:
        validation["issues"].append("설정 파일이 존재하지 않습니다 (기본값 사용)")
        # 파일이 없어도 valid=True (기본값 사용 가능)

    if not info["directory_exists"]:
        validation["issues"].append("설정 디렉토리가 존재하지 않습니다")
        validation["valid"] = False

    if info["directory_exists"] and not info["directory_writable"]:
        validation["issues"].append("설정 디렉토리에 쓰기 권한이 없습니다")
        validation["valid"] = False

    if info["file_exists"]:
        try:
            with open(info["settings_file_path"], 'r', encoding='utf-8') as f:
                json.load(f)
        except json.JSONDecodeError:
            validation["issues"].append("설정 파일의 JSON 형식이 올바르지 않습니다")
            validation["valid"] = False
        except Exception as e:
            validation["issues"].append(f"설정 파일 읽기 오류: {str(e)}")
            validation["valid"] = False

    return validation


# ===============================
# 4. 편의 함수들 (기존 코드 호환성)
# ===============================

def get_ollama_host() -> str:
    """현재 Ollama 호스트 반환"""
    try:
        dynamic_settings = _load_settings()
        return dynamic_settings.get("ollama_host", settings.ollama_host)
    except:
        return settings.ollama_host


def get_ollama_model() -> str:
    """현재 Ollama 모델 반환"""
    try:
        dynamic_settings = _load_settings()
        return dynamic_settings.get("ollama_model", settings.ollama_model)
    except:
        return settings.ollama_model


# ===============================
# 5. 초기화 및 검증
# ===============================

# 모듈 로드 시 설정 시스템 초기화
try:
    # 설정 파일 존재 여부 및 유효성 검사
    validation_result = validate_settings_file()

    if validation_result["valid"]:
        logger.info("Settings system initialized successfully")
    else:
        logger.warning(f"Settings system has issues: {validation_result['issues']}")
        logger.info("Will use default settings")

    # 테스트 로딩
    test_settings = _load_settings()
    logger.info(f"Settings test load successful: {len(test_settings)} categories")

except Exception as e:
    logger.error(f"Settings system initialization failed: {e}")
    logger.info("Falling back to environment variables only")

# ===============================
# 6. 하위 호환성을 위한 별칭들
# ===============================

# 기존 코드가 기대하는 이름들
SETTINGS_FILE_PATH = SETTINGS_PATHS[0]  # 첫 번째 경로를 기본값으로


# 기존 함수명 별칭 (혹시 다른 곳에서 사용 중일 경우)
def _get_default_settings() -> Dict[str, Any]:
    """기본 설정 반환 (하위 호환성)"""
    return _DEFAULTS.copy()


# ===============================
# 7. Export (다른 모듈에서 import할 객체들)
# ===============================

__all__ = [
    'settings',  # 기존 Pydantic 스타일 설정 객체
    '_load_settings',  # 동적 설정 로딩 함수
    'save_settings',  # 설정 저장 함수
    'get_settings_file_info',  # 디버깅 함수
    'validate_settings_file',  # 검증 함수
    'get_ollama_host',  # 편의 함수
    'get_ollama_model',  # 편의 함수
    'SETTINGS_FILE_PATH'  # 설정 파일 경로
]