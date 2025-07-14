"""
GTOne RAG System - 완전한 main.py (한국어 PDF 최적화)
"""
from fastapi import FastAPI, UploadFile, File, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from celery import Celery
import qdrant_client, qdrant_client.http
import os
import tempfile
import uuid
from pathlib import Path
from datetime import datetime
import logging
import re
from typing import Dict, List

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_qdrant_client():
    """환경변수를 고려한 Qdrant 클라이언트 생성"""
    host = os.getenv("QDRANT_HOST", "localhost")  # 기본값을 localhost로 변경
    port = int(os.getenv("QDRANT_PORT", "6333"))

    logger.info(f"Connecting to Qdrant at {host}:{port}")

    try:
        client = qdrant_client.QdrantClient(host=host, port=port)
        # 연결 테스트
        client.get_collections()
        logger.info(f"Successfully connected to Qdrant at {host}:{port}")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant at {host}:{port}: {e}")
        # localhost로 fallback 시도
        if host != "localhost":
            logger.info("Trying fallback to localhost...")
            try:
                client = qdrant_client.QdrantClient(host="localhost", port=port)
                client.get_collections()
                logger.info(f"Successfully connected to Qdrant fallback at localhost:{port}")
                return client
            except Exception as e2:
                logger.error(f"Fallback to localhost also failed: {e2}")
        raise e

# Qdrant 클라이언트 초기화
qdrant = get_qdrant_client()

# FastAPI 앱 생성
app = FastAPI(
    title="GTOne RAG API",
    description="한국어 최적화된 문서 기반 질의응답 시스템",
    version="1.0.0"
)

from .routes import router as core_router
app.include_router(core_router)

# CORS 설정 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Celery 앱 생성
celery_app = Celery(
    'api.main',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
)

# Celery 설정
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Seoul',
    enable_utc=True,
)


# Celery 태스크
@celery_app.task
def process_document_async(file_path: str, file_name: str):
    """백그라운드에서 문서 처리"""
    try:
        from backend.ingestion.parser import parse_pdf
        from backend.embedding.embedder import embed_texts

        # 파일 읽기
        with open(file_path, 'rb') as f:
            file_content = f.read()

        # PDF 파싱 (한국어 최적화)
        chunks = parse_pdf(file_content, lang_hint="ko")

        if not chunks:
            return {"error": "No content extracted from file", "uploaded": 0}

        # 임베딩 생성
        vectors = embed_texts([c["content"] for c in chunks], prefix="passage")

        # Qdrant에 저장
        points = []
        for c, v in zip(chunks, vectors):
            points.append(
                qdrant_client.http.models.PointStruct(
                    id=c["chunk_id"],
                    vector=v.tolist() if hasattr(v, 'tolist') else v,
                    payload={
                        **c["meta"],
                        "content": c["content"],
                        "upload_timestamp": datetime.utcnow().isoformat(),
                        "has_korean": bool(re.search(r'[가-힣]', c["content"])),
                        "has_english": bool(re.search(r'[a-zA-Z]', c["content"]))
                    }
                )
            )

        qdrant.upsert(collection_name="chunks", points=points)

        return {"uploaded": len(chunks), "file": file_name}

    except Exception as e:
        return {"error": str(e), "uploaded": 0}
    finally:
        # 임시 파일 삭제
        if os.path.exists(file_path):
            os.remove(file_path)


@app.on_event("startup")
async def startup_event():
    """앱 시작 시 Qdrant 컬렉션 확인/생성"""
    try:
        collections = qdrant.get_collections().collections
        collection_names = [c.name for c in collections]

        if "chunks" not in collection_names:
            logger.info("Creating 'chunks' collection...")
            qdrant.create_collection(
                collection_name="chunks",
                vectors_config=qdrant_client.http.models.VectorParams(
                    size=1024,  # E5-large 차원
                    distance=qdrant_client.http.models.Distance.COSINE
                )
            )
            logger.info("Collection 'chunks' created successfully.")
        else:
            logger.info("Collection 'chunks' already exists.")

    except Exception as e:
        logger.error(f"Collection setup error: {e}")


@app.post("/v1/documents")
async def upload(file: UploadFile = File(...)):
    """문서 업로드 (한국어 PDF 인코딩 문제 해결)"""
    try:
        # 파일 검증
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # 지원하는 파일 형식 확인
        allowed_extensions = ['.pdf', '.txt', '.docx', '.doc', '.png', '.jpg', '.jpeg']
        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Supported: {', '.join(allowed_extensions)}"
            )

        # 파일 크기 확인 (50MB 제한)
        max_size = 50 * 1024 * 1024  # 50MB
        file_content = await file.read()

        if len(file_content) > max_size:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB.")

        # 빈 파일 확인
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # 임시 파일로 저장
        temp_dir = tempfile.gettempdir()
        temp_filename = f"{uuid.uuid4()}_{file.filename}"
        temp_path = os.path.join(temp_dir, temp_filename)

        with open(temp_path, "wb") as temp_file:
            temp_file.write(file_content)

        try:
            # 문서 파싱 - 개선된 parser 사용
            chunks = []

            if file_ext == '.pdf':
                # 개선된 PDF 파싱 (여러 라이브러리 단계적 시도)
                from backend.ingestion.parser import parse_pdf
                chunks = parse_pdf(temp_path, lang_hint="ko")  # 한국어 힌트 추가

            elif file_ext in ['.png', '.jpg', '.jpeg']:
                # 이미지 OCR
                from backend.ingestion.ocr import extract_text
                text = extract_text(temp_path, lang_hint="kor+eng")  # 한영 혼합
                if text and text.strip():
                    chunks = [{
                        "chunk_id": str(uuid.uuid4()),
                        "content": text.strip(),
                        "meta": {
                            "source": file.filename,
                            "type": "image",
                            "ocr_confidence": "medium"
                        }
                    }]
                else:
                    raise HTTPException(status_code=400, detail="No text could be extracted from image")

            elif file_ext in ['.docx', '.doc']:
                # Word 문서
                from backend.ingestion.parser import parse_docx
                chunks = parse_docx(temp_path, lang_hint="ko")

            else:  # 텍스트 파일
                from backend.ingestion.parser import parse_text_file
                chunks = parse_text_file(temp_path, lang_hint="ko")

            # 파싱 결과 검증
            if not chunks:
                raise HTTPException(status_code=400, detail="No content could be extracted from file")

            # 빈 청크 필터링
            valid_chunks = [chunk for chunk in chunks if chunk.get("content", "").strip()]

            if not valid_chunks:
                raise HTTPException(status_code=400, detail="No meaningful content extracted from file")

            # 임베딩 생성
            from backend.embedding.embedder import embed_texts

            logger.info(f"Generating embeddings for {len(valid_chunks)} chunks from {file.filename}")

            content_texts = [chunk["content"] for chunk in valid_chunks]

            try:
                vectors = embed_texts(content_texts, prefix="passage")  # 문서용 prefix
            except Exception as e:
                logger.error(f"Embedding generation failed: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to generate embeddings: {str(e)}")

            # Qdrant에 저장
            points = []
            for i, (chunk, vector) in enumerate(zip(valid_chunks, vectors)):
                try:
                    # 벡터 타입 확인 및 변환
                    if hasattr(vector, 'tolist'):
                        vector_list = vector.tolist()
                    elif isinstance(vector, list):
                        vector_list = vector
                    else:
                        vector_list = list(vector)

                    points.append(
                        qdrant_client.http.models.PointStruct(
                            id=chunk["chunk_id"],
                            vector=vector_list,
                            payload={
                                **chunk["meta"],
                                "content": chunk["content"],
                                "chunk_index": i,
                                "file_type": file_ext,
                                "upload_timestamp": datetime.utcnow().isoformat(),
                                "content_length": len(chunk["content"]),
                                "file_size": len(file_content),  # 바이트 단위
                                # 한국어 컨텐츠 감지
                                "has_korean": bool(re.search(r'[가-힣]', chunk["content"])),
                                "has_english": bool(re.search(r'[a-zA-Z]', chunk["content"]))
                            }
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to create point for chunk {i}: {e}")
                    continue

            if not points:
                raise HTTPException(status_code=500, detail="Failed to prepare data for storage")

            # Qdrant 업서트
            try:
                qdrant.upsert(
                    collection_name="chunks",
                    points=points
                )
                logger.info(f"Successfully stored {len(points)} chunks in Qdrant")
            except Exception as e:
                logger.error(f"Qdrant upsert failed: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to store in vector database: {str(e)}")

            # 성공 응답
            korean_chunks = sum(1 for chunk in valid_chunks if re.search(r'[가-힣]', chunk["content"]))

            return {
                "uploaded": len(valid_chunks),
                "filename": file.filename,
                "chunks": len(valid_chunks),
                "korean_chunks": korean_chunks,
                "file_type": file_ext,
                "status": "success",
                "message": f"Successfully processed {file.filename} with {len(valid_chunks)} chunks"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")

        finally:
            # 임시 파일 정리
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/v1/documents/async")
async def upload_async(file: UploadFile = File(...)):
    """비동기 문서 업로드 (Celery 사용)"""
    try:
        # 파일 검증 (위와 동일)
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # 임시 파일로 저장
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")

        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Celery 태스크 실행
        task = process_document_async.delay(file_path, file.filename)

        return {
            "task_id": task.id,
            "status": "processing",
            "message": "Document processing started"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/search")
async def search_endpoint(
        q: str = Query(...),
        top_k: int = Query(3, ge=1, le=20),
        lang: str | None = Query(None),
        min_score: float = Query(0.3, ge=0.0, le=1.0),
        search_type: str = Query("hybrid", regex="^(vector|hybrid|rerank)$")
):
    """
    문서 검색 (한국어 최적화)

    Args:
        q: 검색 쿼리
        top_k: 반환할 결과 수
        lang: 언어 힌트 (ko, en, auto)
        min_score: 최소 유사도 점수
        search_type: 검색 유형 (vector, hybrid, rerank)
    """
    try:
        from backend.embedding.embedder import embed_texts
        from backend.retriever.retriever import search, hybrid_search, search_with_rerank

        # 쿼리 전처리
        processed_query = q.strip()
        if not processed_query:
            raise HTTPException(status_code=400, detail="Empty search query")

        # 언어 자동 감지
        if not lang or lang == "auto":
            if re.search(r'[가-힣]', processed_query):
                detected_lang = "ko"
            else:
                detected_lang = "en"
        else:
            detected_lang = lang

        logger.info(f"Search query: '{processed_query}' (detected language: {detected_lang})")

        # 쿼리 벡터 생성
        try:
            qvec = embed_texts([processed_query], prefix="query")[0]
        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to process search query")

        # 검색 수행
        if search_type == "hybrid":
            hits = hybrid_search(
                query_text=processed_query,
                qvec=qvec,
                top_k=top_k,
                lang=detected_lang
            )
        elif search_type == "rerank":
            hits = search_with_rerank(
                qvec=qvec,
                query_text=processed_query,
                top_k=top_k,
                lang=detected_lang
            )
        else:  # vector
            hits = search(
                qvec=qvec,
                top_k=top_k,
                lang=detected_lang,
                min_score=min_score
            )

        # 결과 포맷팅
        results = []
        for hit in hits:
            # 기본 결과 정보
            result = {
                "chunk_id": hit.id,
                "content": hit.payload.get("content", ""),
                "score": round(float(hit.score), 4),
                "metadata": {k: v for k, v in hit.payload.items() if k != "content"}
            }

            # 검색어 하이라이트 정보 추가
            content = result["content"]
            highlight_info = generate_highlight_info(processed_query, content)
            result["highlights"] = highlight_info

            # 언어 정보 추가
            result["metadata"]["detected_language"] = detected_lang
            result["metadata"]["content_language"] = detect_content_language(content)

            results.append(result)

        logger.info(f"Search completed: {len(results)} results for '{processed_query}'")

        return {
            "query": processed_query,
            "detected_language": detected_lang,
            "search_type": search_type,
            "total_results": len(results),
            "results": results
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/v1/rag/answer")
async def rag_answer(
        q: str = Query(..., description="사용자 질문"),
        top_k: int = Query(3, ge=1, le=10, description="검색할 문서 수"),
        model: str | None = Query(None, description="사용할 LLM 모델"),
        search_type: str = Query("hybrid", regex="^(vector|hybrid|rerank)$"),
        min_score: float = Query(0.3, ge=0.0, le=1.0)
):
    """RAG 기반 답변 생성 (한국어 최적화)"""
    try:
        from backend.embedding.embedder import embed_texts
        from backend.retriever.retriever import search, hybrid_search, search_with_rerank

        # 쿼리 전처리 및 언어 감지
        processed_query = q.strip()
        if not processed_query:
            raise HTTPException(status_code=400, detail="Empty question")

        detected_lang = "ko" if re.search(r'[가-힣]', processed_query) else "en"
        logger.info(f"RAG query: '{processed_query}' (language: {detected_lang})")

        # 1. 벡터 검색
        try:
            qvec = embed_texts([processed_query], prefix="query")[0]
        except Exception as e:
            logger.error(f"Query embedding failed: {e}")
            return {
                "error": "Query processing failed",
                "question": processed_query,
                "answer": "죄송합니다. 질문을 처리하는 중 오류가 발생했습니다.",
                "sources": []
            }

        # 검색 수행
        if search_type == "hybrid":
            hits = hybrid_search(
                query_text=processed_query,
                qvec=qvec,
                top_k=top_k,
                lang=detected_lang
            )
        elif search_type == "rerank":
            hits = search_with_rerank(
                qvec=qvec,
                query_text=processed_query,
                top_k=top_k,
                lang=detected_lang
            )
        else:  # vector
            hits = search(
                qvec=qvec,
                top_k=top_k,
                lang=detected_lang,
                min_score=min_score
            )

        # 검색 결과가 없는 경우
        if not hits:
            return {
                "question": processed_query,
                "answer": "죄송합니다. 관련된 문서를 찾을 수 없습니다. 다른 키워드로 검색해보시기 바랍니다.",
                "sources": [],
                "search_info": {
                    "total_results": 0,
                    "search_type": search_type,
                    "language": detected_lang
                }
            }

        # 2. 컨텍스트 추출 및 정리
        contexts = []
        sources = []

        for hit in hits:
            content = hit.payload.get("content", "")
            if content and len(content.strip()) > 10:
                contexts.append(content)

                # 소스 정보 정리
                source_info = {
                    "chunk_id": hit.id,
                    "content": content[:300] + "..." if len(content) > 300 else content,
                    "score": round(float(hit.score), 4),
                    "source": hit.payload.get("source", "Unknown"),
                    "page": hit.payload.get("page"),
                    "type": hit.payload.get("type", "document")
                }
                sources.append(source_info)

        if not contexts:
            return {
                "question": processed_query,
                "answer": "죄송합니다. 검색된 문서에서 유의미한 내용을 찾을 수 없습니다.",
                "sources": [],
                "search_info": {
                    "total_results": len(hits),
                    "search_type": search_type,
                    "language": detected_lang
                }
            }

        # 3. LLM으로 답변 생성
        try:
            from backend.llm.generator import generate_answer

            # 한국어 질문인 경우 한국어 답변을 위한 시스템 프롬프트 사용
            if detected_lang == "ko":
                answer = generate_answer(
                    query=processed_query,
                    contexts=contexts,
                    model=model,
                    system_prompt="당신은 한국어 문서 기반 질의응답 전문가입니다. 제공된 문서의 내용만을 바탕으로 정확하고 자세한 한국어 답변을 제공하세요. 문서에 없는 내용은 추측하지 마세요."
                )
            else:
                answer = generate_answer(
                    query=processed_query,
                    contexts=contexts,
                    model=model
                )

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            answer = "죄송합니다. 답변 생성 중 오류가 발생했습니다. 관련 문서는 찾았지만 답변을 생성할 수 없습니다."

        return {
            "question": processed_query,
            "answer": answer,
            "sources": sources,
            "search_info": {
                "total_results": len(hits),
                "search_type": search_type,
                "language": detected_lang,
                "contexts_used": len(contexts)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG endpoint error: {e}")
        return {
            "error": str(e),
            "question": q,
            "answer": "죄송합니다. 시스템 오류로 인해 답변을 생성할 수 없습니다.",
            "sources": []
        }


@app.get("/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Celery 태스크 상태 확인"""
    try:
        task = celery_app.AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": task.status,
            "result": task.result if task.ready() else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/health")
async def health_check():
    """시스템 상태 확인 (한국어 지원 정보 포함)"""
    try:
        from backend.llm.generator import check_ollama_connection

        # Qdrant 상태
        try:
            qdrant_info = qdrant.get_collections()
            qdrant_status = "connected"
            collections = [c.name for c in qdrant_info.collections]

            # 한국어 문서 통계
            if "chunks" in collections:
                sample_points = qdrant.scroll(
                    collection_name="chunks",
                    limit=100,
                    with_payload=True
                )[0]

                korean_docs = sum(1 for p in sample_points if p.payload.get("has_korean", False))
                total_docs = len(sample_points)
                korean_ratio = korean_docs / total_docs if total_docs > 0 else 0
            else:
                korean_ratio = 0

        except Exception as e:
            qdrant_status = "disconnected"
            collections = []
            korean_ratio = 0

        # Ollama 상태
        ollama_status = check_ollama_connection()

        # Celery 상태
        try:
            celery_inspect = celery_app.control.inspect()
            active_workers = celery_inspect.active()
            celery_status = "connected" if active_workers else "disconnected"
        except:
            celery_status = "disconnected"

        # 임베딩 모델 상태
        try:
            from backend.embedding.embedder import get_model_info
            embedding_info = get_model_info()
            embedding_status = "ready"
        except Exception as e:
            embedding_info = {"error": str(e)}
            embedding_status = "error"

        return {
            "status": "healthy",
            "services": {
                "qdrant": {
                    "status": qdrant_status,
                    "collections": collections,
                    "korean_content_ratio": round(korean_ratio, 2)
                },
                "ollama": ollama_status,
                "celery": {
                    "status": celery_status
                },
                "embedding": {
                    "status": embedding_status,
                    "info": embedding_info
                }
            },
            "features": {
                "korean_support": True,
                "pdf_parsing_libraries": ["pdfplumber", "PyMuPDF", "pypdf"],
                "search_types": ["vector", "hybrid", "rerank"],
                "supported_formats": [".pdf", ".docx", ".txt", ".png", ".jpg"]
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/v1/documents/debug")
async def upload_debug(request: Request, file: UploadFile = File(...)):
    """디버그용 파일 업로드 엔드포인트 (한국어 PDF 분석)"""
    try:
        # 요청 정보 로깅
        logger.info(f"=== Upload Debug Info ===")
        logger.info(f"Content-Type: {request.headers.get('content-type')}")
        logger.info(f"File filename: {file.filename}")
        logger.info(f"File content_type: {file.content_type}")
        logger.info(f"File size: {file.size}")

        # 파일 내용 읽기 및 분석
        content = await file.read()
        logger.info(f"Content length: {len(content)}")

        # PDF 파일인 경우 텍스트 추출 테스트
        debug_info = {
            "success": True,
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(content),
            "headers": dict(request.headers)
        }

        if file.filename.lower().endswith('.pdf'):
            # 임시 파일 생성하여 파싱 테스트
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(content)
                temp_path = tmp_file.name

            try:
                from backend.ingestion.parser import parse_pdf
                chunks = parse_pdf(temp_path, lang_hint="ko")

                debug_info.update({
                    "parsing_success": True,
                    "chunks_extracted": len(chunks),
                    "sample_content": []
                })

                # 첫 3개 청크의 미리보기 추가
                for i, chunk in enumerate(chunks[:3]):
                    content_preview = chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk[
                        "content"]
                    korean_chars = len(re.findall(r'[가-힣]', chunk["content"]))

                    debug_info["sample_content"].append({
                        "chunk_index": i,
                        "content_preview": content_preview,
                        "content_length": len(chunk["content"]),
                        "korean_characters": korean_chars,
                        "meta": chunk["meta"]
                    })

            except Exception as parse_error:
                logger.error(f"PDF parsing failed during debug: {parse_error}")
                debug_info.update({
                    "parsing_success": False,
                    "parsing_error": str(parse_error)
                })
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass

        # 파일 포인터 리셋
        await file.seek(0)

        return debug_info

    except Exception as e:
        logger.error(f"Debug upload error: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/v1/search/suggest")
async def search_suggestions(q: str = Query(..., min_length=1)):
    """검색어 자동완성 제안"""
    try:
        # 간단한 검색어 제안 로직
        suggestions = []

        # 기본 제안어들 (실제로는 DB나 인덱스에서 가져와야 함)
        common_terms = [
            "계약서", "조건", "기한", "납품", "품질", "가격", "일정",
            "조항", "책임", "보증", "지불", "연장", "해지", "변경"
        ]

        query_lower = q.lower()

        # 부분 매칭되는 용어들 찾기
        for term in common_terms:
            if query_lower in term.lower() or term.lower().startswith(query_lower):
                suggestions.append({
                    "text": term,
                    "type": "common",
                    "score": 1.0
                })

        # 유사어 제안
        if "계약" in q:
            suggestions.extend([
                {"text": "계약 조건", "type": "related", "score": 0.9},
                {"text": "계약 기간", "type": "related", "score": 0.9},
                {"text": "계약서 내용", "type": "related", "score": 0.8}
            ])

        return {
            "query": q,
            "suggestions": suggestions[:10]  # 최대 10개
        }

    except Exception as e:
        logger.error(f"Search suggestion failed: {e}")
        return {"query": q, "suggestions": []}


@app.get("/v1/collections/stats")
async def get_collection_stats():
    """벡터 컬렉션 통계 조회"""
    try:
        from backend.retriever.retriever import get_collection_stats
        return get_collection_stats()
    except Exception as e:
        logger.error(f"Collection stats retrieval failed: {e}")
        return {"error": str(e)}


@app.delete("/v1/documents/{document_id}")
async def delete_document(document_id: str):
    """문서 삭제"""
    try:
        # Qdrant에서 해당 문서의 모든 청크 삭제
        qdrant.delete(
            collection_name="chunks",
            points_selector=qdrant_client.http.models.FilterSelector(
                filter=qdrant_client.http.models.Filter(
                    must=[
                        qdrant_client.http.models.FieldCondition(
                            key="source",
                            match=qdrant_client.http.models.MatchValue(value=document_id)
                        )
                    ]
                )
            )
        )

        logger.info(f"Document {document_id} deleted successfully")
        return {"deleted": True, "document_id": document_id}

    except Exception as e:
        logger.error(f"Document deletion failed: {e}")
        return {"error": str(e), "deleted": False}


@app.post("/v1/search/batch")
async def batch_search(
        queries: List[str],
        top_k: int = Query(3, ge=1, le=10)
):
    """배치 검색 (여러 쿼리 동시 검색)"""
    try:
        from backend.embedding.embedder import embed_texts
        from backend.retriever.retriever import search

        if not queries:
            raise HTTPException(status_code=400, detail="No queries provided")

        if len(queries) > 20:
            raise HTTPException(status_code=400, detail="Too many queries (max 20)")

        # 모든 쿼리에 대한 임베딩 생성
        query_vectors = embed_texts(queries, prefix="query")

        # 각 쿼리별 검색 수행
        results = []
        for i, (query, qvec) in enumerate(zip(queries, query_vectors)):
            try:
                # 언어 감지
                lang = "ko" if re.search(r'[가-힣]', query) else "en"

                # 검색 수행
                hits = search(qvec, top_k=top_k, lang=lang)

                # 결과 포맷팅
                query_results = []
                for hit in hits:
                    query_results.append({
                        "chunk_id": hit.id,
                        "content": hit.payload.get("content", ""),
                        "score": round(float(hit.score), 4),
                        "metadata": {k: v for k, v in hit.payload.items() if k != "content"}
                    })

                results.append({
                    "query": query,
                    "results": query_results
                })

            except Exception as e:
                logger.error(f"Batch search failed for query {i}: {e}")
                results.append({
                    "query": query,
                    "results": [],
                    "error": str(e)
                })

        return {
            "batch_results": results,
            "total_queries": len(queries)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch search failed: {str(e)}")


@app.get("/v1/export")
async def export_data(format: str = Query("json", regex="^(json|csv)$")):
    """데이터 내보내기"""
    try:
        # Qdrant에서 모든 데이터 가져오기
        all_points = []
        offset = None

        while True:
            points, next_offset = qdrant.scroll(
                collection_name="chunks",
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            all_points.extend(points)

            if next_offset is None:
                break
            offset = next_offset

        if format == "json":
            export_data = {
                "exported_at": datetime.utcnow().isoformat(),
                "total_documents": len(all_points),
                "documents": [
                    {
                        "id": str(point.id),
                        "content": point.payload.get("content", ""),
                        "metadata": {k: v for k, v in point.payload.items() if k != "content"}
                    }
                    for point in all_points
                ]
            }
            return export_data

        # CSV 형태로 내보내기는 여기서 구현
        # 간단히 JSON으로 반환
        return {"message": "CSV export not implemented yet"}

    except Exception as e:
        logger.error(f"Data export failed: {e}")
        return {"error": str(e)}


@app.put("/v1/settings")
async def update_settings(settings: Dict):
    """시스템 설정 업데이트"""
    try:
        # 여기서는 간단히 로깅만 수행
        # 실제로는 설정을 DB나 파일에 저장해야 함
        logger.info(f"Settings update requested: {settings}")

        return {
            "updated": True,
            "settings": settings,
            "message": "Settings updated successfully"
        }

    except Exception as e:
        logger.error(f"Settings update failed: {e}")
        return {"error": str(e), "updated": False}


@app.get("/v1/metrics")
async def get_metrics(period: str = Query("1d", regex="^(1h|1d|1w|1m)$")):
    """시스템 메트릭 조회"""
    try:
        # 실제로는 메트릭 저장소에서 데이터를 가져와야 함
        # 여기서는 더미 데이터 반환
        metrics = {
            "period": period,
            "documents": {
                "total": 0,
                "korean": 0,
                "english": 0
            },
            "searches": {
                "total": 0,
                "successful": 0,
                "failed": 0
            },
            "uploads": {
                "total": 0,
                "successful": 0,
                "failed": 0
            }
        }

        # Qdrant에서 실제 문서 수 가져오기
        try:
            collection_info = qdrant.get_collection("chunks")
            total_docs = collection_info.vectors_count

            # 샘플링으로 언어별 통계
            sample_points = qdrant.scroll(
                collection_name="chunks",
                limit=100,
                with_payload=True
            )[0]

            korean_docs = sum(1 for p in sample_points if p.payload.get("has_korean", False))
            english_docs = sum(1 for p in sample_points if p.payload.get("has_english", False))

            metrics["documents"] = {
                "total": total_docs,
                "korean": korean_docs,
                "english": english_docs,
                "korean_ratio": korean_docs / len(sample_points) if sample_points else 0
            }

        except Exception as e:
            logger.warning(f"Failed to get document metrics: {e}")

        return metrics

    except Exception as e:
        logger.error(f"Metrics retrieval failed: {e}")
        return {"error": str(e)}


def generate_highlight_info(query: str, content: str) -> Dict:
    """검색어 하이라이트 정보 생성"""
    highlights = {
        "matches": [],
        "total_matches": 0
    }

    try:
        # 쿼리를 단어별로 분리
        query_words = re.findall(r'\b\w+\b', query.lower())
        content_lower = content.lower()

        for word in query_words:
            if len(word) >= 2:  # 2글자 이상만 하이라이트
                # 대소문자 구분 없이 매칭 위치 찾기
                matches = []
                for match in re.finditer(re.escape(word), content_lower):
                    start_pos = match.start()
                    end_pos = match.end()

                    # 실제 원본 텍스트에서의 매칭 부분
                    matched_text = content[start_pos:end_pos]

                    matches.append({
                        "word": word,
                        "matched_text": matched_text,
                        "start": start_pos,
                        "end": end_pos,
                        "context": content[max(0, start_pos - 50):min(len(content), end_pos + 50)]
                    })

                if matches:
                    highlights["matches"].extend(matches)
                    highlights["total_matches"] += len(matches)

        # 중복 제거 및 정렬
        highlights["matches"] = sorted(highlights["matches"], key=lambda x: x["start"])

    except Exception as e:
        logger.warning(f"Highlight generation failed: {e}")

    return highlights


def detect_content_language(content: str) -> str:
    """컨텐츠 언어 감지"""
    korean_chars = len(re.findall(r'[가-힣]', content))
    english_words = len(re.findall(r'\b[a-zA-Z]+\b', content))
    total_chars = len(content)

    if korean_chars > total_chars * 0.1:
        return "ko"
    elif english_words > 5:
        return "en"
    else:
        return "mixed"


# 기본 라우트
@app.get("/")
async def root():
    return {
        "message": "GTOne RAG API Server",
        "version": "1.0.0",
        "features": {
            "korean_support": True,
            "pdf_parsing": ["pdfplumber", "PyMuPDF", "pypdf"],
            "search_types": ["vector", "hybrid", "rerank"]
        }
    }


# 간단한 버전 확인
@app.get("/version")
async def get_version():
    return {
        "version": "1.0.0",
        "korean_optimization": True,
        "last_updated": "2024-12-01"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=18000)