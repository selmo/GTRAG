#!/bin/bash

# ==================================================
# GTOne RAG - 전체 임시 파일 정리 스크립트
# 위치: ./scripts/cleanup_all.sh
# 모든 GTOne RAG 관련 임시 파일과 생성된 파일들을 제거
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
log_cleanup() { echo -e "${PURPLE}🧹 $1${NC}"; }

# ---------- 배너 ----------
echo -e "${CYAN}🧹 GTOne RAG - 전체 임시 파일 정리${NC}"
echo "====================================="

CLEANUP_START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
log_info "정리 시작 시간: $CLEANUP_START_TIME"

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
    log_warning "프로젝트 루트 자동 감지 실패"
    PROJECT_ROOT="$(pwd)"
    log_warning "현재 디렉토리를 프로젝트 루트로 설정: $PROJECT_ROOT"
fi

cd "$PROJECT_ROOT" || {
    log_error "프로젝트 루트로 이동 실패: $PROJECT_ROOT"
    exit 1
}

log_info "작업 디렉토리: $(pwd)"

# ---------- 정리 옵션 선택 ----------
echo -e "\n${YELLOW}🎯 정리 수준을 선택하세요:${NC}"
echo "   1) 기본 정리 (PID 파일, 임시 파일만)"
echo "   2) 표준 정리 (기본 + 로그 파일)"
echo "   3) 전체 정리 (표준 + Conda 환경, Docker 볼륨)"
echo "   4) 완전 정리 (전체 + Docker 이미지, 네트워크)"
echo "   q) 취소"
echo ""
read -p "선택 (1-4, q): " cleanup_level

case $cleanup_level in
    [1])
        log_info "기본 정리 모드 선택"
        CLEANUP_LEVEL="basic"
        ;;
    [2])
        log_info "표준 정리 모드 선택"
        CLEANUP_LEVEL="standard"
        ;;
    [3])
        log_info "전체 정리 모드 선택"
        CLEANUP_LEVEL="full"
        ;;
    [4])
        log_info "완전 정리 모드 선택"
        CLEANUP_LEVEL="complete"
        ;;
    [Qq])
        log_info "정리 취소됨"
        exit 0
        ;;
    *)
        log_warning "잘못된 선택. 기본 정리 모드로 진행"
        CLEANUP_LEVEL="basic"
        ;;
esac

# ---------- 정리 통계 변수 ----------
cleaned_files=0
cleaned_dirs=0
cleaned_size=0

# ---------- 파일 크기 계산 함수 ----------
get_file_size() {
    local file="$1"
    if [[ -f "$file" ]]; then
        if command -v stat &> /dev/null; then
            stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo 0
        else
            echo 0
        fi
    else
        echo 0
    fi
}

# ---------- 안전한 파일 제거 함수 ----------
safe_remove() {
    local target="$1"
    local description="${2:-$target}"

    if [[ -e "$target" ]]; then
        local size=0
        if [[ -f "$target" ]]; then
            size=$(get_file_size "$target")
            cleaned_files=$((cleaned_files + 1))
        elif [[ -d "$target" ]]; then
            if command -v du &> /dev/null; then
                size=$(du -sb "$target" 2>/dev/null | cut -f1 || echo 0)
            fi
            cleaned_dirs=$((cleaned_dirs + 1))
        fi

        cleaned_size=$((cleaned_size + size))

        rm -rf "$target" 2>/dev/null || {
            log_warning "제거 실패: $description"
            return 1
        }

        echo "   ✓ $description"
        return 0
    fi
    return 0
}

# ---------- 1. PID 파일 정리 ----------
log_cleanup "PID 파일 정리 중..."

pid_files=(
    ".api.pid"
    ".celery.pid"
    ".streamlit.pid"
    "backend/.api.pid"
    "backend/.celery.pid"
    "frontend/.streamlit.pid"
)

for pid_file in "${pid_files[@]}"; do
    safe_remove "$pid_file" "PID 파일: $pid_file"
done

# ---------- 2. 서비스 정보 파일 정리 ----------
log_cleanup "서비스 정보 파일 정리 중..."

info_files=(
    ".backend_info"
    ".frontend_info"
    ".infra_info"
    "backend/.backend_info"
    "frontend/.frontend_info"
    "infrastructure/.infra_info"
)

for info_file in "${info_files[@]}"; do
    safe_remove "$info_file" "정보 파일: $info_file"
done

# ---------- 3. nohup 출력 파일 정리 ----------
log_cleanup "nohup 출력 파일 정리 중..."

nohup_files=(
    "nohup.out"
    "backend/nohup.out"
    "frontend/nohup.out"
    "infrastructure/nohup.out"
)

for nohup_file in "${nohup_files[@]}"; do
    safe_remove "$nohup_file" "nohup 출력: $nohup_file"
done

# ---------- 4. 로그 파일 정리 (표준 이상) ----------
if [[ "$CLEANUP_LEVEL" != "basic" ]]; then
    log_cleanup "로그 파일 정리 중..."

    # 메인 로그 디렉토리들
    log_dirs=(
        "logs"
        "backend/logs"
        "frontend/logs"
        "infrastructure/logs"
    )

    total_log_files=0

    for log_dir in "${log_dirs[@]}"; do
        if [[ -d "$log_dir" ]]; then
            echo "   디렉토리 확인: $log_dir"

            # 로그 파일 목록 표시
            log_files=$(find "$log_dir" -type f \( -name "*.log" -o -name "*.log.*" -o -name "nohup.out" \) 2>/dev/null)

            if [[ -n "$log_files" ]]; then
                log_count=$(echo "$log_files" | wc -l)
                total_log_files=$((total_log_files + log_count))

                echo "   발견된 로그 파일: $log_dir ($log_count 개)"

                # 각 파일을 개별적으로 표시하고 삭제
                while IFS= read -r log_file; do
                    if [[ -f "$log_file" ]]; then
                        file_size=$(get_file_size "$log_file")
                        cleaned_size=$((cleaned_size + file_size))

                        rm -f "$log_file" 2>/dev/null || {
                            log_warning "삭제 실패: $log_file"
                            continue
                        }

                        cleaned_files=$((cleaned_files + 1))
                        echo "     ✓ $(basename "$log_file")"
                    fi
                done <<< "$log_files"

                echo "   ✓ $log_dir 정리 완료 ($log_count 개 파일)"
            else
                echo "   - $log_dir: 로그 파일 없음"
            fi

            # 빈 로그 디렉토리 제거 (logs는 보존)
            if [[ "$log_dir" != "logs" ]] && [[ -z "$(ls -A "$log_dir" 2>/dev/null)" ]]; then
                safe_remove "$log_dir" "빈 로그 디렉토리: $log_dir"
            fi
        else
            echo "   - $log_dir: 디렉토리 없음"
        fi
    done

    # 개별 로그 파일들 (디렉토리 외부)
    echo "   개별 로그 파일 확인 중..."
    individual_logs=(
        "api.log"
        "celery.log"
        "streamlit.log"
        "uvicorn.log"
        "nohup.out"
        "backend/api.log"
        "backend/celery.log"
        "backend/uvicorn.log"
        "backend/nohup.out"
        "frontend/streamlit.log"
        "frontend/nohup.out"
        "infrastructure/docker.log"
        "infrastructure/nohup.out"
    )

    for log_file in "${individual_logs[@]}"; do
        if [[ -f "$log_file" ]]; then
            safe_remove "$log_file" "개별 로그: $log_file"
            total_log_files=$((total_log_files + 1))
        fi
    done

    # 패턴 기반 로그 파일 찾기 (더 광범위)
    echo "   패턴 기반 로그 파일 검색 중..."

    if command -v find &> /dev/null; then
        # 다양한 로그 파일 패턴
        log_patterns=(
            "*.log"
            "*.log.*"
            "*.out"
            "*_log"
            "*-log"
        )

        for pattern in "${log_patterns[@]}"; do
            pattern_files=$(find . -maxdepth 3 -name "$pattern" -type f 2>/dev/null | grep -v -E '\.(git|node_modules|venv|__pycache__)' || true)

            if [[ -n "$pattern_files" ]]; then
                while IFS= read -r pattern_file; do
                    # 중요한 파일들은 건너뛰기
                    if [[ "$pattern_file" == *"config"* ]] || \
                       [[ "$pattern_file" == *"readme"* ]] || \
                       [[ "$pattern_file" == *"README"* ]] || \
                       [[ "$pattern_file" == *"requirements"* ]]; then
                        continue
                    fi

                    if [[ -f "$pattern_file" ]]; then
                        # 파일 내용으로 로그 파일인지 확인
                        if file "$pattern_file" 2>/dev/null | grep -qi "text"; then
                            safe_remove "$pattern_file" "패턴 로그: $pattern_file"
                            total_log_files=$((total_log_files + 1))
                        fi
                    fi
                done <<< "$pattern_files"
            fi
        done
    fi

    if [[ $total_log_files -gt 0 ]]; then
        log_success "총 $total_log_files 개의 로그 파일이 정리되었습니다"
    else
        echo "   정리할 로그 파일이 없습니다"
    fi
fi

# ---------- 5. Python 관련 임시 파일 정리 ----------
log_cleanup "Python 임시 파일 정리 중..."

# __pycache__ 디렉토리
if command -v find &> /dev/null; then
    pycache_dirs=$(find . -type d -name "__pycache__" 2>/dev/null)
    for pycache_dir in $pycache_dirs; do
        safe_remove "$pycache_dir" "Python 캐시: $pycache_dir"
    done

    # .pyc 파일
    pyc_files=$(find . -name "*.pyc" 2>/dev/null)
    for pyc_file in $pyc_files; do
        safe_remove "$pyc_file" "Python 바이트코드: $pyc_file"
    done

    # .pyo 파일
    pyo_files=$(find . -name "*.pyo" 2>/dev/null)
    for pyo_file in $pyo_files; do
        safe_remove "$pyo_file" "Python 최적화: $pyo_file"
    done
fi

# ---------- 6. Streamlit 관련 파일 정리 ----------
log_cleanup "Streamlit 관련 파일 정리 중..."

# .streamlit/secrets.toml (설정은 보존)
streamlit_dirs=(
    ".streamlit"
    "frontend/.streamlit"
)

for streamlit_dir in "${streamlit_dirs[@]}"; do
    if [[ -d "$streamlit_dir" ]]; then
        # secrets.toml이 있으면 백업
        if [[ -f "$streamlit_dir/secrets.toml" ]]; then
            echo "   ⚠️  $streamlit_dir/secrets.toml 보존됨 (보안 정보 포함)"
        fi

        # 캐시 파일들만 정리
        cache_files=(
            "$streamlit_dir/.streamlit"
            "$streamlit_dir/logs"
        )

        for cache_file in "${cache_files[@]}"; do
            safe_remove "$cache_file" "Streamlit 캐시: $cache_file"
        done
    fi
done

# ---------- 7. 데이터베이스 관련 임시 파일 정리 ----------
log_cleanup "데이터베이스 임시 파일 정리 중..."

db_temp_files=(
    "*.db-journal"
    "*.db-wal"
    "*.db-shm"
    ".qdrant_lock"
    ".redis_lock"
)

for pattern in "${db_temp_files[@]}"; do
    if command -v find &> /dev/null; then
        temp_files=$(find . -name "$pattern" 2>/dev/null)
        for temp_file in $temp_files; do
            safe_remove "$temp_file" "DB 임시파일: $temp_file"
        done
    fi
done

# ---------- 8. Conda 환경 정리 (전체 이상) ----------
if [[ "$CLEANUP_LEVEL" == "full" || "$CLEANUP_LEVEL" == "complete" ]]; then
    log_cleanup "Conda 환경 정리 확인..."

    if command -v conda &> /dev/null; then
        CONDA_ENV_NAME="GTRAG"

        if conda env list | grep -q "^$CONDA_ENV_NAME "; then
            echo "   Conda 환경 '$CONDA_ENV_NAME' 발견됨"
            echo -e "${YELLOW}   Conda 환경을 제거하시겠습니까? (y/n)${NC}"
            echo "   주의: 설치된 모든 패키지가 삭제됩니다."
            read -r response

            if [[ "$response" =~ ^[Yy]$ ]]; then
                echo "   Conda 환경 '$CONDA_ENV_NAME' 제거 중..."
                conda env remove -n $CONDA_ENV_NAME -y > /dev/null 2>&1 || {
                    log_warning "Conda 환경 제거 실패"
                }
                echo "   ✓ Conda 환경 정리됨"
            else
                echo "   Conda 환경 보존됨"
            fi
        else
            echo "   Conda 환경 '$CONDA_ENV_NAME' 없음"
        fi
    else
        echo "   Conda가 설치되지 않음"
    fi
fi

# ---------- 9. Docker 관련 정리 (완전 정리) ----------
if [[ "$CLEANUP_LEVEL" == "complete" ]]; then
    log_cleanup "Docker 관련 정리 확인..."

    if command -v docker &> /dev/null && docker info > /dev/null 2>&1; then
        # GTOne RAG 관련 Docker 리소스 확인
        gtrag_containers=$(docker ps -a --filter "name=qdrant" --filter "name=redis" --format "{{.Names}}" 2>/dev/null | grep -E "(qdrant|redis)" || true)
        gtrag_volumes=$(docker volume ls --filter "name=qdrant" --filter "name=redis" --format "{{.Name}}" 2>/dev/null | grep -E "(qdrant|redis)" || true)
        gtrag_networks=$(docker network ls --filter "name=gtrag" --format "{{.Name}}" 2>/dev/null | grep gtrag || true)

        if [[ -n "$gtrag_containers" || -n "$gtrag_volumes" || -n "$gtrag_networks" ]]; then
            echo "   GTOne RAG Docker 리소스 발견됨:"

            if [[ -n "$gtrag_containers" ]]; then
                echo "     컨테이너: $gtrag_containers"
            fi
            if [[ -n "$gtrag_volumes" ]]; then
                echo "     볼륨: $gtrag_volumes"
            fi
            if [[ -n "$gtrag_networks" ]]; then
                echo "     네트워크: $gtrag_networks"
            fi

            echo -e "${YELLOW}   Docker 리소스를 제거하시겠습니까? (y/n)${NC}"
            echo "   주의: 저장된 데이터가 모두 삭제됩니다."
            read -r response

            if [[ "$response" =~ ^[Yy]$ ]]; then
                # 컨테이너 정지 및 제거
                if [[ -n "$gtrag_containers" ]]; then
                    echo "   컨테이너 정지 및 제거 중..."
                    for container in $gtrag_containers; do
                        docker stop "$container" > /dev/null 2>&1 || true
                        docker rm "$container" > /dev/null 2>&1 || true
                        echo "   ✓ 컨테이너 제거됨: $container"
                    done
                fi

                # 볼륨 제거
                if [[ -n "$gtrag_volumes" ]]; then
                    echo "   볼륨 제거 중..."
                    for volume in $gtrag_volumes; do
                        docker volume rm "$volume" > /dev/null 2>&1 || true
                        echo "   ✓ 볼륨 제거됨: $volume"
                    done
                fi

                # 네트워크 제거
                if [[ -n "$gtrag_networks" ]]; then
                    echo "   네트워크 제거 중..."
                    for network in $gtrag_networks; do
                        docker network rm "$network" > /dev/null 2>&1 || true
                        echo "   ✓ 네트워크 제거됨: $network"
                    done
                fi

                echo "   ✓ Docker 리소스 정리 완료"
            else
                echo "   Docker 리소스 보존됨"
            fi
        else
            echo "   GTOne RAG 관련 Docker 리소스 없음"
        fi
    else
        echo "   Docker가 설치되지 않았거나 실행되지 않음"
    fi
fi

# ---------- 10. 기타 임시 파일 정리 ----------
log_cleanup "기타 임시 파일 정리 중..."

misc_files=(
    ".DS_Store"
    "Thumbs.db"
    "*.tmp"
    "*.temp"
    "*.swp"
    "*.swo"
    "*~"
    ".vscode/settings.json"
    ".idea/"
)

for pattern in "${misc_files[@]}"; do
    if command -v find &> /dev/null; then
        misc_found=$(find . -name "$pattern" 2>/dev/null)
        for misc_file in $misc_found; do
            # 중요한 디렉토리는 건너뛰기
            if [[ "$misc_file" == *".idea"* && -d "$misc_file" ]]; then
                echo "   IDE 설정 디렉토리 건너뜀: $misc_file"
                continue
            fi
            safe_remove "$misc_file" "기타 임시파일: $misc_file"
        done
    fi
done

# ---------- 11. 빈 디렉토리 정리 ----------
if [[ "$CLEANUP_LEVEL" != "basic" ]]; then
    log_cleanup "빈 디렉토리 정리 중..."

    empty_dirs=(
        "logs"
        "backend/logs"
        "frontend/logs"
        "infrastructure/logs"
        "tmp"
        "temp"
        ".cache"
    )

    for empty_dir in "${empty_dirs[@]}"; do
        if [[ -d "$empty_dir" && -z "$(ls -A "$empty_dir" 2>/dev/null)" ]]; then
            safe_remove "$empty_dir" "빈 디렉토리: $empty_dir"
        fi
    done
fi

# ---------- 12. 최종 상태 확인 ----------
log_cleanup "최종 상태 확인 중..."

# 프로세스 상태 확인
echo "   현재 실행 중인 GTOne RAG 관련 프로세스:"
process_count=0

if command -v pgrep &> /dev/null; then
    patterns=("streamlit" "uvicorn.*main" "celery.*worker")

    for pattern in "${patterns[@]}"; do
        pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            for pid in $pids; do
                cmd=$(ps -p $pid -o args= 2>/dev/null | head -c 60)
                echo "     PID $pid: $cmd..."
                process_count=$((process_count + 1))
            done
        fi
    done
fi

if [[ $process_count -eq 0 ]]; then
    echo "     ✓ 실행 중인 GTOne RAG 프로세스 없음"
else
    log_warning "${process_count:-0}개의 프로세스가 여전히 실행 중입니다"
    echo "   프로세스 종료가 필요하면 stop 스크립트들을 사용하세요."
fi

# 포트 상태 확인
echo "   주요 포트 상태:"
main_ports=(8501 18000 6333 6379)
port_names=("Streamlit" "FastAPI" "Qdrant" "Redis")

for i in "${!main_ports[@]}"; do
    port=${main_ports[$i]}
    name=${port_names[$i]}

    if command -v lsof &> /dev/null && lsof -i:$port > /dev/null 2>&1; then
        echo "     포트 $port ($name): 사용 중"
    else
        echo "     포트 $port ($name): ✓ 사용 가능"
    fi
done

# ---------- 13. 정리 완료 메시지 ----------
CLEANUP_END_TIME=$(date '+%Y-%m-%d %H:%M:%S')

# 크기 변환 함수
format_size() {
    local size=$1
    if [[ $size -lt 1024 ]]; then
        echo "${size}B"
    elif [[ $size -lt 1048576 ]]; then
        echo "$((size / 1024))KB"
    else
        echo "$((size / 1048576))MB"
    fi
}

log_success "GTOne RAG 전체 임시 파일 정리 완료!"

echo -e "\n${CYAN}📊 정리 통계:${NC}"
echo "   정리 수준: $CLEANUP_LEVEL"
echo "   시작 시간: $CLEANUP_START_TIME"
echo "   완료 시간: $CLEANUP_END_TIME"
echo "   제거된 파일: ${cleaned_files}개"
echo "   제거된 디렉토리: ${cleaned_dirs}개"
echo "   절약된 공간: $(format_size $cleaned_size)"
echo "   프로젝트 루트: $PROJECT_ROOT"

echo -e "\n${YELLOW}💡 추가 정리가 필요한 경우:${NC}"

if [[ "$CLEANUP_LEVEL" == "basic" ]]; then
    echo "   - 더 완전한 정리: ./scripts/cleanup_all.sh (옵션 2-4 선택)"
fi

if [[ $process_count -gt 0 ]]; then
    echo "   - 실행 중인 프로세스 종료:"
    echo "     ./scripts/stop_backend.sh"
    echo "     ./scripts/stop_frontend.sh"
    echo "     ./scripts/stop_infra.sh"
fi

echo -e "\n${YELLOW}🔄 시스템 재시작:${NC}"
echo "   1. 인프라: ./scripts/start_infra.sh"
echo "   2. 백엔드: ./scripts/start_backend.sh"
echo "   3. 프론트엔드: ./scripts/start_frontend.sh"
echo "   또는 전체: ./scripts/start_all.sh"

echo -e "\n${YELLOW}🧹 수동 정리 명령어:${NC}"
echo "   - Python 캐시: find . -name __pycache__ -exec rm -rf {} +"
echo "   - 로그 파일: find . -name \"*.log\" -delete"
echo "   - Docker 시스템: docker system prune -a"
echo "   - Conda 환경: conda env remove -n GTRAG"

echo -e "\n${GREEN}✨ 시스템이 깨끗하게 정리되었습니다! ✨${NC}"

exit 0