"""
임베딩 모듈 - 지연 로딩 및 캐시 개선 버전
"""
from sentence_transformers import SentenceTransformer
import numpy as np
import os
import logging
from typing import List, Optional
import functools

logger = logging.getLogger(__name__)

# 모델 전역 변수 (지연 로딩)
_model: Optional[SentenceTransformer] = None
_model_loading = False

# 환경변수에서 설정
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large-instruct")
BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))


def get_model() -> SentenceTransformer:
    """
    임베딩 모델을 지연 로딩 방식으로 가져옴
    최초 호출 시에만 모델을 로드하고, 이후에는 캐시된 인스턴스 사용
    """
    global _model, _model_loading

    if _model is not None:
        return _model

    if _model_loading:
        # 다른 스레드에서 로딩 중인 경우 대기
        import time
        while _model_loading and _model is None:
            time.sleep(0.1)
        if _model is not None:
            return _model

    try:
        _model_loading = True
        logger.info(f"🔄 Loading embedding model: {MODEL_NAME}")

        # 캐시 디렉토리 설정
        cache_dir = os.getenv("HF_HOME", "/root/.cache/huggingface")

        # 모델 로딩 (캐시 활용)
        _model = SentenceTransformer(
            MODEL_NAME,
            cache_folder=cache_dir,
            device='cpu'  # GPU가 있다면 'cuda'로 변경
        )

        logger.info(f"✅ Embedding model loaded successfully")
        logger.info(f"📊 Model info: {_model.get_sentence_embedding_dimension()} dimensions")

        return _model

    except Exception as e:
        logger.error(f"❌ Failed to load embedding model: {e}")
        raise RuntimeError(f"Embedding model loading failed: {e}")
    finally:
        _model_loading = False


@functools.lru_cache(maxsize=1000)
def _cached_embed_single(text: str, prefix: str = "query") -> tuple:
    """
    단일 텍스트 임베딩 생성 (캐시 적용)
    tuple로 반환하여 hashable하게 만듦
    """
    model = get_model()

    # 프리픽스 적용
    if prefix and not text.startswith(prefix):
        text = f"{prefix}: {text}"

    # 임베딩 생성
    embedding = model.encode(
        text,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    return tuple(embedding.tolist())


def embed_texts(texts: List[str], prefix: str = "query") -> np.ndarray:
    """
    텍스트 리스트를 벡터로 변환

    Args:
        texts: 임베딩할 텍스트 리스트
        prefix: 텍스트 앞에 붙일 프리픽스 (E5 모델용)

    Returns:
        정규화된 임베딩 벡터 배열
    """
    if not texts:
        return np.array([])

    try:
        # 단일 텍스트인 경우 캐시 활용
        if len(texts) == 1:
            cached_result = _cached_embed_single(texts[0], prefix)
            return np.array([list(cached_result)])

        # 다중 텍스트인 경우 배치 처리
        model = get_model()

        # 프리픽스 적용
        prefixed_texts = []
        for text in texts:
            if prefix and not text.startswith(prefix):
                prefixed_texts.append(f"{prefix}: {text}")
            else:
                prefixed_texts.append(text)

        logger.debug(f"Embedding {len(texts)} texts with batch_size={BATCH_SIZE}")

        # 배치 임베딩 생성
        embeddings = model.encode(
            prefixed_texts,
            batch_size=BATCH_SIZE,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        logger.debug(f"Generated embeddings shape: {embeddings.shape}")
        return embeddings

    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise RuntimeError(f"Failed to generate embeddings: {e}")


def warmup_model():
    """
    모델 워밍업 - 시스템 시작 시 미리 호출하여 초기화
    """
    try:
        logger.info("🔥 Warming up embedding model...")
        model = get_model()

        # 테스트 임베딩 생성
        test_embedding = embed_texts(["test embedding"])
        logger.info(f"✅ Model warmup successful - shape: {test_embedding.shape}")

    except Exception as e:
        logger.error(f"❌ Model warmup failed: {e}")
        raise


def get_model_info() -> dict:
    """
    모델 정보 반환
    """
    try:
        model = get_model()
        return {
            "model_name": MODEL_NAME,
            "dimensions": model.get_sentence_embedding_dimension(),
            "max_sequence_length": getattr(model, 'max_seq_length', 'unknown'),
            "device": str(model.device),
            "is_loaded": _model is not None
        }
    except Exception as e:
        return {
            "model_name": MODEL_NAME,
            "error": str(e),
            "is_loaded": False
        }


def clear_cache():
    """
    임베딩 캐시 초기화
    """
    _cached_embed_single.cache_clear()
    logger.info("Embedding cache cleared")


# 모듈 로드 시 즉시 실행되지 않도록 함수로 래핑
def preload_model_if_needed():
    """
    환경변수가 설정된 경우에만 모델 사전 로딩
    """
    if os.getenv("PRELOAD_EMBEDDING_MODEL", "false").lower() == "true":
        try:
            warmup_model()
        except Exception as e:
            logger.warning(f"Model preloading failed: {e}")


# 환경변수 기반 사전 로딩
if __name__ == "__main__":
    # 직접 실행 시 워밍업 수행
    warmup_model()
else:
    # 모듈 import 시 조건부 사전 로딩
    preload_model_if_needed()