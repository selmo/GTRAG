#!/bin/bash

# =================================================================
# GTOne RAG 공통 함수 라이브러리
# 위치: scripts/common.sh
# =================================================================

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# 프로젝트 설정
PROJECT_NAME="GTOne RAG"
DEFAULT_PORTS=(6333 6379 18000 8501)
PORT_NAMES=("Qdrant" "Redis" "FastAPI" "Streamlit")

# =================================================================
# 로깅 함수들
# =================================================================

log_info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_step() {
    echo -e "\n${PURPLE}🔄 $1${NC}"
    echo "$(printf '%.0s=' {1..50})"
}

# =================================================================
# 환경 확인 함수들
# =================================================================

check_command() {
    local cmd=$1
    local install_hint=$2

    if ! command -v "$cmd" &> /dev/null; then
        log_error "$cmd가 설치되지 않았습니다."
        if [[ -n "$install_hint" ]]; then
            echo "   설치 방법: $install_hint"
        fi
        return 1
    fi
    return 0
}

check_docker() {
    check_command "docker" "https://docs.docker.com/get-docker/" || return 1

    if ! docker info > /dev/null 2>&1; then
        log_error "Docker 데몬이 실행되지 않았습니다."
        echo "   Docker Desktop을 시작하거나 'sudo systemctl start docker' 실행"
        return 1
    fi

    log_success "Docker 환경 확인됨"
    return 0
}

check_conda() {
    check_command "conda" "https://docs.conda.io/en/latest/miniconda.html" || return 1
    log_success "Conda 환경 확인됨: $(conda --version)"
    return 0
}

# =================================================================
# 포트 관리 함수들
# =================================================================

check_port() {
    local port=$1

    if lsof -i:$port > /dev/null 2>&1; then
        return 1  # 포트 사용 중
    else
        return 0  # 포트 사용 가능
    fi
}

get_port_process() {
    local port=$1
    lsof -i:$port 2>/dev/null | tail -n +2 | head -1
}

kill_port_process() {
    local port=$1
    local force=${2:-false}

    if check_port $port; then
        return 0  # 포트가 이미 사용 가능
    fi

    local process_info=$(get_port_process $port)
    if [[ -n "$process_info" ]]; then
        log_warning "포트 $port가 사용 중입니다:"
        echo "   $process_info"

        if $force; then
            log_info "포트 $port 프로세스를 강제 종료합니다..."
            lsof -ti:$port | xargs kill -9 2>/dev/null
            sleep 2
        else
            echo "   기존 프로세스를 종료하시겠습니까? (y/n)"
            read -r response
            if [[ "$response" =~ ^[Yy]$ ]]; then
                lsof -ti:$port | xargs kill -9 2>/dev/null
                sleep 2
            else
                return 1
            fi
        fi
    fi

    return 0
}

# =================================================================
# 서비스 대기 함수들
# =================================================================

wait_for_service() {
    local url=$1
    local timeout=${2:-30}
    local service_name=${3:-"Service"}
    local check_interval=${4:-2}

    log_info "$service_name 준비 대기 중..."

    for i in $(seq 1 $timeout); do
        # HTTP 서비스 체크
        if [[ "$url" =~ ^https?:// ]]; then
            if curl -s --connect-timeout 2 "$url" > /dev/null 2>&1; then
                log_success "$service_name 준비 완료 (${i}초)"
                return 0
            fi
        # Redis 체크
        elif [[ "$url" =~ ^redis:// ]]; then
            if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
                log_success "$service_name 준비 완료 (${i}초)"
                return 0
            fi
        fi

        # 진행 상황 표시
        if [[ $((i % 10)) -eq 0 ]]; then
            log_info "대기 중... ${i}초 경과"
        else
            echo -n "."
        fi

        sleep $check_interval
    done

    echo ""  # 줄바꿈
    log_warning "$service_name 준비 시간 초과 (${timeout}초)"
    return 1
}

wait_for_docker_container() {
    local container_name=$1
    local timeout=${2:-60}

    log_info "Docker 컨테이너 '$container_name' 준비 대기..."

    for i in $(seq 1 $timeout); do
        if docker ps --format "{{.Names}}" | grep -q "^$container_name$"; then
            # 컨테이너가 실행 중인지 확인
            local status=$(docker inspect $container_name --format='{{.State.Status}}')
            if [[ "$status" == "running" ]]; then
                log_success "컨테이너 '$container_name' 준비 완료 (${i}초)"
                return 0
            fi
        fi

        if [[ $((i % 15)) -eq 0 ]]; then
            log_info "대기 중... ${i}초 경과"
        else
            echo -n "."
        fi

        sleep 1
    done

    echo ""
    log_warning "컨테이너 '$container_name' 준비 시간 초과"
    return 1
}

# =================================================================
# 환경변수 관리 함수들
# =================================================================

load_environment() {
    local script_dir=$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)
    local env_files=(
        "$script_dir/.env"
        "$script_dir/../.env"
        "$script_dir/../../.env"
        "./.env"
    )

    for env_file in "${env_files[@]}"; do
        if [[ -f "$env_file" ]]; then
            set -a
            source "$env_file"
            set +a
            log_success "환경 설정 로드: $env_file"
            return 0
        fi
    done

    log_warning "환경 설정 파일을 찾을 수 없습니다. 기본값 사용"
    return 1
}

set_default_env() {
    # 기본 환경변수 설정
    export QDRANT_PORT=${QDRANT_PORT:-6333}
    export REDIS_PORT=${REDIS_PORT:-6379}
    export API_PORT=${API_PORT:-18000}
    export STREAMLIT_PORT=${STREAMLIT_PORT:-8501}
    export OLLAMA_HOST=${OLLAMA_HOST:-"http://172.16.15.112:11434"}
    export API_BASE_URL=${API_BASE_URL:-"http://localhost:$API_PORT"}
    export LOG_LEVEL=${LOG_LEVEL:-"INFO"}
    export DOCKER_NETWORK=${DOCKER_NETWORK:-"gtrag-network"}
}

# =================================================================
# 파일/디렉토리 관리 함수들
# =================================================================

ensure_directory() {
    local dir=$1
    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        log_info "디렉토리 생성: $dir"
    fi
}

find_project_root() {
    local current_dir=$(pwd)
    local search_dir="$current_dir"

    # 최대 5 레벨까지 상위 디렉토리 검색
    for i in {1..5}; do
        if [[ -d "$search_dir/infrastructure" && -d "$search_dir/backend" && -d "$search_dir/frontend" ]]; then
            echo "$search_dir"
            return 0
        fi
        search_dir=$(dirname "$search_dir")
        if [[ "$search_dir" == "/" ]]; then
            break
        fi
    done

    log_error "프로젝트 루트 디렉토리를 찾을 수 없습니다."
    echo "현재 위치: $current_dir"
    echo "필요한 디렉토리: infrastructure/, backend/, frontend/"
    return 1
}

# =================================================================
# 헬스체크 함수들
# =================================================================

detailed_health_check() {
    local service_name=$1
    local url=$2

    case $service_name in
        "Qdrant")
            if curl -s "$url" | grep -q "\"status\":\"ok\""; then
                return 0
            fi
            ;;
        "Redis")
            if redis-cli -h localhost -p ${REDIS_PORT:-6379} ping 2>/dev/null | grep -q "PONG"; then
                return 0
            fi
            ;;
        "API")
            if curl -s "$url" | grep -q "\"status\":\"healthy\""; then
                return 0
            fi
            ;;
        "UI")
            if curl -s --connect-timeout 3 "$url" > /dev/null 2>&1; then
                return 0
            fi
            ;;
    esac

    return 1
}

comprehensive_health_check() {
    log_step "전체 시스템 헬스체크 수행"

    local all_healthy=true
    local services=(
        "Qdrant:http://localhost:${QDRANT_PORT:-6333}/health"
        "Redis:redis://localhost:${REDIS_PORT:-6379}"
        "API:http://localhost:${API_PORT:-18000}/v1/health"
        "UI:http://localhost:${STREAMLIT_PORT:-8501}/_stcore/health"
    )

    for service_info in "${services[@]}"; do
        IFS=':' read -r name url <<< "$service_info"

        echo -n "   $name: "
        if detailed_health_check "$name" "$url"; then
            log_success "정상"
        else
            log_error "비정상"
            all_healthy=false
        fi
    done

    if $all_healthy; then
        log_success "모든 서비스가 정상입니다"
        return 0
    else
        log_warning "일부 서비스에 문제가 있습니다"
        return 1
    fi
}

# =================================================================
# 에러 처리 함수들
# =================================================================

handle_error() {
    local exit_code=$1
    local service_name=$2
    local log_file=${3:-""}

    if [[ $exit_code -ne 0 ]]; then
        log_error "$service_name 시작 실패 (exit code: $exit_code)"

        if [[ -f "$log_file" ]]; then
            log_info "마지막 10줄의 로그:"
            tail -10 "$log_file" | sed 's/^/    /'
            echo ""
        fi

        log_info "문제 해결 방법:"
        echo "  1. 로그 전체 확인: cat $log_file"
        echo "  2. 포트 충돌 확인: lsof -i:${API_PORT:-18000}"
        echo "  3. 개별 서비스 재시작"
        echo "  4. 시스템 정리 후 재시작: ./scripts/stop_all.sh && ./scripts/start_all.sh"

        return 1
    fi

    return 0
}

cleanup_on_exit() {
    local service_name=$1
    local pid_file=${2:-""}

    echo ""
    log_warning "중단 신호를 받았습니다. $service_name 정리 중..."

    if [[ -f "$pid_file" ]]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            log_info "프로세스 $pid 종료됨"
        fi
        rm -f "$pid_file"
    fi

    exit 130
}

# =================================================================
# 사용법 예시
# =================================================================

show_usage_example() {
    cat << 'EOF'
# 공통 함수 사용 예시:

# 1. 공통 함수 로드
source "scripts/common.sh"

# 2. 환경 설정
load_environment
set_default_env

# 3. 기본 확인
check_docker || exit 1
find_project_root || exit 1

# 4. 포트 확인 및 정리
kill_port_process 8501 false

# 5. 서비스 대기
wait_for_service "http://localhost:6333/health" 30 "Qdrant"

# 6. 헬스체크
comprehensive_health_check
EOF
}

# =================================================================
# 초기화 함수
# =================================================================

init_common() {
    # 기본 환경 설정
    set_default_env

    # 기본 디렉토리 생성
    ensure_directory "logs"

    # 시그널 핸들러 설정
    trap 'cleanup_on_exit "Common Script"' INT TERM
}

# 스크립트가 직접 실행된 경우 사용법 표시
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "GTOne RAG 공통 함수 라이브러리"
    echo "이 파일은 다른 스크립트에서 source로 로드하여 사용합니다."
    echo ""
    show_usage_example
fi