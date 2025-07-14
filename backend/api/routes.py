from typing import List
from fastapi import APIRouter, UploadFile, File, Query
from backend.ingestion.parser import parse_pdf
from backend.ingestion.ocr import extract_text
from backend.embedding.embedder import embed_texts
from backend.retriever.retriever import search as vector_search
from uuid import uuid4
from backend.api.schemas import UploadResponse, SearchResponse, SearchHit
import qdrant_client
from backend.api.main import get_qdrant_client   # ✅ main 에서 쓰는 함수 재사용


qdrant = get_qdrant_client()            # 하드코딩 삭제
router = APIRouter()


@router.get("/v1/documents", response_model=List[dict])
async def list_documents():
    """
    Qdrant payload에서 source(파일명)별 청크 수·업로드 시각·언어 비율 등을 모아 반환
    """
    docs = {}
    scroll_offset = None
    while True:
        points, scroll_offset = qdrant.scroll(
            collection_name="chunks",
            limit=256,
            offset=scroll_offset,
            with_payload=True,
            with_vectors=False
        )
        for p in points:
            src = p.payload.get("source", "unknown")
            docs.setdefault(src, {"name": src, "chunks": 0, "latest": None})
            docs[src]["chunks"] += 1
            ts = p.payload.get("upload_timestamp")
            if ts and (docs[src]["latest"] is None or ts > docs[src]["latest"]):
                docs[src]["latest"] = ts

            docs[src].setdefault("size_bytes", 0)
            docs[src]["size_bytes"] += p.payload.get("file_size", 0)

        if scroll_offset is None:
            break

    from datetime import datetime
    # ISO → yyyy-mm-dd HH:MM 로 보기 좋게 변환
    for d in docs.values():
        if d["latest"]:
            d["time"] = datetime.fromisoformat(d["latest"]).strftime("%Y-%m-%d %H:%M")

    for d in docs.values():
        d["time"] = (
            datetime.fromisoformat(d["latest"]).strftime("%Y-%m-%d %H:%M")
            if d["latest"] else None
        )

    for d in docs.values():
        if d["latest"]:
            d["time"] = datetime.fromisoformat(d["latest"]).strftime("%Y-%m-%d %H:%M")
        if d.get("size_bytes"):
            mb = d["size_bytes"] / 1024 / 1024
            d["size"] = f"{mb:.2f} MB"
        else:
            d["size"] = "-"

    return list(docs.values())


@router.post("/v1/documents", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    # ① 파일 저장 (메모리/디스크)
    tmp_path = f"/tmp/{uuid4()}_{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(await file.read())

    # ② 포맷 분기
    chunks = []
    if file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".tif")):
        # OCR → 단일 청크
        text = extract_text(tmp_path)
        chunks = [{
            "chunk_id": str(uuid4()),
            "content": text,
            "meta": {"source": "image"}
        }]
    else:
        # PDF / 이메일 등 → unstructured 파싱
        chunks = parse_pdf(tmp_path)

    # ③ 벡터 생성
    vectors = embed_texts([c["content"] for c in chunks])

    # ④ Qdrant upsert
    qdrant.upsert(
        collection_name="chunks",
        points=[
            qdrant_client.http.models.PointStruct(
                id=c["chunk_id"], vector=v, payload={**c["meta"], "content": c["content"]}
            ) for c, v in zip(chunks, vectors)
        ],
    )
    return UploadResponse(uploaded=len(chunks))


@router.get("/v1/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(3, ge=1, le=20),
    lang: str | None = Query(None, min_length=2, max_length=2),
):
    qvec = embed_texts([q])[0]
    hits = vector_search(qvec, top_k, lang)
    return SearchResponse(
        items=[
            SearchHit(
                chunk_id=h.id,
                content=h.payload.get("content", ""),
                score=h.score,
            )
            for h in hits
        ]
    )
