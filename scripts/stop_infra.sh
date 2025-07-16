#!/bin/bash

echo "🛑 GTOne RAG - 인프라 서비스 종료"
echo "==============================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 종료 시작 시간 기록
STOP_START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "종료 시작 시간: $STOP_START_TIME"

# 1. Docker 환경 확인
echo -e "\n${BLUE}🔍 Docker 환경 확인...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker가 설치되지 않았습니다.${NC}"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker 데몬이 실행되지 않았습니다.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker 환경 확인됨${NC}"

# 2. 실행 중인 GTOne RAG 컨테이너 확인
echo -e "\n${BLUE}📋 GTOne RAG 인프라 컨테이너 확인...${NC}"

# GTOne RAG 관련 컨테이너 목록
GTRAG_CONTAINERS=(
    "qdrant-service"
    "redis-service"
    "qdrant-local"
    "redis-local"
)

# 실행 중인 컨테이너 찾기
running_containers=()
stopped_containers=()

for container in "${GTRAG_CONTAINERS[@]}"; do
    if docker ps --format "table {{.Names}}" | grep -q "^$container$"; then
        running_containers+=("$container")
        echo -e "   - $container: ${YELLOW}실행 중${NC}"
    elif docker ps -a --format "table {{.Names}}" | grep -q "^$container$"; then
        stopped_containers+=("$container")
        echo -e "   - $container: ${BLUE}정지됨${NC}"
    fi
done

if [[ ${#running_containers[@]} -eq 0 && ${#stopped_containers[@]} -eq 0 ]]; then
    echo -e "${GREEN}✅ GTOne RAG 관련 컨테이너가 없습니다.${NC}"
    echo "인프라 서비스가 이미 정리되어 있습니다."
    exit 0
fi

# 3. 실행 중인 컨테이너 정지
if [[ ${#running_containers[@]} -gt 0 ]]; then
    echo -e "\n${BLUE}🛑 실행 중인 컨테이너 정지...${NC}"

    for container in "${running_containers[@]}"; do
        echo -n "   $container 정지 중... "

        # 정상 정지 시도 (더 긴 대기 시간)
        if docker stop -t 30 $container > /dev/null 2>&1; then
            echo -e "${GREEN}완료${NC}"
        else
            echo -e "${YELLOW}강제 정지 시도${NC}"
            docker kill $container > /dev/null 2>&1
        fi

        # 정지 확인
        sleep 2
        if ! docker ps --format "table {{.Names}}" | grep -q "^$container$"; then
            echo -e "      ${GREEN}✅ $container 정지 확인${NC}"
        else
            echo -e "      ${RED}❌ $container 정지 실패${NC}"
        fi
    done
else
    echo -e "\n${GREEN}✅ 정지할 실행 중인 컨테이너가 없습니다.${NC}"
fi

# 4. 컨테이너 제거 옵션
all_containers=("${running_containers[@]}" "${stopped_containers[@]}")

if [[ ${#all_containers[@]} -gt 0 ]]; then
    echo -e "\n${BLUE}🗑️ 컨테이너 제거 옵션...${NC}"
    echo "다음 컨테이너들이 발견되었습니다:"

    for container in "${all_containers[@]}"; do
        status=$(docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep "^$container" | cut -f2)
        echo -e "   - $container: $status"
    done

    echo -e "\n${YELLOW}컨테이너를 완전히 제거하시겠습니까?${NC}"
    echo "   y) 예 - 컨테이너 제거 (데이터 볼륨은 보존)"
    echo "   d) 예 + 데이터 볼륨도 삭제"
    echo "   n) 아니오 - 컨테이너 보존"
    read -r response

    case $response in
        [Yy])
            echo -e "\n${BLUE}📦 컨테이너 제거 중...${NC}"
            for container in "${all_containers[@]}"; do
                echo -n "   $container 제거 중... "
                if docker rm $container > /dev/null 2>&1; then
                    echo -e "${GREEN}완료${NC}"
                else
                    echo -e "${RED}실패${NC}"
                fi
            done
            ;;
        [Dd])
            echo -e "\n${BLUE}📦 컨테이너 및 볼륨 제거 중...${NC}"

            # 컨테이너 제거
            for container in "${all_containers[@]}"; do
                echo -n "   $container 제거 중... "
                if docker rm $container > /dev/null 2>&1; then
                    echo -e "${GREEN}완료${NC}"
                else
                    echo -e "${RED}실패${NC}"
                fi
            done

            # 볼륨 제거
            volumes=("qdrant_data" "redis_data")
            echo -e "\n${BLUE}💾 데이터 볼륨 제거 중...${NC}"
            for volume in "${volumes[@]}"; do
                echo -n "   $volume 제거 중... "
                if docker volume rm $volume > /dev/null 2>&1; then
                    echo -e "${GREEN}완료${NC}"
                else
                    echo -e "${YELLOW}실패 (사용 중이거나 없음)${NC}"
                fi
            done
            ;;
        *)
            echo -e "${BLUE}컨테이너가 보존되었습니다.${NC}"
            ;;
    esac
fi

# 5. 안전한 포트 상태 확인 (강제 정리 제거)
echo -e "\n${BLUE}📊 포트 상태 확인...${NC}"

# 기본 포트들
QDRANT_PORT=${QDRANT_PORT:-6333}
REDIS_PORT=${REDIS_PORT:-6379}

ports=($QDRANT_PORT $REDIS_PORT)
port_names=("Qdrant" "Redis")

# 안전한 Docker 컨테이너별 포트 확인
function check_container_ports() {
    local container_name=$1
    local expected_port=$2

    # 컨테이너가 실행 중인지 확인
    if docker ps --format "table {{.Names}}" | grep -q "^$container_name$"; then
        # 컨테이너의 포트 매핑 확인
        container_ports=$(docker port $container_name 2>/dev/null)
        if [[ -n "$container_ports" ]]; then
            echo -e "   ⚠️  $container_name이 여전히 포트를 사용 중입니다:"
            echo "      $container_ports"
            return 1
        fi
    fi
    return 0
}

# GTOne RAG 컨테이너별 포트 확인만 수행
all_ports_clear=true

for i in "${!ports[@]}"; do
    port=${ports[$i]}
    name=${port_names[$i]}

    echo -n "   포트 $port ($name): "

    # lsof로 포트 사용 확인 (하지만 강제 종료는 하지 않음)
    if command -v lsof &> /dev/null && lsof -i:$port > /dev/null 2>&1; then
        # 포트를 사용하는 프로세스 정보 확인
        process_info=$(lsof -i:$port -t 2>/dev/null | head -1)
        if [[ -n "$process_info" ]]; then
            process_name=$(ps -p $process_info -o comm= 2>/dev/null)

            # Docker 관련 프로세스인지 확인
            if [[ "$process_name" == *"docker"* ]] || [[ "$process_name" == *"containerd"* ]]; then
                echo -e "${YELLOW}Docker 관련 프로세스 사용 중${NC}"
                echo -e "      ${GREEN}✅ 안전 - Docker 시스템 프로세스${NC}"
            else
                echo -e "${RED}외부 프로세스 사용 중${NC}"
                echo "      프로세스: $process_name (PID: $process_info)"
                echo -e "      ${YELLOW}⚠️  수동으로 확인이 필요합니다${NC}"
                all_ports_clear=false
            fi
        else
            echo -e "${YELLOW}사용 중 (정보 확인 불가)${NC}"
        fi
    else
        echo -e "${GREEN}정리됨${NC}"
    fi
done

# 포트 강제 정리 옵션 제거됨 - Docker 데몬 보호

# 6. Docker 네트워크 정리
echo -e "\n${BLUE}🌐 Docker 네트워크 정리...${NC}"

NETWORK_NAME="gtrag-network"

if docker network ls | grep -q "$NETWORK_NAME"; then
    echo -n "   네트워크 '$NETWORK_NAME' 제거 중... "

    # 네트워크를 사용하는 컨테이너가 있는지 확인
    containers_using_network=$(docker network inspect $NETWORK_NAME --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null)

    if [[ -n "$containers_using_network" ]]; then
        echo -e "${YELLOW}사용 중${NC}"
        echo "      다음 컨테이너가 네트워크를 사용 중: $containers_using_network"
        echo "      네트워크는 보존됩니다."
    else
        if docker network rm $NETWORK_NAME > /dev/null 2>&1; then
            echo -e "${GREEN}완료${NC}"
        else
            echo -e "${YELLOW}실패 (기본 네트워크일 수 있음)${NC}"
        fi
    fi
else
    echo "   네트워크 '$NETWORK_NAME': 없음"
fi

# 7. 외부 서비스 상태 확인 (참고용)
echo -e "\n${BLUE}🔗 외부 서비스 상태 (참고용)...${NC}"

# Ollama 상태 확인
OLLAMA_HOST=${OLLAMA_HOST:-"http://172.16.15.112:11434"}
echo -n "   Ollama 서버 ($OLLAMA_HOST): "
if curl -s --connect-timeout 3 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo -e "${GREEN}실행 중${NC} (외부 서비스)"
else
    echo -e "${YELLOW}연결 안됨${NC} (외부 서비스)"
fi

# 8. 임시 파일 정리
echo -e "\n${BLUE}🗑️ 임시 파일 정리...${NC}"

# 인프라 정보 파일 정리
if [[ -f ".infra_info" ]]; then
    echo "   .infra_info 삭제..."
    rm ".infra_info"
fi

# Docker 시스템 정리 (더 안전하게)
echo -n "   Docker 시스템 정리... "
if docker system df 2>/dev/null | grep -q "reclaimable"; then
    echo -e "${YELLOW}정리 가능한 데이터 있음${NC}"
    echo "   Docker 시스템 정리를 실행하시겠습니까? (y/n)"
    echo "   ${YELLOW}⚠️  주의: 사용하지 않는 이미지와 컨테이너만 정리됩니다${NC}"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "   Docker 시스템 정리 실행 중 (안전 모드)..."
        # 더 안전한 정리: 볼륨은 제외하고 dangling 이미지만
        docker image prune -f > /dev/null 2>&1
        docker container prune -f > /dev/null 2>&1
        echo -e "   ${GREEN}✅ Docker 시스템 정리 완료 (안전 모드)${NC}"
    fi
else
    echo -e "${GREEN}정리할 데이터 없음${NC}"
fi

# 9. 최종 상태 확인
echo -e "\n${BLUE}📊 최종 인프라 상태...${NC}"

# Docker 데몬 상태 재확인
echo -n "   Docker 데몬 상태: "
if docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 정상 실행 중${NC}"
else
    echo -e "${RED}❌ 문제 발생!${NC}"
    echo -e "${YELLOW}   Docker 데몬을 다시 시작해야 할 수 있습니다.${NC}"
fi

# 남은 GTOne RAG 관련 컨테이너 확인
echo "   GTOne RAG 관련 컨테이너:"
remaining_containers=0
for container in "${GTRAG_CONTAINERS[@]}"; do
    if docker ps -a --format "table {{.Names}}" | grep -q "^$container$"; then
        status=$(docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep "^$container" | cut -f2)
        echo -e "   - $container: $status"
        remaining_containers=$((remaining_containers + 1))
    fi
done

if [[ $remaining_containers -eq 0 ]]; then
    echo -e "   ${GREEN}✅ GTOne RAG 관련 컨테이너 없음${NC}"
fi

# 남은 볼륨 확인
echo -e "\n   GTOne RAG 관련 볼륨:"
volumes=("qdrant_data" "redis_data")
remaining_volumes=0
for volume in "${volumes[@]}"; do
    if docker volume ls | grep -q "$volume"; then
        size=$(docker volume inspect $volume --format '{{.Mountpoint}}' 2>/dev/null | xargs du -sh 2>/dev/null | cut -f1 || echo "unknown")
        echo -e "   - $volume: 존재 (크기: $size)"
        remaining_volumes=$((remaining_volumes + 1))
    fi
done

if [[ $remaining_volumes -eq 0 ]]; then
    echo -e "   ${GREEN}✅ GTOne RAG 관련 볼륨 없음${NC}"
fi

# 10. 완료 메시지
echo -e "\n${GREEN}✅ GTOne RAG 인프라 서비스 종료 완료!${NC}"

# Docker 데몬 상태에 따른 메시지
if docker info > /dev/null 2>&1; then
    echo -e "\n${GREEN}🎉 Docker 데몬이 정상적으로 실행 중입니다!${NC}"
else
    echo -e "\n${RED}⚠️  Docker 데몬에 문제가 발생했습니다!${NC}"
    echo -e "   ${YELLOW}다음 명령으로 Docker를 다시 시작하세요:${NC}"
    echo -e "   sudo systemctl restart docker"
    echo -e "   또는"
    echo -e "   sudo service docker restart"
fi

if $all_ports_clear; then
    echo -e "\n${GREEN}🎉 모든 포트가 안전하게 정리되었습니다.${NC}"
else
    echo -e "\n${YELLOW}⚠️  일부 포트가 외부 프로세스에 의해 사용 중입니다.${NC}"
    echo -e "   수동으로 확인 후 필요시 정리하세요."
fi

echo -e "\n${BLUE}📊 종료 요약:${NC}"
echo "   종료 시작: $STOP_START_TIME"
echo "   종료 완료: $(date '+%Y-%m-%d %H:%M:%S')"
echo "   남은 컨테이너: $remaining_containers개"
echo "   남은 볼륨: $remaining_volumes개"

echo -e "\n${YELLOW}💡 참고 사항:${NC}"
if [[ $remaining_containers -gt 0 ]]; then
    echo "   - 일부 컨테이너가 보존되었습니다"
    echo "   - 다시 시작: ./scripts/start_infra.sh"
    echo "   - 완전 정리: docker rm \$(docker ps -aq --filter name=qdrant) \$(docker ps -aq --filter name=redis)"
else
    echo "   - 모든 GTOne RAG 인프라가 정리되었습니다"
    echo "   - 새로 시작: ./scripts/start_infra.sh"
fi

if [[ $remaining_volumes -gt 0 ]]; then
    echo "   - 데이터 볼륨이 보존되었습니다 (다음 시작 시 데이터 유지)"
    echo "   - 볼륨 삭제: docker volume rm qdrant_data redis_data"
fi

echo -e "\n${YELLOW}🔄 다음 시작 시:${NC}"
echo "   1. 인프라 시작: ./scripts/start_infra.sh"
echo "   2. 백엔드 시작: cd ../backend && ./scripts/start_backend.sh"
echo "   3. 프론트엔드 시작: cd ../frontend && ./scripts/start_frontend.sh"

echo -e "\n${GREEN}✨ 인프라 서비스 정리 완료! Docker 데몬 보호됨! ✨${NC}"