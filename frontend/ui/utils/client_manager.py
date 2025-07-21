"""
client_manager.py
=================
APIClient 싱글톤 매니저.

모든 프론트엔드 컴포넌트가 **하나의** APIClient 인스턴스를 사용하도록 보장합니다.
불필요한 세션 생성·종료를 방지하여 네트워크 커넥션을 절약하고,
재시도 횟수·타임아웃 등 글로벌 설정을 일관되게 유지합니다.
"""
import threading
import logging


class ClientManager:
    """APIClient 싱글톤 관리 클래스"""
    _lock = threading.Lock()
    _client = None

    @classmethod
    def get_client(cls, **kwargs):
        """
        APIClient 인스턴스를 반환한다.
        kwargs가 주어지면 기존 세션을 해제하고 새로운 인스턴스를 생성한다.
        """
        with cls._lock:
            # 이미 생성돼 있고 새 파라미터가 없는 경우 그대로 반환
            if cls._client and not kwargs:
                return cls._client

            # ✅ 필요 시점에만 import → 순환차단
            from frontend.ui.utils.api_client import APIClient

            # 기존 세션이 있으면 안전하게 종료
            if cls._client:
                try:
                    cls._client.session.close()
                except Exception as exc:
                    logging.warning("APIClient 세션 종료 실패: %s", exc)

            # 새 인스턴스 생성
            cls._client = APIClient(**kwargs)
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
                except Exception as exc:
                    logging.warning("APIClient 세션 종료 실패: %s", exc)
                finally:
                    cls._client = None  # 초기화