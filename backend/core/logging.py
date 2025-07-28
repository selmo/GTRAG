"""
구조화된 로깅 시스템 - JSON 포맷, 타임스탬프, 요청 ID 트래킹
"""
import logging
import logging.handlers
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path
import uuid

try:
    from pythonjsonlogger import jsonlogger

    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False


class TimestampJSONFormatter(jsonlogger.JsonFormatter if HAS_JSON_LOGGER else logging.Formatter):
    """타임스탬프가 포함된 JSON 로그 포매터"""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # 한국 시간대 타임스탬프 추가
        now = datetime.now(timezone.utc)
        log_record['timestamp'] = now.isoformat()
        log_record['timestamp_unix'] = now.timestamp()

        # 로그 레벨 추가
        log_record['level'] = record.levelname
        log_record['logger'] = record.name

        # 요청 ID가 있다면 추가
        from backend.core.request_context import get_request_id
        request_id = get_request_id()
        if request_id:
            log_record['request_id'] = request_id


class RAGLogger:
    """RAG 시스템 전용 로거 클래스"""

    def __init__(self):
        self.loggers = {}
        self._setup_log_directory()

    def _setup_log_directory(self):
        """로그 디렉토리 생성"""
        log_dir = Path("./logs")
        log_dir.mkdir(exist_ok=True)

    def get_logger(self, name: str) -> logging.Logger:
        """컴포넌트별 로거 반환"""
        if name not in self.loggers:
            self.loggers[name] = self._create_logger(name)
        return self.loggers[name]

    def _create_logger(self, name: str) -> logging.Logger:
        """로거 생성 및 설정"""
        logger = logging.getLogger(f"rag.{name}")
        logger.setLevel(logging.INFO)

        # 중복 핸들러 방지
        if logger.handlers:
            return logger

        # JSON 파일 핸들러
        if HAS_JSON_LOGGER:
            json_handler = self._create_json_file_handler(name)
            logger.addHandler(json_handler)

        # 콘솔 핸들러
        console_handler = self._create_console_handler()
        logger.addHandler(console_handler)

        # 에러 전용 파일 핸들러
        error_handler = self._create_error_file_handler()
        logger.addHandler(error_handler)

        return logger

    def _create_json_file_handler(self, name: str) -> logging.Handler:
        """JSON 파일 핸들러 생성"""
        log_file = f"./logs/{name}.json"
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=5,
            encoding='utf-8'
        )

        formatter = TimestampJSONFormatter(
            '%(timestamp)s %(level)s %(logger)s %(message)s'
        )
        handler.setFormatter(formatter)
        handler.setLevel(logging.INFO)

        return handler

    def _create_console_handler(self) -> logging.Handler:
        """콘솔 핸들러 생성"""
        handler = logging.StreamHandler()

        if HAS_JSON_LOGGER:
            formatter = TimestampJSONFormatter(
                '%(timestamp)s %(level)s %(logger)s %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

        handler.setFormatter(formatter)
        handler.setLevel(logging.INFO)

        return handler

    def _create_error_file_handler(self) -> logging.Handler:
        """에러 전용 파일 핸들러"""
        handler = logging.handlers.RotatingFileHandler(
            "./logs/errors.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=3,
            encoding='utf-8'
        )

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(exc_info)s'
        )
        handler.setFormatter(formatter)
        handler.setLevel(logging.ERROR)

        return handler


# 전역 로거 인스턴스
rag_logger = RAGLogger()


def get_logger(component: str) -> logging.Logger:
    """컴포넌트별 로거 반환"""
    return rag_logger.get_logger(component)


def log_llm_interaction(
        logger: logging.Logger,
        prompt: str,
        response: str,
        model: str,
        temperature: float,
        execution_time: float,
        metadata: Optional[Dict[str, Any]] = None
):
    """LLM 상호작용 로깅"""
    log_data = {
        "event_type": "llm_interaction",
        "model": model,
        "temperature": temperature,
        "execution_time_seconds": round(execution_time, 3),
        "prompt_length": len(prompt),
        "response_length": len(response),
        "prompt_preview": prompt[:200] + "..." if len(prompt) > 200 else prompt,
        "response_preview": response[:200] + "..." if len(response) > 200 else response,
        "full_prompt": prompt,
        "full_response": response,
        "metadata": metadata or {}
    }

    logger.info("LLM interaction completed", extra=log_data)


def log_document_processing(
        logger: logging.Logger,
        filename: str,
        file_size: int,
        chunks_created: int,
        processing_time: float,
        doc_id: str,
        metadata: Optional[Dict[str, Any]] = None
):
    """문서 처리 로깅"""
    log_data = {
        "event_type": "document_processing",
        "document_filename": filename,
        "file_size_bytes": file_size,
        "chunks_created": chunks_created,
        "processing_time_seconds": round(processing_time, 3),
        "doc_id": doc_id,
        "chunks_per_kb": round(chunks_created / (file_size / 1024), 2) if file_size > 0 else 0,
        "metadata": metadata or {}
    }

    logger.info("Document processing completed", extra=log_data)


def log_search_operation(
        logger: logging.Logger,
        query: str,
        search_type: str,
        results_count: int,
        execution_time: float,
        top_k: int,
        metadata: Optional[Dict[str, Any]] = None
):
    """검색 작업 로깅"""
    log_data = {
        "event_type": "search_operation",
        "query": query,
        "query_length": len(query),
        "search_type": search_type,
        "results_count": results_count,
        "top_k": top_k,
        "execution_time_seconds": round(execution_time, 3),
        "hit_rate": round(results_count / top_k, 2) if top_k > 0 else 0,
        "metadata": metadata or {}
    }

    logger.info("Search operation completed", extra=log_data)


def log_http_request(
        logger: logging.Logger,
        method: str,
        url: str,
        status_code: int,
        response_time: float,
        request_size: int,
        response_size: int,
        client_ip: str,
        user_agent: str = None,
        metadata: Optional[Dict[str, Any]] = None
):
    """HTTP 요청/응답 로깅"""
    log_data = {
        "event_type": "http_request",
        "method": method,
        "url": url,
        "status_code": status_code,
        "response_time_ms": round(response_time * 1000, 2),
        "request_size_bytes": request_size,
        "response_size_bytes": response_size,
        "client_ip": client_ip,
        "user_agent": user_agent,
        "success": 200 <= status_code < 400,
        "metadata": metadata or {}
    }

    logger.info("HTTP request processed", extra=log_data)