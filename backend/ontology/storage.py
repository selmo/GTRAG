"""
Ontology 저장소 - Qdrant 기반 온톨로지 데이터 관리
기존 시스템의 qdrant 클라이언트를 활용한 통합 저장소
"""
import logging
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict, Counter

from qdrant_client.http import models as rest
from backend.core.qdrant import get_qdrant_client  # 기존 싱글턴 활용
from backend.embedding.embedder import embed_texts, get_embedding_dimension

# extractor의 데이터 모델들 import
from .extractor import OntologyResult, KeywordInfo, EntityInfo, DocumentMetadata, ContextInfo

logger = logging.getLogger(__name__)

# 온톨로지 컬렉션 이름
ONTOLOGY_COLLECTION = "ontology"
KEYWORDS_COLLECTION = "keywords"  # 키워드별 검색을 위한 별도 컬렉션


class OntologyStorage:
    """온톨로지 데이터 저장 및 조회 관리자"""

    def __init__(self):
        self.client = get_qdrant_client()  # 기존 클라이언트 재사용
        self._ensure_collections()

    def _ensure_collections(self):
        """필요한 컬렉션들을 생성"""
        try:
            embedding_dim = get_embedding_dimension()

            # 1. 메인 온톨로지 컬렉션 (문서별 온톨로지 데이터)
            collections = self.client.get_collections().collections
            collection_names = [col.name for col in collections]

            if ONTOLOGY_COLLECTION not in collection_names:
                self.client.create_collection(
                    collection_name=ONTOLOGY_COLLECTION,
                    vectors_config=rest.VectorParams(
                        size=embedding_dim,
                        distance=rest.Distance.COSINE
                    )
                )
                logger.info(f"Created ontology collection: {ONTOLOGY_COLLECTION}")

            # 2. 키워드 컬렉션 (키워드별 검색용)
            if KEYWORDS_COLLECTION not in collection_names:
                self.client.create_collection(
                    collection_name=KEYWORDS_COLLECTION,
                    vectors_config=rest.VectorParams(
                        size=embedding_dim,
                        distance=rest.Distance.COSINE
                    )
                )
                logger.info(f"Created keywords collection: {KEYWORDS_COLLECTION}")

        except Exception as e:
            logger.error(f"Failed to ensure collections: {e}")
            raise

    def store_ontology(self, ontology_result: OntologyResult) -> bool:
        """온톨로지 결과를 저장"""
        try:
            logger.info(f"Storing ontology for document: {ontology_result.source}")

            # 1. 메인 온톨로지 데이터 저장
            self._store_main_ontology(ontology_result)

            # 2. 키워드별 데이터 저장
            self._store_keywords(ontology_result)

            logger.info(f"Successfully stored ontology for {ontology_result.source}")
            return True

        except Exception as e:
            logger.error(f"Failed to store ontology: {e}")
            return False

    def _store_main_ontology(self, result: OntologyResult):
        """메인 온톨로지 데이터 저장"""
        # 문서 전체 요약을 위한 임베딩 생성
        summary_text = self._create_document_summary(result)
        embedding = embed_texts([summary_text], prefix="passage")[0]

        point = rest.PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding.tolist() if hasattr(embedding, "tolist") else embedding,
            payload={
                # 기본 정보
                "doc_id": result.doc_id,
                "source": result.source,
                "extracted_at": result.extracted_at.isoformat(),
                "type": "ontology_main",

                # 메타데이터
                "language": result.metadata.language,
                "document_type": result.metadata.document_type,
                "estimated_domain": result.metadata.estimated_domain,
                "text_statistics": result.metadata.text_statistics,
                "structure_info": result.metadata.structure_info,

                # 키워드 요약
                "keyword_count": len(result.keywords),
                "top_keywords": [kw.term for kw in result.keywords[:10]],
                "keyword_categories": list(set(kw.category for kw in result.keywords)),

                # 개체명 요약
                "entity_count": len(result.metadata.key_entities),
                "entity_types": list(set(ent.label for ent in result.metadata.key_entities)),
                "entities": [ent.text for ent in result.metadata.key_entities[:20]],

                # 컨텍스트 정보
                "main_topics": result.context.main_topics,
                "related_concepts": result.context.related_concepts,
                "domain_indicators": result.context.domain_indicators,
                "cluster_count": len(result.context.semantic_clusters),

                # 성능 통계
                "processing_stats": result.processing_stats,

                # 검색용 통합 텍스트
                "searchable_content": summary_text
            }
        )

        self.client.upsert(
            collection_name=ONTOLOGY_COLLECTION,
            points=[point]
        )

    def _store_keywords(self, result: OntologyResult):
        """키워드별 데이터 저장"""
        points = []

        for keyword in result.keywords:
            # 키워드별 임베딩 생성
            embedding = embed_texts([keyword.term], prefix="query")[0]

            point = rest.PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding.tolist() if hasattr(embedding, "tolist") else embedding,
                payload={
                    # 키워드 정보
                    "keyword": keyword.term,
                    "score": keyword.score,
                    "frequency": keyword.frequency,
                    "category": keyword.category,
                    "positions": keyword.positions,

                    # 문서 연결 정보
                    "doc_id": result.doc_id,
                    "source": result.source,
                    "document_type": result.metadata.document_type,
                    "estimated_domain": result.metadata.estimated_domain,
                    "language": result.metadata.language,

                    # 컨텍스트 연결
                    "related_topics": result.context.main_topics,
                    "related_concepts": result.context.related_concepts,

                    # 메타 정보
                    "type": "keyword",
                    "extracted_at": result.extracted_at.isoformat()
                }
            )
            points.append(point)

        if points:
            # 배치로 저장 (성능 최적화)
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.client.upsert(
                    collection_name=KEYWORDS_COLLECTION,
                    points=batch
                )

    def _create_document_summary(self, result: OntologyResult) -> str:
        """문서 요약 텍스트 생성 (검색용)"""
        summary_parts = []

        # 기본 정보
        summary_parts.append(f"문서: {result.source}")
        summary_parts.append(f"유형: {result.metadata.document_type}")
        summary_parts.append(f"도메인: {result.metadata.estimated_domain}")

        # 주요 키워드
        top_keywords = [kw.term for kw in result.keywords[:15]]
        if top_keywords:
            summary_parts.append(f"키워드: {', '.join(top_keywords)}")

        # 주요 개체명
        entities = [ent.text for ent in result.metadata.key_entities[:10]]
        if entities:
            summary_parts.append(f"개체명: {', '.join(entities)}")

        # 주제
        if result.context.main_topics:
            summary_parts.append(f"주제: {', '.join(result.context.main_topics)}")

        # 관련 개념
        if result.context.related_concepts:
            summary_parts.append(f"관련개념: {', '.join(result.context.related_concepts[:10])}")

        return " | ".join(summary_parts)

    # ────────────────────── 조회 기능 ──────────────────────

    def get_document_ontology(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """특정 문서의 온톨로지 조회"""
        try:
            results, _ = self.client.scroll(
                collection_name=ONTOLOGY_COLLECTION,
                scroll_filter=rest.Filter(
                    must=[
                        rest.FieldCondition(
                            key="doc_id",
                            match=rest.MatchValue(value=doc_id)
                        ),
                        rest.FieldCondition(
                            key="type",
                            match=rest.MatchValue(value="ontology_main")
                        )
                    ]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False
            )

            if results:
                return results[0].payload
            return None

        except Exception as e:
            logger.error(f"Failed to get document ontology: {e}")
            return None

    def search_by_keyword(self, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        """키워드로 관련 문서 검색"""
        try:
            # 키워드 임베딩 생성
            keyword_embedding = embed_texts([keyword], prefix="query")[0]

            # 유사한 키워드 검색
            results = self.client.search(
                collection_name=KEYWORDS_COLLECTION,
                query_vector=keyword_embedding.tolist() if hasattr(keyword_embedding, "tolist") else keyword_embedding,
                limit=limit,
                score_threshold=0.7
            )

            return [
                {
                    "keyword": hit.payload.get("keyword"),
                    "score": hit.score,
                    "doc_id": hit.payload.get("doc_id"),
                    "source": hit.payload.get("source"),
                    "category": hit.payload.get("category"),
                    "document_type": hit.payload.get("document_type"),
                    "estimated_domain": hit.payload.get("estimated_domain")
                }
                for hit in results
            ]

        except Exception as e:
            logger.error(f"Failed to search by keyword: {e}")
            return []

    def search_by_domain(self, domain: str, limit: int = 20) -> List[Dict[str, Any]]:
        """도메인별 문서 검색"""
        try:
            results, _ = self.client.scroll(
                collection_name=ONTOLOGY_COLLECTION,
                scroll_filter=rest.Filter(
                    must=[
                        rest.FieldCondition(
                            key="estimated_domain",
                            match=rest.MatchValue(value=domain)
                        ),
                        rest.FieldCondition(
                            key="type",
                            match=rest.MatchValue(value="ontology_main")
                        )
                    ]
                ),
                limit=limit,
                with_payload=True,
                with_vectors=False
            )

            return [
                {
                    "doc_id": hit.payload.get("doc_id"),
                    "source": hit.payload.get("source"),
                    "document_type": hit.payload.get("document_type"),
                    "keyword_count": hit.payload.get("keyword_count"),
                    "top_keywords": hit.payload.get("top_keywords", []),
                    "main_topics": hit.payload.get("main_topics", []),
                    "extracted_at": hit.payload.get("extracted_at")
                }
                for hit in results
            ]

        except Exception as e:
            logger.error(f"Failed to search by domain: {e}")
            return []

    def get_similar_documents(self, doc_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """유사한 문서 찾기"""
        try:
            # 기준 문서의 온톨로지 가져오기
            base_doc = self.get_document_ontology(doc_id)
            if not base_doc:
                return []

            # 기준 문서와 유사한 문서 검색
            search_text = base_doc.get("searchable_content", "")
            if not search_text:
                return []

            embedding = embed_texts([search_text], prefix="passage")[0]

            results = self.client.search(
                collection_name=ONTOLOGY_COLLECTION,
                query_vector=embedding.tolist() if hasattr(embedding, "tolist") else embedding,
                query_filter=rest.Filter(
                    must_not=[
                        rest.FieldCondition(
                            key="doc_id",
                            match=rest.MatchValue(value=doc_id)
                        )
                    ]
                ),
                limit=limit,
                score_threshold=0.6
            )

            return [
                {
                    "doc_id": hit.payload.get("doc_id"),
                    "source": hit.payload.get("source"),
                    "similarity_score": hit.score,
                    "document_type": hit.payload.get("document_type"),
                    "estimated_domain": hit.payload.get("estimated_domain"),
                    "top_keywords": hit.payload.get("top_keywords", []),
                    "main_topics": hit.payload.get("main_topics", [])
                }
                for hit in results
            ]

        except Exception as e:
            logger.error(f"Failed to find similar documents: {e}")
            return []

    # ────────────────────── 통계 및 분석 ──────────────────────

    def get_ontology_statistics(self) -> Dict[str, Any]:
        """온톨로지 통계 조회"""
        try:
            # 전체 문서 수
            main_docs, _ = self.client.scroll(
                collection_name=ONTOLOGY_COLLECTION,
                scroll_filter=rest.Filter(
                    must=[
                        rest.FieldCondition(
                            key="type",
                            match=rest.MatchValue(value="ontology_main")
                        )
                    ]
                ),
                limit=10000,
                with_payload=True,
                with_vectors=False
            )

            # 키워드 통계
            keywords, _ = self.client.scroll(
                collection_name=KEYWORDS_COLLECTION,
                limit=10000,
                with_payload=True,
                with_vectors=False
            )

            # 도메인별 분포
            domain_counts = Counter()
            doc_type_counts = Counter()
            language_counts = Counter()

            for doc in main_docs:
                payload = doc.payload
                domain_counts[payload.get("estimated_domain", "unknown")] += 1
                doc_type_counts[payload.get("document_type", "unknown")] += 1
                language_counts[payload.get("language", "unknown")] += 1

            # 키워드 카테고리별 분포
            keyword_category_counts = Counter()
            for kw in keywords:
                keyword_category_counts[kw.payload.get("category", "unknown")] += 1

            return {
                "total_documents": len(main_docs),
                "total_keywords": len(keywords),
                "domain_distribution": dict(domain_counts.most_common()),
                "document_type_distribution": dict(doc_type_counts.most_common()),
                "language_distribution": dict(language_counts.most_common()),
                "keyword_category_distribution": dict(keyword_category_counts.most_common()),
                "avg_keywords_per_doc": len(keywords) / len(main_docs) if main_docs else 0
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    def get_top_keywords(self, limit: int = 50, category: Optional[str] = None,
                         domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """상위 키워드 조회"""
        try:
            # 필터 조건 구성
            filter_conditions = []

            if category:
                filter_conditions.append(
                    rest.FieldCondition(
                        key="category",
                        match=rest.MatchValue(value=category)
                    )
                )

            if domain:
                filter_conditions.append(
                    rest.FieldCondition(
                        key="estimated_domain",
                        match=rest.MatchValue(value=domain)
                    )
                )

            scroll_filter = rest.Filter(must=filter_conditions) if filter_conditions else None

            # 키워드 조회
            results, _ = self.client.scroll(
                collection_name=KEYWORDS_COLLECTION,
                scroll_filter=scroll_filter,
                limit=limit * 5,  # 중복 제거를 위해 더 많이 가져옴
                with_payload=True,
                with_vectors=False
            )

            # 키워드별 집계
            keyword_stats = defaultdict(lambda: {
                "frequency_sum": 0,
                "score_sum": 0.0,
                "doc_count": 0,
                "documents": set(),
                "categories": set(),
                "domains": set()
            })

            for hit in results:
                payload = hit.payload
                keyword = payload.get("keyword", "")

                stats = keyword_stats[keyword]
                stats["frequency_sum"] += payload.get("frequency", 0)
                stats["score_sum"] += payload.get("score", 0.0)
                stats["doc_count"] += 1
                stats["documents"].add(payload.get("source", ""))
                stats["categories"].add(payload.get("category", ""))
                stats["domains"].add(payload.get("estimated_domain", ""))

            # 정렬 및 반환
            top_keywords = []
            for keyword, stats in keyword_stats.items():
                top_keywords.append({
                    "keyword": keyword,
                    "total_frequency": stats["frequency_sum"],
                    "avg_score": stats["score_sum"] / stats["doc_count"],
                    "document_count": stats["doc_count"],
                    "categories": list(stats["categories"]),
                    "domains": list(stats["domains"]),
                    "sample_documents": list(stats["documents"])[:5]
                })

            # 빈도와 문서 수를 기준으로 정렬
            top_keywords.sort(
                key=lambda x: (x["document_count"], x["total_frequency"]),
                reverse=True
            )

            return top_keywords[:limit]

        except Exception as e:
            logger.error(f"Failed to get top keywords: {e}")
            return []

    # ────────────────────── 삭제 기능 ──────────────────────

    def delete_document_ontology(self, doc_id: str) -> bool:
        """문서의 온톨로지 데이터 삭제"""
        try:
            # 메인 온톨로지 삭제
            self.client.delete(
                collection_name=ONTOLOGY_COLLECTION,
                points_selector=rest.FilterSelector(
                    filter=rest.Filter(
                        must=[
                            rest.FieldCondition(
                                key="doc_id",
                                match=rest.MatchValue(value=doc_id)
                            )
                        ]
                    )
                )
            )

            # 관련 키워드 삭제
            self.client.delete(
                collection_name=KEYWORDS_COLLECTION,
                points_selector=rest.FilterSelector(
                    filter=rest.Filter(
                        must=[
                            rest.FieldCondition(
                                key="doc_id",
                                match=rest.MatchValue(value=doc_id)
                            )
                        ]
                    )
                )
            )

            logger.info(f"Deleted ontology data for document: {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document ontology: {e}")
            return False

    def clear_all_ontology(self) -> bool:
        """모든 온톨로지 데이터 삭제 (주의!)"""
        try:
            # 컬렉션 삭제 후 재생성
            self.client.delete_collection(ONTOLOGY_COLLECTION)
            self.client.delete_collection(KEYWORDS_COLLECTION)

            # 컬렉션 재생성
            self._ensure_collections()

            logger.warning("All ontology data cleared!")
            return True

        except Exception as e:
            logger.error(f"Failed to clear ontology data: {e}")
            return False


# ────────────────────── 유틸리티 함수 ──────────────────────

def get_ontology_storage() -> OntologyStorage:
    """온톨로지 저장소 인스턴스 반환"""
    return OntologyStorage()


# 테스트용 함수
if __name__ == "__main__":
    storage = OntologyStorage()
    stats = storage.get_ontology_statistics()
    print("Ontology Statistics:", stats)