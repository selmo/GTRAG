"""
개선된 시스템 상태 관리 통합 유틸리티
기존 system_health.py를 기반으로 중복 로직 제거 및 성능 최적화
"""
import streamlit as st
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """서비스 상태 열거형"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"
    ERROR = "error"


class SystemStatus(Enum):
    """전체 시스템 상태 열거형"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    INITIALIZING = "initializing"
    ERROR = "error"


@dataclass
class ServiceInfo:
    """개별 서비스 정보"""
    name: str
    status: ServiceStatus
    message: str = ""
    details: Dict[str, Any] = None
    last_check: datetime = None
    response_time: float = 0.0  # 응답 시간 추가

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.last_check is None:
            self.last_check = datetime.now()


@dataclass
class SystemHealthReport:
    """시스템 전체 상태 보고서"""
    overall_status: SystemStatus
    services: Dict[str, ServiceInfo]
    last_updated: datetime
    cache_expires: datetime
    errors: List[str] = None
    performance_metrics: Dict[str, Any] = None  # 성능 메트릭 추가

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.performance_metrics is None:
            self.performance_metrics = {}


class SystemHealthManager:
    """개선된 시스템 상태 관리 중앙화 클래스"""
    from frontend.ui.core.config import config  # 추가

    # 캐시 설정 (중앙 관리)
    CACHE_DURATION: int = config.cache.system_health_ttl  # 기본 TTL
    FAST_CHECK_DURATION: int = max(5, int(CACHE_DURATION / 3))  # 빠른 확인 TTL

    # 서비스별 우선순위 (핵심 서비스 먼저 확인)
    SERVICE_PRIORITY = {
        'api_server': 1,
        'qdrant': 2,
        'embedder': 3,
        'ollama': 4,
        'celery': 5
    }

    @staticmethod
    @st.cache_data(ttl=config.cache.system_health_ttl, show_spinner=False)
    def _cached_compute(api_base_url: str, quick_check: bool) -> "SystemHealthReport":
        """
        API base_url·quick_check 조합별로 캐시되는 헬퍼.
        cache_hit 플래그를 True 로 세팅한다.
        """
        from frontend.ui.utils.client_manager import ClientManager
        api_client = ClientManager.get_client()
        report = SystemHealthManager._compute_status_core(api_client, quick_check)
        report.performance_metrics["cache_hit"] = True
        return report

    @classmethod
    def get_cached_status(cls, force_fresh: bool = False) -> Optional[SystemHealthReport]:
        """
        캐시된 시스템 상태 반환 (개선된 버전)

        Args:
            force_fresh: True면 캐시 무시하고 새로 확인
        """
        if force_fresh:
            return None

        cache_key = 'system_health_cache'
        if cache_key in st.session_state:
            cached = st.session_state[cache_key]
            if isinstance(cached, SystemHealthReport):
                if datetime.now() < cached.cache_expires:
                    logger.debug("Returning cached system status")
                    return cached
        return None

    @classmethod
    def clear_cache(cls, service_name: Optional[str] = None):
        """캐시 초기화 (개선된 버전)"""
        if service_name:
            # 특정 서비스만 캐시 무효화
            cache_key = f'service_cache_{service_name}'
            if cache_key in st.session_state:
                del st.session_state[cache_key]
        else:
            # 전체 캐시 초기화
            cache_keys = [key for key in st.session_state.keys()
                         if key.startswith(('system_health_cache', 'service_cache_'))]
            for key in cache_keys:
                del st.session_state[key]
        logger.info(f"System health cache cleared: {service_name or 'all'}")

    @classmethod
    def check_full_system_status(cls, api_client, force_refresh: bool = False,
                                quick_check: bool = False) -> SystemHealthReport:
        """
        전체 시스템 상태 종합 확인 (성능 최적화)

        Args:
            api_client: API 클라이언트 인스턴스
            force_refresh: 캐시 무시하고 강제 새로고침
            quick_check: 빠른 확인 모드 (핵심 서비스만)
        """

        # st.cache_data 사용
        if not force_refresh:
            try:
                return cls._cached_compute(api_client.base_url, quick_check)
            except Exception:
                # 캐시 miss 시 ↓ 기존 계산 로직 수행
                pass

        logger.info(f"Checking system status (quick={quick_check})")
        start_time = datetime.now()

        services = {}
        overall_errors = []
        performance_metrics = {}

        try:
            # 1. API 서버 우선 확인 (가장 중요)
            api_service = cls._check_api_server_optimized(api_client)
            services['api_server'] = api_service

            if api_service.status == ServiceStatus.CONNECTED:
                # 2. 빠른 확인 모드가 아니면 상세 확인
                if not quick_check:
                    health_services = cls._check_health_endpoint_parallel(api_client)
                    services.update(health_services)

                    # 3. 임베딩 모델 동작 확인
                    embedder_service = cls._check_embedder_smart(api_client)
                    services['embedder'] = embedder_service
                else:
                    # 빠른 모드: 기본 서비스만 확인
                    for service_name in ['qdrant', 'ollama']:
                        services[service_name] = ServiceInfo(
                            name=service_name,
                            status=ServiceStatus.UNKNOWN,
                            message="Quick check - not verified"
                        )
            else:
                # API 서버 실패 시 다른 서비스들도 실패로 설정
                for service_name in ['qdrant', 'ollama', 'celery', 'embedder']:
                    services[service_name] = ServiceInfo(
                        name=service_name,
                        status=ServiceStatus.UNKNOWN,
                        message="API server unavailable"
                    )
                overall_errors.append("API server connection failed")

        except Exception as e:
            logger.error(f"Error during system status check: {e}")
            overall_errors.append(f"System check failed: {str(e)}")

            # 오류 시 모든 서비스를 ERROR로 설정
            for service_name in ['api_server', 'qdrant', 'ollama', 'celery', 'embedder']:
                if service_name not in services:
                    services[service_name] = ServiceInfo(
                        name=service_name,
                        status=ServiceStatus.ERROR,
                        message=str(e)
                    )

        # 성능 메트릭 수집
        check_duration = (datetime.now() - start_time).total_seconds()
        performance_metrics = {
            'check_duration': check_duration,
            'services_checked': len(services),
            'quick_mode': quick_check,
            'cache_hit': False
        }

        # 전체 시스템 상태 결정
        overall_status = cls._determine_overall_status_smart(services, overall_errors, quick_check)

        # 캐시 지속 시간 결정 (상태에 따라 차등 적용)
        cache_duration = cls._get_cache_duration(overall_status, quick_check)

        # 보고서 생성
        now = datetime.now()
        report = SystemHealthReport(
            overall_status=overall_status,
            services=services,
            last_updated=now,
            cache_expires=now + timedelta(seconds=cache_duration),
            errors=overall_errors,
            performance_metrics=performance_metrics
        )

        # 캐시에 저장
        st.session_state['system_health_cache'] = report

        logger.info(f"System status check completed: {overall_status.value} "
                   f"({check_duration:.2f}s)")
        return report

    @classmethod
    def _check_api_server_optimized(cls, api_client) -> ServiceInfo:
        """API 서버 최적화 확인"""
        start_time = datetime.now()

        try:
            # 더 가벼운 엔드포인트 사용 (docs 대신 health)
            response = requests.get(f"{api_client.base_url}/v1/health", timeout=3)
            response_time = (datetime.now() - start_time).total_seconds()

            if response.status_code == 200:
                return ServiceInfo(
                    name="api_server",
                    status=ServiceStatus.CONNECTED,
                    message="API server responding",
                    details={"base_url": api_client.base_url},
                    response_time=response_time
                )
            else:
                return ServiceInfo(
                    name="api_server",
                    status=ServiceStatus.ERROR,
                    message=f"API server returned status {response.status_code}",
                    response_time=response_time
                )
        except requests.exceptions.ConnectionError:
            return ServiceInfo(
                name="api_server",
                status=ServiceStatus.DISCONNECTED,
                message="Cannot connect to API server"
            )
        except requests.exceptions.Timeout:
            return ServiceInfo(
                name="api_server",
                status=ServiceStatus.DEGRADED,
                message="API server timeout"
            )
        except Exception as e:
            return ServiceInfo(
                name="api_server",
                status=ServiceStatus.ERROR,
                message=f"API check failed: {str(e)}"
            )

    @classmethod
    def _check_health_endpoint_parallel(cls, api_client) -> Dict[str, ServiceInfo]:
        """헬스체크 엔드포인트 병렬 확인 (기존 로직 유지하되 최적화)"""
        services = {}

        try:
            response = requests.get(f"{api_client.base_url}/v1/health", timeout=8)
            if response.status_code == 200:
                health_data = response.json()

                # ▶︎ 새 방어 코드
                if not isinstance(health_data, dict):
                    logger.warning("Unexpected health response: %s", health_data)
                    health_data = {"services": {}}  # 최소 구조 보장

                service_data = health_data.get("services", {})

                # 서비스별 정보 파싱 (기존 로직 유지)
                for service_name in ['qdrant', 'ollama', 'celery']:
                    service_info = service_data.get(service_name, {})
                    service_status = service_info.get("status", "unknown")

                    services[service_name] = ServiceInfo(
                        name=service_name,
                        status=ServiceStatus.CONNECTED if service_status == "connected"
                               else ServiceStatus.DISCONNECTED,
                        message=service_info.get("message", ""),
                        details=cls._extract_service_details(service_name, service_info)
                    )
            else:
                # 실패 시 모든 서비스 UNKNOWN
                for service_name in ['qdrant', 'ollama', 'celery']:
                    services[service_name] = ServiceInfo(
                        name=service_name,
                        status=ServiceStatus.UNKNOWN,
                        message=f"Health check returned {response.status_code}"
                    )

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            for service_name in ['qdrant', 'ollama', 'celery']:
                services[service_name] = ServiceInfo(
                    name=service_name,
                    status=ServiceStatus.ERROR,
                    message=f"Health check error: {str(e)}"
                )

        return services

    @classmethod
    def _extract_service_details(cls, service_name: str, service_info: Dict) -> Dict:
        """서비스별 세부 정보 추출"""
        if service_name == "qdrant":
            return {
                "collections": service_info.get("collections", []),
                "host": service_info.get("host", ""),
                "korean_content_ratio": service_info.get("korean_content_ratio", 0)
            }
        elif service_name == "ollama":
            return {
                "host": service_info.get("host", ""),
                "models": service_info.get("models", []),
                "total_models": service_info.get("total_models", 0)
            }
        elif service_name == "celery":
            return service_info.get("details", {})

        return {}

    @classmethod
    def _check_embedder_smart(cls, api_client) -> ServiceInfo:
        """스마트 임베딩 모델 확인 (캐시 활용)"""
        # 캐시된 결과 확인
        cache_key = 'service_cache_embedder'
        if cache_key in st.session_state:
            cached_time, cached_result = st.session_state[cache_key]
            if datetime.now() - cached_time < timedelta(seconds=60):  # 1분 캐시
                return cached_result

        start_time = datetime.now()

        try:
            # 더 가벼운 테스트 (top_k=1로 최소화)
            response = requests.get(
                f"{api_client.base_url}/v1/search",
                params={"q": "test", "top_k": 1},
                timeout=10
            )

            response_time = (datetime.now() - start_time).total_seconds()

            if response.status_code in [200, 404]:
                result = ServiceInfo(
                    name="embedder",
                    status=ServiceStatus.CONNECTED,
                    message="Embedding model functioning",
                    details={"test_response_code": response.status_code},
                    response_time=response_time
                )
            else:
                result = ServiceInfo(
                    name="embedder",
                    status=ServiceStatus.ERROR,
                    message=f"Embedder test failed with status {response.status_code}",
                    response_time=response_time
                )

        except requests.exceptions.Timeout:
            result = ServiceInfo(
                name="embedder",
                status=ServiceStatus.DEGRADED,
                message="Embedder response timeout (model may be loading)"
            )
        except Exception as e:
            result = ServiceInfo(
                name="embedder",
                status=ServiceStatus.ERROR,
                message=f"Embedder test error: {str(e)}"
            )

        # 결과 캐시
        st.session_state[cache_key] = (datetime.now(), result)

        return result

    @classmethod
    def _determine_overall_status_smart(cls, services: Dict[str, ServiceInfo],
                                       errors: List[str], quick_check: bool) -> SystemStatus:
        """스마트 전체 상태 결정 (우선순위 고려)"""

        if errors:
            return SystemStatus.ERROR

        # 핵심 서비스별 가중치 적용
        critical_services = ['api_server', 'qdrant', 'embedder']
        important_services = ['ollama']

        critical_status = []
        important_status = []

        for service_name, service_info in services.items():
            if service_name in critical_services:
                critical_status.append(service_info.status)
            elif service_name in important_services:
                important_status.append(service_info.status)

        # 핵심 서비스 중 하나라도 실패하면 UNHEALTHY
        if any(status in [ServiceStatus.ERROR, ServiceStatus.DISCONNECTED]
               for status in critical_status):
            return SystemStatus.UNHEALTHY

        # 빠른 확인 모드에서는 덜 엄격한 기준 적용
        if quick_check:
            if any(status == ServiceStatus.CONNECTED for status in critical_status):
                return SystemStatus.HEALTHY
            else:
                return SystemStatus.INITIALIZING

        # 일반 모드: 더 엄격한 기준
        if all(status == ServiceStatus.CONNECTED for status in critical_status):
            # 중요 서비스 상태 확인
            if any(status in [ServiceStatus.DEGRADED, ServiceStatus.ERROR]
                   for status in important_status):
                return SystemStatus.DEGRADED
            return SystemStatus.HEALTHY

        # 일부 핵심 서비스가 성능 저하
        if any(status == ServiceStatus.DEGRADED for status in critical_status):
            return SystemStatus.DEGRADED

        # 알 수 없는 상태가 있으면 초기화 중
        all_status = [info.status for info in services.values()]
        if any(status == ServiceStatus.UNKNOWN for status in all_status):
            return SystemStatus.INITIALIZING

        return SystemStatus.DEGRADED

    @classmethod
    def _get_cache_duration(cls, status: SystemStatus, quick_check: bool) -> int:
        """상태에 따른 적응형 캐시 지속 시간"""
        base_duration = cls.FAST_CHECK_DURATION if quick_check else cls.CACHE_DURATION

        # 상태별 캐시 시간 조정
        if status == SystemStatus.HEALTHY:
            return base_duration * 2  # 정상일 때는 더 오래 캐시
        elif status in [SystemStatus.ERROR, SystemStatus.UNHEALTHY]:
            return base_duration // 2  # 문제 있을 때는 자주 확인
        else:
            return base_duration

    @classmethod
    def check_model_availability_enhanced(cls, api_client) -> Tuple[bool, Optional[str], Dict]:
        """
        향상된 모델 사용 가능 여부 확인

        Returns:
            Tuple: (사용가능여부, 에러메시지, 추가정보)
        """
        additional_info = {}

        try:
            start_time = datetime.now()

            # 1. 사용 가능한 모델 목록 확인
            available_models = api_client.get_available_models()
            model_check_time = (datetime.now() - start_time).total_seconds()

            additional_info['model_check_time'] = model_check_time
            additional_info['available_models_count'] = len(available_models) if available_models else 0

            if not available_models:
                return False, "사용 가능한 모델이 없습니다. Ollama 서버를 확인하세요.", additional_info

            # 2. 선택된 모델 확인
            selected_model = st.session_state.get('selected_model')
            additional_info['selected_model'] = selected_model

            if not selected_model:
                return False, "모델이 선택되지 않았습니다. 설정 페이지에서 모델을 선택하세요.", additional_info

            # 3. 모델 호환성 확인
            if selected_model not in available_models:
                additional_info['model_mismatch'] = True
                return False, f"선택된 모델 '{selected_model}'이 더 이상 사용할 수 없습니다.", additional_info

            # 4. 모델 상태 추가 확인 (선택적)
            try:
                model_info = api_client.get_model_info(selected_model)
                if 'error' not in model_info:
                    additional_info['model_size'] = model_info.get('size', 0)
                    additional_info['model_modified'] = model_info.get('modified_at')
            except:
                pass  # 모델 정보 확인 실패는 치명적이지 않음

            additional_info['status'] = 'ready'
            return True, None, additional_info

        except Exception as e:
            logger.error(f"Enhanced model availability check failed: {e}")
            additional_info['error'] = str(e)
            return False, f"모델 상태 확인 실패: {str(e)}", additional_info

    @classmethod
    def get_system_overview(cls, api_client) -> Dict[str, Any]:
        """
        시스템 전체 개요 정보 반환 (대시보드용)
        """
        overview = {
            'timestamp': datetime.now(),
            'system_ready': False,
            'critical_issues': [],
            'warnings': [],
            'performance': {},
            'services': {},
            'recommendations': []
        }

        try:
            # 빠른 상태 확인
            report = cls.check_full_system_status(api_client, quick_check=True)

            overview['system_ready'] = report.overall_status in [
                SystemStatus.HEALTHY, SystemStatus.DEGRADED
            ]

            # 문제점 분류
            for service_name, service_info in report.services.items():
                if service_info.status in [ServiceStatus.ERROR, ServiceStatus.DISCONNECTED]:
                    overview['critical_issues'].append(f"{service_name}: {service_info.message}")
                elif service_info.status == ServiceStatus.DEGRADED:
                    overview['warnings'].append(f"{service_name}: {service_info.message}")

            # 성능 정보
            overview['performance'] = report.performance_metrics

            # 서비스 요약
            for service_name, service_info in report.services.items():
                overview['services'][service_name] = {
                    'status': service_info.status.value,
                    'response_time': service_info.response_time
                }

            # 추천 사항
            if overview['critical_issues']:
                overview['recommendations'].append("시스템 상태 페이지에서 문제를 확인하세요")
            if len(overview['warnings']) > 2:
                overview['recommendations'].append("일부 서비스 성능이 저하되었습니다")

        except Exception as e:
            overview['critical_issues'].append(f"시스템 상태 확인 실패: {str(e)}")

        return overview

    # 기존 호환성 메서드들 유지
    @classmethod
    def check_model_availability(cls, api_client) -> Tuple[bool, Optional[str]]:
        """기존 호환성을 위한 메서드"""
        is_available, error_msg, _ = cls.check_model_availability_enhanced(api_client)
        return is_available, error_msg

    @classmethod
    def is_system_ready(cls, api_client) -> Tuple[bool, SystemHealthReport]:
        """기존 호환성을 위한 메서드"""
        report = cls.check_full_system_status(api_client)
        is_ready = report.overall_status in [SystemStatus.HEALTHY, SystemStatus.DEGRADED]
        return is_ready, report

    @classmethod
    def get_status_display_info(cls, status: SystemStatus) -> Tuple[str, str, str]:
        """기존 display 정보 메서드 유지"""
        status_info = {
            SystemStatus.HEALTHY: ("✅", "시스템 정상 작동 중", "success"),
            SystemStatus.DEGRADED: ("⚠️", "일부 서비스에 문제가 있습니다", "warning"),
            SystemStatus.UNHEALTHY: ("❌", "시스템에 심각한 문제가 있습니다", "error"),
            SystemStatus.INITIALIZING: ("⏳", "시스템 초기화 중입니다", "info"),
            SystemStatus.ERROR: ("🚫", "시스템 확인 중 오류가 발생했습니다", "error")
        }
        return status_info.get(status, ("❓", "알 수 없는 상태", "info"))

    @classmethod
    def get_service_display_info(cls, status: ServiceStatus) -> Tuple[str, str]:
        """기존 서비스 display 정보 메서드 유지"""
        status_info = {
            ServiceStatus.CONNECTED: ("🟢", "연결됨"),
            ServiceStatus.DISCONNECTED: ("🔴", "연결 실패"),
            ServiceStatus.DEGRADED: ("🟡", "성능 저하"),
            ServiceStatus.UNKNOWN: ("⚪", "상태 불명"),
            ServiceStatus.ERROR: ("🚫", "오류")
        }
        return status_info.get(status, ("❓", "알 수 없음"))


# 편의 함수들 (기존 호환성 유지)
def check_system_ready(api_client) -> Tuple[bool, Dict]:
    """기존 호환성 함수"""
    is_ready, report = SystemHealthManager.is_system_ready(api_client)

    status_dict = {
        "qdrant": report.services.get('qdrant', ServiceInfo("", ServiceStatus.ERROR)).status == ServiceStatus.CONNECTED,
        "ollama": report.services.get('ollama', ServiceInfo("", ServiceStatus.ERROR)).status == ServiceStatus.CONNECTED,
        "embedder": report.services.get('embedder', ServiceInfo("", ServiceStatus.ERROR)).status == ServiceStatus.CONNECTED,
        "overall": is_ready
    }

    if not is_ready:
        status_dict["error"] = f"System status: {report.overall_status.value}"

    return is_ready, status_dict


def check_model_availability(api_client):
    """기존 호환성 함수"""
    return SystemHealthManager.check_model_availability(api_client)