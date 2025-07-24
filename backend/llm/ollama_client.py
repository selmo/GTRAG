"""
Ollama API 클라이언트 - 텍스트 생성 기능 추가
"""
import requests
import logging
import os
from typing import List, Dict, Optional, Any
import json

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama API 클라이언트 - 조회 및 생성 기능"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.session = requests.Session()

        # 기본 헤더 설정
        self.session.headers.update({
            "Content-Type": "application/json"
        })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """HTTP 요청 실행"""
        url = f"{self.base_url}{endpoint}"

        # 타임아웃 기본값 설정
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 60  # 텍스트 생성은 시간이 걸릴 수 있음

        try:
            logger.debug(f"Making {method} request to {url}")
            if 'json' in kwargs:
                logger.debug(f"Request data: {kwargs['json']}")

            response = self.session.request(method, url, **kwargs)

            logger.debug(f"Response status: {response.status_code}")
            response.raise_for_status()
            return response

        except requests.exceptions.Timeout as e:
            logger.error(f"Ollama API timeout: {method} {url} - {e}")
            raise Exception(f"Ollama 서버 응답 시간 초과 ({kwargs.get('timeout')}초)")

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Ollama API connection error: {method} {url} - {e}")
            raise Exception(f"Ollama 서버에 연결할 수 없습니다 ({self.base_url})")

        except requests.exceptions.HTTPError as e:
            logger.error(f"Ollama API HTTP error: {method} {url} - {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    raise Exception(f"Ollama API 오류: {error_detail}")
                except:
                    raise Exception(f"Ollama API HTTP {e.response.status_code} 오류")
            raise Exception(f"Ollama API 오류: {str(e)}")

        except Exception as e:
            logger.error(f"Ollama API request failed: {method} {url} - {e}")
            raise

    def list_models(self) -> List[Dict]:
        """설치된 모델 목록 조회"""
        try:
            response = self._make_request("GET", "/api/tags", timeout=10)
            data = response.json()
            models = data.get("models", [])
            logger.info(f"Retrieved {len(models)} models from Ollama")
            return models
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def get_model_info(self, model_name: str) -> Dict:
        """모델 상세 정보 조회"""
        try:
            response = self._make_request("POST", "/api/show",
                                        json={"name": model_name},
                                        timeout=15)
            result = response.json()
            logger.info(f"Retrieved info for model: {model_name}")
            return result
        except Exception as e:
            logger.error(f"Failed to get model info for {model_name}: {e}")
            return {"error": str(e)}

    def generate(self,
                model: str,
                prompt: str,
                system: Optional[str] = None,
                options: Optional[Dict[str, Any]] = None,
                stream: bool = False) -> Dict[str, Any]:
        """
        텍스트 생성

        Args:
            model: 사용할 모델명
            prompt: 입력 프롬프트
            system: 시스템 메시지 (선택사항)
            options: 생성 옵션 (temperature, num_predict 등)
            stream: 스트리밍 여부 (현재는 False만 지원)

        Returns:
            생성 결과 딕셔너리
        """
        try:
            # 요청 데이터 구성
            request_data = {
                "model": model,
                "prompt": prompt,
                "stream": stream
            }

            if system:
                request_data["system"] = system

            if options:
                request_data["options"] = options

            logger.info(f"Generating text with model: {model}")
            logger.debug(f"Prompt length: {len(prompt)} characters")

            # API 호출
            response = self._make_request("POST", "/api/generate",
                                        json=request_data,
                                        timeout=120)  # 긴 텍스트 생성을 위해 타임아웃 증가

            result = response.json()

            # 응답 검증
            if not result.get("response"):
                logger.warning("Empty response from Ollama")
                return {
                    "response": "죄송합니다. 모델에서 응답을 생성하지 못했습니다.",
                    "model": model,
                    "done": True
                }

            logger.info(f"Text generation completed. Response length: {len(result.get('response', ''))}")
            return result

        except Exception as e:
            logger.error(f"Text generation failed for model {model}: {e}")
            # 사용자 친화적인 오류 메시지 반환
            return {
                "response": f"텍스트 생성 중 오류가 발생했습니다: {str(e)}",
                "model": model,
                "done": True,
                "error": str(e)
            }

    def chat(self,
             model: str,
             messages: List[Dict[str, str]],
             options: Optional[Dict[str, Any]] = None,
             stream: bool = False) -> Dict[str, Any]:
        """
        채팅 형식 대화 생성

        Args:
            model: 사용할 모델명
            messages: 메시지 목록 [{"role": "user/assistant", "content": "..."}]
            options: 생성 옵션
            stream: 스트리밍 여부

        Returns:
            채팅 응답 딕셔너리
        """
        try:
            request_data = {
                "model": model,
                "messages": messages,
                "stream": stream
            }

            if options:
                request_data["options"] = options

            logger.info(f"Chat generation with model: {model}, messages: {len(messages)}")

            response = self._make_request("POST", "/api/chat",
                                        json=request_data,
                                        timeout=120)

            result = response.json()
            logger.info("Chat generation completed")
            return result

        except Exception as e:
            logger.error(f"Chat generation failed for model {model}: {e}")
            return {
                "message": {
                    "role": "assistant",
                    "content": f"채팅 생성 중 오류가 발생했습니다: {str(e)}"
                },
                "model": model,
                "done": True,
                "error": str(e)
            }

    def check_connection(self) -> Dict:
        """연결 상태 확인"""
        try:
            response = self._make_request("GET", "/api/tags", timeout=10)
            models = response.json().get("models", [])
            return {
                "status": "connected",
                "host": self.base_url,
                "models": [model.get("name", "") for model in models],
                "total_models": len(models),
                "version": "ok"
            }
        except Exception as e:
            return {
                "status": "disconnected",
                "host": self.base_url,
                "error": str(e),
                "models": [],
                "total_models": 0
            }

    def pull_model(self, model_name: str) -> Dict[str, Any]:
        """
        모델 다운로드

        Args:
            model_name: 다운로드할 모델명

        Returns:
            다운로드 결과
        """
        try:
            logger.info(f"Pulling model: {model_name}")

            response = self._make_request("POST", "/api/pull",
                                        json={"name": model_name},
                                        timeout=600)  # 10분 타임아웃

            result = response.json()
            logger.info(f"Model {model_name} pulled successfully")
            return result

        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            return {"error": str(e)}

    def delete_model(self, model_name: str) -> Dict[str, Any]:
        """
        모델 삭제

        Args:
            model_name: 삭제할 모델명

        Returns:
            삭제 결과
        """
        try:
            logger.info(f"Deleting model: {model_name}")

            response = self._make_request("DELETE", "/api/delete",
                                        json={"name": model_name},
                                        timeout=30)

            result = response.json() if response.content else {"status": "success"}
            logger.info(f"Model {model_name} deleted successfully")
            return result

        except Exception as e:
            logger.error(f"Failed to delete model {model_name}: {e}")
            return {"error": str(e)}


# 싱글톤 인스턴스
_default_client = None


def get_ollama_client() -> OllamaClient:
    """기본 Ollama 클라이언트 반환"""
    global _default_client
    if _default_client is None:
        try:
            from backend.core.config import settings
            base_url = settings.ollama_host
        except:
            # 설정 로딩 실패 시 기본값 사용
            base_url = "http://localhost:11434"

        _default_client = OllamaClient(base_url=base_url)
        logger.info(f"Ollama client initialized with base URL: {base_url}")
    return _default_client


def reset_ollama_client():
    """클라이언트 인스턴스 초기화 (테스트용)"""
    global _default_client
    _default_client = None