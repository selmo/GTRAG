"""
문서 업로드 / 조회 라우터
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
    UploadFile, Query, Response, Path as ApiPath
)

router = APIRouter()
COLLECTION = "chunks"


@router.post("/v1/documents", summary="단일 문서 업로드")
async def upload_document(
        file: UploadFile = File(...),
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

    # 문서 업로드 시작 로깅
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
            "upload_timestamp": datetime.now().isoformat()
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

        # 전체 처리 시간 계산 및 완료 로깅
        total_time = time.time() - start_time

        # 문서 처리 완료 로깅
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
                "collection": COLLECTION
            }
        )

        return {
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


@router.get("/v1/documents", summary="문서 목록 / 통계 조회")
async def list_documents(
    stats: bool = Query(False, description="true → 통계만 반환"),
    qdrant=Depends(qdrant_dep),
):
    """
    Qdrant `chunks` 컬렉션을 스캔해
    • stats=False  → 각 문서별 메타데이터 + 청크 수
    • stats=True   → 문서·청크 집계치만
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
            )

    if stats:
        return {
            "total_documents": len(docs),
            "total_chunks": sum(d["chunks"] for d in docs.values()),
        }

    return list(docs.values())


@router.delete(
    "/v1/documents/{doc_key}",
    summary="문서 및 해당 청크 삭제",
    status_code=204,
)
async def delete_document(
    doc_key: str = ApiPath(..., description="doc_id(또는 uuid_prefix)+파일명"),
    qdrant=Depends(qdrant_dep),
):
    """
    * doc_key 에 UUID 가 포함돼 있으면 **doc_id** 로 간주
    * 그렇지 않으면 **source(원본 파일명)** 으로 매칭
    삭제된 청크 수가 0 이면 404 반환.
    """
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

    # ② Qdrant 삭제 ------------------------------------------------------
    del_res = qdrant.delete(
        collection_name=COLLECTION,
        points_selector=rest.FilterSelector(filter=flt),  # ✅ 핵심 수정
        wait=True,
    )

    if del_res.status != rest.UpdateStatus.COMPLETED:
        raise HTTPException(status_code=500, detail="Deletion failed")

    # ③ 후행 스캔으로 실제 삭제 여부 재검증 ------------------------------
    remained, _ = qdrant.scroll(
        collection_name=COLLECTION,
        scroll_filter=flt,                # ✅ 최신 시그니처에 맞춤
        with_payload=False,
        with_vectors=False,
        limit=1,
    )
    if remained:
        raise HTTPException(status_code=404, detail="Document not found")

    return Response(status_code=204)