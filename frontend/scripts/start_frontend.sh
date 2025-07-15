#!/bin/bash

echo "🎨 GTOne RAG - 프론트엔드 UI 시작"
echo "====================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 시작 시간 기록
START_TIME=$(date)
echo "시작 시간: $START_TIME"

# 경로 설정 (GTRAG 루트에서 실행되는 것을 가정)
SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$FRONTEND_DIR")"

echo -e "\n${BLUE}📁 경로 확인...${NC}"
echo "   프로젝트 루트: $PROJECT_ROOT"
echo "   프론트엔드 디렉토리: $FRONTEND_DIR"
echo "   스크립트 디렉토리: $SCRIPT_DIR"

# 현재 디렉토리 확인
CURRENT_DIR="$(pwd)"
echo "   현재 실행 디렉토리: $CURRENT_DIR"

# GTRAG 루트에서 실행되었는지 확인
if [[ ! -d "frontend" ]] || [[ ! -d "backend" ]]; then
    echo -e "${RED}❌ GTRAG 프로젝트 루트에서 실행해주세요.${NC}"
    echo "현재 위치: $CURRENT_DIR"
    echo "올바른 실행: cd /path/to/GTRAG && frontend/scripts/start_frontend.sh"
    exit 1
fi

# frontend 디렉토리로 이동
cd "$FRONTEND_DIR" || {
    echo -e "${RED}❌ 프론트엔드 디렉토리로 이동할 수 없습니다: $FRONTEND_DIR${NC}"
    exit 1
}

echo -e "${GREEN}✅ 프론트엔드 디렉토리로 이동: $(pwd)${NC}"

# 1. Conda 환경 확인
echo -e "\n${BLUE}🐍 Conda 환경 확인...${NC}"

if ! command -v conda &> /dev/null; then
    echo -e "${RED}❌ Conda가 설치되지 않았습니다.${NC}"
    echo "   Conda 설치 방법:"
    echo "   - Anaconda: https://www.anaconda.com/products/distribution"
    echo "   - Miniconda: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo -e "${GREEN}✅ Conda 버전: $(conda --version)${NC}"

# UI 구조 확인
echo -e "\n${BLUE}📂 UI 구조 확인...${NC}"

# 필수 파일들 검사
REQUIRED_FILES=(
    "ui/Home.py"
    "ui/Loading.py"
    "ui/__init__.py"
    "ui/utils/__init__.py"
    "ui/utils/api_client.py"
    "ui/utils/session.py"
    "ui/utils/helpers.py"
    "ui/utils/streamlit_helpers.py"
    "ui/components/__init__.py"
    "ui/components/sidebar.py"
    "ui/components/uploader.py"
    "ui/components/chatting.py"
    "ui/components/searching.py"
    "ui/pages/__init__.py"
    "ui/pages/documents.py"
    "ui/pages/search.py"
    "ui/pages/settings.py"
)

missing_files=()
for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        missing_files+=("$file")
    fi
done

if [[ ${#missing_files[@]} -ne 0 ]]; then
    echo -e "${RED}❌ 누락된 파일들:${NC}"
    for file in "${missing_files[@]}"; do
        echo "     - $file"
    done
    echo -e "${YELLOW}⚠️  일부 기능이 제대로 작동하지 않을 수 있습니다.${NC}"
    echo "   누락된 파일들을 생성해주세요."
    exit 1
else
    echo -e "${GREEN}✅ 모든 필수 파일이 존재합니다.${NC}"
fi

# 페이지 및 컴포넌트 수 확인
if [[ -d "ui/pages" ]]; then
    page_count=$(find ui/pages -name "*.py" -not -name "__init__.py" 2>/dev/null | wc -l)
    echo "   페이지 수: $page_count개"
fi

if [[ -d "ui/components" ]]; then
    component_count=$(find ui/components -name "*.py" -not -name "__init__.py" 2>/dev/null | wc -l)
    echo "   컴포넌트 수: $component_count개"
fi

# 2. Conda 환경 설정
echo -e "\n${BLUE}📦 GTRAG Conda 환경 설정...${NC}"

CONDA_ENV_NAME="GTRAG"

if conda env list | grep -q "^$CONDA_ENV_NAME "; then
    echo -e "${GREEN}✅ $CONDA_ENV_NAME 환경이 이미 존재합니다.${NC}"
else
    echo -e "${YELLOW}⚠️  $CONDA_ENV_NAME 환경이 없습니다. 생성 중...${NC}"
    conda create -n $CONDA_ENV_NAME python=3.11 -y

    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✅ $CONDA_ENV_NAME 환경이 성공적으로 생성되었습니다.${NC}"
    else
        echo -e "${RED}❌ $CONDA_ENV_NAME 환경 생성에 실패했습니다.${NC}"
        exit 1
    fi
fi

# 3. Conda 환경 활성화
echo -e "\n${BLUE}🔧 $CONDA_ENV_NAME 환경 활성화...${NC}"

# Conda 초기화 경로들
CONDA_INIT_PATHS=(
    "$HOME/anaconda3/etc/profile.d/conda.sh"
    "$HOME/miniconda3/etc/profile.d/conda.sh"
    "/opt/anaconda3/etc/profile.d/conda.sh"
    "/opt/miniconda3/etc/profile.d/conda.sh"
    "/usr/local/anaconda3/etc/profile.d/conda.sh"
    "/usr/local/miniconda3/etc/profile.d/conda.sh"
)

CONDA_SOURCED=false
for conda_path in "${CONDA_INIT_PATHS[@]}"; do
    if [[ -f "$conda_path" ]]; then
        source "$conda_path"
        CONDA_SOURCED=true
        echo "   Conda 초기화: $conda_path"
        break
    fi
done

if [[ "$CONDA_SOURCED" == false ]]; then
    eval "$(conda shell.bash hook)" 2>/dev/null || {
        echo -e "${RED}❌ Conda 초기화에 실패했습니다.${NC}"
        echo "다음 명령을 수동으로 실행하세요:"
        echo "conda init bash"
        echo "source ~/.bashrc"
        exit 1
    }
fi

# 환경 활성화
conda activate $CONDA_ENV_NAME

if [[ $? -eq 0 ]]; then
    echo -e "${GREEN}✅ $CONDA_ENV_NAME 환경이 활성화되었습니다.${NC}"
    echo "   현재 Python 경로: $(which python)"
    echo "   현재 Python 버전: $(python --version)"
else
    echo -e "${RED}❌ $CONDA_ENV_NAME 환경 활성화에 실패했습니다.${NC}"
    exit 1
fi

# 4. 의존성 설치
echo -e "\n${BLUE}📚 Python 패키지 설치 확인...${NC}"

# requirements 파일 찾기 (frontend 디렉토리 기준)
if [[ -f "requirements-frontend.txt" ]]; then
    REQ_FILE="requirements-frontend.txt"
    echo "프론트엔드 전용 requirements 파일 사용: $REQ_FILE"
elif [[ -f "requirements.txt" ]]; then
    REQ_FILE="requirements.txt"
    echo "공통 requirements 파일 사용: $REQ_FILE"
elif [[ -f "../requirements.txt" ]]; then
    REQ_FILE="../requirements.txt"
    echo "프로젝트 루트 requirements 파일 사용: $REQ_FILE"
else
    echo -e "${RED}❌ requirements 파일을 찾을 수 없습니다.${NC}"
    echo "다음 중 하나의 파일이 필요합니다:"
    echo "  - frontend/requirements-frontend.txt (프론트엔드 전용)"
    echo "  - frontend/requirements.txt"
    echo "  - requirements.txt (프로젝트 루트)"
    exit 1
fi

# 핵심 패키지 확인
echo "핵심 패키지 설치 상태 확인..."
missing_packages=()

required_packages=(
    "streamlit"
    "requests"
    "pandas"
    "numpy"
    "plotly"
    "Pillow"
)

for package in "${required_packages[@]}"; do
    if ! python -c "import $package" &> /dev/null; then
        missing_packages+=("$package")
    fi
done

# 패키지 설치
if [[ ${#missing_packages[@]} -ne 0 ]]; then
    echo -e "${YELLOW}⚠️  누락된 패키지: ${missing_packages[*]}${NC}"
    echo "패키지를 설치합니다..."

    pip install -r "$REQ_FILE"

    if [[ $? -eq 0 ]]; then
        echo -e "${GREEN}✅ 패키지 설치 완료${NC}"
    else
        echo -e "${RED}❌ 패키지 설치 실패${NC}"
        echo "수동 설치를 시도하세요:"
        echo "pip install streamlit requests pandas numpy plotly Pillow"
        exit 1
    fi
else
    echo -e "${GREEN}✅ 모든 필수 패키지가 설치되어 있습니다${NC}"
fi

# Streamlit 버전 확인
STREAMLIT_VERSION=$(python -c "import streamlit; print(streamlit.__version__)" 2>/dev/null || echo "unknown")
echo "   Streamlit 버전: $STREAMLIT_VERSION"

# 5. 환경변수 설정
echo -e "\n${BLUE}🔧 환경변수 설정...${NC}"

# .env 파일 로드 (프로젝트 루트 우선, 그 다음 frontend)
if [[ -f "../.env" ]]; then
    echo "   프로젝트 루트 .env 파일에서 설정 로드"
    set -a
    source "../.env"
    set +a
elif [[ -f ".env" ]]; then
    echo "   frontend .env 파일에서 설정 로드"
    set -a
    source ".env"
    set +a
fi

# 기본값 설정
export API_BASE_URL=${API_BASE_URL:-"http://localhost:18000"}
export STREAMLIT_SERVER_PORT=${STREAMLIT_SERVER_PORT:-"8501"}
export STREAMLIT_SERVER_ADDRESS=${STREAMLIT_SERVER_ADDRESS:-"0.0.0.0"}
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=${STREAMLIT_BROWSER_GATHER_USAGE_STATS:-"false"}
export STREAMLIT_GLOBAL_DEVELOPMENT_MODE=${STREAMLIT_GLOBAL_DEVELOPMENT_MODE:-"false"}

echo "   Conda 환경: $CONDA_ENV_NAME"
echo "   API_BASE_URL: $API_BASE_URL"
echo "   STREAMLIT_PORT: $STREAMLIT_SERVER_PORT"
echo "   STREAMLIT_ADDRESS: $STREAMLIT_SERVER_ADDRESS"

# 6. 백엔드 연결 확인
echo -e "\n${BLUE}🔗 백엔드 서비스 연결 확인...${NC}"

echo -n "   백엔드 API 서버 연결... "
if curl -s --connect-timeout 5 "$API_BASE_URL/docs" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 연결됨${NC}"

    echo -n "   백엔드 헬스체크... "
    if curl -s --connect-timeout 5 "$API_BASE_URL/v1/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 정상${NC}"
        BACKEND_READY=true
    else
        echo -e "${YELLOW}⚠️  헬스체크 실패${NC}"
        BACKEND_READY=false
    fi
else
    echo -e "${RED}❌ 연결 실패${NC}"
    BACKEND_READY=false
fi

if [[ "$BACKEND_READY" == false ]]; then
    echo -e "${YELLOW}   백엔드 서버가 실행 중인지 확인하세요.${NC}"
    echo "   백엔드 시작 방법:"
    echo "     1. Docker: cd backend && docker-compose up -d"
    echo "     2. 스크립트: cd backend && ./scripts/start_backend.sh"
    echo ""
    echo -e "${YELLOW}   백엔드 없이 프론트엔드만 시작하시겠습니까? (y/n)${NC}"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 7. Streamlit 설정 파일 처리
echo -e "\n${BLUE}⚙️ Streamlit 설정...${NC}"

STREAMLIT_CONFIG_DIR=".streamlit"
STREAMLIT_CONFIG_FILE="$STREAMLIT_CONFIG_DIR/config.toml"

# 설정 디렉토리 생성
if [[ ! -d "$STREAMLIT_CONFIG_DIR" ]]; then
    mkdir -p "$STREAMLIT_CONFIG_DIR"
    echo "   .streamlit 디렉토리 생성됨"
fi

# OS 감지
OS_TYPE=$(uname -s)
echo "   운영체제: $OS_TYPE"

# 설정 파일 생성/업데이트
if [[ ! -f "$STREAMLIT_CONFIG_FILE" ]]; then
    if [[ -f "config.toml" ]]; then
        echo "   기존 config.toml을 복사"
        cp config.toml "$STREAMLIT_CONFIG_FILE"
    else
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
    fi
    echo -e "   ${GREEN}✅ Streamlit 설정 파일 준비됨${NC}"
else
    echo "   기존 Streamlit 설정 파일 사용"
fi

# 8. 기존 프로세스 정리
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

# 9. 로그 디렉토리 생성
mkdir -p logs

# 10. Streamlit 애플리케이션 시작
echo -e "\n${BLUE}🚀 Streamlit 애플리케이션 시작...${NC}"

# 메인 애플리케이션 파일 결정
if [[ -f "ui/Home.py" ]]; then
    STREAMLIT_APP="ui/Home.py"
elif [[ -f "streamlit_app.py" ]]; then
    STREAMLIT_APP="streamlit_app.py"
else
    echo -e "${RED}❌ 메인 애플리케이션 파일을 찾을 수 없습니다.${NC}"
    echo "다음 중 하나가 필요합니다:"
    echo "  - ui/Home.py (권장)"
    echo "  - streamlit_app.py"
    exit 1
fi

echo "   메인 앱 파일: $STREAMLIT_APP"
echo "   Conda 환경: $CONDA_ENV_NAME"

# Python path 설정 (ui 모듈 import를 위해)
export PYTHONPATH="$FRONTEND_DIR:$PROJECT_ROOT:$PYTHONPATH"

# Streamlit 실행 명령어 구성
STREAMLIT_CMD="streamlit run $STREAMLIT_APP"
STREAMLIT_ARGS=""

# 기본 서버 설정
STREAMLIT_ARGS="$STREAMLIT_ARGS --server.address $STREAMLIT_SERVER_ADDRESS"
STREAMLIT_ARGS="$STREAMLIT_ARGS --server.port $STREAMLIT_SERVER_PORT"

# OS별 최적화 설정
if [[ "$OS_TYPE" == "Darwin" ]]; then
    echo "   macOS 최적화 설정 적용"
    STREAMLIT_ARGS="$STREAMLIT_ARGS --server.fileWatcherType auto"
elif [[ "$OS_TYPE" == "Linux" ]]; then
    echo "   Linux 최적화 설정 적용"
    STREAMLIT_ARGS="$STREAMLIT_ARGS --server.fileWatcherType polling"
fi

# 전체 명령어
FULL_STREAMLIT_CMD="$STREAMLIT_CMD $STREAMLIT_ARGS"
echo "   실행 명령어: $FULL_STREAMLIT_CMD"

# Streamlit 실행 (백그라운드)
echo "   Streamlit 시작 중..."
nohup $FULL_STREAMLIT_CMD > logs/streamlit.log 2>&1 &
STREAMLIT_PID=$!
echo "   PID: $STREAMLIT_PID"
echo $STREAMLIT_PID > .streamlit.pid

# 11. 서비스 준비 대기
echo -e "\n${BLUE}⏳ Streamlit 서비스 준비 대기...${NC}"
echo -n "대기 중"

max_attempts=30
attempt=0
streamlit_ready=false

while [[ $attempt -lt $max_attempts ]] && [[ $streamlit_ready == false ]]; do
    sleep 5
    echo -n "."
    attempt=$((attempt + 1))

    # Streamlit 서버 상태 확인
    if curl -s http://localhost:$STREAMLIT_SERVER_PORT/_stcore/health > /dev/null 2>&1; then
        streamlit_ready=true
        echo -e "\n${GREEN}✅ Streamlit 서비스 준비 완료!${NC}"
        break
    elif curl -s http://localhost:$STREAMLIT_SERVER_PORT > /dev/null 2>&1; then
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
    echo "로그를 확인해보세요: tail -f $FRONTEND_DIR/logs/streamlit.log"

    if kill -0 "$STREAMLIT_PID" 2>/dev/null; then
        echo -e "${BLUE}프로세스는 실행 중입니다. 브라우저에서 직접 접속해보세요.${NC}"
        echo "URL: http://localhost:$STREAMLIT_SERVER_PORT"
    else
        echo -e "${RED}프로세스가 종료되었습니다.${NC}"
        echo "문제 해결 방법:"
        echo "  1. 로그 확인: tail -20 $FRONTEND_DIR/logs/streamlit.log"
        echo "  2. 수동 실행: cd $FRONTEND_DIR && $FULL_STREAMLIT_CMD"
        echo "  3. 패키지 재설치: pip install -r $REQ_FILE --upgrade"
    fi
fi

# 12. 최종 상태 확인 및 완료 메시지
echo -e "\n${BLUE}📊 프론트엔드 서비스 상태 확인...${NC}"

# 프로세스 상태
if [[ -f ".streamlit.pid" ]]; then
    PID=$(cat ".streamlit.pid")
    if kill -0 "$PID" 2>/dev/null; then
        echo -e "   - Streamlit: ${GREEN}실행 중${NC} (PID: $PID)"
    else
        echo -e "   - Streamlit: ${RED}실행 실패${NC}"
    fi
fi

# 서비스 테스트
echo "   서비스 엔드포인트 테스트:"
endpoints=(
    "http://localhost:${STREAMLIT_SERVER_PORT}|웹 UI"
    "${API_BASE_URL}/docs|백엔드 API"
)

for endpoint_info in "${endpoints[@]}"; do
    IFS='|' read -r url desc <<< "$endpoint_info"
    echo -n "   - $desc: "
    if curl -s --connect-timeout 3 "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 정상${NC}"
    else
        echo -e "${RED}❌ 실패${NC}"
    fi
done

# 브라우저 자동 열기
if [[ $streamlit_ready == true ]]; then
    echo -e "\n${YELLOW}🌐 브라우저에서 앱을 여시겠습니까? (y/n)${NC}"
    read -r -t 10 response || response="n"
    if [[ "$response" =~ ^[Yy]$ ]]; then
        if [[ "$OS_TYPE" == "Darwin" ]]; then
            open "http://localhost:$STREAMLIT_SERVER_PORT"
        elif [[ "$OS_TYPE" == "Linux" ]]; then
            if command -v xdg-open &> /dev/null; then
                xdg-open "http://localhost:$STREAMLIT_SERVER_PORT" 2>/dev/null
            fi
        fi
        echo "   브라우저에서 앱을 열었습니다."
    fi
fi

# 완료 메시지
echo -e "\n${GREEN}🎉 GTOne RAG 프론트엔드 서비스 시작 완료!${NC}"
echo -e "\n${YELLOW}📌 서비스 정보:${NC}"
echo -e "   🐍 Conda 환경: $CONDA_ENV_NAME"
echo -e "   🌐 웹 UI: http://localhost:$STREAMLIT_SERVER_PORT"
echo -e "   📊 백엔드 API: $API_BASE_URL"
echo -e "   📁 로그 파일: $FRONTEND_DIR/logs/streamlit.log"
echo -e "   🔧 설정 파일: $FRONTEND_DIR/$STREAMLIT_CONFIG_FILE"

echo -e "\n${YELLOW}📋 유용한 명령어:${NC}"
echo -e "   📊 로그 확인: tail -f $FRONTEND_DIR/logs/streamlit.log"
echo -e "   🛑 서비스 종료: frontend/scripts/stop_frontend.sh (또는 kill $STREAMLIT_PID)"
echo -e "   🔄 환경 재활성화: conda activate $CONDA_ENV_NAME"
echo -e "   🔧 설정 확인: cat $FRONTEND_DIR/$STREAMLIT_CONFIG_FILE"

echo -e "\n${YELLOW}💡 사용 방법:${NC}"
echo -e "   1. 웹 브라우저에서 http://localhost:$STREAMLIT_SERVER_PORT 접속"
echo -e "   2. 시스템 상태 확인 (사이드바)"
echo -e "   3. 문서 업로드 (사이드바 또는 문서 관리 페이지)"
echo -e "   4. AI와 채팅 또는 문서 검색"

if [[ "$BACKEND_READY" == false ]]; then
    echo -e "\n${YELLOW}⚠️  참고: 백엔드 서버가 연결되지 않았습니다.${NC}"
    echo -e "   모든 기능을 사용하려면 백엔드를 먼저 시작하세요:"
    echo -e "   cd backend && docker-compose up -d"
fi

echo -e "\n${GREEN}✨ 프론트엔드 서비스 실행 중! (GTRAG 루트에서 시작됨) ✨${NC}"

# 서비스 정보 저장
cat > .frontend_info << EOF
# GTOne RAG Frontend Service Info
# Generated: $(date)
# Started from: $CURRENT_DIR
PROJECT_ROOT=$PROJECT_ROOT
FRONTEND_DIR=$FRONTEND_DIR
CONDA_ENV=$CONDA_ENV_NAME
STREAMLIT_PID=$STREAMLIT_PID
STREAMLIT_URL=http://localhost:$STREAMLIT_SERVER_PORT
API_BASE_URL=$API_BASE_URL
PYTHON_PATH=$(which python)
STREAMLIT_VERSION=$STREAMLIT_VERSION
BACKEND_READY=$BACKEND_READY
OS_TYPE=$OS_TYPE
EOF

echo "서비스 정보가 $FRONTEND_DIR/.frontend_info에 저장되었습니다."