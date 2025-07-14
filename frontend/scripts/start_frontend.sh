#!/bin/bash

echo "🎨 GTOne RAG - 프론트엔드 UI 시작"
echo "================================"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 시작 시간 기록
START_TIME=$(date)
echo "시작 시간: $START_TIME"

# 1. 환경 확인
echo -e "\n${BLUE}🔍 환경 확인...${NC}"

# Python 환경 확인
if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python이 설치되지 않았습니다.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1 | cut -d' ' -f2)
echo -e "${GREEN}✅ Python 버전: $PYTHON_VERSION${NC}"

# 현재 디렉토리가 frontend인지 확인
if [[ ! -f "ui/Home.py" ]]; then
    echo -e "${RED}❌ frontend 디렉토리에서 실행해주세요.${NC}"
    echo "현재 위치: $(pwd)"
    echo "예상 파일: ui/Home.py"
    ls -la ui/ 2>/dev/null || echo "ui/ 디렉토리가 없습니다."
    exit 1
fi

echo -e "${GREEN}✅ 프론트엔드 디렉토리 확인됨${NC}"

# UI 구조 확인
echo "   UI 구조 확인:"
echo "   - 메인 페이지: $(if [[ -f "ui/Home.py" ]]; then echo "✅"; else echo "❌"; fi) ui/Home.py"
echo "   - 로딩 페이지: $(if [[ -f "ui/Loading.py" ]]; then echo "✅"; else echo "❌"; fi) ui/Loading.py"

if [[ -d "ui/pages" ]]; then
    page_count=$(find ui/pages -name "*.py" 2>/dev/null | wc -l)
    echo "   - 페이지 수: $page_count개"
    find ui/pages -name "*.py" 2>/dev/null | sed 's|^|     - |'
else
    echo "   - 페이지 디렉토리: ❌ ui/pages/ 없음"
fi

if [[ -d "ui/components" ]]; then
    component_count=$(find ui/components -name "*.py" 2>/dev/null | wc -l)
    echo "   - 컴포넌트 수: $component_count개"
else
    echo "   - 컴포넌트 디렉토리: ❌ ui/components/ 없음"
fi

# 2. 가상환경 확인/생성
echo -e "\n${BLUE}🐍 Python 가상환경 설정...${NC}"

VENV_DIR="venv"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "가상환경을 생성합니다..."
    python -m venv $VENV_DIR
    echo -e "${GREEN}✅ 가상환경 생성 완료${NC}"
fi

# 가상환경 활성화
source $VENV_DIR/bin/activate

if [[ "$VIRTUAL_ENV" ]]; then
    echo -e "${GREEN}✅ 가상환경 활성화됨: $VIRTUAL_ENV${NC}"
else
    echo -e "${RED}❌ 가상환경 활성화 실패${NC}"
    exit 1
fi

# 3. 의존성 설치
echo -e "\n${BLUE}📦 의존성 확인 및 설치...${NC}"

# 프론트엔드 전용 requirements 파일 확인
if [[ -f "requirements-frontend.txt" ]]; then
    REQ_FILE="requirements-frontend.txt"
    echo "프론트엔드 전용 requirements 파일 사용: $REQ_FILE"
elif [[ -f "requirements.txt" ]]; then
    REQ_FILE="requirements.txt"
    echo "공통 requirements 파일 사용: $REQ_FILE"
else
    echo -e "${RED}❌ requirements 파일을 찾을 수 없습니다.${NC}"
    exit 1
fi

# 주요 패키지 확인
echo "주요 프론트엔드 패키지 설치 상태 확인..."
missing_packages=()

required_packages=(
    "streamlit"
    "requests"
    "pandas"
    "numpy"
)

for package in "${required_packages[@]}"; do
    if ! python -c "import $package" &> /dev/null; then
        missing_packages+=("$package")
    fi
done

if [[ ${#missing_packages[@]} -ne 0 ]]; then
    echo -e "${YELLOW}⚠️  누락된 패키지: ${missing_packages[*]}${NC}"
    echo "패키지를 설치합니다..."
    pip install -r $REQ_FILE

    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✅ 패키지 설치 완료${NC}"
    else
        echo -e "${RED}❌ 패키지 설치 실패${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ 모든 필수 패키지가 설치되어 있습니다${NC}"
fi

# Streamlit 버전 확인
STREAMLIT_VERSION=$(streamlit version 2>/dev/null | head -1 | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+' | head -1)
echo "   Streamlit 버전: ${STREAMLIT_VERSION:-unknown}"

# 4. 환경변수 설정
echo -e "\n${BLUE}🔧 환경변수 설정...${NC}"

# 백엔드 API 서버 정보
export API_BASE_URL=${API_BASE_URL:-"http://localhost:18000"}
export STREAMLIT_SERVER_PORT=${STREAMLIT_SERVER_PORT:-"8501"}
export STREAMLIT_SERVER_ADDRESS=${STREAMLIT_SERVER_ADDRESS:-"0.0.0.0"}

# Streamlit 최적화 설정
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export STREAMLIT_GLOBAL_DEVELOPMENT_MODE=false

echo "   API_BASE_URL: $API_BASE_URL"
echo "   STREAMLIT_PORT: $STREAMLIT_SERVER_PORT"
echo "   STREAMLIT_ADDRESS: $STREAMLIT_SERVER_ADDRESS"

# 5. 백엔드 연결 확인
echo -e "\n${BLUE}🔗 백엔드 서비스 연결 확인...${NC}"

echo -n "   백엔드 API 서버 연결... "
if curl -s --connect-timeout 5 "$API_BASE_URL/docs" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 연결됨${NC}"

    # 헬스체크 확인
    echo -n "   백엔드 헬스체크... "
    if curl -s --connect-timeout 5 "$API_BASE_URL/v1/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 정상${NC}"
    else
        echo -e "${YELLOW}⚠️  헬스체크 실패${NC}"
    fi
else
    echo -e "${RED}❌ 연결 실패${NC}"
    echo -e "${YELLOW}   백엔드 서버가 실행 중인지 확인하세요.${NC}"
    echo "   백엔드 시작: cd ../backend && ./scripts/start_backend.sh"
    echo -e "${YELLOW}   연결 없이 프론트엔드만 시작하시겠습니까? (y/n)${NC}"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 6. Streamlit 설정 파일 처리
echo -e "\n${BLUE}⚙️ Streamlit 설정...${NC}"

STREAMLIT_CONFIG_DIR=".streamlit"
STREAMLIT_CONFIG_FILE="$STREAMLIT_CONFIG_DIR/config.toml"

# 설정 디렉토리 생성
if [[ ! -d "$STREAMLIT_CONFIG_DIR" ]]; then
    mkdir -p "$STREAMLIT_CONFIG_DIR"
    echo "   .streamlit 디렉토리 생성됨"
fi

# OS 감지 및 최적화 설정
OS_TYPE=$(uname -s)
echo "   운영체제: $OS_TYPE"

# 설정 파일 생성/업데이트
if [[ ! -f "$STREAMLIT_CONFIG_FILE" ]]; then
    echo "   Streamlit 설정 파일 생성 중..."

    cat > "$STREAMLIT_CONFIG_FILE" << EOF
[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"

[server]
port = $STREAMLIT_SERVER_PORT
address = "$STREAMLIT_SERVER_ADDRESS"
enableCORS = false
enableXsrfProtection = false
maxUploadSize = 50
enableWebsocketCompression = true
fileWatcherType = "auto"

[browser]
gatherUsageStats = false
serverAddress = "$STREAMLIT_SERVER_ADDRESS"

[runner]
magicEnabled = true
installTracer = false
fixMatplotlib = true

[logger]
level = "info"

[global]
developmentMode = false
maxCachedMessageAge = 2
minCachedMessageSize = 1

[client]
caching = true
displayEnabled = true
EOF

    echo -e "   ${GREEN}✅ Streamlit 설정 파일 생성됨${NC}"
else
    echo "   기존 Streamlit 설정 파일 사용"
fi

# 7. 기존 프로세스 정리
echo -e "\n${BLUE}🧹 기존 프로세스 정리...${NC}"

# PID 파일 확인
if [[ -f ".streamlit.pid" ]]; then
    PID=$(cat ".streamlit.pid")
    if kill -0 "$PID" 2>/dev/null; then
        echo "   기존 Streamlit 프로세스 종료: PID $PID"
        kill "$PID" 2>/dev/null
        sleep 2
    fi
    rm ".streamlit.pid"
fi

# 포트 충돌 확인
echo -n "   포트 $STREAMLIT_SERVER_PORT 확인... "
if lsof -i:$STREAMLIT_SERVER_PORT > /dev/null 2>&1; then
    echo -e "${YELLOW}사용 중${NC}"
    echo "   기존 프로세스를 종료하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        lsof -ti:$STREAMLIT_SERVER_PORT | xargs kill -9 2>/dev/null
        sleep 2
    else
        echo -e "${RED}❌ 포트 충돌로 인해 시작할 수 없습니다.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}사용 가능${NC}"
fi

# 8. 로그 디렉토리 생성
mkdir -p logs

# 9. Streamlit 애플리케이션 시작
echo -e "\n${BLUE}🚀 Streamlit 애플리케이션 시작...${NC}"

# 메인 애플리케이션 파일 설정
STREAMLIT_APP="ui/Home.py"
echo "   메인 앱 파일: $STREAMLIT_APP"

# Streamlit 실행 명령어 구성
STREAMLIT_CMD="streamlit run $STREAMLIT_APP"
STREAMLIT_ARGS=""

# 기본 서버 설정
STREAMLIT_ARGS="$STREAMLIT_ARGS --server.address $STREAMLIT_SERVER_ADDRESS"
STREAMLIT_ARGS="$STREAMLIT_ARGS --server.port $STREAMLIT_SERVER_PORT"
STREAMLIT_ARGS="$STREAMLIT_ARGS --server.enableCORS false"
STREAMLIT_ARGS="$STREAMLIT_ARGS --server.enableXsrfProtection false"
STREAMLIT_ARGS="$STREAMLIT_ARGS --browser.gatherUsageStats false"

# OS별 최적화 설정
if [[ "$OS_TYPE" == "Darwin" ]]; then
    echo "   macOS 최적화 설정 적용"
    STREAMLIT_ARGS="$STREAMLIT_ARGS --server.fileWatcherType auto"
    STREAMLIT_ARGS="$STREAMLIT_ARGS --server.enableStaticServing true"
elif [[ "$OS_TYPE" == "Linux" ]]; then
    echo "   Linux 최적화 설정 적용"
    STREAMLIT_ARGS="$STREAMLIT_ARGS --server.fileWatcherType polling"
else
    echo "   기본 설정 적용"
    STREAMLIT_ARGS="$STREAMLIT_ARGS --server.fileWatcherType auto"
fi

# 전체 명령어 구성
FULL_STREAMLIT_CMD="$STREAMLIT_CMD $STREAMLIT_ARGS"
echo "   실행 명령어: $FULL_STREAMLIT_CMD"

# Streamlit 실행 (백그라운드)
echo "   Streamlit 시작 중..."
echo "" | nohup $FULL_STREAMLIT_CMD > logs/streamlit.log 2>&1 &
STREAMLIT_PID=$!
echo "   PID: $STREAMLIT_PID"
echo $STREAMLIT_PID > .streamlit.pid

# 10. 서비스 준비 대기
echo -e "\n${BLUE}⏳ Streamlit 서비스 준비 대기...${NC}"
echo -n "대기 중"

max_attempts=24  # 2분 대기
attempt=0
streamlit_ready=false

while [[ $attempt -lt $max_attempts ]] && [[ $streamlit_ready == false ]]; do
    sleep 5
    echo -n "."
    attempt=$((attempt + 1))

    # Streamlit 서버 상태 확인
    if curl -s http://localhost:$STREAMLIT_SERVER_PORT > /dev/null 2>&1; then
        streamlit_ready=true
        echo -e "\n${GREEN}✅ Streamlit 서비스 준비 완료!${NC}"
        break
    fi

    # 주기적 상태 출력
    if [[ $((attempt % 6)) -eq 0 ]]; then
        echo -e "\n   진행 중... ($((attempt * 5))초 경과)"

        # 프로세스 상태 확인
        if kill -0 "$STREAMLIT_PID" 2>/dev/null; then
            echo "   프로세스 상태: ✅ 실행 중"
        else
            echo "   프로세스 상태: ❌ 종료됨"
            echo "   로그 확인: tail -f logs/streamlit.log"
            break
        fi
        echo -n "   계속 대기 중"
    fi
done

if [[ $streamlit_ready == false ]]; then
    echo -e "\n${YELLOW}⚠️  Streamlit 서비스 시작이 지연되고 있습니다.${NC}"
    echo "로그를 확인해보세요: tail -f logs/streamlit.log"

    # 프로세스 상태 재확인
    if kill -0 "$STREAMLIT_PID" 2>/dev/null; then
        echo -e "${BLUE}프로세스는 실행 중입니다. 조금 더 기다려보세요.${NC}"
    else
        echo -e "${RED}프로세스가 종료되었습니다. 로그를 확인하세요.${NC}"
    fi
fi

# 11. 최종 상태 확인
echo -e "\n${BLUE}📊 프론트엔드 서비스 상태 확인...${NC}"

# 프로세스 상태
echo "   프로세스 상태:"
if [[ -f ".streamlit.pid" ]]; then
    PID=$(cat ".streamlit.pid")
    if kill -0 "$PID" 2>/dev/null; then
        echo -e "   - Streamlit: ${GREEN}실행 중${NC} (PID: $PID)"
    else
        echo -e "   - Streamlit: ${RED}실행 실패${NC}"
    fi
fi

# 서비스 엔드포인트 테스트
echo "   서비스 엔드포인트 테스트:"
urls=(
    "http://localhost:$STREAMLIT_SERVER_PORT:웹 UI"
)

for url_info in "${urls[@]}"; do
    IFS=':' read -r url desc <<< "$url_info"
    echo -n "   - $desc: "
    if curl -s "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 정상${NC}"
    else
        echo -e "${RED}❌ 실패${NC}"
    fi
done

# 브라우저 자동 열기 (선택적)
if [[ $streamlit_ready == true ]]; then
    echo -e "\n${YELLOW}🌐 브라우저에서 앱을 여시겠습니까? (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        if [[ "$OS_TYPE" == "Darwin" ]]; then
            open "http://localhost:$STREAMLIT_SERVER_PORT"
        elif [[ "$OS_TYPE" == "Linux" ]]; then
            xdg-open "http://localhost:$STREAMLIT_SERVER_PORT" 2>/dev/null
        fi
        echo "   브라우저에서 앱을 열었습니다."
    fi
fi

# 12. 완료 메시지
echo -e "\n${GREEN}🎉 프론트엔드 서비스 시작 완료!${NC}"
echo -e "\n${YELLOW}📌 서비스 정보:${NC}"
echo -e "   🌐 웹 UI: http://localhost:$STREAMLIT_SERVER_PORT"
echo -e "   📊 백엔드 API: $API_BASE_URL"
echo -e "   📁 로그 파일: $(pwd)/logs/streamlit.log"

echo -e "\n${YELLOW}📋 유용한 명령어:${NC}"
echo -e "   📊 로그 확인: tail -f logs/streamlit.log"
echo -e "   🛑 서비스 종료: ./scripts/stop_frontend.sh"
echo -e "   🔄 서비스 재시작: ./scripts/stop_frontend.sh && ./scripts/start_frontend.sh"

echo -e "\n${YELLOW}💡 사용 방법:${NC}"
echo -e "   1. 웹 브라우저에서 http://localhost:$STREAMLIT_SERVER_PORT 접속"
echo -e "   2. 사이드바에서 문서 업로드"
echo -e "   3. 채팅으로 AI와 대화"
echo -e "   4. 검색 페이지에서 문서 검색"

echo -e "\n${GREEN}✨ 프론트엔드 서비스 실행 중! ✨${NC}"

# 서비스 정보 저장
cat > .frontend_info << EOF
# GTOne RAG Frontend Service Info
# Generated: $(date)
STREAMLIT_PID=$STREAMLIT_PID
STREAMLIT_URL=http://localhost:$STREAMLIT_SERVER_PORT
API_BASE_URL=$API_BASE_URL
VIRTUAL_ENV=$VIRTUAL_ENV
STREAMLIT_VERSION=$STREAMLIT_VERSION
EOF