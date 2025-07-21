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
from datetime import datetime
import json
import logging
import time
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


class APIClient:
    """GTOne RAG System API 클라이언트 - 개선된 버전"""

    def __init__(self, base_url: str = None, timeout: int = None):
        """
        API 클라이언트 초기화

        Args:
            base_url: API 서버 URL (기본값: config에서 가져옴)
            timeout: 요청 타임아웃 (기본값: config에서 가져옴)
        """
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

    def set_timeout(self, timeout: int):
        """타임아웃 설정 변경"""
        self.timeout = timeout
        logger.info(f"Timeout updated to {timeout} seconds")

    def set_retries(self, max_retries: int):
        """재시도 횟수 설정"""
        self.max_retries = max_retries
        logger.info(f"Max retries updated to {max_retries}")

    @retry_on_failure()
    def list_documents(self) -> List[Dict]:
        """문서 목록 조회 - 개선된 에러 처리"""
        try:
            response = self._make_request("GET", Constants.Endpoints.DOCUMENTS)
            return response.json()
        except Exception as e:
            logger.error(f"Document list fetch error: {e}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "문서 목록 조회")
            return []

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        HTTP 요청 실행 - 개선된 버전

        Args:
            method: HTTP 메소드 (GET, POST, PUT, DELETE)
            endpoint: API 엔드포인트
            **kwargs: requests 라이브러리 추가 인자

        Returns:
            Response 객체

        Raises:
            requests.exceptions.RequestException: 요청 실패
        """
        url = f"{self.base_url}{endpoint}"

        # 타임아웃 설정
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout

        # 요청 로깅
        logger.debug(f"Making {method} request to {url}")

        try:
            response = self.session.request(method, url, **kwargs)

            # 응답 로깅
            logger.debug(f"Response: {response.status_code} from {url}")

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
            if HAS_ERROR_HANDLER:
                status_code = response.status_code if 'response' in locals() else 'Unknown'
                raise GTRagError(
                    f"API 서버 오류 (HTTP {status_code})",
                    ErrorType.API_RESPONSE,
                    ErrorSeverity.MEDIUM,
                    [
                        "잠시 후 다시 시도해보세요",
                        "서버 로그를 확인하세요"
                    ]
                )
            raise

        except Exception as e:
            logger.error(f"Unexpected error: {method} {url} - {e}")
            raise

    @retry_on_failure()
    def upload_document(self, file, metadata: Optional[Dict] = None) -> Dict:
        """
        문서 업로드 - 개선된 버전

        Args:
            file: 업로드할 파일 객체 (Streamlit UploadedFile)
            metadata: 추가 메타데이터

        Returns:
            업로드 결과 (uploaded: 청크 수)
        """
        if HAS_ERROR_HANDLER:
            with ErrorContext("문서 업로드") as ctx:
                try:
                    return self._upload_document_impl(file, metadata)
                except Exception as e:
                    ctx.add_error(e)
                    return {"error": str(e), "uploaded": 0}
        else:
            return self._upload_document_impl(file, metadata)

    def _upload_document_impl(self, file, metadata: Optional[Dict] = None) -> Dict:
        """문서 업로드 구현"""
        try:
            # 파일 크기 검증
            file_size_mb = file.size / (1024 * 1024) if file.size else 0
            if file_size_mb > config.file.max_file_size_mb:
                if HAS_ERROR_HANDLER:
                    handle_file_error(
                        Exception(f"파일 크기 초과: {file_size_mb:.1f}MB > {config.file.max_file_size_mb}MB"),
                        file.name
                    )
                return {"error": f"파일 크기가 {config.file.max_file_size_mb}MB를 초과합니다", "uploaded": 0}

            # 파일 준비
            files = {
                "file": (file.name, file.getvalue(), file.type)
            }

            # 메타데이터가 있으면 추가
            data = {}
            if metadata:
                data['metadata'] = json.dumps(metadata)

            # 업로드 요청
            response = self._make_request(
                "POST",
                Constants.Endpoints.DOCUMENTS,
                files=files,
                data=data,
                timeout=config.file.upload_timeout
            )

            result = response.json()
            logger.info(f"Document uploaded successfully: {file.name} -> {result.get('uploaded', 0)} chunks")
            return result

        except Exception as e:
            logger.error(f"Document upload failed: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_file_error(e, file.name)
            return {"error": str(e), "uploaded": 0}

    @retry_on_failure()
    def upload_document_async(self, file, metadata: Optional[Dict] = None) -> Dict:
        """
        비동기 문서 업로드

        Args:
            file: 업로드할 파일 객체
            metadata: 추가 메타데이터

        Returns:
            태스크 정보 (task_id, status)
        """
        try:
            files = {
                "file": (file.name, file.getvalue(), file.type)
            }

            data = {}
            if metadata:
                data['metadata'] = json.dumps(metadata)

            response = self._make_request(
                "POST",
                f"{Constants.Endpoints.DOCUMENTS}/async",
                files=files,
                data=data
            )

            return response.json()

        except Exception as e:
            logger.error(f"Async document upload failed: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "비동기 문서 업로드")
            return {"error": str(e), "task_id": None}

    @retry_on_failure()
    def search(self, query: str, top_k: int = None, filters: Optional[Dict] = None) -> List[Dict]:
        """
        문서 검색 - 설정 기반

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 수 (기본값: config에서 가져옴)
            filters: 검색 필터 (언어, 날짜 등)

        Returns:
            검색 결과 리스트
        """
        if top_k is None:
            top_k = Constants.Defaults.TOP_K

        try:
            params = {
                "q": query,
                "top_k": min(top_k, config.ui.max_search_results)  # 설정 기반 제한
            }

            # 필터 추가
            if filters:
                if 'lang' in filters:
                    params['lang'] = filters['lang']
                if 'min_score' in filters:
                    params['min_score'] = filters['min_score']

            response = self._make_request("GET", Constants.Endpoints.SEARCH, params=params)
            results = response.json()

            logger.info(f"Search completed: '{query}' -> {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "문서 검색")
            return []

    @retry_on_failure()
    def generate_answer(self, query: str, top_k: int = None,
                        model: Optional[str] = None,
                        temperature: Optional[float] = None,
                        system_prompt: Optional[str] = None,
                        min_score: Optional[float] = None,
                        search_type: Optional[str] = None,
                        timeout: Optional[int] = None,
                        **kwargs) -> Dict:
        """
        RAG 답변 생성 - 설정 기반 개선

        Args:
            query: 사용자 질문
            top_k: 검색할 문서 수 (기본값: Constants에서 가져옴)
            model: 사용할 LLM 모델
            temperature: 생성 온도 (기본값: Constants에서 가져옴)
            system_prompt: 시스템 프롬프트 (기본값: Constants에서 가져옴)
            min_score: 최소 유사도 점수 (기본값: Constants에서 가져옴)
            search_type: 검색 타입 (기본값: Constants에서 가져옴)
            timeout: 요청 타임아웃 (기본값: config에서 가져옴)

        Returns:
            답변 결과 (answer, sources, question)
        """
        try:
            # 기본값 설정 (Constants 사용)
            params = {
                "q": query,
                "top_k": top_k or Constants.Defaults.TOP_K,
                "temperature": temperature or Constants.Defaults.TEMPERATURE,
                "system_prompt": system_prompt or Constants.Defaults.SYSTEM_PROMPT,
                "min_score": min_score or Constants.Defaults.MIN_SIMILARITY,
                "search_type": search_type or Constants.Defaults.SEARCH_TYPE
            }

            # 모델 파라미터 추가
            if model:
                params["model"] = model
                logger.info(f"Using model: {model}")

            # 추가 파라미터 처리
            passthrough_keys = {"max_tokens", "top_p", "frequency_penalty", "context_window"}
            for k in passthrough_keys & kwargs.keys():
                params[k] = kwargs[k]

            # 타임아웃 설정
            request_timeout = timeout or config.api.timeout

            logger.info(f"RAG request params: {params}")
            logger.info(f"Using timeout: {request_timeout} seconds")

            response = self._make_request(
                "POST",
                Constants.Endpoints.RAG_ANSWER,
                params=params,
                timeout=request_timeout
            )

            result = response.json()

            # 응답 로그 추가
            if "search_info" in result:
                search_info = result["search_info"]
                logger.info(f"RAG response: {search_info.get('total_results', 0)} results found")

            logger.info(f"Answer generated for query: '{query}'")
            return result

        except requests.exceptions.Timeout:
            logger.error(f"RAG request timeout after {request_timeout} seconds")
            return {
                "error": "응답 시간 초과",
                "question": query,
                "answer": "죄송합니다. 답변 생성에 시간이 너무 오래 걸려 중단되었습니다. 더 짧은 질문이나 구체적인 질문을 시도해보세요.",
                "sources": []
            }
        except Exception as e:
            logger.error(f"Answer generation failed: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "RAG 답변 생성")
            return {
                "error": str(e),
                "question": query,
                "answer": "죄송합니다. 답변 생성 중 오류가 발생했습니다.",
                "sources": []
            }

    @retry_on_failure()
    def health_check(self) -> Dict:
        """
        시스템 상태 확인 - 개선된 버전

        Returns:
            시스템 상태 정보
        """
        try:
            response = self._make_request("GET", Constants.Endpoints.HEALTH)
            data = response.json()

            # ✅ 1. 반환 타입 일관성 보장 -----------------------------
            if isinstance(data, str):
                # 백엔드가 "OK" 등 문자열만 주는 경우
                data = {"status": data}
            elif not isinstance(data, dict):
                # 예기치 않은 타입 보호
                data = {"status": Constants.Status.UNKNOWN,
                        "raw": data}

            # ✅ 2. 타임스탬프·기본 필드 보강 ------------------------
            data.setdefault("timestamp", datetime.now().isoformat())
            data.setdefault("services", {})
            logger.info("Health check completed")

            return data

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": Constants.Status.ERROR,
                "message": str(e),
                "services": {
                    "qdrant": {"status": Constants.Status.UNKNOWN},
                    "ollama": {"status": Constants.Status.UNKNOWN},
                    "celery": {"status": Constants.Status.UNKNOWN}
                },
                "timestamp": datetime.now().isoformat()
            }

    @retry_on_failure()
    def get_task_status(self, task_id: str) -> Dict:
        """
        비동기 작업 상태 확인

        Args:
            task_id: 작업 ID

        Returns:
            작업 상태 정보
        """
        try:
            response = self._make_request("GET", f"/v1/tasks/{task_id}")
            return response.json()

        except Exception as e:
            logger.error(f"Task status check failed: {str(e)}")
            return {
                "task_id": task_id,
                "status": Constants.Status.ERROR,
                "message": str(e)
            }

    @retry_on_failure()
    def get_collection_stats(self) -> Dict:
        """
        벡터 컬렉션 통계 조회

        Returns:
            컬렉션 통계 정보
        """
        try:
            response = self._make_request("GET", "/v1/collections/stats")
            return response.json()

        except Exception as e:
            logger.error(f"Collection stats retrieval failed: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "컬렉션 통계 조회")
            return {"error": str(e)}

    @retry_on_failure()
    def delete_document(self, document_id: str) -> Dict:
        """
        문서 삭제

        Args:
            document_id: 삭제할 문서 ID

        Returns:
            삭제 결과
        """
        try:
            response = self._make_request("DELETE", f"{Constants.Endpoints.DOCUMENTS}/{document_id}")
            result = response.json()
            logger.info(f"Document deleted: {document_id}")
            return result

        except Exception as e:
            logger.error(f"Document deletion failed: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, f"문서 삭제: {document_id}")
            return {"error": str(e), "deleted": False}

    @retry_on_failure()
    def batch_search(self, queries: List[str], top_k: int = None) -> List[List[Dict]]:
        """
        배치 검색 (여러 쿼리 동시 검색)

        Args:
            queries: 검색 쿼리 리스트
            top_k: 각 쿼리당 반환할 결과 수

        Returns:
            각 쿼리에 대한 검색 결과 리스트
        """
        if top_k is None:
            top_k = Constants.Defaults.TOP_K

        try:
            response = self._make_request(
                "POST",
                f"{Constants.Endpoints.SEARCH}/batch",
                json={
                    "queries": queries,
                    "top_k": top_k
                }
            )
            return response.json()

        except Exception as e:
            logger.error(f"Batch search failed: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "배치 검색")
            return [[] for _ in queries]

    def export_data(self, format: str = "json") -> Union[Dict, bytes]:
        """
        데이터 내보내기

        Args:
            format: 내보내기 형식 (json, csv, xlsx)

        Returns:
            내보낸 데이터
        """
        try:
            response = self._make_request(
                "GET",
                "/v1/export",
                params={"format": format}
            )

            if format == "json":
                return response.json()
            else:
                return response.content

        except Exception as e:
            logger.error(f"Data export failed: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "데이터 내보내기")
            return {"error": str(e)}

    @retry_on_failure()
    def update_settings(self, settings: Dict) -> Dict:
        """
        시스템 설정 업데이트

        Args:
            settings: 업데이트할 설정

        Returns:
            업데이트 결과
        """
        try:
            response = self._make_request(
                "PUT",
                Constants.Endpoints.SETTINGS,
                json=settings
            )
            result = response.json()
            logger.info("Settings updated successfully")
            return result

        except Exception as e:
            logger.error(f"Settings update failed: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "설정 업데이트")
            return {"error": str(e), "updated": False}

    def get_metrics(self, period: str = "1d") -> Dict:
        """
        시스템 메트릭 조회

        Args:
            period: 조회 기간 (1h, 1d, 1w, 1m)

        Returns:
            메트릭 데이터
        """
        try:
            response = self._make_request(
                "GET",
                "/v1/metrics",
                params={"period": period}
            )
            return response.json()

        except Exception as e:
            logger.error(f"Metrics retrieval failed: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "메트릭 조회")
            return {"error": str(e)}

    @retry_on_failure()
    def get_model_info(self, model_name: str) -> Dict:
        """
        특정 모델의 상세 정보 조회

        Args:
            model_name: 모델 이름

        Returns:
            모델 정보 딕셔너리
        """
        try:
            response = self._make_request("GET", f"{Constants.Endpoints.MODELS}/{model_name}")
            return response.json()

        except Exception as e:
            logger.error(f"Failed to retrieve model info for {model_name}: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, f"모델 정보 조회: {model_name}")
            return {"error": str(e)}

    def pull_model(self, model_name: str) -> Dict:
        """
        모델 다운로드/풀

        Args:
            model_name: 다운로드할 모델 이름

        Returns:
            다운로드 상태
        """
        try:
            response = self._make_request(
                "POST",
                f"{Constants.Endpoints.MODELS}/pull",
                json={"name": model_name}
            )
            return response.json()

        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, f"모델 다운로드: {model_name}")
            return {"error": str(e), "success": False}

    def delete_model(self, model_name: str) -> Dict:
        """
        모델 삭제

        Args:
            model_name: 삭제할 모델 이름

        Returns:
            삭제 결과
        """
        try:
            response = self._make_request("DELETE", f"{Constants.Endpoints.MODELS}/{model_name}")
            return response.json()

        except Exception as e:
            logger.error(f"Failed to delete model {model_name}: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, f"모델 삭제: {model_name}")
            return {"error": str(e), "success": False}

    @retry_on_failure()
    def get_available_models(self) -> List[str]:
        """
        사용 가능한 LLM 모델 목록 조회 - 개선된 버전

        Returns:
            모델 이름 리스트 (실패 시 빈 리스트)
        """
        try:
            response = self._make_request("GET", Constants.Endpoints.MODELS)
            result = response.json()

            # 응답 형식에 따라 처리
            if isinstance(result, list):
                models = result
            elif isinstance(result, dict):
                # 새로운 API 응답 형식
                if 'models' in result:
                    models = result['models']
                elif 'model_list' in result:
                    models = result['model_list']
                else:
                    models = []
            else:
                models = []

            logger.info(f"Retrieved {len(models)} available models")
            return models

        except Exception as e:
            logger.error(f"Failed to retrieve models: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "모델 목록 조회")
            return []

    def get_models_status(self) -> Dict:
        """
        모델 서버 상태 및 통계 조회

        Returns:
            모델 서버 상태 정보
        """
        try:
            response = self._make_request("GET", f"{Constants.Endpoints.MODELS}/status")
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get models status: {str(e)}")
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "모델 상태 조회")
            return {"error": str(e)}

    def close(self):
        """세션 종료"""
        self.session.close()
        logger.info("API Client session closed")

    def __enter__(self):
        """컨텍스트 매니저 진입"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.close()

    def get_connection_info(self) -> Dict:
        """연결 정보 반환"""
        return {
            "base_url": self.base_url,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "environment": config.environment.value,
            "session_active": bool(self.session)
        }

    # ===================================
    # ===================================
    #   🔧 시스템 설정 관련 API (NEW)
    # ===================================
    @retry_on_failure()
    def get_settings(self) -> Dict:
        """백엔드에 저장된 시스템 설정을 조회한다."""
        try:
            response = self._make_request(
                "GET",
                Constants.Endpoints.SETTINGS  # 사용중 점: "/v1/settings" 각정
            )
            settings = response.json() or {}
            logger.info("Settings retrieved successfully (%d keys)", len(settings))
            return settings

        except Exception as e:
            logger.error("Settings retrieval failed: %s", e)
            if HAS_ERROR_HANDLER:
                handle_api_error(e, "설정 조회")
            # 실패 시 기본값 사용을 위해 빈 dict 반환
            return {}

    # ===== 설정 저장 =====
    def update_settings(self, settings: Dict[str, Any]) -> None:
        """설정을 서버에 저장(전체 덮어쓰기)."""
        self._make_request(
            "PUT", Constants.Endpoints.SETTINGS, json=settings, timeout=5
        )

    def test_connection(self) -> Dict:
        """연결 테스트"""
        try:
            start_time = time.time()
            health_data = self.health_check()
            response_time = time.time() - start_time

            return {
                "success": True,
                "response_time": response_time,
                "health_data": health_data,
                "connection_info": self.get_connection_info()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "connection_info": self.get_connection_info()
            }
