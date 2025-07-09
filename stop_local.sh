#!/bin/bash

echo "🛑 GTOne RAG System 종료 중..."

# PID 파일에서 프로세스 ID 읽기
if [ -f .api.pid ]; then
    API_PID=$(cat .api.pid)
    echo "Stopping API server (PID: $API_PID)..."
    kill $API_PID 2>/dev/null
    rm .api.pid
fi

if [ -f .celery.pid ]; then
    CELERY_PID=$(cat .celery.pid)
    echo "Stopping Celery worker (PID: $CELERY_PID)..."
    kill $CELERY_PID 2>/dev/null
    rm .celery.pid
fi

if [ -f .streamlit.pid ]; then
    STREAMLIT_PID=$(cat .streamlit.pid)
    echo "Stopping Streamlit UI (PID: $STREAMLIT_PID)..."
    kill $STREAMLIT_PID 2>/dev/null
    rm .streamlit.pid
fi

# 포트가 여전히 사용 중인지 확인
sleep 2

# 18000 포트 확인
if lsof -i:18000 > /dev/null 2>&1; then
    echo "⚠️  포트 18000이 여전히 사용 중입니다. 강제 종료 중..."
    lsof -ti:18000 | xargs kill -9 2>/dev/null
fi

# 8501 포트 확인
if lsof -i:8501 > /dev/null 2>&1; then
    echo "⚠️  포트 8501이 여전히 사용 중입니다. 강제 종료 중..."
    lsof -ti:8501 | xargs kill -9 2>/dev/null
fi

echo "✅ 모든 서비스가 종료되었습니다."