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
    import time
    from backend.core.logging import get_logger, log_search_operation
    from backend.core.request_context import get_request_id

    # 로거 설정
    logger = get_logger("search")
    start_time = time.time()

    query_text = q.strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # 검색 요청 시작 로깅
    request_id = get_request_id()
    import re
    logger.info(
        f"Search request started",
        extra={
            "event_type": "search_request_start",
            "request_id": request_id,
            "query": query_text,
            "query_length": len(query_text),
            "search_type": search_type,
            "top_k": top_k,
            "has_korean": bool(re.search(r"[가-힣]", query_text)),
            "has_english": bool(re.search(r"[a-zA-Z]", query_text))
        }
    )

    try:
        # 임베딩 생성
        embedding_start = time.time()
        try:
            qvec = embed_texts([query_text], prefix="query")[0]
            embedding_time = time.time() - embedding_start

            logger.info("Query embedding generated", extra={
                "event_type": "search_embedding_completed",
                "embedding_time_seconds": round(embedding_time, 3),
                "vector_dimension": len(qvec) if hasattr(qvec, '__len__') else 'unknown'
            })

        except Exception as e:
            logger.error(f"Search embedding failed: {e}", extra={
                "event_type": "search_embedding_error",
                "error": str(e)
            })
            raise HTTPException(500, f"검색용 임베딩 생성 실패: {str(e)}")

        # 실제 검색 수행
        search_start = time.time()
        try:
            if search_type == "vector":
                hits = retriever.search(qvec, top_k=top_k, qdrant=qdrant)
            elif search_type == "rerank":
                hits = retriever.search_with_rerank(query_text, qvec, top_k=top_k, qdrant=qdrant)
            else:  # hybrid
                hits = retriever.hybrid_search(query_text, qvec, top_k=top_k, qdrant=qdrant)

            search_time = time.time() - search_start

        except Exception as e:
            logger.error(f"Search execution failed: {e}", extra={
                "event_type": "search_execution_error",
                "search_type": search_type,
                "error": str(e)
            })
            raise HTTPException(500, f"검색 실행 실패: {str(e)}")

        # 결과 처리 및 통계 생성
        processing_start = time.time()

        results = []
        score_stats = {
            "min_score": float('inf'),
            "max_score": float('-inf'),
            "avg_score": 0,
            "scores": []
        }

        content_stats = {
            "total_content_length": 0,
            "avg_content_length": 0,
            "sources": set()
        }

        for hit in hits:
            score = round(float(hit.score), 4)
            content = hit.payload.get("content", "")
            metadata = {k: v for k, v in hit.payload.items() if k != "content"}

            # 통계 수집
            score_stats["scores"].append(score)
            score_stats["min_score"] = min(score_stats["min_score"], score)
            score_stats["max_score"] = max(score_stats["max_score"], score)

            content_stats["total_content_length"] += len(content)
            content_stats["sources"].add(hit.payload.get("source", "Unknown"))

            results.append({
                "id": hit.id,
                "score": score,
                "content": content,
                "metadata": metadata,
            })

        # 통계 계산 완료
        if score_stats["scores"]:
            score_stats["avg_score"] = round(sum(score_stats["scores"]) / len(score_stats["scores"]), 4)
            content_stats["avg_content_length"] = round(content_stats["total_content_length"] / len(hits),
                                                        2) if hits else 0
        else:
            score_stats["min_score"] = 0
            score_stats["max_score"] = 0

        processing_time = time.time() - processing_start
        total_time = time.time() - start_time

        # 검색 완료 로깅
        log_search_operation(
            logger,
            query=query_text,
            search_type=search_type,
            results_count=len(hits),
            execution_time=total_time,
            top_k=top_k,
            metadata={
                "performance_breakdown": {
                    "embedding_time": round(embedding_time, 3),
                    "search_time": round(search_time, 3),
                    "processing_time": round(processing_time, 3)
                },
                "result_statistics": {
                    "score_stats": {
                        "min": score_stats["min_score"],
                        "max": score_stats["max_score"],
                        "avg": score_stats["avg_score"]
                    },
                    "content_stats": {
                        "total_sources": len(content_stats["sources"]),
                        "avg_content_length": content_stats["avg_content_length"],
                        "total_content_length": content_stats["total_content_length"]
                    }
                },
                "unique_sources": list(content_stats["sources"])[:5]  # 최대 5개 소스만 로깅
            }
        )

        return results

    except HTTPException:
        raise
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"Search request failed: {e}", extra={
            "event_type": "search_request_error",
            "query": query_text,
            "search_type": search_type,
            "top_k": top_k,
            "total_time_seconds": round(total_time, 3),
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)
        raise HTTPException(500, f"검색 요청 실패: {str(e)}")
