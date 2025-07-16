#!/bin/bash

# ==================================================
# GTOne RAG - 전체 시스템 시작 스크립트
# 위치: ./scripts/start_all.sh
# 인프라 → 백엔드 → 프론트엔드 순서로 자동 시작
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
log_step() { echo -e "${PURPLE}🚀 $1${NC}"; }

# ---------- 배너 ----------
echo -e "${CYAN}🚀 GTOne RAG - 전체 시스템 시작${NC}"
echo "====================================="

START_ALL_TIME=$(date '+%Y-%m-%d %H:%M:%S')
log_info "전체 시작 시간: $START_ALL_TIME"

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

# ---------- 시작 모드 선택 ----------
echo -e "\n${YELLOW}🎯 시작 모드를 선택하세요:${NC}"
echo "   1) 자동 모드 (모든 입력을 자동으로 'y' 처리)"
echo "   2) 대화형 모드 (각 단계별 확인)"
echo "   3) 강제 모드 (충돌 시 강제 종료 후 시작)"
echo "   q) 취소"
echo ""
read -p "선택 (1-3, q): " start_mode

case $start_mode in
    [1])
        log_info "자동 모드 선택 - 모든 확인을 자동으로 진행합니다"
        AUTO_MODE=true
        FORCE_MODE=false
        ;;
    [2])
        log_info "대화형 모드 선택 - 각 단계별로 확인합니다"
        AUTO_MODE=false
        FORCE_MODE=false
        ;;
    [3])
        log_info "강제 모드 선택 - 충돌 시 강제로 해결합니다"
        AUTO_MODE=true
        FORCE_MODE=true
        ;;
    [Qq])
        log_info "시작 취소됨"
        exit 0
        ;;
    *)
        log_warning "잘못된 선택. 자동 모드로 진행합니다"
        AUTO_MODE=true
        FORCE_MODE=false
        ;;
esac

# ---------- 환경변수 설정 ----------
# 자동화를 위한 환경변수 설정
if [[ "$AUTO_MODE" == true ]]; then
    export GTRAG_AUTO_MODE="true"
    export GTRAG_AUTO_CONFIRM="y"
    export GTRAG_SKIP_PROMPTS="true"
fi

if [[ "$FORCE_MODE" == true ]]; then
    export GTRAG_FORCE_MODE="true"
    export GTRAG_KILL_CONFLICTS="true"
fi

# ---------- 스크립트 존재 확인 ----------
log_info "필요한 스크립트 확인 중..."

INFRA_SCRIPT="scripts/start_infra.sh"
BACKEND_SCRIPT="scripts/start_backend.sh"
FRONTEND_SCRIPT="scripts/start_frontend.sh"

scripts_found=0

if [[ -f "$INFRA_SCRIPT" ]]; then
    log_success "인프라 스크립트 확인: $INFRA_SCRIPT"
    scripts_found=$((scripts_found + 1))
else
    log_warning "인프라 스크립트 없음: $INFRA_SCRIPT"
fi

if [[ -f "$BACKEND_SCRIPT" ]]; then
    log_success "백엔드 스크립트 확인: $BACKEND_SCRIPT"
    scripts_found=$((scripts_found + 1))
else
    log_warning "백엔드 스크립트 없음: $BACKEND_SCRIPT"
fi

if [[ -f "$FRONTEND_SCRIPT" ]]; then
    log_success "프론트엔드 스크립트 확인: $FRONTEND_SCRIPT"
    scripts_found=$((scripts_found + 1))
else
    log_warning "프론트엔드 스크립트 없음: $FRONTEND_SCRIPT"
fi

if [[ $scripts_found -eq 0 ]]; then
    log_error "시작 스크립트를 찾을 수 없습니다!"
    exit 1
fi

# ---------- 기존 프로세스 정리 (강제 모드) ----------
if [[ "$FORCE_MODE" == true ]]; then
    log_step "강제 모드: 기존 프로세스 정리 중..."

    # 주요 포트들의 프로세스 강제 종료
    CONFLICT_PORTS=(6333 6379 18000 8501)

    for port in "${CONFLICT_PORTS[@]}"; do
        if command -v lsof &> /dev/null && lsof -i:$port > /dev/null 2>&1; then
            echo "   포트 $port 사용 프로세스 강제 종료 중..."
            lsof -ti:$port | xargs kill -9 2>/dev/null || true
            sleep 1
        fi
    done

    # GTOne RAG 관련 프로세스 패턴 종료
    if command -v pgrep &> /dev/null; then
        patterns=("streamlit" "uvicorn.*main" "celery.*worker")
        for pattern in "${patterns[@]}"; do
            pids=$(pgrep -f "$pattern" 2>/dev/null || true)
            if [[ -n "$pids" ]]; then
                echo "   $pattern 프로세스 종료 중..."
                echo $pids | xargs kill -9 2>/dev/null || true
            fi
        done
    fi

    log_success "기존 프로세스 정리 완료"
fi

# ---------- 자동 응답 함수 ----------
run_with_auto_input() {
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
    "*continue*" { send "y\r"; exp_continue }
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

# ---------- 1단계: 인프라 서비스 시작 ----------
if [[ -f "$INFRA_SCRIPT" ]]; then
    log_step "1단계: 인프라 서비스 시작 중..."
    echo "   스크립트: $INFRA_SCRIPT"

    cd "$(dirname "$INFRA_SCRIPT")" || {
        log_error "인프라 스크립트 디렉토리로 이동 실패"
        exit 1
    }

    if run_with_auto_input "./$(basename "$INFRA_SCRIPT")" "인프라"; then
        log_success "인프라 서비스 시작 완료"

        # 인프라 서비스 준비 대기
        echo "   인프라 서비스 안정화 대기 중..."
        sleep 10

        # Qdrant 및 Redis 연결 확인
        echo -n "   Qdrant 연결 확인... "
        if curl -s --connect-timeout 5 "http://localhost:6333/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✅${NC}"
        else
            echo -e "${YELLOW}⚠️${NC}"
            log_warning "Qdrant 연결 확인 실패"
        fi

        echo -n "   Redis 연결 확인... "
        if command -v redis-cli &> /dev/null && redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
            echo -e "${GREEN}✅${NC}"
        elif docker exec redis-service redis-cli ping > /dev/null 2>&1; then
            echo -e "${GREEN}✅${NC}"
        else
            echo -e "${YELLOW}⚠️${NC}"
            log_warning "Redis 연결 확인 실패"
        fi
    else
        log_error "인프라 서비스 시작 실패"
        exit 1
    fi

    cd "$PROJECT_ROOT" || exit 1
else
    log_warning "인프라 스크립트를 건너뜁니다"
fi

# ---------- 2단계: 백엔드 서비스 시작 ----------
if [[ -f "$BACKEND_SCRIPT" ]]; then
    log_step "2단계: 백엔드 서비스 시작 중..."
    echo "   스크립트: $BACKEND_SCRIPT"

    cd "$(dirname "$BACKEND_SCRIPT")" || {
        log_error "백엔드 스크립트 디렉토리로 이동 실패"
        exit 1
    }

    if run_with_auto_input "./$(basename "$BACKEND_SCRIPT")" "백엔드"; then
        log_success "백엔드 서비스 시작 완료"

        # 백엔드 서비스 준비 대기
        echo "   백엔드 서비스 안정화 대기 중..."
        sleep 15

        # FastAPI 서버 연결 확인
        echo -n "   FastAPI 서버 확인... "
        max_attempts=30
        attempt=0
        api_ready=false

        while [[ $attempt -lt $max_attempts ]] && [[ $api_ready == false ]]; do
            if curl -s --connect-timeout 2 "http://localhost:18000/docs" > /dev/null 2>&1; then
                api_ready=true
                echo -e "${GREEN}✅${NC}"
                break
            fi
            echo -n "."
            sleep 2
            attempt=$((attempt + 1))
        done

        if [[ $api_ready == false ]]; then
            echo -e "${YELLOW}⚠️${NC}"
            log_warning "FastAPI 서버 응답 시간 초과"
        fi

        # 헬스체크 확인
        echo -n "   헬스체크 확인... "
        if curl -s "http://localhost:18000/v1/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✅${NC}"
        else
            echo -e "${YELLOW}⚠️${NC}"
        fi
    else
        log_error "백엔드 서비스 시작 실패"
        exit 1
    fi

    cd "$PROJECT_ROOT" || exit 1
else
    log_warning "백엔드 스크립트를 건너뜁니다"
fi

# ---------- 3단계: 프론트엔드 서비스 시작 ----------
if [[ -f "$FRONTEND_SCRIPT" ]]; then
    log_step "3단계: 프론트엔드 서비스 시작 중..."
    echo "   스크립트: $FRONTEND_SCRIPT"

    cd "$(dirname "$FRONTEND_SCRIPT")" || {
        log_error "프론트엔드 스크립트 디렉토리로 이동 실패"
        exit 1
    }

    if run_with_auto_input "./$(basename "$FRONTEND_SCRIPT")" "프론트엔드"; then
        log_success "프론트엔드 서비스 시작 완료"

        # 프론트엔드 서비스 준비 대기
        echo "   프론트엔드 서비스 안정화 대기 중..."
        sleep 10

        # Streamlit 서버 연결 확인
        echo -n "   Streamlit 서버 확인... "
        max_attempts=20
        attempt=0
        frontend_ready=false

        while [[ $attempt -lt $max_attempts ]] && [[ $frontend_ready == false ]]; do
            if curl -s --connect-timeout 2 "http://localhost:8501" > /dev/null 2>&1; then
                frontend_ready=true
                echo -e "${GREEN}✅${NC}"
                break
            fi
            echo -n "."
            sleep 3
            attempt=$((attempt + 1))
        done

        if [[ $frontend_ready == false ]]; then
            echo -e "${YELLOW}⚠️${NC}"
            log_warning "Streamlit 서버 응답 시간 초과"
        fi
    else
        log_error "프론트엔드 서비스 시작 실패"
        exit 1
    fi

    cd "$PROJECT_ROOT" || exit 1
else
    log_warning "프론트엔드 스크립트를 건너뜁니다"
fi

# ---------- 최종 상태 확인 ----------
log_step "전체 시스템 상태 확인 중..."

# 서비스별 상태 확인
services_status=()

# 인프라 서비스
echo "   🏗️ 인프라 서비스:"
if curl -s --connect-timeout 3 "http://localhost:6333/health" > /dev/null 2>&1; then
    echo "      - Qdrant: ✅ 정상"
    services_status+=("qdrant:ok")
else
    echo "      - Qdrant: ❌ 오류"
    services_status+=("qdrant:error")
fi

if (command -v redis-cli &> /dev/null && redis-cli -h localhost -p 6379 ping > /dev/null 2>&1) || \
   (docker exec redis-service redis-cli ping > /dev/null 2>&1); then
    echo "      - Redis: ✅ 정상"
    services_status+=("redis:ok")
else
    echo "      - Redis: ❌ 오류"
    services_status+=("redis:error")
fi

# 백엔드 서비스
echo "   🔧 백엔드 서비스:"
if curl -s --connect-timeout 3 "http://localhost:18000/v1/health" > /dev/null 2>&1; then
    echo "      - FastAPI: ✅ 정상"
    services_status+=("fastapi:ok")
else
    echo "      - FastAPI: ❌ 오류"
    services_status+=("fastapi:error")
fi

# Celery 프로세스 확인
if command -v pgrep &> /dev/null && pgrep -f "celery.*worker" > /dev/null 2>&1; then
    echo "      - Celery: ✅ 정상"
    services_status+=("celery:ok")
else
    echo "      - Celery: ❌ 오류"
    services_status+=("celery:error")
fi

# 프론트엔드 서비스
echo "   🎨 프론트엔드 서비스:"
if curl -s --connect-timeout 3 "http://localhost:8501" > /dev/null 2>&1; then
    echo "      - Streamlit: ✅ 정상"
    services_status+=("streamlit:ok")
else
    echo "      - Streamlit: ❌ 오류"
    services_status+=("streamlit:error")
fi

# 포트 상태 요약
echo -e "\n   📊 포트 상태:"
main_ports=(6333 6379 18000 8501)
port_names=("Qdrant" "Redis" "FastAPI" "Streamlit")

for i in "${!main_ports[@]}"; do
    port=${main_ports[$i]}
    name=${port_names[$i]}

    if command -v lsof &> /dev/null && lsof -i:$port > /dev/null 2>&1; then
        echo "      - 포트 $port ($name): ✅ 사용 중"
    else
        echo "      - 포트 $port ($name): ❌ 사용 안함"
    fi
done

# 성공한 서비스 개수 계산
successful_services=$(echo "${services_status[@]}" | grep -o ":ok" | wc -l)
total_services=${#services_status[@]}

# ---------- 완료 메시지 ----------
START_ALL_END_TIME=$(date '+%Y-%m-%d %H:%M:%S')

echo -e "\n${CYAN}🎉 GTOne RAG 전체 시스템 시작 완료!${NC}"

echo -e "\n${BLUE}📊 시작 요약:${NC}"
echo "   시작 모드: $(if [[ "$AUTO_MODE" == true ]]; then echo "자동 모드"; else echo "대화형 모드"; fi)"
echo "   시작 시간: $START_ALL_TIME"
echo "   완료 시간: $START_ALL_END_TIME"
echo "   성공한 서비스: $successful_services/$total_services"
echo "   프로젝트 루트: $PROJECT_ROOT"

if [[ $successful_services -eq $total_services ]]; then
    echo -e "\n${GREEN}✨ 모든 서비스가 성공적으로 시작되었습니다! ✨${NC}"

    echo -e "\n${YELLOW}🌐 서비스 접속 정보:${NC}"
    echo "   - 🎨 웹 UI: http://localhost:8501"
    echo "   - 📊 API 문서: http://localhost:18000/docs"
    echo "   - 🗄️ Qdrant Dashboard: http://localhost:6333/dashboard"
    echo "   - 🔧 API 헬스체크: http://localhost:18000/v1/health"

    # 자동으로 브라우저 열기 (자동 모드가 아닌 경우에만)
    if [[ "$AUTO_MODE" != true ]]; then
        echo -e "\n${YELLOW}🌐 브라우저에서 웹 UI를 여시겠습니까? (y/n)${NC}"
        read -r -t 10 open_browser || open_browser="n"

        if [[ "$open_browser" =~ ^[Yy]$ ]]; then
            OS_TYPE=$(uname -s)
            if [[ "$OS_TYPE" == "Darwin" ]]; then
                open "http://localhost:8501" 2>/dev/null
            elif [[ "$OS_TYPE" == "Linux" ]]; then
                if command -v xdg-open &> /dev/null; then
                    xdg-open "http://localhost:8501" 2>/dev/null &
                fi
            fi
            echo "   브라우저에서 웹 UI를 열었습니다."
        fi
    fi
else
    echo -e "\n${YELLOW}⚠️ 일부 서비스가 완전히 시작되지 않았습니다.${NC}"
    echo "   문제 해결:"
    echo "   1. 로그 확인: tail -f */logs/*.log"
    echo "   2. 개별 서비스 재시작"
    echo "   3. 전체 재시작: ./scripts/stop_all.sh && ./scripts/start_all.sh"
fi

echo -e "\n${YELLOW}🛠️ 유용한 명령어:${NC}"
echo "   - 전체 중지: ./scripts/stop_all.sh"
echo "   - 상태 확인: ./scripts/status_all.sh"
echo "   - 로그 확인: tail -f logs/*.log"
echo "   - 임시파일 정리: ./scripts/cleanup_all.sh"

echo -e "\n${GREEN}🚀 GTOne RAG 시스템이 준비되었습니다! 🚀${NC}"

exit 0