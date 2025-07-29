"""
API 응답 처리 통합 유틸리티
모든 API 호출을 일관되게 처리하고 사용자 친화적인 오류 메시지를 제공
"""
import streamlit as st
import time
import logging
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from functools import wraps
from dataclasses import dataclass
from enum import Enum

from frontend.ui.utils.client_manager import ClientManager
from frontend.ui.components.common import LoadingSpinner, ErrorDisplay


class APIErrorType(Enum):
    """API 오류 유형"""
    NETWORK_ERROR = "network"
    SERVER_ERROR = "server"
    VALIDATION_ERROR = "validation"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class APIResponse:
    """표준화된 API 응답"""
    success: bool
    data: Any = None
    error_type: Optional[APIErrorType] = None
    error_message: str = ""
    status_code: Optional[int] = None
    response_time: float = 0.0


class APICallConfig:
    """API 호출 설정"""
    def __init__(
        self,
        show_loading: bool = True,
        loading_message: str = "데이터를 불러오는 중...",
        cache_key: Optional[str] = None,
        cache_ttl: int = 300,  # 5분
        retry_count: int = 2,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
        validate_response: Optional[Callable] = None,
        error_messages: Optional[Dict[APIErrorType, str]] = None
    ):
        self.show_loading = show_loading
        self.loading_message = loading_message
        self.cache_key = cache_key
        self.cache_ttl = cache_ttl
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.validate_response = validate_response
        self.error_messages = error_messages or self._get_default_error_messages()

    def _get_default_error_messages(self) -> Dict[APIErrorType, str]:
        return {
            APIErrorType.NETWORK_ERROR: "네트워크 연결에 문제가 있습니다. 인터넷 연결을 확인해주세요.",
            APIErrorType.SERVER_ERROR: "서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
            APIErrorType.VALIDATION_ERROR: "요청 데이터가 올바르지 않습니다. 입력값을 확인해주세요.",
            APIErrorType.NOT_FOUND: "요청한 데이터를 찾을 수 없습니다.",
            APIErrorType.TIMEOUT: "요청 시간이 초과되었습니다. 네트워크 상태를 확인해주세요.",
            APIErrorType.UNKNOWN: "알 수 없는 오류가 발생했습니다. 관리자에게 문의해주세요."
        }


class APICacheManager:
    """API 응답 캐시 관리"""

    @staticmethod
    def get_cache_key(endpoint: str, params: Dict = None) -> str:
        """캐시 키 생성"""
        import hashlib
        cache_data = f"{endpoint}_{params or {}}"
        return f"api_cache_{hashlib.md5(cache_data.encode()).hexdigest()}"

    @staticmethod
    def get_cached_response(cache_key: str, ttl: int) -> Optional[Any]:
        """캐시된 응답 조회"""
        if cache_key not in st.session_state:
            return None

        cached_data = st.session_state[cache_key]
        if not isinstance(cached_data, dict):
            return None

        cache_time = cached_data.get('timestamp', 0)
        if time.time() - cache_time > ttl:
            del st.session_state[cache_key]
            return None

        return cached_data.get('data')

    @staticmethod
    def set_cached_response(cache_key: str, data: Any):
        """응답 캐시 저장"""
        st.session_state[cache_key] = {
            'data': data,
            'timestamp': time.time()
        }


class APIResponseProcessor:
    """API 응답 처리"""

    @staticmethod
    def classify_error(exception: Exception, status_code: Optional[int] = None) -> APIErrorType:
        """오류 유형 분류"""
        error_msg = str(exception).lower()

        if status_code:
            if status_code == 404:
                return APIErrorType.NOT_FOUND
            elif status_code >= 500:
                return APIErrorType.SERVER_ERROR
            elif status_code >= 400:
                return APIErrorType.VALIDATION_ERROR

        if any(keyword in error_msg for keyword in ['network', 'connection', 'dns']):
            return APIErrorType.NETWORK_ERROR
        elif any(keyword in error_msg for keyword in ['timeout', 'time out']):
            return APIErrorType.TIMEOUT
        elif any(keyword in error_msg for keyword in ['validation', 'invalid', 'bad request']):
            return APIErrorType.VALIDATION_ERROR
        else:
            return APIErrorType.UNKNOWN

    @staticmethod
    def normalize_response(response: Any) -> Any:
        """응답 정규화"""
        # 리스트인 경우 그대로 반환
        if isinstance(response, list):
            return response

        # 딕셔너리인 경우 데이터 추출
        if isinstance(response, dict):
            # 오류 응답 확인
            if response.get("error"):
                raise Exception(response["error"])

            # 일반적인 데이터 키들에서 추출 시도
            for key in ["data", "results", "items", "keywords", "documents"]:
                if key in response:
                    return response[key]

            # 키가 없으면 전체 딕셔너리 반환
            return response

        # 기타 타입은 그대로 반환
        return response

    @staticmethod
    def validate_response_structure(response: Any, expected_type: type = None) -> bool:
        """응답 구조 검증"""
        if expected_type:
            if not isinstance(response, expected_type):
                return False

        # 리스트인 경우 빈 리스트가 아닌지 확인
        if isinstance(response, list):
            return True  # 빈 리스트도 유효한 응답으로 처리

        # 딕셔너리인 경우 필수 필드 확인
        if isinstance(response, dict):
            return True  # 기본적으로 유효하다고 가정

        return response is not None


def api_call_handler(config: APICallConfig = None):
    """API 호출 데코레이터"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 설정 기본값 적용
            call_config = config or APICallConfig()

            # 캐시 확인
            if call_config.cache_key:
                cached_response = APICacheManager.get_cached_response(
                    call_config.cache_key,
                    call_config.cache_ttl
                )
                if cached_response is not None:
                    return APIResponse(success=True, data=cached_response)

            # 로딩 상태 표시
            loading_container = None
            if call_config.show_loading:
                loading_container = st.empty()
                with loading_container:
                    LoadingSpinner.render_inline_spinner(call_config.loading_message)

            # API 호출 시작 시간
            start_time = time.time()

            # 재시도 로직
            last_exception = None
            for attempt in range(call_config.retry_count + 1):
                try:
                    # 실제 API 호출
                    response = func(*args, **kwargs)

                    # 응답 정규화
                    normalized_response = APIResponseProcessor.normalize_response(response)

                    # 응답 검증
                    if call_config.validate_response:
                        if not call_config.validate_response(normalized_response):
                            raise Exception("응답 데이터 검증 실패")

                    # 응답 시간 계산
                    response_time = time.time() - start_time

                    # 캐시 저장
                    if call_config.cache_key:
                        APICacheManager.set_cached_response(call_config.cache_key, normalized_response)

                    # 로딩 제거
                    if loading_container:
                        loading_container.empty()

                    return APIResponse(
                        success=True,
                        data=normalized_response,
                        response_time=response_time
                    )

                except Exception as e:
                    last_exception = e
                    error_type = APIResponseProcessor.classify_error(e)

                    if attempt < call_config.retry_count:
                        # 재시도 대상 오류인지 확인
                        if error_type in [APIErrorType.NETWORK_ERROR, APIErrorType.TIMEOUT, APIErrorType.SERVER_ERROR]:
                            wait_time = call_config.retry_delay * (2 ** attempt)
                            time.sleep(wait_time)
                            continue

                    # 재시도 불가능하거나 최종 실패
                    break

            # 모든 재시도 실패
            response_time = time.time() - start_time
            error_type = APIResponseProcessor.classify_error(last_exception)

            # 로딩 제거
            if loading_container:
                loading_container.empty()

            # 오류 메시지 표시
            error_message = call_config.error_messages.get(error_type, str(last_exception))
            ErrorDisplay.render_error_with_suggestions(
                error_message,
                suggestions=_get_error_suggestions(error_type),
                error_type="error"
            )

            return APIResponse(
                success=False,
                error_type=error_type,
                error_message=error_message,
                response_time=response_time
            )

        return wrapper
    return decorator


def _get_error_suggestions(error_type: APIErrorType) -> List[str]:
    """오류 타입별 해결 제안"""
    suggestions_map = {
        APIErrorType.NETWORK_ERROR: [
            "인터넷 연결 상태를 확인하세요",
            "VPN 또는 프록시 설정을 확인하세요",
            "방화벽이 연결을 차단하지 않는지 확인하세요"
        ],
        APIErrorType.SERVER_ERROR: [
            "잠시 후 다시 시도해보세요",
            "백엔드 서버 상태를 확인하세요",
            "로그에서 자세한 오류 정보를 확인하세요"
        ],
        APIErrorType.VALIDATION_ERROR: [
            "입력 데이터를 다시 확인해보세요",
            "필수 필드가 누락되지 않았는지 확인하세요",
            "데이터 형식이 올바른지 확인하세요"
        ],
        APIErrorType.NOT_FOUND: [
            "요청한 리소스가 존재하는지 확인하세요",
            "API 엔드포인트 경로를 확인하세요",
            "필요한 데이터가 먼저 생성되었는지 확인하세요"
        ],
        APIErrorType.TIMEOUT: [
            "네트워크 연결 속도를 확인하세요",
            "요청 크기를 줄여보세요",
            "타임아웃 설정을 늘려보세요"
        ]
    }
    return suggestions_map.get(error_type, ["관리자에게 문의하세요"])


class OntologyAPIManager:
    """온톨로지 API 전용 관리자"""

    def __init__(self):
        self.client = ClientManager.get_client()
        self.base_config = APICallConfig(
            show_loading=True,
            retry_count=2,
            timeout=30.0
        )

    def get_ontology_statistics(self) -> APIResponse:
        """온톨로지 통계 조회"""
        config = APICallConfig(
            loading_message="통계를 불러오는 중...",
            cache_key="ontology_stats",
            cache_ttl=180,  # 3분 캐시
            validate_response=lambda data: isinstance(data, dict)
        )

        @api_call_handler(config)
        def _get_stats():
            return self.client.request("GET", "/v1/ontology/statistics")

        return _get_stats()

    def search_by_keyword(self, keyword: str, limit: int = 10, min_score: float = 0.7) -> APIResponse:
        """키워드 검색"""
        if not keyword.strip():
            return APIResponse(
                success=False,
                error_type=APIErrorType.VALIDATION_ERROR,
                error_message="검색어를 입력해주세요"
            )

        config = APICallConfig(
            loading_message=f"'{keyword}' 검색 중...",
            validate_response=lambda data: isinstance(data, list)
        )

        @api_call_handler(config)
        def _search():
            payload = {
                "keyword": keyword,
                "limit": limit,
                "min_score": min_score
            }
            return self.client.request("POST", "/v1/ontology/search/keywords", json=payload)

        return _search()

    def search_by_domain(self, domain: str, limit: int = 20) -> APIResponse:
        """도메인별 검색"""
        config = APICallConfig(
            loading_message=f"{domain} 도메인 문서 검색 중...",
            validate_response=lambda data: isinstance(data, list)
        )

        @api_call_handler(config)
        def _search():
            payload = {
                "domain": domain,
                "limit": limit
            }
            return self.client.request("POST", "/v1/ontology/search/domain", json=payload)

        return _search()

    def get_top_keywords(self, limit: int = 50, category: str = None, domain: str = None) -> APIResponse:
        """상위 키워드 조회"""
        config = APICallConfig(
            loading_message="인기 키워드를 불러오는 중...",
            cache_key=f"top_keywords_{limit}_{category}_{domain}",
            cache_ttl=300,  # 5분 캐시
            validate_response=lambda data: isinstance(data, list)
        )

        @api_call_handler(config)
        def _get_keywords():
            payload = {
                "limit": limit,
                "min_doc_count": 1,
                "sort_by": "document_count"
            }
            if category:
                payload["category"] = category
            if domain:
                payload["domain"] = domain

            return self.client.request("POST", "/v1/ontology/keywords/top", json=payload)

        return _get_keywords()

    def get_document_ontology(self, doc_id: str) -> APIResponse:
        """문서별 온톨로지 조회"""
        config = APICallConfig(
            loading_message="문서 온톨로지를 불러오는 중...",
            cache_key=f"doc_ontology_{doc_id}",
            cache_ttl=600,  # 10분 캐시
            validate_response=lambda data: isinstance(data, dict) and 'doc_id' in data
        )

        @api_call_handler(config)
        def _get_ontology():
            return self.client.request("GET", f"/v1/ontology/{doc_id}")

        return _get_ontology()

    def get_similar_documents(self, doc_id: str, limit: int = 5, min_similarity: float = 0.6) -> APIResponse:
        """유사 문서 검색"""
        config = APICallConfig(
            loading_message="유사 문서를 찾는 중...",
            validate_response=lambda data: isinstance(data, list)
        )

        @api_call_handler(config)
        def _get_similar():
            payload = {
                "doc_id": doc_id,
                "limit": limit,
                "min_similarity": min_similarity
            }
            return self.client.request("POST", "/v1/ontology/search/similar", json=payload)

        return _get_similar()


def safe_api_call(func: Callable, error_message: str = "API 호출 중 오류가 발생했습니다") -> Tuple[bool, Any]:
    """
    안전한 API 호출 래퍼

    Returns:
        (성공여부, 데이터 또는 오류메시지)
    """
    try:
        result = func()
        if isinstance(result, APIResponse) and result.success:
            return True, result.data
        elif isinstance(result, APIResponse):
            return False, result.error_message
        else:
            return True, result
    except Exception as e:
        st.error(f"{error_message}: {str(e)}")
        return False, str(e)


def display_api_response(response: APIResponse, success_message: str = None) -> bool:
    """
    API 응답을 사용자에게 표시

    Returns:
        성공 여부
    """
    if response.success:
        if success_message:
            st.success(success_message)
        return True
    else:
        ErrorDisplay.render_error_with_suggestions(
            response.error_message,
            error_type="error",
            suggestions=_get_error_suggestions(response.error_type)
        )
        return False


# 편의 함수들
def create_loading_config(message: str, cache_key: str = None, cache_ttl: int = 300) -> APICallConfig:
    """로딩 설정 생성"""
    return APICallConfig(
        loading_message=message,
        cache_key=cache_key,
        cache_ttl=cache_ttl
    )


def create_validation_config(validator: Callable, error_message: str = "응답 데이터가 유효하지 않습니다") -> APICallConfig:
    """검증 설정 생성"""
    return APICallConfig(
        validate_response=validator,
        error_messages={APIErrorType.VALIDATION_ERROR: error_message}
    )