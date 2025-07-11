from fastapi import FastAPI, UploadFile, File, Query
from celery import Celery
from ingestion.parser import parse_pdf
from embedding.embedder import embed_texts
from retriever.retriever import search
import asyncio, qdrant_client, qdrant_client.http
import os

# FastAPI 앱 생성
app = FastAPI(title="GTOne POC API")

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

# Qdrant 클라이언트
qdrant = qdrant_client.QdrantClient(
    host=os.getenv("QDRANT_HOST", "qdrant"),
    port=int(os.getenv("QDRANT_PORT", "6333"))
)


# Celery 태스크 예시
@celery_app.task
def process_document_async(file_path: str, file_name: str):
    """백그라운드에서 문서 처리"""
    with open(file_path, 'rb') as f:
        chunks = parse_pdf(f.read())

    vectors = embed_texts([c["content"] for c in chunks])

    qdrant.upsert(
        collection_name="chunks",
        points=[
            qdrant_client.http.models.PointStruct(
                id=c["chunk_id"],
                vector=v,
                payload=c["meta"]
            ) for c, v in zip(chunks, vectors)
        ],
    )

    # 임시 파일 삭제
    os.remove(file_path)
    return {"uploaded": len(chunks), "file": file_name}


@app.on_event("startup")
async def startup_event():
    """앱 시작 시 Qdrant 컬렉션 확인/생성"""
    try:
        collections = qdrant.get_collections().collections
        if "chunks" not in [c.name for c in collections]:
            qdrant.create_collection(
                collection_name="chunks",
                vectors_config=qdrant_client.http.models.VectorParams(
                    size=1024,  # E5-large 차원
                    distance=qdrant_client.http.models.Distance.COSINE
                )
            )
    except Exception as e:
        print(f"Collection setup error: {e}")


@app.post("/v1/documents")
async def upload(file: UploadFile = File(...)):
    chunks = parse_pdf(await file.read())
    vectors = embed_texts([c["content"] for c in chunks])
    qdrant.upsert(
        collection_name="chunks",
        points=[
            qdrant_client.http.models.PointStruct(
                id=c["chunk_id"], vector=v, payload=c["meta"]
            ) for c, v in zip(chunks, vectors)
        ],
    )
    return {"uploaded": len(chunks)}


@app.post("/v1/documents/async")
async def upload_async(file: UploadFile = File(...)):
    """비동기 문서 업로드 (Celery 사용)"""
    # 임시 파일로 저장
    import tempfile
    import uuid

    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{file.filename}")

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Celery 태스크 실행
    task = process_document_async.delay(file_path, file.filename)

    return {
        "task_id": task.id,
        "status": "processing",
        "message": "Document processing started"
    }


@app.get("/v1/search")
async def search_endpoint(
        q: str = Query(...), top_k: int = 3, lang: str | None = None
):
    qvec = embed_texts([q])[0]
    hits = search(qvec, top_k, lang)
    return [
        {
            "chunk_id": h.id,
            "content": h.payload.get("content", ""),
            "score": h.score,
        }
        for h in hits
    ]


@app.get("/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Celery 태스크 상태 확인"""
    task = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": task.status,
        "result": task.result if task.ready() else None
    }


@app.post("/v1/rag/answer")
async def rag_answer(
        q: str = Query(..., description="사용자 질문"),
        top_k: int = Query(3, ge=1, le=10, description="검색할 문서 수"),
        model: str | None = Query(None, description="사용할 LLM 모델")
):
    """RAG 기반 답변 생성"""
    try:
        # 1. 벡터 검색
        qvec = embed_texts([q])[0]
        hits = search(qvec, top_k)

        # 2. 컨텍스트 추출
        contexts = [h.payload.get("content", "") for h in hits]

        # 3. LLM으로 답변 생성
        from llm.generator import generate_answer
        answer = generate_answer(q, contexts, model)

        return {
            "question": q,
            "answer": answer,
            "sources": [
                {
                    "chunk_id": h.id,
                    "content": h.payload.get("content", "")[:200] + "...",
                    "score": h.score
                }
                for h in hits
            ]
        }
    except Exception as e:
        return {
            "error": str(e),
            "question": q,
            "answer": "답변 생성 중 오류가 발생했습니다."
        }


@app.get("/v1/health")
async def health_check():
    """시스템 상태 확인"""
    from llm.generator import check_ollama_connection

    # Qdrant 상태
    try:
        qdrant_info = qdrant.get_collections()
        qdrant_status = "connected"
        collections = [c.name for c in qdrant_info.collections]
    except:
        qdrant_status = "disconnected"
        collections = []

    # Ollama 상태
    ollama_status = check_ollama_connection()

    return {
        "status": "healthy",
        "services": {
            "qdrant": {
                "status": qdrant_status,
                "collections": collections
            },
            "ollama": ollama_status,
            "celery": {
                "status": "connected" if celery_app.control.inspect().active() else "disconnected"
            }
        }
    }


# 라우터 추가 (옵션)
from api.routes import router

app.include_router(router, prefix="/api")