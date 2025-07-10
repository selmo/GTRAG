#!/bin/bash
# GTOne RAG System 상세 진단 스크립트

echo "🔍 GTOne RAG System 상세 진단 시작"
echo "======================================"

# 1. Supervisor 프로세스 상태 확인
echo "1️⃣ Supervisor 프로세스 상태:"
docker compose -f docker/development/docker-compose.yml exec gtrag-dev supervisorctl status

echo -e "\n2️⃣ 실행 중인 프로세스 확인:"
docker compose -f docker/development/docker-compose.yml exec gtrag-dev ps aux | grep -E "(redis|qdrant|uvicorn|celery|streamlit)" | grep -v grep

echo -e "\n3️⃣ 포트 리스닝 상태:"
docker compose -f docker/development/docker-compose.yml exec gtrag-dev netstat -tlnp

echo -e "\n4️⃣ API 서버 로그 (마지막 50줄):"
docker compose -f docker/development/docker-compose.yml exec gtrag-dev tail -n 50 /var/log/supervisor/api.log

echo -e "\n5️⃣ Qdrant 로그 (마지막 50줄):"
docker compose -f docker/development/docker-compose.yml exec gtrag-dev tail -n 50 /var/log/supervisor/qdrant.log

echo -e "\n6️⃣ Celery 로그 (마지막 20줄):"
docker compose -f docker/development/docker-compose.yml exec gtrag-dev tail -n 20 /var/log/supervisor/celery.log

echo -e "\n7️⃣ Supervisor 메인 로그:"
docker compose -f docker/development/docker-compose.yml exec gtrag-dev tail -n 30 /var/log/supervisor/supervisord.log

echo -e "\n8️⃣ 디렉토리 구조 확인:"
docker compose -f docker/development/docker-compose.yml exec gtrag-dev ls -la /app/

echo -e "\n9️⃣ Python 모듈 확인:"
docker compose -f docker/development/docker-compose.yml exec gtrag-dev python -c "import sys; print('Python path:'); [print(p) for p in sys.path]"

echo -e "\n🔟 API 모듈 존재 확인:"
docker compose -f docker/development/docker-compose.yml exec gtrag-dev ls -la /app/api/

echo -e "\n진단 완료. 위 결과를 바탕으로 문제를 분석하겠습니다."