FROM python:3.11-slim

# 빌드 인자로 아키텍처 정보 받기
ARG TARGETARCH
ARG BUILDPLATFORM
ARG TARGETPLATFORM

# 환경변수 기본값 설정
ENV PYTHONPATH=/app
ENV OLLAMA_HOST=http://172.16.15.112:11434
ENV QDRANT_PORT=6333
ENV CELERY_BROKER_URL=redis://localhost:6379/0
ENV CELERY_RESULT_BACKEND=redis://localhost:6379/0
ENV API_BASE_URL=http://localhost:18000

# 빌드 정보 출력
RUN echo "=== Build Information ===" && \
    echo "Build Platform: ${BUILDPLATFORM}" && \
    echo "Target Platform: ${TARGETPLATFORM}" && \
    echo "Target Architecture: ${TARGETARCH}" && \
    echo "Runtime Architecture: $(uname -m)" && \
    echo "========================="

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-kor \
    tesseract-ocr-eng \
    libmagic1 \
    libxml2 \
    libxslt1-dev \
    poppler-utils \
    curl \
    redis-server \
    supervisor \
    wget \
    htop \
    vim \
    net-tools \
    procps \
    lsof \
    file \
    && rm -rf /var/lib/apt/lists/*

# 아키텍처별 Qdrant 설치 여부 결정
RUN ARCH=$(uname -m) && \
    echo "Detected runtime architecture: $ARCH" && \
    if [ "$ARCH" = "x86_64" ]; then \
        echo "Installing Qdrant binary for x86_64..."; \
        QDRANT_URL="https://github.com/qdrant/qdrant/releases/download/v1.9.3/qdrant-x86_64-unknown-linux-gnu.tar.gz"; \
        wget -O /tmp/qdrant.tar.gz "$QDRANT_URL" && \
        tar -xzf /tmp/qdrant.tar.gz -C /usr/local/bin/ && \
        chmod +x /usr/local/bin/qdrant && \
        rm /tmp/qdrant.tar.gz && \
        /usr/local/bin/qdrant --version && \
        echo "Qdrant binary installation successful" && \
        echo "QDRANT_MODE=binary" > /app/.arch-config; \
    else \
        echo "ARM64 detected - will use external Qdrant container"; \
        echo "QDRANT_MODE=external" > /app/.arch-config; \
        touch /usr/local/bin/qdrant; \
    fi

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ========================================
# 🔥 추가: 임베딩 모델 사전 다운로드
# ========================================
RUN echo "=== Pre-downloading embedding models ===" && \
    python -c "\
import os; \
from sentence_transformers import SentenceTransformer; \
print('Downloading E5-large model...'); \
model = SentenceTransformer('intfloat/multilingual-e5-large-instruct'); \
print('✅ E5-large model downloaded successfully'); \
test_vec = model.encode(['test'], convert_to_numpy=True); \
print(f'✅ Model test successful - vector shape: {test_vec.shape}'); \
" && \
    echo "=== Model pre-download completed ==="

# 애플리케이션 코드 복사
COPY . .

# 디렉토리 구조 생성
RUN mkdir -p \
    api \
    ingestion \
    embedding \
    retriever \
    scripts \
    llm \
    ui/pages \
    ui/components \
    ui/utils \
    .streamlit \
    /var/lib/qdrant/storage \
    /var/lib/redis \
    /var/log/supervisor

# 파일들을 올바른 위치로 이동
RUN if [ -f "main.py" ]; then mv main.py api/; fi && \
    if [ -f "routes.py" ]; then mv routes.py api/; fi && \
    if [ -f "schemas.py" ]; then mv schemas.py api/; fi && \
    if [ -f "parser.py" ]; then mv parser.py ingestion/; fi && \
    if [ -f "ocr.py" ]; then mv ocr.py ingestion/; fi && \
    if [ -f "embedder.py" ]; then mv embedder.py embedding/; fi && \
    if [ -f "retriever.py" ]; then mv retriever.py retriever/; fi && \
    if [ -f "migrate_vectors.py" ]; then mv migrate_vectors.py scripts/; fi && \
    if [ -f "streamlit_app.py" ] && [ ! -f "ui/streamlit_app.py" ]; then mv streamlit_app.py ui/; fi

# __init__.py 파일 생성
RUN touch \
    api/__init__.py \
    ingestion/__init__.py \
    embedding/__init__.py \
    retriever/__init__.py \
    llm/__init__.py \
    ui/__init__.py \
    ui/components/__init__.py \
    ui/utils/__init__.py \
    ui/pages/__init__.py

# ========================================
# 🔥 추가: 모듈 사전 로드 테스트
# ========================================
RUN echo "=== Testing module imports ===" && \
    cd /app && \
    python -c "\
print('Testing embedder import...'); \
from embedding.embedder import embed_texts; \
print('✅ Embedder import successful'); \
print('Testing API imports...'); \
import api.main; \
print('✅ API main import successful'); \
print('All critical imports completed successfully'); \
" && \
    echo "=== Module import test completed ==="

# Supervisor 설정 스크립트 생성
RUN cat > /app/setup-supervisor.sh << 'SETUP_SCRIPT_EOF'
#!/bin/bash
set -e

echo "Setting up Supervisor configuration..."

# 아키텍처 설정 읽기
if [ -f /app/.arch-config ]; then
    QDRANT_MODE=$(cat /app/.arch-config | cut -d'=' -f2)
    echo "Qdrant Mode: $QDRANT_MODE"
else
    QDRANT_MODE="unknown"
    echo "Warning: Architecture config not found, using unknown mode"
fi

# 기본 Supervisor 설정 생성
cat > /etc/supervisor/conf.d/supervisord.conf << 'SUPERVISOR_BASE_EOF'
[supervisord]
nodaemon=true
user=root
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.pid
loglevel=info

[supervisorctl]
serverurl=unix:///var/run/supervisor.sock

[unix_http_server]
file=/var/run/supervisor.sock
chmod=0700

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[program:redis]
command=redis-server --appendonly yes --dir /var/lib/redis --bind 127.0.0.1 --port 6379
stdout_logfile=/var/log/supervisor/redis.log
stderr_logfile=/var/log/supervisor/redis.log
autorestart=true
user=root
priority=100
startsecs=3
startretries=3
SUPERVISOR_BASE_EOF

# 아키텍처별 Qdrant 섹션 추가
if [ "$QDRANT_MODE" = "binary" ]; then
    echo "Adding Qdrant binary section..."
    cat >> /etc/supervisor/conf.d/supervisord.conf << 'QDRANT_BINARY_EOF'

[program:qdrant]
command=qdrant --config-path /app/qdrant-config.yaml
stdout_logfile=/var/log/supervisor/qdrant.log
stderr_logfile=/var/log/supervisor/qdrant.log
autorestart=true
user=root
environment=QDRANT__LOG_LEVEL=INFO,QDRANT__SERVICE__HTTP_PORT=6333
priority=200
startsecs=5
startretries=3
QDRANT_BINARY_EOF
    echo "QDRANT_HOST=localhost" > /app/.env-override
else
    echo "Skipping Qdrant binary section for external mode..."
    echo "QDRANT_HOST=qdrant" > /app/.env-override
fi

# 환경변수 설정 읽기
QDRANT_HOST_SETTING=$(cat /app/.env-override)
echo "Using environment setting: $QDRANT_HOST_SETTING"

# API 및 기타 서비스 섹션 추가
cat >> /etc/supervisor/conf.d/supervisord.conf << EOF

[program:api]
command=uvicorn api.main:app --host 0.0.0.0 --port 18000 --reload
directory=/app
stdout_logfile=/var/log/supervisor/api.log
stderr_logfile=/var/log/supervisor/api.log
autorestart=true
user=root
environment=PYTHONPATH=/app,CELERY_BROKER_URL=redis://localhost:6379/0,CELERY_RESULT_BACKEND=redis://localhost:6379/0,${QDRANT_HOST_SETTING},QDRANT_PORT=6333
priority=300
startsecs=10
startretries=3

[program:celery]
command=celery -A api.main.celery_app worker -l info --concurrency=2
directory=/app
stdout_logfile=/var/log/supervisor/celery.log
stderr_logfile=/var/log/supervisor/celery.log
autorestart=true
user=root
environment=PYTHONPATH=/app,CELERY_BROKER_URL=redis://localhost:6379/0,CELERY_RESULT_BACKEND=redis://localhost:6379/0,${QDRANT_HOST_SETTING},QDRANT_PORT=6333
priority=400
startsecs=15
startretries=3

[program:streamlit]
command=streamlit run ui/Home.py --server.address 0.0.0.0 --server.port 8501 --server.enableCORS false --server.enableXsrfProtection false
directory=/app
stdout_logfile=/var/log/supervisor/streamlit.log
stderr_logfile=/var/log/supervisor/streamlit.log
autorestart=true
user=root
environment=PYTHONPATH=/app,API_BASE_URL=http://localhost:18000,STREAMLIT_SERVER_ENABLE_CORS=false,STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
priority=500
startsecs=20
startretries=3
EOF

echo "Supervisor configuration completed."
echo "Configuration preview:"
head -20 /etc/supervisor/conf.d/supervisord.conf
SETUP_SCRIPT_EOF

# 설정 스크립트 실행
RUN chmod +x /app/setup-supervisor.sh && \
    /app/setup-supervisor.sh

# Qdrant 설정 파일 생성
RUN cat > /app/qdrant-config.yaml << 'QDRANT_CONFIG_EOF'
log_level: INFO
service:
  http_port: 6333
  grpc_port: 6334
storage:
  storage_path: /var/lib/qdrant/storage
  snapshots_path: /var/lib/qdrant/snapshots
  temp_path: /var/lib/qdrant/temp
cluster:
  enabled: false
telemetry:
  disabled: true
QDRANT_CONFIG_EOF

# 시작 스크립트 생성
RUN cat > /app/start.sh << 'START_SCRIPT_EOF'
#!/bin/bash
set -e

echo "🚀 GTOne RAG System Starting..."
echo "Architecture: $(uname -m)"

# 아키텍처 설정 읽기
if [ -f /app/.arch-config ]; then
    QDRANT_MODE=$(cat /app/.arch-config | cut -d'=' -f2)
    echo "Qdrant Mode: $QDRANT_MODE"

    if [ "$QDRANT_MODE" = "binary" ]; then
        echo "Using built-in Qdrant binary"
        if [ -f /usr/local/bin/qdrant ]; then
            echo "Qdrant Version: $(/usr/local/bin/qdrant --version 2>/dev/null || echo 'version check failed')"
        fi
    else
        echo "Using external Qdrant container"
        echo "Waiting for external Qdrant to be ready..."
        for i in {1..30}; do
            if curl -s http://qdrant:6333/health > /dev/null 2>&1; then
                echo "✅ External Qdrant is ready"
                break
            fi
            echo "⏳ Waiting for Qdrant... ($i/30)"
            sleep 2
        done
    fi
fi

# 환경변수 override 적용
if [ -f /app/.env-override ]; then
    export $(cat /app/.env-override | xargs)
    echo "Applied environment overrides: $(cat /app/.env-override)"
fi

# 디렉토리 권한 설정
chown -R root:root /var/lib/redis /var/log/supervisor 2>/dev/null || true
if [ -d /var/lib/qdrant ]; then
    chown -R root:root /var/lib/qdrant 2>/dev/null || true
fi

echo "Starting Supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
START_SCRIPT_EOF

RUN chmod +x /app/start.sh

# 헬스체크 스크립트 생성
RUN cat > /app/healthcheck.sh << 'HEALTHCHECK_SCRIPT_EOF'
#!/bin/bash
set -e

echo "=== Health Check Start ==="

# Streamlit 체크
if curl -f http://localhost:8501/ > /dev/null 2>&1; then
    echo "✅ Streamlit: OK"
else
    echo "❌ Streamlit: FAIL"
    exit 1
fi

# Redis 체크
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis: OK"
else
    echo "❌ Redis: FAIL"
    exit 1
fi

# Qdrant 체크 (아키텍처별)
if [ -f /app/.arch-config ]; then
    QDRANT_MODE=$(cat /app/.arch-config | cut -d'=' -f2)
    if [ "$QDRANT_MODE" = "binary" ]; then
        QDRANT_URL="http://localhost:6333/health"
    else
        QDRANT_URL="http://qdrant:6333/health"
    fi
else
    QDRANT_URL="http://localhost:6333/health"
    QDRANT_MODE="unknown"
fi

if curl -f "$QDRANT_URL" > /dev/null 2>&1; then
    echo "✅ Qdrant: OK ($QDRANT_MODE)"
else
    echo "❌ Qdrant: FAIL ($QDRANT_MODE)"
    exit 1
fi

# API 체크 (관대하게)
if curl -f http://localhost:18000/docs > /dev/null 2>&1; then
    echo "✅ API: OK"
else
    echo "⚠️ API: 시작 중..."
fi

echo "=== Health Check End ==="
HEALTHCHECK_SCRIPT_EOF

RUN chmod +x /app/healthcheck.sh

# 권한 설정
RUN chmod -R 755 /var/log/supervisor && \
    chmod -R 755 /var/lib/redis && \
    if [ -d /var/lib/qdrant ]; then chmod -R 755 /var/lib/qdrant; fi

# 빌드 완료 정보 출력
RUN echo "=== Build Complete ===" && \
    echo "Architecture: $(uname -m)" && \
    echo "Qdrant Config: $(cat /app/.arch-config 2>/dev/null || echo 'config not found')" && \
    echo "Environment Override: $(cat /app/.env-override 2>/dev/null || echo 'no override')" && \
    echo "Project Structure:" && \
    ls -la /app/ && \
    echo "Supervisor Config Check:" && \
    head -15 /etc/supervisor/conf.d/supervisord.conf && \
    echo "======================="

# 포트 노출
EXPOSE 8501

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=15s --start-period=120s --retries=5 \
    CMD /app/healthcheck.sh

# 시작 스크립트 실행
CMD ["/app/start.sh"]