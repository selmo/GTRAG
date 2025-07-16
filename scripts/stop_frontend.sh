#!/bin/bash

echo "🛑 GTOne RAG - 프론트엔드 UI 종료"
echo "=================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 로그 함수
log_info() { echo -e "${BLUE}ℹ️ $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# 종료 시작 시간
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
        if [[ -d "$current_dir/frontend" && -d "$current_dir/backend" ]] || \
           [[ -f "$current_dir/backend/api/main.py" ]] || \
           [[ -f "$current_dir/frontend/requirements-frontend.txt" ]] || \
           [[ -f "$current_dir/frontend/requirements.txt" ]]; then
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
    echo "현재 위치에서 프론트엔드 프로세스만 종료하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        PROJECT_ROOT="$(pwd)"
        log_warning "현재 디렉토리를 프로젝트 루트로 설정: $PROJECT_ROOT"
    else
        exit 1
    fi
fi

# frontend 디렉토리 찾기
if [[ -d "$PROJECT_ROOT/frontend" ]]; then
    FRONTEND_DIR="$PROJECT_ROOT/frontend"
elif [[ -f "$PROJECT_ROOT/requirements-frontend.txt" ]] || [[ -d "$PROJECT_ROOT/ui" ]] || [[ -d "$PROJECT_ROOT/.streamlit" ]]; then
    # 현재 디렉토리가 frontend 디렉토리인 경우
    FRONTEND_DIR="$PROJECT_ROOT"
    PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
else
    log_warning "frontend 디렉토리를 찾을 수 없습니다. 현재 디렉토리에서 진행합니다."
    FRONTEND_DIR="$PROJECT_ROOT"
fi

cd "$FRONTEND_DIR" || {
    log_error "프론트엔드 디렉토리로 이동할 수 없습니다: $FRONTEND_DIR"
    exit 1
}

log_info "프로젝트 루트: $PROJECT_ROOT"
log_info "프론트엔드 디렉토리: $FRONTEND_DIR"
log_success "작업 디렉토리: $(pwd)"

# 서비스 정보 파일 확인
if [[ -f ".frontend_info" ]]; then
    log_info "기존 서비스 정보 확인..."

    # 서비스 정보 읽기
    source .frontend_info 2>/dev/null || true

    if [[ -n "$STREAMLIT_PID" ]]; then
        echo "   저장된 PID: $STREAMLIT_PID"
        echo "   Conda 환경: $CONDA_ENV"
        echo "   서비스 URL: $STREAMLIT_URL"
    fi
else
    log_warning "서비스 정보 파일이 없습니다."
fi

# 1. PID 파일로 프로세스 종료
log_info "실행 중인 Streamlit 프로세스 확인..."

processes_killed=0

# 여러 위치에서 PID 파일 찾기
pid_locations=(".streamlit.pid" "frontend/.streamlit.pid" "../.streamlit.pid")
found_pid_file=""

for pid_file in "${pid_locations[@]}"; do
    if [[ -f "$pid_file" ]]; then
        found_pid_file="$pid_file"
        break
    fi
done

if [[ -n "$found_pid_file" ]]; then
    PID=$(cat "$found_pid_file")
    echo "   PID 파일에서 찾은 프로세스: $PID ($found_pid_file)"

    if kill -0 "$PID" 2>/dev/null; then
        echo -n "   프로세스 $PID 종료 중... "

        # SIGTERM 시도
        kill -TERM "$PID" 2>/dev/null
        sleep 3

        # 프로세스가 여전히 살아있으면 SIGKILL
        if kill -0 "$PID" 2>/dev/null; then
            echo "강제 종료"
            kill -9 "$PID" 2>/dev/null
            sleep 1
        else
            echo "정상 종료"
        fi

        processes_killed=$((processes_killed + 1))
    else
        echo "   프로세스 $PID가 이미 종료되었습니다."
    fi

    # PID 파일 삭제
    rm "$found_pid_file"
    echo "   PID 파일 삭제됨: $found_pid_file"
else
    echo "   PID 파일이 없습니다."
fi

# 2. 포트 기반으로 프로세스 찾기
log_info "포트 기반 프로세스 검색..."

# 기본 포트들 확인
PORTS_TO_CHECK=(8501 8502 8503)

# 환경변수에서 포트 가져오기
if [[ -n "$STREAMLIT_SERVER_PORT" ]]; then
    PORTS_TO_CHECK=("$STREAMLIT_SERVER_PORT" "${PORTS_TO_CHECK[@]}")
fi

for port in "${PORTS_TO_CHECK[@]}"; do
    echo -n "   포트 $port 확인... "

    # lsof로 포트 사용 프로세스 찾기
    if command -v lsof &> /dev/null; then
        PIDs=$(lsof -ti:$port 2>/dev/null || true)

        if [[ -n "$PIDs" ]]; then
            echo "프로세스 발견"

            for pid in $PIDs; do
                # 프로세스 정보 확인
                process_name=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
                if [[ "$process_name" == *"streamlit"* ]] || ps -p $pid -o args= 2>/dev/null | grep -q streamlit; then
                    echo "     Streamlit 프로세스 $pid 종료 중..."

                    # SIGTERM 시도
                    kill -TERM $pid 2>/dev/null || true
                    sleep 2

                    # 강제 종료
                    if kill -0 $pid 2>/dev/null; then
                        kill -9 $pid 2>/dev/null || true
                        echo "     강제 종료됨"
                    else
                        echo "     정상 종료됨"
                    fi

                    processes_killed=$((processes_killed + 1))
                else
                    echo "     비-Streamlit 프로세스 $pid (건너뜀): $process_name"
                fi
            done
        else
            echo "사용 안함"
        fi
    else
        echo "lsof 명령어 없음"
    fi
done

# 3. 이름 기반으로 Streamlit 프로세스 찾기
log_info "이름 기반 Streamlit 프로세스 검색..."

if command -v pgrep &> /dev/null; then
    # 다양한 Streamlit 프로세스 패턴 검색
    streamlit_patterns=(
        "streamlit.*ui/Home.py"
        "streamlit.*streamlit_app.py"
        "streamlit.*app.py"
        "streamlit run"
    )

    all_streamlit_pids=""

    for pattern in "${streamlit_patterns[@]}"; do
        pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            all_streamlit_pids="$all_streamlit_pids $pids"
        fi
    done

    # 중복 제거
    if [[ -n "$all_streamlit_pids" ]]; then
        streamlit_pids=$(echo $all_streamlit_pids | tr ' ' '\n' | sort -u | tr '\n' ' ')

        echo "   발견된 Streamlit 프로세스들:"

        for pid in $streamlit_pids; do
            if kill -0 $pid 2>/dev/null; then
                cmd=$(ps -p $pid -o args= 2>/dev/null | head -c 80)
                echo "     PID $pid: $cmd..."

                echo -n "     종료 중... "
                kill -TERM $pid 2>/dev/null || true
                sleep 2

                if kill -0 $pid 2>/dev/null; then
                    kill -9 $pid 2>/dev/null || true
                    echo "강제 종료"
                else
                    echo "정상 종료"
                fi

                processes_killed=$((processes_killed + 1))
            fi
        done
    else
        echo "   이름 기반으로 찾은 Streamlit 프로세스가 없습니다."
    fi
else
    echo "   pgrep 명령어가 없습니다."
fi

# 4. 정리 작업
log_info "정리 작업..."

# 임시 파일들 정리
temp_files=(
    ".streamlit.pid"
    ".frontend_info"
    "nohup.out"
)

for file in "${temp_files[@]}"; do
    if [[ -f "$file" ]]; then
        rm "$file"
        echo "   $file 삭제됨"
    fi
done

# 로그 파일 관리
log_info "로그 파일 관리..."

if [[ -d "logs" ]]; then
    log_count=$(find logs -name "*.log" 2>/dev/null | wc -l)
    if [[ $log_count -gt 0 ]]; then
        echo "   $log_count 개의 로그 파일이 있습니다."
        echo "   로그 파일을 삭제하시겠습니까? (y/n/backup)"
        echo "     y: 삭제"
        echo "     n: 보존"
        echo "     backup: 백업 후 삭제"
        read -r response

        case $response in
            [Yy])
                rm -f logs/*.log
                log_success "로그 파일 삭제 완료"
                ;;
            [Bb]*)
                timestamp=$(date '+%Y%m%d_%H%M%S')
                mkdir -p "logs/backup"
                mv logs/*.log "logs/backup/" 2>/dev/null || true
                log_success "로그 파일이 logs/backup/으로 백업됨"
                ;;
            *)
                log_info "로그 파일 보존"
                ;;
        esac
    fi
fi

# 오래된 백업 로그 정리 (선택적)
if [[ -d "logs/backup" ]]; then
    backup_count=$(find logs/backup -name "*.log" 2>/dev/null | wc -l)
    if [[ $backup_count -gt 20 ]]; then
        echo "   백업 로그가 많습니다 ($backup_count 개). 오래된 것을 정리하시겠습니까? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            find logs/backup -name "*.log" -mtime +7 -delete 2>/dev/null || true
            log_success "7일 이전 백업 로그 정리 완료"
        fi
    fi
fi

# 5. Conda 환경 정보
if [[ -n "$CONDA_ENV" ]]; then
    log_info "Conda 환경 정보..."
    echo "   현재 Conda 환경: $CONDA_ENV"
    echo "   환경을 비활성화하려면: conda deactivate"
    if [[ "$CONDA_ENV" != "base" ]]; then
        echo "   환경을 완전히 제거하려면: conda env remove -n $CONDA_ENV"
    fi
fi

# 6. 최종 상태 확인
log_info "종료 후 상태 확인..."

# 포트 상태 재확인
for port in "${PORTS_TO_CHECK[@]}"; do
    echo -n "   포트 $port: "
    if command -v lsof &> /dev/null && lsof -i:$port > /dev/null 2>&1; then
        echo -e "${YELLOW}여전히 사용 중${NC}"
        # 사용 중인 프로세스 정보
        process_info=$(lsof -i:$port 2>/dev/null | tail -n +2 | head -1)
        if [[ -n "$process_info" ]]; then
            echo "      $process_info"
        fi
    else
        echo -e "${GREEN}사용 가능${NC}"
    fi
done

# 남은 Streamlit 프로세스 확인
if command -v pgrep &> /dev/null; then
    remaining_streamlit=$(pgrep -f streamlit 2>/dev/null | wc -l)
    echo "   남은 Streamlit 프로세스: $remaining_streamlit개"

    if [[ $remaining_streamlit -gt 0 ]]; then
        log_warning "일부 Streamlit 프로세스가 남아있을 수 있습니다."
        echo "   수동 확인: ps aux | grep streamlit"
        echo "   수동 종료: pkill -f streamlit"
    fi
fi

# Python 프로세스 상태 (참고용)
if command -v pgrep &> /dev/null; then
    python_count=$(pgrep -f python | wc -l)
    echo "   실행 중인 Python 프로세스: $python_count개"
fi

# 7. 완료 메시지
STOP_END_TIME=$(date '+%Y-%m-%d %H:%M:%S')

if [[ $processes_killed -gt 0 ]]; then
    log_success "GTOne RAG 프론트엔드 종료 완료!"
    echo -e "${GREEN}   $processes_killed개의 프로세스가 종료되었습니다.${NC}"
else
    log_success "GTOne RAG 프론트엔드 종료 완료!"
    echo -e "${YELLOW}   종료할 실행 중인 프로세스가 없었습니다.${NC}"
fi

echo -e "\n${BLUE}📊 종료 요약:${NC}"
echo "   종료 시작: $STOP_START_TIME"
echo "   종료 완료: $STOP_END_TIME"
echo "   프로젝트 루트: $PROJECT_ROOT"
echo "   프론트엔드 디렉토리: $FRONTEND_DIR"
echo "   종료된 프로세스 수: $processes_killed개"

echo -e "\n${YELLOW}📋 종료 후 정보:${NC}"
echo -e "   📁 로그 위치: $FRONTEND_DIR/logs/"
echo -e "   🔧 설정 위치: $FRONTEND_DIR/.streamlit/"
echo -e "   🐍 Conda 환경: ${CONDA_ENV:-"환경 정보 없음"}"
echo -e "   🐍 Conda 환경: ${CONDA_ENV:-"환경 정보 없음"}"

echo -e "\n${YELLOW}💡 다시 시작하려면:${NC}"
if [[ -f "$PROJECT_ROOT/frontend/scripts/start_frontend.sh" ]]; then
    echo -e "   cd $PROJECT_ROOT"
    echo -e "   ./frontend/scripts/start_frontend.sh"
elif [[ -f "scripts/start_frontend.sh" ]]; then
    echo -e "   ./scripts/start_frontend.sh"
else
    echo -e "   start_frontend.sh 스크립트를 찾아서 실행하세요"
fi

echo -e "\n${YELLOW}🧹 추가 정리 명령어:${NC}"
echo -e "   전체 로그 삭제: rm -rf $FRONTEND_DIR/logs/*"
echo -e "   설정 초기화: rm -rf $FRONTEND_DIR/.streamlit/"
if [[ -n "$CONDA_ENV" && "$CONDA_ENV" != "base" ]]; then
    echo -e "   Conda 환경 제거: conda env remove -n $CONDA_ENV"
fi

echo -e "\n${YELLOW}🔧 문제 해결:${NC}"
echo -e "   - 포트 확인: ${YELLOW}lsof -i:8501${NC}"
echo -e "   - 프로세스 확인: ${YELLOW}ps aux | grep streamlit${NC}"
echo -e "   - 강제 종료: ${YELLOW}pkill -f streamlit${NC}"

echo -e "\n${GREEN}✅ 프론트엔드 서비스 종료 완료!${NC}"

exit 0