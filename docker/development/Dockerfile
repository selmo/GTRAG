FROM python:3.11-slim

# 환경변수 기본값 설정 (먼저 설정)
ENV PYTHONPATH=/app
ENV OLLAMA_HOST=http://172.16.15.112:11434
ENV QDRANT_HOST=localhost
ENV QDRANT_PORT=6333
ENV CELERY_BROKER_URL=redis://localhost:6379/0
ENV CELERY_RESULT_BACKEND=redis://localhost:6379/0
ENV API_BASE_URL=http://localhost:18000

# 시스템 패키지 설치 (한 번에 모든 패키지 설치)
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
    && rm -rf /var/lib/apt/lists/*

# Qdrant 바이너리 다운로드 및 설치
RUN wget -O /tmp/qdrant.tar.gz https://github.com/qdrant/qdrant/releases/download/v1.9.3/qdrant-x86_64-unknown-linux-gnu.tar.gz \
    && tar -xzf /tmp/qdrant.tar.gz -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/qdrant \
    && rm /tmp/qdrant.tar.gz

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

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

# 파일들을 올바른 위치로 이동 (이미 정리되어 있지 않은 경우)
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

# Supervisor 설정 파일 생성
RUN cat <<EOF > /etc/supervisor/conf.d/supervisord.conf
[supervisord]
nodaemon=true
user=root
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.pid

[supervisorctl]
serverurl=unix:///var/run/supervisor.sock

[unix_http_server]
file=/var/run/supervisor.sock
chmod=0700

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[program:redis]
command=redis-server --appendonly yes --dir /var/lib/redis
stdout_logfile=/var/log/supervisor/redis.log
stderr_logfile=/var/log/supervisor/redis.log
autorestart=true
user=root
priority=100

[program:qdrant]
command=qdrant --config-path /app/qdrant-config.yaml
stdout_logfile=/var/log/supervisor/qdrant.log
stderr_logfile=/var/log/supervisor/qdrant.log
autorestart=true
user=root
environment=QDRANT__LOG_LEVEL=INFO,QDRANT__SERVICE__HTTP_PORT=6333
priority=200

[program:api]
command=uvicorn api.main:app --host 0.0.0.0 --port 18000 --reload
directory=/app
stdout_logfile=/var/log/supervisor/api.log
stderr_logfile=/var/log/supervisor/api.log
autorestart=true
user=root
environment=PYTHONPATH=/app,CELERY_BROKER_URL=redis://localhost:6379/0,CELERY_RESULT_BACKEND=redis://localhost:6379/0,QDRANT_HOST=localhost,QDRANT_PORT=6333
priority=300

[program:celery]
command=celery -A api.main.celery_app worker -l info
directory=/app
stdout_logfile=/var/log/supervisor/celery.log
stderr_logfile=/var/log/supervisor/celery.log
autorestart=true
user=root
environment=PYTHONPATH=/app,CELERY_BROKER_URL=redis://localhost:6379/0,CELERY_RESULT_BACKEND=redis://localhost:6379/0,QDRANT_HOST=localhost,QDRANT_PORT=6333
priority=400

[program:streamlit]
command=streamlit run ui/Home.py --server.address 0.0.0.0 --server.port 8501 --server.enableCORS false --server.enableXsrfProtection false
directory=/app
stdout_logfile=/var/log/supervisor/streamlit.log
stderr_logfile=/var/log/supervisor/streamlit.log
autorestart=true
user=root
environment=PYTHONPATH=/app,API_BASE_URL=http://localhost:18000,STREAMLIT_SERVER_ENABLE_CORS=false,STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
priority=500
EOF

# Qdrant 설정 파일 생성
RUN cat <<EOF > /app/qdrant-config.yaml
log_level: INFO
service:
  http_port: 6333
  grpc_port: 6334
storage:
  storage_path: /var/lib/qdrant/storage
EOF

# 로그 디렉토리 권한 설정
RUN chmod -R 755 /var/log/supervisor && \
    chmod -R 755 /var/lib/qdrant && \
    chmod -R 755 /var/lib/redis

# 포트 노출 (외부로는 Streamlit만)
EXPOSE 8501

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/ && \
        curl -f http://localhost:18000/v1/health && \
        curl -f http://localhost:6333/health

# Supervisor를 통해 모든 서비스 실행
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]