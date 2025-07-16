"""
API 클라이언트 유틸리티 - 개선된 버전
Streamlit UI에서 백엔드 API와 통신하기 위한 클라이언트
"""
import requests
import os
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import json
import logging

# 로깅 설정
logger = logging.getLogger(__name__)


class APIClient:
    """GTOne RAG System API 클라이언트"""

    def __init__(self, base_url: str = None, timeout: int = 300):
        """
        API 클라이언트 초기화

        Args:
            base_url: API 서버 URL (기본값: 환경변수 또는 localhost)
            timeout: 요청 타임아웃 (초)
        """
        self.base_url = base_url or os.getenv("API_BASE_URL", "http://localhost:18000")
        self.timeout = timeout
        self.session = requests.Session()

        # 기본 헤더 설정
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

        logger.info(f"API Client initialized with base URL: {self.base_url}")

    def set_timeout(self, timeout: int):
        """타임아웃 설정 변경"""
        self.timeout = timeout
        logger.info(f"Timeout updated to {timeout} seconds")

    def list_documents(self) -> List[Dict]:
        try:
            res = self._make_request("GET", "/v1/documents")
            return res.json()
        except Exception as e:
            logger.error(f"Document list fetch error: {e}")
            return []

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        HTTP 요청 실행

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

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {method} {url}")
            raise
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error: {method} {url}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {method} {url} - {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {method} {url} - {e}")
            raise

    def upload_document(self, file, metadata: Optional[Dict] = None) -> Dict:
        """
        문서 업로드

        Args:
            file: 업로드할 파일 객체 (Streamlit UploadedFile)
            metadata: 추가 메타데이터

        Returns:
            업로드 결과 (uploaded: 청크 수)
        """
        try:
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
                "/v1/documents",
                files=files,
                data=data
            )

            result = response.json()
            logger.info(f"Document uploaded successfully: {file.name} -> {result.get('uploaded', 0)} chunks")
            return result

        except Exception as e:
            logger.error(f"Document upload failed: {str(e)}")
            return {"error": str(e), "uploaded": 0}

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
                "/v1/documents/async",
                files=files,
                data=data
            )

            return response.json()

        except Exception as e:
            logger.error(f"Async document upload failed: {str(e)}")
            return {"error": str(e), "task_id": None}

    def search(self, query: str, top_k: int = 3, filters: Optional[Dict] = None) -> List[Dict]:
        """
        문서 검색

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 수
            filters: 검색 필터 (언어, 날짜 등)

        Returns:
            검색 결과 리스트
        """
        try:
            params = {
                "q": query,
                "top_k": top_k
            }

            # 필터 추가
            if filters:
                if 'lang' in filters:
                    params['lang'] = filters['lang']
                if 'min_score' in filters:
                    params['min_score'] = filters['min_score']

            response = self._make_request("GET", "/v1/search", params=params)
            results = response.json()

            logger.info(f"Search completed: '{query}' -> {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return []

    def generate_answer(self, query: str, top_k: int = 3,
                        model: Optional[str] = None,
                        temperature: Optional[float] = None,
                        system_prompt: Optional[str] = None,
                        min_score: Optional[float] = None,
                        search_type: Optional[str] = None,
                        timeout: Optional[int] = None) -> Dict:
        """
        RAG 답변 생성

        Args:
            query: 사용자 질문
            top_k: 검색할 문서 수
            model: 사용할 LLM 모델
            temperature: 생성 온도
            system_prompt: 시스템 프롬프트
            min_score: 최소 유사도 점수 (기본값: 0.3)
            search_type: 검색 타입 (vector, hybrid, rerank)
            timeout: 요청 타임아웃 (초)

        Returns:
            답변 결과 (answer, sources, question)
        """
        try:
            params = {
                "q": query,
                "top_k": top_k
            }

            # 모델 파라미터 추가
            if model:
                params["model"] = model
                logger.info(f"Using model: {model}")

            if temperature is not None:
                params["temperature"] = temperature

            if system_prompt:
                params["system_prompt"] = system_prompt

            if min_score is not None:
                params["min_score"] = min_score

            if search_type is not None:
                params["search_type"] = search_type

            # 타임아웃 설정
            request_timeout = timeout or self.timeout

            logger.info(f"RAG request params: {params}")
            logger.info(f"Using timeout: {request_timeout} seconds")

            response = self._make_request(
                "POST",
                "/v1/rag/answer",
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
            return {
                "error": str(e),
                "question": query,
                "answer": "죄송합니다. 답변 생성 중 오류가 발생했습니다.",
                "sources": []
            }

    def health_check(self) -> Dict:
        """
        시스템 상태 확인

        Returns:
            시스템 상태 정보
        """
        try:
            response = self._make_request("GET", "/v1/health")
            health_data = response.json()

            logger.info("Health check completed successfully")
            return health_data

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "services": {
                    "qdrant": {"status": "unknown"},
                    "ollama": {"status": "unknown"},
                    "celery": {"status": "unknown"}
                }
            }

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
                "status": "error",
                "message": str(e)
            }

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
            return {"error": str(e)}

    def delete_document(self, document_id: str) -> Dict:
        """
        문서 삭제

        Args:
            document_id: 삭제할 문서 ID

        Returns:
            삭제 결과
        """
        try:
            response = self._make_request("DELETE", f"/v1/documents/{document_id}")
            return response.json()

        except Exception as e:
            logger.error(f"Document deletion failed: {str(e)}")
            return {"error": str(e), "deleted": False}

    def batch_search(self, queries: List[str], top_k: int = 3) -> List[List[Dict]]:
        """
        배치 검색 (여러 쿼리 동시 검색)

        Args:
            queries: 검색 쿼리 리스트
            top_k: 각 쿼리당 반환할 결과 수

        Returns:
            각 쿼리에 대한 검색 결과 리스트
        """
        try:
            response = self._make_request(
                "POST",
                "/v1/search/batch",
                json={
                    "queries": queries,
                    "top_k": top_k
                }
            )
            return response.json()

        except Exception as e:
            logger.error(f"Batch search failed: {str(e)}")
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
            return {"error": str(e)}

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
                "/v1/settings",
                json=settings
            )
            return response.json()

        except Exception as e:
            logger.error(f"Settings update failed: {str(e)}")
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

    def get_model_info(self, model_name: str) -> Dict:
        """
        특정 모델의 상세 정보 조회

        Args:
            model_name: 모델 이름

        Returns:
            모델 정보 딕셔너리
        """
        try:
            response = self._make_request("GET", f"/v1/models/{model_name}")
            return response.json()

        except Exception as e:
            logger.error(f"Failed to retrieve model info for {model_name}: {str(e)}")
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
                "/v1/models/pull",
                json={"name": model_name}
            )
            return response.json()

        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {str(e)}")
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
            response = self._make_request("DELETE", f"/v1/models/{model_name}")
            return response.json()

        except Exception as e:
            logger.error(f"Failed to delete model {model_name}: {str(e)}")
            return {"error": str(e), "success": False}

    def get_available_models(self) -> List[str]:
        """
        사용 가능한 LLM 모델 목록 조회

        Returns:
            모델 이름 리스트 (실패 시 빈 리스트)
        """
        try:
            response = self._make_request("GET", "/v1/models")
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
            # ❌ 하드코딩된 기본 모델 목록 제거 - 실패 시 빈 리스트 반환
            return []

    def get_models_status(self) -> Dict:
        """
        모델 서버 상태 및 통계 조회

        Returns:
            모델 서버 상태 정보
        """
        try:
            response = self._make_request("GET", "/v1/models/status")
            return response.json()

        except Exception as e:
            logger.error(f"Failed to get models status: {str(e)}")
            return {"error": str(e)}

    
# 간단한 사용을 위한 싱글톤 인스턴스
_default_client = None


def get_default_client() -> APIClient:
    """기본 API 클라이언트 인스턴스 반환"""
    global _default_client
    if _default_client is None:
        _default_client = APIClient()
    return _default_client


# 편의 함수들
def upload_document(file, metadata: Optional[Dict] = None) -> Dict:
    """문서 업로드 (기본 클라이언트 사용)"""
    return get_default_client().upload_document(file, metadata)


def search(query: str, top_k: int = 3, filters: Optional[Dict] = None) -> List[Dict]:
    """문서 검색 (기본 클라이언트 사용)"""
    return get_default_client().search(query, top_k, filters)


def generate_answer(query: str, top_k: int = 3, model: Optional[str] = None) -> Dict:
    """RAG 답변 생성 (기본 클라이언트 사용)"""
    return get_default_client().generate_answer(query, top_k, model)


def health_check() -> Dict:
    """시스템 상태 확인 (기본 클라이언트 사용)"""
    return get_default_client().health_check()


def get_available_models() -> List[str]:
    """사용 가능한 모델 목록 조회 (기본 클라이언트 사용)"""
    return get_default_client().get_available_models()

def get_model_info(model_name: str) -> Dict:
    """모델 정보 조회 (기본 클라이언트 사용)"""
    return get_default_client().get_model_info(model_name)