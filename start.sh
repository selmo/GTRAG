#!/bin/bash

echo "🚀 GTOne RAG System 시작 중..."

# 1. 프로젝트 구조 확인 및 생성
echo "📁 프로젝트 구조 확인 중..."
mkdir -p api ingestion embedding retriever scripts llm

# __init__.py 파일 생성
touch api/__init__.py ingestion/__init__.py embedding/__init__.py retriever/__init__.py llm/__init__.py

# 2. Docker Compose 빌드 및 시작
echo "🐳 Docker 컨테이너 시작 중..."
docker compose up --build -d

# 3. 서비스 준비 대기
echo "⏳ 서비스 준비 중... (30초 대기)"
sleep 30

# 4. 서비스 상태 확인
echo "✅ 서비스 상태 확인 중..."

# API 상태 확인
if curl -s http://localhost:8000/v1/health > /dev/null; then
    echo "✅ API 서버: 정상 작동"
else
    echo "❌ API 서버: 연결 실패"
fi

# Streamlit 상태 확인
if curl -s http://localhost:8501 > /dev/null; then
    echo "✅ Web UI: 정상 작동"
else
    echo "❌ Web UI: 연결 실패"
fi

echo ""
echo "🎉 GTOne RAG System이 준비되었습니다!"
echo ""
echo "📌 접속 정보:"
echo "   - Web UI: http://localhost:8501"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Qdrant UI: http://localhost:6333/dashboard"
echo ""
echo "💡 시스템 종료: docker compose down"
echo "📋 로그 확인: docker compose logs -f"