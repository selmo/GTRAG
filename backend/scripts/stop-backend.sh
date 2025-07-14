#!/bin/bash

echo "🛑 GTOne RAG - 백엔드 서비스 종료"
echo "================================"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 종료 시작 시간 기록
STOP_START_TIME=$(date)
echo "종료 시작 시간: $STOP_START_TIME"

# 1. 현재 디렉토리 확인
if [[ ! -f "api/main.py" ]]; then
    echo -e "${RED}❌ backend 디렉토리에서 실행해주세요.${NC}"
    echo "현재 위치: $(pwd)"
    exit 1
fi

echo -e "${GREEN}✅ 백엔드 디렉토리 확인됨${NC}"

# 2. PID 파일에서 프로세스 종료
echo -e "\n${BLUE}📋 등록된 프로세스 종료 중...${NC}"

stop_service() {
    local pidfile=$1
    local service_name=$2
    local timeout=${3:-10}

    if [[ -f "$pidfile" ]]; then
        PID=$(cat "$pidfile")
        echo -n "   $service_name (PID: $PID) 종료 중... "

        # 프로세스가 실제로 실행 중인지 확인
        if kill -0 "$PID" 2>/dev/null; then
            # SIGTERM으로 정상 종료 시도
            kill "$PID" 2>/dev/null

            # 지정된 시간만큼 대기
            for i in $(seq 1 $timeout); do
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

# 각 서비스 종료 (역순)
stop_service ".celery.pid" "Celery 워커" 15
stop_service ".api.pid" "FastAPI 서버" 10

# 3. 포트 기반 프로세스 정리
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

# 백엔드 포트들 정리
cleanup_port 18000 "FastAPI"

# 4. 프로세스명 기반 추가 정리
echo -e "\n${BLUE}🧹 프로세스명 기반 추가 정리...${NC}"

# Uvicorn 프로세스 찾기
echo -n "   Uvicorn 프로세스 확인... "
UVICORN_PIDS=$(pgrep -f "uvicorn.*api.main" 2>/dev/null)
if [[ -n "$UVICORN_PIDS" ]]; then
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
if [[ -n "$CELERY_PIDS" ]]; then
    echo -e "${YELLOW}발견됨${NC}"
    for PID in $CELERY_PIDS; do
        echo "      Celery PID $PID 종료..."
        kill -9 "$PID" 2>/dev/null
    done
else
    echo -e "${GREEN}없음${NC}"
fi

# Python 백엔드 관련 프로세스 찾기
echo -n "   Python 백엔드 프로세스 확인... "
PYTHON_BACKEND_PIDS=$(pgrep -f "python.*api/" 2>/dev/null)
if [[ -n "$PYTHON_BACKEND_PIDS" ]]; then
    echo -e "${YELLOW}발견됨${NC}"
    for PID in $PYTHON_BACKEND_PIDS; do
        echo "      Python 백엔드 PID $PID 종료..."
        kill -9 "$PID" 2>/dev/null
    done
else
    echo -e "${GREEN}없음${NC}"
fi

# 5. 최종 포트 상태 확인
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
check_final_port_status 18000 "FastAPI" || all_ports_clear=false

# 6. 임시 파일 정리
echo -e "\n${BLUE}🗑️ 임시 파일 정리...${NC}"

# PID 파일들 정리 (혹시 남아있다면)
for pidfile in .api.pid .celery.pid; do
    if [[ -f "$pidfile" ]]; then
        echo "   $pidfile 삭제..."
        rm "$pidfile"
    fi
done

# 백엔드 정보 파일 정리
if [[ -f ".backend_info" ]]; then
    echo "   .backend_info 삭제..."
    rm ".backend_info"
fi

# 7. 가상환경 비활성화 안내
echo -e "\n${BLUE}🐍 가상환경 상태...${NC}"
if [[ "$VIRTUAL_ENV" ]]; then
    echo -e "   현재 가상환경: ${GREEN}$VIRTUAL_ENV${NC}"
    echo -e "   ${YELLOW}deactivate${NC} 명령으로 가상환경을 비활성화할 수 있습니다."
else
    echo "   가상환경 없음"
fi

# 8. 로그 파일 관리
echo -e "\n${BLUE}📋 로그 파일 관리...${NC}"

if [[ -d "logs" ]]; then
    log_count=$(find logs -name "*.log" 2>/dev/null | wc -l)
    if [[ $log_count -gt 0 ]]; then
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

# 9. 서비스 의존성 상태 확인
echo -e "\n${BLUE}🔗 외부 서비스 상태 확인...${NC}"

# Qdrant 상태 (참고용)
echo -n "   Qdrant 서비스: "
if curl -s --connect-timeout 3 localhost:6333/health > /dev/null 2>&1; then
    echo -e "${GREEN}실행 중${NC} (독립적으로 실행됨)"
else
    echo -e "${YELLOW}중지됨${NC}"
fi

# Redis 상태 (참고용)
echo -n "   Redis 서비스: "
if redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
    echo -e "${GREEN}실행 중${NC} (독립적으로 실행됨)"
elif command -v docker &> /dev/null && docker exec redis-local redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}실행 중${NC} (Docker)"
else
    echo -e "${YELLOW}중지됨${NC}"
fi

# 10. 최종 결과
echo -e "\n${GREEN}✅ GTOne RAG 백엔드 서비스 종료 완료!${NC}"

if $all_ports_clear; then
    echo -e "\n${GREEN}🎉 모든 백엔드 포트가 정리되었습니다.${NC}"
else
    echo -e "\n${YELLOW}⚠️  일부 포트가 여전히 사용 중입니다.${NC}"
    echo "강제 정리가 필요하면 다음 명령을 실행하세요:"
    echo "   sudo lsof -ti:18000 | xargs sudo kill -9"
fi

echo -e "\n${BLUE}📊 종료 요약:${NC}"
echo "   종료 시작: $STOP_START_TIME"
echo "   종료 완료: $(date)"
echo "   다음 시작: ./scripts/start_backend.sh"

echo -e "\n${YELLOW}💡 참고 사항:${NC}"
echo "   - Qdrant와 Redis는 독립적으로 실행됩니다"
echo "   - 필요시 인프라 스크립트로 별도 관리하세요"
echo "   - 로그 파일은 보존되었습니다 (선택적 삭제)"

echo -e "\n${GREEN}✨ 백엔드 서비스 정리 완료! ✨${NC}"