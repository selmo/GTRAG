#!/bin/bash

echo "🛑 GTOne RAG - 전체 시스템 종료"
echo "==============================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# 종료 시작 시간 기록
OVERALL_STOP_TIME=$(date)
echo "전체 종료 시간: $OVERALL_STOP_TIME"

# 프로젝트 루트 디렉토리 확인
if [[ ! -d "infrastructure" && ! -d "backend" && ! -d "frontend" ]]; then
    echo -e "${RED}❌ 프로젝트 루트 디렉토리에서 실행해주세요.${NC}"
    echo "현재 위치: $(pwd)"
    echo "필요한 디렉토리: infrastructure/, backend/, frontend/ 중 하나 이상"

    # 현재 디렉토리가 하위 디렉토리인지 확인
    if [[ -f "../scripts/stop_all.sh" ]]; then
        echo "상위 디렉토리에서 실행하세요: cd .. && ./scripts/stop_all.sh"
    fi
    exit 1
fi

echo -e "${GREEN}✅ 프로젝트 루트 디렉토리 확인됨${NC}"

# 1. 종료 옵션 확인
echo -e "\n${BLUE}⚙️ 종료 옵션...${NC}"

# 기본 옵션
FORCE_STOP=false
KEEP_DATA=true
VERBOSE=false
CLEANUP_DOCKER=false

# 명령행 인자 처리
while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE_STOP=true
            shift
            ;;
        --clean-data)
            KEEP_DATA=false
            shift
            ;;
        --cleanup-docker)
            CLEANUP_DOCKER=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            echo "사용법: $0 [옵션]"
            echo "옵션:"
            echo "  --force           강제 종료 (SIGKILL 사용)"
            echo "  --clean-data      데이터 볼륨도 삭제"
            echo "  --cleanup-docker  Docker 시스템 정리"
            echo "  --verbose         상세 로그 표시"
            echo "  --help            도움말 표시"
            exit 0
            ;;
        *)
            echo -e "${YELLOW}⚠️  알 수 없는 옵션: $1${NC}"
            shift
            ;;
    esac
done

# 종료 계획 표시
echo "종료 계획:"
echo "   강제 종료: $(if $FORCE_STOP; then echo "활성화"; else echo "정상 종료"; fi)"
echo "   데이터 보존: $(if $KEEP_DATA; then echo "보존"; else echo "삭제"; fi)"
echo "   Docker 정리: $(if $CLEANUP_DOCKER; then echo "수행"; else echo "건너뛰기"; fi)"

# 2. 현재 실행 중인 서비스 확인
echo -e "\n${BLUE}🔍 실행 중인 서비스 확인...${NC}"

# GTOne RAG 관련 포트들
GTRAG_PORTS=(8501 18000 6333 6379)
PORT_NAMES=("Streamlit UI" "FastAPI" "Qdrant" "Redis")
running_services=()

for i in "${!GTRAG_PORTS[@]}"; do
    port=${GTRAG_PORTS[$i]}
    name=${PORT_NAMES[$i]}

    if lsof -i:$port > /dev/null 2>&1; then
        running_services+=("$name:$port")
        echo -e "   - $name (포트 $port): ${YELLOW}실행 중${NC}"
    fi
done

if [[ ${#running_services[@]} -eq 0 ]]; then
    echo -e "${GREEN}✅ 실행 중인 GTOne RAG 서비스가 없습니다.${NC}"
    echo "시스템이 이미 정리되어 있습니다."

    # Docker 컨테이너만 확인
    gtrag_containers=$(docker ps -a --format "{{.Names}}" | grep -E "(qdrant|redis).*service" | wc -l)
    if [[ $gtrag_containers -gt 0 ]]; then
        echo -e "${BLUE}Docker 컨테이너 정리만 수행하시겠습니까? (y/n)${NC}"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            exit 0
        fi
    else
        exit 0
    fi
else
    echo -e "\n${YELLOW}⚠️  ${#running_services[@]}개의 서비스가 실행 중입니다: ${running_services[*]}${NC}"
fi

# 3. 프론트엔드 종료 (역순)
echo -e "\n${BLUE}🎨 [1/3] 프론트엔드 서비스 종료...${NC}"
echo "======================================"

if [[ -f "frontend/scripts/stop_frontend.sh" ]]; then
    cd frontend

    if $VERBOSE; then
        ./scripts/stop_frontend.sh
    else
        ./scripts/stop_frontend.sh > /tmp/frontend_stop.log 2>&1
    fi

    frontend_exit_code=$?
    cd ..

    if [[ $frontend_exit_code -eq 0 ]]; then
        echo -e "${GREEN}✅ 프론트엔드 서비스 종료 완료${NC}"
    else
        echo -e "${YELLOW}⚠️ 프론트엔드 서비스 종료 중 오류 발생${NC}"
        if [[ ! $VERBOSE ]]; then
            echo "로그 확인: cat /tmp/frontend_stop.log"
        fi
    fi
else
    echo -e "${YELLOW}⚠️ 프론트엔드 종료 스크립트를 찾을 수 없습니다${NC}"

    # 수동으로 Streamlit 프로세스 종료
    echo "   수동으로 Streamlit 프로세스 종료 중..."
    if $FORCE_STOP; then
        pkill -9 -f "streamlit" 2>/dev/null
    else
        pkill -f "streamlit" 2>/dev/null
    fi
fi

# 포트 8501 정리 확인
sleep 2
if lsof -i:8501 > /dev/null 2>&1; then
    echo -e "${YELLOW}   포트 8501이 여전히 사용 중입니다. 강제 정리...${NC}"
    lsof -ti:8501 | xargs kill -9 2>/dev/null
fi

# 4. 백엔드 종료
echo -e "\n${CYAN}🔧 [2/3] 백엔드 서비스 종료...${NC}"
echo "====================================="

if [[ -f "backend/scripts/stop_backend.sh" ]]; then
    cd backend

    if $VERBOSE; then
        ./scripts/stop_backend.sh
    else
        ./scripts/stop_backend.sh > /tmp/backend_stop.log 2>&1
    fi

    backend_exit_code=$?
    cd ..

    if [[ $backend_exit_code -eq 0 ]]; then
        echo -e "${GREEN}✅ 백엔드 서비스 종료 완료${NC}"
    else
        echo -e "${YELLOW}⚠️ 백엔드 서비스 종료 중 오류 발생${NC}"
        if [[ ! $VERBOSE ]]; then
            echo "로그 확인: cat /tmp/backend_stop.log"
        fi
    fi
else
    echo -e "${YELLOW}⚠️ 백엔드 종료 스크립트를 찾을 수 없습니다${NC}"

    # 수동으로 백엔드 프로세스 종료
    echo "   수동으로 백엔드 프로세스 종료 중..."
    if $FORCE_STOP; then
        pkill -9 -f "uvicorn.*api.main" 2>/dev/null
        pkill -9 -f "celery.*api.main" 2>/dev/null
    else
        pkill -f "uvicorn.*api.main" 2>/dev/null
        pkill -f "celery.*api.main" 2>/dev/null
    fi
fi

# 포트 18000 정리 확인
sleep 2
if lsof -i:18000 > /dev/null 2>&1; then
    echo -e "${YELLOW}   포트 18000이 여전히 사용 중입니다. 강제 정리...${NC}"
    lsof -ti:18000 | xargs kill -9 2>/dev/null
fi

# 5. 인프라 종료
echo -e "\n${PURPLE}🏗️ [3/3] 인프라 서비스 종료...${NC}"
echo "======================================"

if [[ -f "infrastructure/scripts/stop_infra.sh" ]]; then
    cd infrastructure

    if $VERBOSE; then
        ./scripts/stop_infra.sh
    else
        ./scripts/stop_infra.sh > /tmp/infra_stop.log 2>&1
    fi

    infra_exit_code=$?
    cd ..

    if [[ $infra_exit_code -eq 0 ]]; then
        echo -e "${GREEN}✅ 인프라 서비스 종료 완료${NC}"
    else
        echo -e "${YELLOW}⚠️ 인프라 서비스 종료 중 오류 발생${NC}"
        if [[ ! $VERBOSE ]]; then
            echo "로그 확인: cat /tmp/infra_stop.log"
        fi
    fi
else
    echo -e "${YELLOW}⚠️ 인프라 종료 스크립트를 찾을 수 없습니다${NC}"

    # 수동으로 Docker 컨테이너 종료
    echo "   수동으로 Docker 컨테이너 종료 중..."

    containers=("qdrant-service" "redis-service" "qdrant-local" "redis-local")
    for container in "${containers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^$container$"; then
            echo "      $container 종료 중..."
            if $FORCE_STOP; then
                docker kill $container > /dev/null 2>&1
            else
                docker stop $container > /dev/null 2>&1
            fi
        fi
    done
fi

# 6. 추가 정리 작업
echo -e "\n${BLUE}🧹 추가 정리 작업...${NC}"

# 모든 GTOne RAG 관련 프로세스 강제 종료
echo "   남은 프로세스 정리 중..."
if $FORCE_STOP; then
    # Python 관련 프로세스
    pkill -9 -f "python.*ui/" 2>/dev/null
    pkill -9 -f "python.*api/" 2>/dev/null
    pkill -9 -f "streamlit.*ui/" 2>/dev/null
    pkill -9 -f "uvicorn.*main" 2>/dev/null
    pkill -9 -f "celery.*main" 2>/dev/null
fi

# 포트 강제 정리
echo "   포트 강제 정리 중..."
for port in "${GTRAG_PORTS[@]}"; do
    if lsof -i:$port > /dev/null 2>&1; then
        echo "      포트 $port 정리 중..."
        lsof -ti:$port | xargs kill -9 2>/dev/null
    fi
done

# 7. 데이터 정리 (선택적)
if [[ $KEEP_DATA == false ]]; then
    echo -e "\n${BLUE}🗑️ 데이터 정리...${NC}"

    echo -e "${RED}⚠️ 경고: 모든 데이터가 삭제됩니다!${NC}"
    echo "정말로 데이터를 삭제하시겠습니까? (DELETE 입력)"
    read -r confirmation

    if [[ "$confirmation" == "DELETE" ]]; then
        echo "   Docker 볼륨 삭제 중..."
        docker volume rm qdrant_data redis_data 2>/dev/null

        echo "   로그 파일 삭제 중..."
        rm -rf backend/logs/* 2>/dev/null
        rm -rf frontend/logs/* 2>/dev/null

        echo "   임시 파일 삭제 중..."
        rm -f .system_info 2>/dev/null
        rm -f backend/.backend_info 2>/dev/null
        rm -f frontend/.frontend_info 2>/dev/null
        rm -f infrastructure/.infra_info 2>/dev/null

        echo -e "   ${GREEN}✅ 데이터 정리 완료${NC}"
    else
        echo -e "   ${BLUE}데이터 삭제가 취소되었습니다.${NC}"
    fi
fi

# 8. Docker 시스템 정리 (선택적)
if [[ $CLEANUP_DOCKER == true ]]; then
    echo -e "\n${BLUE}🐳 Docker 시스템 정리...${NC}"

    echo "   사용하지 않는 Docker 리소스 정리 중..."
    docker system prune -f > /dev/null 2>&1

    echo "   사용하지 않는 이미지 정리 중..."
    docker image prune -f > /dev/null 2>&1

    echo -e "   ${GREEN}✅ Docker 시스템 정리 완료${NC}"
fi

# 9. 최종 상태 확인
echo -e "\n${BLUE}📊 최종 시스템 상태 확인...${NC}"
echo "==============================="

# 포트 상태 확인
all_ports_clear=true
for i in "${!GTRAG_PORTS[@]}"; do
    port=${GTRAG_PORTS[$i]}
    name=${PORT_NAMES[$i]}

    echo -n "   $name (포트 $port): "
    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "${RED}여전히 사용 중${NC}"
        all_ports_clear=false
    else
        echo -e "${GREEN}정리됨${NC}"
    fi
done

# Docker 컨테이너 상태
echo -e "\n   Docker 컨테이너:"
gtrag_containers=$(docker ps -a --format "{{.Names}}" | grep -E "(qdrant|redis).*(service|local)")
if [[ -n "$gtrag_containers" ]]; then
    echo "$gtrag_containers" | while read container; do
        status=$(docker ps -a --format "{{.Names}}\t{{.Status}}" | grep "^$container" | cut -f2)
        echo -e "   - $container: $status"
    done
else
    echo -e "   ${GREEN}✅ GTOne RAG 관련 컨테이너 없음${NC}"
fi

# Docker 볼륨 상태
echo -e "\n   Docker 볼륨:"
volumes=("qdrant_data" "redis_data")
remaining_volumes=0
for volume in "${volumes[@]}"; do
    if docker volume ls | grep -q "$volume"; then
        echo -e "   - $volume: 존재"
        remaining_volumes=$((remaining_volumes + 1))
    fi
done

if [[ $remaining_volumes -eq 0 ]]; then
    echo -e "   ${GREEN}✅ GTone RAG 관련 볼륨 없음${NC}"
fi

# 10. 최종 결과
echo -e "\n${GREEN}✅ GTOne RAG 전체 시스템 종료 완료!${NC}"
echo "==============================="

OVERALL_END_TIME=$(date)
echo "종료 시작: $OVERALL_STOP_TIME"
echo "종료 완료: $OVERALL_END_TIME"

if $all_ports_clear; then
    echo -e "\n${GREEN}🎉 모든 서비스 포트가 정리되었습니다.${NC}"
else
    echo -e "\n${YELLOW}⚠️ 일부 포트가 여전히 사용 중입니다.${NC}"
    echo "시스템을 재부팅하거나 다음 명령으로 강제 정리하세요:"
    echo "   sudo lsof -ti:8501,18000,6333,6379 | xargs sudo kill -9"
fi

echo -e "\n${BLUE}📊 종료 요약:${NC}"
echo "   정리된 서비스: ${#running_services[@]}개"
echo "   정리된 포트: $(if $all_ports_clear; then echo "모두"; else echo "일부"; fi)"
echo "   데이터 보존: $(if $KEEP_DATA; then echo "예"; else echo "아니오"; fi)"

echo -e "\n${YELLOW}💡 다음 시작 시:${NC}"
echo "   전체 시작: ./scripts/start_all.sh"
echo "   개별 시작:"
echo "   1. cd infrastructure && ./scripts/start_infra.sh"
echo "   2. cd backend && ./scripts/start_backend.sh"
echo "   3. cd frontend && ./scripts/start_frontend.sh"

if [[ $remaining_volumes -gt 0 ]]; then
    echo -e "\n${BLUE}📦 데이터 보존:${NC}"
    echo "   Docker 볼륨이 보존되었습니다."
    echo "   다음 시작 시 기존 데이터가 복원됩니다."
fi

echo -e "\n${GREEN}✨ 시스템이 안전하게 종료되었습니다! ✨${NC}"

# 임시 로그 파일 정리
rm -f /tmp/frontend_stop.log /tmp/backend_stop.log /tmp/infra_stop.log 2>/dev/null