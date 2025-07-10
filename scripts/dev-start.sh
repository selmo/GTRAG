#!/bin/bash

echo "🚀 GTOne RAG System - 개발환경 시작 중..."

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 현재 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "📁 프로젝트 루트: $PROJECT_ROOT"
cd "$PROJECT_ROOT"

# 1. 시스템 아키텍처 감지
echo -e "\n${BLUE}🔍 시스템 아키텍처 감지:${NC}"
HOST_ARCH=$(uname -m)
echo "   Host Architecture: $HOST_ARCH"

# Apple Silicon 감지 및 배포 모드 결정
if [[ $(uname -m) == "arm64" ]] && [[ $(uname -s) == "Darwin" ]]; then
    echo "   🍎 Apple Silicon Mac 감지됨"
    DEPLOYMENT_MODE="arm64"
    COMPOSE_PROFILES="arm64"
    export DOCKER_DEFAULT_PLATFORM=linux/arm64
elif [[ $(uname -m) == "x86_64" ]]; then
    echo "   🖥️  x86_64 시스템 감지됨"
    DEPLOYMENT_MODE="x86_64"
    COMPOSE_PROFILES=""
    export DOCKER_DEFAULT_PLATFORM=linux/amd64
else
    echo "   ❓ 알 수 없는 아키텍처: $HOST_ARCH (ARM64 모드로 처리)"
    DEPLOYMENT_MODE="arm64"
    COMPOSE_PROFILES="arm64"
fi

echo "   🎯 배포 모드: $DEPLOYMENT_MODE"
echo "   📋 Docker 프로파일: ${COMPOSE_PROFILES:-"기본값"}"

# 2. Docker 환경 확인
echo -e "\n${BLUE}🐳 Docker 환경 확인:${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker가 설치되지 않았습니다.${NC}"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose가 설치되지 않았습니다.${NC}"
    exit 1
fi

echo "   Docker Version: $(docker --version)"
echo "   Docker Compose Version: $(docker compose version --short)"

# 3. 환경 파일 확인
echo -e "\n${BLUE}⚙️ 환경 설정 확인:${NC}"
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️ .env 파일이 없습니다. .env.example에서 복사합니다...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ .env 파일이 생성되었습니다.${NC}"
    else
        echo -e "${RED}❌ .env.example 파일도 없습니다.${NC}"
        exit 1
    fi
fi

# 4. Ollama 서버 연결 확인
echo -e "\n${BLUE}🤖 Ollama 서버 연결 확인:${NC}"
OLLAMA_HOST=$(grep OLLAMA_HOST .env | cut -d'=' -f2)
if [ -n "$OLLAMA_HOST" ]; then
    if curl -s --connect-timeout 5 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama 서버 연결 성공: $OLLAMA_HOST${NC}"
    else
        echo -e "${YELLOW}⚠️ Ollama 서버 연결 실패: $OLLAMA_HOST${NC}"
        echo -e "${YELLOW}   LLM 기능이 제한될 수 있습니다.${NC}"
    fi
fi

# 5. 기존 컨테이너 정리 (선택적)
if [ "$1" == "--clean" ]; then
    echo -e "\n${YELLOW}🧹 기존 컨테이너 정리 중...${NC}"
    if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
        docker compose -f docker/development/docker-compose.yml --profile arm64 down -v
    else
        docker compose -f docker/development/docker-compose.yml down -v
    fi
    docker system prune -f
fi

# 6. 아키텍처별 빌드 및 시작
echo -e "\n${BLUE}🚀 시스템 시작 ($DEPLOYMENT_MODE 모드):${NC}"

if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    echo "   🍎 ARM64 모드: 외부 Qdrant + 메인 앱"
    echo "   - 먼저 메인 앱 빌드"
    echo "   - 그 다음 외부 Qdrant 컨테이너 시작"
    echo "   - 설정 자동 보정 적용"

    # ARM64: 메인 앱 먼저 빌드
    docker compose -f docker/development/docker-compose.yml build gtrag-dev
    docker compose -f docker/development/docker-compose.yml up -d gtrag-dev

    # 외부 Qdrant 시작
    docker compose -f docker/development/docker-compose.yml --profile arm64 up -d qdrant

elif [ "$DEPLOYMENT_MODE" = "x86_64" ]; then
    echo "   🖥️  x86_64 모드: 단일 컨테이너 통합"
    echo "   - 내장 Qdrant 바이너리 포함"
    echo "   - 모든 서비스 단일 컨테이너"

    # x86_64: 단일 컨테이너
    docker compose -f docker/development/docker-compose.yml up --build -d gtrag-dev
fi

# 7. ARM64 환경 설정 자동 보정
if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    echo -e "\n${BLUE}🔧 ARM64 환경 설정 자동 보정:${NC}"

    # 컨테이너가 시작될 때까지 대기
    echo "   메인 앱 컨테이너 시작 대기 중..."
    for i in {1..15}; do
        if docker compose -f docker/development/docker-compose.yml ps | grep -q "gtrag-dev.*running"; then
            echo -e "   ${GREEN}✅ 메인 앱 컨테이너 시작됨${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done

    # 아키텍처 설정 파일 확인 및 생성
    echo "   아키텍처 설정 파일 확인 중..."
    if ! docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev test -f /app/.arch-config 2>/dev/null; then
        echo -e "   ${YELLOW}⚠️ 아키텍처 설정 파일이 없습니다. 생성 중...${NC}"
        docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev bash -c "
            echo 'QDRANT_MODE=external' > /app/.arch-config
            echo 'QDRANT_HOST=qdrant' > /app/.env-override
            echo '✅ ARM64 설정 파일 생성 완료'
        "

        # Supervisor 설정 재생성
        echo "   Supervisor 설정 재생성 중..."
        docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev /app/setup-supervisor.sh > /dev/null 2>&1

        # 서비스 재시작
        echo "   서비스 재시작 중..."
        docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev supervisorctl reread > /dev/null 2>&1
        docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev supervisorctl update > /dev/null 2>&1
        docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev supervisorctl restart all > /dev/null 2>&1

        echo -e "   ${GREEN}✅ ARM64 환경 설정 보정 완료${NC}"
    else
        echo -e "   ${GREEN}✅ 아키텍처 설정이 이미 올바르게 구성됨${NC}"
    fi
fi

# 8. 서비스 준비 대기
echo -e "\n${BLUE}⏳ 서비스 준비 중...${NC}"
echo -n "대기 중"

max_attempts=60
attempt=0

while [ $attempt -lt $max_attempts ]; do
    sleep 5
    echo -n "."
    attempt=$((attempt + 1))

    # Streamlit 확인
    if curl -s http://localhost:8501 > /dev/null 2>&1; then
        # ARM64에서는 추가로 Qdrant 확인
        if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
            if curl -s http://localhost:6333/health > /dev/null 2>&1; then
                echo -e "\n${GREEN}✅ 모든 서비스가 준비되었습니다!${NC}"
                break
            fi
        else
            echo -e "\n${GREEN}✅ 서비스가 준비되었습니다!${NC}"
            break
        fi
    fi

    # 중간 진행상황 알림
    if [ $((attempt % 12)) -eq 0 ]; then
        echo -e "\n   진행 중... ($((attempt * 5))초 경과)"
        if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
            docker compose -f docker/development/docker-compose.yml --profile arm64 ps
        else
            docker compose -f docker/development/docker-compose.yml ps
        fi
        echo -n "   계속 대기 중"
    fi

    if [ $attempt -eq $max_attempts ]; then
        echo -e "\n${YELLOW}⚠️ 서비스 시작이 예상보다 지연되고 있습니다.${NC}"
    fi
done

# 9. 상세 서비스 상태 확인
echo -e "\n${BLUE}📊 서비스 상태 확인 ($DEPLOYMENT_MODE 모드):${NC}"

# 컨테이너 상태
echo -e "\n${YELLOW}컨테이너 상태:${NC}"
if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    docker compose -f docker/development/docker-compose.yml --profile arm64 ps
else
    docker compose -f docker/development/docker-compose.yml ps
fi

# 아키텍처별 상태 확인
if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    echo -e "\n${YELLOW}ARM64 전용 상태:${NC}"

    # 외부 Qdrant 확인
    if curl -s http://localhost:6333/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 외부 Qdrant: 정상 작동${NC}"
    else
        echo -e "${RED}❌ 외부 Qdrant: 연결 실패${NC}"
    fi

    # 메인 앱에서 Qdrant 연결 확인
    if docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev curl -s http://qdrant:6333/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 앱→Qdrant 연결: 정상${NC}"
    else
        echo -e "${RED}❌ 앱→Qdrant 연결: 실패${NC}"
    fi

elif [ "$DEPLOYMENT_MODE" = "x86_64" ]; then
    echo -e "\n${YELLOW}x86_64 전용 상태:${NC}"

    # 내장 Qdrant 확인
    if docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev curl -s http://localhost:6333/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 내장 Qdrant: 정상 작동${NC}"
    else
        echo -e "${RED}❌ 내장 Qdrant: 연결 실패${NC}"
    fi
fi

# 공통 서비스 확인
echo -e "\n${YELLOW}공통 서비스 상태:${NC}"

# Streamlit
if curl -s http://localhost:8501 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Streamlit UI: 정상 작동${NC}"
else
    echo -e "${RED}❌ Streamlit UI: 연결 실패${NC}"
fi

# API 서버
if docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev curl -s http://localhost:18000/docs > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API 서버: 정상 작동${NC}"
else
    echo -e "${RED}❌ API 서버: 연결 실패${NC}"
fi

# Redis
if docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis: 정상 작동${NC}"
else
    echo -e "${RED}❌ Redis: 연결 실패${NC}"
fi

# 10. 결과 및 접속 정보
echo -e "\n${GREEN}🎉 GTOne RAG System 개발환경 시작 완료! ($DEPLOYMENT_MODE 모드)${NC}"

echo -e "\n${YELLOW}📌 접속 정보:${NC}"
echo -e "   🌐 Web UI: http://localhost:8501"
if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    echo -e "   🗄️ Qdrant Dashboard: http://localhost:6333/dashboard (외부 컨테이너)"
else
    echo -e "   🗄️ Qdrant Dashboard: http://localhost:6333/dashboard (내장)"
fi

echo -e "\n${YELLOW}💻 현재 설정:${NC}"
echo -e "   Host Architecture: $HOST_ARCH"
echo -e "   Deployment Mode: $DEPLOYMENT_MODE"
echo -e "   Docker Platform: ${DOCKER_DEFAULT_PLATFORM:-auto}"

if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    echo -e "   🍎 ARM64 최적화:"
    echo -e "     - 외부 Qdrant 컨테이너 사용"
    echo -e "     - 네트워크 기반 통신"
    echo -e "     - 자동 설정 보정 적용"
elif [ "$DEPLOYMENT_MODE" = "x86_64" ]; then
    echo -e "   🖥️  x86_64 최적화:"
    echo -e "     - 단일 컨테이너 통합"
    echo -e "     - 내장 Qdrant 바이너리"
    echo -e "     - localhost 고속 통신"
fi

echo -e "\n${YELLOW}💡 유용한 명령어:${NC}"
if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    echo -e "   📋 로그 확인: docker compose -f docker/development/docker-compose.yml --profile arm64 logs -f"
    echo -e "   📊 전체 상태: docker compose -f docker/development/docker-compose.yml --profile arm64 ps"
    echo -e "   🔍 Qdrant 접속: docker compose -f docker/development/docker-compose.yml --profile arm64 exec qdrant /bin/sh"
else
    echo -e "   📋 로그 확인: docker compose -f docker/development/docker-compose.yml logs -f"
    echo -e "   📊 프로세스 상태: docker compose -f docker/development/docker-compose.yml exec gtrag-dev supervisorctl status"
fi

echo -e "   🐚 컨테이너 접속: docker compose -f docker/development/docker-compose.yml exec gtrag-dev /bin/bash"
echo -e "   🏥 헬스체크: docker compose -f docker/development/docker-compose.yml exec gtrag-dev /app/healthcheck.sh"

if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    echo -e "   🛑 서비스 종료: docker compose -f docker/development/docker-compose.yml --profile arm64 down"
else
    echo -e "   🛑 서비스 종료: docker compose -f docker/development/docker-compose.yml down"
fi

echo -e "\n${YELLOW}🔧 문제 해결:${NC}"
if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    echo -e "   🐛 Qdrant 로그: docker compose -f docker/development/docker-compose.yml --profile arm64 logs qdrant"
    echo -e "   🐛 앱 로그: docker compose -f docker/development/docker-compose.yml logs gtrag-dev"
else
    echo -e "   🐛 상세 로그: docker compose -f docker/development/docker-compose.yml logs gtrag-dev"
fi

# 11. 브라우저 자동 열기 (선택적)
if [ "$2" == "--open" ] || [ "$1" == "--open" ]; then
    echo -e "\n${BLUE}🌐 브라우저 열기 중...${NC}"
    sleep 3
    if command -v open &> /dev/null; then
        open http://localhost:8501
    elif command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8501
    else
        echo -e "${YELLOW}   수동으로 http://localhost:8501 을 열어주세요.${NC}"
    fi
fi

echo -e "\n${GREEN}✨ 아키텍처별 최적화 환경 준비 완료! 즐거운 개발 되세요! ✨${NC}"