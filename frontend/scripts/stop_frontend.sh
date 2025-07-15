#!/bin/bash

echo "🛑 GTOne RAG - 프론트엔드 UI 종료"
echo "=================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 경로 설정
SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$FRONTEND_DIR")"

echo -e "\n${BLUE}📁 경로 확인...${NC}"
echo "   프로젝트 루트: $PROJECT_ROOT"
echo "   프론트엔드 디렉토리: $FRONTEND_DIR"

# 현재 디렉토리 확인
CURRENT_DIR="$(pwd)"
echo "   현재 실행 디렉토리: $CURRENT_DIR"

# GTRAG 루트에서 실행되었는지 확인
if [[ ! -d "frontend" ]] || [[ ! -d "backend" ]]; then
    echo -e "${YELLOW}⚠️  GTRAG 프로젝트 루트에서 실행하는 것을 권장합니다.${NC}"
    echo "현재 위치: $CURRENT_DIR"
    echo "권장 실행: cd /path/to/GTRAG && frontend/scripts/stop_frontend.sh"
fi

# frontend 디렉토리로 이동
cd "$FRONTEND_DIR" || {
    echo -e "${RED}❌ 프론트엔드 디렉토리로 이동할 수 없습니다: $FRONTEND_DIR${NC}"
    exit 1
}

echo -e "${GREEN}✅ 프론트엔드 디렉토리로 이동: $(pwd)${NC}"

# 서비스 정보 파일 확인
if [[ -f ".frontend_info" ]]; then
    echo -e "\n${BLUE}📋 기존 서비스 정보 확인...${NC}"

    # 서비스 정보 읽기
    source .frontend_info 2>/dev/null || true

    if [[ -n "$STREAMLIT_PID" ]]; then
        echo "   저장된 PID: $STREAMLIT_PID"
        echo "   Conda 환경: $CONDA_ENV"
        echo "   서비스 URL: $STREAMLIT_URL"
    fi
else
    echo -e "\n${YELLOW}⚠️  서비스 정보 파일이 없습니다.${NC}"
fi

# 1. PID 파일로 프로세스 종료
echo -e "\n${BLUE}🔍 실행 중인 Streamlit 프로세스 확인...${NC}"

processes_killed=0

if [[ -f ".streamlit.pid" ]]; then
    PID=$(cat ".streamlit.pid")
    echo "   PID 파일에서 찾은 프로세스: $PID"

    if kill -0 "$PID" 2>/dev/null; then
        echo -n "   프로세스 $PID 종료 중... "

        # SIGTERM 시도
        kill "$PID" 2>/dev/null
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
    rm ".streamlit.pid"
    echo "   PID 파일 삭제됨"
else
    echo "   PID 파일이 없습니다."
fi

# 2. 포트 기반으로 프로세스 찾기
echo -e "\n${BLUE}🔍 포트 기반 프로세스 검색...${NC}"

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
        PIDs=$(lsof -ti:$port 2>/dev/null)

        if [[ -n "$PIDs" ]]; then
            echo "프로세스 발견"

            for pid in $PIDs; do
                # 프로세스 정보 확인
                if ps -p $pid -o comm= | grep -q streamlit; then
                    echo "     Streamlit 프로세스 $pid 종료 중..."

                    # SIGTERM 시도
                    kill $pid 2>/dev/null
                    sleep 2

                    # 강제 종료
                    if kill -0 $pid 2>/dev/null; then
                        kill -9 $pid 2>/dev/null
                        echo "     강제 종료됨"
                    else
                        echo "     정상 종료됨"
                    fi

                    processes_killed=$((processes_killed + 1))
                else
                    echo "     비-Streamlit 프로세스 $pid (건너뜀)"
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
echo -e "\n${BLUE}🔍 이름 기반 Streamlit 프로세스 검색...${NC}"

if command -v pgrep &> /dev/null; then
    streamlit_pids=$(pgrep -f "streamlit.*ui/Home.py\|streamlit.*streamlit_app.py" 2>/dev/null)

    if [[ -n "$streamlit_pids" ]]; then
        echo "   발견된 Streamlit 프로세스들:"

        for pid in $streamlit_pids; do
            cmd=$(ps -p $pid -o args= 2>/dev/null)
            echo "     PID $pid: $cmd"

            echo -n "     종료 중... "
            kill $pid 2>/dev/null
            sleep 2

            if kill -0 $pid 2>/dev/null; then
                kill -9 $pid 2>/dev/null
                echo "강제 종료"
            else
                echo "정상 종료"
            fi

            processes_killed=$((processes_killed + 1))
        done
    else
        echo "   이름 기반으로 찾은 Streamlit 프로세스가 없습니다."
    fi
else
    echo "   pgrep 명령어가 없습니다."
fi

# 4. 정리 작업
echo -e "\n${BLUE}🧹 정리 작업...${NC}"

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

# 로그 파일은 유지하되 rotate
if [[ -f "logs/streamlit.log" ]]; then
    if [[ -s "logs/streamlit.log" ]]; then
        # 로그 파일이 비어있지 않으면 백업
        timestamp=$(date +"%Y%m%d_%H%M%S")
        mv "logs/streamlit.log" "logs/streamlit_${timestamp}.log"
        echo "   로그 파일이 logs/streamlit_${timestamp}.log로 백업됨"

        # 오래된 로그 파일들 정리 (10개 이상이면 오래된 것 삭제)
        log_count=$(ls logs/streamlit_*.log 2>/dev/null | wc -l)
        if [[ $log_count -gt 10 ]]; then
            ls -t logs/streamlit_*.log | tail -n +11 | xargs rm -f
            echo "   오래된 로그 파일들 정리됨"
        fi
    else
        rm "logs/streamlit.log"
        echo "   빈 로그 파일 삭제됨"
    fi
fi

# 5. Conda 환경 정리 (선택적)
if [[ -n "$CONDA_ENV" ]]; then
    echo -e "\n${BLUE}🐍 Conda 환경 관리...${NC}"
    echo "   현재 Conda 환경: $CONDA_ENV"

    # 환경 비활성화는 스크립트에서는 의미가 없으므로 안내만
    echo "   Conda 환경을 비활성화하려면: conda deactivate"
    echo "   환경을 완전히 제거하려면: conda env remove -n $CONDA_ENV"
fi

# 6. 최종 상태 확인
echo -e "\n${BLUE}📊 종료 후 상태 확인...${NC}"

# 포트 상태 재확인
for port in "${PORTS_TO_CHECK[@]}"; do
    echo -n "   포트 $port: "
    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "${YELLOW}여전히 사용 중${NC}"
    else
        echo -e "${GREEN}사용 가능${NC}"
    fi
done

# 남은 Streamlit 프로세스 확인
if command -v pgrep &> /dev/null; then
    remaining_streamlit=$(pgrep -f streamlit 2>/dev/null | wc -l)
    echo "   남은 Streamlit 프로세스: $remaining_streamlit개"

    if [[ $remaining_streamlit -gt 0 ]]; then
        echo -e "${YELLOW}   ⚠️  일부 Streamlit 프로세스가 남아있을 수 있습니다.${NC}"
        echo "   수동 확인: ps aux | grep streamlit"
        echo "   수동 종료: pkill -f streamlit"
    fi
fi

# 7. 완료 메시지
echo -e "\n${GREEN}✅ GTOne RAG 프론트엔드 종료 완료!${NC}"

if [[ $processes_killed -gt 0 ]]; then
    echo -e "${GREEN}   $processes_killed개의 프로세스가 종료되었습니다.${NC}"
else
    echo -e "${YELLOW}   종료할 실행 중인 프로세스가 없었습니다.${NC}"
fi

echo -e "\n${YELLOW}📋 종료 후 정보:${NC}"
echo -e "   📁 로그 위치: $FRONTEND_DIR/logs/"
echo -e "   🔧 설정 위치: $FRONTEND_DIR/.streamlit/"
echo -e "   🐍 Conda 환경: ${CONDA_ENV:-"환경 정보 없음"}"

echo -e "\n${YELLOW}💡 다시 시작하려면:${NC}"
echo -e "   cd $PROJECT_ROOT"
echo -e "   frontend/scripts/start_frontend.sh"

echo -e "\n${YELLOW}🧹 추가 정리 명령어:${NC}"
echo -e "   전체 로그 삭제: rm -rf $FRONTEND_DIR/logs/*"
echo -e "   설정 초기화: rm -rf $FRONTEND_DIR/.streamlit/"
echo -e "   Conda 환경 제거: conda env remove -n ${CONDA_ENV:-"GTRAG"}"

# 정리 완료 확인
echo -e "\n${BLUE}정리가 완료되었습니다. 안전하게 종료할 수 있습니다.${NC}"