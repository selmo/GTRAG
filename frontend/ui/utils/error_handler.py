"""
통합 에러 처리 시스템
frontend/ui/utils/error_handler.py
"""
import streamlit as st
import logging
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime
import traceback


class ErrorType(Enum):
    """에러 타입 분류"""
    API_CONNECTION = "api_connection"
    API_TIMEOUT = "api_timeout"
    API_RESPONSE = "api_response"
    FILE_UPLOAD = "file_upload"
    FILE_VALIDATION = "file_validation"
    MODEL_CONFIG = "model_config"
    SYSTEM_HEALTH = "system_health"
    VALIDATION = "validation"
    PERMISSION = "permission"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """에러 심각도"""
    LOW = "low"  # 정보성, 계속 진행 가능
    MEDIUM = "medium"  # 경고, 일부 기능 제한
    HIGH = "high"  # 오류, 주요 기능 중단
    CRITICAL = "critical"  # 치명적, 시스템 사용 불가


class GTRagError(Exception):
    """GTOne RAG 시스템 커스텀 예외"""

    def __init__(self, message: str, error_type: ErrorType = ErrorType.UNKNOWN,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 suggestions: List[str] = None, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.severity = severity
        self.suggestions = suggestions or []
        self.details = details or {}
        self.timestamp = datetime.now()


class ErrorHandler:
    """통합 에러 처리 클래스"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._error_history = []

    def handle_error(self, error: Exception, context: str = None,
                     show_traceback: bool = False) -> None:
        """에러 처리 및 사용자 표시"""

        # 에러 분류 및 분석
        error_info = self._analyze_error(error, context)

        # 로깅
        self._log_error(error_info, show_traceback)

        # 사용자에게 표시
        self._display_error_to_user(error_info)

        # 에러 히스토리에 추가
        self._add_to_history(error_info)

    def _analyze_error(self, error: Exception, context: str = None) -> Dict[str, Any]:
        """에러 분석 및 분류"""

        if isinstance(error, GTRagError):
            return {
                "type": error.error_type,
                "severity": error.severity,
                "message": error.message,
                "suggestions": error.suggestions,
                "details": error.details,
                "context": context,
                "timestamp": error.timestamp,
                "original_error": error
            }

        # 일반 예외 분석
        error_type, severity, suggestions = self._classify_standard_error(error)

        return {
            "type": error_type,
            "severity": severity,
            "message": str(error),
            "suggestions": suggestions,
            "details": {"exception_type": type(error).__name__},
            "context": context,
            "timestamp": datetime.now(),
            "original_error": error
        }

    def _classify_standard_error(self, error: Exception) -> Tuple[ErrorType, ErrorSeverity, List[str]]:
        """표준 예외 분류"""
        error_str = str(error).lower()

        # 연결 오류
        if "connection" in error_str or "connectionerror" in str(type(error)):
            return ErrorType.API_CONNECTION, ErrorSeverity.HIGH, [
                "네트워크 연결을 확인하세요",
                "API 서버가 실행 중인지 확인하세요",
                "방화벽 설정을 확인하세요"
            ]

        # 타임아웃 오류
        if "timeout" in error_str:
            return ErrorType.API_TIMEOUT, ErrorSeverity.MEDIUM, [
                "요청 시간을 늘려보세요",
                "더 간단한 질문을 시도해보세요",
                "서버 상태를 확인하세요"
            ]

        # 파일 관련 오류
        if "file" in error_str or "upload" in error_str:
            return ErrorType.FILE_UPLOAD, ErrorSeverity.MEDIUM, [
                "파일 크기를 확인하세요 (50MB 이하)",
                "지원되는 파일 형식인지 확인하세요",
                "파일이 손상되지 않았는지 확인하세요"
            ]

        # 모델 관련 오류
        if "model" in error_str or "ollama" in error_str:
            return ErrorType.MODEL_CONFIG, ErrorSeverity.HIGH, [
                "모델이 올바르게 설치되었는지 확인하세요",
                "Ollama 서버가 실행 중인지 확인하세요",
                "설정 페이지에서 모델을 다시 선택하세요"
            ]

        # 권한 오류
        if "permission" in error_str or "forbidden" in error_str:
            return ErrorType.PERMISSION, ErrorSeverity.HIGH, [
                "관리자 권한이 필요할 수 있습니다",
                "API 키나 인증 정보를 확인하세요"
            ]

        # 검증 오류
        if "validation" in error_str or "invalid" in error_str:
            return ErrorType.VALIDATION, ErrorSeverity.LOW, [
                "입력값을 다시 확인하세요",
                "필수 필드가 모두 입력되었는지 확인하세요"
            ]

        return ErrorType.UNKNOWN, ErrorSeverity.MEDIUM, [
            "페이지를 새로고침해보세요",
            "문제가 지속되면 지원팀에 문의하세요"
        ]

    def _log_error(self, error_info: Dict[str, Any], show_traceback: bool = False):
        """에러 로깅"""
        severity = error_info["severity"]
        message = f"[{error_info['type'].value.upper()}] {error_info['message']}"

        if error_info["context"]:
            message += f" (Context: {error_info['context']})"

        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(message)
        elif severity == ErrorSeverity.HIGH:
            self.logger.error(message)
        elif severity == ErrorSeverity.MEDIUM:
            self.logger.warning(message)
        else:
            self.logger.info(message)

        if show_traceback and error_info["original_error"]:
            self.logger.error(traceback.format_exc())

    def _display_error_to_user(self, error_info: Dict[str, Any]):
        """사용자에게 에러 표시"""
        severity = error_info["severity"]
        message = error_info["message"]
        suggestions = error_info["suggestions"]

        # 심각도에 따른 표시 방식
        if severity == ErrorSeverity.CRITICAL:
            st.error(f"🚨 치명적 오류: {message}")
            st.error("시스템을 사용할 수 없습니다. 관리자에게 문의하세요.")
        elif severity == ErrorSeverity.HIGH:
            st.error(f"❌ 오류: {message}")
        elif severity == ErrorSeverity.MEDIUM:
            st.warning(f"⚠️ 경고: {message}")
        else:
            st.info(f"ℹ️ 알림: {message}")

        # 해결 방안 표시
        if suggestions:
            with st.expander("💡 해결 방안", expanded=(severity.value in ["high", "critical"])):
                for i, suggestion in enumerate(suggestions, 1):
                    st.write(f"{i}. {suggestion}")

        # 추가 세부 정보 (개발 모드에서만)
        if self._is_debug_mode() and error_info["details"]:
            with st.expander("🔧 기술 세부 정보"):
                st.json(error_info["details"])

    def _add_to_history(self, error_info: Dict[str, Any]):
        """에러 히스토리에 추가"""
        self._error_history.append(error_info)

        # 최대 100개까지만 유지
        if len(self._error_history) > 100:
            self._error_history = self._error_history[-100:]

    def _is_debug_mode(self) -> bool:
        """디버그 모드 확인"""
        try:
            from frontend.ui.core.config import config
            return config.is_development()
        except:
            return False

    def get_error_stats(self) -> Dict[str, Any]:
        """에러 통계 반환"""
        if not self._error_history:
            return {"total": 0, "by_type": {}, "by_severity": {}}

        by_type = {}
        by_severity = {}

        for error in self._error_history:
            error_type = error["type"].value
            severity = error["severity"].value

            by_type[error_type] = by_type.get(error_type, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            "total": len(self._error_history),
            "by_type": by_type,
            "by_severity": by_severity,
            "recent_errors": self._error_history[-5:]  # 최근 5개
        }

    def clear_history(self):
        """에러 히스토리 초기화"""
        self._error_history.clear()


# 전역 에러 핸들러 인스턴스
error_handler = ErrorHandler()


# 편의 함수들
def handle_api_error(error, context: str = None):
    """API 에러 처리"""
    # 문자열이 전달된 경우 Exception 객체로 변환
    if isinstance(error, str):
        error_msg = error
    else:
        error_msg = str(error)

    if "timeout" in error_msg.lower():
        raise GTRagError(
            "API 요청 시간이 초과되었습니다",
            ErrorType.API_TIMEOUT,
            ErrorSeverity.MEDIUM,
            ["타임아웃 설정을 늘려보세요", "더 간단한 요청을 시도해보세요"]
        )
    elif "connection" in error_msg.lower():
        raise GTRagError(
            "API 서버에 연결할 수 없습니다",
            ErrorType.API_CONNECTION,
            ErrorSeverity.HIGH,
            ["서버가 실행 중인지 확인하세요", "네트워크 연결을 확인하세요"]
        )
    else:
        raise GTRagError(
            f"API 오류: {error_msg}",
            ErrorType.API_RESPONSE,
            ErrorSeverity.MEDIUM,
            ["잠시 후 다시 시도해보세요"]
        )


def handle_file_error(error: Exception, filename: str = None):
    """파일 처리 에러"""
    context = f"파일: {filename}" if filename else None

    if "size" in str(error).lower():
        raise GTRagError(
            "파일 크기가 제한을 초과했습니다",
            ErrorType.FILE_VALIDATION,
            ErrorSeverity.LOW,
            ["50MB 이하의 파일을 사용하세요", "파일을 분할하여 업로드하세요"],
            {"filename": filename}
        )
    elif "format" in str(error).lower() or "extension" in str(error).lower():
        raise GTRagError(
            "지원하지 않는 파일 형식입니다",
            ErrorType.FILE_VALIDATION,
            ErrorSeverity.LOW,
            ["PDF, Word, 텍스트, 이미지 파일을 사용하세요"],
            {"filename": filename}
        )
    else:
        raise GTRagError(
            f"파일 처리 오류: {str(error)}",
            ErrorType.FILE_UPLOAD,
            ErrorSeverity.MEDIUM,
            ["파일이 손상되지 않았는지 확인하세요"],
            {"filename": filename}
        )


def handle_model_error(error: Exception, model_name: str = None):
    """모델 관련 에러"""
    context = f"모델: {model_name}" if model_name else None

    raise GTRagError(
        f"모델 오류: {str(error)}",
        ErrorType.MODEL_CONFIG,
        ErrorSeverity.HIGH,
        [
            "설정 페이지에서 모델을 다시 선택하세요",
            "Ollama 서버 상태를 확인하세요",
            "모델이 올바르게 설치되었는지 확인하세요"
        ],
        {"model": model_name}
    )


def handle_validation_error(error: Exception, field_name: str = None):
    """검증 에러"""
    context = f"필드: {field_name}" if field_name else None

    raise GTRagError(
        f"입력값 오류: {str(error)}",
        ErrorType.VALIDATION,
        ErrorSeverity.LOW,
        ["입력값을 다시 확인하세요", "필수 필드를 모두 입력하세요"],
        {"field": field_name}
    )


# 데코레이터
def error_boundary(error_type: ErrorType = ErrorType.UNKNOWN,
                   context: str = None, show_traceback: bool = False):
    """에러 경계 데코레이터"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except GTRagError:
                # 이미 처리된 에러는 다시 발생
                raise
            except Exception as e:
                # 일반 예외를 GTRagError로 변환
                error_handler.handle_error(e, context, show_traceback)
                return None

        return wrapper

    return decorator


# 컨텍스트 매니저
class ErrorContext:
    """에러 컨텍스트 관리"""

    def __init__(self, context_name: str, show_errors: bool = True):
        self.context_name = context_name
        self.show_errors = show_errors
        self.errors = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and self.show_errors:
            error_handler.handle_error(exc_val, self.context_name)
        return False  # 예외를 다시 발생시킴

    def add_error(self, error: Exception):
        """에러 추가"""
        self.errors.append(error)

    def has_errors(self) -> bool:
        """에러 존재 여부"""
        return len(self.errors) > 0

    def show_all_errors(self):
        """모든 에러 표시"""
        for error in self.errors:
            error_handler.handle_error(error, self.context_name)


# 사용 예시
def example_usage():
    """사용 예시"""

    # 1. 데코레이터 사용
    @error_boundary(ErrorType.API_CONNECTION, "파일 업로드")
    def upload_file(file):
        # 파일 업로드 로직
        pass

    # 2. 컨텍스트 매니저 사용
    with ErrorContext("모델 설정"):
        # 모델 설정 로직
        pass

    # 3. 직접 에러 발생
    try:
        # 어떤 작업
        pass
    except Exception as e:
        handle_api_error(e, "RAG 답변 생성")

    # 4. 커스텀 에러 발생
    raise GTRagError(
        "사용자 정의 오류",
        ErrorType.VALIDATION,
        ErrorSeverity.LOW,
        ["해결 방안 1", "해결 방안 2"]
    )