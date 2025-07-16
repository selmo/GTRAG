#!/bin/bash

echo "🚀 GTOne RAG 백엔드 시작 (Enhanced)"
echo "=================================="

# 공통 함수 로드 시도
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_SCRIPT="$SCRIPT_DIR/../../scripts/common.sh"

if [[ -f "$COMMON_SCRIPT" ]]; then
    source "$COMMON_SCRIPT"
    init_common
else
    # 공통 함수가 없는 경우 기본 함수들 정의
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'

    log_info() { echo -e "${BLUE}ℹ️ $1${NC}"; }
    log_success() { echo -e "${GREEN}✅ $1${NC}"; }
    log_warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }
    log_error() { echo -e "${RED}❌ $1${NC}"; }

    check_port() {
        local port=$1
        if lsof -i:$port > /dev/null 2>&1; then
            return 1  # 포트 사용 중
        else
            return 0  # 포트 사용 가능
        fi
    }

    wait_for_service() {
        local url=$1
        local timeout=${2:-30}
        local service_name=${3:-"Service"}

        log_info "$service_name 준비 대기 중..."

        for i in $(seq 1 $timeout); do
            if curl -s --connect-timeout 2 "$url" > /dev/null 2>&1; then
                log_success "$service_name 준비 완료 (${i}초)"
                return 0
            fi
            if [[ $((i % 10)) -eq 0 ]]; then
                echo "   대기 중... ${i}초 경과"
            else
                echo -n "."
            fi
            sleep 1
        done

        echo ""
        log_warning "$service_name 준비 시간 초과"
        return 1
    }
fi

START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
log_info "시작 시간: $START_TIME"

# 1. 프로젝트 루트 찾기 (개선된 로직)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log_info "스크립트 위치: $SCRIPT_DIR"

# 프로젝트 루트 찾기 함수
find_project_root() {
    local current_dir="$1"
    local max_depth=5
    local depth=0

    while [[ $depth -lt $max_depth ]]; do
        # 프로젝트 루트 판별 조건들
        if [[ -f "$current_dir/backend/api/main.py" ]] || \
           [[ -f "$current_dir/backend/requirements.txt" ]] || \
           [[ -f "$current_dir/backend/requirements-backend.txt" ]] || \
           [[ -d "$current_dir/backend" && -d "$current_dir/frontend" ]]; then
            echo "$current_dir"
            return 0
        fi

        # 한 단계 위로 이동
        current_dir="$(dirname "$current_dir")"
        depth=$((depth + 1))

        # 루트 디렉토리에 도달한 경우 중단
        if [[ "$current_dir" == "/" ]]; then
            break
        fi
    done

    return 1
}

# 프로젝트 루트 찾기 시도
if PROJECT_ROOT=$(find_project_root "$SCRIPT_DIR"); then
    log_success "프로젝트 루트 발견: $PROJECT_ROOT"
elif PROJECT_ROOT=$(find_project_root "$(pwd)"); then
    log_success "프로젝트 루트 발견: $PROJECT_ROOT"
else
    log_error "프로젝트 루트를 찾을 수 없습니다."
    echo "다음 중 하나가 포함된 디렉토리에서 실행하세요:"
    echo "  - backend/api/main.py"
    echo "  - backend/requirements-backend.txt"
    echo "  - backend/ 및 frontend/ 디렉토리"
    echo ""
    echo "현재 디렉토리에서 강제로 실행하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        PROJECT_ROOT="$(pwd)"
        log_warning "현재 디렉토리를 프로젝트 루트로 설정: $PROJECT_ROOT"
    else
        exit 1
    fi
fi

cd "$PROJECT_ROOT" || {
    log_error "프로젝트 루트로 이동할 수 없습니다: $PROJECT_ROOT"
    exit 1
}

log_info "프로젝트 루트: $(pwd)"

# 2. 환경변수 로드
log_info "환경변수 설정..."

# .env 파일 로드 시도
ENV_FILES=(".env" "../.env" "backend/.env")
ENV_LOADED=false

for env_file in "${ENV_FILES[@]}"; do
    if [[ -f "$env_file" ]]; then
        set -a
        source "$env_file"
        set +a
        log_success "환경 설정 로드: $env_file"
        ENV_LOADED=true
        break
    fi
done

if [[ $ENV_LOADED == false ]]; then
    log_warning "환경 설정 파일을 찾을 수 없습니다. 기본값 사용"
fi

# 기본 환경변수 설정
export API_PORT=${API_PORT:-18000}
export API_HOST=${API_HOST:-"0.0.0.0"}
export QDRANT_PORT=${QDRANT_PORT:-6333}
export REDIS_PORT=${REDIS_PORT:-6379}
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"
export LOG_LEVEL=${LOG_LEVEL:-"INFO"}

log_info "환경변수 설정 완료"
echo "   API_PORT: $API_PORT"
echo "   QDRANT_PORT: $QDRANT_PORT"
echo "   REDIS_PORT: $REDIS_PORT"
echo "   PYTHONPATH: $PYTHONPATH"

# 3. 필수 도구 확인
log_info "필수 도구 확인..."

# Python 확인
if ! command -v python &> /dev/null; then
    log_error "Python이 설치되지 않았습니다."
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1)
log_success "Python 확인: $PYTHON_VERSION"

# Conda 환경 확인
if ! command -v conda &> /dev/null; then
    log_error "Conda가 설치되지 않았습니다."
    echo "   설치 방법: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

log_success "Conda 버전: $(conda --version)"

# 4. Conda 환경 설정
CONDA_ENV_NAME="GTRAG"

log_info "Conda 환경 설정..."

if conda env list | grep -q "^$CONDA_ENV_NAME "; then
    log_success "환경 '$CONDA_ENV_NAME' 존재"
else
    log_warning "환경 '$CONDA_ENV_NAME' 없음. 생성 중..."
    conda create -n $CONDA_ENV_NAME python=3.11 -y || {
        log_error "Conda 환경 생성 실패"
        exit 1
    }
    log_success "환경 '$CONDA_ENV_NAME' 생성 완료"
fi

# 5. Conda 환경 활성화
log_info "Conda 환경 활성화..."

# Conda 초기화
CONDA_BASE=$(conda info --base)
if [[ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]]; then
    source "$CONDA_BASE/etc/profile.d/conda.sh"
else
    # 대안 방법
    eval "$(conda shell.bash hook)" 2>/dev/null || {
        log_error "Conda 초기화 실패"
        exit 1
    }
fi

conda activate $CONDA_ENV_NAME || {
    log_error "Conda 환경 활성화 실패"
    exit 1
}

log_success "Conda 환경 '$CONDA_ENV_NAME' 활성화됨"
echo "   현재 Python: $(which python)"

# 6. 의존성 서비스 확인
log_info "의존성 서비스 확인..."

# Qdrant 확인
echo -n "   Qdrant 서버 확인... "
if curl -s --connect-timeout 3 "http://localhost:$QDRANT_PORT/health" > /dev/null 2>&1; then
    log_success "연결됨"
else
    log_warning "연결 실패"
    echo "   Qdrant가 준비되지 않았습니다. 계속하시겠습니까? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "   인프라를 먼저 시작하세요: cd infrastructure && ./scripts/start_infra.sh"
        exit 1
    fi
fi

# Redis 확인
echo -n "   Redis 서버 확인... "
if command -v redis-cli &> /dev/null; then
    if redis-cli -h localhost -p $REDIS_PORT ping > /dev/null 2>&1; then
        log_success "연결됨"
    else
        log_warning "연결 실패"
        echo "   Redis가 준비되지 않았습니다. 계속하시겠습니까? (y/n)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            echo "   인프라를 먼저 시작하세요: cd infrastructure && ./scripts/start_infra.sh"
            exit 1
        fi
    fi
else
    log_warning "redis-cli 없음 (Docker 컨테이너 확인)"
    if docker ps --format "{{.Names}}" | grep -q "redis"; then
        log_success "Redis 컨테이너 실행 중"
    else
        log_warning "Redis 컨테이너가 실행되지 않음"
    fi
fi

# 7. 포트 충돌 확인
log_info "포트 충돌 확인..."

if ! check_port $API_PORT; then
    log_warning "포트 $API_PORT이 사용 중입니다."

    # 사용 중인 프로세스 정보
    process_info=$(lsof -i:$API_PORT | tail -n +2)
    if [[ -n "$process_info" ]]; then
        echo "   사용 중인 프로세스:"
        echo "$process_info" | while read line; do
            echo "      $line"
        done
    fi

    echo "   기존 프로세스를 종료하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "포트 $API_PORT 프로세스 종료 중..."
        lsof -ti:$API_PORT | xargs kill -9 2>/dev/null
        sleep 2

        if check_port $API_PORT; then
            log_success "포트 $API_PORT 정리 완료"
        else
            log_error "포트 정리 실패"
            exit 1
        fi
    else
        log_error "포트 충돌로 시작할 수 없습니다."
        exit 1
    fi
else
    log_success "포트 $API_PORT 사용 가능"
fi

# 8. 의존성 설치
log_info "Python 패키지 설치 확인..."
log_info "현재 작업 디렉토리: $(pwd)"

# requirements 파일 찾기
REQ_FILES=(
    "backend/requirements-backend.txt"
    "backend/requirements.txt"
    "requirements.txt"
)

REQ_FILE=""
log_info "Requirements 파일 탐색 중..."
for req_file in "${REQ_FILES[@]}"; do
    if [[ -f "$req_file" ]]; then
        REQ_FILE="$req_file"
        log_success "Requirements 파일 발견: $req_file"
        break
    fi
done

if [[ -z "$REQ_FILE" ]]; then
    log_error "requirements 파일을 찾을 수 없습니다."
    echo ""
    echo "현재 디렉토리 구조:"
    echo "  현재 위치: $(pwd)"
    if [[ -d "backend" ]]; then
        echo "  backend 디렉토리 내용:"
        ls -la backend/ | grep -E "(requirements|\.txt)" || echo "    requirements 파일 없음"
    else
        echo "  ❌ backend 디렉토리가 없습니다"
    fi
    echo ""
    echo "찾고 있는 파일들:"
    for req_file in "${REQ_FILES[@]}"; do
        echo "  - $req_file"
    done
    echo ""
    echo "올바른 프로젝트 루트에서 실행하고 있는지 확인하세요."
    exit 1
fi

log_info "Requirements 파일: $REQ_FILE"

# 핵심 패키지 확인
missing_packages=()
required_packages=("fastapi" "uvicorn" "celery" "redis" "requests")

for package in "${required_packages[@]}"; do
    if ! python -c "import $package" &> /dev/null; then
        missing_packages+=("$package")
    fi
done

if [[ ${#missing_packages[@]} -gt 0 ]]; then
    log_warning "누락된 패키지: ${missing_packages[*]}"
    log_info "패키지 설치 중..."

    pip install -r "$REQ_FILE" || {
        log_error "패키지 설치 실패"
        echo "수동 설치를 시도하세요:"
        echo "  conda activate $CONDA_ENV_NAME"
        echo "  pip install -r $REQ_FILE"
        exit 1
    }

    log_success "패키지 설치 완료"
else
    log_success "모든 필수 패키지가 설치되어 있습니다"
fi

# FastAPI 및 Celery 버전 확인
echo "   핵심 패키지 버전:"
echo "   - FastAPI: $(python -c "import fastapi; print(fastapi.__version__)" 2>/dev/null || echo "설치되지 않음")"
echo "   - Uvicorn: $(python -c "import uvicorn; print(uvicorn.__version__)" 2>/dev/null || echo "설치되지 않음")"
echo "   - Celery: $(python -c "import celery; print(celery.__version__)" 2>/dev/null || echo "설치되지 않음")"

# 9. 로그 디렉토리 생성
log_info "로그 디렉토리 설정..."
mkdir -p logs backend/logs
log_success "로그 디렉토리 준비 완료"

# 10. 기존 프로세스 정리
log_info "기존 백엔드 프로세스 정리..."

# PID 파일 확인 및 정리
PID_FILES=(".api.pid" "backend/.api.pid" ".celery.pid" "backend/.celery.pid")
for pid_file in "${PID_FILES[@]}"; do
    if [[ -f "$pid_file" ]]; then
        PID=$(cat "$pid_file")
        if kill -0 "$PID" 2>/dev/null; then
            log_info "기존 프로세스 종료: PID $PID"
            kill "$PID" 2>/dev/null
            sleep 2
            if kill -0 "$PID" 2>/dev/null; then
                kill -9 "$PID" 2>/dev/null
            fi
        fi
        rm -f "$pid_file"
    fi
done

# 11. FastAPI 서버 시작
log_info "FastAPI 서버 시작..."

# Uvicorn 명령어 구성
UVICORN_CMD="uvicorn backend.api.main:app"
UVICORN_ARGS="--host $API_HOST --port $API_PORT --reload"

# 로그 설정
if [[ "$LOG_LEVEL" == "DEBUG" ]]; then
    UVICORN_ARGS="$UVICORN_ARGS --log-level debug"
else
    UVICORN_ARGS="$UVICORN_ARGS --log-level info"
fi

# 백그라운드에서 실행
nohup $UVICORN_CMD $UVICORN_ARGS > logs/api.log 2>&1 &
API_PID=$!
echo $API_PID > .api.pid

log_success "FastAPI 서버 시작됨 (PID: $API_PID)"
echo "   명령어: $UVICORN_CMD $UVICORN_ARGS"
echo "   로그 파일: logs/api.log"

# 12. Celery 워커 시작
log_info "Celery 워커 시작..."

# Celery 명령어 구성
CELERY_CMD="celery -A backend.api.main.celery_app worker"
CELERY_ARGS="--loglevel=info --concurrency=2"

# 백그라운드에서 실행
nohup $CELERY_CMD $CELERY_ARGS > logs/celery.log 2>&1 &
CELERY_PID=$!
echo $CELERY_PID > .celery.pid

log_success "Celery 워커 시작됨 (PID: $CELERY_PID)"
echo "   명령어: $CELERY_CMD $CELERY_ARGS"
echo "   로그 파일: logs/celery.log"

# 13. 서비스 준비 대기
log_info "백엔드 서비스 준비 대기..."

# FastAPI 서버 준비 대기
if wait_for_service "http://localhost:$API_PORT/docs" 30 "FastAPI"; then
    log_success "FastAPI 서버 준비 완료"
else
    log_warning "FastAPI 서버 준비 시간 초과"
    echo "   로그 확인: tail -f logs/api.log"
fi

# 헬스체크 엔드포인트 확인
echo -n "   헬스체크 엔드포인트 확인... "
if curl -s "http://localhost:$API_PORT/v1/health" > /dev/null 2>&1; then
    log_success "정상"
else
    log_warning "응답 없음"
fi

# 14. 최종 상태 확인
log_info "최종 백엔드 상태 확인..."

# 프로세스 상태
if [[ -f ".api.pid" ]]; then
    API_PID=$(cat ".api.pid")
    if kill -0 "$API_PID" 2>/dev/null; then
        log_success "FastAPI 프로세스 실행 중 (PID: $API_PID)"
    else
        log_error "FastAPI 프로세스 실행 실패"
    fi
fi

if [[ -f ".celery.pid" ]]; then
    CELERY_PID=$(cat ".celery.pid")
    if kill -0 "$CELERY_PID" 2>/dev/null; then
        log_success "Celery 프로세스 실행 중 (PID: $CELERY_PID)"
    else
        log_error "Celery 프로세스 실행 실패"
    fi
fi

# 포트 상태
echo -n "   포트 $API_PORT 상태: "
if lsof -i:$API_PORT > /dev/null 2>&1; then
    log_success "사용 중"
else
    log_error "사용되지 않음"
fi

# 15. 완료 메시지
log_success "GTOne RAG 백엔드 서비스 시작 완료!"

END_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "시작 시간: $START_TIME"
echo "완료 시간: $END_TIME"

echo -e "\n${YELLOW}📌 백엔드 서비스 정보:${NC}"
echo -e "   🔗 API 문서:        http://localhost:$API_PORT/docs"
echo -e "   📊 헬스체크:        http://localhost:$API_PORT/v1/health"
echo -e "   📊 메트릭스:        http://localhost:$API_PORT/metrics"
echo -e "   🐍 Conda 환경:     $CONDA_ENV_NAME"

echo -e "\n${YELLOW}📋 유용한 명령어:${NC}"
echo -e "   📊 로그 확인:"
echo -e "      - FastAPI:      tail -f logs/api.log"
echo -e "      - Celery:       tail -f logs/celery.log"
echo -e "   🛑 서비스 종료:     ./backend/scripts/stop_backend.sh"
echo -e "   🔄 환경 재활성화:   conda activate $CONDA_ENV_NAME"

echo -e "\n${YELLOW}💡 다음 단계:${NC}"
echo -e "   1. API 문서 확인:   http://localhost:$API_PORT/docs"
echo -e "   2. 헬스체크 테스트: curl http://localhost:$API_PORT/v1/health"
echo -e "   3. 프론트엔드 시작: cd frontend && ./scripts/start_frontend.sh"

echo -e "\n${GREEN}✨ 백엔드 서비스 실행 중! ✨${NC}"

# 백엔드 정보 저장
cat > .backend_info << EOF
# GTOne RAG Backend Service Info
# Generated: $(date '+%Y-%m-%d %H:%M:%S')
API_PID=$API_PID
CELERY_PID=$CELERY_PID
API_PORT=$API_PORT
CONDA_ENV=$CONDA_ENV_NAME
API_URL=http://localhost:$API_PORT
PYTHON_PATH=$(which python)
PROJECT_ROOT=$PROJECT_ROOT
START_TIME=$START_TIME
END_TIME=$END_TIME
EOF

log_info "백엔드 정보가 .backend_info에 저장되었습니다."