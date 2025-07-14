#!/bin/bash

echo "🚀 GTOne RAG 백엔드 시작 (Conda 환경)"
echo "======================================"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

START_TIME=$(date)
echo "시작 시간: $START_TIME"

# 1. Conda 환경 확인
echo -e "\n${BLUE}🐍 Conda 환경 확인...${NC}"
if ! command -v conda &> /dev/null; then
    echo -e "${RED}❌ Conda가 설치되어 있지 않습니다.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Conda 버전: $(conda --version)${NC}"

# 2. 환경 이름 설정
CONDA_ENV_NAME="GTRAG"

if conda env list | grep -q "^$CONDA_ENV_NAME "; then
    echo -e "${GREEN}✅ 환경 '$CONDA_ENV_NAME' 존재${NC}"
else
    echo -e "${YELLOW}⚠️ 환경 '$CONDA_ENV_NAME' 없음. 생성 중...${NC}"
    conda create -n $CONDA_ENV_NAME python=3.11 -y || exit 1
fi

# 3. Conda 환경 활성화
echo -e "\n${BLUE}📦 Conda 환경 활성화...${NC}"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate $CONDA_ENV_NAME || exit 1

# 4. PYTHONPATH 설정
export PYTHONPATH=$(pwd):$PYTHONPATH
echo "   PYTHONPATH: $PYTHONPATH"

# 5. 의존성 설치
echo -e "\n${BLUE}📚 의존성 설치 확인...${NC}"
REQ_FILE="backend/requirements-backend.txt"
if [[ -f "$REQ_FILE" ]]; then
    pip install -r "$REQ_FILE" || exit 1
else
    echo -e "${RED}❌ requirements 파일이 없습니다: $REQ_FILE${NC}"
    exit 1
fi

# 6. 로그 디렉토리 생성
mkdir -p logs

# 7. FastAPI 서버 실행
echo -e "\n${BLUE}🚀 FastAPI 서버 시작...${NC}"
nohup uvicorn backend.api.main:app --host 0.0.0.0 --port 18000 --reload > logs/api.log 2>&1 &
API_PID=$!
echo $API_PID > .api.pid
echo "   ✅ FastAPI 실행 (PID: $API_PID)"

# 8. Celery 워커 실행
echo -e "\n${BLUE}⚙️ Celery 워커 시작...${NC}"
nohup celery -A backend.api.main.celery_app worker -l info > logs/celery.log 2>&1 &
CELERY_PID=$!
echo $CELERY_PID > .celery.pid
echo "   ✅ Celery 실행 (PID: $CELERY_PID)"

# 9. 상태 확인
sleep 5
echo -e "\n${BLUE}📊 서비스 상태 확인...${NC}"
curl -s http://localhost:18000/v1/health > /dev/null
if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✅ 백엔드 서비스 정상 작동 중${NC}"
else
    echo -e "${YELLOW}⚠️ FastAPI 서비스 응답이 없습니다. logs/api.log 확인 바랍니다.${NC}"
fi

# 10. 완료 메시지
echo -e "\n${GREEN}🎉 백엔드 서비스가 성공적으로 시작되었습니다.${NC}"
echo "   🔗 API 문서: http://localhost:18000/docs"
echo "   📁 로그 디렉토리: $(pwd)/logs"
