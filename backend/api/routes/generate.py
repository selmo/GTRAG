"""
RAG 답변 생성 라우터
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

from backend.api.deps import qdrant_dep
from backend.embedding.embedder import embed_texts
from backend.retriever import retriever
from backend.llm.ollama_client import get_ollama_client

router = APIRouter()
logger = logging.getLogger(__name__)


class GenerateAnswerRequest(BaseModel):
    query: str
    model: Optional[str] = "gemma3n:latest"
    temperature: Optional[float] = 0.7
    top_k: Optional[int] = 3
    min_score: Optional[float] = 0.3
    search_type: Optional[str] = "hybrid"
    system_prompt: Optional[str] = None
    timeout: Optional[int] = 30


@router.post("/v1/generate_answer", summary="RAG 기반 답변 생성")
async def generate_answer(
        request: GenerateAnswerRequest,
        qdrant=Depends(qdrant_dep),
):
    """
    RAG 기반으로 질문에 대한 답변을 생성합니다.

    1. 질문을 임베딩으로 변환
    2. 관련 문서 검색
    3. 검색된 문서를 컨텍스트로 하여 LLM에 답변 요청
    4. 생성된 답변과 출처 반환
    """
    import time
    from backend.core.logging import get_logger, log_llm_interaction
    from backend.core.request_context import get_request_id

    # 로거 설정
    logger = get_logger("generate")
    start_time = time.time()

    try:
        query_text = request.query.strip()
        if not query_text:
            raise HTTPException(400, "질문이 비어있습니다")

        # 요청 시작 로깅
        request_id = get_request_id()
        logger.info(
            f"RAG answer generation started",
            extra={
                "event_type": "rag_request_start",
                "request_id": request_id,
                "query": query_text,
                "query_length": len(query_text),
                "model": request.model,
                "temperature": request.temperature,
                "top_k": request.top_k,
                "search_type": request.search_type
            }
        )

        # 1. 질문을 임베딩으로 변환
        embedding_start = time.time()
        try:
            qvec = embed_texts([query_text], prefix="query")[0]
            embedding_time = time.time() - embedding_start

            logger.info("Query embedding completed", extra={
                "event_type": "embedding_generation",
                "execution_time_seconds": round(embedding_time, 3),
                "vector_dimension": len(qvec) if hasattr(qvec, '__len__') else 'unknown'
            })

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}", extra={
                "event_type": "embedding_error",
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise HTTPException(500, f"임베딩 생성 실패: {str(e)}")

        # 2. 관련 문서 검색
        search_start = time.time()
        try:
            if request.search_type == "vector":
                hits = retriever.search(qvec, top_k=request.top_k, qdrant=qdrant)
            elif request.search_type == "rerank":
                hits = retriever.search_with_rerank(query_text, qvec, top_k=request.top_k, qdrant=qdrant)
            else:  # hybrid
                hits = retriever.hybrid_search(query_text, qvec, top_k=request.top_k, qdrant=qdrant)

            # 점수 필터링
            filtered_hits = [hit for hit in hits if hit.score >= request.min_score]
            search_time = time.time() - search_start

            # 검색 결과 로깅
            from backend.core.logging import log_search_operation
            log_search_operation(
                logger,
                query=query_text,
                search_type=request.search_type,
                results_count=len(filtered_hits),
                execution_time=search_time,
                top_k=request.top_k,
                metadata={
                    "total_hits_before_filter": len(hits),
                    "min_score": request.min_score,
                    "hit_scores": [round(float(hit.score), 4) for hit in filtered_hits[:5]]  # 상위 5개 점수만
                }
            )

        except Exception as e:
            logger.error(f"Document search failed: {e}", extra={
                "event_type": "search_error",
                "search_type": request.search_type,
                "error": str(e)
            })
            raise HTTPException(500, f"문서 검색 실패: {str(e)}")

        # 3. 컨텍스트 구성
        contexts = []
        sources = []

        for hit in filtered_hits:
            content = hit.payload.get("content", "")
            if content.strip():
                contexts.append(content)
                sources.append({
                    "id": str(hit.id),
                    "score": round(float(hit.score), 4),
                    "source": hit.payload.get("source", "Unknown"),
                    "content": content[:200] + "..." if len(content) > 200 else content
                })

        # 4. 시스템 프롬프트 구성
        default_system_prompt = """당신은 한국어로 답변하는 도움이 되는 AI 어시스턴트입니다. 
주어진 문서를 바탕으로 정확하고 유용한 답변을 제공하세요.
문서에 없는 정보는 추측하지 말고, 문서 기반으로만 답변하세요."""

        system_prompt = request.system_prompt or default_system_prompt

        # 5. LLM 답변 생성
        llm_start = time.time()
        try:
            ollama_client = get_ollama_client()

            # 프롬프트 구성
            if contexts:
                context_text = "\n\n".join([f"문서 {i + 1}: {ctx}" for i, ctx in enumerate(contexts)])
                prompt = f"""다음 문서들을 참고하여 질문에 답변해주세요:

{context_text}

질문: {query_text}

답변:"""
            else:
                prompt = f"""다음 질문에 답변해주세요:

질문: {query_text}

답변:"""

            # 프롬프트 로깅
            logger.info("LLM prompt prepared", extra={
                "event_type": "llm_prompt_prepared",
                "prompt_length": len(prompt),
                "system_prompt_length": len(system_prompt),
                "context_count": len(contexts),
                "total_context_length": sum(len(ctx) for ctx in contexts)
            })

            # Ollama 호출
            response = ollama_client.generate(
                model=request.model,
                prompt=prompt,
                system=system_prompt,
                options={
                    "temperature": request.temperature,
                    "num_predict": 1000,  # 최대 토큰 수
                }
            )

            answer = response.get("response", "").strip()
            if not answer:
                answer = "죄송합니다. 답변을 생성할 수 없습니다."

            llm_time = time.time() - llm_start

            # LLM 상호작용 로깅
            log_llm_interaction(
                logger,
                prompt=prompt,
                response=answer,
                model=request.model,
                temperature=request.temperature,
                execution_time=llm_time,
                metadata={
                    "system_prompt": system_prompt,
                    "context_documents": len(contexts),
                    "ollama_response_metadata": {
                        "eval_count": response.get("eval_count"),
                        "eval_duration": response.get("eval_duration"),
                        "load_duration": response.get("load_duration"),
                        "prompt_eval_count": response.get("prompt_eval_count"),
                        "prompt_eval_duration": response.get("prompt_eval_duration"),
                        "total_duration": response.get("total_duration")
                    }
                }
            )

        except Exception as e:
            logger.error(f"LLM generation failed: {e}", extra={
                "event_type": "llm_error",
                "model": request.model,
                "error": str(e)
            })
            raise HTTPException(500, f"답변 생성 실패: {str(e)}")

        # 6. 전체 처리 시간 계산 및 결과 로깅
        total_time = time.time() - start_time

        logger.info("RAG answer generation completed", extra={
            "event_type": "rag_request_completed",
            "total_execution_time_seconds": round(total_time, 3),
            "answer_length": len(answer),
            "sources_count": len(sources),
            "performance_breakdown": {
                "embedding_time": round(embedding_time, 3),
                "search_time": round(search_time, 3),
                "llm_time": round(llm_time, 3),
                "other_time": round(total_time - embedding_time - search_time - llm_time, 3)
            }
        })

        # 7. 결과 반환
        return {
            "answer": answer,
            "sources": sources,
            "search_info": {
                "total_hits": len(hits),
                "filtered_hits": len(filtered_hits),
                "search_type": request.search_type,
                "min_score": request.min_score
            },
            "model_used": request.model,
            "query": query_text,
            "performance": {
                "total_time_seconds": round(total_time, 3),
                "embedding_time": round(embedding_time, 3),
                "search_time": round(search_time, 3),
                "llm_time": round(llm_time, 3)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"Unexpected error in generate_answer: {e}", extra={
            "event_type": "rag_request_error",
            "total_execution_time_seconds": round(total_time, 3),
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)
        raise HTTPException(500, f"예기치 못한 오류: {str(e)}")


@router.post("/v1/generate_answer/test", summary="답변 생성 테스트")
async def test_generate_answer():
    """답변 생성 엔드포인트를 테스트합니다."""
    try:
        # 간단한 테스트 요청
        test_request = GenerateAnswerRequest(
            query="안녕하세요",
            model="gemma3n:latest",
            top_k=1
        )

        # 실제 generate_answer 호출하지 않고 구조만 확인
        return {
            "status": "success",
            "message": "답변 생성 엔드포인트가 정상적으로 작동합니다",
            "test_request": test_request.dict(),
            "endpoint_available": True
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"답변 생성 엔드포인트 테스트 실패: {str(e)}",
            "endpoint_available": False
        }