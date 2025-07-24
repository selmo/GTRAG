#!/bin/bash

echo "🏗️ GTOne RAG - 인프라 서비스 시작"
echo "================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 시작 시간 기록
START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
echo "시작 시간: $START_TIME"

# 1. 환경 확인
echo -e "\n${BLUE}🔍 환경 확인...${NC}"

# Docker 설치 확인
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker가 설치되지 않았습니다.${NC}"
    echo "   Docker 설치 방법:"
    echo "   - macOS: https://docs.docker.com/desktop/mac/install/"
    echo "   - Ubuntu: sudo apt-get install docker.io"
    echo "   - CentOS: sudo yum install docker"
    exit 1
fi

# Docker 데몬 실행 확인
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker 데몬이 실행되지 않았습니다.${NC}"
    echo "   Docker 데몬 시작:"
    echo "   - macOS: Docker Desktop 실행"
    echo "   - Linux: sudo systemctl start docker"
    exit 1
fi

DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
echo -e "${GREEN}✅ Docker 버전: $DOCKER_VERSION${NC}"

# 2. 아키텍처 감지
echo -e "\n${BLUE}🏗️ 아키텍처 감지...${NC}"

ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" || "$ARCH" == "aarch64" ]]; then
    TARGETARCH="arm64"
    DOCKER_PLATFORM="linux/arm64"
elif [[ "$ARCH" == "x86_64" ]]; then
    TARGETARCH="amd64"
    DOCKER_PLATFORM="linux/amd64"
else
    TARGETARCH="amd64"  # 기본값
    DOCKER_PLATFORM="linux/amd64"
fi

export TARGETARCH
export DOCKER_DEFAULT_PLATFORM=$DOCKER_PLATFORM

echo "   호스트 아키텍처: $ARCH"
echo "   타겟 아키텍처: $TARGETARCH"
echo "   Docker 플랫폼: $DOCKER_PLATFORM"

# 3. 환경변수 설정
echo -e "\n${BLUE}🔧 환경변수 설정...${NC}"

# .env 파일 확인 및 로드
if [[ -f ".env" ]]; then
    source .env
    echo -e "${GREEN}✅ .env 파일 로드됨${NC}"
else
    echo -e "${YELLOW}⚠️  .env 파일이 없습니다. 기본값 사용${NC}"
fi

# 기본 포트 설정
QDRANT_PORT=${QDRANT_PORT:-6333}
REDIS_PORT=${REDIS_PORT:-6379}
OLLAMA_HOST=${OLLAMA_HOST:-"http://localhost:11434"}

echo "   Qdrant 포트: $QDRANT_PORT"
echo "   Redis 포트: $REDIS_PORT"
echo "   Ollama 호스트: $OLLAMA_HOST"

# 4. 포트 충돌 확인
echo -e "\n${BLUE}🔍 포트 충돌 확인...${NC}"

check_port_conflict() {
    local port=$1
    local service=$2

    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  포트 $port ($service)가 이미 사용 중입니다.${NC}"

        # 사용 중인 프로세스 정보
        process_info=$(lsof -i:$port | tail -n +2)
        echo "   사용 중인 프로세스:"
        echo "$process_info" | while read line; do
            echo "      $line"
        done

        echo "   기존 프로세스를 종료하고 계속하시겠습니까? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            lsof -ti:$port | xargs kill -9 2>/dev/null
            sleep 2
            echo -e "   ${GREEN}✅ 포트 $port 정리됨${NC}"
            return 0
        else
            echo -e "   ${RED}❌ 포트 충돌로 인해 계속할 수 없습니다.${NC}"
            return 1
        fi
    else
        echo -e "   포트 $port ($service): ${GREEN}사용 가능${NC}"
        return 0
    fi
}

# 주요 포트들 확인
check_port_conflict $QDRANT_PORT "Qdrant" || exit 1
check_port_conflict $REDIS_PORT "Redis" || exit 1

# 5. Docker 네트워크 생성
echo -e "\n${BLUE}🌐 Docker 네트워크 설정...${NC}"

NETWORK_NAME="gtrag-network"

# 기존 네트워크 확인
if docker network ls | grep -q "$NETWORK_NAME"; then
    echo -e "   네트워크 '$NETWORK_NAME': ${GREEN}이미 존재${NC}"
else
    echo "   네트워크 '$NETWORK_NAME' 생성 중..."
    docker network create $NETWORK_NAME > /dev/null 2>&1
    if [[ $? -eq 0 ]]; then
        echo -e "   ${GREEN}✅ 네트워크 생성 완료${NC}"
    else
        echo -e "   ${YELLOW}⚠️  네트워크 생성 실패 (기본 네트워크 사용)${NC}"
    fi
fi

# 6. Docker 볼륨 생성
echo -e "\n${BLUE}💾 Docker 볼륨 설정...${NC}"

############################################
# (파일 상단 util 함수 영역 - 아무 곳에 삽입)
############################################
create_qdrant_collection() {
  local collection_name=${1:-chunks}      # 기본값: chunks
  local vector_size=${2:-1024}            # 모델 임베딩 차원
  local distance=${3:-Cosine}             # Cosine | Dot | Euclid

  # 이미 컬렉션이 있으면 바로 종료
  if curl -s "http://localhost:$QDRANT_PORT/collections/$collection_name" \
       | grep -q '"status":"green"'; then
    echo "   ➖ 컬렉션 '$collection_name' 이미 존재 – 스킵"
    return 0
  fi

  echo "   ➕ 컬렉션 '$collection_name' 생성 중..."
  curl -s -X PUT "http://localhost:$QDRANT_PORT/collections/$collection_name" \
       -H "Content-Type: application/json" \
       -d "{
             \"vectors\": {
               \"size\": ${vector_size},
               \"distance\": \"${distance}\"
             }
           }" \
    && echo "   ✅ 생성 완료" \
    || echo "   ❌ 생성 실패"
}

create_volume() {
    local volume_name=$1
    local description=$2

    if docker volume ls | grep -q "$volume_name"; then
        echo -e "   볼륨 '$volume_name' ($description): ${GREEN}이미 존재${NC}"
    else
        echo "   볼륨 '$volume_name' ($description) 생성 중..."
        docker volume create $volume_name > /dev/null 2>&1
        if [[ $? -eq 0 ]]; then
            echo -e "   ${GREEN}✅ 볼륨 생성 완료${NC}"
        else
            echo -e "   ${RED}❌ 볼륨 생성 실패${NC}"
            return 1
        fi
    fi
}

create_volume "qdrant_data" "Qdrant 데이터" || exit 1
create_volume "redis_data" "Redis 데이터" || exit 1

# 7. Qdrant 서비스 시작
echo -e "\n${BLUE}🗄️ Qdrant 벡터 데이터베이스 시작...${NC}"

start_qdrant() {
    local container_name="qdrant-service"

    # 기존 컨테이너 확인
    if docker ps -a --format "table {{.Names}}" | grep -q "^$container_name$"; then
        echo "   기존 Qdrant 컨테이너 발견"

        # 실행 중인지 확인
        if docker ps --format "table {{.Names}}" | grep -q "^$container_name$"; then
            echo -e "   ${GREEN}✅ Qdrant가 이미 실행 중입니다${NC}"
            return 0
        else
            echo "   기존 컨테이너 시작 중..."
            docker start $container_name > /dev/null 2>&1
        fi
    else
        echo "   새 Qdrant 컨테이너 생성 및 시작 중..."

        # Qdrant 컨테이너 실행
        docker run -d \
            --name $container_name \
            --platform $DOCKER_PLATFORM \
            -p $QDRANT_PORT:6333 \
            -p $((QDRANT_PORT + 1)):6334 \
            -v qdrant_data:/qdrant/storage \
            --network $NETWORK_NAME \
            --restart unless-stopped \
            --health-cmd="curl -f http://localhost:6333/healthz || exit 1" \
            --health-interval=10s \
            --health-timeout=5s \
            --health-retries=5 \
            qdrant/qdrant:v1.9.3 > /dev/null 2>&1

        if [[ $? -ne 0 ]]; then
            echo -e "   ${RED}❌ Qdrant 컨테이너 시작 실패${NC}"
            return 1
        fi
    fi

    # 서비스 준비 대기
    echo -n "   Qdrant 서비스 준비 대기"
    max_attempts=60  # 3분 대기
    attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        if curl -s --connect-timeout 2 "http://localhost:$QDRANT_PORT/health" > /dev/null 2>&1; then
            echo -e "\n   ${GREEN}✅ Qdrant 서비스 준비 완료! (${attempt}초)${NC}"

            # ① API 테스트
            if curl -s "http://localhost:$QDRANT_PORT/collections" > /dev/null 2>&1; then
                echo -e "   ${GREEN}✅ Qdrant API 테스트 성공${NC}"
            else
                echo -e "   ${YELLOW}⚠️  Qdrant 기본 동작하지만 API 응답 지연${NC}"
            fi

            # ② 컬렉션이 없을 때만 생성
            create_qdrant_collection "chunks" "${EMBEDDING_DIM:-1024}" "${QDRANT_DISTANCE:-Cosine}"

            return 0
        fi

        # 진행 표시
        echo -n "."

        # 15초마다 상태 표시
        if [[ $((attempt % 15)) -eq 0 && $attempt -gt 0 ]]; then
            echo -e "\n   진행 중... ${attempt}초 경과"

            # 컨테이너 상태 확인
            container_status=$(docker inspect $container_name --format='{{.State.Status}}' 2>/dev/null)
            health_status=$(docker inspect $container_name --format='{{.State.Health.Status}}' 2>/dev/null)
            echo "   컨테이너 상태: $container_status"
            if [[ -n "$health_status" ]]; then
                echo "   헬스체크: $health_status"
            fi
            echo -n "   계속 대기 중"
        fi

        sleep 1
        attempt=$((attempt + 1))
    done

    echo -e "\n   ${RED}❌ Qdrant 서비스 시작 시간 초과${NC}"
    echo "   컨테이너 로그 확인: docker logs $container_name"
    return 1
}

start_qdrant || exit 1

# 8. Redis 서비스 시작
echo -e "\n${BLUE}🔴 Redis 캐시 서버 시작...${NC}"

start_redis() {
    local container_name="redis-service"

    # 기존 컨테이너 확인
    if docker ps -a --format "table {{.Names}}" | grep -q "^$container_name$"; then
        echo "   기존 Redis 컨테이너 발견"

        # 실행 중인지 확인
        if docker ps --format "table {{.Names}}" | grep -q "^$container_name$"; then
            echo -e "   ${GREEN}✅ Redis가 이미 실행 중입니다${NC}"
            return 0
        else
            echo "   기존 컨테이너 시작 중..."
            docker start $container_name > /dev/null 2>&1
        fi
    else
        echo "   새 Redis 컨테이너 생성 및 시작 중..."

        # Redis 컨테이너 실행
        docker run -d \
            --name $container_name \
            --platform $DOCKER_PLATFORM \
            -p $REDIS_PORT:6379 \
            -v redis_data:/data \
            --network $NETWORK_NAME \
            --restart unless-stopped \
            --health-cmd="redis-cli ping" \
            --health-interval=5s \
            --health-timeout=3s \
            --health-retries=5 \
            redis:7-alpine redis-server --appendonly yes --bind 0.0.0.0 > /dev/null 2>&1

        if [[ $? -ne 0 ]]; then
            echo -e "   ${RED}❌ Redis 컨테이너 시작 실패${NC}"
            return 1
        fi
    fi

    # 서비스 준비 대기
    echo -n "   Redis 서비스 준비 대기"
    max_attempts=30  # 1.5분 대기
    attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        # 여러 방법으로 Redis 연결 테스트
        if docker exec $container_name redis-cli ping 2>/dev/null | grep -q "PONG"; then
            echo -e "\n   ${GREEN}✅ Redis 서비스 준비 완료! (${attempt}초)${NC}"

            # 추가 기능 테스트
            if docker exec $container_name redis-cli set test_key "hello" > /dev/null 2>&1 && \
               docker exec $container_name redis-cli get test_key > /dev/null 2>&1 && \
               docker exec $container_name redis-cli del test_key > /dev/null 2>&1; then
                echo -e "   ${GREEN}✅ Redis 읽기/쓰기 테스트 성공${NC}"
            else
                echo -e "   ${YELLOW}⚠️  Redis 기본 동작하지만 읽기/쓰기 테스트 실패${NC}"
            fi
            return 0
        fi

        # 진행 표시
        echo -n "."

        # 10초마다 상태 표시
        if [[ $((attempt % 10)) -eq 0 && $attempt -gt 0 ]]; then
            echo -e "\n   진행 중... ${attempt}초 경과"

            # 컨테이너 상태 확인
            container_status=$(docker inspect $container_name --format='{{.State.Status}}' 2>/dev/null)
            health_status=$(docker inspect $container_name --format='{{.State.Health.Status}}' 2>/dev/null)
            echo "   컨테이너 상태: $container_status"
            if [[ -n "$health_status" ]]; then
                echo "   헬스체크: $health_status"
            fi
            echo -n "   계속 대기 중"
        fi

        sleep 1
        attempt=$((attempt + 1))
    done

    echo -e "\n   ${RED}❌ Redis 서비스 시작 시간 초과${NC}"
    echo "   컨테이너 로그 확인: docker logs $container_name"
    return 1
}

start_redis || exit 1

# 9. 외부 서비스 확인 (Ollama)
echo -e "\n${BLUE}🤖 외부 LLM 서비스 확인...${NC}"

check_ollama() {
    echo -n "   Ollama 서버 연결 테스트... "

    if curl -s --connect-timeout 5 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 연결됨${NC}"

        # 사용 가능한 모델 확인
        echo -n "   사용 가능한 모델 확인... "
        models=$(curl -s "$OLLAMA_HOST/api/tags" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | head -3)
        if [[ -n "$models" ]]; then
            echo -e "${GREEN}확인됨${NC}"
            echo "   모델 목록:"
            echo "$models" | while read model; do
                echo "      - $model"
            done
        else
            echo -e "${YELLOW}모델 없음${NC}"
        fi
        return 0
    else
        echo -e "${YELLOW}❌ 연결 실패${NC}"
        echo -e "   ${YELLOW}⚠️  Ollama 서버에 연결할 수 없습니다.${NC}"
        echo "   LLM 기능이 제한될 수 있습니다."
        echo "   Ollama 서버 주소: $OLLAMA_HOST"
        return 1
    fi
}

check_ollama

# 10. 최종 상태 확인
echo -e "\n${BLUE}📊 인프라 서비스 상태 확인...${NC}"

# 컨테이너 상태
echo "   실행 중인 컨테이너:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(qdrant|redis)" | while read line; do
    echo "   $line"
done

# 포트 상태
echo -e "\n   포트 상태:"
ports=($QDRANT_PORT $REDIS_PORT)
port_names=("Qdrant" "Redis")

for i in "${!ports[@]}"; do
    port=${ports[$i]}
    name=${port_names[$i]}

    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "   - 포트 $port ($name): ${GREEN}사용 중${NC}"
    else
        echo -e "   - 포트 $port ($name): ${RED}사용되지 않음${NC}"
    fi
done

# 11. 네트워크 및 볼륨 정보
echo -e "\n   Docker 리소스:"
echo "   네트워크: $NETWORK_NAME"
echo "   볼륨: qdrant_data, redis_data"

# 12. 완료 메시지
echo -e "\n${GREEN}🎉 인프라 서비스 시작 완료!${NC}"

echo -e "\n${YELLOW}📌 서비스 정보:${NC}"
echo -e "   🗄️ Qdrant: http://localhost:$QDRANT_PORT"
echo -e "   🗄️ Qdrant Dashboard: http://localhost:$QDRANT_PORT/dashboard"
echo -e "   🔴 Redis: localhost:$REDIS_PORT"
echo -e "   🤖 Ollama: $OLLAMA_HOST"

echo -e "\n${YELLOW}📋 유용한 명령어:${NC}"
echo -e "   📊 컨테이너 상태: docker ps"
echo -e "   📋 로그 확인:"
echo -e "      - Qdrant: docker logs qdrant-service"
echo -e "      - Redis: docker logs redis-service"
echo -e "   🛑 인프라 종료: ./infrastructure/scripts/stop_infra.sh"

echo -e "\n${YELLOW}🔗 다음 단계:${NC}"
echo -e "   1. 백엔드 시작: ./backend/scripts/start_backend.sh"
echo -e "   2. 프론트엔드 시작: ./frontend/scripts/start_frontend.sh"
echo -e "   3. 또는 전체 시스템: ./scripts/start_all.sh"

echo -e "\n${GREEN}✨ 인프라 서비스 실행 중! ✨${NC}"

# 인프라 정보 저장
cat > .infra_info << EOF
# GTOne RAG Infrastructure Service Info
# Generated: $(date)
QDRANT_CONTAINER=qdrant-service
REDIS_CONTAINER=redis-service
QDRANT_PORT=$QDRANT_PORT
REDIS_PORT=$REDIS_PORT
DOCKER_NETWORK=$NETWORK_NAME
DOCKER_PLATFORM=$DOCKER_PLATFORM
OLLAMA_HOST=$OLLAMA_HOST
EOF