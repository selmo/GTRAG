#!/bin/bash

# ==================================================
# GTOne RAG - 전체 시스템 종료 스크립트
# 위치: ./scripts/stop_all.sh
# 프론트엔드 → 백엔드 → 인프라 순서로 자동 종료
# ==================================================

set -euo pipefail

# ---------- 색상 정의 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# ---------- 로그 함수 ----------
log_info() { echo -e "${BLUE}ℹ️ $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_step() { echo -e "${PURPLE}🛑 $1${NC}"; }

# ---------- 배너 ----------
echo -e "${CYAN}🛑 GTOne RAG - 전체 시스템 종료${NC}"
echo "====================================="

STOP_ALL_TIME=$(date '+%Y-%m-%d %H:%M:%S')
log_info "전체 종료 시간: $STOP_ALL_TIME"

# ---------- 프로젝트 루트 찾기 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log_info "스크립트 위치: $SCRIPT_DIR"

find_project_root() {
    local current_dir="$1"
    local max_depth=5
    local depth=0

    while [[ $depth -lt $max_depth ]]; do
        if [[ -d "$current_dir/backend" && -d "$current_dir/frontend" ]] || \
           [[ -f "$current_dir/backend/api/main.py" ]] || \
           [[ -d "$current_dir/scripts" ]]; then
            echo "$current_dir"
            return 0
        fi

        current_dir="$(dirname "$current_dir")"
        depth=$((depth + 1))

        if [[ "$current_dir" == "/" ]]; then
            break
        fi
    done

    return 1
}

if PROJECT_ROOT=$(find_project_root "$SCRIPT_DIR"); then
    log_success "프로젝트 루트 발견: $PROJECT_ROOT"
elif PROJECT_ROOT=$(find_project_root "$(pwd)"); then
    log_success "프로젝트 루트 발견: $PROJECT_ROOT"
else
    log_error "프로젝트 루트를 찾을 수 없습니다."
    exit 1
fi

cd "$PROJECT_ROOT" || {
    log_error "프로젝트 루트로 이동 실패: $PROJECT_ROOT"
    exit 1
}

log_info "작업 디렉토리: $(pwd)"

# ---------- 종료 모드 선택 ----------
echo -e "\n${YELLOW}🎯 종료 모드를 선택하세요:${NC}"
echo "   1) 자동 모드 (모든 입력을 자동으로 'y' 처리)"
echo "   2) 대화형 모드 (각 단계별 확인)"
echo "   3) 강제 모드 (즉시 모든 프로세스 강제 종료)"
echo "   4) 안전 모드 (스크립트 없이 직접 프로세스만 종료)"
echo "   q) 취소"
echo ""
read -p "선택 (1-4, q): " stop_mode

case $stop_mode in
    [1])
        log_info "자동 모드 선택 - 모든 확인을 자동으로 진행합니다"
        AUTO_MODE=true
        FORCE_MODE=false
        DIRECT_MODE=false
        ;;
    [2])
        log_info "대화형 모드 선택 - 각 단계별로 확인합니다"
        AUTO_MODE=false
        FORCE_MODE=false
        DIRECT_MODE=false
        ;;
    [3])
        log_info "강제 모드 선택 - 즉시 모든 프로세스를 강제 종료합니다"
        AUTO_MODE=true
        FORCE_MODE=true
        DIRECT_MODE=false
        ;;
    [4])
        log_info "안전 모드 선택 - 스크립트 없이 프로세스만 종료합니다"
        AUTO_MODE=true
        FORCE_MODE=false
        DIRECT_MODE=true
        ;;
    [Qq])
        log_info "종료 취소됨"
        exit 0
        ;;
    *)
        log_warning "잘못된 선택. 자동 모드로 진행합니다"
        AUTO_MODE=true
        FORCE_MODE=false
        DIRECT_MODE=false
        ;;
esac

# ---------- 환경변수 설정 ----------
if [[ "$AUTO_MODE" == true ]]; then
    export GTRAG_AUTO_MODE="true"
    export GTRAG_AUTO_CONFIRM="y"
    export GTRAG_SKIP_PROMPTS="true"
fi

if [[ "$FORCE_MODE" == true ]]; then
    export GTRAG_FORCE_MODE="true"
    export GTRAG_KILL_CONFLICTS="true"
fi

# ---------- 현재 실행 중인 서비스 확인 ----------
log_step "현재 실행 중인 GTOne RAG 서비스 확인..."

running_services=()

# 포트 기반 서비스 확인
main_ports=(8501 18000 6333 6379)
port_names=("Streamlit" "FastAPI" "Qdrant" "Redis")

for i in "${!main_ports[@]}"; do
    port=${main_ports[$i]}
    name=${port_names[$i]}

    if command -v lsof &> /dev/null && lsof -i:$port > /dev/null 2>&1; then
        echo "   - $name (포트 $port): 실행 중"
        running_services+=("$name:$port")
    else
        echo "   - $name (포트 $port): 정지됨"
    fi
done

# 프로세스 패턴 기반 확인
if command -v pgrep &> /dev/null; then
    patterns=("streamlit" "uvicorn.*main" "celery.*worker")
    pattern_names=("Streamlit" "FastAPI" "Celery")

    for i in "${!patterns[@]}"; do
        pattern=${patterns[$i]}
        name=${pattern_names[$i]}

        pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            running_services+=("$name:process")
        fi
    done
fi

if [[ ${#running_services[@]} -eq 0 ]]; then
    log_success "실행 중인 GTOne RAG 서비스가 없습니다."
    echo "시스템이 이미 정리되어 있습니다."
    exit 0
fi

echo "   발견된 실행 중인 서비스: ${#running_services[@]}개"

# ---------- 직접 종료 모드 ----------
if [[ "$DIRECT_MODE" == true ]]; then
    log_step "안전 모드: 직접 프로세스 종료..."

    # 1. Streamlit 프로세스 종료
    if command -v pgrep &> /dev/null; then
        streamlit_pids=$(pgrep -f "streamlit" 2>/dev/null || true)
        if [[ -n "$streamlit_pids" ]]; then
            echo "   Streamlit 프로세스 종료 중..."
            for pid in $streamlit_pids; do
                echo "     PID $pid 종료..."
                kill -TERM $pid 2>/dev/null || true
                sleep 2
                if kill -0 $pid 2>/dev/null; then
                    kill -9 $pid 2>/dev/null || true
                fi
            done
        fi
    fi

    # 2. FastAPI/Uvicorn 프로세스 종료
    if command -v pgrep &> /dev/null; then
        uvicorn_pids=$(pgrep -f "uvicorn.*main" 2>/dev/null || true)
        if [[ -n "$uvicorn_pids" ]]; then
            echo "   FastAPI 프로세스 종료 중..."
            for pid in $uvicorn_pids; do
                echo "     PID $pid 종료..."
                kill -TERM $pid 2>/dev/null || true
                sleep 2
                if kill -0 $pid 2>/dev/null; then
                    kill -9 $pid 2>/dev/null || true
                fi
            done
        fi
    fi

    # 3. Celery 프로세스 종료
    if command -v pgrep &> /dev/null; then
        celery_pids=$(pgrep -f "celery.*worker" 2>/dev/null || true)
        if [[ -n "$celery_pids" ]]; then
            echo "   Celery 프로세스 종료 중..."
            for pid in $celery_pids; do
                echo "     PID $pid 종료..."
                kill -TERM $pid 2>/dev/null || true
                sleep 2
                if kill -0 $pid 2>/dev/null; then
                    kill -9 $pid 2>/dev/null || true
                fi
            done
        fi
    fi

    # 4. Docker 컨테이너 정지 (선택적)
    echo -e "\n   Docker 컨테이너도 정지하시겠습니까? (y/n)"
    read -r stop_docker

    if [[ "$stop_docker" =~ ^[Yy]$ ]]; then
        if command -v docker &> /dev/null && docker info > /dev/null 2>&1; then
            gtrag_containers=$(docker ps --filter "name=qdrant" --filter "name=redis" --format "{{.Names}}" 2>/dev/null | grep -E "(qdrant|redis)" || true)

            if [[ -n "$gtrag_containers" ]]; then
                echo "   Docker 컨테이너 정지 중..."
                for container in $gtrag_containers; do
                    echo "     $container 정지..."
                    docker stop $container > /dev/null 2>&1 || true
                done
            fi
        fi
    fi

    # 5. PID 파일 정리
    echo "   임시 파일 정리 중..."
    pid_files=(".api.pid" ".celery.pid" ".streamlit.pid" "backend/.api.pid" "backend/.celery.pid" "frontend/.streamlit.pid")
    for pid_file in "${pid_files[@]}"; do
        if [[ -f "$pid_file" ]]; then
            rm -f "$pid_file"
            echo "     $pid_file 삭제됨"
        fi
    done

    log_success "안전 모드 종료 완료"

elif [[ "$FORCE_MODE" == true ]]; then
    # ---------- 강제 종료 모드 ----------
    log_step "강제 모드: 즉시 모든 프로세스 종료..."

    # 모든 관련 프로세스 강제 종료
    if command -v pgrep &> /dev/null; then
        all_patterns=("streamlit" "uvicorn" "celery" "fastapi")
        for pattern in "${all_patterns[@]}"; do
            pids=$(pgrep -f "$pattern" 2>/dev/null || true)
            if [[ -n "$pids" ]]; then
                echo "   $pattern 프로세스 강제 종료: $pids"
                echo $pids | xargs kill -9 2>/dev/null || true
            fi
        done
    fi

    # 포트 기반 강제 종료
    for port in "${main_ports[@]}"; do
        if command -v lsof &> /dev/null && lsof -i:$port > /dev/null 2>&1; then
            echo "   포트 $port 프로세스 강제 종료..."
            lsof -ti:$port | xargs kill -9 2>/dev/null || true
        fi
    done

    # Docker 컨테이너 강제 정지
    if command -v docker &> /dev/null && docker info > /dev/null 2>&1; then
        gtrag_containers=$(docker ps --filter "name=qdrant" --filter "name=redis" --format "{{.Names}}" 2>/dev/null | grep -E "(qdrant|redis)" || true)
        if [[ -n "$gtrag_containers" ]]; then
            echo "   Docker 컨테이너 강제 정지: $gtrag_containers"
            for container in $gtrag_containers; do
                docker kill $container > /dev/null 2>&1 || true
            done
        fi
    fi

    log_success "강제 종료 완료"

else
    # ---------- 스크립트 기반 정상 종료 ----------

    # 스크립트 존재 확인
    log_info "종료 스크립트 확인 중..."

    FRONTEND_STOP_SCRIPT="scripts/stop_frontend.sh"
    BACKEND_STOP_SCRIPT="scripts/stop_backend.sh"
    INFRA_STOP_SCRIPT="scripts/stop_infra.sh"

    scripts_found=0

    if [[ -f "$FRONTEND_STOP_SCRIPT" ]]; then
        log_success "프론트엔드 종료 스크립트 확인: $FRONTEND_STOP_SCRIPT"
        scripts_found=$((scripts_found + 1))
    else
        log_warning "프론트엔드 종료 스크립트 없음: $FRONTEND_STOP_SCRIPT"
    fi

    if [[ -f "$BACKEND_STOP_SCRIPT" ]]; then
        log_success "백엔드 종료 스크립트 확인: $BACKEND_STOP_SCRIPT"
        scripts_found=$((scripts_found + 1))
    else
        log_warning "백엔드 종료 스크립트 없음: $BACKEND_STOP_SCRIPT"
    fi

    if [[ -f "$INFRA_STOP_SCRIPT" ]]; then
        log_success "인프라 종료 스크립트 확인: $INFRA_STOP_SCRIPT"
        scripts_found=$((scripts_found + 1))
    else
        log_warning "인프라 종료 스크립트 없음: $INFRA_STOP_SCRIPT"
    fi

    # ---------- 자동 응답 함수 ----------
    run_stop_with_auto_input() {
        local script_path="$1"
        local script_name="$2"

        if [[ "$AUTO_MODE" == true ]]; then
            # expect를 사용할 수 있으면 사용
            if command -v expect &> /dev/null; then
                expect << EOF
spawn bash "$script_path"
expect {
    "*? (y/n)" { send "y\r"; exp_continue }
    "*? (Y/n)" { send "y\r"; exp_continue }
    "*? (y/N)" { send "y\r"; exp_continue }
    "*삭제*" { send "y\r"; exp_continue }
    "*제거*" { send "y\r"; exp_continue }
    "*종료*" { send "y\r"; exp_continue }
    "*계속*" { send "y\r"; exp_continue }
    eof
}
EOF
            else
                # expect가 없으면 yes 명령어 사용
                echo "y" | bash "$script_path" || bash "$script_path" < <(yes "y")
            fi
        else
            # 대화형 모드
            bash "$script_path"
        fi
    }

    # ---------- 1단계: 프론트엔드 서비스 종료 ----------
    if [[ -f "$FRONTEND_STOP_SCRIPT" ]]; then
        log_step "1단계: 프론트엔드 서비스 종료 중..."
        echo "   스크립트: $FRONTEND_STOP_SCRIPT"

        cd "$(dirname "$FRONTEND_STOP_SCRIPT")" || {
            log_error "프론트엔드 스크립트 디렉토리로 이동 실패"
            exit 1
        }

        if run_stop_with_auto_input "./$(basename "$FRONTEND_STOP_SCRIPT")" "프론트엔드"; then
            log_success "프론트엔드 서비스 종료 완료"
        else
            log_warning "프론트엔드 서비스 종료 중 오류 발생"
        fi

        cd "$PROJECT_ROOT" || exit 1
        sleep 2
    else
        log_warning "프론트엔드 종료 스크립트를 건너뜁니다"
    fi

    # ---------- 2단계: 백엔드 서비스 종료 ----------
    if [[ -f "$BACKEND_STOP_SCRIPT" ]]; then
        log_step "2단계: 백엔드 서비스 종료 중..."
        echo "   스크립트: $BACKEND_STOP_SCRIPT"

        cd "$(dirname "$BACKEND_STOP_SCRIPT")" || {
            log_error "백엔드 스크립트 디렉토리로 이동 실패"
            exit 1
        }

        if run_stop_with_auto_input "./$(basename "$BACKEND_STOP_SCRIPT")" "백엔드"; then
            log_success "백엔드 서비스 종료 완료"
        else
            log_warning "백엔드 서비스 종료 중 오류 발생"
        fi

        cd "$PROJECT_ROOT" || exit 1
        sleep 2
    else
        log_warning "백엔드 종료 스크립트를 건너뜁니다"
    fi

    # ---------- 3단계: 인프라 서비스 종료 ----------
    if [[ -f "$INFRA_STOP_SCRIPT" ]]; then
        log_step "3단계: 인프라 서비스 종료 중..."
        echo "   스크립트: $INFRA_STOP_SCRIPT"

        cd "$(dirname "$INFRA_STOP_SCRIPT")" || {
            log_error "인프라 스크립트 디렉토리로 이동 실패"
            exit 1
        }

        if run_stop_with_auto_input "./$(basename "$INFRA_STOP_SCRIPT")" "인프라"; then
            log_success "인프라 서비스 종료 완료"
        else
            log_warning "인프라 서비스 종료 중 오류 발생"
        fi

        cd "$PROJECT_ROOT" || exit 1
    else
        log_warning "인프라 종료 스크립트를 건너뜁니다"
    fi
fi

# ---------- 최종 상태 확인 ----------
log_step "종료 후 상태 확인 중..."

# 서비스별 종료 확인
echo "   🔍 종료 확인:"

all_stopped=true

# 포트 상태 재확인
for i in "${!main_ports[@]}"; do
    port=${main_ports[$i]}
    name=${port_names[$i]}

    if command -v lsof &> /dev/null && lsof -i:$port > /dev/null 2>&1; then
        echo "      - $name (포트 $port): ⚠️ 여전히 실행 중"
        all_stopped=false

        # 사용 중인 프로세스 정보
        process_info=$(lsof -i:$port 2>/dev/null | tail -n +2 | head -1)
        if [[ -n "$process_info" ]]; then
            echo "        $process_info"
        fi
    else
        echo "      - $name (포트 $port): ✅ 정지됨"
    fi
done

# 프로세스 패턴 재확인
if command -v pgrep &> /dev/null; then
    remaining_patterns=("streamlit" "uvicorn.*main" "celery.*worker")
    for pattern in "${remaining_patterns[@]}"; do
        pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            echo "      - $pattern 프로세스: ⚠️ 여전히 실행 중 (PID: $pids)"
            all_stopped=false
        fi
    done
fi

# Docker 컨테이너 상태
if command -v docker &> /dev/null && docker info > /dev/null 2>&1; then
    echo "   🐳 Docker 컨테이너 상태:"
    gtrag_containers=$(docker ps --filter "name=qdrant" --filter "name=redis" --format "{{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "(qdrant|redis)" || true)

    if [[ -n "$gtrag_containers" ]]; then
        echo "$gtrag_containers" | while read container_info; do
            echo "      - $container_info"
        done
        all_stopped=false
    else
        echo "      - ✅ GTOne RAG 관련 컨테이너 없음"
    fi
fi

# 임시 파일 상태
echo "   📁 임시 파일 상태:"
temp_files=(".api.pid" ".celery.pid" ".streamlit.pid" ".backend_info" ".frontend_info" ".infra_info")
remaining_files=0

for temp_file in "${temp_files[@]}"; do
    if [[ -f "$temp_file" ]]; then
        echo "      - $temp_file: ⚠️ 남아있음"
        remaining_files=$((remaining_files + 1))
    fi
done

if [[ $remaining_files -eq 0 ]]; then
    echo "      - ✅ 임시 파일 모두 정리됨"
fi

# ---------- 완료 메시지 ----------
STOP_ALL_END_TIME=$(date '+%Y-%m-%d %H:%M:%S')

echo -e "\n${CYAN}🏁 GTOne RAG 전체 시스템 종료 완료!${NC}"

echo -e "\n${BLUE}📊 종료 요약:${NC}"
echo "   종료 모드: $(if [[ "$DIRECT_MODE" == true ]]; then echo "안전 모드"; elif [[ "$FORCE_MODE" == true ]]; then echo "강제 모드"; elif [[ "$AUTO_MODE" == true ]]; then echo "자동 모드"; else echo "대화형 모드"; fi)"
echo "   종료 시작: $STOP_ALL_TIME"
echo "   종료 완료: $STOP_ALL_END_TIME"
echo "   프로젝트 루트: $PROJECT_ROOT"

if [[ "$all_stopped" == true ]]; then
    echo -e "\n${GREEN}✨ 모든 서비스가 성공적으로 종료되었습니다! ✨${NC}"

    echo -e "\n${YELLOW}🧹 추가 정리 옵션:${NC}"
    echo "   - 임시 파일 정리: ./scripts/cleanup_all.sh"
    echo "   - Docker 완전 정리: docker system prune -a"
    echo "   - Conda 환경 제거: conda env remove -n GTRAG"
else
    echo -e "\n${YELLOW}⚠️ 일부 서비스나 프로세스가 완전히 종료되지 않았습니다.${NC}"

    echo -e "\n${YELLOW}🔧 수동 정리 방법:${NC}"
    echo "   - 남은 프로세스: pkill -f streamlit && pkill -f uvicorn && pkill -f celery"
    echo "   - 포트 정리: sudo lsof -ti:8501,18000,6333,6379 | xargs sudo kill -9"
    echo "   - Docker 정리: docker stop \$(docker ps -q --filter name=qdrant) \$(docker ps -q --filter name=redis)"
    echo "   - 강제 모드 재실행: ./scripts/stop_all.sh (옵션 3 선택)"
fi

echo -e "\n${YELLOW}🔄 다시 시작하려면:${NC}"
echo "   - 전체 시작: ./scripts/start_all.sh"
echo "   - 개별 시작:"
echo "     1. ./scripts/start_infra.sh"
echo "     2. ./scripts/start_backend.sh"
echo "     3. ./scripts/start_frontend.sh"

echo -e "\n${GREEN}🛑 시스템 종료가 완료되었습니다! 🛑${NC}"

exit 0