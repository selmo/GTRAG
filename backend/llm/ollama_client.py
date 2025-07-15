"""
Ollama API 클라이언트 - 간소화 버전
"""
import requests
import logging
import os
from typing import List, Dict

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama API 클라이언트 - 조회 기능만"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.session = requests.Session()

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """HTTP 요청 실행"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"Ollama API request failed: {method} {url} - {e}")
            raise

    def list_models(self) -> List[Dict]:
        """설치된 모델 목록 조회"""
        try:
            response = self._make_request("GET", "/api/tags")
            data = response.json()
            return data.get("models", [])
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def get_model_info(self, model_name: str) -> Dict:
        """모델 상세 정보 조회"""
        try:
            response = self._make_request("POST", "/api/show", json={"name": model_name})
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get model info for {model_name}: {e}")
            return {"error": str(e)}

    def check_connection(self) -> Dict:
        """연결 상태 확인"""
        try:
            response = self._make_request("GET", "/api/tags")
            models = response.json().get("models", [])
            return {
                "status": "connected",
                "host": self.base_url,
                "models": [model.get("name", "") for model in models],
                "total_models": len(models)
            }
        except Exception as e:
            return {
                "status": "disconnected",
                "host": self.base_url,
                "error": str(e),
                "models": [],
                "total_models": 0
            }


# 싱글톤 인스턴스
_default_client = None


def get_ollama_client() -> OllamaClient:
    """기본 Ollama 클라이언트 반환"""
    global _default_client
    if _default_client is None:
        _default_client = OllamaClient()
    return _default_client