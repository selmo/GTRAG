from fastapi import APIRouter, UploadFile, File, Depends, Query
from ingestion.parser import parse_pdf
from ingestion.ocr import extract_text
from embedding.embedder import embed_texts
from retriever.retriever import search as vector_search
from uuid import uuid4
from .schemas import UploadResponse, SearchResponse, SearchHit
import qdrant_client

router = APIRouter()
qdrant = qdrant_client.QdrantClient(host="qdrant", port=6333)


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
