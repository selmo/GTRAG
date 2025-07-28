"""
HTTP 요청/응답 로깅 미들웨어
"""
import time
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse

from backend.core.logging import get_logger, log_http_request
from backend.core.request_context import set_request_id, generate_request_id


class LoggingMiddleware(BaseHTTPMiddleware):
    """HTTP 요청/응답을 로깅하는 미들웨어"""

    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.logger = get_logger("http")
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/favicon.ico"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 요청 ID 생성 및 설정
        request_id = generate_request_id()
        set_request_id(request_id)

        # 제외 경로 체크
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # 요청 시작 시간
        start_time = time.time()

        # 요청 정보 수집
        method = request.method
        url = str(request.url)
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        # 요청 바디 크기 계산
        request_size = await self._get_request_size(request)

        # 요청 시작 로깅
        self.logger.info(
            f"HTTP request started: {method} {url}",
            extra={
                "event_type": "http_request_start",
                "request_id": request_id,
                "method": method,
                "url": url,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "request_size_bytes": request_size
            }
        )

        # 요청 처리
        try:
            response = await call_next(request)

            # 응답 시간 계산
            process_time = time.time() - start_time

            # 응답 크기 계산
            response_size = await self._get_response_size(response)

            # HTTP 요청/응답 로깅
            log_http_request(
                self.logger,
                method=method,
                url=url,
                status_code=response.status_code,
                response_time=process_time,
                request_size=request_size,
                response_size=response_size,
                client_ip=client_ip,
                user_agent=user_agent,
                metadata={
                    "request_id": request_id,
                    "response_headers": dict(response.headers)
                }
            )

            # 응답 헤더에 요청 ID 추가
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # 에러 시간 계산
            process_time = time.time() - start_time

            # 에러 로깅
            self.logger.error(
                f"HTTP request failed: {method} {url}",
                extra={
                    "event_type": "http_request_error",
                    "request_id": request_id,
                    "method": method,
                    "url": url,
                    "client_ip": client_ip,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "response_time_seconds": round(process_time, 3)
                },
                exc_info=True
            )
            raise

    def _get_client_ip(self, request: Request) -> str:
        """클라이언트 IP 주소 추출"""
        # X-Forwarded-For 헤더 확인 (프록시 환경)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # X-Real-IP 헤더 확인
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # 직접 연결
        if request.client:
            return request.client.host

        return "unknown"

    async def _get_request_size(self, request: Request) -> int:
        """요청 바디 크기 계산"""
        try:
            content_length = request.headers.get("content-length")
            if content_length:
                return int(content_length)

            # Content-Length가 없는 경우 바디 읽기 시도
            body = await request.body()
            return len(body) if body else 0

        except Exception:
            return 0

    async def _get_response_size(self, response: Response) -> int:
        """응답 크기 계산"""
        try:
            if hasattr(response, 'body') and response.body:
                return len(response.body)

            # StreamingResponse인 경우
            if isinstance(response, StreamingResponse):
                content_length = response.headers.get("content-length")
                if content_length:
                    return int(content_length)

            return 0

        except Exception:
            return 0


class DetailedLoggingMiddleware(BaseHTTPMiddleware):
    """상세한 요청/응답 데이터를 로깅하는 미들웨어 (개발/디버깅용)"""

    def __init__(self, app, log_body: bool = False, max_body_size: int = 1024):
        super().__init__(app)
        self.logger = get_logger("http_detailed")
        self.log_body = log_body
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 요청 헤더 로깅
        request_headers = dict(request.headers)
        self.logger.debug(
            "Request headers",
            extra={
                "event_type": "request_headers",
                "headers": request_headers,
                "method": request.method,
                "url": str(request.url)
            }
        )

        # 요청 바디 로깅 (선택적)
        if self.log_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body and len(body) <= self.max_body_size:
                    try:
                        # JSON 파싱 시도
                        body_data = json.loads(body.decode('utf-8'))
                        self.logger.debug(
                            "Request body (JSON)",
                            extra={
                                "event_type": "request_body",
                                "body": body_data,
                                "content_type": request.headers.get("content-type")
                            }
                        )
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # 텍스트로 로깅
                        self.logger.debug(
                            "Request body (text)",
                            extra={
                                "event_type": "request_body",
                                "body": body.decode('utf-8', errors='ignore')[:self.max_body_size],
                                "content_type": request.headers.get("content-type")
                            }
                        )
            except Exception as e:
                self.logger.warning(f"Failed to log request body: {e}")

        response = await call_next(request)

        # 응답 헤더 로깅
        response_headers = dict(response.headers)
        self.logger.debug(
            "Response headers",
            extra={
                "event_type": "response_headers",
                "headers": response_headers,
                "status_code": response.status_code
            }
        )

        return response