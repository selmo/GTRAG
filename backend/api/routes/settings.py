from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ValidationError
from typing import Dict, Any, Optional
from backend.core.config import _load_settings, save_settings, get_settings_file_info, validate_settings_file
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)


# 설정 스키마 정의
class SettingsUpdateModel(BaseModel):
    ollama_host: Optional[str] = None
    ollama_model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_k: Optional[int] = None

    class Config:
        extra = "allow"  # 추가 필드 허용


@router.get("/v1/settings", summary="현재 런타임 설정 조회")
async def get_settings():
    """현재 설정을 조회합니다."""
    try:
        settings = _load_settings()
        logger.info(f"Settings retrieved successfully: {len(settings)} keys")
        return settings
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        raise HTTPException(500, f"설정 조회 실패: {str(e)}")


@router.put("/v1/settings", summary="런타임 설정 갱신")
async def put_settings(request: Request, payload: Dict[str, Any]):
    """설정을 업데이트합니다."""
    try:
        # 요청 로깅
        client_ip = request.client.host if request.client else "unknown"
        logger.info(f"Settings update request from {client_ip}: {list(payload.keys())}")

        # 빈 payload 확인
        if not payload:
            logger.warning("Empty payload received for settings update")
            return {"status": "ok", "message": "빈 설정이 전달되었습니다"}

        # 데이터 검증
        validated_data = {}
        for key, value in payload.items():
            # None 값 제거
            if value is not None:
                validated_data[key] = value

        if not validated_data:
            logger.warning("All payload values were None")
            return {"status": "ok", "message": "유효한 설정값이 없습니다"}

        # 설정 저장
        logger.info(f"Saving validated settings: {list(validated_data.keys())}")
        save_settings(validated_data)

        logger.info("Settings saved successfully")
        return {
            "status": "ok",
            "message": "설정이 성공적으로 저장되었습니다",
            "updated_keys": list(validated_data.keys())
        }

    except ValidationError as e:
        logger.error(f"Settings validation error: {e}")
        raise HTTPException(400, f"설정 검증 실패: {str(e)}")

    except FileNotFoundError as e:
        logger.error(f"Settings file not found: {e}")
        raise HTTPException(500, "설정 파일을 찾을 수 없습니다")

    except PermissionError as e:
        logger.error(f"Settings file permission error: {e}")
        raise HTTPException(500, "설정 파일 쓰기 권한이 없습니다")

    except Exception as e:
        logger.error(f"Unexpected error during settings update: {e}")
        raise HTTPException(500, f"설정 저장 중 오류가 발생했습니다: {str(e)}")


@router.post("/v1/settings/test", summary="설정 엔드포인트 테스트")
async def test_settings():
    """설정 엔드포인트가 정상 작동하는지 테스트합니다."""
    try:
        # 설정 조회 테스트
        current_settings = _load_settings()

        # 빈 설정 저장 테스트
        save_settings({})

        return {
            "status": "ok",
            "message": "설정 엔드포인트가 정상 작동합니다",
            "current_settings_count": len(current_settings),
            "test_passed": True
        }
    except Exception as e:
        logger.error(f"Settings endpoint test failed: {e}")
        return {
            "status": "error",
            "message": f"설정 엔드포인트 테스트 실패: {str(e)}",
            "test_passed": False
        }


@router.get("/v1/settings/validate", summary="설정 검증")
async def validate_settings():
    """현재 설정이 유효한지 검증합니다."""
    try:
        settings = _load_settings()

        # 기본 검증
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        # Ollama Host 검증
        if "ollama_host" in settings:
            host = settings["ollama_host"]
            if not isinstance(host, str) or not host.strip():
                validation_results["errors"].append("ollama_host가 유효하지 않습니다")
                validation_results["valid"] = False

        # 모델 검증
        if "ollama_model" in settings:
            model = settings["ollama_model"]
            if not isinstance(model, str) or not model.strip():
                validation_results["warnings"].append("ollama_model이 설정되지 않았습니다")

        return validation_results

    except Exception as e:
        logger.error(f"Settings validation failed: {e}")
        raise HTTPException(500, f"설정 검증 실패: {str(e)}")


@router.get("/v1/settings/debug", summary="설정 파일 디버깅 정보")
async def debug_settings():
    """설정 파일 로딩/저장 상태를 디버깅합니다."""
    try:
        # 현재 로딩된 설정
        current_settings = _load_settings()

        # 파일 정보
        file_info = get_settings_file_info()

        # 파일 유효성 검사
        validation = validate_settings_file()

        return {
            "status": "success",
            "current_settings": current_settings,
            "file_info": file_info,
            "validation": validation,
            "settings_count": len(current_settings)
        }

    except Exception as e:
        logger.error(f"Settings debug failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }


@router.post("/v1/settings/reload", summary="설정 파일 강제 재로딩")
async def reload_settings():
    """설정 파일을 강제로 다시 로딩합니다."""
    try:
        # 설정 강제 재로딩
        reloaded_settings = _load_settings()

        return {
            "status": "success",
            "message": "설정이 성공적으로 재로딩되었습니다",
            "settings": reloaded_settings,
            "settings_count": len(reloaded_settings)
        }

    except Exception as e:
        logger.error(f"Settings reload failed: {e}")
        return {
            "status": "error",
            "message": f"설정 재로딩 실패: {str(e)}"
        }


@router.get("/v1/settings/file-content", summary="설정 파일 내용 직접 조회")
async def get_settings_file_content():
    """설정 파일의 실제 내용을 직접 조회합니다."""
    import os

    settings_path = "./data/settings.json"

    try:
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                file_content = f.read()

            try:
                parsed_content = json.loads(file_content)
                return {
                    "status": "success",
                    "file_exists": True,
                    "file_path": settings_path,
                    "raw_content": file_content,
                    "parsed_content": parsed_content,
                    "file_size": len(file_content)
                }
            except json.JSONDecodeError as e:
                return {
                    "status": "error",
                    "file_exists": True,
                    "file_path": settings_path,
                    "raw_content": file_content,
                    "error": f"JSON 파싱 오류: {str(e)}"
                }
        else:
            return {
                "status": "error",
                "file_exists": False,
                "file_path": settings_path,
                "error": "설정 파일이 존재하지 않습니다"
            }

    except Exception as e:
        return {
            "status": "error",
            "file_path": settings_path,
            "error": f"파일 읽기 오류: {str(e)}"
        }