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
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 디렉토리 구조 생성
RUN mkdir -p api ingestion embedding retriever scripts llm

# 파일들을 올바른 위치로 이동
RUN mv main.py routes.py schemas.py api/ 2>/dev/null || true
RUN mv parser.py ocr.py ingestion/ 2>/dev/null || true
RUN mv embedder.py embedding/ 2>/dev/null || true
RUN mv retriever.py retriever/ 2>/dev/null || true
RUN mv migrate_vectors.py scripts/ 2>/dev/null || true

# __init__.py 파일 생성
RUN touch api/__init__.py ingestion/__init__.py embedding/__init__.py retriever/__init__.py llm/__init__.py

# 임시 디렉토리 생성
RUN mkdir -p /tmp

# 기본 포트 노출
EXPOSE 8000