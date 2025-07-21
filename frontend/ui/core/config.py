"""
설정 및 상수 중앙화
frontend/ui/core/config.py
"""
import os
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class Environment(Enum):
    """환경 설정"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class APIConfig:
    """API 설정"""
    base_url: str = "http://localhost:18000"
    timeout: int = 300
    max_retries: int = 3
    health_check_interval: int = 30


@dataclass
class FileConfig:
    """파일 설정"""
    max_file_size_mb: int = 50
    max_archive_size_mb: int = 100
    allowed_extensions: List[str] = None
    allowed_archive_extensions: List[str] = None
    upload_timeout: int = 180

    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = [
                'pdf', 'txt', 'png', 'jpg', 'jpeg', 'docx', 'doc',
                'gif', 'bmp', 'tiff', 'md', 'rtf'
            ]

        if self.allowed_archive_extensions is None:
            self.allowed_archive_extensions = ['zip', 'rar', '7z', 'tar']


@dataclass
class UIConfig:
    """UI 설정"""
    page_title: str = "GTOne RAG System"
    page_icon: str = "📚"
    layout: str = "wide"
    initial_sidebar_state: str = "expanded"
    theme: str = "light"

    # 페이지네이션
    default_page_size: int = 10
    max_page_size: int = 100

    # 표시 설정
    max_search_results: int = 20
    max_chat_history: int = 100
    max_file_preview_length: int = 300


@dataclass
class CacheConfig:
    """캐시 설정"""
    system_health_ttl: int = 30  # 초
    model_list_ttl: int = 300  # 초
    search_results_ttl: int = 60  # 초
    file_list_ttl: int = 120  # 초


class SystemConfig:
    """시스템 설정 통합 클래스"""

    def __init__(self):
        self.environment = Environment(os.getenv("ENVIRONMENT", "development"))

        # 환경별 설정 로드
        self.api = self._load_api_config()
        self.file = self._load_file_config()
        self.ui = self._load_ui_config()
        self.cache = self._load_cache_config()

    def _load_api_config(self) -> APIConfig:
        """API 설정 로드"""
        return APIConfig(
            base_url=os.getenv("API_BASE_URL", "http://localhost:18000"),
            timeout=int(os.getenv("API_TIMEOUT", "300")),
            max_retries=int(os.getenv("API_MAX_RETRIES", "3")),
            health_check_interval=int(os.getenv("HEALTH_CHECK_INTERVAL", "30"))
        )

    def _load_file_config(self) -> FileConfig:
        """파일 설정 로드"""
        return FileConfig(
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "50")),
            max_archive_size_mb=int(os.getenv("MAX_ARCHIVE_SIZE_MB", "100")),
            upload_timeout=int(os.getenv("UPLOAD_TIMEOUT", "180"))
        )

    def _load_ui_config(self) -> UIConfig:
        """UI 설정 로드"""
        return UIConfig(
            theme=os.getenv("UI_THEME", "light"),
            default_page_size=int(os.getenv("DEFAULT_PAGE_SIZE", "10")),
            max_search_results=int(os.getenv("MAX_SEARCH_RESULTS", "20"))
        )

    def _load_cache_config(self) -> CacheConfig:
        """캐시 설정 로드"""
        return CacheConfig(
            system_health_ttl=int(os.getenv("CACHE_HEALTH_TTL", "30")),
            model_list_ttl=int(os.getenv("CACHE_MODEL_TTL", "300")),
            search_results_ttl=int(os.getenv("CACHE_SEARCH_TTL", "60"))
        )

    def is_development(self) -> bool:
        """개발 환경 여부"""
        return self.environment == Environment.DEVELOPMENT

    def is_production(self) -> bool:
        """프로덕션 환경 여부"""
        return self.environment == Environment.PRODUCTION


# 전역 설정 인스턴스
config = SystemConfig()


# 상수 정의
class Constants:
    """시스템 상수"""

    # 아이콘
    class Icons:
        DOCUMENT = "📄"
        SEARCH = "🔍"
        AI = "🤖"
        UPLOAD = "📤"
        DOWNLOAD = "📥"
        DELETE = "🗑️"
        SETTINGS = "⚙️"
        STATUS_OK = "✅"
        STATUS_WARNING = "⚠️"
        STATUS_ERROR = "❌"
        STATUS_INFO = "ℹ️"
        LOADING = "⏳"
        REFRESH = "🔄"

        # 파일 타입별 아이콘
        FILE_ICONS = {
            'pdf': '📄',
            'doc': '📝', 'docx': '📝',
            'txt': '📃', 'md': '📃',
            'png': '🖼️', 'jpg': '🖼️', 'jpeg': '🖼️', 'gif': '🖼️',
            'zip': '📦', 'rar': '📦', '7z': '📦',
            'xlsx': '📊', 'csv': '📊',
            'default': '📎'
        }

    # URL 및 경로
    class URLs:
        DOCS = "http://localhost:18000/docs"
        QDRANT_UI = "http://localhost:6333/dashboard"
        GITHUB = "https://github.com/your-org/gtrag"
        SUPPORT_EMAIL = "support@gtone.com"

    # API 엔드포인트
    class Endpoints:
        HEALTH = "/v1/health"
        DOCUMENTS = "/v1/documents"
        SEARCH = "/v1/search"
        RAG_ANSWER = "/v1/rag/answer"
        MODELS = "/v1/models"
        SETTINGS = "/v1/settings"

    # 상태 코드 및 메시지
    class Status:
        HEALTHY = "healthy"
        DEGRADED = "degraded"
        UNHEALTHY = "unhealthy"
        ERROR = "error"
        INITIALIZING = "initializing"

        CONNECTED = "connected"
        DISCONNECTED = "disconnected"
        UNKNOWN = "unknown"

    # 기본값
    class Defaults:
        TEMPERATURE = 0.3
        MAX_TOKENS = 1000
        TOP_K = 3
        MIN_SIMILARITY = 0.5
        CHUNK_SIZE = 500
        CHUNK_OVERLAP = 50
        CONTEXT_WINDOW = 3000

        SYSTEM_PROMPT = "당신은 문서 기반 질의응답 시스템입니다. 제공된 문서의 내용만을 바탕으로 정확하고 도움이 되는 답변을 제공하세요."

        EMBEDDING_MODEL = "intfloat/multilingual-e5-large-instruct"
        SEARCH_TYPE = "hybrid"

    # 제한값
    class Limits:
        MIN_TEMPERATURE = 0.0
        MAX_TEMPERATURE = 2.0
        MIN_TOP_K = 1
        MAX_TOP_K = 50
        MIN_TOKENS = 100
        MAX_TOKENS = 8000
        MIN_SIMILARITY = 0.0
        MAX_SIMILARITY = 1.0

    # 색상 테마
    class Colors:
        PRIMARY = "#ff6b6b"
        SUCCESS = "#28a745"
        WARNING = "#ffc107"
        ERROR = "#dc3545"
        INFO = "#17a2b8"

        # 유사도 점수별 색상
        SIMILARITY_HIGH = "#28a745"  # 0.8+
        SIMILARITY_MEDIUM = "#ffc107"  # 0.6-0.8
        SIMILARITY_LOW = "#fd7e14"  # 0.4-0.6
        SIMILARITY_POOR = "#dc3545"  # 0.4 미만


# 설정 검증 함수
def validate_config():
    """설정 유효성 검사"""
    errors = []

    # API 설정 검증
    if config.api.timeout < 30:
        errors.append("API 타임아웃이 너무 짧습니다 (최소 30초)")

    # 파일 설정 검증
    if config.file.max_file_size_mb <= 0:
        errors.append("최대 파일 크기는 0보다 커야 합니다")

    if config.file.max_archive_size_mb <= config.file.max_file_size_mb:
        errors.append("압축 파일 최대 크기는 일반 파일보다 커야 합니다")

    # UI 설정 검증
    if config.ui.default_page_size <= 0:
        errors.append("기본 페이지 크기는 0보다 커야 합니다")

    return errors


# 설정 내보내기/가져오기
def export_config() -> Dict[str, Any]:
    """현재 설정을 딕셔너리로 내보내기"""
    return {
        "environment": config.environment.value,
        "api": {
            "base_url": config.api.base_url,
            "timeout": config.api.timeout,
            "max_retries": config.api.max_retries,
            "health_check_interval": config.api.health_check_interval
        },
        "file": {
            "max_file_size_mb": config.file.max_file_size_mb,
            "max_archive_size_mb": config.file.max_archive_size_mb,
            "allowed_extensions": config.file.allowed_extensions,
            "upload_timeout": config.file.upload_timeout
        },
        "ui": {
            "theme": config.ui.theme,
            "default_page_size": config.ui.default_page_size,
            "max_search_results": config.ui.max_search_results
        },
        "cache": {
            "system_health_ttl": config.cache.system_health_ttl,
            "model_list_ttl": config.cache.model_list_ttl,
            "search_results_ttl": config.cache.search_results_ttl
        }
    }


def import_config(config_data: Dict[str, Any]) -> bool:
    """설정 딕셔너리에서 설정 가져오기"""
    try:
        # 환경 변수 업데이트 (재시작 필요)
        if "api" in config_data:
            api_config = config_data["api"]
            os.environ["API_BASE_URL"] = api_config.get("base_url", config.api.base_url)
            os.environ["API_TIMEOUT"] = str(api_config.get("timeout", config.api.timeout))

        if "file" in config_data:
            file_config = config_data["file"]
            os.environ["MAX_FILE_SIZE_MB"] = str(file_config.get("max_file_size_mb", config.file.max_file_size_mb))
            os.environ["MAX_ARCHIVE_SIZE_MB"] = str(
                file_config.get("max_archive_size_mb", config.file.max_archive_size_mb))

        # UI 설정은 즉시 적용 가능
        if "ui" in config_data:
            ui_config = config_data["ui"]
            config.ui.theme = ui_config.get("theme", config.ui.theme)
            config.ui.default_page_size = ui_config.get("default_page_size", config.ui.default_page_size)

        return True
    except Exception as e:
        print(f"설정 가져오기 실패: {e}")
        return False


# 편의 함수들
def get_file_icon(filename: str) -> str:
    """파일 아이콘 반환"""
    if not filename or '.' not in filename:
        return Constants.Icons.FILE_ICONS['default']

    ext = filename.lower().split('.')[-1]
    return Constants.Icons.FILE_ICONS.get(ext, Constants.Icons.FILE_ICONS['default'])


def get_similarity_color(score: float) -> str:
    """유사도 점수에 따른 색상 반환"""
    if score >= 0.8:
        return Constants.Colors.SIMILARITY_HIGH
    elif score >= 0.6:
        return Constants.Colors.SIMILARITY_MEDIUM
    elif score >= 0.4:
        return Constants.Colors.SIMILARITY_LOW
    else:
        return Constants.Colors.SIMILARITY_POOR


def get_status_color(status: str) -> str:
    """상태에 따른 색상 반환"""
    status_colors = {
        Constants.Status.HEALTHY: Constants.Colors.SUCCESS,
        Constants.Status.CONNECTED: Constants.Colors.SUCCESS,
        Constants.Status.DEGRADED: Constants.Colors.WARNING,
        Constants.Status.UNHEALTHY: Constants.Colors.ERROR,
        Constants.Status.DISCONNECTED: Constants.Colors.ERROR,
        Constants.Status.ERROR: Constants.Colors.ERROR,
        Constants.Status.INITIALIZING: Constants.Colors.INFO,
        Constants.Status.UNKNOWN: Constants.Colors.INFO
    }
    return status_colors.get(status, Constants.Colors.INFO)


def is_valid_file_extension(filename: str) -> bool:
    """파일 확장자 유효성 검사"""
    if not filename or '.' not in filename:
        return False

    ext = filename.lower().split('.')[-1]
    all_extensions = config.file.allowed_extensions + config.file.allowed_archive_extensions
    return ext in all_extensions


def get_max_file_size(is_archive: bool = False) -> int:
    """최대 파일 크기 반환 (MB)"""
    return config.file.max_archive_size_mb if is_archive else config.file.max_file_size_mb


# 환경별 설정 오버라이드
if config.is_development():
    # 개발 환경에서는 더 관대한 설정
    config.api.timeout = max(config.api.timeout, 60)
    config.cache.system_health_ttl = min(config.cache.system_health_ttl, 10)

elif config.is_production():
    # 프로덕션 환경에서는 더 엄격한 설정
    config.file.max_file_size_mb = min(config.file.max_file_size_mb, 20)
    config.ui.max_search_results = min(config.ui.max_search_results, 10)