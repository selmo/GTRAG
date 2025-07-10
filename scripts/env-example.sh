# GTOne RAG System 환경 설정
# 이 파일을 .env로 복사하여 사용하세요: cp .env.example .env

# --- Qdrant Vector Database ---
# Docker Compose 내부 통신용 (변경하지 마세요)
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT__URL=http://qdrant:6333
# Qdrant Cloud 사용 시 API 키 입력
QDRANT__API_KEY=

# --- Ollama LLM Server ---
# 외부 Ollama 서버 주소 (필수 설정!)
OLLAMA_HOST=http://172.16.15.112:11434
# 사용할 모델 (llama3, mistral, phi 등)
OLLAMA_MODEL=llama3:8b-instruct

# --- Celery Background Tasks ---
# Docker Compose 내부 통신용 (변경하지 마세요)
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# --- OCR Settings (Optional) ---
# Azure AI Vision 사용 시 (선택사항)
# AZURE_AI_KEY=your-azure-vision-api-key
# AZURE_AI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/

# --- API Settings ---
# API 서버 설정
API_HOST=0.0.0.0
API_PORT=18000
API_RELOAD=true

# --- Embedding Model ---
# 임베딩 모델 (기본값 사용 권장)
EMBEDDING_MODEL=intfloat/multilingual-e5-large-instruct

# --- System Settings ---
# 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# --- Performance Tuning ---
# 동시 처리 워커 수
CELERY_WORKERS=2
# 임베딩 배치 크기
EMBEDDING_BATCH_SIZE=32
# 최대 업로드 파일 크기 (MB)
MAX_FILE_SIZE_MB=50