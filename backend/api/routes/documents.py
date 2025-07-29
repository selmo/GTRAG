"""
문서 업로드 / 조회 라우터 - Ontology 추출 통합 버전
"""
from qdrant_client.http import models as rest
from backend.api.deps import qdrant_dep
from pathlib import Path
import tempfile, os, re, uuid
from datetime import datetime, timezone
from backend.ingestion.parser import parse_pdf, parse_file_by_extension
from backend.embedding.embedder import embed_texts

from fastapi import (
    APIRouter, Depends, File, HTTPException,
    UploadFile, Query, Response, Path as ApiPath, BackgroundTasks
)

# ─────────────────── Ontology 통합 Import ───────────────────
try:
    from backend.ontology.extractor import extract_ontology_from_chunks
    from backend.ontology.storage import get_ontology_storage
    ONTOLOGY_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Ontology modules not available: {e}")
    ONTOLOGY_AVAILABLE = False

router = APIRouter()
COLLECTION = "chunks"


# ─────────────────── 백그라운드 온톨로지 추출 ───────────────────

async def extract_ontology_background(doc_id: str, chunks_data: list, source: str):
    """백그라운드에서 온톨로지 추출"""
    if not ONTOLOGY_AVAILABLE:
        return

    try:
        from backend.core.logging import get_logger
        logger = get_logger("ontology_background")
        import json
        source = json.dumps(source, ensure_ascii=False)

        logger.info(f"Starting background ontology extraction for: {source}")

        # 청크 데이터 변환
        chunks = []
        for chunk_data in chunks_data:
            chunks.append({
                'content': chunk_data.get('content', ''),
                'meta': chunk_data
            })

        # 온톨로지 추출
        result = extract_ontology_from_chunks(chunks, doc_id, source)

        # 저장
        storage = get_ontology_storage()
        success = storage.store_ontology(result)

        if success:
            logger.info(f"Background ontology extraction completed for: {source}")
            logger.info(f"Extracted: {len(result.keywords)} keywords, "
                       f"{len(result.metadata.key_entities)} entities, "
                       f"{len(result.context.main_topics)} topics")
        else:
            logger.error(f"Failed to store ontology for: {source}")

    except Exception as e:
        from backend.core.logging import get_logger
        logger = get_logger("ontology_background")
        logger.error(f"Background ontology extraction failed for {source}: {e}", exc_info=True)


@router.post("/v1/documents", summary="단일 문서 업로드 (Ontology 통합)")
async def upload_document(
        file: UploadFile = File(...),
        background_tasks: BackgroundTasks = BackgroundTasks(),
        enable_ontology: bool = Query(default=True, description="온톨로지 추출 활성화"),
        qdrant=Depends(qdrant_dep)
):
    import time
    from backend.core.logging import get_logger, log_document_processing
    from backend.core.request_context import get_request_id

    # 로거 설정
    logger = get_logger("documents")
    start_time = time.time()

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename supplied")

    binary: bytes = await file.read()
    original_name = file.filename
    file_size = len(binary)
    doc_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    # 문서 업로드 시작 로깅 (온톨로지 상태 포함)
    request_id = get_request_id()
    logger.info(
        f"Document upload started: {original_name}",
        extra={
            "event_type": "document_upload_start",
            "request_id": request_id,
            "document_filename": original_name,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "doc_id": doc_id,
            "file_extension": Path(original_name).suffix.lower(),
            "content_type": file.content_type,
            "upload_timestamp": datetime.now().isoformat(),
            "ontology_enabled": enable_ontology and ONTOLOGY_AVAILABLE
        }
    )

    try:
        # ─────────── ① 파일 타입별 파싱 ───────────
        parsing_start = time.time()
        ext = Path(original_name).suffix.lower()

        logger.info(f"Starting file parsing for: {ext}", extra={
            "event_type": "file_parsing_start",
            "file_extension": ext,
            "parser_type": "pdf" if ext == ".pdf" else "generic"
        })

        if ext == ".pdf":
            chunks = parse_pdf(binary, lang_hint="ko")
        else:
            # 임시파일에 기록 후 확장자 기반 파싱
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(binary)
                tmp_path = tmp.name
            try:
                chunks = parse_file_by_extension(tmp_path, lang_hint="ko")
            finally:
                os.unlink(tmp_path)

        parsing_time = time.time() - parsing_start

        if not chunks:
            logger.error(f"No text extracted from file", extra={
                "event_type": "parsing_failed",
                "file_extension": ext,
                "parsing_time_seconds": round(parsing_time, 3)
            })
            raise HTTPException(status_code=400,
                                detail=f"Unable to extract text from {ext or 'file'}")

        # 파싱 완료 로깅
        chunk_stats = {
            "total_chunks": len(chunks),
            "avg_chunk_length": round(sum(len(c["content"]) for c in chunks) / len(chunks), 2) if chunks else 0,
            "total_text_length": sum(len(c["content"]) for c in chunks),
            "has_korean": any(re.search(r"[가-힣]", c["content"]) for c in chunks),
            "has_english": any(re.search(r"[a-zA-Z]", c["content"]) for c in chunks)
        }

        logger.info("File parsing completed", extra={
            "event_type": "file_parsing_completed",
            "parsing_time_seconds": round(parsing_time, 3),
            **chunk_stats
        })

        # ─────────── ② 임베딩 + Qdrant 업서트 ───────────
        embedding_start = time.time()

        logger.info("Starting text embedding", extra={
            "event_type": "embedding_start",
            "chunks_to_embed": len(chunks)
        })

        try:
            vectors = embed_texts([c["content"] for c in chunks], prefix="passage")
            embedding_time = time.time() - embedding_start

            logger.info("Text embedding completed", extra={
                "event_type": "embedding_completed",
                "embedding_time_seconds": round(embedding_time, 3),
                "vectors_generated": len(vectors)
            })

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}", extra={
                "event_type": "embedding_error",
                "error": str(e),
                "chunks_count": len(chunks)
            })
            raise

        # Qdrant 포인트 생성 및 업서트
        qdrant_start = time.time()

        logger.info("Creating Qdrant points", extra={
            "event_type": "qdrant_upsert_start",
            "points_count": len(chunks)
        })

        points = [
            rest.PointStruct(
                id=str(uuid.uuid4()),
                vector=v.tolist() if hasattr(v, "tolist") else v,
                payload={
                    **c["meta"],
                    "content": c["content"],
                    # 추가 메타데이터
                    "doc_id": doc_id,
                    "source": original_name,
                    "file_size": file_size,
                    "uploaded_at": now_iso,
                    "created_at": now_iso,
                    "modified_at": now_iso,
                    "has_korean": bool(re.search(r"[가-힣]", c["content"])),
                    "has_english": bool(re.search(r"[a-zA-Z]", c["content"])),
                    "chunk_index": i,
                    "chunk_length": len(c["content"])
                },
            )
            for i, (c, v) in enumerate(zip(chunks, vectors))
        ]

        try:
            qdrant.upsert(collection_name=COLLECTION, points=points)
            qdrant_time = time.time() - qdrant_start

            logger.info("Qdrant upsert completed", extra={
                "event_type": "qdrant_upsert_completed",
                "qdrant_time_seconds": round(qdrant_time, 3),
                "collection": COLLECTION,
                "points_inserted": len(points)
            })

        except Exception as e:
            logger.error(f"Qdrant upsert failed: {e}", extra={
                "event_type": "qdrant_error",
                "collection": COLLECTION,
                "points_count": len(points),
                "error": str(e)
            })
            raise

        # ─────────── ③ 백그라운드 온톨로지 추출 예약 ───────────
        ontology_scheduled = False
        if enable_ontology and ONTOLOGY_AVAILABLE:
            try:
                # 청크 데이터를 백그라운드 작업용으로 준비
                chunks_for_ontology = []
                for i, (chunk, point) in enumerate(zip(chunks, points)):
                    chunks_for_ontology.append({
                        "content": chunk["content"],
                        "meta": point.payload,
                        "chunk_index": i
                    })

                # 백그라운드 작업 예약
                background_tasks.add_task(
                    extract_ontology_background,
                    doc_id=doc_id,
                    chunks_data=chunks_for_ontology,
                    source=original_name
                )

                ontology_scheduled = True
                logger.info("Ontology extraction scheduled for background processing", extra={
                    "event_type": "ontology_scheduled",
                    "doc_id": doc_id,
                    "chunks_count": len(chunks_for_ontology)
                })

            except Exception as e:
                logger.warning(f"Failed to schedule ontology extraction: {e}", extra={
                    "event_type": "ontology_schedule_failed",
                    "error": str(e)
                })

        # 전체 처리 시간 계산 및 완료 로깅
        total_time = time.time() - start_time

        # 문서 처리 완료 로깅 (온톨로지 상태 포함)
        log_document_processing(
            logger,
            filename=original_name,
            file_size=file_size,
            chunks_created=len(points),
            processing_time=total_time,
            doc_id=doc_id,
            metadata={
                "file_extension": ext,
                "text_stats": chunk_stats,
                "performance_breakdown": {
                    "parsing_time": round(parsing_time, 3),
                    "embedding_time": round(embedding_time, 3),
                    "qdrant_time": round(qdrant_time, 3),
                    "other_time": round(total_time - parsing_time - embedding_time - qdrant_time, 3)
                },
                "collection": COLLECTION,
                "ontology_scheduled": ontology_scheduled,
                "ontology_available": ONTOLOGY_AVAILABLE
            }
        )

        # ─────────── ④ 응답 생성 (온톨로지 정보 포함) ───────────
        response_data = {
            "uploaded": len(points),
            "collection": COLLECTION,
            "doc_id": doc_id,
            "name": original_name,
            "performance": {
                "total_time_seconds": round(total_time, 3),
                "parsing_time": round(parsing_time, 3),
                "embedding_time": round(embedding_time, 3),
                "qdrant_time": round(qdrant_time, 3)
            },
            "statistics": {
                "file_size_bytes": file_size,
                "chunks_created": len(points),
                "total_text_length": chunk_stats["total_text_length"],
                "avg_chunk_length": chunk_stats["avg_chunk_length"]
            }
        }

        # 온톨로지 관련 정보 추가
        if ONTOLOGY_AVAILABLE:
            response_data["ontology"] = {
                "enabled": enable_ontology,
                "scheduled": ontology_scheduled,
                "status": "processing" if ontology_scheduled else "disabled",
                "estimated_completion": "1-5 minutes" if ontology_scheduled else None
            }
        else:
            response_data["ontology"] = {
                "enabled": False,
                "available": False,
                "status": "unavailable",
                "reason": "Ontology modules not installed"
            }

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"Document upload failed: {e}", extra={
            "event_type": "document_upload_error",
            "document_filename": original_name,
            "doc_id": doc_id,
            "total_time_seconds": round(total_time, 3),
            "error": str(e),
            "error_type": type(e).__name__,
            "failure_timestamp": datetime.now().isoformat()
        }, exc_info=True)
        raise HTTPException(500, f"문서 업로드 실패: {str(e)}")


@router.get("/v1/documents", summary="문서 목록 / 통계 조회 (Ontology 정보 포함)")
async def list_documents(
    stats: bool = Query(False, description="true → 통계만 반환"),
    include_ontology: bool = Query(default=True, description="온톨로지 상태 포함"),
    qdrant=Depends(qdrant_dep),
):
    """
    Qdrant `chunks` 컬렉션을 스캔해
    • stats=False  → 각 문서별 메타데이터 + 청크 수 + 온톨로지 상태
    • stats=True   → 문서·청크·온톨로지 집계치만
    을 반환한다.
    """
    # 1️⃣ 모든 포인트 스크롤
    points, _ = qdrant.scroll(
        collection_name=COLLECTION,
        with_payload=True,
        with_vectors=False,
        limit=10000,       # 큰 값 → 한 번에
    )

    # 2️⃣ 문서별 집계
    from collections import defaultdict
    docs = defaultdict(lambda: {"chunks": 0})
    for p, payload in zip(points, points):
        doc_id = payload.payload.get("doc_id") or payload.payload.get("source") or "unknown"
        d = docs[doc_id]
        d["chunks"] += 1
        # 최초 한 번만 기본 메타 채움
        if "name" not in d:
            display_name = payload.payload.get("source") or doc_id
            d.update(
                name=display_name,
                uploaded_at=payload.payload.get("uploaded_at"),
                created_at=payload.payload.get("created_at"),
                modified_at=payload.payload.get("modified_at"),
                size=payload.payload.get("file_size") or payload.payload.get("size"),
                doc_id=doc_id if doc_id != "unknown" else payload.payload.get("doc_id")
            )

    # 3️⃣ 온톨로지 상태 조회 (옵션)
    ontology_status = {}
    if include_ontology and ONTOLOGY_AVAILABLE:
        try:
            storage = get_ontology_storage()
            ontology_stats = storage.get_ontology_statistics()

            # 각 문서별 온톨로지 존재 여부 확인
            for doc_id in docs.keys():
                if doc_id != "unknown":
                    ontology_data = storage.get_document_ontology(doc_id)
                    ontology_status[doc_id] = {
                        "has_ontology": ontology_data is not None,
                        "extracted_at": ontology_data.get("extracted_at") if ontology_data else None,
                        "keyword_count": ontology_data.get("keyword_count", 0) if ontology_data else 0,
                        "entity_count": ontology_data.get("entity_count", 0) if ontology_data else 0
                    }
        except Exception as e:
            from backend.core.logging import get_logger
            logger = get_logger("documents")
            logger.warning(f"Failed to get ontology status: {e}")

    if stats:
        # 통계 응답 (온톨로지 정보 포함)
        response = {
            "total_documents": len(docs),
            "total_chunks": sum(d["chunks"] for d in docs.values()),
        }

        if include_ontology and ONTOLOGY_AVAILABLE:
            ontology_count = sum(1 for status in ontology_status.values() if status.get("has_ontology", False))
            response["ontology"] = {
                "total_with_ontology": ontology_count,
                "total_without_ontology": len(docs) - ontology_count,
                "ontology_coverage": round(ontology_count / len(docs) * 100, 1) if docs else 0,
                "available": True
            }
        else:
            response["ontology"] = {
                "available": ONTOLOGY_AVAILABLE,
                "reason": "Modules not available" if not ONTOLOGY_AVAILABLE else "Disabled"
            }

        return response

    # 문서 목록 응답 (온톨로지 정보 포함)
    doc_list = []
    for doc_data in docs.values():
        doc_entry = dict(doc_data)

        # 온톨로지 상태 추가
        if include_ontology and doc_data.get("doc_id") in ontology_status:
            doc_entry["ontology"] = ontology_status[doc_data["doc_id"]]
        elif include_ontology:
            doc_entry["ontology"] = {
                "has_ontology": False,
                "available": ONTOLOGY_AVAILABLE
            }

        doc_list.append(doc_entry)

    return doc_list


@router.delete(
    "/v1/documents/{doc_key}",
    summary="문서 및 해당 청크 삭제 (Ontology 포함)",
    status_code=204,
)
async def delete_document(
    doc_key: str = ApiPath(..., description="doc_id(또는 uuid_prefix)+파일명"),
    delete_ontology: bool = Query(default=True, description="온톨로지 데이터도 함께 삭제"),
    qdrant=Depends(qdrant_dep),
):
    """
    * doc_key 에 UUID 가 포함돼 있으면 **doc_id** 로 간주
    * 그렇지 않으면 **source(원본 파일명)** 으로 매칭
    삭제된 청크 수가 0 이면 404 반환.
    온톨로지 데이터도 함께 삭제 가능.
    """
    from backend.core.logging import get_logger
    logger = get_logger("documents")

    # ① doc_id 추출 & 조건 구성 -----------------------------------------
    m = re.match(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", doc_key, re.I)
    uuid_str = m.group(1) if m else None

    conditions: list[rest.FieldCondition] = []
    if uuid_str:
        try:
            uuid.UUID(uuid_str)
            conditions.append(rest.FieldCondition(key="doc_id",
                                                  match=rest.MatchValue(value=uuid_str)))
        except ValueError:
            pass

    # source(파일명) fallback
    conditions.append(rest.FieldCondition(key="source",
                                          match=rest.MatchValue(value=doc_key)))

    flt = rest.Filter(should=conditions)

    # ② 온톨로지 데이터 삭제 (먼저 실행) ------------------------------------
    ontology_deleted = False
    if delete_ontology and ONTOLOGY_AVAILABLE:
        try:
            storage = get_ontology_storage()

            # doc_id 확인을 위해 먼저 청크 조회
            existing_chunks, _ = qdrant.scroll(
                collection_name=COLLECTION,
                scroll_filter=flt,
                limit=1,
                with_payload=True,
                with_vectors=False
            )

            if existing_chunks:
                actual_doc_id = existing_chunks[0].payload.get("doc_id")
                if actual_doc_id:
                    ontology_deleted = storage.delete_document_ontology(actual_doc_id)
                    if ontology_deleted:
                        logger.info(f"Deleted ontology data for document: {actual_doc_id}")

        except Exception as e:
            logger.warning(f"Failed to delete ontology data: {e}")

    # ③ Qdrant 청크 삭제 ------------------------------------------------------
    del_res = qdrant.delete(
        collection_name=COLLECTION,
        points_selector=rest.FilterSelector(filter=flt),  # ✅ 핵심 수정
        wait=True,
    )

    if del_res.status != rest.UpdateStatus.COMPLETED:
        raise HTTPException(status_code=500, detail="Deletion failed")

    # ④ 후행 스캔으로 실제 삭제 여부 재검증 ------------------------------
    remained, _ = qdrant.scroll(
        collection_name=COLLECTION,
        scroll_filter=flt,                # ✅ 최신 시그니처에 맞춤
        with_payload=False,
        with_vectors=False,
        limit=1,
    )
    if remained:
        raise HTTPException(status_code=404, detail="Document not found")

    # ⑤ 삭제 완료 로깅
    logger.info(f"Document deleted: {doc_key}", extra={
        "event_type": "document_deleted",
        "doc_key": doc_key,
        "ontology_deleted": ontology_deleted,
        "ontology_enabled": delete_ontology and ONTOLOGY_AVAILABLE
    })

    return Response(status_code=204)


# ─────────────────── 온톨로지 상태 조회 엔드포인트 ───────────────────

@router.get("/v1/documents/{doc_id}/ontology/status",
            summary="문서 온톨로지 상태 조회",
            description="특정 문서의 온톨로지 추출 상태를 확인합니다.")
async def get_document_ontology_status(
    doc_id: str = ApiPath(..., description="문서 ID")
):
    """문서의 온톨로지 상태 조회"""
    if not ONTOLOGY_AVAILABLE:
        return {
            "available": False,
            "reason": "Ontology modules not installed"
        }

    try:
        storage = get_ontology_storage()
        ontology_data = storage.get_document_ontology(doc_id)

        if ontology_data:
            return {
                "available": True,
                "has_ontology": True,
                "status": "completed",
                "extracted_at": ontology_data.get("extracted_at"),
                "keyword_count": ontology_data.get("keyword_count", 0),
                "entity_count": ontology_data.get("entity_count", 0),
                "main_topics": ontology_data.get("main_topics", []),
                "estimated_domain": ontology_data.get("estimated_domain"),
                "document_type": ontology_data.get("document_type")
            }
        else:
            return {
                "available": True,
                "has_ontology": False,
                "status": "not_extracted",
                "message": "Ontology has not been extracted for this document"
            }

    except Exception as e:
        from backend.core.logging import get_logger
        logger = get_logger("documents")
        logger.error(f"Failed to get ontology status for {doc_id}: {e}")

        return {
            "available": True,
            "has_ontology": False,
            "status": "error",
            "error": str(e)
        }


@router.post("/v1/documents/{doc_id}/ontology/extract",
             summary="문서 온톨로지 재추출",
             description="특정 문서의 온톨로지를 강제로 재추출합니다.")
async def reextract_document_ontology(
    doc_id: str = ApiPath(..., description="문서 ID"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    qdrant=Depends(qdrant_dep)
):
    """문서 온톨로지 재추출"""
    if not ONTOLOGY_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Ontology extraction not available"
        )

    try:
        from backend.core.logging import get_logger
        logger = get_logger("documents")

        # 문서 청크 조회
        chunks_data, _ = qdrant.scroll(
            collection_name=COLLECTION,
            scroll_filter=rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="doc_id",
                        match=rest.MatchValue(value=doc_id)
                    )
                ]
            ),
            limit=10000,
            with_payload=True,
            with_vectors=False
        )

        if not chunks_data:
            raise HTTPException(
                status_code=404,
                detail=f"Document not found: {doc_id}"
            )

        # 청크 데이터 준비
        chunks_for_ontology = []
        source = "unknown"
        for chunk_point in chunks_data:
            payload = chunk_point.payload
            chunks_for_ontology.append({
                "content": payload.get("content", ""),
                "meta": payload
            })
            if source == "unknown" and payload.get("source"):
                source = payload.get("source")

        # 백그라운드 재추출 예약
        background_tasks.add_task(
            extract_ontology_background,
            doc_id=doc_id,
            chunks_data=chunks_for_ontology,
            source=source
        )

        logger.info(f"Ontology re-extraction scheduled for: {doc_id}")

        return {
            "success": True,
            "message": "Ontology re-extraction scheduled",
            "doc_id": doc_id,
            "source": source,
            "chunks_count": len(chunks_for_ontology),
            "estimated_completion": "1-5 minutes"
        }

    except HTTPException:
        raise
    except Exception as e:
        from backend.core.logging import get_logger
        logger = get_logger("documents")
        logger.error(f"Failed to schedule ontology re-extraction for {doc_id}: {e}")

        raise HTTPException(
            status_code=500,
            detail=f"Failed to schedule ontology re-extraction: {str(e)}"
        )