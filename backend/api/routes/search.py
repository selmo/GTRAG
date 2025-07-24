"""
검색 라우터 (vector / hybrid / rerank)
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import qdrant_dep
from backend.embedding.embedder import embed_texts
from backend.retriever import retriever

router = APIRouter()


@router.get("/v1/search", summary="문서 검색")
async def search_endpoint(
    q: str = Query(..., min_length=1),
    top_k: int = Query(3, ge=1, le=20),
    search_type: str = Query("hybrid", regex="^(vector|hybrid|rerank)$"),
    qdrant=Depends(qdrant_dep),
):
    query_text = q.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    qvec = embed_texts([query_text], prefix="query")[0]

    if search_type == "vector":
        hits = retriever.search(qvec, top_k=top_k, qdrant=qdrant)
    elif search_type == "rerank":
        hits = retriever.search_with_rerank(query_text, qvec, top_k=top_k, qdrant=qdrant)
    else:  # hybrid
        hits = retriever.hybrid_search(query_text, qvec, top_k=top_k, qdrant=qdrant)

    return [
        {
            "id": hit.id,
            "score": round(float(hit.score), 4),
            "content": hit.payload.get("content"),
            "metadata": {k: v for k, v in hit.payload.items() if k != "content"},
        }
        for hit in hits
    ]
