"""
임베딩 모듈 - macOS/conda 환경 최적화 버전 (수정됨)
Sentence Transformers를 사용한 다국어 임베딩 생성
"""
import os
import sys
import logging
from pathlib import Path
from typing import List, Optional
import numpy as np
from functools import lru_cache

# 로깅 설정
logger = logging.getLogger(__name__)

# 환경변수 설정 (모델 다운로드 경로 지정)
def setup_cache_directories():
    """캐시 디렉토리 설정"""
    # 프로젝트 루트 기준으로 캐시 디렉토리 설정
    project_root = Path(__file__).parent.parent
    cache_root = project_root / ".cache"

    # 캐시 디렉토리 생성
    cache_root.mkdir(exist_ok=True)

    # 환경변수 설정
    os.environ["TRANSFORMERS_CACHE"] = str(cache_root / "transformers")
    os.environ["HF_HOME"] = str(cache_root / "huggingface")
    os.environ["TORCH_HOME"] = str(cache_root / "torch")
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(cache_root / "sentence_transformers")

    # 디렉토리 생성
    for env_var in ["TRANSFORMERS_CACHE", "HF_HOME", "TORCH_HOME", "SENTENCE_TRANSFORMERS_HOME"]:
        Path(os.environ[env_var]).mkdir(parents=True, exist_ok=True)

    logger.info(f"Cache directories set up in: {cache_root}")
    return cache_root

# 캐시 디렉토리 초기 설정
try:
    setup_cache_directories()
except Exception as e:
    logger.warning(f"Failed to setup cache directories: {e}")

# 이제 sentence_transformers import
try:
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    logger.error(f"Failed to import sentence_transformers: {e}")
    raise

# 기본 모델 설정
DEFAULT_MODEL = "intfloat/multilingual-e5-large-instruct"
FALLBACK_MODELS = [
    "intfloat/multilingual-e5-base",
    "intfloat/e5-large-v2",
    "sentence-transformers/all-MiniLM-L6-v2"
]

# 전역 모델 인스턴스
_model_instance: Optional[SentenceTransformer] = None
_model_lock = False


def get_model_name(model: SentenceTransformer) -> str:
    """모델 이름을 안전하게 가져오기"""
    # 여러 가능한 속성들을 시도
    for attr in ['model_name', '_model_name', 'model_name_or_path', '_model_name_or_path']:
        if hasattr(model, attr):
            value = getattr(model, attr)
            if value:
                return str(value)

    # 모델 설정에서 찾기 시도
    if hasattr(model, '_modules') and hasattr(model._modules, '0'):
        first_module = model._modules['0']
        if hasattr(first_module, 'auto_model') and hasattr(first_module.auto_model, 'config'):
            config = first_module.auto_model.config
            if hasattr(config, '_name_or_path'):
                return str(config._name_or_path)
            if hasattr(config, 'name_or_path'):
                return str(config.name_or_path)

    # 기본값 반환
    return "unknown"


@lru_cache(maxsize=1)
def get_model(model_name: str = DEFAULT_MODEL) -> SentenceTransformer:
    """
    임베딩 모델 로드 (캐시된 인스턴스 반환)

    Args:
        model_name: 사용할 모델명

    Returns:
        SentenceTransformer 모델 인스턴스

    Raises:
        RuntimeError: 모델 로드 실패 시
    """
    global _model_instance, _model_lock

    if _model_instance is not None:
        return _model_instance

    if _model_lock:
        # 다른 프로세스에서 로딩 중인 경우 대기
        import time
        for _ in range(30):  # 최대 30초 대기
            time.sleep(1)
            if _model_instance is not None:
                return _model_instance
        raise RuntimeError("Model loading timeout")

    _model_lock = True

    try:
        logger.info(f"Loading embedding model: {model_name}")

        # 모델 로드 시도
        models_to_try = [model_name] + FALLBACK_MODELS

        for idx, model_to_load in enumerate(models_to_try):
            try:
                logger.info(f"Attempting to load model {idx+1}/{len(models_to_try)}: {model_to_load}")

                # 모델 로드 옵션
                model_kwargs = {
                    'device': 'cpu',  # CPU 강제 사용 (Apple Silicon 호환성)
                    'trust_remote_code': True,
                }

                # 캐시 디렉토리가 설정되었는지 확인
                if "SENTENCE_TRANSFORMERS_HOME" in os.environ:
                    logger.info(f"Using cache directory: {os.environ['SENTENCE_TRANSFORMERS_HOME']}")

                _model_instance = SentenceTransformer(
                    model_to_load,
                    **model_kwargs
                )

                # 모델 이름 안전하게 가져오기
                actual_model_name = get_model_name(_model_instance)
                logger.info(f"Successfully loaded model: {model_to_load} (actual: {actual_model_name})")
                logger.info(f"Model max sequence length: {_model_instance.max_seq_length}")

                # 모델 테스트
                test_text = "테스트 텍스트"
                test_embedding = _model_instance.encode([test_text], convert_to_tensor=False)
                logger.info(f"Model test successful. Embedding shape: {test_embedding.shape}")

                break

            except Exception as e:
                logger.warning(f"Failed to load model {model_to_load}: {e}")
                if idx == len(models_to_try) - 1:
                    raise RuntimeError(f"All models failed to load. Last error: {e}")
                continue

        return _model_instance

    except Exception as e:
        logger.error(f"Model loading failed: {e}")
        raise RuntimeError(f"Embedding model loading failed: {e}")

    finally:
        _model_lock = False


@lru_cache(maxsize=128)
def _cached_embed_single(text: str, prefix: str = "query") -> np.ndarray:
    """
    단일 텍스트 임베딩 (캐시됨)

    Args:
        text: 임베딩할 텍스트
        prefix: 임베딩 prefix (query, passage)

    Returns:
        정규화된 임베딩 벡터
    """
    try:
        model = get_model()

        # E5 모델의 경우 prefix 추가 (모델 이름 안전하게 확인)
        model_name = get_model_name(model).lower()
        if "e5" in model_name:
            prefixed_text = f"{prefix}: {text}"
        else:
            prefixed_text = text

        embedding = model.encode(
            [prefixed_text],
            batch_size=1,
            convert_to_tensor=False,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        return embedding[0]

    except Exception as e:
        logger.error(f"Single embedding failed: {e}")
        raise


def embed_texts(texts: List[str], prefix: str = "query", batch_size: int = 32) -> np.ndarray:
    """
    텍스트 리스트를 임베딩 벡터로 변환

    Args:
        texts: 임베딩할 텍스트 리스트
        prefix: 임베딩 prefix (E5 모델용)
        batch_size: 배치 크기

    Returns:
        정규화된 임베딩 벡터 배열 (shape: [len(texts), embedding_dim])

    Raises:
        RuntimeError: 임베딩 생성 실패 시
    """
    if not texts:
        return np.array([])

    try:
        # 단일 텍스트인 경우 캐시된 함수 사용
        if len(texts) == 1:
            return np.array([_cached_embed_single(texts[0], prefix)])

        # 복수 텍스트인 경우
        model = get_model()

        logger.info(f"Generating embeddings for {len(texts)} texts")

        # E5 모델의 경우 prefix 추가 (모델 이름 안전하게 확인)
        model_name = get_model_name(model).lower()
        if "e5" in model_name:
            prefixed_texts = [f"{prefix}: {text}" for text in texts]
        else:
            prefixed_texts = texts

        # 배치 처리
        embeddings = model.encode(
            prefixed_texts,
            batch_size=batch_size,
            convert_to_tensor=False,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 10,  # 10개 이상일 때만 진행률 표시
            device='cpu'  # CPU 강제 사용
        )

        logger.info(f"Successfully generated embeddings: {embeddings.shape}")
        return embeddings

    except Exception as e:
        logger.error(f"Batch embedding failed: {e}")
        raise RuntimeError(f"Failed to generate embeddings: {e}")


def get_embedding_dimension(model_name: str = DEFAULT_MODEL) -> int:
    """
    임베딩 모델의 차원 수 반환

    Args:
        model_name: 모델명

    Returns:
        임베딩 차원 수
    """
    try:
        model = get_model(model_name)
        # 테스트 임베딩으로 차원 확인
        test_embedding = model.encode(["test"], convert_to_tensor=False)
        return test_embedding.shape[1]
    except Exception as e:
        logger.error(f"Failed to get embedding dimension: {e}")
        # 기본값 반환
        return 1024 if "large" in model_name else 384


def clear_model_cache():
    """모델 캐시 정리"""
    global _model_instance
    _model_instance = None
    _cached_embed_single.cache_clear()
    logger.info("Model cache cleared")


def get_model_info() -> dict:
    """현재 로드된 모델 정보 반환"""
    try:
        model = get_model()
        model_name = get_model_name(model)
        return {
            "model_name": model_name,
            "max_seq_length": getattr(model, 'max_seq_length', 'unknown'),
            "device": str(getattr(model, 'device', 'unknown')),
            "cache_dir": os.environ.get("SENTENCE_TRANSFORMERS_HOME", "default"),
            "embedding_dimension": get_embedding_dimension()
        }
    except Exception as e:
        return {"error": str(e)}


# 모듈 초기화 시 환경 확인
def _check_environment():
    """환경 설정 확인"""
    logger.info("Checking embedding environment...")

    # 캐시 디렉토리 확인
    cache_dirs = {
        "transformers": os.environ.get("TRANSFORMERS_CACHE"),
        "huggingface": os.environ.get("HF_HOME"),
        "torch": os.environ.get("TORCH_HOME"),
        "sentence_transformers": os.environ.get("SENTENCE_TRANSFORMERS_HOME")
    }

    for name, path in cache_dirs.items():
        if path and Path(path).exists():
            logger.info(f"✅ {name} cache: {path}")
        else:
            logger.warning(f"⚠️  {name} cache not set or missing: {path}")


# 모듈 로드 시 환경 체크
if __name__ != "__main__":
    _check_environment()


# 테스트용 메인 함수
if __name__ == "__main__":
    # 테스트 코드
    print("🧪 Embedding 모듈 테스트")

    try:
        # 1. 환경 확인
        print("\n1. 환경 설정 확인:")
        _check_environment()

        # 2. 모델 로드 테스트
        print("\n2. 모델 로드 테스트:")
        model_info = get_model_info()
        for key, value in model_info.items():
            print(f"   {key}: {value}")

        # 3. 임베딩 생성 테스트
        print("\n3. 임베딩 생성 테스트:")
        test_texts = [
            "안녕하세요, 세상!",
            "Hello, world!",
            "문서 기반 질의응답 시스템"
        ]

        embeddings = embed_texts(test_texts)
        print(f"   텍스트 수: {len(test_texts)}")
        print(f"   임베딩 형태: {embeddings.shape}")
        print(f"   첫 번째 임베딩 (처음 5개): {embeddings[0][:5]}")

        print("\n✅ 모든 테스트 통과!")

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()