"""
Ontology API 라우터 - 온톨로지 추출 및 관리 엔드포인트
"""
import logging
import time
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, Path as ApiPath, BackgroundTasks
from fastapi.responses import JSONResponse

# 기존 시스템 임포트
from backend.api.deps import qdrant_dep
from backend.core.logging import get_logger

# 온톨로지 모듈 임포트
from ...ontology.extractor import OntologyExtractor, extract_ontology_from_chunks
from ...ontology.storage import OntologyStorage, get_ontology_storage
from ...ontology.models import (
    # 요청 모델
    KeywordSearchRequest, DomainSearchRequest, SimilarDocumentsRequest,
    TopKeywordsRequest, BatchExtractionRequest, ExtractionConfig,

    # 응답 모델
    OntologyResultModel, KeywordSearchResult, DocumentSummary,
    SimilarDocumentResult, TopKeywordResult, OntologyStatistics,
    BatchExtractionResult, SystemHealthModel, SuccessResponse,

    # 변환 함수
    convert_ontology_result_to_model
)

logger = get_logger("ontology_api")
router = APIRouter(prefix="/v1/ontology")

# 온톨로지 추출기 인스턴스 (전역)
_extractor_instance = None

def get_ontology_extractor() -> OntologyExtractor:
    """온톨로지 추출기 인스턴스 반환"""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = OntologyExtractor()
    return _extractor_instance


# ────────────────────── 시스템 관리 (먼저 정의) ──────────────────────

@router.get("/health",
            response_model=SystemHealthModel,
            summary="시스템 상태 확인",
            description="온톨로지 시스템의 상태를 확인합니다.")
async def get_system_health(
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """시스템 상태 확인"""
    try:
        # 컬렉션 상태 확인
        collections_status = {}
        try:
            collections = storage.client.get_collections().collections
            collection_names = [col.name for col in collections]
            collections_status["ontology"] = "ontology" in collection_names
            collections_status["keywords"] = "keywords" in collection_names
        except:
            collections_status = {"ontology": False, "keywords": False}

        # 임베딩 모델 상태 확인
        embedding_status = True
        try:
            from backend.embedding.embedder import get_model
            get_model()
        except:
            embedding_status = False

        # KeyBERT 상태 확인
        keybert_status = True
        try:
            import keybert
        except ImportError:
            keybert_status = False

        # spaCy 상태 확인
        spacy_status = True
        try:
            import spacy
        except ImportError:
            spacy_status = False

        # 통계 조회
        stats = storage.get_ontology_statistics()

        return SystemHealthModel(
            ontology_collections_status=collections_status,
            embedding_model_status=embedding_status,
            keybert_available=keybert_status,
            spacy_available=spacy_status,
            total_documents=stats.get("total_documents", 0),
            total_keywords=stats.get("total_keywords", 0),
            last_extraction=None  # TODO: 마지막 추출 시간 추적
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.delete("/clear",
               response_model=SuccessResponse,
               summary="모든 온톨로지 데이터 삭제",
               description="⚠️ 주의: 모든 온톨로지 데이터를 삭제합니다.")
async def clear_all_ontology(
    confirm: bool = Query(..., description="삭제 확인 (true 필수)"),
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """모든 온톨로지 데이터 삭제"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required: set confirm=true to proceed"
        )

    try:
        success = storage.clear_all_ontology()
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to clear ontology data"
            )

        logger.warning("All ontology data cleared!")
        return SuccessResponse(message="All ontology data cleared successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear ontology data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear ontology data: {str(e)}"
        )


@router.get("/domains",
            response_model=List[str],
            summary="도메인 목록",
            description="시스템에 등록된 모든 도메인 목록을 조회합니다.")
async def get_domains(
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """도메인 목록 조회"""
    try:
        stats = storage.get_ontology_statistics()
        domains = list(stats.get("domain_distribution", {}).keys())
        return sorted(domains)

    except Exception as e:
        logger.error(f"Failed to get domains: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get domains: {str(e)}"
        )


@router.get("/statistics",
            response_model=OntologyStatistics,
            summary="온톨로지 통계",
            description="전체 온톨로지 데이터의 통계를 조회합니다.")
async def get_ontology_statistics(
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """온톨로지 통계 조회"""
    try:
        stats = storage.get_ontology_statistics()

        return OntologyStatistics(
            total_documents=stats.get("total_documents", 0),
            total_keywords=stats.get("total_keywords", 0),
            domain_distribution=stats.get("domain_distribution", {}),
            document_type_distribution=stats.get("document_type_distribution", {}),
            language_distribution=stats.get("language_distribution", {}),
            keyword_category_distribution=stats.get("keyword_category_distribution", {}),
            avg_keywords_per_doc=stats.get("avg_keywords_per_doc", 0.0)
        )

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )


# ────────────────────── 온톨로지 추출 ──────────────────────
from backend.core.config import settings  # ⬅️ 설정 불러오기
from backend.core.config import get_default_keyword_methods

@router.post("/extract/{doc_id}",
             response_model=OntologyResultModel,
             summary="문서 온톨로지 추출",
             description="특정 문서에서 키워드, 메타데이터, 컨텍스트를 추출합니다.")
async def extract_document_ontology(
    doc_id: str = ApiPath(..., description="문서 ID"),
    force: bool = Query(default=False, description="기존 결과 무시하고 재추출"),
    methods: Optional[str] = Query(default=None, description="사용할 키워드 추출기 (예: keybert,llm)"),
    qdrant=Depends(qdrant_dep),
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """문서에서 온톨로지 추출"""
    logger.info(f"Ontology extraction requested for document: {doc_id} (methods={methods})")

    try:
        if not force:
            existing = storage.get_document_ontology(doc_id)
            if existing:
                logger.info(f"Returning existing ontology for document: {doc_id}")
                return _convert_storage_result_to_model(existing, doc_id)

        # 청크 불러오기
        chunks_data, _ = qdrant.scroll(
            collection_name="chunks",
            scroll_filter={
                "must": [
                    {"key": "doc_id", "match": {"value": doc_id}}
                ]
            },
            limit=10000,
            with_payload=True,
            with_vectors=False
        )

        if not chunks_data:
            raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

        chunks = []
        source = "unknown"
        for chunk_point in chunks_data:
            payload = chunk_point.payload
            chunks.append({'content': payload.get('content', ''), 'meta': payload})
            if source == "unknown" and payload.get('source'):
                source = payload.get('source')

        # 추출기 선택
        method_list = [m.strip().lower() for m in (methods or get_default_keyword_methods()).split(",") if m.strip()]
        extractor = get_ontology_extractor()
        result = extractor.extract_ontology(text="\n\n".join(c["content"] for c in chunks),
                                            doc_id=doc_id,
                                            source=source,
                                            chunks=[c["content"] for c in chunks],
                                            keyword_methods=method_list)

        success = storage.store_ontology(result)
        if not success:
            logger.warning(f"Failed to store ontology for document: {doc_id}")

        return convert_ontology_result_to_model(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ontology extraction failed for {doc_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ontology extraction failed: {str(e)}")



@router.get("/{doc_id}",
            response_model=OntologyResultModel,
            summary="문서 온톨로지 조회",
            description="저장된 문서의 온톨로지 정보를 조회합니다.")
async def get_document_ontology(
    doc_id: str = ApiPath(..., description="문서 ID"),
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """문서의 온톨로지 조회"""
    try:
        result = storage.get_document_ontology(doc_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Ontology not found for document: {doc_id}"
            )

        return _convert_storage_result_to_model(result, doc_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ontology for {doc_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve ontology: {str(e)}"
        )


@router.delete("/{doc_id}",
               response_model=SuccessResponse,
               summary="문서 온톨로지 삭제",
               description="문서의 온톨로지 데이터를 삭제합니다.")
async def delete_document_ontology(
    doc_id: str = ApiPath(..., description="문서 ID"),
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """문서의 온톨로지 삭제"""
    try:
        success = storage.delete_document_ontology(doc_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Ontology not found for document: {doc_id}"
            )

        logger.info(f"Deleted ontology for document: {doc_id}")
        return SuccessResponse(message=f"Ontology deleted for document: {doc_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete ontology for {doc_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete ontology: {str(e)}"
        )


# ────────────────────── 검색 기능 ──────────────────────

@router.post("/search/keywords",
             response_model=List[KeywordSearchResult],
             summary="키워드 검색",
             description="키워드를 기반으로 관련 문서와 키워드를 검색합니다.")
async def search_by_keyword(
    request: KeywordSearchRequest,
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """키워드 기반 검색"""
    try:
        logger.info(f"Keyword search: {request.keyword}")

        results = storage.search_by_keyword(
            keyword=request.keyword,
            limit=request.limit
        )

        # 응답 모델로 변환
        return [
            KeywordSearchResult(
                keyword=hit["keyword"],
                score=hit["score"],
                doc_id=hit["doc_id"],
                source=hit["source"],
                category=hit["category"],
                document_type=hit["document_type"],
                estimated_domain=hit["estimated_domain"]
            )
            for hit in results
            if hit["score"] >= request.min_score
        ]

    except Exception as e:
        logger.error(f"Keyword search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Keyword search failed: {str(e)}"
        )


@router.post("/search/domain",
             response_model=List[DocumentSummary],
             summary="도메인별 검색",
             description="특정 도메인의 문서들을 검색합니다.")
async def search_by_domain(
    request: DomainSearchRequest,
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """도메인별 문서 검색"""
    try:
        logger.info(f"Domain search: {request.domain}")

        results = storage.search_by_domain(
            domain=request.domain.value,
            limit=request.limit
        )

        # 응답 모델로 변환
        return [
            DocumentSummary(
                doc_id=hit["doc_id"],
                source=hit["source"],
                document_type=hit["document_type"],
                estimated_domain=request.domain,
                language="unknown",  # storage에서 제공하지 않음
                keyword_count=hit["keyword_count"],
                entity_count=0,  # storage에서 제공하지 않음
                top_keywords=hit["top_keywords"],
                main_topics=hit["main_topics"],
                extracted_at=datetime.fromisoformat(hit["extracted_at"])
            )
            for hit in results
        ]

    except Exception as e:
        logger.error(f"Domain search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Domain search failed: {str(e)}"
        )


@router.post("/search/similar",
             response_model=List[SimilarDocumentResult],
             summary="유사 문서 검색",
             description="특정 문서와 유사한 문서들을 찾습니다.")
async def search_similar_documents(
    request: SimilarDocumentsRequest,
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """유사 문서 검색"""
    try:
        logger.info(f"Similar documents search for: {request.doc_id}")

        results = storage.get_similar_documents(
            doc_id=request.doc_id,
            limit=request.limit
        )

        # 최소 유사도 필터링 및 응답 모델 변환
        return [
            SimilarDocumentResult(
                doc_id=hit["doc_id"],
                source=hit["source"],
                similarity_score=hit["similarity_score"],
                document_type=hit["document_type"],
                estimated_domain=hit["estimated_domain"],
                top_keywords=hit["top_keywords"],
                main_topics=hit["main_topics"]
            )
            for hit in results
            if hit["similarity_score"] >= request.min_similarity
        ]

    except Exception as e:
        logger.error(f"Similar documents search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Similar documents search failed: {str(e)}"
        )


# ────────────────────── 분석 및 통계 ──────────────────────

@router.get("/statistics",
            response_model=OntologyStatistics,
            summary="온톨로지 통계",
            description="전체 온톨로지 데이터의 통계를 조회합니다.")
async def get_ontology_statistics(
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """온톨로지 통계 조회"""
    try:
        stats = storage.get_ontology_statistics()

        return OntologyStatistics(
            total_documents=stats.get("total_documents", 0),
            total_keywords=stats.get("total_keywords", 0),
            domain_distribution=stats.get("domain_distribution", {}),
            document_type_distribution=stats.get("document_type_distribution", {}),
            language_distribution=stats.get("language_distribution", {}),
            keyword_category_distribution=stats.get("keyword_category_distribution", {}),
            avg_keywords_per_doc=stats.get("avg_keywords_per_doc", 0.0)
        )

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )


@router.post("/keywords/top",
             response_model=List[TopKeywordResult],
             summary="상위 키워드 조회",
             description="빈도와 중요도를 기준으로 상위 키워드를 조회합니다.")
async def get_top_keywords(
    request: TopKeywordsRequest,
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """상위 키워드 조회"""
    try:
        logger.info(f"Top keywords request: limit={request.limit}, category={request.category}")

        results = storage.get_top_keywords(
            limit=request.limit,
            category=request.category.value if request.category else None,
            domain=request.domain.value if request.domain else None
        )

        # 최소 문서 수 필터링 및 응답 모델 변환
        return [
            TopKeywordResult(
                keyword=hit["keyword"],
                total_frequency=hit["total_frequency"],
                avg_score=hit["avg_score"],
                document_count=hit["document_count"],
                categories=hit["categories"],
                domains=hit["domains"],
                sample_documents=hit["sample_documents"]
            )
            for hit in results
            if hit["document_count"] >= request.min_doc_count
        ]

    except Exception as e:
        logger.error(f"Top keywords query failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Top keywords query failed: {str(e)}"
        )


@router.get("/domains",
            response_model=List[str],
            summary="도메인 목록",
            description="시스템에 등록된 모든 도메인 목록을 조회합니다.")
async def get_domains(
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """도메인 목록 조회"""
    try:
        stats = storage.get_ontology_statistics()
        domains = list(stats.get("domain_distribution", {}).keys())
        return sorted(domains)

    except Exception as e:
        logger.error(f"Failed to get domains: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get domains: {str(e)}"
        )


# ────────────────────── 배치 처리 ──────────────────────

@router.post("/extract/batch",
             response_model=BatchExtractionResult,
             summary="배치 온톨로지 추출",
             description="여러 문서에 대해 배치로 온톨로지를 추출합니다.")
async def batch_extract_ontology(
    request: BatchExtractionRequest,
    background_tasks: BackgroundTasks,
    storage: OntologyStorage = Depends(get_ontology_storage),
    qdrant=Depends(qdrant_dep)
):
    """배치 온톨로지 추출"""
    try:
        logger.info(f"Batch extraction requested for {len(request.doc_ids)} documents")

        start_time = time.time()
        successful = 0
        failed = 0
        skipped = 0
        failed_doc_ids = []

        for doc_id in request.doc_ids:
            try:
                # 기존 온톨로지 확인
                if not request.force_reextract:
                    existing = storage.get_document_ontology(doc_id)
                    if existing:
                        skipped += 1
                        continue

                # 문서 청크 조회
                chunks_data, _ = qdrant.scroll(
                    collection_name="chunks",
                    scroll_filter={
                        "must": [
                            {"key": "doc_id", "match": {"value": doc_id}}
                        ]
                    },
                    limit=10000,
                    with_payload=True,
                    with_vectors=False
                )

                if not chunks_data:
                    failed += 1
                    failed_doc_ids.append(doc_id)
                    continue

                # 청크 변환
                chunks = []
                source = "unknown"
                for chunk_point in chunks_data:
                    payload = chunk_point.payload
                    chunks.append({
                        'content': payload.get('content', ''),
                        'meta': payload
                    })
                    if source == "unknown" and payload.get('source'):
                        source = payload.get('source')

                # 온톨로지 추출
                extractor = get_ontology_extractor()
                result = extract_ontology_from_chunks(chunks, doc_id, source)

                # 저장
                if storage.store_ontology(result):
                    successful += 1
                else:
                    failed += 1
                    failed_doc_ids.append(doc_id)

            except Exception as e:
                logger.error(f"Failed to extract ontology for {doc_id}: {e}")
                failed += 1
                failed_doc_ids.append(doc_id)

        processing_time = time.time() - start_time

        logger.info(f"Batch extraction completed: {successful} successful, {failed} failed, {skipped} skipped")

        return BatchExtractionResult(
            total_requested=len(request.doc_ids),
            successful=successful,
            failed=failed,
            skipped=skipped,
            processing_time=processing_time,
            failed_doc_ids=failed_doc_ids
        )

    except Exception as e:
        logger.error(f"Batch extraction failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch extraction failed: {str(e)}"
        )


# ────────────────────── 시스템 관리 (먼저 정의) ──────────────────────

@router.get("/health",
            response_model=SystemHealthModel,
            summary="시스템 상태 확인",
            description="온톨로지 시스템의 상태를 확인합니다.")
async def get_system_health(
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """시스템 상태 확인"""
    try:
        # 컬렉션 상태 확인
        collections_status = {}
        try:
            collections = storage.client.get_collections().collections
            collection_names = [col.name for col in collections]
            collections_status["ontology"] = "ontology" in collection_names
            collections_status["keywords"] = "keywords" in collection_names
        except:
            collections_status = {"ontology": False, "keywords": False}

        # 임베딩 모델 상태 확인
        embedding_status = True
        try:
            from backend.embedding.embedder import get_model
            get_model()
        except:
            embedding_status = False

        # KeyBERT 상태 확인
        keybert_status = True
        try:
            import keybert
        except ImportError:
            keybert_status = False

        # spaCy 상태 확인
        spacy_status = True
        try:
            import spacy
        except ImportError:
            spacy_status = False

        # 통계 조회
        stats = storage.get_ontology_statistics()

        return SystemHealthModel(
            ontology_collections_status=collections_status,
            embedding_model_status=embedding_status,
            keybert_available=keybert_status,
            spacy_available=spacy_status,
            total_documents=stats.get("total_documents", 0),
            total_keywords=stats.get("total_keywords", 0),
            last_extraction=None  # TODO: 마지막 추출 시간 추적
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.delete("/clear",
               response_model=SuccessResponse,
               summary="모든 온톨로지 데이터 삭제",
               description="⚠️ 주의: 모든 온톨로지 데이터를 삭제합니다.")
async def clear_all_ontology(
    confirm: bool = Query(..., description="삭제 확인 (true 필수)"),
    storage: OntologyStorage = Depends(get_ontology_storage)
):
    """모든 온톨로지 데이터 삭제"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required: set confirm=true to proceed"
        )

    try:
        success = storage.clear_all_ontology()
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to clear ontology data"
            )

        logger.warning("All ontology data cleared!")
        return SuccessResponse(message="All ontology data cleared successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear ontology data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear ontology data: {str(e)}"
        )


# ────────────────────── 유틸리티 함수 ──────────────────────

def _convert_storage_result_to_model(storage_result: Dict[str, Any], doc_id: str) -> OntologyResultModel:
    """저장소 결과를 API 모델로 변환"""
    from ...ontology.models import (
        KeywordInfoModel, DocumentMetadataModel, ContextInfoModel,
        TextStatisticsModel, StructureInfoModel, ProcessingStatsModel,
        EntityInfoModel, SemanticClusterModel
    )

    # 키워드 변환 (저장소에서는 요약된 형태로만 제공)
    keywords = []
    for keyword_term in storage_result.get("top_keywords", []):
        keywords.append(KeywordInfoModel(
            term=keyword_term,
            score=0.8,  # 기본값
            frequency=1,  # 기본값
            category="general",  # 기본값
            positions=[]
        ))

    # 개체명 변환
    entities = []
    for entity_text in storage_result.get("entities", []):
        entities.append(EntityInfoModel(
            text=entity_text,
            label="UNKNOWN",  # 기본값
            start=0,  # 기본값
            end=len(entity_text),  # 기본값
            confidence=1.0
        ))

    return OntologyResultModel(
        doc_id=doc_id,
        source=storage_result.get("source", "unknown"),
        keywords=keywords,
        metadata=DocumentMetadataModel(
            language=storage_result.get("language", "unknown"),
            document_type=storage_result.get("document_type", "general"),
            estimated_domain=storage_result.get("estimated_domain", "general"),
            key_entities=entities,
            text_statistics=TextStatisticsModel(
                **storage_result.get("text_statistics", {
                    "total_length": 0, "lines": 0, "words": 0, "sentences": 0,
                    "korean_chars": 0, "english_chars": 0, "numbers": 0,
                    "avg_word_length": 0.0, "avg_sentence_length": 0.0
                })
            ),
            structure_info=StructureInfoModel(
                **storage_result.get("structure_info", {
                    "total_lines": 0, "empty_lines": 0, "potential_headers": 0,
                    "list_items": 0, "has_numbered_sections": False, "has_bullet_points": False
                })
            )
        ),
        context=ContextInfoModel(
            main_topics=storage_result.get("main_topics", []),
            semantic_clusters=[],  # 저장소에서 제공하지 않음
            related_concepts=storage_result.get("related_concepts", []),
            domain_indicators=storage_result.get("domain_indicators", [])
        ),
        extracted_at=datetime.fromisoformat(storage_result.get("extracted_at", datetime.now().isoformat())),
        processing_stats=ProcessingStatsModel(
            **storage_result.get("processing_stats", {
                "total_time": 0.0, "keywords_time": 0.0, "metadata_time": 0.0,
                "context_time": 0.0, "keywords_count": 0, "entities_count": 0, "topics_count": 0
            })
        )
    )