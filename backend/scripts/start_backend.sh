#!/bin/bash

echo "🔧 GTOne RAG - 백엔드 서비스 시작 (Conda 환경)"
echo "=============================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 시작 시간 기록
START_TIME=$(date)
echo "시작 시간: $START_TIME"

# 1. Conda 환경 확인
echo -e "\n${BLUE}🐍 Conda 환경 확인...${NC}"

if ! command -v conda &> /dev/null; then
    echo -e "${RED}❌ Conda가 설치되지 않았습니다.${NC}"
    echo "   Conda 설치 방법:"
    echo "   - Anaconda: https://www.anaconda.com/products/distribution"
    echo "   - Miniconda: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo -e "${GREEN}✅ Conda 버전: $(conda --version)${NC}"

# 현재 디렉토리가 backend인지 확인
if [[ ! -f "backend/api/main.py" ]]; then
    echo -e "${RED}❌ 프로젝트 디렉토리에서 실행해주세요.${NC}"
    echo "현재 위치: $(pwd)"
    exit 1
fi

echo -e "${GREEN}✅ 백엔드 디렉토리 확인됨${NC}"

# 2. GTRAG Conda 환경 확인/생성
echo -e "\n${BLUE}📦 GTRAG Conda 환경 설정...${NC}"

CONDA_ENV_NAME="GTRAG"

if conda env list | grep -q "^$CONDA_ENV_NAME "; then
    echo -e "${GREEN}✅ $CONDA_ENV_NAME 환경이 이미 존재합니다.${NC}"
else
    echo -e "${YELLOW}⚠️  $CONDA_ENV_NAME 환경이 없습니다. 생성 중...${NC}"

    # Python 3.11로 환경 생성
    conda create -n $CONDA_ENV_NAME python=3.11 -y

    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✅ $CONDA_ENV_NAME 환경이 성공적으로 생성되었습니다.${NC}"
    else
        echo -e "${RED}❌ $CONDA_ENV_NAME 환경 생성에 실패했습니다.${NC}"
        exit 1
    fi
fi

# 3. Conda 환경 활성화
echo -e "\n${BLUE}🔧 $CONDA_ENV_NAME 환경 활성화...${NC}"

# Conda 초기화 (필요한 경우)
if [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
elif [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [[ -f "/opt/anaconda3/etc/profile.d/conda.sh" ]]; then
    source "/opt/anaconda3/etc/profile.d/conda.sh"
elif [[ -f "/opt/miniconda3/etc/profile.d/conda.sh" ]]; then
    source "/opt/miniconda3/etc/profile.d/conda.sh"
else
    # conda init 시도
    eval "$(conda shell.bash hook)"
fi

# GTRAG-Backend 환경 활성화
conda activate $CONDA_ENV_NAME

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✅ $CONDA_ENV_NAME 환경이 활성화되었습니다.${NC}"
    echo "   현재 Python 경로: $(which python)"
    echo "   현재 Python 버전: $(python --version)"
else
    echo -e "${RED}❌ $CONDA_ENV_NAME 환경 활성화에 실패했습니다.${NC}"
    exit 1
fi

# 4. 의존성 설치
echo -e "\n${BLUE}📚 Python 패키지 설치 확인...${NC}"

# requirements.txt 파일 확인
if [[ -f "backend/requirements-backend.txt" ]]; then
    REQ_FILE="backend/requirements-backend.txt"
elif [[ -f "backend/requirements.txt" ]]; then
    REQ_FILE="backend/requirements.txt"
else
    echo -e "${RED}❌ requirements 파일을 찾을 수 없습니다.${NC}"
    exit 1
fi

echo "사용할 requirements 파일: $REQ_FILE"

# 주요 패키지 설치 상태 확인
echo "주요 백엔드 패키지 설치 상태 확인 중..."

missing_packages=()

# 필수 패키지 목록
required_packages=(
    "fastapi"
    "uvicorn"
    "celery"
    "redis"
    "qdrant_client"
    "sentence_transformers"
    "requests"
)

for package in "${required_packages[@]}"; do
    if ! python -c "import ${package//-/_}" &> /dev/null; then
        missing_packages+=("$package")
    fi
done

# 누락된 패키지가 있으면 설치
if [[ ${#missing_packages[@]} -ne 0 ]]; then
    echo -e "${YELLOW}⚠️  누락된 패키지가 있습니다. 설치 중...${NC}"
    echo "누락된 패키지: ${missing_packages[*]}"

    pip install -r $REQ_FILE

    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✅ 패키지 설치가 완료되었습니다.${NC}"
    else
        echo -e "${RED}❌ 패키지 설치에 실패했습니다.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ 모든 필수 패키지가 설치되어 있습니다.${NC}"
fi

# 5. 환경변수 설정
echo -e "\n${BLUE}🔧 환경변수 설정...${NC}"

# .env 파일 확인
if [[ -f ".env" ]]; then
    source .env
    echo -e "${GREEN}✅ .env 파일 로드됨${NC}"
else
    echo -e "${YELLOW}⚠️  .env 파일이 없습니다. 기본값 사용${NC}"
fi

# 기본 환경변수 설정
export PYTHONPATH=$(pwd):${PYTHONPATH}
export QDRANT_HOST=${QDRANT_HOST:-"qdrant"}
export QDRANT_PORT=${QDRANT_PORT:-"6333"}
export OLLAMA_HOST=${OLLAMA_HOST:-"http://172.16.15.112:11434"}
export CELERY_BROKER_URL=${CELERY_BROKER_URL:-"redis://localhost:6379/0"}
export CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-"redis://localhost:6379/0"}

echo "   Conda 환경: $CONDA_ENV_NAME"
echo "   PYTHONPATH: $PYTHONPATH"
echo "   QDRANT_HOST: $QDRANT_HOST:$QDRANT_PORT"
echo "   OLLAMA_HOST: $OLLAMA_HOST"
echo "   CELERY_BROKER: $CELERY_BROKER_URL"

# 6. 서비스 의존성 확인
echo -e "\n${BLUE}🔗 서비스 의존성 확인...${NC}"

# Qdrant 확인
echo -n "   Qdrant 연결 테스트... "
if curl -s --connect-timeout 3 "$QDRANT_HOST:$QDRANT_PORT/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 연결됨${NC}"
else
    echo -e "${RED}❌ 연결 실패${NC}"
    echo -e "${YELLOW}   Qdrant가 실행 중인지 확인하세요: cd ../infrastructure && ./scripts/start_infra.sh${NC}"
fi

# Redis 확인
echo -n "   Redis 연결 테스트... "
if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 연결됨${NC}"
elif command -v docker &> /dev/null && docker exec redis-service redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 연결됨 (Docker)${NC}"
else
    echo -e "${RED}❌ 연결 실패${NC}"
    echo -e "${YELLOW}   Redis가 실행 중인지 확인하세요: cd ../infrastructure && ./scripts/start_infra.sh${NC}"
fi

# Ollama 확인 (선택적)
echo -n "   Ollama 연결 테스트... "
if curl -s --connect-timeout 5 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 연결됨${NC}"
else
    echo -e "${YELLOW}⚠️  연결 실패 (LLM 기능 제한됨)${NC}"
fi

# 7. 기존 프로세스 정리
echo -e "\n${BLUE}🧹 기존 프로세스 정리...${NC}"

# PID 파일들 확인
for pidfile in .api.pid .celery.pid; do
    if [[ -f "$pidfile" ]]; then
        PID=$(cat "$pidfile")
        if kill -0 "$PID" 2>/dev/null; then
            echo "   기존 프로세스 종료: $pidfile (PID: $PID)"
            kill "$PID" 2>/dev/null
            sleep 2
        fi
        rm "$pidfile"
    fi
done

# 포트 충돌 확인
check_port() {
    local port=$1
    local service=$2

    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "${YELLOW}   포트 $port ($service)가 사용 중입니다.${NC}"
        echo "   기존 프로세스를 종료하시겠습니까? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            lsof -ti:$port | xargs kill -9 2>/dev/null
            sleep 2
        else
            return 1
        fi
    fi
    return 0
}

check_port 18000 "API 서버" || exit 1

# 8. 로그 디렉토리 생성
mkdir -p logs

# 9. 서비스 시작
echo -e "\n${BLUE}🚀 백엔드 서비스 시작...${NC}"

export PYTHONPATH=$(pwd):$PYTHONPATH

# FastAPI 서버 시작
echo "   1. FastAPI 서버 시작 중..."
echo "      Conda 환경: $CONDA_ENV_NAME"
echo "      명령어: uvicorn api.main:app --host 0.0.0.0 --port 18000 --reload"

nohup uvicorn api.main:app --host 0.0.0.0 --port 18000 --reload > logs/api.log 2>&1 &
API_PID=$!
echo "      PID: $API_PID"
echo $API_PID > .api.pid

# Celery Worker 시작
echo "   2. Celery 워커 시작 중..."
echo "      명령어: celery -A api.main.celery_app worker -l info"

nohup celery -A api.main.celery_app worker -l info > logs/celery.log 2>&1 &
CELERY_PID=$!
echo "      PID: $CELERY_PID"
echo $CELERY_PID > .celery.pid

# 10. 서비스 준비 대기
echo -e "\n${BLUE}⏳ 서비스 준비 대기...${NC}"
echo -n "대기 중"

max_attempts=24  # 2분 대기
attempt=0
api_ready=false

while [[ $attempt -lt $max_attempts ]] && [[ $api_ready == false ]]; do
    sleep 5
    echo -n "."
    attempt=$((attempt + 1))

    # API 서버 상태 확인
    if curl -s http://localhost:18000/docs > /dev/null 2>&1; then
        api_ready=true
        echo -e "\n${GREEN}✅ API 서버 준비 완료!${NC}"
        break
    fi

    # 주기적 상태 출력
    if [[ $((attempt % 6)) -eq 0 ]]; then
        echo -e "\n   진행 중... ($((attempt * 5))초 경과)"
        echo -n "   계속 대기 중"
    fi
done

if [[ $api_ready == false ]]; then
    echo -e "\n${YELLOW}⚠️  API 서버 시작이 지연되고 있습니다.${NC}"
    echo "로그를 확인해보세요: tail -f logs/api.log"
fi

# 11. 최종 상태 확인
echo -e "\n${BLUE}📊 백엔드 서비스 상태 확인...${NC}"

# 프로세스 상태
echo "   프로세스 상태:"
for pidfile in .api.pid .celery.pid; do
    if [[ -f "$pidfile" ]]; then
        PID=$(cat "$pidfile")
        service_name=$(basename "$pidfile" .pid)
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "   - $service_name: ${GREEN}실행 중${NC} (PID: $PID)"
        else
            echo -e "   - $service_name: ${RED}실행 실패${NC}"
        fi
    fi
done

# API 엔드포인트 테스트
echo "   API 엔드포인트 테스트:"
endpoints=(
    "http://localhost:18000/docs:API 문서"
    "http://localhost:18000/v1/health:헬스체크"
)

for endpoint_info in "${endpoints[@]}"; do
    IFS=':' read -r url desc <<< "$endpoint_info"
    echo -n "   - $desc: "
    if curl -s "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 정상${NC}"
    else
        echo -e "${RED}❌ 실패${NC}"
    fi
done

# 12. 완료 메시지
echo -e "\n${GREEN}🎉 백엔드 서비스 시작 완료!${NC}"
echo -e "\n${YELLOW}📌 서비스 정보:${NC}"
echo -e "   🐍 Conda 환경: $CONDA_ENV_NAME"
echo -e "   🌐 API 문서: http://localhost:18000/docs"
echo -e "   📊 헬스체크: http://localhost:18000/v1/health"
echo -e "   📁 로그 디렉토리: $(pwd)/logs"

echo -e "\n${YELLOW}📋 유용한 명령어:${NC}"
echo -e "   📊 로그 확인:"
echo -e "      - API: tail -f logs/api.log"
echo -e "      - Celery: tail -f logs/celery.log"
echo -e "   🛑 서비스 종료: ./scripts/stop_backend.sh"
echo -e "   🔄 환경 재활성화: conda activate $CONDA_ENV_NAME"

echo -e "\n${YELLOW}💡 다음 단계:${NC}"
echo -e "   1. 프론트엔드 시작: cd ../frontend && ./scripts/start_frontend.sh"
echo -e "   2. 또는 전체 시스템: cd .. && ./scripts/start_all.sh"

echo -e "\n${GREEN}✨ 백엔드 서비스 실행 중! (Conda: $CONDA_ENV_NAME) ✨${NC}"

# 서비스 정보 저장
cat > .backend_info << EOF
# GTOne RAG Backend Service Info (Conda)
# Generated: $(date)
CONDA_ENV=$CONDA_ENV_NAME
API_PID=$API_PID
CELERY_PID=$CELERY_PID
API_URL=http://localhost:18000
PYTHON_PATH=$(which python)
PYTHONPATH=$PYTHONPATH
EOF