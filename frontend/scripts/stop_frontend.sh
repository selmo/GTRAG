#!/bin/bash

echo "🛑 GTOne RAG - 프론트엔드 UI 종료"
echo "==============================="

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
if [[ ! -f "ui/Home.py" ]]; then
    echo -e "${RED}❌ frontend 디렉토리에서 실행해주세요.${NC}"
    echo "현재 위치: $(pwd)"
    exit 1
fi

echo -e "${GREEN}✅ 프론트엔드 디렉토리 확인됨${NC}"

# 2. PID 파일에서 프로세스 종료
echo -e "\n${BLUE}📋 등록된 프로세스 종료 중...${NC}"

stop_streamlit_service() {
    local pidfile=".streamlit.pid"
    local timeout=15

    if [[ -f "$pidfile" ]]; then
        PID=$(cat "$pidfile")
        echo -n "   Streamlit 서비스 (PID: $PID) 종료 중... "

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
        echo "   Streamlit PID 파일 없음"
    fi
}

stop_streamlit_service

# 3. 포트 기반 프로세스 정리
echo -e "\n${BLUE}🔍 포트 기반 프로세스 정리...${NC}"

# 기본 Streamlit 포트들 확인
STREAMLIT_PORTS=(8501 8502 8503)

cleanup_streamlit_port() {
    local port=$1

    echo -n "   포트 $port (Streamlit) 확인... "

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

# 모든 Streamlit 포트 정리
for port in "${STREAMLIT_PORTS[@]}"; do
    cleanup_streamlit_port $port
done

# 4. 프로세스명 기반 추가 정리
echo -e "\n${BLUE}🧹 프로세스명 기반 추가 정리...${NC}"

# Streamlit 프로세스 찾기
echo -n "   Streamlit 프로세스 확인... "
STREAMLIT_PIDS=$(pgrep -f "streamlit.*ui/" 2>/dev/null)
if [[ -n "$STREAMLIT_PIDS" ]]; then
    echo -e "${YELLOW}발견됨${NC}"
    for PID in $STREAMLIT_PIDS; do
        echo "      Streamlit PID $PID 종료..."
        kill -9 "$PID" 2>/dev/null
    done
else
    echo -e "${GREEN}없음${NC}"
fi

# 일반적인 Streamlit 프로세스 찾기
echo -n "   일반 Streamlit 프로세스 확인... "
GENERAL_STREAMLIT_PIDS=$(pgrep -f "streamlit.*run" 2>/dev/null)
if [[ -n "$GENERAL_STREAMLIT_PIDS" ]]; then
    echo -e "${YELLOW}발견됨${NC}"
    for PID in $GENERAL_STREAMLIT_PIDS; do
        echo "      Streamlit PID $PID 종료..."
        kill -9 "$PID" 2>/dev/null
    done
else
    echo -e "${GREEN}없음${NC}"
fi

# Python UI 관련 프로세스 찾기
echo -n "   Python UI 프로세스 확인... "
PYTHON_UI_PIDS=$(pgrep -f "python.*ui/" 2>/dev/null)
if [[ -n "$PYTHON_UI_PIDS" ]]; then
    echo -e "${YELLOW}발견됨${NC}"
    for PID in $PYTHON_UI_PIDS; do
        echo "      Python UI PID $PID 종료..."
        kill -9 "$PID" 2>/dev/null
    done
else
    echo -e "${GREEN}없음${NC}"
fi

# 5. 최종 포트 상태 확인
echo -e "\n${BLUE}📊 최종 포트 상태 확인...${NC}"

check_final_port_status() {
    local port=$1

    echo -n "   포트 $port: "
    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "${RED}여전히 사용 중${NC}"
        return 1
    else
        echo -e "${GREEN}정리됨${NC}"
        return 0
    fi
}

all_ports_clear=true
for port in "${STREAMLIT_PORTS[@]}"; do
    check_final_port_status $port || all_ports_clear=false
done

# 6. 임시 파일 정리
echo -e "\n${BLUE}🗑️ 임시 파일 정리...${NC}"

# PID 파일들 정리
for pidfile in .streamlit.pid; do
    if [[ -f "$pidfile" ]]; then
        echo "   $pidfile 삭제..."
        rm "$pidfile"
    fi
done

# 프론트엔드 정보 파일 정리
if [[ -f ".frontend_info" ]]; then
    echo "   .frontend_info 삭제..."
    rm ".frontend_info"
fi

# Streamlit 캐시 정리 (선택적)
echo -n "   Streamlit 캐시 정리... "
if [[ -d ".streamlit" ]]; then
    cache_files=$(find .streamlit -name "*.cache" 2>/dev/null | wc -l)
    if [[ $cache_files -gt 0 ]]; then
        echo -e "${YELLOW}$cache_files 개 캐시 파일 발견${NC}"
        echo "   캐시 파일을 삭제하시겠습니까? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            find .streamlit -name "*.cache" -delete 2>/dev/null
            echo -e "      ${GREEN}캐시 파일 삭제됨${NC}"
        else
            echo -e "      ${BLUE}캐시 파일 보존됨${NC}"
        fi
    else
        echo -e "${GREEN}없음${NC}"
    fi
else
    echo -e "${GREEN}없음${NC}"
fi

# 7. 가상환경 상태 안내
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

        # 최근 로그 파일 정보 표시
        if [[ -f "logs/streamlit.log" ]]; then
            log_size=$(du -h logs/streamlit.log 2>/dev/null | cut -f1)
            echo "   - streamlit.log: ${log_size:-unknown}"
        fi

        echo "   로그 파일을 삭제하시겠습니까? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            rm -f logs/*.log
            echo -e "   ${GREEN}로그 파일이 삭제되었습니다.${NC}"
        else
            echo -e "   ${BLUE}로그 파일이 보존되었습니다.${NC}"
            echo "   로그 확인: tail -f logs/streamlit.log"
        fi
    else
        echo "   로그 파일 없음"
    fi
fi

# 9. 백엔드 서비스 상태 확인 (참고용)
echo -e "\n${BLUE}🔗 백엔드 서비스 상태 확인...${NC}"

# API 서버 상태 (참고용)
API_URL=${API_BASE_URL:-"http://localhost:18000"}
echo -n "   백엔드 API 서버: "
if curl -s --connect-timeout 3 "$API_URL/docs" > /dev/null 2>&1; then
    echo -e "${GREEN}실행 중${NC} ($API_URL)"
else
    echo -e "${YELLOW}중지됨${NC} 또는 연결 불가"
fi

# 10. 브라우저 탭 정리 안내
echo -e "\n${BLUE}🌐 브라우저 정리 안내...${NC}"
echo "   브라우저에서 다음 탭들을 닫으실 수 있습니다:"
for port in "${STREAMLIT_PORTS[@]}"; do
    echo "   - http://localhost:$port"
done

# 11. 최종 결과
echo -e "\n${GREEN}✅ GTOne RAG 프론트엔드 서비스 종료 완료!${NC}"

if $all_ports_clear; then
    echo -e "\n${GREEN}🎉 모든 프론트엔드 포트가 정리되었습니다.${NC}"
else
    echo -e "\n${YELLOW}⚠️  일부 포트가 여전히 사용 중입니다.${NC}"
    echo "강제 정리가 필요하면 다음 명령을 실행하세요:"
    echo "   sudo lsof -ti:8501,8502,8503 | xargs sudo kill -9"
fi

echo -e "\n${BLUE}📊 종료 요약:${NC}"
echo "   종료 시작: $STOP_START_TIME"
echo "   종료 완료: $(date)"
echo "   다음 시작: ./scripts/start_frontend.sh"

echo -e "\n${YELLOW}💡 참고 사항:${NC}"
echo "   - 백엔드 서비스는 독립적으로 실행됩니다"
echo "   - 전체 시스템 종료는 백엔드와 인프라도 별도로 종료하세요"
echo "   - 설정 파일과 로그는 보존되었습니다"

echo -e "\n${YELLOW}🔄 다음 실행 시:${NC}"
echo "   1. 백엔드 확인: curl http://localhost:18000/docs"
echo "   2. 프론트엔드 시작: ./scripts/start_frontend.sh"
echo "   3. 브라우저에서 http://localhost:8501 접속"

echo -e "\n${GREEN}✨ 프론트엔드 서비스 정리 완료! ✨${NC}"