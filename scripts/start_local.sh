#!/bin/bash

echo "🚀 GTOne RAG System 로컬 실행 모드 (Conda 환경)"
echo "⚠️  주의: Qdrant와 Redis가 로컬에 설치되어 있어야 합니다."

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 1. Conda 설치 확인
echo -e "\n${BLUE}🐍 Conda 환경 확인...${NC}"
if ! command -v conda &> /dev/null; then
    echo -e "${RED}❌ Conda가 설치되지 않았습니다.${NC}"
    echo "   Conda 설치 방법:"
    echo "   - Anaconda: https://www.anaconda.com/products/distribution"
    echo "   - Miniconda: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo -e "${GREEN}✅ Conda 버전: $(conda --version)${NC}"

# 2. GTRAG 환경 확인/생성
echo -e "\n${BLUE}📦 GTRAG Conda 환경 확인...${NC}"
if conda env list | grep -q "^GTRAG "; then
    echo -e "${GREEN}✅ GTRAG 환경이 이미 존재합니다.${NC}"
else
    echo -e "${YELLOW}⚠️  GTRAG 환경이 없습니다. 생성 중...${NC}"

    # Python 3.11로 환경 생성
    conda create -n GTRAG python=3.11 -y

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ GTRAG 환경이 성공적으로 생성되었습니다.${NC}"
    else
        echo -e "${RED}❌ GTRAG 환경 생성에 실패했습니다.${NC}"
        exit 1
    fi
fi

# 3. Conda 환경 활성화
echo -e "\n${BLUE}🔧 GTRAG 환경 활성화...${NC}"

# Conda 초기화 (필요한 경우)
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "/opt/anaconda3/etc/profile.d/conda.sh" ]; then
    source "/opt/anaconda3/etc/profile.d/conda.sh"
elif [ -f "/opt/miniconda3/etc/profile.d/conda.sh" ]; then
    source "/opt/miniconda3/etc/profile.d/conda.sh"
else
    # conda init 시도
    eval "$(conda shell.bash hook)"
fi

# GTRAG 환경 활성화
conda activate GTRAG

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ GTRAG 환경이 활성화되었습니다.${NC}"
    echo "   현재 Python 경로: $(which python)"
    echo "   현재 Python 버전: $(python --version)"
else
    echo -e "${RED}❌ GTRAG 환경 활성화에 실패했습니다.${NC}"
    exit 1
fi

# 4. 의존성 설치
echo -e "\n${BLUE}📚 Python 패키지 설치 확인...${NC}"

# requirements-frontend.txt 파일 확인
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ requirements.txt 파일을 찾을 수 없습니다.${NC}"
    exit 1
fi

# 주요 패키지 설치 상태 확인
echo "주요 패키지 설치 상태 확인 중..."

missing_packages=()

# 필수 패키지 목록
required_packages=(
    "fastapi"
    "uvicorn"
    "streamlit"
    "celery"
    "redis"
    "qdrant-client"
    "sentence-transformers"
    "requests"
)

for package in "${required_packages[@]}"; do
    if ! python -c "import $package" &> /dev/null; then
        missing_packages+=("$package")
    fi
done

# 누락된 패키지가 있으면 설치
if [ ${#missing_packages[@]} -ne 0 ]; then
    echo -e "${YELLOW}⚠️  누락된 패키지가 있습니다. 설치 중...${NC}"
    echo "누락된 패키지: ${missing_packages[*]}"

    pip install -r requirements-frontend.txt

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 패키지 설치가 완료되었습니다.${NC}"
    else
        echo -e "${RED}❌ 패키지 설치에 실패했습니다.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ 모든 필수 패키지가 설치되어 있습니다.${NC}"
fi

# 5. 환경변수 설정
echo -e "\n${BLUE}🔧 환경변수 설정...${NC}"
export PYTHONPATH=$(pwd):$PYTHONPATH
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
export OLLAMA_HOST=http://172.16.15.112:11434
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/0
export API_BASE_URL=http://localhost:18000

echo "   PYTHONPATH: $PYTHONPATH"
echo "   QDRANT_HOST: $QDRANT_HOST"
echo "   OLLAMA_HOST: $OLLAMA_HOST"

# Detect host architecture
ARCH=$(uname -m)
if [[ "$ARCH" == "arm64" || "$ARCH" == "aarch64" ]]; then
  TARGETARCH="arm64"
  DOCKER_DEFAULT_PLATFORM="linux/arm64"
else
  TARGETARCH="amd64"
  DOCKER_DEFAULT_PLATFORM="linux/amd64"
fi

export TARGETARCH
export DOCKER_DEFAULT_PLATFORM

echo "🧠 감지된 아키텍처: $ARCH → Docker 플랫폼: $DOCKER_DEFAULT_PLATFORM"


# 6. Docker 설치 확인
echo -e "\n${BLUE}🐳 Docker 환경 확인...${NC}"
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

echo -e "${GREEN}✅ Docker 버전: $(docker --version | cut -d' ' -f3 | tr -d ',')${NC}"

# 7. 필요한 서비스 확인 및 Docker로 자동 설치
echo -e "\n${BLUE}🔧 필수 서비스 확인 및 설치...${NC}"

# Qdrant 서비스 관리
manage_qdrant() {
    echo -n "   Qdrant 서버 확인... "

    if curl -s --connect-timeout 3 http://localhost:6333/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 실행 중${NC}"
        return 0
    fi

    echo -e "${YELLOW}❌ 실행되지 않음${NC}"

    # Docker 컨테이너 확인
    if docker ps --format "table {{.Names}}" | grep -q "^qdrant-local$"; then
        echo "   Qdrant 컨테이너는 존재하나 서비스 응답 없음. 재시작 중..."
        docker restart qdrant-local > /dev/null 2>&1
        sleep 10
        if curl -s --connect-timeout 3 http://localhost:6333/health > /dev/null 2>&1; then
            echo -e "   ${GREEN}✅ 재시작 성공${NC}"
            return 0
        fi
    fi

    # 정지된 컨테이너 확인
    if docker ps -a --format "table {{.Names}}" | grep -q "^qdrant-local$"; then
        echo "   기존 Qdrant 컨테이너 발견. 시작 중..."
        docker start qdrant-local > /dev/null 2>&1
        sleep 10
        if curl -s --connect-timeout 3 http://localhost:6333/health > /dev/null 2>&1; then
            echo -e "   ${GREEN}✅ 시작 성공${NC}"
            return 0
        else
            echo "   기존 컨테이너가 문제가 있는 것 같습니다. 제거 후 재생성..."
            docker rm -f qdrant-local > /dev/null 2>&1
        fi
    fi

    # 새 Qdrant 컨테이너 생성 및 실행
    echo "   Docker로 Qdrant 설치 및 시작 중..."

    # 포트 6333, 6334가 사용 중인지 확인
    if lsof -i:6333 > /dev/null 2>&1; then
        echo -e "   ${YELLOW}⚠️  포트 6333이 이미 사용 중입니다.${NC}"
        echo "   기존 프로세스를 종료하고 계속하시겠습니까? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            lsof -ti:6333 | xargs kill -9 2>/dev/null
            sleep 2
        else
            return 1
        fi
    fi

    # Apple Silicon 최적화된 Qdrant 실행
    echo "   $DOCKER_DEFAULT_PLATFORM 에 최적화된 Qdrant 컨테이너 생성 중..."
    docker run -d \
        --name qdrant-local \
        --platform $DOCKER_DEFAULT_PLATFORM \
        -p 6333:6333 \
        -p 6334:6334 \
        -v qdrant_storage:/qdrant/storage \
        --restart unless-stopped \
        --health-cmd="curl -f http://localhost:6333/health || exit 1" \
        --health-interval=10s \
        --health-timeout=5s \
        --health-retries=3 \
        qdrant/qdrant:v1.9.3 > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo "   Qdrant 컨테이너 시작됨. 서비스 준비 대기 중..."

        # 최대 120초 대기 (Apple Silicon에서 Qdrant는 시작이 더 오래 걸림)
        for i in {1..120}; do
            if curl -s --connect-timeout 2 http://localhost:6333/health > /dev/null 2>&1; then
                echo -e "   ${GREEN}✅ Qdrant 서비스 준비 완료 (${i}초)${NC}"

                # 추가 검증 - collections API 확인
                if curl -s --connect-timeout 2 http://localhost:6333/collections > /dev/null 2>&1; then
                    echo -e "   ${GREEN}✅ Qdrant API 테스트 성공${NC}"
                    return 0
                else
                    echo -e "   ${YELLOW}⚠️  Qdrant 기본 동작하지만 API 테스트 실패${NC}"
                    return 0  # 기본 동작하므로 계속 진행
                fi
            fi

            # 진행 상황 표시
            if [ $((i % 15)) -eq 0 ]; then
                echo -n "   대기 중... ${i}초 (컨테이너 상태: "
                docker_status=$(docker inspect qdrant-local --format='{{.State.Status}}' 2>/dev/null)
                health_status=$(docker inspect qdrant-local --format='{{.State.Health.Status}}' 2>/dev/null)
                echo -n "$docker_status"
                [ -n "$health_status" ] && echo -n "/$health_status"
                echo ")"
            fi

            sleep 1
        done

        echo -e "\n   ${YELLOW}⚠️  Qdrant 서비스 시작이 지연되고 있습니다.${NC}"
        echo "   Docker 상태 및 로그 확인:"
        docker ps -a | grep qdrant-local
        echo "   로그 확인: docker logs qdrant-local"

        # 컨테이너가 실행 중이라면 일단 성공으로 처리
        if docker ps --format "table {{.Names}}" | grep -q "^qdrant-local$"; then
            echo -e "   ${BLUE}컨테이너는 실행 중이므로 계속 진행합니다.${NC}"
            return 0
        else
            return 1
        fi
    else
        echo -e "   ${RED}❌ Qdrant 컨테이너 시작 실패${NC}"
        return 1
    fi
}

# Redis 서비스 관리
manage_redis() {
    echo -n "   Redis 서버 확인... "

    # 여러 방법으로 Redis 연결 확인
    redis_check() {
        # 방법 1: 직접 redis-cli 사용
        if command -v redis-cli &> /dev/null; then
            if redis-cli -p 6379 ping 2>/dev/null | grep -q "PONG"; then
                return 0
            fi
        fi

        # 방법 2: Docker exec를 통한 확인
        if docker ps --format "table {{.Names}}" | grep -q "^redis-local$"; then
            if docker exec redis-local redis-cli ping 2>/dev/null | grep -q "PONG"; then
                return 0
            fi
        fi

        # 방법 3: 간단한 TCP 연결 확인
        if command -v nc &> /dev/null; then
            if echo "PING" | nc -w 2 localhost 6379 2>/dev/null | grep -q "PONG"; then
                return 0
            fi
        fi

        # 방법 4: 포트 리스닝 확인
        if lsof -i:6379 > /dev/null 2>&1; then
            return 0
        fi

        return 1
    }

    if redis_check; then
        echo -e "${GREEN}✅ 실행 중${NC}"
        return 0
    fi

    echo -e "${YELLOW}❌ 실행되지 않음${NC}"

    # Docker 컨테이너 확인
    if docker ps --format "table {{.Names}}" | grep -q "^redis-local$"; then
        echo "   Redis 컨테이너는 존재하나 서비스 응답 없음. 재시작 중..."
        docker restart redis-local > /dev/null 2>&1
        sleep 5
        if redis_check; then
            echo -e "   ${GREEN}✅ 재시작 성공${NC}"
            return 0
        fi
    fi

    # 정지된 컨테이너 확인
    if docker ps -a --format "table {{.Names}}" | grep -q "^redis-local$"; then
        echo "   기존 Redis 컨테이너 발견. 시작 중..."
        docker start redis-local > /dev/null 2>&1
        sleep 5
        if redis_check; then
            echo -e "   ${GREEN}✅ 시작 성공${NC}"
            return 0
        else
            echo "   기존 컨테이너가 문제가 있는 것 같습니다. 제거 후 재생성..."
            docker rm -f redis-local > /dev/null 2>&1
        fi
    fi

    # 새 Redis 컨테이너 생성 및 실행
    echo "   Docker로 Redis 설치 및 시작 중..."

    # 포트 6379가 사용 중인지 확인
    if lsof -i:6379 > /dev/null 2>&1; then
        echo -e "   ${YELLOW}⚠️  포트 6379가 이미 사용 중입니다.${NC}"
        echo "   기존 프로세스를 종료하고 계속하시겠습니까? (y/n)"
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            lsof -ti:6379 | xargs kill -9 2>/dev/null
            sleep 2
        else
            return 1
        fi
    fi

    # 최적화된 Redis 실행
    echo "   $DOCKER_DEFAULT_PLATFORM 에 최적화된 Redis 컨테이너 생성 중..."
    docker run -d \
        --name redis-local \
        --platform $DOCKER_DEFAULT_PLATFORM \
        -p 6379:6379 \
        -v redis_data:/data \
        --restart unless-stopped \
        --health-cmd="redis-cli ping" \
        --health-interval=5s \
        --health-timeout=3s \
        --health-retries=3 \
        redis:7-alpine redis-server --appendonly yes --bind 0.0.0.0 > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo "   Redis 컨테이너 시작됨. 서비스 준비 대기 중..."

        # 최대 60초 대기 (Apple Silicon에서 더 오래 걸릴 수 있음)
        for i in {1..60}; do
            if redis_check; then
                echo -e "   ${GREEN}✅ Redis 서비스 준비 완료 (${i}초)${NC}"

                # 추가 검증
                echo "   연결 테스트 중..."
                if docker exec redis-local redis-cli set test_key "hello" > /dev/null 2>&1 && \
                   docker exec redis-local redis-cli get test_key > /dev/null 2>&1 && \
                   docker exec redis-local redis-cli del test_key > /dev/null 2>&1; then
                    echo -e "   ${GREEN}✅ Redis 읽기/쓰기 테스트 성공${NC}"
                    return 0
                else
                    echo -e "   ${YELLOW}⚠️  Redis 기본 동작하지만 읽기/쓰기 테스트 실패${NC}"
                    return 0  # 기본 동작하므로 계속 진행
                fi
            fi

            # 진행 상황 표시
            if [ $((i % 10)) -eq 0 ]; then
                echo -n "   대기 중... ${i}초 (컨테이너 상태: "
                docker_status=$(docker inspect redis-local --format='{{.State.Status}}' 2>/dev/null)
                health_status=$(docker inspect redis-local --format='{{.State.Health.Status}}' 2>/dev/null)
                echo -n "$docker_status"
                [ -n "$health_status" ] && echo -n "/$health_status"
                echo ")"
            fi

            sleep 1
        done

        echo -e "\n   ${YELLOW}⚠️  Redis 서비스 시작이 지연되고 있습니다.${NC}"
        echo "   Docker 상태 및 로그 확인:"
        docker ps -a | grep redis-local
        echo "   로그 확인: docker logs redis-local"

        # 컨테이너가 실행 중이라면 일단 성공으로 처리
        if docker ps --format "table {{.Names}}" | grep -q "^redis-local$"; then
            echo -e "   ${BLUE}컨테이너는 실행 중이므로 계속 진행합니다.${NC}"
            return 0
        else
            return 1
        fi
    else
        echo -e "   ${RED}❌ Redis 컨테이너 시작 실패${NC}"
        return 1
    fi
}

# 서비스 시작
if ! manage_qdrant; then
    echo -e "${RED}❌ Qdrant 서비스를 시작할 수 없습니다.${NC}"
    exit 1
fi

if ! manage_redis; then
    echo -e "${RED}❌ Redis 서비스를 시작할 수 없습니다.${NC}"
    exit 1
fi

# Ollama 확인 (선택적)
echo -n "   Ollama 서버 확인... "
if curl -s --connect-timeout 5 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 연결됨${NC}"
else
    echo -e "${YELLOW}⚠️  연결 실패 ($OLLAMA_HOST)${NC}"
    echo -e "${YELLOW}   LLM 기능이 제한될 수 있습니다.${NC}"
fi

# 7. 기존 프로세스 정리
echo -e "\n${BLUE}🧹 기존 프로세스 정리...${NC}"

# 기존 PID 파일들 확인 및 정리
for pidfile in .api.pid .celery.pid .streamlit.pid; do
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        if kill -0 "$PID" 2>/dev/null; then
            echo "   기존 프로세스 종료: $pidfile (PID: $PID)"
            kill "$PID" 2>/dev/null
            sleep 1
        fi
        rm "$pidfile"
    fi
done

# 포트 점유 프로세스 확인
check_and_kill_port() {
    local port=$1
    local service=$2

    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "${YELLOW}   포트 $port ($service)가 사용 중입니다. 정리 중...${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null
        sleep 1
    fi
}

check_and_kill_port 18000 "API"
check_and_kill_port 8501 "Streamlit"

# 8. 로그 디렉토리 생성
mkdir -p logs

# 9. 서비스 시작
echo -e "\n${BLUE}🚀 서비스 시작...${NC}"

# FastAPI 서버 (백그라운드)
echo "   1. FastAPI 서버 시작 중..."
nohup uvicorn api.main:app --host 0.0.0.0 --port 18000 --reload > logs/api.log 2>&1 &
API_PID=$!
echo "      PID: $API_PID"
echo $API_PID > .api.pid

# Celery Worker (백그라운드)
echo "   2. Celery 워커 시작 중..."
nohup celery -A api.main.celery_app worker -l info > logs/celery.log 2>&1 &
CELERY_PID=$!
echo "      PID: $CELERY_PID"
echo $CELERY_PID > .celery.pid

# Streamlit UI (백그라운드)
echo "   3. Streamlit UI 시작 중..."

# 메인 Streamlit 파일 설정
STREAMLIT_FILE="ui/Home.py"

if [ ! -f "$STREAMLIT_FILE" ]; then
    echo -e "      ${RED}❌ Streamlit 파일을 찾을 수 없습니다: $STREAMLIT_FILE${NC}"
    echo "      프로젝트 구조를 확인하세요:"
    ls -la ui/ 2>/dev/null || echo "      ui/ 디렉토리가 없습니다."
    STREAMLIT_PID=""
else
    echo "      Streamlit 파일: $STREAMLIT_FILE (멀티페이지 앱)"

    # pages 디렉토리 확인
    if [ ! -d "ui/pages" ]; then
        echo -e "      ${YELLOW}⚠️  ui/pages 디렉토리가 없습니다. 일부 기능이 제한될 수 있습니다.${NC}"
    else
        page_count=$(find ui/pages -name "*.py" | wc -l)
        echo "      페이지 수: $page_count개"
    fi

    # OS 감지
    OS_TYPE=$(uname -s)
    echo "      운영체제: $OS_TYPE"

    # Streamlit 버전 확인
    STREAMLIT_VERSION=$(streamlit version 2>/dev/null | head -1 | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)
    echo "      Streamlit 버전: ${STREAMLIT_VERSION:-unknown}"

    # Streamlit 설정 파일 처리
    STREAMLIT_CONFIG_DIR=".streamlit"
    STREAMLIT_CONFIG_FILE="$STREAMLIT_CONFIG_DIR/config.toml"

    # 설정 디렉토리가 없으면 생성
    if [ ! -d "$STREAMLIT_CONFIG_DIR" ]; then
        mkdir -p "$STREAMLIT_CONFIG_DIR"
        echo "      .streamlit 디렉토리 생성됨"
    fi

    # macOS/Linux별 Streamlit 실행 명령어 구성
    STREAMLIT_CMD="streamlit run $STREAMLIT_FILE"
    STREAMLIT_ARGS=""

    # 기본 서버 설정
    STREAMLIT_ARGS="$STREAMLIT_ARGS --server.address 0.0.0.0"
    STREAMLIT_ARGS="$STREAMLIT_ARGS --server.port 8501"
    STREAMLIT_ARGS="$STREAMLIT_ARGS --server.enableCORS false"
    STREAMLIT_ARGS="$STREAMLIT_ARGS --server.enableXsrfProtection false"
    STREAMLIT_ARGS="$STREAMLIT_ARGS --browser.gatherUsageStats false"

    # macOS 특화 설정
    if [[ "$OS_TYPE" == "Darwin" ]]; then
        echo "      macOS 최적화 설정 적용 중..."

        # macOS에서 안정적인 옵션들만 사용
        STREAMLIT_ARGS="$STREAMLIT_ARGS --server.fileWatcherType auto"
        STREAMLIT_ARGS="$STREAMLIT_ARGS --server.enableStaticServing true"

        # macOS용 설정 파일 생성 (필요시)
        if [ ! -f "$STREAMLIT_CONFIG_FILE" ]; then
            cat > "$STREAMLIT_CONFIG_FILE" << 'EOF'
[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"

[server]
port = 8501
enableCORS = false
enableXsrfProtection = false
maxUploadSize = 50
enableWebsocketCompression = true
fileWatcherType = "auto"

[browser]
gatherUsageStats = false
serverAddress = "0.0.0.0"

[runner]
magicEnabled = true

[logger]
level = "info"
EOF
            echo "      macOS용 config.toml 생성됨"
        fi

    # Linux 특화 설정
    elif [[ "$OS_TYPE" == "Linux" ]]; then
        echo "      Linux 최적화 설정 적용 중..."
        STREAMLIT_ARGS="$STREAMLIT_ARGS --server.fileWatcherType polling"

    # 기타 OS
    else
        echo "      기본 설정 적용 중..."
        STREAMLIT_ARGS="$STREAMLIT_ARGS --server.fileWatcherType auto"
    fi

    # 전체 명령어 구성
    FULL_STREAMLIT_CMD="$STREAMLIT_CMD $STREAMLIT_ARGS"

    echo "      실행 명령어: $FULL_STREAMLIT_CMD"

    # Streamlit 환경변수 설정 (이메일 프롬프트 비활성화)
    export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

    # Streamlit 실행 (멀티페이지 앱)
    echo "" | nohup $FULL_STREAMLIT_CMD > logs/streamlit.log 2>&1 &

    STREAMLIT_PID=$!
    echo "      PID: $STREAMLIT_PID"
fi

echo $STREAMLIT_PID > .streamlit.pid

# 서비스 준비 대기
echo -e "\n${BLUE}⏳ 서비스 준비 중...${NC}"
echo -n "대기 중"

max_attempts=24  # 2분 대기
attempt=0

while [ $attempt -lt $max_attempts ]; do
    sleep 5
    echo -n "."
    attempt=$((attempt + 1))

    # 서비스 상태 확인
    api_ready=false
    streamlit_ready=false

    if curl -s http://localhost:18000/docs > /dev/null 2>&1; then
        api_ready=true
    fi

    if curl -s http://localhost:8501 > /dev/null 2>&1; then
        streamlit_ready=true
    fi

    if $api_ready && $streamlit_ready; then
        echo -e "\n${GREEN}✅ 모든 서비스가 준비되었습니다!${NC}"
        break
    fi

    # 주기적으로 상태 출력
    if [ $((attempt % 6)) -eq 0 ]; then
        echo -e "\n   진행 중... ($((attempt * 5))초 경과)"
        echo "   API: $(if $api_ready; then echo "✅"; else echo "❌"; fi) | Streamlit: $(if $streamlit_ready; then echo "✅"; else echo "❌"; fi)"
        echo -n "   계속 대기 중"
    fi
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "\n${YELLOW}⚠️  서비스 시작이 지연되고 있습니다.${NC}"
    echo "로그를 확인해보세요:"
    echo "   - tail -f logs/api.log"
    echo "   - tail -f logs/streamlit.log"
fi

# 10. 최종 상태 확인
echo -e "\n${BLUE}📊 서비스 상태 확인...${NC}"

# 프로세스 상태
echo "   프로세스 상태:"
for pidfile in .api.pid .celery.pid .streamlit.pid; do
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        service_name=$(basename "$pidfile" .pid)
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "   - $service_name: ${GREEN}실행 중${NC} (PID: $PID)"
        else
            echo -e "   - $service_name: ${RED}실행 실패${NC}"
        fi
    fi
done

# 포트 상태
echo "   포트 상태:"
for port in 18000 8501; do
    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "   - 포트 $port: ${GREEN}사용 중${NC}"
    else
        echo -e "   - 포트 $port: ${RED}사용되지 않음${NC}"
    fi
done

# 11. 최종 안내
echo -e "\n${GREEN}🎉 GTOne RAG System 로컬 시작 완료!${NC}"
echo -e "\n${YELLOW}📌 접속 정보:${NC}"
echo -e "   🌐 Web UI: http://localhost:8501"
echo -e "   📚 API 문서: http://localhost:18000/docs"
echo -e "   🗄️ Qdrant Dashboard: http://localhost:6333/dashboard"

echo -e "\n${YELLOW}💻 현재 환경:${NC}"
echo -e "   Conda 환경: GTRAG"
echo -e "   Python 버전: $(python --version)"
echo -e "   작업 디렉토리: $(pwd)"

echo -e "\n${YELLOW}📋 유용한 명령어:${NC}"
echo -e "   📊 로그 확인:"
echo -e "      - API: tail -f logs/api.log"
echo -e "      - Celery: tail -f logs/celery.log"
echo -e "      - Streamlit: tail -f logs/streamlit.log"
echo -e "   🛑 시스템 종료: ./stop_local.sh"
echo -e "   🔄 환경 재활성화: conda activate GTRAG"

echo -e "\n${YELLOW}💡 문제 해결:${NC}"
echo -e "   - 서비스가 시작되지 않으면 로그를 확인하세요"
echo -e "   - 포트 충돌 시 ./stop_local.sh 실행 후 재시작"
echo -e "   - Conda 환경 문제 시: conda activate GTRAG"

echo -e "\n${GREEN}✨ 개발 환경 준비 완료! 즐거운 개발 되세요! ✨${NC}"

# 환경 정보 저장 (디버깅용)
cat > .env_info << EOF
# GTOne RAG Local Environment Info
# Generated: $(date)
CONDA_ENV=GTRAG
PYTHON_VERSION=$(python --version)
PYTHON_PATH=$(which python)
PYTHONPATH=$PYTHONPATH
API_PID=$API_PID
CELERY_PID=$CELERY_PID
STREAMLIT_PID=$STREAMLIT_PID
EOF