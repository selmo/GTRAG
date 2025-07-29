"""
API 클라이언트 유틸리티 - 개선된 버전
- 설정 중앙화 적용
- 에러 처리 표준화
- 로깅 시스템 통합
- 재시도 로직 추가
"""
import requests
import os
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
import json
import logging
import time
import re
from functools import wraps

# 통일된 import 경로
from frontend.ui.core.config import config, Constants

# 조건부 import (표준 패턴)
try:
    from frontend.ui.utils.error_handler import (
        ErrorContext, GTRagError, ErrorType, ErrorSeverity,
        handle_api_error, handle_file_error
    )
    HAS_ERROR_HANDLER = True
except ImportError:
    ErrorContext = None
    GTRagError = None
    ErrorType = None
    ErrorSeverity = None
    HAS_ERROR_HANDLER = False

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,          # 이미 설정돼 있어도 덮어쓰게끔 (Python 3.8+)
)
logger = logging.getLogger(__name__)


def retry_on_failure(max_retries: int = None, delay: float = 1.0, backoff: float = 2.0):
    """API 호출 재시도 데코레이터"""
    if max_retries is None:
        max_retries = config.api.max_retries

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout) as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries + 1}), "
                                     f"retrying in {wait_time:.1f}s: {str(e)}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"API call failed after {max_retries + 1} attempts: {str(e)}")
                except Exception as e:
                    # 재시도하지 않는 예외들
                    logger.error(f"API call failed with non-retryable error: {str(e)}")
                    raise

            # 모든 재시도 실패
            if HAS_ERROR_HANDLER:
                handle_api_error(last_exception, "API 호출 재시도 실패")
            raise last_exception

        return wrapper
    return decorator


# ===============================
# 수정된 APIClient 클래스의 설정 관련 메서드들
# ===============================

class APIClient:
    """GTOne RAG System API 클라이언트 - 수정된 버전"""

    def __init__(self, base_url: str = None, timeout: int = None):
        # 기존 초기화 코드 유지...
        self.base_url = base_url or config.api.base_url
        self.timeout = timeout or config.api.timeout
        self.max_retries = config.api.max_retries
        self.session = requests.Session()

        # 기본 헤더 설정
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"GTOne-RAG-Client/1.0.0"
        })

        logger.info(f"API Client initialized with base URL: {self.base_url}")

    # ===============================
    # 설정 관련 메서드 (통합 및 수정)
    # ===============================

    @retry_on_failure()
    def get_settings(self) -> Dict:
        """
        백엔드에 저장된 시스템 설정을 조회

        Returns:
            설정 딕셔너리
        """
        try:
            response = self._make_request("GET", Constants.Endpoints.SETTINGS)
            settings = response.json() or {}
            logger.info(f"Settings retrieved successfully ({len(settings)} keys)")
            return settings

        except Exception as e:
            logger.error(f"Settings retrieval failed: {e}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "설정 조회")
            # 실패 시 기본값 반환
            return {
                "ollama_host": "http://localhost:11434",
                "ollama_model": "qwen3:30b"  # 기본값
            }

    @retry_on_failure()
    def update_settings(self, settings: Dict[str, Any]) -> Dict:
        """
        시스템 설정 업데이트 (통합된 메서드)

        Args:
            settings: 업데이트할 설정 딕셔너리

        Returns:
            업데이트 결과
        """
        try:
            # 요청 데이터 검증
            if not isinstance(settings, dict):
                raise ValueError("설정은 딕셔너리 형태여야 합니다")

            # 빈 값 필터링
            filtered_settings = {k: v for k, v in settings.items() if v is not None}

            logger.info(f"Updating settings: {list(filtered_settings.keys())}")

            response = self._make_request(
                "PUT",
                Constants.Endpoints.SETTINGS,
                json=filtered_settings,
                timeout=10  # 설정 저장은 빠르게 처리되어야 함
            )

            result = response.json()
            logger.info("Settings updated successfully")
            return result

        except requests.exceptions.HTTPError as e:
            # HTTP 오류 상세 처리
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    logger.error(f"Settings update HTTP error: {e.response.status_code} - {error_detail}")
                    return {
                        "status": "error",
                        "message": f"HTTP {e.response.status_code}: {error_detail.get('detail', str(e))}",
                        "error_code": e.response.status_code
                    }
                except:
                    logger.error(f"Settings update HTTP error: {e.response.status_code} - {e.response.text}")
                    return {
                        "status": "error",
                        "message": f"HTTP {e.response.status_code}: {e.response.text}",
                        "error_code": e.response.status_code
                    }
            else:
                logger.error(f"Settings update HTTP error: {str(e)}")
                return {"status": "error", "message": str(e)}

        except Exception as e:
            logger.error(f"Settings update failed: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "설정 업데이트")
            return {
                "status": "error",
                "message": str(e),
                "updated": False
            }

    def test_settings_endpoint(self) -> Dict:
        """
        설정 엔드포인트 테스트

        Returns:
            테스트 결과
        """
        try:
            # GET 테스트
            get_result = self.get_settings()

            # 간단한 PUT 테스트 (빈 딕셔너리)
            test_settings = {}
            put_result = self.update_settings(test_settings)

            return {
                "status": "success",
                "get_test": "passed" if isinstance(get_result, dict) else "failed",
                "put_test": "passed" if put_result.get("status") == "ok" else "failed",
                "get_result": get_result,
                "put_result": put_result
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "get_test": "failed",
                "put_test": "failed"
            }

    # APIClient 클래스에 추가할 메서드
    @retry_on_failure()
    def request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        범용 HTTP 요청 메서드 - 온톨로지 API 호환성 제공

        Args:
            method: HTTP 메서드 (GET, POST, PUT, DELETE)
            endpoint: API 엔드포인트
            **kwargs: 추가 요청 매개변수 (json, params, headers 등)

        Returns:
            API 응답 딕셔너리
        """
        try:
            logger.info(f"🔗 API 요청: {method} {endpoint}")

            # _make_request를 통해 실제 HTTP 요청 실행
            response = self._make_request(method, endpoint, **kwargs)

            # JSON 응답 파싱
            if response.content:
                try:
                    result = response.json()
                    logger.debug(f"📥 응답 파싱 성공: {type(result)}")
                    return result
                except ValueError as e:
                    logger.warning(f"⚠️ JSON 파싱 실패: {str(e)}")
                    # JSON이 아닌 응답의 경우 텍스트 반환
                    return {"raw_response": response.text, "status_code": response.status_code}
            else:
                # 빈 응답 (예: 204 No Content)
                return {"status_code": response.status_code, "message": "No content"}

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP 오류: {method} {endpoint}")

            # 오류 응답 파싱 시도
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    return {
                        "error": True,
                        "status_code": e.response.status_code,
                        "message": error_data.get("detail", str(e)),
                        **error_data
                    }
                except ValueError:
                    return {
                        "error": True,
                        "status_code": e.response.status_code,
                        "message": e.response.text or str(e)
                    }
            else:
                return {"error": True, "message": str(e)}

        except requests.exceptions.ConnectionError as e:
            logger.error(f"🔌 연결 오류: {self.base_url}")
            return {
                "error": True,
                "message": f"서버에 연결할 수 없습니다: {self.base_url}",
                "type": "connection_error"
            }

        except requests.exceptions.Timeout as e:
            logger.error(f"⏰ 타임아웃: {method} {endpoint}")
            return {
                "error": True,
                "message": f"요청 시간 초과 ({self.timeout}초)",
                "type": "timeout"
            }

        except Exception as e:
            logger.error(f"💥 예기치 못한 오류: {type(e).__name__}: {str(e)}")
            return {
                "error": True,
                "message": f"API 요청 중 오류 발생: {str(e)}",
                "type": "unexpected_error"
            }

    # ===============================
    # 기타 메서드들 (기존과 동일)
    # ===============================

    def set_timeout(self, timeout: int):
        """타임아웃 설정 변경"""
        self.timeout = timeout
        logger.info(f"Timeout updated to {timeout} seconds")

    def set_retries(self, max_retries: int):
        """재시도 횟수 설정"""
        self.max_retries = max_retries
        logger.info(f"Max retries updated to {max_retries}")

    # _make_request 메서드는 기존과 동일하게 유지
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        HTTP 요청 실행 - 개선된 에러 처리
        """
        url = f"{self.base_url}{endpoint}"

        # 타임아웃 설정
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout

        # 요청 로깅
        logger.debug(f"Making {method} request to {url}")
        if 'json' in kwargs:
            logger.debug(f"Request data: {kwargs['json']}")

        try:
            response = self.session.request(method, url, **kwargs)

            # 응답 로깅
            logger.debug(f"Response: {response.status_code} from {url}")

            # 상세 오류 로깅
            if response.status_code >= 400:
                logger.error(f"HTTP Error {response.status_code}: {response.text}")

            response.raise_for_status()
            return response

        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout: {method} {url} (timeout: {kwargs.get('timeout')}s)")
            if HAS_ERROR_HANDLER:
                raise GTRagError(
                    f"API 요청 시간 초과 ({kwargs.get('timeout')}초)",
                    ErrorType.API_TIMEOUT,
                    ErrorSeverity.MEDIUM,
                    [
                        "타임아웃 설정을 늘려보세요",
                        "더 간단한 요청을 시도해보세요",
                        "서버 상태를 확인하세요"
                    ]
                )
            raise

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {method} {url}")
            if HAS_ERROR_HANDLER:
                raise GTRagError(
                    "API 서버에 연결할 수 없습니다",
                    ErrorType.API_CONNECTION,
                    ErrorSeverity.HIGH,
                    [
                        f"서버가 실행 중인지 확인하세요 ({self.base_url})",
                        "네트워크 연결을 확인하세요",
                        "방화벽 설정을 확인하세요"
                    ]
                )
            raise

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {method} {url} - {e}")
            # HTTPError는 재발생시켜서 상위에서 처리하도록 함
            raise

        except Exception as e:
            logger.error(f"Unexpected error: {method} {url} - {e}")
            raise

    @retry_on_failure()
    def get_available_models(self) -> List[str]:
        """
        사용 가능한 LLM 모델 목록 조회 - 강화된 디버깅 버전

        Returns:
            모델 이름 리스트 (실패 시 빈 리스트)
        """
        # 디버깅 정보 출력
        endpoint_url = f"{self.base_url}{Constants.Endpoints.MODELS}"
        logger.info(f"🔍 get_available_models 시작")
        logger.info(f"🔗 요청 URL: {endpoint_url}")
        logger.info(f"📡 Base URL: {self.base_url}")
        logger.info(f"🎯 Endpoint: {Constants.Endpoints.MODELS}")

        try:
            # 1. 요청 전 상태 로깅
            logger.info("📤 API 요청 전송 중...")

            response = self._make_request("GET", Constants.Endpoints.MODELS)

            # 2. 응답 상태 로깅
            logger.info(f"📥 응답 받음 - 상태 코드: {response.status_code}")
            logger.info(f"📦 응답 크기: {len(response.content)} bytes")

            # 3. 응답 파싱
            result = response.json()
            logger.info(f"🔄 파싱된 응답 타입: {type(result)}")
            logger.info(f"📄 원본 응답 데이터: {result}")

            # 4. 응답 형식에 따라 처리
            models = []

            if isinstance(result, list):
                models = result
                logger.info(f"✅ 직접 리스트 형식 - {len(models)}개 모델")
                logger.info(f"📋 모델 목록: {models}")

            elif isinstance(result, dict):
                logger.info(f"📊 딕셔너리 형식 - 키들: {list(result.keys())}")

                # 새로운 API 응답 형식
                if 'models' in result:
                    models = result['models']
                    logger.info(f"✅ 'models' 키에서 {len(models)}개 모델 발견")
                elif 'model_list' in result:
                    models = result['model_list']
                    logger.info(f"✅ 'model_list' 키에서 {len(models)}개 모델 발견")
                else:
                    logger.warning(f"⚠️ 예상하지 못한 딕셔너리 구조. 사용 가능한 키: {list(result.keys())}")
                    models = []
            else:
                logger.error(f"❌ 예상하지 못한 응답 타입: {type(result)}")
                models = []

            # 5. 최종 결과 로깅
            logger.info(f"🎯 최종 처리된 모델 수: {len(models)}")
            logger.info(f"📝 최종 모델 목록: {models}")

            return models

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP 오류 발생")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"🔢 상태 코드: {e.response.status_code}")
                logger.error(f"📄 응답 텍스트: {e.response.text}")

                if e.response.status_code == 404:
                    logger.error(f"🚫 엔드포인트를 찾을 수 없음: {endpoint_url}")
                    logger.error("💡 해결 방법: Backend의 models router 등록 확인")

            if HAS_ERROR_HANDLER:
                handle_api_error(e, "모델 목록 조회")
            return []

        except requests.exceptions.ConnectionError as e:
            logger.error(f"🔌 연결 오류: {self.base_url}")
            logger.error(f"📝 오류 내용: {str(e)}")
            return []

        except Exception as e:
            logger.error(f"💥 예기치 못한 오류")
            logger.error(f"🏷️ 오류 타입: {type(e).__name__}")
            logger.error(f"📝 오류 메시지: {str(e)}")

            # 스택 트레이스 출력
            import traceback
            logger.error(f"📚 스택 트레이스:")
            logger.error(traceback.format_exc())

            if HAS_ERROR_HANDLER:
                handle_api_error(e, "모델 목록 조회")
            return []

    # 추가: Constants.Endpoints.MODELS 값 확인을 위한 디버깅 메서드
    def debug_endpoints(self) -> Dict:
        """엔드포인트 설정 디버깅"""
        debug_info = {
            "base_url": self.base_url,
            "endpoints": {
                "models": getattr(Constants.Endpoints, 'MODELS', 'NOT_FOUND'),
                "settings": getattr(Constants.Endpoints, 'SETTINGS', 'NOT_FOUND'),
            },
            "full_models_url": f"{self.base_url}{getattr(Constants.Endpoints, 'MODELS', 'UNKNOWN')}",
        }

        # Constants 클래스 전체 확인
        try:
            endpoints_attrs = [attr for attr in dir(Constants.Endpoints) if not attr.startswith('_')]
            debug_info["available_endpoints"] = {
                attr: getattr(Constants.Endpoints, attr) for attr in endpoints_attrs
            }
        except:
            debug_info["available_endpoints"] = "Constants.Endpoints 접근 실패"

        return debug_info

    @retry_on_failure()
    def generate_answer(self, query: str, model: str = None, **kwargs) -> Dict[str, Any]:
        """
        RAG 기반 답변 생성

        Args:
            query: 사용자 질문
            model: 사용할 모델명
            **kwargs: 추가 매개변수 (temperature, top_k, min_score, search_type 등)

        Returns:
            답변 결과 딕셔너리
        """
        try:
            # 요청 데이터 구성
            request_data = {
                "query": query,
                "model": model or "gemma3n:latest",
                **kwargs
            }

            # 기본값 설정
            if "temperature" not in request_data:
                request_data["temperature"] = 0.7
            if "top_k" not in request_data:
                request_data["top_k"] = 3
            if "min_score" not in request_data:
                request_data["min_score"] = 0.3
            if "search_type" not in request_data:
                request_data["search_type"] = "hybrid"

            logger.info(f"Generating answer for query: '{query[:50]}...' with model: {request_data['model']}")
            logger.debug(f"Request parameters: {request_data}")

            # API 호출
            response = self._make_request(
                "POST",
                "/v1/generate_answer",
                json=request_data
            )

            result = response.json()
            logger.info("Answer generated successfully")
            logger.debug(f"Response keys: {list(result.keys())}")

            return result

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error in generate_answer: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_message = error_detail.get('detail', str(e))

                    if e.response.status_code == 404:
                        error_message = "generate_answer 엔드포인트를 찾을 수 없습니다. 백엔드 서버가 최신 버전인지 확인하세요."
                    elif e.response.status_code == 503:
                        error_message = "Ollama 서버에 연결할 수 없습니다. Ollama가 실행 중인지 확인하세요."

                    return {
                        "error": f"HTTP {e.response.status_code}: {error_message}",
                        "status_code": e.response.status_code,
                        "answer": "죄송합니다. 서버 오류로 인해 답변을 생성할 수 없습니다."
                    }
                except:
                    return {
                        "error": f"HTTP {e.response.status_code}: {e.response.text}",
                        "status_code": e.response.status_code,
                        "answer": "죄송합니다. 서버 오류로 인해 답변을 생성할 수 없습니다."
                    }
            else:
                return {
                    "error": str(e),
                    "answer": "죄송합니다. 네트워크 오류로 인해 답변을 생성할 수 없습니다."
                }

        except Exception as e:
            logger.error(f"Error in generate_answer: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "답변 생성")
            return {
                "error": str(e),
                "answer": "죄송합니다. 예기치 못한 오류로 인해 답변을 생성할 수 없습니다."
            }

    @retry_on_failure()
    def health_check(self) -> Dict[str, Any]:
        """
        백엔드 서버 헬스체크

        Returns:
            헬스체크 결과
        """
        try:
            response = self._make_request("GET", "/v1/health")
            result = response.json()
            logger.info("Health check successful")
            return result
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "헬스체크")
            return {
                "status": "unhealthy",
                "error": str(e),
                "qdrant": False,
                "ollama": False,
                "celery": False
            }

    @retry_on_failure()
    def search(
            self,
            query: str,
            top_k: int = None,
            search_type: str = None,
            min_score: float = None,
            lang: str = None,
            filters: Dict[str, Any] = None,
            **kwargs
    ) -> Dict[str, Any]:
        """
        문서 검색 API 호출 - 최적화된 버전

        Args:
            query: 검색 쿼리 (필수)
            top_k: 반환할 결과 개수 (1-20, 기본값: 3)
            search_type: 검색 유형 ("vector", "hybrid", "rerank", 기본값: "hybrid")
            min_score: 최소 유사도 점수 (0.0-1.0, 기본값: 0.3)
            lang: 언어 필터 ("ko", "en", "auto", 기본값: None)
            filters: 추가 필터 조건 (dict)
            **kwargs: 추가 매개변수

        Returns:
            검색 결과 딕셔너리:
            {
                "results": [검색 결과 리스트],
                "total_count": 전체 결과 수,
                "query": 검색 쿼리,
                "search_type": 사용된 검색 유형,
                "processing_time": 처리 시간
            }
        """
        # 입력 검증
        if not query or not query.strip():
            logger.error("Empty search query provided")
            if HAS_ERROR_HANDLER:
                raise GTRagError(
                    "검색어를 입력해주세요",
                    ErrorType.VALIDATION,
                    ErrorSeverity.LOW,
                    ["최소 1글자 이상 입력하세요"]
                )
            raise ValueError("검색어가 비어있습니다")

        query = query.strip()

        # 기본값 설정
        top_k = top_k or Constants.Defaults.TOP_K
        search_type = search_type or Constants.Defaults.SEARCH_TYPE
        min_score = min_score if min_score is not None else Constants.Defaults.MIN_SIMILARITY

        # 매개변수 검증
        if not (Constants.Limits.MIN_TOP_K <= top_k <= Constants.Limits.MAX_TOP_K):
            logger.warning(f"top_k value {top_k} out of range, clamping to valid range")
            top_k = max(Constants.Limits.MIN_TOP_K, min(top_k, Constants.Limits.MAX_TOP_K))

        if not (Constants.Limits.MIN_SIMILARITY <= min_score <= Constants.Limits.MAX_SIMILARITY):
            logger.warning(f"min_score value {min_score} out of range, clamping to valid range")
            min_score = max(Constants.Limits.MIN_SIMILARITY, min(min_score, Constants.Limits.MAX_SIMILARITY))

        if search_type not in ["vector", "hybrid", "rerank"]:
            logger.warning(f"Invalid search_type '{search_type}', using 'hybrid'")
            search_type = "hybrid"

        # 요청 파라미터 구성
        params = {
            "q": query,
            "top_k": top_k,
            "search_type": search_type
        }

        # 선택적 파라미터 추가
        if min_score != Constants.Defaults.MIN_SIMILARITY:
            params["min_score"] = min_score

        if lang:
            params["lang"] = lang

        # 추가 필터 처리
        if filters:
            for key, value in filters.items():
                if value is not None:
                    params[f"filter_{key}"] = value

        # 요청 로깅
        logger.info(f"🔍 검색 시작: '{query[:50]}{'...' if len(query) > 50 else ''}'")
        logger.info(f"📊 검색 옵션: top_k={top_k}, type={search_type}, min_score={min_score}")
        logger.debug(f"🔧 전체 파라미터: {params}")

        start_time = time.time()

        try:
            # API 호출
            response = self._make_request(
                "GET",
                Constants.Endpoints.SEARCH,
                params=params,
                timeout=self.timeout
            )

            processing_time = time.time() - start_time

            # 응답 파싱
            raw_results = response.json()
            logger.info(f"📥 원본 응답 수신: {type(raw_results)} ({len(response.content)} bytes)")
            logger.debug(f"📄 원본 데이터: {raw_results}")

            # 결과 후처리
            processed_results = self._process_search_results(raw_results, query, min_score)

            # 성공 로깅
            result_count = len(processed_results.get("results", []))
            logger.info(f"✅ 검색 완료: {result_count}개 결과 (처리시간: {processing_time:.2f}초)")

            # 통계 정보 추가
            processed_results.update({
                "query": query,
                "search_type": search_type,
                "processing_time": round(processing_time, 3),
                "total_count": result_count,
                "parameters": {
                    "top_k": top_k,
                    "min_score": min_score,
                    "search_type": search_type
                }
            })

            return processed_results

        except requests.exceptions.HTTPError as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ HTTP 오류 ({processing_time:.2f}초 후)")

            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                logger.error(f"🔢 상태 코드: {status_code}")

                try:
                    error_detail = e.response.json()
                    error_message = error_detail.get('detail', str(e))
                    logger.error(f"📄 오류 세부사항: {error_detail}")
                except:
                    error_message = e.response.text
                    logger.error(f"📄 오류 텍스트: {error_message}")

                # 상태 코드별 처리
                if status_code == 400:
                    if HAS_ERROR_HANDLER:
                        raise GTRagError(
                            f"잘못된 검색 요청: {error_message}",
                            ErrorType.VALIDATION,
                            ErrorSeverity.LOW,
                            ["검색어를 다시 확인해주세요", "특수문자를 제거해보세요"]
                        )
                    return {"results": [], "error": f"잘못된 요청: {error_message}"}

                elif status_code == 404:
                    if HAS_ERROR_HANDLER:
                        raise GTRagError(
                            "검색 API를 찾을 수 없습니다",
                            ErrorType.API_RESPONSE,
                            ErrorSeverity.HIGH,
                            ["백엔드 서버가 최신 버전인지 확인하세요", f"엔드포인트 확인: {Constants.Endpoints.SEARCH}"]
                        )
                    return {"results": [], "error": "검색 API를 찾을 수 없습니다"}

                elif status_code == 503:
                    if HAS_ERROR_HANDLER:
                        raise GTRagError(
                            "검색 서비스를 사용할 수 없습니다",
                            ErrorType.API_RESPONSE,
                            ErrorSeverity.HIGH,
                            ["Qdrant 데이터베이스 상태를 확인하세요", "잠시 후 다시 시도해보세요"]
                        )
                    return {"results": [], "error": "검색 서비스 일시 중단"}

                else:
                    if HAS_ERROR_HANDLER:
                        raise GTRagError(
                            f"검색 서버 오류: HTTP {status_code}",
                            ErrorType.API_RESPONSE,
                            ErrorSeverity.MEDIUM,
                            ["잠시 후 다시 시도해보세요", "문제가 지속되면 관리자에게 문의하세요"]
                        )
                    return {"results": [], "error": f"서버 오류 ({status_code})"}
            else:
                if HAS_ERROR_HANDLER:
                    handle_api_error(e, "문서 검색")
                return {"results": [], "error": "네트워크 오류"}

        except requests.exceptions.Timeout as e:
            processing_time = time.time() - start_time
            logger.error(f"⏰ 검색 타임아웃 ({processing_time:.2f}초)")

            if HAS_ERROR_HANDLER:
                raise GTRagError(
                    f"검색 요청 시간 초과 ({self.timeout}초)",
                    ErrorType.API_TIMEOUT,
                    ErrorSeverity.MEDIUM,
                    [
                        "더 짧은 검색어를 사용해보세요",
                        "검색 결과 개수를 줄여보세요",
                        f"현재 타임아웃: {self.timeout}초"
                    ]
                )
            return {"results": [], "error": f"검색 시간 초과 ({self.timeout}초)"}

        except requests.exceptions.ConnectionError as e:
            processing_time = time.time() - start_time
            logger.error(f"🔌 연결 오류 ({processing_time:.2f}초 후): {self.base_url}")

            if HAS_ERROR_HANDLER:
                raise GTRagError(
                    "검색 서버에 연결할 수 없습니다",
                    ErrorType.API_CONNECTION,
                    ErrorSeverity.HIGH,
                    [
                        f"서버가 실행 중인지 확인하세요 ({self.base_url})",
                        "네트워크 연결을 확인하세요",
                        "방화벽 설정을 확인하세요"
                    ]
                )
            return {"results": [], "error": "서버 연결 실패"}

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"💥 예기치 못한 검색 오류 ({processing_time:.2f}초 후)")
            logger.error(f"🏷️ 오류 타입: {type(e).__name__}")
            logger.error(f"📝 오류 메시지: {str(e)}")

            # 스택 트레이스 출력 (디버그 모드)
            if config.is_development():
                import traceback
                logger.error(f"📚 스택 트레이스:")
                logger.error(traceback.format_exc())

            if HAS_ERROR_HANDLER:
                handle_api_error(e, "문서 검색")

            return {
                "results": [],
                "error": f"검색 중 오류 발생: {str(e)}",
                "query": query,
                "processing_time": round(processing_time, 3)
            }

    def _process_search_results(self, raw_results: Any, query: str, min_score: float) -> Dict[str, Any]:
        """
        검색 결과 후처리 및 유효성 검사

        Args:
            raw_results: API에서 받은 원본 결과
            query: 검색 쿼리
            min_score: 최소 점수 필터

        Returns:
            처리된 검색 결과
        """
        try:
            # 결과 형식 정규화
            if isinstance(raw_results, list):
                results = raw_results
            elif isinstance(raw_results, dict):
                results = raw_results.get("results", raw_results.get("items", []))
            else:
                logger.warning(f"⚠️ 예상하지 못한 결과 형식: {type(raw_results)}")
                results = []

            logger.info(f"📊 후처리 전 결과: {len(results)}개")

            # 개별 결과 검증 및 정리
            processed_results = []

            for idx, result in enumerate(results):
                try:
                    # 필수 필드 검증
                    if not isinstance(result, dict):
                        logger.warning(f"⚠️ 결과 {idx}: dict가 아님 ({type(result)}), 건너뜀")
                        continue

                    # 점수 검증 및 필터링
                    score = result.get('score', 0.0)
                    if not isinstance(score, (int, float)):
                        logger.warning(f"⚠️ 결과 {idx}: 유효하지 않은 점수 ({score}), 건너뜀")
                        continue

                    if score < min_score:
                        logger.debug(f"🔽 결과 {idx}: 점수 {score:.3f} < {min_score}, 필터링됨")
                        continue

                    # 필수 필드 확인 및 기본값 설정
                    processed_result = {
                        "id": result.get("id", f"unknown_{idx}"),
                        "score": round(float(score), 4),
                        "content": result.get("content", "").strip(),
                        "metadata": result.get("metadata", {})
                    }

                    # 내용 검증
                    if not processed_result["content"]:
                        logger.warning(f"⚠️ 결과 {idx}: 빈 내용, 건너뜀")
                        continue

                    # 메타데이터 정리
                    metadata = processed_result["metadata"]
                    if not isinstance(metadata, dict):
                        logger.warning(f"⚠️ 결과 {idx}: 메타데이터가 dict가 아님, 초기화")
                        processed_result["metadata"] = {}

                    # 추가 정보 보강
                    processed_result["content_length"] = len(processed_result["content"])
                    processed_result["has_korean"] = bool(re.search(r'[가-힣]', processed_result["content"]))

                    # 검색어 하이라이트 정보 추가 (선택적)
                    if query and len(query.strip()) > 1:
                        highlight_count = self._count_query_matches(processed_result["content"], query)
                        processed_result["highlight_count"] = highlight_count

                    processed_results.append(processed_result)
                    logger.debug(f"✅ 결과 {idx}: 처리 완료 (점수: {score:.3f})")

                except Exception as e:
                    logger.error(f"❌ 결과 {idx} 처리 중 오류: {str(e)}")
                    continue

            # 점수순 정렬 (안전장치)
            processed_results.sort(key=lambda x: x.get('score', 0), reverse=True)

            logger.info(f"✅ 후처리 완료: {len(processed_results)}개 결과")

            # 품질 통계
            if processed_results:
                scores = [r['score'] for r in processed_results]
                avg_score = sum(scores) / len(scores)
                max_score = max(scores)
                min_score_actual = min(scores)

                logger.info(f"📈 품질 통계: 평균 {avg_score:.3f}, 최고 {max_score:.3f}, 최저 {min_score_actual:.3f}")

            return {
                "results": processed_results,
                "total_count": len(processed_results),
                "filtered_count": len(results) - len(processed_results) if isinstance(results, list) else 0
            }

        except Exception as e:
            logger.error(f"❌ 검색 결과 후처리 중 오류: {str(e)}")
            return {
                "results": [],
                "total_count": 0,
                "error": f"결과 처리 오류: {str(e)}"
            }

    def _count_query_matches(self, content: str, query: str) -> int:
        """검색어 매칭 횟수 계산"""
        try:
            if not content or not query:
                return 0

            # 단순 키워드 매칭 (대소문자 무시)
            content_lower = content.lower()
            query_terms = [term.strip() for term in query.lower().split() if term.strip()]

            total_matches = 0
            for term in query_terms:
                if len(term) >= 2:  # 2글자 이상만 카운트
                    matches = content_lower.count(term.lower())
                    total_matches += matches

            return total_matches

        except Exception as e:
            logger.warning(f"검색어 매칭 계산 오류: {str(e)}")
            return 0

    # 검색 관련 편의 메서드들
    @retry_on_failure()
    def search_by_file(self, query: str, filename: str, **kwargs) -> Dict[str, Any]:
        """특정 파일에서만 검색"""
        filters = kwargs.get('filters', {})
        filters['source'] = filename
        kwargs['filters'] = filters

        logger.info(f"🔍 파일별 검색: '{filename}'에서 '{query}' 검색")
        return self.search(query, **kwargs)

    @retry_on_failure()
    def search_recent(self, query: str, days: int = 7, **kwargs) -> Dict[str, Any]:
        """최근 업로드된 문서에서만 검색"""
        from datetime import datetime, timedelta

        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        filters = kwargs.get('filters', {})
        filters['uploaded_after'] = cutoff_date
        kwargs['filters'] = filters

        logger.info(f"🔍 최근 검색: {days}일 이내 문서에서 '{query}' 검색")
        return self.search(query, **kwargs)

    def get_search_suggestions(self, query: str) -> List[str]:
        """검색어 제안 생성"""
        try:
            suggestions = []

            # 띄어쓰기 관련 제안
            if ' ' in query:
                suggestions.append(query.replace(' ', ''))
            elif len(query) > 4:
                mid = len(query) // 2
                suggestions.append(f"{query[:mid]} {query[mid:]}")

            # 유사어 제안 (확장 가능)
            synonyms = {
                '계약': ['협약', '약정', '계약서'],
                '납품': ['배송', '인도', '납기'],
                '품질': ['품질관리', 'QC', '검사'],
                '가격': ['비용', '금액', '요금'],
                '일정': ['스케줄', '기간', '기한']
            }

            for word, syns in synonyms.items():
                if word in query:
                    for syn in syns[:2]:
                        suggestion = query.replace(word, syn)
                        if suggestion not in suggestions:
                            suggestions.append(suggestion)

            return suggestions[:5]  # 최대 5개

        except Exception as e:
            logger.warning(f"검색어 제안 생성 오류: {str(e)}")
            return []

    # APIClient 클래스에 추가할 문서 관리 메서드들

    @retry_on_failure()
    def list_documents(
            self,
            stats_only: bool = False,
            include_details: bool = True,
            sort_by: str = "uploaded_at",
            sort_desc: bool = True,
            **kwargs
    ) -> Dict[str, Any]:
        """
        서버에서 문서 목록 조회 - 최적화된 버전

        Args:
            stats_only: True이면 통계만 반환, False이면 전체 목록
            include_details: 상세 정보 포함 여부
            sort_by: 정렬 기준 ("uploaded_at", "name", "chunks", "size")
            sort_desc: 내림차순 정렬 여부
            **kwargs: 추가 필터 옵션

        Returns:
            문서 목록 딕셔너리:
            {
                "documents": [문서 목록] or None (stats_only=True인 경우),
                "total_documents": 총 문서 수,
                "total_chunks": 총 청크 수,
                "total_size": 총 크기 (추정),
                "last_updated": 조회 시간
            }
        """
        # 요청 파라미터 구성
        params = {
            "stats": str(stats_only).lower()
        }

        # 추가 필터 파라미터
        for key, value in kwargs.items():
            if value is not None:
                params[key] = value

        logger.info(f"📋 문서 목록 조회 시작 (통계만: {stats_only})")
        logger.debug(f"🔧 요청 파라미터: {params}")

        start_time = time.time()

        try:
            # API 호출
            response = self._make_request(
                "GET",
                Constants.Endpoints.DOCUMENTS,
                params=params,
                timeout=min(self.timeout, 30)  # 문서 목록은 빠르게
            )

            processing_time = time.time() - start_time

            # 응답 파싱
            raw_data = response.json()
            logger.info(f"📥 원본 데이터 수신: {type(raw_data)} ({len(response.content)} bytes)")
            logger.debug(f"📄 원본 응답: {raw_data}")

            # 응답 처리
            if stats_only:
                # 통계만 요청한 경우
                if isinstance(raw_data, dict) and "total_documents" in raw_data:
                    result = {
                        "documents": None,
                        "total_documents": raw_data.get("total_documents", 0),
                        "total_chunks": raw_data.get("total_chunks", 0),
                        "total_size": 0,  # 서버에서 제공하지 않는 경우
                        "last_updated": datetime.now().isoformat(),
                        "processing_time": round(processing_time, 3)
                    }
                    logger.info(f"📊 통계 조회 완료: {result['total_documents']}개 문서, {result['total_chunks']}개 청크")
                    return result
                else:
                    logger.warning("⚠️ 예상하지 못한 통계 응답 형식")
                    return self._create_empty_documents_response(processing_time)

            else:
                # 전체 목록 요청한 경우
                documents = self._process_documents_list(raw_data, sort_by, sort_desc, include_details)

                # 통계 계산
                total_documents = len(documents)
                total_chunks = sum(doc.get("chunks", 0) for doc in documents)
                total_size = sum(self._parse_document_size(doc.get("size")) for doc in documents)

                result = {
                    "documents": documents,
                    "total_documents": total_documents,
                    "total_chunks": total_chunks,
                    "total_size": total_size,
                    "last_updated": datetime.now().isoformat(),
                    "processing_time": round(processing_time, 3)
                }

                logger.info(f"📋 문서 목록 조회 완료: {total_documents}개 문서 (처리시간: {processing_time:.2f}초)")
                return result

        except requests.exceptions.HTTPError as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ HTTP 오류 ({processing_time:.2f}초 후)")

            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                logger.error(f"🔢 상태 코드: {status_code}")

                if status_code == 404:
                    if HAS_ERROR_HANDLER:
                        raise GTRagError(
                            "문서 목록 API를 찾을 수 없습니다",
                            ErrorType.API_RESPONSE,
                            ErrorSeverity.HIGH,
                            ["백엔드 서버가 최신 버전인지 확인하세요", f"엔드포인트 확인: {Constants.Endpoints.DOCUMENTS}"]
                        )
                    return self._create_empty_documents_response(processing_time, "API 엔드포인트를 찾을 수 없음")

                elif status_code == 503:
                    if HAS_ERROR_HANDLER:
                        raise GTRagError(
                            "문서 서비스를 사용할 수 없습니다",
                            ErrorType.API_RESPONSE,
                            ErrorSeverity.HIGH,
                            ["Qdrant 데이터베이스 상태를 확인하세요", "잠시 후 다시 시도해보세요"]
                        )
                    return self._create_empty_documents_response(processing_time, "문서 서비스 일시 중단")

                else:
                    if HAS_ERROR_HANDLER:
                        raise GTRagError(
                            f"문서 목록 조회 실패: HTTP {status_code}",
                            ErrorType.API_RESPONSE,
                            ErrorSeverity.MEDIUM,
                            ["잠시 후 다시 시도해보세요"]
                        )
                    return self._create_empty_documents_response(processing_time, f"서버 오류 ({status_code})")
            else:
                if HAS_ERROR_HANDLER:
                    handle_api_error(e, "문서 목록 조회")
                return self._create_empty_documents_response(processing_time, "네트워크 오류")

        except requests.exceptions.Timeout as e:
            processing_time = time.time() - start_time
            logger.error(f"⏰ 문서 목록 조회 타임아웃 ({processing_time:.2f}초)")

            if HAS_ERROR_HANDLER:
                raise GTRagError(
                    f"문서 목록 조회 시간 초과 ({self.timeout}초)",
                    ErrorType.API_TIMEOUT,
                    ErrorSeverity.MEDIUM,
                    ["잠시 후 다시 시도해보세요", f"현재 타임아웃: {self.timeout}초"]
                )
            return self._create_empty_documents_response(processing_time, f"시간 초과 ({self.timeout}초)")

        except requests.exceptions.ConnectionError as e:
            processing_time = time.time() - start_time
            logger.error(f"🔌 연결 오류 ({processing_time:.2f}초 후): {self.base_url}")

            if HAS_ERROR_HANDLER:
                raise GTRagError(
                    "문서 서버에 연결할 수 없습니다",
                    ErrorType.API_CONNECTION,
                    ErrorSeverity.HIGH,
                    [f"서버가 실행 중인지 확인하세요 ({self.base_url})", "네트워크 연결을 확인하세요"]
                )
            return self._create_empty_documents_response(processing_time, "서버 연결 실패")

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"💥 예기치 못한 문서 목록 조회 오류 ({processing_time:.2f}초 후)")
            logger.error(f"🏷️ 오류 타입: {type(e).__name__}")
            logger.error(f"📝 오류 메시지: {str(e)}")

            if config.is_development():
                import traceback
                logger.error(f"📚 스택 트레이스:")
                logger.error(traceback.format_exc())

            if HAS_ERROR_HANDLER:
                handle_api_error(e, "문서 목록 조회")

            return self._create_empty_documents_response(processing_time, f"오류 발생: {str(e)}")

    def _process_documents_list(self, raw_data: Any, sort_by: str, sort_desc: bool, include_details: bool) -> List[
        Dict]:
        """
        원본 문서 데이터를 처리하여 정제된 목록 반환

        Args:
            raw_data: API에서 받은 원본 데이터
            sort_by: 정렬 기준
            sort_desc: 내림차순 여부
            include_details: 상세 정보 포함 여부

        Returns:
            처리된 문서 목록
        """
        try:
            # 데이터 형식 정규화
            if isinstance(raw_data, list):
                documents = raw_data
            elif isinstance(raw_data, dict):
                documents = raw_data.get("documents", raw_data.get("items", []))
            else:
                logger.warning(f"⚠️ 예상하지 못한 문서 목록 형식: {type(raw_data)}")
                return []

            if not isinstance(documents, list):
                logger.warning(f"⚠️ 문서 데이터가 리스트가 아님: {type(documents)}")
                return []

            logger.info(f"📊 후처리 전 문서: {len(documents)}개")

            # 개별 문서 처리
            processed_docs = []

            for idx, doc in enumerate(documents):
                try:
                    if not isinstance(doc, dict):
                        logger.warning(f"⚠️ 문서 {idx}: dict가 아님 ({type(doc)}), 건너뜀")
                        continue

                    # 필수 필드 검증 및 기본값 설정
                    processed_doc = {
                        "name": doc.get("name", f"Unknown_{idx}"),
                        "chunks": max(0, int(doc.get("chunks", 0))),
                        "size": doc.get("size", 0),
                        "uploaded_at": doc.get("uploaded_at"),
                        "created_at": doc.get("created_at"),
                        "modified_at": doc.get("modified_at")
                    }

                    # 상세 정보 추가
                    if include_details:
                        processed_doc.update({
                            "doc_id": doc.get("doc_id"),
                            "file_size": self._parse_document_size(doc.get("size")),
                            "size_mb": self._parse_document_size(doc.get("size")) / (1024 * 1024),
                            "has_chunks": processed_doc["chunks"] > 0,
                            "upload_status": "completed" if processed_doc["chunks"] > 0 else "failed"
                        })

                    # 시간 정보 정제
                    for time_field in ["uploaded_at", "created_at", "modified_at"]:
                        if processed_doc[time_field]:
                            processed_doc[time_field] = self._format_document_timestamp(processed_doc[time_field])

                    processed_docs.append(processed_doc)
                    logger.debug(f"✅ 문서 {idx}: 처리 완료 ({processed_doc['name']})")

                except Exception as e:
                    logger.error(f"❌ 문서 {idx} 처리 중 오류: {str(e)}")
                    continue

            # 정렬
            processed_docs = self._sort_documents(processed_docs, sort_by, sort_desc)

            logger.info(f"✅ 문서 목록 후처리 완료: {len(processed_docs)}개")
            return processed_docs

        except Exception as e:
            logger.error(f"❌ 문서 목록 후처리 중 오류: {str(e)}")
            return []

    def _sort_documents(self, documents: List[Dict], sort_by: str, sort_desc: bool) -> List[Dict]:
        """문서 목록 정렬"""
        try:
            if not documents:
                return documents

            # 정렬 키 함수 정의
            sort_key_map = {
                "name": lambda x: x.get("name", "").lower(),
                "chunks": lambda x: x.get("chunks", 0),
                "size": lambda x: self._parse_document_size(x.get("size", 0)),
                "uploaded_at": lambda x: self._parse_document_timestamp(x.get("uploaded_at")),
                "created_at": lambda x: self._parse_document_timestamp(x.get("created_at")),
                "modified_at": lambda x: self._parse_document_timestamp(x.get("modified_at"))
            }

            sort_key = sort_key_map.get(sort_by, sort_key_map["uploaded_at"])

            sorted_docs = sorted(documents, key=sort_key, reverse=sort_desc)
            logger.debug(f"📊 문서 정렬 완료: {sort_by} ({'내림차순' if sort_desc else '오름차순'})")

            return sorted_docs

        except Exception as e:
            logger.warning(f"⚠️ 문서 정렬 중 오류: {str(e)}, 원본 순서 유지")
            return documents

    def _parse_document_size(self, size_value: Any) -> float:
        """문서 크기를 바이트 단위로 파싱"""
        try:
            if isinstance(size_value, (int, float)):
                return float(size_value)

            if isinstance(size_value, str):
                # "1.5 MB" 형태 파싱
                # 🔧 로컬 import 제거 (상단에서 이미 import됨)
                match = re.search(r'([\d.]+)\s*(MB|KB|GB|B)?', str(size_value), re.IGNORECASE)
                if match:
                    value = float(match.group(1))
                    unit = (match.group(2) or 'B').upper()

                    multipliers = {
                        'B': 1,
                        'KB': 1024,
                        'MB': 1024 * 1024,
                        'GB': 1024 * 1024 * 1024
                    }

                    return value * multipliers.get(unit, 1)

            return 0.0

        except Exception as e:
            logger.debug(f"크기 파싱 오류: {size_value} -> {str(e)}")
            return 0.0

    def _parse_document_timestamp(self, timestamp_value: Any) -> datetime:
        """문서 타임스탬프를 datetime 객체로 파싱"""
        try:
            if isinstance(timestamp_value, datetime):
                return timestamp_value

            if isinstance(timestamp_value, str) and timestamp_value:
                # ISO 형식 파싱
                try:
                    # 'Z' 접미사 처리
                    ts_str = timestamp_value.replace('Z', '+00:00')
                    return datetime.fromisoformat(ts_str)
                except ValueError:
                    # 다른 형식들 시도
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
                        try:
                            return datetime.strptime(timestamp_value, fmt)
                        except ValueError:
                            continue

            elif isinstance(timestamp_value, (int, float)):
                # Unix 타임스탬프
                ts = timestamp_value
                if ts > 1e12:  # 밀리초인 경우
                    ts = ts / 1000
                return datetime.fromtimestamp(ts, tz=timezone.utc)

            # 파싱 실패 시 현재 시간 반환
            return datetime.now()

        except Exception as e:
            logger.debug(f"타임스탬프 파싱 오류: {timestamp_value} -> {str(e)}")
            return datetime.now()

    def _format_document_timestamp(self, timestamp_value: Any) -> str:
        """문서 타임스탬프를 사용자 친화적 형식으로 포맷"""
        try:
            dt = self._parse_document_timestamp(timestamp_value)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.debug(f"타임스탬프 포맷 오류: {timestamp_value} -> {str(e)}")
            return str(timestamp_value) if timestamp_value else "-"

    def _create_empty_documents_response(self, processing_time: float, error_message: str = None) -> Dict[str, Any]:
        """빈 문서 응답 생성"""
        return {
            "documents": [],
            "total_documents": 0,
            "total_chunks": 0,
            "total_size": 0,
            "last_updated": datetime.now().isoformat(),
            "processing_time": round(processing_time, 3),
            "error": error_message
        }

    @retry_on_failure()
    def delete_document(self, document_key: str, **kwargs) -> Dict[str, Any]:
        """
        문서 삭제 - 최적화된 버전

        Args:
            document_key: 문서 식별자 (doc_id, 파일명, 또는 복합키)
            **kwargs: 추가 옵션

        Returns:
            삭제 결과 딕셔너리
        """
        if not document_key or not document_key.strip():
            logger.error("빈 문서 키 제공됨")
            if HAS_ERROR_HANDLER:
                raise GTRagError(
                    "삭제할 문서를 지정해주세요",
                    ErrorType.VALIDATION,
                    ErrorSeverity.LOW,
                    ["올바른 문서 이름이나 ID를 입력하세요"]
                )
            raise ValueError("문서 키가 비어있습니다")

        document_key = document_key.strip()

        logger.info(f"🗑️ 문서 삭제 시작: '{document_key}'")

        start_time = time.time()

        try:
            # API 호출 (DELETE 요청)
            response = self._make_request(
                "DELETE",
                f"{Constants.Endpoints.DOCUMENTS}/{document_key}",
                timeout=min(self.timeout, 60)  # 삭제는 시간이 걸릴 수 있음
            )

            processing_time = time.time() - start_time

            # 204 No Content 응답 확인
            if response.status_code == 204:
                logger.info(f"✅ 문서 삭제 완료: '{document_key}' (처리시간: {processing_time:.2f}초)")
                return {
                    "status": "success",
                    "message": f"문서 '{document_key}'가 성공적으로 삭제되었습니다",
                    "document_key": document_key,
                    "processing_time": round(processing_time, 3),
                    "deleted_at": datetime.now().isoformat()
                }
            else:
                # 예상하지 못한 응답 코드
                logger.warning(f"⚠️ 예상하지 못한 삭제 응답 코드: {response.status_code}")
                return {
                    "status": "unknown",
                    "message": f"문서 삭제 응답이 명확하지 않습니다 (코드: {response.status_code})",
                    "document_key": document_key,
                    "processing_time": round(processing_time, 3)
                }

        except requests.exceptions.HTTPError as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ 문서 삭제 HTTP 오류 ({processing_time:.2f}초 후)")

            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                logger.error(f"🔢 상태 코드: {status_code}")

                if status_code == 404:
                    logger.info(f"📄 문서를 찾을 수 없음: '{document_key}'")
                    if HAS_ERROR_HANDLER:
                        raise GTRagError(
                            f"문서 '{document_key}'를 찾을 수 없습니다",
                            ErrorType.VALIDATION,
                            ErrorSeverity.LOW,
                            ["문서 이름을 다시 확인하세요", "이미 삭제된 문서일 수 있습니다"]
                        )
                    return {
                        "status": "not_found",
                        "message": f"문서 '{document_key}'를 찾을 수 없습니다",
                        "document_key": document_key,
                        "processing_time": round(processing_time, 3)
                    }

                elif status_code == 403:
                    if HAS_ERROR_HANDLER:
                        raise GTRagError(
                            "문서 삭제 권한이 없습니다",
                            ErrorType.PERMISSION,
                            ErrorSeverity.HIGH,
                            ["관리자 권한이 필요할 수 있습니다"]
                        )
                    return {
                        "status": "forbidden",
                        "message": "문서 삭제 권한이 없습니다",
                        "document_key": document_key,
                        "processing_time": round(processing_time, 3)
                    }

                elif status_code == 500:
                    if HAS_ERROR_HANDLER:
                        raise GTRagError(
                            "서버에서 문서 삭제 중 오류가 발생했습니다",
                            ErrorType.API_RESPONSE,
                            ErrorSeverity.HIGH,
                            ["잠시 후 다시 시도해보세요", "문제가 지속되면 관리자에게 문의하세요"]
                        )
                    return {
                        "status": "server_error",
                        "message": "서버에서 삭제 중 오류가 발생했습니다",
                        "document_key": document_key,
                        "processing_time": round(processing_time, 3)
                    }

                else:
                    if HAS_ERROR_HANDLER:
                        raise GTRagError(
                            f"문서 삭제 실패: HTTP {status_code}",
                            ErrorType.API_RESPONSE,
                            ErrorSeverity.MEDIUM,
                            ["잠시 후 다시 시도해보세요"]
                        )
                    return {
                        "status": "error",
                        "message": f"문서 삭제 실패 (코드: {status_code})",
                        "document_key": document_key,
                        "processing_time": round(processing_time, 3)
                    }
            else:
                if HAS_ERROR_HANDLER:
                    handle_api_error(e, "문서 삭제")
                return {
                    "status": "error",
                    "message": "네트워크 오류로 문서 삭제에 실패했습니다",
                    "document_key": document_key,
                    "processing_time": round(processing_time, 3)
                }

        except requests.exceptions.Timeout as e:
            processing_time = time.time() - start_time
            logger.error(f"⏰ 문서 삭제 타임아웃 ({processing_time:.2f}초)")

            if HAS_ERROR_HANDLER:
                raise GTRagError(
                    f"문서 삭제 시간 초과 ({self.timeout}초)",
                    ErrorType.API_TIMEOUT,
                    ErrorSeverity.MEDIUM,
                    ["더 짧은 시간에 다시 시도해보세요", "큰 문서는 삭제에 시간이 걸릴 수 있습니다"]
                )
            return {
                "status": "timeout",
                "message": f"문서 삭제 시간 초과 ({self.timeout}초)",
                "document_key": document_key,
                "processing_time": round(processing_time, 3)
            }

        except requests.exceptions.ConnectionError as e:
            processing_time = time.time() - start_time
            logger.error(f"🔌 문서 삭제 연결 오류 ({processing_time:.2f}초 후): {self.base_url}")

            if HAS_ERROR_HANDLER:
                raise GTRagError(
                    "문서 서버에 연결할 수 없습니다",
                    ErrorType.API_CONNECTION,
                    ErrorSeverity.HIGH,
                    [f"서버가 실행 중인지 확인하세요 ({self.base_url})", "네트워크 연결을 확인하세요"]
                )
            return {
                "status": "connection_error",
                "message": "서버 연결 실패로 문서를 삭제할 수 없습니다",
                "document_key": document_key,
                "processing_time": round(processing_time, 3)
            }

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"💥 예기치 못한 문서 삭제 오류 ({processing_time:.2f}초 후)")
            logger.error(f"🏷️ 오류 타입: {type(e).__name__}")
            logger.error(f"📝 오류 메시지: {str(e)}")

            if config.is_development():
                import traceback
                logger.error(f"📚 스택 트레이스:")
                logger.error(traceback.format_exc())

            if HAS_ERROR_HANDLER:
                handle_api_error(e, "문서 삭제")

            return {
                "status": "error",
                "message": f"문서 삭제 중 오류 발생: {str(e)}",
                "document_key": document_key,
                "processing_time": round(processing_time, 3)
            }

    @retry_on_failure()
    def get_document_details(self, document_key: str, **kwargs) -> Dict[str, Any]:
        """
        특정 문서의 상세 정보 조회

        Args:
            document_key: 문서 식별자
            **kwargs: 추가 옵션

        Returns:
            문서 상세 정보
        """
        if not document_key or not document_key.strip():
            if HAS_ERROR_HANDLER:
                raise GTRagError(
                    "조회할 문서를 지정해주세요",
                    ErrorType.VALIDATION,
                    ErrorSeverity.LOW,
                    ["올바른 문서 이름이나 ID를 입력하세요"]
                )
            raise ValueError("문서 키가 비어있습니다")

        document_key = document_key.strip()

        logger.info(f"📄 문서 상세 정보 조회: '{document_key}'")

        try:
            # 전체 문서 목록에서 해당 문서 찾기
            documents_response = self.list_documents(stats_only=False, include_details=True)
            documents = documents_response.get("documents", [])

            # 문서 검색 (이름 또는 ID로)
            target_doc = None
            for doc in documents:
                if (doc.get("name") == document_key or
                        doc.get("doc_id") == document_key or
                        document_key in doc.get("name", "")):
                    target_doc = doc
                    break

            if target_doc:
                logger.info(f"✅ 문서 상세 정보 찾음: '{target_doc.get('name')}'")
                return {
                    "status": "found",
                    "document": target_doc,
                    "found_at": datetime.now().isoformat()
                }
            else:
                logger.info(f"📄 문서를 찾을 수 없음: '{document_key}'")
                return {
                    "status": "not_found",
                    "message": f"문서 '{document_key}'를 찾을 수 없습니다",
                    "searched_key": document_key
                }

        except Exception as e:
            logger.error(f"❌ 문서 상세 정보 조회 오류: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "문서 상세 정보 조회")

            return {
                "status": "error",
                "message": f"문서 정보 조회 중 오류 발생: {str(e)}",
                "searched_key": document_key
            }

    def sync_local_with_server_documents(self) -> Dict[str, Any]:
        import streamlit as st
        """
        로컬 세션의 문서 목록을 서버와 동기화

        Returns:
            동기화 결과
        """
        logger.info("🔄 문서 목록 서버 동기화 시작")

        try:
            # 서버에서 문서 목록 조회
            server_response = self.list_documents(stats_only=False, include_details=True)
            server_docs = server_response.get("documents", [])

            # 세션 데이터와 비교
            if 'uploaded_files' not in st.session_state:
                st.session_state.uploaded_files = []

            local_docs = st.session_state.uploaded_files

            # 서버 문서를 세션 형식으로 변환
            synced_docs = []
            for server_doc in server_docs:
                synced_doc = {
                    "name": server_doc.get("name", "Unknown"),
                    "original_name": server_doc.get("name", "Unknown"),
                    "time": server_doc.get("uploaded_at", "Unknown"),
                    "chunks": server_doc.get("chunks", 0),
                    "size": f"{server_doc.get('size_mb', 0):.2f} MB",
                    "type": "document",
                    "synced_from_server": True,
                    "uploaded_at": server_doc.get("uploaded_at"),
                    "created_at": server_doc.get("created_at"),
                    "modified_at": server_doc.get("modified_at")
                }
                synced_docs.append(synced_doc)

            # 세션 상태 업데이트
            st.session_state.uploaded_files = synced_docs

            sync_result = {
                "status": "success",
                "synced_count": len(synced_docs),
                "server_total": server_response.get("total_documents", 0),
                "server_chunks": server_response.get("total_chunks", 0),
                "sync_time": datetime.now().isoformat()
            }

            logger.info(f"✅ 문서 동기화 완료: {sync_result['synced_count']}개 문서")
            return sync_result

        except Exception as e:
            logger.error(f"❌ 문서 동기화 오류: {str(e)}")
            return {
                "status": "error",
                "message": f"동기화 중 오류 발생: {str(e)}",
                "sync_time": datetime.now().isoformat()
            }

    # 편의 메서드들
    def get_documents_stats(self) -> Dict[str, Any]:
        """문서 통계만 빠르게 조회"""
        return self.list_documents(stats_only=True)

    def search_documents_by_name(self, name_pattern: str) -> List[Dict]:
        """이름으로 문서 검색"""
        try:
            response = self.list_documents(stats_only=False)
            documents = response.get("documents", [])

            name_pattern_lower = name_pattern.lower()
            matching_docs = [
                doc for doc in documents
                if name_pattern_lower in doc.get("name", "").lower()
            ]

            logger.info(f"🔍 이름 검색 '{name_pattern}': {len(matching_docs)}개 문서 발견")
            return matching_docs

        except Exception as e:
            logger.error(f"❌ 문서 이름 검색 오류: {str(e)}")
            return []

    def get_documents_by_date_range(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """날짜 범위로 문서 필터링"""
        try:
            response = self.list_documents(stats_only=False)
            documents = response.get("documents", [])

            if not start_date and not end_date:
                return documents

            filtered_docs = []
            for doc in documents:
                doc_date = self._parse_document_timestamp(doc.get("uploaded_at"))

                include_doc = True
                if start_date:
                    start_dt = self._parse_document_timestamp(start_date)
                    if doc_date < start_dt:
                        include_doc = False

                if end_date and include_doc:
                    end_dt = self._parse_document_timestamp(end_date)
                    if doc_date > end_dt:
                        include_doc = False

                if include_doc:
                    filtered_docs.append(doc)

            logger.info(f"📅 날짜 필터링 결과: {len(filtered_docs)}개 문서")
            return filtered_docs

        except Exception as e:
            logger.error(f"❌ 날짜별 문서 필터링 오류: {str(e)}")
            return []

    def bulk_delete_documents(self, document_keys: List[str]) -> Dict[str, Any]:
        """여러 문서 일괄 삭제"""
        if not document_keys:
            return {"status": "error", "message": "삭제할 문서 목록이 비어있습니다"}

        logger.info(f"🗑️ 일괄 삭제 시작: {len(document_keys)}개 문서")

        results = {
            "total": len(document_keys),
            "success": 0,
            "failed": 0,
            "errors": [],
            "deleted_documents": []
        }

        for doc_key in document_keys:
            try:
                delete_result = self.delete_document(doc_key)

                if delete_result.get("status") == "success":
                    results["success"] += 1
                    results["deleted_documents"].append(doc_key)
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "document": doc_key,
                        "error": delete_result.get("message", "Unknown error")
                    })

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "document": doc_key,
                    "error": str(e)
                })

        results["status"] = "completed"
        logger.info(f"✅ 일괄 삭제 완료: 성공 {results['success']}개, 실패 {results['failed']}개")

        return results