"""
개선된 벡터 검색 모듈 - 한국어 검색 최적화 (호스트 설정 수정)
"""
import qdrant_client
from qdrant_client.http import models as rest
from typing import List, Optional, Dict, Any
import logging
import re
import os

# 로깅 설정
logger = logging.getLogger(__name__)

# Qdrant 클라이언트 초기화 - 환경변수 사용
def get_qdrant_client():
    """환경변수를 고려한 Qdrant 클라이언트 생성"""
    host = os.getenv("QDRANT_HOST", "localhost")  # 기본값을 localhost로 변경
    port = int(os.getenv("QDRANT_PORT", "6333"))

    logger.info(f"Connecting to Qdrant at {host}:{port}")

    try:
        client = qdrant_client.QdrantClient(host=host, port=port)
        # 연결 테스트
        client.get_collections()
        logger.info(f"Successfully connected to Qdrant at {host}:{port}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant at {host}:{port}: {e}")
        # localhost로 fallback 시도
        if host != "localhost":
            logger.info("Trying fallback to localhost...")
            try:
                client = qdrant_client.QdrantClient(host="localhost", port=port)
                client.get_collections()
                logger.info(f"Successfully connected to Qdrant fallback at localhost:{port}")
                return client
            except Exception as e2:
                logger.error(f"Fallback to localhost also failed: {e2}")
        raise e

# 전역 클라이언트 인스턴스
client = None

def get_client():
    """클라이언트 인스턴스 반환"""
    global client
    if client is None:
        client = get_qdrant_client()
    return client

def search(qvec, top_k=3, lang=None, filters=None, min_score=0.3):
    """
    벡터 검색 수행 (한국어 최적화)

    Args:
        qvec: 쿼리 벡터
        top_k: 반환할 결과 수
        lang: 언어 필터 ("ko", "en", "auto")
        filters: 추가 필터 조건
        min_score: 최소 유사도 점수
    """
    try:
        qdrant_client = get_client()

        # 기본 필터 조건 구성
        filter_conditions = []

        # 언어 필터
        if lang and lang != "auto":
            if lang == "ko" or lang == "korean":
                # 한국어 컨텐츠 우선
                filter_conditions.append(
                    rest.FieldCondition(
                        key="has_korean",
                        match=rest.MatchValue(value=True)
                    )
                )
            elif lang == "en" or lang == "english":
                # 영어 컨텐츠 우선
                filter_conditions.append(
                    rest.FieldCondition(
                        key="has_english",
                        match=rest.MatchValue(value=True)
                    )
                )

        # 추가 필터 조건
        if filters:
            # 파일 타입 필터
            if "file_type" in filters:
                filter_conditions.append(
                    rest.FieldCondition(
                        key="file_type",
                        match=rest.MatchValue(value=filters["file_type"])
                    )
                )

            # 날짜 범위 필터 (예시)
            if "date_from" in filters:
                filter_conditions.append(
                    rest.FieldCondition(
                        key="upload_timestamp",
                        range=rest.Range(gte=filters["date_from"])
                    )
                )

            # 소스 파일 필터
            if "source" in filters:
                filter_conditions.append(
                    rest.FieldCondition(
                        key="source",
                        match=rest.MatchValue(value=filters["source"])
                    )
                )

        # 필터 객체 생성
        query_filter = None
        if filter_conditions:
            query_filter = rest.Filter(must=filter_conditions)

        # 벡터 검색 수행
        results = qdrant_client.search(
            collection_name="chunks",
            query_vector=qvec,
            limit=top_k * 2,  # 여유분을 두고 더 많이 검색
            query_filter=query_filter,
            score_threshold=min_score  # 최소 점수 필터링
        )

        # 결과 후처리
        processed_results = []
        for result in results:
            # 점수가 너무 낮은 결과 제외
            if result.score < min_score:
                continue

            processed_results.append(result)

            # 원하는 개수만큼 수집되면 중단
            if len(processed_results) >= top_k:
                break

        logger.info(f"Vector search completed: {len(processed_results)} results (score >= {min_score})")

        return processed_results

    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return []


def hybrid_search(query_text: str, qvec, top_k=3, lang=None, boost_korean=True):
    """
    하이브리드 검색 (벡터 + 키워드)

    Args:
        query_text: 원본 쿼리 텍스트
        qvec: 쿼리 벡터
        top_k: 반환할 결과 수
        lang: 언어 힌트
        boost_korean: 한국어 매칭 부스트 여부
    """
    try:
        # 1단계: 벡터 검색
        vector_results = search(qvec, top_k=top_k*2, lang=lang)

        if not vector_results:
            return []

        # 2단계: 키워드 매칭으로 점수 조정
        enhanced_results = []

        # 쿼리에서 키워드 추출
        keywords = extract_keywords(query_text, lang)

        for result in vector_results:
            content = result.payload.get("content", "")
            enhanced_score = result.score

            # 키워드 매칭 보너스
            keyword_matches = 0
            for keyword in keywords:
                if keyword.lower() in content.lower():
                    keyword_matches += 1
                    # 정확한 매칭에 보너스
                    if keyword in content:
                        enhanced_score += 0.1
                    else:
                        enhanced_score += 0.05

            # 한국어 쿼리이고 한국어 결과인 경우 부스트
            if boost_korean and has_korean(query_text) and result.payload.get("has_korean", False):
                enhanced_score += 0.1

            # 결과 객체에 향상된 점수 추가
            result.score = min(enhanced_score, 1.0)  # 최대 1.0으로 제한
            result.payload["keyword_matches"] = keyword_matches

            enhanced_results.append(result)

        # 향상된 점수로 재정렬
        enhanced_results.sort(key=lambda x: x.score, reverse=True)

        return enhanced_results[:top_k]

    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        return search(qvec, top_k, lang)  # 실패 시 일반 검색으로 fallback


def extract_keywords(text: str, lang: str = None) -> List[str]:
    """텍스트에서 키워드 추출"""
    if not text:
        return []

    # 기본적인 키워드 추출
    # 공백과 구두점으로 분리
    words = re.findall(r'\b\w+\b', text)

    # 너무 짧은 단어 제외 (한국어는 1글자, 영어는 2글자 이상)
    keywords = []
    for word in words:
        if has_korean(word) and len(word) >= 1:
            keywords.append(word)
        elif len(word) >= 2:
            keywords.append(word)

    return list(set(keywords))  # 중복 제거


def has_korean(text: str) -> bool:
    """텍스트에 한국어가 포함되어 있는지 확인"""
    return bool(re.search(r'[가-힣]', text))


def search_with_rerank(qvec, query_text: str, top_k=3, lang=None):
    """
    재순위화를 포함한 검색

    Args:
        qvec: 쿼리 벡터
        query_text: 원본 쿼리 텍스트
        top_k: 최종 반환할 결과 수
        lang: 언어 힌트
    """
    try:
        # 1단계: 더 많은 후보 검색
        candidates = search(qvec, top_k=top_k*3, lang=lang, min_score=0.2)

        if not candidates:
            return []

        # 2단계: 재순위화
        reranked_results = []

        for candidate in candidates:
            content = candidate.payload.get("content", "")

            # 재순위화 점수 계산
            rerank_score = calculate_rerank_score(
                query_text=query_text,
                content=content,
                vector_score=candidate.score,
                metadata=candidate.payload
            )

            # 새로운 점수로 업데이트
            candidate.score = rerank_score
            reranked_results.append(candidate)

        # 재순위화된 점수로 정렬
        reranked_results.sort(key=lambda x: x.score, reverse=True)

        return reranked_results[:top_k]

    except Exception as e:
        logger.error(f"Search with rerank failed: {e}")
        return search(qvec, top_k, lang)


def calculate_rerank_score(query_text: str, content: str, vector_score: float, metadata: Dict) -> float:
    """재순위화 점수 계산"""
    base_score = vector_score

    # 1. 키워드 매칭 점수
    query_keywords = extract_keywords(query_text)
    content_lower = content.lower()

    keyword_score = 0
    for keyword in query_keywords:
        if keyword.lower() in content_lower:
            # 정확한 매칭
            if keyword in content:
                keyword_score += 0.1
            else:
                keyword_score += 0.05

    # 2. 언어 일치 보너스
    language_bonus = 0
    if has_korean(query_text) and metadata.get("has_korean", False):
        language_bonus = 0.1
    elif not has_korean(query_text) and metadata.get("has_english", False):
        language_bonus = 0.05

    # 3. 컨텐츠 품질 점수
    quality_score = 0
    content_length = len(content)

    # 적당한 길이의 컨텐츠 선호 (너무 짧거나 길지 않은)
    if 100 <= content_length <= 1000:
        quality_score = 0.05
    elif 50 <= content_length <= 2000:
        quality_score = 0.02

    # 4. 최신성 보너스 (옵션)
    recency_bonus = 0
    # 구현 필요시 추가

    # 최종 점수 계산
    final_score = base_score + keyword_score + language_bonus + quality_score + recency_bonus

    return min(final_score, 1.0)  # 최대 1.0으로 제한


def get_collection_stats() -> Dict[str, Any]:
    """컬렉션 통계 정보 반환"""
    try:
        qdrant_client = get_client()
        collection_info = qdrant_client.get_collection("chunks")

        stats = {
            "total_vectors": collection_info.vectors_count,
            "indexed_vectors": collection_info.indexed_vectors_count,
            "status": collection_info.status,
            "optimizer_status": collection_info.optimizer_status,
        }

        # 추가 통계 (스크롤을 통한 샘플링)
        try:
            sample_results = qdrant_client.scroll(
                collection_name="chunks",
                limit=100,
                with_payload=True
            )[0]

            korean_docs = sum(1 for r in sample_results if r.payload.get("has_korean", False))
            english_docs = sum(1 for r in sample_results if r.payload.get("has_english", False))

            stats.update({
                "sample_size": len(sample_results),
                "korean_docs_ratio": korean_docs / len(sample_results) if sample_results else 0,
                "english_docs_ratio": english_docs / len(sample_results) if sample_results else 0,
            })

        except Exception as e:
            logger.warning(f"Failed to get additional stats: {e}")

        return stats

    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        return {"error": str(e)}


def search_similar_documents(doc_id: str, top_k: int = 5) -> List:
    """특정 문서와 유사한 문서들 검색"""
    try:
        qdrant_client = get_client()

        # 1. 원본 문서 벡터 가져오기
        points = qdrant_client.retrieve(
            collection_name="chunks",
            ids=[doc_id],
            with_vectors=True
        )

        if not points:
            return []

        original_vector = points[0].vector

        # 2. 유사한 문서 검색 (원본 제외)
        results = qdrant_client.search(
            collection_name="chunks",
            query_vector=original_vector,
            limit=top_k + 1,  # +1 for excluding original
            query_filter=rest.Filter(
                must_not=[
                    rest.FieldCondition(
                        key="chunk_id",
                        match=rest.MatchValue(value=doc_id)
                    )
                ]
            )
        )

        return results[:top_k]

    except Exception as e:
        logger.error(f"Similar document search failed: {e}")
        return []


# 하위 호환성을 위한 기본 search 함수 유지
def search_default(qvec, top_k=3, lang=None):
    """기본 검색 함수 (하위 호환성)"""
    return search(qvec, top_k, lang)