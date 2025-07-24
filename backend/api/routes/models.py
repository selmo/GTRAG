# backend/api/routes/models.py - 라우터 순서 수정

from fastapi import APIRouter, HTTPException
import requests
import urllib.parse
import logging
from typing import List, Dict, Any

router = APIRouter()
logger = logging.getLogger(__name__)

# Ollama 서버 URL - 포트 11434 (기본값)
OLLAMA_BASE_URL = "http://localhost:11434"


# ⚠️ 중요: 구체적인 경로들을 먼저 정의해야 합니다!

@router.get("/v1/models/debug", summary="모델 API 디버깅")
async def debug_models():
    """모델 API 디버깅 정보를 제공합니다."""
    debug_info = {
        "ollama_url": OLLAMA_BASE_URL,
        "backend_port": "18000",  # 실제 포트 반영
        "tests": {}
    }

    try:
        # Ollama 연결 테스트
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        debug_info["tests"]["ollama_connection"] = {
            "status": "success" if response.status_code == 200 else "failed",
            "status_code": response.status_code,
            "response_size": len(response.content) if response.content else 0
        }

        if response.status_code == 200:
            data = response.json()
            models = [m.get("name", "Unknown") for m in data.get("models", [])]
            debug_info["tests"]["ollama_data"] = {
                "status": "success",
                "models_count": len(models),
                "models_list": models,
                "raw_response": data
            }

    except Exception as e:
        debug_info["tests"]["ollama_connection"] = {
            "status": "failed",
            "error": str(e),
            "error_type": type(e).__name__
        }

    return debug_info


@router.get("/v1/models/status", summary="모델 서버 상태 조회")
async def get_models_status():
    """Ollama 서버 상태를 조회합니다."""
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)

        if response.status_code == 200:
            data = response.json()
            models = [m.get("name", "Unknown") for m in data.get("models", [])]

            return {
                "status": "healthy",
                "ollama_url": OLLAMA_BASE_URL,
                "model_count": len(models),
                "connection": "success",
                "models": models
            }
        else:
            return {
                "status": "error",
                "ollama_url": OLLAMA_BASE_URL,
                "error": f"HTTP {response.status_code}",
                "connection": "failed"
            }

    except requests.exceptions.ConnectionError:
        return {
            "status": "disconnected",
            "ollama_url": OLLAMA_BASE_URL,
            "error": "Connection refused",
            "connection": "failed"
        }

    except Exception as e:
        return {
            "status": "error",
            "ollama_url": OLLAMA_BASE_URL,
            "error": str(e),
            "connection": "failed"
        }


@router.get("/v1/models", summary="사용 가능한 모델 목록 조회")
async def get_models():
    """Ollama에서 사용 가능한 모델 목록을 조회합니다."""
    try:
        logger.info(f"Requesting models from Ollama: {OLLAMA_BASE_URL}/api/tags")

        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)

        if response.status_code == 200:
            data = response.json()
            models = []

            logger.info(f"Ollama response: {data}")

            # Ollama API 응답 형식에 따라 처리
            if "models" in data:
                for model in data["models"]:
                    if "name" in model:
                        models.append(model["name"])

            logger.info(f"Retrieved {len(models)} models from Ollama: {models}")
            return models

        else:
            logger.error(f"Ollama API error: {response.status_code} - {response.text}")
            raise HTTPException(502, f"Ollama 서버 오류: {response.status_code}")

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Cannot connect to Ollama server at {OLLAMA_BASE_URL}: {e}")
        raise HTTPException(503, f"Ollama 서버에 연결할 수 없습니다. {OLLAMA_BASE_URL}이 실행 중인지 확인하세요.")

    except requests.exceptions.Timeout as e:
        logger.error(f"Ollama server timeout: {e}")
        raise HTTPException(504, "Ollama 서버 응답 시간 초과")

    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        raise HTTPException(500, f"모델 목록 조회 실패: {str(e)}")


# ⚠️ 동적 경로는 마지막에 정의
@router.get("/v1/models/{model_name}", summary="특정 모델 정보 조회")
async def get_model_info(model_name: str):
    """특정 모델의 상세 정보를 조회합니다."""
    try:
        # URL 디코딩
        decoded_model = urllib.parse.unquote(model_name)
        logger.info(f"Getting info for model: {decoded_model}")

        # Ollama에서 모델 목록을 가져와서 해당 모델 찾기
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)

        if response.status_code == 200:
            data = response.json()

            if "models" in data:
                for model in data["models"]:
                    if model.get("name") == decoded_model:
                        logger.info(f"Found model info for: {decoded_model}")
                        return model

                # 모델을 찾지 못한 경우
                available_models = [m.get("name", "Unknown") for m in data["models"]]
                logger.warning(f"Model not found: {decoded_model}")
                raise HTTPException(
                    404,
                    f"모델 '{decoded_model}'을 찾을 수 없습니다. 사용 가능한 모델: {available_models}"
                )
            else:
                logger.error("No models in Ollama response")
                raise HTTPException(500, "Ollama 응답 형식이 올바르지 않습니다")
        else:
            logger.error(f"Ollama API error: {response.status_code}")
            raise HTTPException(502, f"Ollama 서버 오류: {response.status_code}")

    except HTTPException:
        raise

    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to Ollama server")
        raise HTTPException(503, "Ollama 서버에 연결할 수 없습니다")

    except requests.exceptions.Timeout:
        logger.error("Ollama server timeout")
        raise HTTPException(504, "Ollama 서버 응답 시간 초과")

    except Exception as e:
        logger.error(f"Failed to get model info for {decoded_model}: {e}")
        raise HTTPException(500, f"모델 정보 조회 실패: {str(e)}")


@router.post("/v1/models/pull", summary="모델 다운로드")
async def pull_model(request: Dict[str, str]):
    """새 모델을 다운로드합니다."""
    try:
        model_name = request.get("name")
        if not model_name:
            raise HTTPException(400, "모델 이름이 필요합니다")

        logger.info(f"Pulling model: {model_name}")

        # Ollama pull API 호출
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/pull",
            json={"name": model_name},
            timeout=300  # 5분 타임아웃
        )

        if response.status_code == 200:
            logger.info(f"Model {model_name} pulled successfully")
            return {"success": True, "message": f"모델 '{model_name}' 다운로드 완료"}
        else:
            logger.error(f"Model pull failed: {response.text}")
            raise HTTPException(502, f"모델 다운로드 실패: {response.text}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Model pull failed: {e}")
        raise HTTPException(500, f"모델 다운로드 실패: {str(e)}")