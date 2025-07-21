"""
강화된 모델 설정 중앙 관리 유틸리티
기존 model_manager.py를 개선하여 성능 최적화 및 기능 확장
"""
import streamlit as st
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
import logging
from dataclasses import dataclass, asdict, field
from enum import Enum
import json
from functools import lru_cache
import hashlib

logger = logging.getLogger(__name__)


class ModelValidationError(Exception):
    """모델 설정 검증 오류"""
    pass


class SettingCategory(Enum):
    """설정 카테고리"""
    LLM = "llm"
    RAG = "rag"
    API = "api"
    UI = "ui"
    PERFORMANCE = "performance"


class ValidationLevel(Enum):
    """검증 수준"""
    NONE = "none"
    BASIC = "basic"
    STRICT = "strict"
    REALTIME = "realtime"


@dataclass
class ModelSettings:
    """확장된 모델 설정 데이터 클래스"""
    # LLM 설정
    model: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 1000
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0  # 추가
    system_prompt: str = "당신은 문서 기반 질의응답 시스템입니다. 제공된 문서의 내용만을 바탕으로 정확하고 도움이 되는 답변을 제공하세요."

    # RAG 설정
    rag_top_k: int = 3
    min_similarity: float = 0.5
    context_window: int = 3000
    chunk_size: int = 500
    chunk_overlap: int = 50
    embedding_model: str = "intfloat/multilingual-e5-large-instruct"
    search_type: str = "hybrid"
    rerank_enabled: bool = False  # 추가

    # API 설정
    api_timeout: int = 300
    rag_timeout: int = 600
    retry_attempts: int = 3  # 추가
    rate_limit: Optional[int] = None  # 추가

    # UI 설정
    show_sources: bool = True
    show_debug_info: bool = False
    auto_scroll: bool = True
    theme: str = "light"  # 추가

    # 성능 설정 (추가)
    batch_size: int = 1
    cache_enabled: bool = True
    parallel_processing: bool = False

    # 메타데이터
    last_updated: Optional[datetime] = field(default_factory=datetime.now)
    updated_by: str = "user"
    version: str = "1.0"
    config_hash: Optional[str] = field(default=None)  # 설정 변경 감지용

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()

        # 설정 해시 생성 (변경 감지용)
        if self.config_hash is None:
            self.config_hash = self._generate_config_hash()

    def _generate_config_hash(self) -> str:
        """설정의 해시값 생성 (변경 감지용)"""
        # 메타데이터 제외한 설정값들로 해시 생성
        config_dict = asdict(self)
        excluded_keys = {'last_updated', 'updated_by', 'config_hash'}

        filtered_config = {k: v for k, v in config_dict.items()
                          if k not in excluded_keys}

        config_str = json.dumps(filtered_config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()

    def has_changed(self) -> bool:
        """설정이 변경되었는지 확인"""
        current_hash = self._generate_config_hash()
        return current_hash != self.config_hash

    def update_hash(self):
        """해시값 업데이트"""
        self.config_hash = self._generate_config_hash()
        self.last_updated = datetime.now()


class EnhancedModelManager:
    """강화된 모델 설정 중앙 관리 클래스"""

    # 세션 상태 키
    SETTINGS_KEY = "enhanced_model_settings"
    CACHE_KEY = "model_settings_cache"
    VALIDATION_KEY = "model_settings_validation"
    HISTORY_KEY = "model_settings_history"
    PROFILE_KEY = "model_settings_profiles"

    # 설정 제약 조건 (확장)
    CONSTRAINTS = {
        "temperature": {"min": 0.0, "max": 2.0, "step": 0.1},
        "max_tokens": {"min": 100, "max": 8000, "step": 100},
        "top_p": {"min": 0.0, "max": 1.0, "step": 0.05},
        "frequency_penalty": {"min": 0.0, "max": 2.0, "step": 0.1},
        "presence_penalty": {"min": 0.0, "max": 2.0, "step": 0.1},
        "rag_top_k": {"min": 1, "max": 50, "step": 1},
        "min_similarity": {"min": 0.0, "max": 1.0, "step": 0.05},
        "context_window": {"min": 500, "max": 16000, "step": 500},
        "chunk_size": {"min": 100, "max": 2000, "step": 100},
        "chunk_overlap": {"min": 0, "max": 500, "step": 50},
        "api_timeout": {"min": 30, "max": 1800, "step": 30},
        "rag_timeout": {"min": 60, "max": 1800, "step": 60},
        "retry_attempts": {"min": 1, "max": 10, "step": 1},
        "batch_size": {"min": 1, "max": 100, "step": 1}
    }

    # 필수 설정 항목
    REQUIRED_SETTINGS = ["model"]

    # 설정 프로필 (사전 정의된 설정 조합)
    SETTING_PROFILES = {
        "기본": {
            "temperature": 0.3,
            "max_tokens": 1000,
            "rag_top_k": 3,
            "min_similarity": 0.5
        },
        "창의적": {
            "temperature": 0.8,
            "max_tokens": 1500,
            "rag_top_k": 5,
            "min_similarity": 0.4,
            "frequency_penalty": 0.2
        },
        "정확성 중심": {
            "temperature": 0.1,
            "max_tokens": 800,
            "rag_top_k": 7,
            "min_similarity": 0.7,
            "rerank_enabled": True
        },
        "빠른 응답": {
            "temperature": 0.3,
            "max_tokens": 500,
            "rag_top_k": 2,
            "min_similarity": 0.6,
            "api_timeout": 120,
            "rag_timeout": 180
        }
    }

    @classmethod
    def initialize(cls, validation_level: ValidationLevel = ValidationLevel.BASIC):
        """모델 설정 초기화 (개선된 버전)"""
        if cls.SETTINGS_KEY not in st.session_state:
            # 기존 설정 마이그레이션
            migrated_settings = cls._migrate_existing_settings()
            st.session_state[cls.SETTINGS_KEY] = migrated_settings
            logger.info("Enhanced ModelManager initialized with migrated settings")

        # 캐시 및 히스토리 초기화
        for key in [cls.CACHE_KEY, cls.VALIDATION_KEY, cls.HISTORY_KEY, cls.PROFILE_KEY]:
            if key not in st.session_state:
                st.session_state[key] = {} if key == cls.CACHE_KEY else []

        # 검증 수준 설정
        st.session_state.validation_level = validation_level

    @classmethod
    def _migrate_existing_settings(cls) -> ModelSettings:
        """기존 세션 상태에서 설정 마이그레이션 (확장)"""
        settings = ModelSettings()

        # 기존 + 새로운 설정 매핑
        migration_map = {
            "selected_model": "model",
            "temperature": "temperature",
            "max_tokens": "max_tokens",
            "top_p": "top_p",
            "frequency_penalty": "frequency_penalty",
            "system_prompt": "system_prompt",
            "rag_top_k": "rag_top_k",
            "min_similarity": "min_similarity",
            "context_window": "context_window",
            "chunk_size": "chunk_size",
            "chunk_overlap": "chunk_overlap",
            "embedding_model": "embedding_model",
            "search_type": "search_type",
            "api_timeout": "api_timeout",
            "rag_timeout": "rag_timeout",
            # 새로운 설정들
            "show_sources": "show_sources",
            "show_debug_info": "show_debug_info",
            "auto_scroll": "auto_scroll"
        }

        for old_key, new_key in migration_map.items():
            if old_key in st.session_state:
                try:
                    setattr(settings, new_key, st.session_state[old_key])
                    logger.debug(f"Migrated {old_key} -> {new_key}: {st.session_state[old_key]}")
                except Exception as e:
                    logger.warning(f"Failed to migrate {old_key}: {e}")

        settings.last_updated = datetime.now()
        settings.updated_by = "migration"
        settings.update_hash()

        return settings

    @classmethod
    def get_settings(cls) -> ModelSettings:
        """현재 모델 설정 반환"""
        cls.initialize()
        return st.session_state[cls.SETTINGS_KEY]

    @classmethod
    def update_setting(cls, key: str, value: Any, validate: bool = True,
                      save_to_history: bool = True) -> Tuple[bool, Optional[str]]:
        """개별 설정 값 업데이트 (개선된 버전)"""
        cls.initialize()

        try:
            # 값 검증
            if validate:
                validation_level = st.session_state.get('validation_level', ValidationLevel.BASIC)
                cls._validate_single_setting(key, value, validation_level)

            # 설정 업데이트
            settings = cls.get_settings()
            if hasattr(settings, key):
                old_value = getattr(settings, key)

                # 히스토리 저장
                if save_to_history and old_value != value:
                    cls._save_setting_history(key, old_value, value)

                setattr(settings, key, value)
                settings.last_updated = datetime.now()
                settings.updated_by = "user"
                settings.update_hash()

                # 세션 상태 업데이트
                st.session_state[cls.SETTINGS_KEY] = settings

                # 캐시 무효화
                cls._invalidate_cache()

                # 기존 세션 상태도 동기화 (하위 호환성)
                cls._sync_to_legacy_session_state(key, value)

                logger.info(f"Setting updated: {key} = {old_value} -> {value}")
                return True, None
            else:
                error_msg = f"Invalid setting key: {key}"
                logger.warning(error_msg)
                return False, error_msg

        except ModelValidationError as e:
            error_msg = f"Validation failed for {key}={value}: {e}"
            logger.error(error_msg)
            return False, str(e)
        except Exception as e:
            error_msg = f"Failed to update setting {key}: {e}"
            logger.error(error_msg)
            return False, error_msg

    @classmethod
    def _save_setting_history(cls, key: str, old_value: Any, new_value: Any):
        """설정 변경 히스토리 저장"""
        if cls.HISTORY_KEY not in st.session_state:
            st.session_state[cls.HISTORY_KEY] = []

        history_entry = {
            'timestamp': datetime.now(),
            'key': key,
            'old_value': old_value,
            'new_value': new_value,
            'user': st.session_state.get('user', 'unknown')
        }

        st.session_state[cls.HISTORY_KEY].append(history_entry)

        # 최대 100개 엔트리까지만 유지
        if len(st.session_state[cls.HISTORY_KEY]) > 100:
            st.session_state[cls.HISTORY_KEY] = st.session_state[cls.HISTORY_KEY][-100:]

    @classmethod
    def apply_profile(cls, profile_name: str) -> Tuple[bool, List[str]]:
        """설정 프로필 적용"""
        if profile_name not in cls.SETTING_PROFILES:
            return False, [f"Unknown profile: {profile_name}"]

        profile_settings = cls.SETTING_PROFILES[profile_name]
        return cls.update_multiple_settings(profile_settings, validate=True)

    @classmethod
    def create_custom_profile(cls, profile_name: str, settings_dict: Dict[str, Any]) -> bool:
        """커스텀 프로필 생성"""
        if cls.PROFILE_KEY not in st.session_state:
            st.session_state[cls.PROFILE_KEY] = {}

        # 설정 검증
        try:
            for key, value in settings_dict.items():
                cls._validate_single_setting(key, value, ValidationLevel.BASIC)
        except ModelValidationError as e:
            logger.error(f"Profile validation failed: {e}")
            return False

        # 프로필 저장
        st.session_state[cls.PROFILE_KEY][profile_name] = {
            'settings': settings_dict,
            'created_at': datetime.now(),
            'created_by': st.session_state.get('user', 'unknown')
        }

        logger.info(f"Custom profile created: {profile_name}")
        return True

    @classmethod
    def get_available_profiles(cls) -> Dict[str, Dict]:
        """사용 가능한 프로필 목록 반환"""
        profiles = {}

        # 기본 프로필
        for name, settings in cls.SETTING_PROFILES.items():
            profiles[name] = {
                'settings': settings,
                'type': 'default',
                'description': f'사전 정의된 {name} 프로필'
            }

        # 커스텀 프로필
        custom_profiles = st.session_state.get(cls.PROFILE_KEY, {})
        for name, profile_data in custom_profiles.items():
            profiles[name] = {
                'settings': profile_data['settings'],
                'type': 'custom',
                'created_at': profile_data.get('created_at'),
                'description': f'사용자 정의 프로필'
            }

        return profiles

    @classmethod
    def update_multiple_settings(cls, settings_dict: Dict[str, Any],
                                validate: bool = True,
                                batch_mode: bool = True) -> Tuple[bool, List[str]]:
        """여러 설정 값 일괄 업데이트 (개선된 버전)"""
        cls.initialize()
        errors = []
        success_count = 0

        # 배치 모드에서는 히스토리 저장 최적화
        old_settings = {}
        if batch_mode:
            current_settings = cls.get_settings()
            old_settings = {k: getattr(current_settings, k, None)
                           for k in settings_dict.keys()
                           if hasattr(current_settings, k)}

        # 먼저 모든 설정 검증 (검증 활성화 시)
        if validate:
            validation_level = st.session_state.get('validation_level', ValidationLevel.BASIC)
            for key, value in settings_dict.items():
                try:
                    cls._validate_single_setting(key, value, validation_level)
                except ModelValidationError as e:
                    errors.append(f"{key}: {str(e)}")

        # 검증 오류가 있으면 업데이트 중단
        if errors:
            return False, errors

        # 일괄 업데이트
        settings = cls.get_settings()
        updated_keys = []

        for key, value in settings_dict.items():
            if hasattr(settings, key):
                old_value = getattr(settings, key)
                if old_value != value:  # 실제로 변경된 경우만
                    setattr(settings, key, value)
                    updated_keys.append(key)

                    # 개별 히스토리 저장 (배치 모드가 아닌 경우)
                    if not batch_mode:
                        cls._save_setting_history(key, old_value, value)

                    cls._sync_to_legacy_session_state(key, value)
                    success_count += 1
            else:
                errors.append(f"Invalid setting key: {key}")

        if success_count > 0:
            settings.last_updated = datetime.now()
            settings.updated_by = "batch_update" if batch_mode else "user"
            settings.update_hash()
            st.session_state[cls.SETTINGS_KEY] = settings
            cls._invalidate_cache()

            # 배치 모드에서는 한 번에 히스토리 저장
            if batch_mode and updated_keys:
                cls._save_batch_history(old_settings, settings_dict, updated_keys)

        logger.info(f"Batch update completed: {success_count} settings updated, {len(errors)} errors")
        return len(errors) == 0, errors

    @classmethod
    def _save_batch_history(cls, old_settings: Dict, new_settings: Dict, updated_keys: List[str]):
        """배치 업데이트 히스토리 저장"""
        if cls.HISTORY_KEY not in st.session_state:
            st.session_state[cls.HISTORY_KEY] = []

        history_entry = {
            'timestamp': datetime.now(),
            'type': 'batch_update',
            'changes': {
                key: {
                    'old_value': old_settings.get(key),
                    'new_value': new_settings.get(key)
                }
                for key in updated_keys
            },
            'user': st.session_state.get('user', 'unknown')
        }

        st.session_state[cls.HISTORY_KEY].append(history_entry)

    @classmethod
    def validate_all_settings(cls, validation_level: ValidationLevel = None) -> Tuple[bool, List[str]]:
        """전체 설정 검증 (개선된 버전)"""
        cls.initialize()
        settings = cls.get_settings()
        errors = []

        if validation_level is None:
            validation_level = st.session_state.get('validation_level', ValidationLevel.BASIC)

        # 필수 설정 확인
        for required_key in cls.REQUIRED_SETTINGS:
            value = getattr(settings, required_key, None)
            if value is None or value == "":
                errors.append(f"필수 설정이 누락되었습니다: {required_key}")

        # 개별 설정 검증
        for key, value in asdict(settings).items():
            if key in ["last_updated", "updated_by", "version", "config_hash"]:  # 메타데이터 제외
                continue
            try:
                cls._validate_single_setting(key, value, validation_level)
            except ModelValidationError as e:
                errors.append(f"{key}: {str(e)}")

        # 논리적 일관성 검증
        if validation_level in [ValidationLevel.STRICT, ValidationLevel.REALTIME]:
            logical_errors = cls._validate_logical_consistency(settings)
            errors.extend(logical_errors)

        # 성능 영향 검증 (REALTIME 모드)
        if validation_level == ValidationLevel.REALTIME:
            performance_warnings = cls._validate_performance_impact(settings)
            errors.extend([f"성능 경고: {w}" for w in performance_warnings])

        # 검증 결과 캐시
        is_valid = len(errors) == 0
        st.session_state[cls.VALIDATION_KEY] = {
            "is_valid": is_valid,
            "errors": errors,
            "checked_at": datetime.now(),
            "validation_level": validation_level.value
        }

        return is_valid, errors

    @classmethod
    def _validate_single_setting(cls, key: str, value: Any, validation_level: ValidationLevel):
        """개별 설정 검증 (확장된 버전)"""
        if key in cls.CONSTRAINTS:
            constraint = cls.CONSTRAINTS[key]

            # 숫자 범위 검증
            if "min" in constraint and value < constraint["min"]:
                raise ModelValidationError(f"{key} 값이 최소값 {constraint['min']}보다 작습니다: {value}")

            if "max" in constraint and value > constraint["max"]:
                raise ModelValidationError(f"{key} 값이 최대값 {constraint['max']}보다 큽니다: {value}")

            # 단계 검증 (STRICT 모드)
            if validation_level in [ValidationLevel.STRICT, ValidationLevel.REALTIME]:
                if "step" in constraint:
                    step = constraint["step"]
                    min_val = constraint.get("min", 0)
                    if (value - min_val) % step != 0:
                        raise ModelValidationError(f"{key} 값이 {step} 단위가 아닙니다: {value}")

        # 특별한 검증 규칙
        if key == "model" and value is not None:
            if not isinstance(value, str) or len(value.strip()) == 0:
                raise ModelValidationError("모델명은 비어있을 수 없습니다")

            # REALTIME 모드에서는 모델 존재 여부도 확인
            if validation_level == ValidationLevel.REALTIME:
                try:
                    from frontend.ui.utils.client_manager import ClientManager
                    api_client = ClientManager.get_client()
                    available_models = api_client.get_available_models()
                    if available_models and value not in available_models:
                        raise ModelValidationError(f"모델 '{value}'이 사용 불가능합니다")
                except Exception:
                    pass  # API 호출 실패는 무시

        if key == "system_prompt":
            if not isinstance(value, str) or len(value.strip()) < 10:
                raise ModelValidationError("시스템 프롬프트는 최소 10자 이상이어야 합니다")

        if key == "embedding_model":
            allowed_models = [
                "intfloat/multilingual-e5-large-instruct",
                "intfloat/e5-large-v2",
                "sentence-transformers/all-MiniLM-L6-v2"  # 추가
            ]
            if value not in allowed_models:
                raise ModelValidationError(f"지원되지 않는 임베딩 모델입니다: {value}")

        # 문자열 길이 검증
        if key == "search_type":
            allowed_types = ["semantic", "keyword", "hybrid", "neural"]  # 확장
            if value not in allowed_types:
                raise ModelValidationError(f"지원되지 않는 검색 타입입니다: {value}")

    @classmethod
    def _validate_logical_consistency(cls, settings: ModelSettings) -> List[str]:
        """논리적 일관성 검증 (확장)"""
        errors = []

        # 기존 검증
        if settings.chunk_overlap >= settings.chunk_size:
            errors.append("청크 중첩 크기는 청크 크기보다 작아야 합니다")

        if settings.context_window < settings.chunk_size * settings.rag_top_k:
            errors.append("컨텍스트 윈도우가 검색할 청크들을 담기에 너무 작습니다")

        if settings.rag_timeout <= settings.api_timeout:
            errors.append("RAG 타임아웃은 API 타임아웃보다 길어야 합니다")

        # 새로운 검증
        if settings.temperature > 1.0 and settings.max_tokens > 2000:
            errors.append("높은 temperature와 많은 토큰 수는 일관성 없는 긴 응답을 생성할 수 있습니다")

        if settings.min_similarity > 0.8 and settings.rag_top_k < 3:
            errors.append("높은 유사도 임계값과 적은 검색 문서 수는 결과 부족을 초래할 수 있습니다")

        if settings.frequency_penalty > 1.0 and settings.presence_penalty > 1.0:
            errors.append("높은 frequency와 presence penalty는 반복적이고 제한적인 응답을 생성할 수 있습니다")

        return errors

    @classmethod
    def _validate_performance_impact(cls, settings: ModelSettings) -> List[str]:
        """성능 영향 검증"""
        warnings = []

        # 높은 리소스 사용 경고
        if settings.max_tokens > 4000:
            warnings.append("높은 max_tokens은 응답 시간을 크게 증가시킵니다")

        if settings.rag_top_k > 10:
            warnings.append("많은 검색 문서는 처리 시간을 증가시킵니다")

        if settings.context_window > 8000:
            warnings.append("큰 컨텍스트 윈도우는 메모리 사용량을 증가시킵니다")

        if settings.chunk_size < 200:
            warnings.append("작은 청크 크기는 많은 청크 생성으로 인해 검색 성능을 저하시킬 수 있습니다")

        if settings.rerank_enabled and settings.rag_top_k > 20:
            warnings.append("재순위화와 많은 검색 문서 조합은 처리 시간을 크게 증가시킵니다")

        return warnings

    @classmethod
    def get_optimization_suggestions(cls) -> Dict[str, List[str]]:
        """설정 최적화 제안"""
        settings = cls.get_settings()
        suggestions = {
            'performance': [],
            'accuracy': [],
            'cost': [],
            'user_experience': []
        }

        # 성능 최적화
        if settings.rag_top_k > 5:
            suggestions['performance'].append("검색 문서 수를 3-5개로 줄여 응답 속도 향상")

        if settings.max_tokens > 2000:
            suggestions['performance'].append("max_tokens을 1000-1500으로 설정하여 응답 시간 단축")

        # 정확성 향상
        if settings.min_similarity < 0.3:
            suggestions['accuracy'].append("최소 유사도를 0.4-0.6으로 높여 관련성 향상")

        if settings.temperature > 0.7:
            suggestions['accuracy'].append("temperature를 0.2-0.5로 낮춰 일관성 있는 답변 생성")

        # 비용 절약
        if settings.max_tokens > 1500:
            suggestions['cost'].append("max_tokens 제한으로 API 비용 절약")

        # 사용자 경험
        if not settings.show_sources:
            suggestions['user_experience'].append("소스 표시를 활성화하여 답변 신뢰성 향상")

        if settings.api_timeout < 120:
            suggestions['user_experience'].append("API 타임아웃을 늘려 복잡한 질문 처리 개선")

        return suggestions

    @classmethod
    def get_setting_analytics(cls) -> Dict[str, Any]:
        """설정 사용 분석"""
        analytics = {
            'usage_patterns': {},
            'change_frequency': {},
            'popular_values': {},
            'optimization_score': 0
        }

        # 히스토리에서 패턴 분석
        history = st.session_state.get(cls.HISTORY_KEY, [])
        if history:
            # 변경 빈도 분석
            for entry in history:
                if entry.get('type') == 'batch_update':
                    for key in entry.get('changes', {}):
                        analytics['change_frequency'][key] = analytics['change_frequency'].get(key, 0) + 1
                else:
                    key = entry.get('key')
                    if key:
                        analytics['change_frequency'][key] = analytics['change_frequency'].get(key, 0) + 1

            # 인기 값 분석
            settings_values = {}
            for entry in history:
                if entry.get('type') == 'batch_update':
                    for key, change in entry.get('changes', {}).items():
                        new_val = change.get('new_value')
                        if new_val is not None:
                            if key not in settings_values:
                                settings_values[key] = {}
                            settings_values[key][str(new_val)] = settings_values[key].get(str(new_val), 0) + 1
                else:
                    key = entry.get('key')
                    new_val = entry.get('new_value')
                    if key and new_val is not None:
                        if key not in settings_values:
                            settings_values[key] = {}
                        settings_values[key][str(new_val)] = settings_values[key].get(str(new_val), 0) + 1

            analytics['popular_values'] = settings_values

        # 최적화 점수 계산
        analytics['optimization_score'] = cls._calculate_optimization_score()

        return analytics

    @classmethod
    def _calculate_optimization_score(cls) -> float:
        """설정 최적화 점수 계산 (0-100)"""
        settings = cls.get_settings()
        score = 100.0

        # 성능 점수
        if settings.rag_top_k > 10:
            score -= 15
        elif settings.rag_top_k > 5:
            score -= 5

        if settings.max_tokens > 3000:
            score -= 10
        elif settings.max_tokens > 2000:
            score -= 5

        # 정확성 점수
        if settings.min_similarity < 0.3:
            score -= 15
        elif settings.min_similarity < 0.4:
            score -= 5

        if settings.temperature > 1.0:
            score -= 10
        elif settings.temperature > 0.8:
            score -= 5

        # 사용성 점수
        if not settings.show_sources:
            score -= 10

        if settings.api_timeout < 60:
            score -= 5

        return max(0, score)

    # 기존 호환성 메서드들 (간소화된 인터페이스)
    @classmethod
    def get_settings_dict(cls) -> Dict[str, Any]:
        """설정을 딕셔너리 형태로 반환 (기존 호환성)"""
        settings = cls.get_settings()
        return {
            'model': settings.model,
            'temperature': settings.temperature,
            'system_prompt': settings.system_prompt,
            'rag_top_k': settings.rag_top_k,
            'min_similarity': settings.min_similarity,
            'rag_timeout': settings.rag_timeout,
            'api_timeout': settings.api_timeout,
            'max_tokens': settings.max_tokens,
            'top_p': settings.top_p,
            'frequency_penalty': settings.frequency_penalty,
            'context_window': settings.context_window,
            'search_type': settings.search_type
        }

    @classmethod
    def apply_to_api_request(cls, base_params: Dict[str, Any]) -> Dict[str, Any]:
        """API 요청에 현재 설정 적용 (기존 유지 + 확장)"""
        settings = cls.get_settings()

        enhanced_params = base_params.copy()

        # LLM 설정 적용
        if settings.model:
            enhanced_params["model"] = settings.model
        enhanced_params["temperature"] = settings.temperature
        enhanced_params["system_prompt"] = settings.system_prompt
        enhanced_params["max_tokens"] = settings.max_tokens
        enhanced_params["top_p"] = settings.top_p
        enhanced_params["frequency_penalty"] = settings.frequency_penalty

        # 새로운 파라미터
        if settings.presence_penalty > 0:
            enhanced_params["presence_penalty"] = settings.presence_penalty

        # RAG 설정 적용
        enhanced_params["top_k"] = settings.rag_top_k
        enhanced_params["min_score"] = settings.min_similarity
        enhanced_params["search_type"] = settings.search_type
        enhanced_params["timeout"] = settings.rag_timeout

        if settings.rerank_enabled:
            enhanced_params["rerank"] = True

        # 성능 설정
        if settings.retry_attempts > 1:
            enhanced_params["retry_attempts"] = settings.retry_attempts

        return enhanced_params

    @classmethod
    def get_validation_status(cls) -> Dict[str, Any]:
        """현재 검증 상태 반환 (기존 유지)"""
        cls.initialize()
        return st.session_state.get(cls.VALIDATION_KEY, {"is_valid": False, "errors": []})

    @classmethod
    def is_model_ready(cls) -> Tuple[bool, Optional[str]]:
        """모델 사용 준비 상태 확인 (기존 유지)"""
        settings = cls.get_settings()

        if not settings.model:
            return False, "모델이 선택되지 않았습니다"

        is_valid, errors = cls.validate_all_settings()
        if not is_valid:
            return False, f"설정 오류: {'; '.join(errors[:2])}"

        return True, None

    # 추가 편의 메서드들
    @classmethod
    def reset_to_defaults(cls, category: Optional[SettingCategory] = None):
        """설정을 기본값으로 초기화 (카테고리별 가능)"""
        if category is None:
            # 전체 초기화
            default_settings = ModelSettings()
            default_settings.last_updated = datetime.now()
            default_settings.updated_by = "reset"
            st.session_state[cls.SETTINGS_KEY] = default_settings
        else:
            # 카테고리별 초기화
            default_settings = ModelSettings()
            current_settings = cls.get_settings()

            category_fields = cls._get_category_fields(category)
            for field in category_fields:
                if hasattr(default_settings, field):
                    setattr(current_settings, field, getattr(default_settings, field))

            current_settings.last_updated = datetime.now()
            current_settings.updated_by = f"reset_{category.value}"
            current_settings.update_hash()
            st.session_state[cls.SETTINGS_KEY] = current_settings

        cls._invalidate_cache()
        logger.info(f"Settings reset: {category.value if category else 'all'}")

    @classmethod
    def _get_category_fields(cls, category: SettingCategory) -> List[str]:
        """카테고리별 설정 필드 반환"""
        field_mapping = {
            SettingCategory.LLM: ['model', 'temperature', 'max_tokens', 'top_p',
                                 'frequency_penalty', 'presence_penalty', 'system_prompt'],
            SettingCategory.RAG: ['rag_top_k', 'min_similarity', 'context_window',
                                 'chunk_size', 'chunk_overlap', 'embedding_model',
                                 'search_type', 'rerank_enabled'],
            SettingCategory.API: ['api_timeout', 'rag_timeout', 'retry_attempts', 'rate_limit'],
            SettingCategory.UI: ['show_sources', 'show_debug_info', 'auto_scroll', 'theme'],
            SettingCategory.PERFORMANCE: ['batch_size', 'cache_enabled', 'parallel_processing']
        }
        return field_mapping.get(category, [])

    @classmethod
    def export_settings(cls, include_history: bool = False) -> Dict[str, Any]:
        """설정을 내보내기 형식으로 변환 (확장)"""
        settings = cls.get_settings()
        export_data = asdict(settings)

        export_data.update({
            "export_version": "2.0",
            "exported_at": datetime.now().isoformat(),
            "exported_by": st.session_state.get('user', 'unknown')
        })

        if include_history:
            export_data["history"] = st.session_state.get(cls.HISTORY_KEY, [])
            export_data["custom_profiles"] = st.session_state.get(cls.PROFILE_KEY, {})

        return export_data

    @classmethod
    def _sync_to_legacy_session_state(cls, key: str, value: Any):
        """기존 세션 상태 키와 동기화 (하위 호환성, 기존 유지)"""
        legacy_map = {
            "model": "selected_model",
            "temperature": "temperature",
            "max_tokens": "max_tokens",
            "top_p": "top_p",
            "frequency_penalty": "frequency_penalty",
            "system_prompt": "system_prompt",
            "rag_top_k": "rag_top_k",
            "min_similarity": "min_similarity",
            "context_window": "context_window",
            "chunk_size": "chunk_size",
            "chunk_overlap": "chunk_overlap",
            "embedding_model": "embedding_model",
            "search_type": "search_type",
            "api_timeout": "api_timeout",
            "rag_timeout": "rag_timeout"
        }

        legacy_key = legacy_map.get(key, key)
        st.session_state[legacy_key] = value

    @classmethod
    def _invalidate_cache(cls):
        """설정 캐시 무효화 (기존 유지)"""
        if cls.CACHE_KEY in st.session_state:
            st.session_state[cls.CACHE_KEY] = {}


# 편의 함수들 (기존 호환성)
def get_model_settings() -> Dict[str, Any]:
    """기존 코드 호환성을 위한 함수"""
    return EnhancedModelManager.get_settings_dict()


def update_model_setting(key: str, value: Any) -> bool:
    """개별 설정 업데이트 (편의 함수)"""
    success, error = EnhancedModelManager.update_setting(key, value)
    return success


def validate_model_settings() -> Tuple[bool, List[str]]:
    """모델 설정 검증 (편의 함수)"""
    return EnhancedModelManager.validate_all_settings()


def is_model_configured() -> bool:
    """모델이 설정되어 있는지 확인 (편의 함수)"""
    is_ready, _ = EnhancedModelManager.is_model_ready()
    return is_ready


# 새로운 편의 함수들
def apply_setting_profile(profile_name: str) -> bool:
    """설정 프로필 적용 (편의 함수)"""
    success, errors = EnhancedModelManager.apply_profile(profile_name)
    return success


def get_setting_suggestions() -> Dict[str, List[str]]:
    """설정 최적화 제안 (편의 함수)"""
    return EnhancedModelManager.get_optimization_suggestions()


def calculate_settings_score() -> float:
    """설정 최적화 점수 (편의 함수)"""
    return EnhancedModelManager._calculate_optimization_score()