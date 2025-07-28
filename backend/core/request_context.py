"""
요청 ID 컨텍스트 관리 - FastAPI 요청별 추적
"""
from contextvars import ContextVar
from typing import Optional
import uuid

# 요청 ID를 저장하는 컨텍스트 변수
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


def generate_request_id() -> str:
    """새로운 요청 ID 생성"""
    return str(uuid.uuid4())


def set_request_id(request_id: str) -> None:
    """현재 컨텍스트에 요청 ID 설정"""
    request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    """현재 컨텍스트의 요청 ID 반환"""
    return request_id_var.get()


def get_or_create_request_id() -> str:
    """요청 ID 반환, 없으면 새로 생성"""
    current_id = get_request_id()
    if not current_id:
        current_id = generate_request_id()
        set_request_id(current_id)
    return current_id