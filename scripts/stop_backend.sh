#!/bin/bash

# ==================================================
# GTOne RAG – 백엔드 서비스 종료 스크립트
# (backend/scripts/stop_backend.sh 위치에서 실행)
# ==================================================

set -euo pipefail

# ---------- 색상 정의 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---------- 로그 함수 ----------
log_info() { echo -e "${BLUE}ℹ️ $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# ---------- 배너 ----------
echo -e "${RED}🛑 GTOne RAG - 백엔드 서비스 종료${NC}"
echo "================================"

STOP_START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
log_info "종료 시작 시간: $STOP_START_TIME"

# ---------- 프로젝트 루트 찾기 (개선된 로직) ----------
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
    log_warning "자동 감지 실패. 수동 지정을 시도합니다."
    echo "다음 중 하나가 포함된 디렉토리에서 실행하세요:"
    echo "  - backend/api/main.py"
    echo "  - backend/requirements-backend.txt"
    echo "  - backend/ 및 frontend/ 디렉토리"
    echo ""
    echo "현재 위치에서 백엔드 프로세스만 종료하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        PROJECT_ROOT="$(pwd)"
        log_warning "현재 디렉토리를 프로젝트 루트로 설정: $PROJECT_ROOT"
    else
        exit 1
    fi
fi

cd "$PROJECT_ROOT" || {
    log_error "프로젝트 루트로 이동 실패: $PROJECT_ROOT"
    exit 1
}

log_info "작업 디렉토리: $(pwd)"

# ---------- 구조 확인 (유연한 검증) ----------
backend_found=false

if [[ -f "backend/api/main.py" ]]; then
    log_success "backend/api/main.py 확인"
    backend_found=true
elif [[ -d "backend" ]]; then
    log_warning "backend 디렉토리는 있지만 main.py를 찾을 수 없습니다"
    echo "   백엔드 프로세스 정리는 계속 진행됩니다."
    backend_found=true
else
    log_warning "backend 디렉토리가 없습니다"
    echo "   일반적인 백엔드 프로세스 정리만 수행됩니다."
fi

# ---------- 함수: PID 기반 서비스 종료 ----------
stop_service() {
    local pidfile=$1
    local service_name=$2
    local timeout=${3:-10}

    # 여러 위치에서 PID 파일 찾기
    local found_pidfile=""
    for location in "$pidfile" "backend/$pidfile" "./$pidfile"; do
        if [[ -f "$location" ]]; then
            found_pidfile="$location"
            break
        fi
    done

    if [[ -n "$found_pidfile" ]]; then
        local PID=$(cat "$found_pidfile")
        echo -n "   $service_name (PID: $PID) 종료 중... "

        if kill -0 "$PID" 2>/dev/null; then
            kill -TERM "$PID" 2>/dev/null  # 정상 종료 시도
            for _ in $(seq 1 $timeout); do
                if ! kill -0 "$PID" 2>/dev/null; then
                    echo -e "${GREEN}완료${NC}"
                    break
                fi
                sleep 1
            done
            if kill -0 "$PID" 2>/dev/null; then
                echo -e "${YELLOW}강제 종료${NC}"
                kill -9 "$PID" 2>/dev/null
            fi
        else
            echo -e "${YELLOW}이미 종료됨${NC}"
        fi
        rm -f "$found_pidfile"
    else
        echo "   $service_name PID 파일 없음"
    fi
}

# ---------- 서비스 종료 ----------
log_info "백엔드 서비스 종료 중..."

stop_service ".celery.pid" "Celery 워커" 15
stop_service ".api.pid" "FastAPI 서버" 10

# ---------- 포트 기반 정리 ----------
cleanup_port() {
    local port=$1
    local name=$2
    echo -n "   포트 $port ($name) 확인... "

    if command -v lsof &> /dev/null && lsof -i:$port > /dev/null 2>&1; then
        echo -e "${YELLOW}사용 중${NC}"
        echo "      프로세스 정리 중..."
        local PIDS=$(lsof -ti:$port 2>/dev/null || true)
        for PID in $PIDS; do
            if [[ -n "$PID" ]]; then
                echo "      PID $PID 종료 중..."

                # 프로세스 정보 확인
                local process_name=$(ps -p $PID -o comm= 2>/dev/null || echo "unknown")

                # Docker 관련 프로세스인지 확인
                if [[ "$process_name" == *"docker"* ]] || [[ "$process_name" == *"containerd"* ]]; then
                    log_warning "      Docker 관련 프로세스 - 건너뜀 (PID: $PID)"
                    continue
                fi

                kill -TERM "$PID" 2>/dev/null || true
                sleep 2
                if kill -0 "$PID" 2>/dev/null; then
                    echo "      PID $PID 강제 종료..."
                    kill -9 "$PID" 2>/dev/null || true
                fi
            fi
        done
    else
        echo -e "${GREEN}정리됨${NC}"
    fi
}

# 기본 백엔드 포트들 정리
log_info "포트 상태 확인 및 정리..."
cleanup_port 18000 "FastAPI"
cleanup_port 8000 "대체 FastAPI"

# ---------- 프로세스 패턴 기반 추가 정리 ----------
kill_if_exists() {
    local pattern=$1
    local desc=$2
    echo -n "   $desc 프로세스 확인... "

    if command -v pgrep &> /dev/null; then
        local PIDS=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [[ -n "$PIDS" ]]; then
            echo -e "${YELLOW}발견됨${NC}"
            for PID in $PIDS; do
                # 프로세스가 여전히 존재하는지 확인
                if kill -0 "$PID" 2>/dev/null; then
                    echo "      $desc PID $PID 종료..."
                    kill -TERM "$PID" 2>/dev/null || true
                    sleep 2
                    if kill -0 "$PID" 2>/dev/null; then
                        kill -9 "$PID" 2>/dev/null || true
                    fi
                fi
            done
        else
            echo -e "${GREEN}없음${NC}"
        fi
    else
        echo -e "${YELLOW}pgrep 없음 - 건너뜀${NC}"
    fi
}

# 다양한 백엔드 프로세스 패턴 정리
log_info "프로세스 패턴 기반 정리..."
kill_if_exists "uvicorn.*main" "Uvicorn"
kill_if_exists "celery.*worker" "Celery"
kill_if_exists "fastapi" "FastAPI"
kill_if_exists "python.*api" "Python API"

# ---------- 임시 파일 정리 ----------
log_info "임시 파일 정리 중..."

# PID 파일들 정리
for pidfile in .api.pid .celery.pid backend/.api.pid backend/.celery.pid; do
    if [[ -f "$pidfile" ]]; then
        echo "   $pidfile 삭제..."
        rm -f "$pidfile"
    fi
done

# 백엔드 정보 파일 정리
for info_file in .backend_info backend/.backend_info; do
    if [[ -f "$info_file" ]]; then
        echo "   $info_file 삭제..."
        rm -f "$info_file"
    fi
done

# ---------- 로그 정리 옵션 ----------
log_info "로그 정리 옵션..."

log_dirs=("logs" "backend/logs")
total_logs=0

for log_dir in "${log_dirs[@]}"; do
    if [[ -d "$log_dir" ]]; then
        log_count=$(find "$log_dir" -name "*.log" 2>/dev/null | wc -l)
        total_logs=$((total_logs + log_count))
        if [[ $log_count -gt 0 ]]; then
            echo "   $log_dir: $log_count 개 로그 파일"
        fi
    fi
done

if [[ $total_logs -gt 0 ]]; then
    echo "   총 $total_logs 개의 로그 파일이 있습니다. 삭제하시겠습니까? (y/n)"
    read -r resp
    if [[ "$resp" =~ ^[Yy]$ ]]; then
        for log_dir in "${log_dirs[@]}"; do
            if [[ -d "$log_dir" ]]; then
                rm -f "$log_dir"/*.log 2>/dev/null || true
            fi
        done
        log_success "로그 삭제 완료"
    else
        log_info "로그 보존"
    fi
else
    log_success "정리할 로그 파일 없음"
fi

# ---------- 최종 상태 확인 ----------
log_info "최종 상태 확인..."

all_ports_clear=true

# 포트 상태 확인
check_ports=(18000 8000)
for port in "${check_ports[@]}"; do
    echo -n "   포트 $port: "
    if command -v lsof &> /dev/null && lsof -i:$port > /dev/null 2>&1; then
        echo -e "${RED}여전히 사용 중${NC}"
        all_ports_clear=false
        # 사용 중인 프로세스 정보 표시
        process_info=$(lsof -i:$port 2>/dev/null | tail -n +2 | head -1)
        if [[ -n "$process_info" ]]; then
            echo "      $process_info"
        fi
    else
        echo -e "${GREEN}정리됨${NC}"
    fi
done

# Conda 환경 확인
echo -n "   Conda 환경: "
if [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
    echo -e "${BLUE}$CONDA_DEFAULT_ENV 활성화됨${NC}"
else
    echo -e "${GREEN}기본 환경${NC}"
fi

# ---------- 완료 메시지 ----------
STOP_END_TIME=$(date '+%Y-%m-%d %H:%M:%S')

if $all_ports_clear; then
    log_success "GTOne RAG 백엔드 서비스가 완전히 종료되었습니다!"
else
    log_warning "일부 포트가 여전히 사용 중입니다."
    echo -e "   수동 정리: ${YELLOW}sudo lsof -ti:18000 | xargs sudo kill -9${NC}"
fi

echo -e "\n${BLUE}📊 종료 요약:${NC}"
echo "   종료 시작: $STOP_START_TIME"
echo "   종료 완료: $STOP_END_TIME"
echo "   프로젝트 루트: $PROJECT_ROOT"

echo -e "\n${YELLOW}💡 참고 사항:${NC}"
if [[ $backend_found == true ]]; then
    echo -e "   🔄 다시 시작: ${GREEN}./scripts/start_backend.sh${NC}"
    if [[ -f "scripts/start_backend.sh" ]]; then
        echo -e "   📍 시작 스크립트: scripts/start_backend.sh"
    else
        echo -e "   📍 시작 스크립트를 찾을 수 없습니다"
    fi
else
    echo -e "   ⚠️  백엔드 구조를 확인한 후 수동으로 시작하세요"
fi

echo -e "\n${YELLOW}🔧 문제 해결:${NC}"
echo -e "   - 포트 충돌: ${YELLOW}lsof -i:18000${NC}"
echo -e "   - 프로세스 확인: ${YELLOW}ps aux | grep python${NC}"
echo -e "   - 로그 확인: ${YELLOW}tail -f logs/*.log${NC}"

echo -e "\n${GREEN}✅ 백엔드 서비스 종료 완료!${NC}"

exit 0