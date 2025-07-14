"""
API 클라이언트 유틸리티
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

    def __init__(self, base_url: str = None, timeout: int = 30):
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

    # ui/utils/api_client.py
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
                        system_prompt: Optional[str] = None) -> Dict:
        """
        RAG 답변 생성

        Args:
            query: 사용자 질문
            top_k: 검색할 문서 수
            model: 사용할 LLM 모델
            temperature: 생성 온도
            system_prompt: 시스템 프롬프트

        Returns:
            답변 결과 (answer, sources, question)
        """
        try:
            params = {
                "q": query,
                "top_k": top_k
            }

            # 선택적 파라미터 추가
            if model:
                params["model"] = model
            if temperature is not None:
                params["temperature"] = temperature
            if system_prompt:
                params["system_prompt"] = system_prompt

            response = self._make_request(
                "POST",
                "/v1/rag/answer",
                params=params
            )

            result = response.json()
            logger.info(f"Answer generated for query: '{query}'")
            return result

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