"""
client_manager.py
=================
APIClient 싱글톤 매니저 - 최적화된 버전

모든 프론트엔드 컴포넌트가 **하나의** APIClient 인스턴스를 사용하도록 보장합니다.
불필요한 세션 생성·종료를 방지하여 네트워크 커넥션을 절약하고,
재시도 횟수·타임아웃 등 글로벌 설정을 일관되게 유지합니다.
"""
import threading
import logging
import time
from typing import Optional, Dict, Any


class ClientManager:
    """APIClient 싱글톤 관리 클래스 - 캐싱 최적화"""
    _lock = threading.Lock()
    _client = None
    _last_params_hash = None  # 🔧 파라미터 변경 감지
    _creation_time = None     # 🔧 생성 시간 추적

    """
    client_manager.py 수정 - 세션 상태 안전 처리
    기존 client_manager.py의 get_client 메서드를 다음으로 교체
    """

    @classmethod
    def get_client(cls, force_refresh: bool = False, **kwargs):
        """
        APIClient 인스턴스를 반환한다 - 세션 상태 안전 처리
        """
        with cls._lock:
            # 파라미터 해시 계산 (변경 감지용)
            current_params_hash = hash(frozenset(kwargs.items())) if kwargs else None

            # 🔧 세션 상태 안전 초기화
            try:
                import streamlit as st

                # 세션 상태가 올바른 타입인지 확인
                if not hasattr(st.session_state, 'setdefault'):
                    # 문제가 있으면 무시하고 계속
                    pass
                else:
                    # 안전하게 세션 상태 초기화
                    if 'api_client_cached' not in st.session_state:
                        st.session_state.api_client_cached = None

                    # 타입 검증: 문자열이면 None으로 초기화
                    if isinstance(st.session_state.get('api_client_cached'), str):
                        st.session_state.api_client_cached = None

            except Exception as e:
                # 세션 상태 문제가 있어도 클라이언트 생성은 계속
                logging.warning(f"세션 상태 초기화 실패: {e}")

            # 기존 클라이언트 재사용 조건 확인
            should_reuse = (
                    cls._client is not None and
                    not force_refresh and
                    not kwargs and  # 새 파라미터가 없음
                    cls._creation_time and
                    time.time() - cls._creation_time < 300  # 5분 이내 생성
            )

            # 파라미터 변경 감지
            if (kwargs and
                    cls._last_params_hash is not None and
                    current_params_hash != cls._last_params_hash):
                should_reuse = False
                logging.info("🔄 API 클라이언트 파라미터 변경 감지, 재생성")

            if should_reuse:
                logging.debug("♻️ 기존 API 클라이언트 재사용")
                return cls._client

            # ✅ 필요 시점에만 import → 순환차단
            from frontend.ui.utils.api_client import APIClient

            # 기존 세션이 있으면 안전하게 종료
            if cls._client:
                try:
                    cls._client.session.close()
                    logging.debug("🔒 기존 API 클라이언트 세션 종료")
                except Exception as exc:
                    logging.warning("APIClient 세션 종료 실패: %s", exc)

            # 새 인스턴스 생성
            logging.info("🚀 새 API 클라이언트 생성")
            cls._client = APIClient(**kwargs)
            cls._last_params_hash = current_params_hash
            cls._creation_time = time.time()

            try:
                import streamlit as st
                # 세션 상태 타입 검증
                if hasattr(st, 'session_state'):
                    for key, value in st.session_state.items():
                        if isinstance(value, str) and key.endswith('_cached'):
                            st.session_state[key] = None
            except Exception as e:
                logging.warning(f"세션 상태 정리 실패: {e}")

            return cls._client

    @classmethod
    def reset_client(cls) -> None:
        """
        싱글톤을 완전히 초기화한다.
        - APIClient 내부의 requests.Session을 닫아 리소스를 해제
        - _client 를 None 으로 돌려 재생성 가능 상태로 만든다
        """
        with cls._lock:
            if cls._client:
                try:
                    cls._client.session.close()  # 네트워크 커넥션 정리
                    logging.info("🔒 API 클라이언트 완전 초기화")
                except Exception as exc:
                    logging.warning("APIClient 세션 종료 실패: %s", exc)
                finally:
                    cls._client = None  # 초기화
                    cls._last_params_hash = None
                    cls._creation_time = None

    @classmethod
    def is_client_valid(cls) -> bool:
        """현재 클라이언트가 유효한지 확인"""
        return (cls._client is not None and
                cls._creation_time is not None and
                time.time() - cls._creation_time < 600)  # 10분 유효

    @classmethod
    def get_client_info(cls) -> Dict[str, Any]:
        """클라이언트 상태 정보 반환 (디버깅용)"""
        with cls._lock:
            return {
                "has_client": cls._client is not None,
                "creation_time": cls._creation_time,
                "age_seconds": time.time() - cls._creation_time if cls._creation_time else None,
                "params_hash": cls._last_params_hash,
                "is_valid": cls.is_client_valid()
            }