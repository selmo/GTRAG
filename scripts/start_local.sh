#!/bin/bash

echo "🚀 GTOne RAG System 로컬 실행 모드"
echo "⚠️  주의: Qdrant와 Redis가 로컬에 설치되어 있어야 합니다."

# 1. Python 가상환경 확인/생성
if [ ! -d "venv" ]; then
    echo "📦 Python 가상환경 생성 중..."
    python3 -m venv venv
fi

# 2. 가상환경 활성화
echo "🐍 Python 가상환경 활성화..."
source venv/bin/activate

# 3. 의존성 설치
echo "📚 Python 패키지 설치 중..."
pip install -r requirements.txt

# 4. 환경변수 설정
echo "🔧 환경변수 설정..."
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
export OLLAMA_HOST=http://172.16.15.112:11434
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/0

# 5. 필요한 서비스 확인
echo "✅ 서비스 상태 확인..."

# Qdrant 확인
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "✅ Qdrant: 실행 중"
else
    echo "❌ Qdrant: 실행되지 않음"
    echo "   Qdrant 시작: ./qdrant --config-path config/config.yaml"
fi

# Redis 확인
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis: 실행 중"
else
    echo "❌ Redis: 실행되지 않음"
    echo "   Redis 시작: redis-server"
fi

# 6. 서비스 시작
echo ""
echo "🚀 서비스 시작..."

# FastAPI 서버 (백그라운드)
echo "Starting API server..."
nohup uvicorn api.main:app --host 0.0.0.0 --port 18000 --reload > api.log 2>&1 &
API_PID=$!
echo "API Server PID: $API_PID"

# Celery Worker (백그라운드)
echo "Starting Celery worker..."
nohup celery -A api.main.celery_app worker -l info > celery.log 2>&1 &
CELERY_PID=$!
echo "Celery Worker PID: $CELERY_PID"

# Streamlit UI (백그라운드)
echo "Starting Streamlit UI..."
nohup streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501 > streamlit.log 2>&1 &
STREAMLIT_PID=$!
echo "Streamlit PID: $STREAMLIT_PID"

# PID 저장
echo $API_PID > .api.pid
echo $CELERY_PID > .celery.pid
echo $STREAMLIT_PID > .streamlit.pid

# 서비스 준비 대기
echo "⏳ 서비스 준비 중... (10초 대기)"
sleep 10

# 최종 상태 확인
echo ""
echo "✅ 시스템 시작 완료!"
echo ""
echo "📌 접속 정보:"
echo "   - Web UI: http://localhost:8501"
echo "   - API Docs: http://localhost:18000/docs"
echo "   - Qdrant Dashboard: http://localhost:6333/dashboard"
echo ""
echo "📋 로그 확인:"
echo "   - API: tail -f api.log"
echo "   - Celery: tail -f celery.log"
echo "   - Streamlit: tail -f streamlit.log"
echo ""
echo "💡 시스템 종료: ./stop_local.sh"