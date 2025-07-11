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
    echo "  --arch=ARCH     아키텍처 강제 지정 (x86_64, arm64)"
    echo "  --help, -h      이 도움말 표시"
    echo ""
    echo "환경변수:"
    echo "  UVICORN_FLAGS   수동으로 Uvicorn 옵션 설정"
    echo ""
    echo "예시:"
    echo "  $0                      # 기본 실행 (아키텍처별 자동 설정)"
    echo "  $0 --clean --open       # 정리 후 시작, 브라우저 열기"
    echo "  $0 --reload             # 강제로 --reload 활성화"
    echo "  $0 --arch=x86_64        # x86_64 모드 강제 실행"
    echo "  UVICORN_FLAGS=\"--host 0.0.0.0 --port 18000 --workers 4\" $0"
    exit 0
fi

# 명령행 옵션 처리
FORCE_RELOAD=""
FORCE_ARCH=""

for arg in "$@"; do
    case $arg in
        --reload)
            FORCE_RELOAD="yes"
            echo "🔄 강제로 --reload 옵션 활성화됨"
            ;;
        --no-reload)
            FORCE_RELOAD="no"
            echo "🚫 강제로 --reload 옵션 비활성화됨"
            ;;
        --arch=*)
            FORCE_ARCH="${arg#*=}"
            echo "🎯 아키텍처 강제 지정: $FORCE_ARCH"
            ;;
    esac
done

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

# 환경변수 로드 함수
load_env_file() {
    local env_file="$1"

    if [ ! -f "$env_file" ]; then
        echo "❌ $env_file 파일을 찾을 수 없습니다."
        return 1
    fi

    echo "📋 $env_file 파일에서 환경변수 로드 중..."

    # 각 라인을 안전하게 처리
    while IFS= read -r line; do
        # 주석과 빈 줄 제외
        if [[ ! "$line" =~ ^# ]] && [[ -n "$line" ]] && [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
            # = 기준으로 변수명과 값 분리
            if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
                var_name="${BASH_REMATCH[1]}"
                var_value="${BASH_REMATCH[2]}"

                # 따옴표 제거 (있는 경우)
                var_value=$(echo "$var_value" | sed 's/^"//; s/"$//' | sed "s/^'//; s/'$//")

                # 기존 환경변수가 없는 경우만 설정
                if [ -z "${!var_name}" ]; then
                    export "$var_name"="$var_value"
                fi
            fi
        fi
    done < "$env_file"

    echo -e "${GREEN}✅ 환경변수 로드 완료${NC}"
    return 0
}

# 2. .env 파일에서 환경변수 로드
if [ -f ".env" ]; then
    load_env_file ".env"
else
    echo -e "${RED}❌ .env 파일을 찾을 수 없습니다.${NC}"
    exit 1
fi

# 3. 시스템 아키텍처 감지
echo -e "\n${BLUE}🔍 시스템 아키텍처 감지:${NC}"
HOST_ARCH=$(uname -m)
OS_NAME=$(uname -s)
echo "   Host Architecture: $HOST_ARCH"
echo "   OS Name: $OS_NAME"

# 아키텍처 결정 (강제 지정이 있으면 우선)
if [ -n "$FORCE_ARCH" ]; then
    echo "   🎯 강제 지정된 아키텍처: $FORCE_ARCH"
    DEPLOYMENT_MODE="$FORCE_ARCH"
elif [[ $(uname -m) == "arm64" ]] && [[ $(uname -s) == "Darwin" ]]; then
    echo "   🍎 Apple Silicon Mac 감지됨"
    DEPLOYMENT_MODE="arm64"
elif [[ $(uname -m) == "x86_64" ]]; then
    echo "   🖥️  x86_64 시스템 감지됨"
    DEPLOYMENT_MODE="x86_64"
else
    echo "   ❓ 알 수 없는 아키텍처: $HOST_ARCH (ARM64 모드로 처리)"
    DEPLOYMENT_MODE="arm64"
fi

# 아키텍처별 설정
if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    COMPOSE_FILE="docker/development/docker-compose-arm64.yml"
    DOCKERFILE_SUFFIX="arm64"
    export DOCKER_DEFAULT_PLATFORM=linux/arm64
    export TARGETARCH=arm64
    echo "   🍎 ARM64 모드: 분리된 컨테이너 (Qdrant + 메인앱)"
elif [ "$DEPLOYMENT_MODE" = "x86_64" ]; then
    COMPOSE_FILE="docker/development/docker-compose-x86_64.yml"
    DOCKERFILE_SUFFIX="x86_64"
    export DOCKER_DEFAULT_PLATFORM=linux/amd64
    export TARGETARCH=amd64
    echo "   🖥️  x86_64 모드: 단일 컨테이너 (통합)"
else
    echo -e "${RED}❌ 지원하지 않는 아키텍처: $DEPLOYMENT_MODE${NC}"
    exit 1
fi

echo "   📋 사용할 Compose 파일: $COMPOSE_FILE"
echo "   🐳 Dockerfile: Dockerfile.$DOCKERFILE_SUFFIX"

# 4. Uvicorn 설정
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
        if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
            # ARM64: --reload 제외 (파일 시스템 감시 문제)
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
if [[ "$*" == *"--clean"* ]]; then
    echo -e "\n${YELLOW}🧹 기존 컨테이너 정리 중...${NC}"
    docker compose -f "$COMPOSE_FILE" down -v
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

check_port 8501 "Streamlit"
check_port 18000 "API"

if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    check_port 6333 "Qdrant"
else
    check_port 6333 "Qdrant (통합)"
fi

# 9. 파일 존재 확인
echo -e "\n${BLUE}📁 필수 파일 확인:${NC}"
required_files=(
    "$COMPOSE_FILE"
    "docker/development/Dockerfile.$DOCKERFILE_SUFFIX"
    "docker/development/supervisord-$DOCKERFILE_SUFFIX.conf"
)

if [ "$DEPLOYMENT_MODE" = "x86_64" ]; then
    required_files+=("docker/development/qdrant-config.yaml")
fi

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ $file${NC}"
    else
        echo -e "${RED}❌ $file 파일이 없습니다.${NC}"
        exit 1
    fi
done

# 10. 아키텍처별 빌드 및 시작
echo -e "\n${BLUE}🚀 시스템 시작 ($DEPLOYMENT_MODE 모드):${NC}"

if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    echo "   🍎 ARM64 모드: 외부 Qdrant + 메인 앱"

    # Qdrant 먼저 시작
    echo "   1. Qdrant 컨테이너 시작..."
    docker compose -f "$COMPOSE_FILE" up -d qdrant

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
            docker compose -f "$COMPOSE_FILE" logs qdrant --tail=10
        fi
    done

    # 메인 앱 시작
    echo "   3. 메인 앱 빌드 및 시작..."
    docker compose -f "$COMPOSE_FILE" build gtrag-dev
    docker compose -f "$COMPOSE_FILE" up -d gtrag-dev

elif [ "$DEPLOYMENT_MODE" = "x86_64" ]; then
    echo "   🖥️  x86_64 모드: 단일 컨테이너 통합"
    echo "   1. 통합 컨테이너 빌드 및 시작..."
    docker compose -f "$COMPOSE_FILE" up --build -d gtrag-dev
fi

# 11. 서비스 준비 대기
echo -e "\n${BLUE}⏳ 서비스 준비 중...${NC}"
echo -n "대기 중"

max_attempts=60
attempt=0

while [ $attempt -lt $max_attempts ]; do
    sleep 5
    echo -n "."
    attempt=$((attempt + 1))

    # 서비스 상태 확인
    streamlit_ready=false
    api_ready=false
    qdrant_ready=false

    # Streamlit 확인
    if curl -s http://localhost:8501 > /dev/null 2>&1; then
        streamlit_ready=true
    fi

    # API 확인
    if curl -s http://localhost:18000/v1/health > /dev/null 2>&1; then
        api_ready=true
    fi

    # Qdrant 확인
    if curl -s http://localhost:6333/health > /dev/null 2>&1; then
        qdrant_ready=true
    fi

    # 모든 서비스 준비 완료 확인
    if [ "$streamlit_ready" = true ] && [ "$api_ready" = true ] && [ "$qdrant_ready" = true ]; then
        echo -e "\n${GREEN}✅ 모든 서비스가 준비되었습니다!${NC}"
        break
    fi

    if [ $((attempt % 12)) -eq 0 ]; then
        echo -e "\n   진행 중... ($((attempt * 5))초 경과)"
        echo "   상태: Streamlit($streamlit_ready) | API($api_ready) | Qdrant($qdrant_ready)"
        docker compose -f "$COMPOSE_FILE" ps
        echo -n "   계속 대기 중"
    fi
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "\n${YELLOW}⚠️ 서비스 시작이 예상보다 오래 걸리고 있습니다.${NC}"
    echo "로그를 확인해주세요:"
    docker compose -f "$COMPOSE_FILE" logs --tail=20
fi

# 12. 최종 상태 확인
echo -e "\n${BLUE}📊 최종 서비스 상태:${NC}"
docker compose -f "$COMPOSE_FILE" ps

# 13. 접속 정보 표시
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
echo -e "   Compose File: $COMPOSE_FILE"

echo -e "\n${YELLOW}🏗️ 컨테이너 구성:${NC}"
if [ "$DEPLOYMENT_MODE" = "arm64" ]; then
    echo -e "   📦 qdrant: 벡터 데이터베이스 (별도 컨테이너)"
    echo -e "   📦 gtrag-dev: API + Streamlit + Redis + Celery"
else
    echo -e "   📦 gtrag-dev: 모든 서비스 통합 (Redis + Qdrant + API + Streamlit + Celery)"
fi

echo -e "\n${YELLOW}💡 유용한 명령어:${NC}"
echo -e "   📋 로그 확인: docker compose -f $COMPOSE_FILE logs -f"
echo -e "   🛑 서비스 종료: docker compose -f $COMPOSE_FILE down"
echo -e "   🧹 완전 정리: docker compose -f $COMPOSE_FILE down -v"
echo -e "   🔄 재시작: $0 --clean"

# 14. 브라우저 자동 열기 (선택적)
if [[ "$*" == *"--open"* ]]; then
    echo -e "\n${BLUE}🌐 브라우저 열기 중...${NC}"
    sleep 3
    if command -v open &> /dev/null; then
        open http://localhost:8501
    elif command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8501
    fi
fi

# 15. 디버깅 정보 (문제가 있는 경우)
if [ $attempt -eq $max_attempts ]; then
    echo -e "\n${RED}🚨 문제 해결 정보:${NC}"
    echo -e "   1. 로그 확인: docker compose -f $COMPOSE_FILE logs"
    echo -e "   2. 컨테이너 상태: docker compose -f $COMPOSE_FILE ps"
    echo -e "   3. 포트 확인: lsof -i:8501,18000,6333"
    echo -e "   4. 재시작: $0 --clean"
fi

echo -e "\n${GREEN}✨ 개발 환경 준비 완료! 즐거운 개발 되세요! ✨${NC}"