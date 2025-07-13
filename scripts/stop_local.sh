#!/bin/bash

echo "🛑 GTOne RAG System 종료 중..."

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 종료 시작 시간 기록
STOP_START_TIME=$(date)
echo "종료 시작 시간: $STOP_START_TIME"

# 1. PID 파일에서 프로세스 종료
echo -e "\n${BLUE}📋 등록된 프로세스 종료 중...${NC}"

stop_service() {
    local pidfile=$1
    local service_name=$2

    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        echo -n "   $service_name (PID: $PID) 종료 중... "

        # 프로세스가 실제로 실행 중인지 확인
        if kill -0 "$PID" 2>/dev/null; then
            # SIGTERM으로 정상 종료 시도
            kill "$PID" 2>/dev/null

            # 최대 10초 대기
            for i in {1..10}; do
                if ! kill -0 "$PID" 2>/dev/null; then
                    echo -e "${GREEN}완료${NC}"
                    break
                fi
                sleep 1
            done

            # 여전히 실행 중이면 강제 종료
            if kill -0 "$PID" 2>/dev/null; then
                echo -e "${YELLOW}강제 종료${NC}"
                kill -9 "$PID" 2>/dev/null
                sleep 1
            fi
        else
            echo -e "${YELLOW}이미 종료됨${NC}"
        fi

        rm "$pidfile"
    else
        echo "   $service_name PID 파일 없음"
    fi
}

# 각 서비스 종료
stop_service ".streamlit.pid" "Streamlit UI"
stop_service ".api.pid" "FastAPI 서버"
stop_service ".celery.pid" "Celery 워커"

# 2. 포트 기반 프로세스 정리
echo -e "\n${BLUE}🔍 포트 기반 프로세스 정리...${NC}"

cleanup_port() {
    local port=$1
    local service_name=$2

    echo -n "   포트 $port ($service_name) 확인... "

    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "${YELLOW}사용 중${NC}"
        echo "      프로세스 정리 중..."

        # 프로세스 ID 찾기
        PIDS=$(lsof -ti:$port)

        for PID in $PIDS; do
            echo "      PID $PID 종료 중..."
            # 정상 종료 시도
            kill "$PID" 2>/dev/null
            sleep 2

            # 여전히 실행 중이면 강제 종료
            if kill -0 "$PID" 2>/dev/null; then
                echo "      PID $PID 강제 종료..."
                kill -9 "$PID" 2>/dev/null
            fi
        done
    else
        echo -e "${GREEN}정리됨${NC}"
    fi
}

# 주요 포트 정리
cleanup_port 8501 "Streamlit"
cleanup_port 18000 "FastAPI"

# 3. 추가 관련 프로세스 정리
echo -e "\n${BLUE}🧹 관련 프로세스 추가 정리...${NC}"

# Streamlit 프로세스 찾기
echo -n "   Streamlit 프로세스 확인... "
STREAMLIT_PIDS=$(pgrep -f "streamlit.*streamlit_app.py" 2>/dev/null)
if [ -n "$STREAMLIT_PIDS" ]; then
    echo -e "${YELLOW}발견됨${NC}"
    for PID in $STREAMLIT_PIDS; do
        echo "      Streamlit PID $PID 종료..."
        kill -9 "$PID" 2>/dev/null
    done
else
    echo -e "${GREEN}없음${NC}"
fi

# Uvicorn 프로세스 찾기
echo -n "   Uvicorn 프로세스 확인... "
UVICORN_PIDS=$(pgrep -f "uvicorn.*api.main" 2>/dev/null)
if [ -n "$UVICORN_PIDS" ]; then
    echo -e "${YELLOW}발견됨${NC}"
    for PID in $UVICORN_PIDS; do
        echo "      Uvicorn PID $PID 종료..."
        kill -9 "$PID" 2>/dev/null
    done
else
    echo -e "${GREEN}없음${NC}"
fi

# Celery 프로세스 찾기
echo -n "   Celery 프로세스 확인... "
CELERY_PIDS=$(pgrep -f "celery.*api.main" 2>/dev/null)
if [ -n "$CELERY_PIDS" ]; then
    echo -e "${YELLOW}발견됨${NC}"
    for PID in $CELERY_PIDS; do
        echo "      Celery PID $PID 종료..."
        kill -9 "$PID" 2>/dev/null
    done
else
    echo -e "${GREEN}없음${NC}"
fi

# 4. 최종 포트 상태 확인
echo -e "\n${BLUE}📊 최종 포트 상태 확인...${NC}"

check_final_port_status() {
    local port=$1
    local service_name=$2

    echo -n "   포트 $port ($service_name): "
    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "${RED}여전히 사용 중${NC}"
        return 1
    else
        echo -e "${GREEN}정리됨${NC}"
        return 0
    fi
}

all_ports_clear=true
check_final_port_status 8501 "Streamlit" || all_ports_clear=false
check_final_port_status 18000 "FastAPI" || all_ports_clear=false

# 5. 임시 파일 정리
echo -e "\n${BLUE}🗑️ 임시 파일 정리...${NC}"

# PID 파일들 정리 (혹시 남아있다면)
for pidfile in .api.pid .celery.pid .streamlit.pid; do
    if [ -f "$pidfile" ]; then
        echo "   $pidfile 삭제..."
        rm "$pidfile"
    fi
done

# 환경 정보 파일 정리
if [ -f ".env_info" ]; then
    echo "   .env_info 삭제..."
    rm ".env_info"
fi

# 6. 로그 파일 관리
echo -e "\n${BLUE}📋 로그 파일 관리...${NC}"

if [ -d "logs" ]; then
    log_count=$(find logs -name "*.log" | wc -l)
    if [ $log_count -gt 0 ]; then
        echo "   $log_count 개의 로그 파일이 있습니다."
        echo "   로그 파일을 삭제하시겠습니까? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            rm -f logs/*.log
            echo -e "   ${GREEN}로그 파일이 삭제되었습니다.${NC}"
        else
            echo -e "   ${BLUE}로그 파일이 보존되었습니다.${NC}"
        fi
    else
        echo "   로그 파일 없음"
    fi
fi

# 7. Conda 환경 정보
echo -e "\n${BLUE}🐍 Conda 환경 정보...${NC}"
if command -v conda &> /dev/null; then
    current_env=$(conda info --envs | grep '*' | awk '{print $1}')
    if [ "$current_env" = "GTRAG" ]; then
        echo -e "   현재 환경: ${GREEN}GTRAG (활성화됨)${NC}"
        echo -e "   ${YELLOW}conda deactivate${NC} 명령으로 환경을 비활성화할 수 있습니다."
    else
        echo -e "   현재 환경: $current_env"
    fi
else
    echo "   Conda 없음"
fi

# 8. 최종 결과
echo -e "\n${GREEN}✅ GTOne RAG System 종료 완료!${NC}"

if $all_ports_clear; then
    echo -e "\n${GREEN}🎉 모든 포트가 정리되었습니다.${NC}"
else
    echo -e "\n${YELLOW}⚠️  일부 포트가 여전히 사용 중입니다.${NC}"
    echo "시스템을 재부팅하거나 다음 명령으로 강제 정리하세요:"
    echo "   sudo lsof -ti:8501,18000 | xargs sudo kill -9"
fi

echo -e "\n${BLUE}📊 종료 요약:${NC}"
echo "   종료 시작: $STOP_START_TIME"
echo "   종료 완료: $(date)"
echo "   다음 시작: ./start_local.sh"

echo -e "\n${YELLOW}💡 다음에 시작할 때:${NC}"
echo "   1. conda activate GTRAG"
echo "   2. ./start_local.sh"

echo -e "\n${GREEN}✨ 정리 완료! 수고하셨습니다! ✨${NC}"