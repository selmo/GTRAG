FROM python:3.11-slim

# 환경변수 설정
ENV PYTHONPATH=/app
ENV OLLAMA_HOST=http://172.16.15.112:11434
ENV QDRANT_HOST=localhost
ENV QDRANT_PORT=6333
ENV CELERY_BROKER_URL=redis://localhost:6379/0
ENV CELERY_RESULT_BACKEND=redis://localhost:6379/0
ENV API_BASE_URL=http://localhost:18000

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
    && rm -rf /var/lib/apt/lists/*

# Qdrant 바이너리 다운로드
RUN wget -O /tmp/qdrant.tar.gz https://github.com/qdrant/qdrant/releases/download/v1.9.3/qdrant-x86_64-unknown-linux-gnu.tar.gz \
    && tar -xzf /tmp/qdrant.tar.gz -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/qdrant \
    && rm /tmp/qdrant.tar.gz

# 작업 디렉토리
WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 디렉토리 생성
RUN mkdir -p /var/lib/qdrant/storage /var/lib/redis /var/log/supervisor

# 설정 파일 복사
COPY docker/development/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/development/qdrant-config.yaml /app/qdrant-config.yaml

# 권한 설정
RUN chmod -R 755 /var/log/supervisor /var/lib/qdrant /var/lib/redis

# 포트
EXPOSE 8501

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8501/

# 실행
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]