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
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename supplied")

    binary: bytes = await file.read()
    original_name = file.filename
    file_size = len(binary)
    doc_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    # ─────────── ① 파일 타입별 파싱 ───────────
    ext = Path(original_name).suffix.lower()
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

    if not chunks:
        raise HTTPException(status_code=400,
                            detail=f"Unable to extract text from {ext or 'file'}")

    # ─────────── ② 임베딩 + Qdrant 업서트 ───────────
    vectors = embed_texts([c["content"] for c in chunks], prefix="passage")

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
            },
        )
        for c, v in zip(chunks, vectors)
    ]

    qdrant.upsert(collection_name=COLLECTION, points=points)

    return {
        "uploaded": len(points),
        "collection": COLLECTION,
        "doc_id": doc_id,
        "name": original_name,
    }


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