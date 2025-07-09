FROM python:3.11-slim

# 시스템 패키지 설치 (OCR, 문서 처리용)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-kor \
    tesseract-ocr-eng \
    libmagic1 \
    libxml2 \
    libxslt1-dev \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

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
    .streamlit

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

# 임시 디렉토리 생성
RUN mkdir -p /tmp

# Python 경로 설정
ENV PYTHONPATH=/app

# 기본 포트 노출
EXPOSE 18000 8501

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:18000/health || exit 1

# 기본 명령어 (docker-compose에서 오버라이드됨)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "18000"]