#!/bin/bash

echo "🚀 GTOne RAG System - 개발환경 시작 중..."

# 사용법 표시
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    echo "사용법: $0 [옵션]"
    echo ""
    echo "옵션:"
    echo "  --clean         기존 컨테이너 완전 정리 후 시작"
    echo "  --open          시작 후 브라우저 자동 열기"
    echo "  --reload        강제로 --reload 옵션 활성화"
    echo "  --no-reload     강제로 --reload 옵션 비활성화"
    echo "  --help, -h      이 도움말 표시"
    echo ""
    echo "환경변수:"
    echo "  UVICORN_FLAGS   수동으로 Uvicorn 옵션 설정"
    echo ""
    echo "예시:"
    echo "  $0                      # 기본 실행 (아키텍처별 자동 설정)"
    echo "  $0 --clean --open       # 정리 후 시작, 브라우저 열기"
    echo "  $0 --reload             # 강제로 --reload 활성화"
    echo "  UVICORN_FLAGS=\"--host 0.0.0.0 --port 18000 --workers 4\" $0"
    exit 0
fi

# 명령행 옵션 처리
FORCE_RELOAD=""
if [ "$1" == "--reload" ] || [ "$2" == "--reload" ] || [ "$3" == "--reload" ]; then
    FORCE_RELOAD="yes"
    echo "🔄 강제로 --reload 옵션 활성화됨"
elif [ "$1" == "--no-reload" ] || [ "$2" == "--no-reload" ] || [ "$3" == "--no-reload" ]; then
    FORCE_RELOAD="no"
    echo "🚫 강제로 --reload 옵션 비활성화됨"
fi

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

# 1. .env 파일 확인 및 생성
echo -e "\n${BLUE}⚙️ 환경 설정 확인:${NC}"
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️ .env 파일이 없습니다. .env.example에서 복사합니다...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ .env 파일이 생성되었습니다.${NC}"
    else
        echo -e "${RED}❌ .env.example 파일도 없습니다. 기본 .env 파일을 생성합니다.${NC}"
        cat > .env << EOF
# GTOne RAG System 환경 설정
QDRANT_HOST=qdrant
QDRANT_PORT=6333
QDRANT__URL=http://qdrant:6333
OLLAMA_HOST=http://172.16.15.112:11434
OLLAMA_MODEL=llama3:8b-instruct
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
API_HOST=0.0.0.0
API_PORT=18000
API_BASE_URL=http://api:18000
UVICORN_FLAGS=--host 0.0.0.0 --port 18000 --reload
EMBEDDING_MODEL=intfloat/multilingual-e5-large-instruct
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=50
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
TARGETARCH=arm64
DOCKER_DEFAULT_PLATFORM=linux/arm64
EOF
        echo -e "${GREEN}✅ 기본 .env 파일이 생성되었습니다.${NC}"
    fi
fi

# 2. .env 파일에서 환경변수 로드
if [ -f ".env" ]; then
    echo "📋 .env 파일에서 환경변수 로드 중..."
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
    echo -e "${GREEN}✅ 환경변수 로드 완료${NC}"
else
    echo -e "${RED}❌ .env 파일을 찾을 수 없습니다.${NC}"
    exit 1
fi

# 3. 아키텍처별 UVICORN_FLAGS 설정
echo -e "\n${BLUE}⚙️ Uvicorn 설정 구성:${NC}"

# 기본값: --reload 없음 (안정성 우선)
UVICORN_BASE="--host 0.0.0.0 --port 18000"

# 환경변수로 미리 설정되어 있으면 그것을 사용
if [ -n "$UVICORN_FLAGS" ]; then
    echo "   🔧 수동 설정된 UVICORN_FLAGS 사용: $UVICORN_FLAGS"
else
    # 강제 옵션 확인
    if [ "$FORCE_RELOAD" == "yes" ]; then
        export UVICORN_FLAGS="$UVICORN_BASE --reload"
        echo "   🔄 강제로 --reload 활성화"
    elif [ "$FORCE_RELOAD" == "no" ]; then
        export UVICORN_FLAGS="$UVICORN_BASE"
        echo "   🚫 강제로 --reload 비활성화"
    else
        # 아키텍처별 자동 설정
        if [[ $(uname -m) == "arm64" ]] && [[ $(uname -s) == "Darwin" ]]; then
            # ARM64 (Apple Silicon): --reload 제외 (파일 시스템 감시 문제)
            export UVICORN_FLAGS="$UVICORN_BASE"
            echo "   🍎 ARM64 감지: --reload 제외 (안정성 우선)"
            ARCH_NOTE="ARM64 (파일 시스템 감시 문제로 --reload 비활성화)"
        else
            # x86_64: --reload 추가 (개발 편의성)
            export UVICORN_FLAGS="$UVICORN_BASE --reload"
            echo "   🖥️  x86_64 감지: --reload 추가 (개발 편의성)"
            ARCH_NOTE="x86_64 (개발 편의를 위해 --reload 활성화)"
        fi

        echo "   설명: $ARCH_NOTE"
    fi
fi

echo "   최종 UVICORN_FLAGS: $UVICORN_FLAGS"

# .env 파일에 기본 설정이 없으면 추가
if ! grep -q "UVICORN_FLAGS_BASE" .env; then
    cat >> .env << EOF

# --- Uvicorn Settings (기본: 안정성 우선) ---
# 기본적으로는 --reload 없음 (안정성 우선)
# x86_64에서만 개발 편의를 위해 --reload 추가
# 수동 override: export UVICORN_FLAGS="--host 0.0.0.0 --port 18000 --reload"
UVICORN_FLAGS_BASE=--host 0.0.0.0 --port 18000
UVICORN_FLAGS_WITH_RELOAD=--host 0.0.0.0 --port 18000 --reload
EOF
    echo -e "${GREEN}✅ Uvicorn 기본 설정이 .env 파일에 추가되었습니다.${NC}"
fi

# 옵션 정보 표시
echo -e "\n${YELLOW}💡 Uvicorn 옵션 정보:${NC}"
echo "   • 기본 (안정): $UVICORN_BASE"
echo "   • 개발 (재로드): $UVICORN_BASE --reload"
echo "   • 수동 설정: export UVICORN_FLAGS=\"원하는_옵션\""
echo "   • 강제 재로드: $0 --reload"
echo "   • 강제 비활성화: $0 --no-reload"

# 4. 시스템 아키텍처 감지
echo -e "\n${BLUE}🔍 시스템 아키텍처 감지:${NC}"
HOST_ARCH=$(uname -m)
OS_NAME=$(uname -s)
echo "   Host Architecture: $HOST_ARCH"
echo "   OS Name: $OS_NAME"

# Apple Silicon 감지 및 배포 모드 결정
if [[ $(uname -m) == "arm64" ]] && [[ $(uname -s) == "Darwin" ]]; then
    echo "   🍎 Apple Silicon Mac 감지됨"
    DEPLOYMENT_MODE="arm64"
    COMPOSE_PROFILES="arm64"
    export DOCKER_DEFAULT_PLATFORM=linux/arm64
    export TARGETARCH=arm64
elif [[ $(uname -m) == "x86_64" ]]; then
    echo "   🖥️  x86_64 시스템 감지됨"
    DEPLOYMENT_MODE="x86_64"
    COMPOSE_PROFILES=""
    export DOCKER_DEFAULT_PLATFORM=linux/amd64
    export TARGETARCH=amd64
else
    echo "   ❓ 알 수 없는 아키텍처: $HOST_ARCH (ARM64 모드로 처리)"
    DEPLOYMENT_MODE="arm64"
    COMPOSE_PROFILES="arm64"
    export DOCKER_DEFAULT_PLATFORM=linux/arm64
    export TARGETARCH=arm64
fi

echo "   🎯 배포 모드: $DEPLOYMENT_MODE"
echo "   📋 Docker 프로파일: ${COMPOSE_PROFILES:-"기본값"}"

# 5. Docker 환경 확인
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

# 6. Ollama 서버 연결 확인
echo -e "\n${BLUE}🤖 Ollama 서버 연결 확인:${NC}"
if [ -n "$OLLAMA_HOST" ]; then
    if curl -s --connect-timeout 5 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama 서버 연결 성공: $OLLAMA_HOST${NC}"
    else
        echo -e "${YELLOW}⚠️ Ollama 서버 연결 실패: $OLLAMA_HOST${NC}"
        echo -e "${YELLOW}   LLM 기능이 제한될 수 있습니다.${NC}"
    fi
fi

# 7. 기존 컨테이너 정리 (선택적)
if [ "$1" == "--clean" ]; then
    echo -e "\n${YELLOW}🧹 기존 컨테이너 정리 중...${NC}"
    if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
        docker compose -f docker/development/docker-compose.yml --profile arm64 down -v
    else
        docker compose -f docker/development/docker-compose.yml down -v
    fi
    docker system prune -f
fi

# 8. 포트 충돌 확인
echo -e "\n${BLUE}🔍 포트 충돌 확인:${NC}"
check_port() {
    local port=$1
    local service=$2
    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️ 포트 $port ($service)가 이미 사용 중입니다.${NC}"
        lsof -i:$port
        echo "계속 진행하시겠습니까? (y/n)"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        echo -e "${GREEN}✅ 포트 $port ($service) 사용 가능${NC}"
    fi
}

check_port 6333 "Qdrant"
check_port 8501 "Streamlit"
check_port 18000 "API"

# 9. 아키텍처별 빌드 및 시작
echo -e "\n${BLUE}🚀 시스템 시작 ($DEPLOYMENT_MODE 모드):${NC}"

if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    echo "   🍎 ARM64 모드: 외부 Qdrant + 메인 앱"

    # Qdrant 먼저 시작
    echo "   1. Qdrant 컨테이너 시작..."
    docker compose -f docker/development/docker-compose.yml --profile arm64 up -d qdrant

    # Qdrant 준비 대기
    echo "   2. Qdrant 준비 대기..."
    for i in {1..30}; do
        if curl -s http://localhost:6333/health > /dev/null 2>&1; then
            echo -e "   ${GREEN}✅ Qdrant 준비 완료${NC}"
            break
        fi
        echo -n "."
        sleep 2
        if [ $i -eq 30 ]; then
            echo -e "\n   ${YELLOW}⚠️ Qdrant 시작이 지연되고 있습니다. 로그를 확인하세요.${NC}"
            docker compose -f docker/development/docker-compose.yml logs qdrant --tail=10
        fi
    done

    # 메인 앱 시작
    echo "   3. 메인 앱 빌드 및 시작..."
    docker compose -f docker/development/docker-compose.yml build gtrag-dev
    docker compose -f docker/development/docker-compose.yml up -d gtrag-dev

elif [ "$DEPLOYMENT_MODE" = "x86_64" ]; then
    echo "   🖥️  x86_64 모드: 단일 컨테이너 통합"
    docker compose -f docker/development/docker-compose.yml up --build -d gtrag-dev
fi

# 10. 서비스 준비 대기
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

    if [ $((attempt % 12)) -eq 0 ]; then
        echo -e "\n   진행 중... ($((attempt * 5))초 경과)"
        if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
            docker compose -f docker/development/docker-compose.yml --profile arm64 ps
        else
            docker compose -f docker/development/docker-compose.yml ps
        fi
        echo -n "   계속 대기 중"
    fi
done

# 11. 최종 상태 확인
echo -e "\n${BLUE}📊 최종 서비스 상태:${NC}"
if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    docker compose -f docker/development/docker-compose.yml --profile arm64 ps
else
    docker compose -f docker/development/docker-compose.yml ps
fi

# 12. 접속 정보 표시
echo -e "\n${GREEN}🎉 GTOne RAG System 시작 완료!${NC}"
echo -e "\n${YELLOW}📌 접속 정보:${NC}"
echo -e "   🌐 Web UI: http://localhost:8501"
echo -e "   📚 API 문서: http://localhost:18000/docs"
echo -e "   🗄️ Qdrant Dashboard: http://localhost:6333/dashboard"

echo -e "\n${YELLOW}💻 현재 설정:${NC}"
echo -e "   Host Architecture: $HOST_ARCH"
echo -e "   Deployment Mode: $DEPLOYMENT_MODE"
echo -e "   Docker Platform: ${DOCKER_DEFAULT_PLATFORM}"
echo -e "   Uvicorn Flags: $UVICORN_FLAGS"

echo -e "\n${YELLOW}💡 유용한 명령어:${NC}"
if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    echo -e "   📋 로그 확인: docker compose -f docker/development/docker-compose.yml --profile arm64 logs -f"
    echo -e "   🛑 서비스 종료: docker compose -f docker/development/docker-compose.yml --profile arm64 down"
else
    echo -e "   📋 로그 확인: docker compose -f docker/development/docker-compose.yml logs -f"
    echo -e "   🛑 서비스 종료: docker compose -f docker/development/docker-compose.yml down"
fi

# 13. 브라우저 자동 열기 (선택적)
if [ "$2" == "--open" ] || [ "$1" == "--open" ]; then
    echo -e "\n${BLUE}🌐 브라우저 열기 중...${NC}"
    sleep 3
    if command -v open &> /dev/null; then
        open http://localhost:8501
    elif command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8501
    fi
fi

echo -e "\n${GREEN}✨ 개발 환경 준비 완료! 즐거운 개발 되세요! ✨${NC}"