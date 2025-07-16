#!/bin/bash

echo "🎨 GTOne RAG - 프론트엔드 UI 시작"
echo "====================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 로그 함수
log_info() { echo -e "${BLUE}ℹ️ $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# 시작 시간 기록
START_TIME=$(date '+%Y-%m-%d %H:%M:%S')
log_info "시작 시간: $START_TIME"

# ---------- 프로젝트 루트 찾기 (개선된 로직) ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log_info "스크립트 위치: $SCRIPT_DIR"

# 프로젝트 루트 찾기 함수
find_project_root() {
    local current_dir="$1"
    local max_depth=5
    local depth=0

    while [[ $depth -lt $max_depth ]]; do
        # 프로젝트 루트 판별 조건들
        if [[ -d "$current_dir/frontend" && -d "$current_dir/backend" ]] || \
           [[ -f "$current_dir/backend/api/main.py" ]] || \
           [[ -f "$current_dir/frontend/requirements-frontend.txt" ]] || \
           [[ -f "$current_dir/frontend/requirements.txt" ]]; then
            echo "$current_dir"
            return 0
        fi

        # 한 단계 위로 이동
        current_dir="$(dirname "$current_dir")"
        depth=$((depth + 1))

        # 루트 디렉토리에 도달한 경우 중단
        if [[ "$current_dir" == "/" ]]; then
            break
        fi
    done

    return 1
}

# 프로젝트 루트 찾기 시도
if PROJECT_ROOT=$(find_project_root "$SCRIPT_DIR"); then
    log_success "프로젝트 루트 발견: $PROJECT_ROOT"
elif PROJECT_ROOT=$(find_project_root "$(pwd)"); then
    log_success "프로젝트 루트 발견: $PROJECT_ROOT"
else
    log_warning "자동 감지 실패. 수동 지정을 시도합니다."
    echo "다음 중 하나가 포함된 디렉토리에서 실행하세요:"
    echo "  - frontend/ 및 backend/ 디렉토리"
    echo "  - frontend/requirements-frontend.txt"
    echo ""
    echo "현재 디렉토리에서 강제로 실행하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        PROJECT_ROOT="$(pwd)"
        log_warning "현재 디렉토리를 프로젝트 루트로 설정: $PROJECT_ROOT"
    else
        exit 1
    fi
fi

# frontend 디렉토리 찾기
if [[ -d "$PROJECT_ROOT/frontend" ]]; then
    FRONTEND_DIR="$PROJECT_ROOT/frontend"
elif [[ -f "$PROJECT_ROOT/requirements-frontend.txt" ]] || [[ -d "$PROJECT_ROOT/ui" ]]; then
    # 현재 디렉토리가 frontend 디렉토리인 경우
    FRONTEND_DIR="$PROJECT_ROOT"
    PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
else
    log_error "frontend 디렉토리를 찾을 수 없습니다."
    exit 1
fi

cd "$FRONTEND_DIR" || {
    log_error "프론트엔드 디렉토리로 이동할 수 없습니다: $FRONTEND_DIR"
    exit 1
}

log_info "프로젝트 루트: $PROJECT_ROOT"
log_info "프론트엔드 디렉토리: $FRONTEND_DIR"
log_success "작업 디렉토리: $(pwd)"

# 1. Conda 환경 확인
log_info "Conda 환경 확인..."

if ! command -v conda &> /dev/null; then
    log_error "Conda가 설치되지 않았습니다."
    echo "   Conda 설치 방법:"
    echo "   - Anaconda: https://www.anaconda.com/products/distribution"
    echo "   - Miniconda: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

log_success "Conda 버전: $(conda --version)"

# 2. UI 구조 확인 (유연한 검증)
log_info "UI 구조 확인..."

# 필수 구조 확인 (유연하게)
frontend_structure_found=false

if [[ -f "ui/Home.py" ]] || [[ -f "streamlit_app.py" ]] || [[ -f "app.py" ]]; then
    log_success "메인 애플리케이션 파일 확인됨"
    frontend_structure_found=true
elif [[ -d "ui" ]] || [[ -f "requirements-frontend.txt" ]] || [[ -f "requirements.txt" ]]; then
    log_warning "부분적인 프론트엔드 구조 발견"
    echo "   Streamlit 애플리케이션이 기본 구조와 다를 수 있습니다."
    frontend_structure_found=true
else
    log_warning "표준 프론트엔드 구조를 찾을 수 없습니다"
    echo "   현재 디렉토리 내용:"
    ls -la . | head -10
    echo ""
    echo "   계속하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        frontend_structure_found=true
    else
        exit 1
    fi
fi

# 메인 앱 파일 찾기
STREAMLIT_APP=""
app_candidates=("ui/Home.py" "streamlit_app.py" "app.py" "main.py")

for app_file in "${app_candidates[@]}"; do
    if [[ -f "$app_file" ]]; then
        STREAMLIT_APP="$app_file"
        log_success "메인 앱 파일 발견: $app_file"
        break
    fi
done

if [[ -z "$STREAMLIT_APP" ]]; then
    log_warning "메인 애플리케이션 파일을 찾을 수 없습니다."
    echo "   찾고 있는 파일들: ${app_candidates[*]}"
    echo "   직접 입력하시겠습니까? (파일 경로 입력 또는 Enter로 건너뛰기)"
    read -r custom_app
    if [[ -n "$custom_app" && -f "$custom_app" ]]; then
        STREAMLIT_APP="$custom_app"
        log_success "사용자 지정 앱 파일: $custom_app"
    else
        log_warning "기본 파일로 생성하여 진행합니다."
        STREAMLIT_APP="streamlit_app.py"
    fi
fi

# 3. Conda 환경 설정
CONDA_ENV_NAME="GTRAG"
log_info "Conda 환경 설정..."

if conda env list | grep -q "^$CONDA_ENV_NAME "; then
    log_success "$CONDA_ENV_NAME 환경이 이미 존재합니다."
else
    log_warning "$CONDA_ENV_NAME 환경이 없습니다. 생성 중..."
    conda create -n $CONDA_ENV_NAME python=3.11 -y

    if [[ $? -eq 0 ]]; then
        log_success "$CONDA_ENV_NAME 환경이 성공적으로 생성되었습니다."
    else
        log_error "$CONDA_ENV_NAME 환경 생성에 실패했습니다."
        exit 1
    fi
fi

# 4. Conda 환경 활성화
log_info "$CONDA_ENV_NAME 환경 활성화..."

# Conda 초기화
CONDA_BASE=$(conda info --base)
if [[ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]]; then
    source "$CONDA_BASE/etc/profile.d/conda.sh"
else
    eval "$(conda shell.bash hook)" 2>/dev/null || {
        log_error "Conda 초기화에 실패했습니다."
        echo "다음 명령을 수동으로 실행하세요:"
        echo "conda init bash"
        echo "source ~/.bashrc"
        exit 1
    }
fi

conda activate $CONDA_ENV_NAME

if [[ $? -eq 0 ]]; then
    log_success "$CONDA_ENV_NAME 환경이 활성화되었습니다."
    echo "   현재 Python 경로: $(which python)"
    echo "   현재 Python 버전: $(python --version)"
else
    log_error "$CONDA_ENV_NAME 환경 활성화에 실패했습니다."
    exit 1
fi

# 5. 의존성 설치
log_info "Python 패키지 설치 확인..."

# requirements 파일 찾기
REQ_FILES=(
    "requirements-frontend.txt"
    "requirements.txt"
    "../requirements.txt"
    "$PROJECT_ROOT/requirements.txt"
)

REQ_FILE=""
log_info "Requirements 파일 탐색 중..."
for req_file in "${REQ_FILES[@]}"; do
    if [[ -f "$req_file" ]]; then
        REQ_FILE="$req_file"
        log_success "Requirements 파일 발견: $req_file"
        break
    fi
done

if [[ -z "$REQ_FILE" ]]; then
    log_warning "requirements 파일을 찾을 수 없습니다."
    echo ""
    echo "현재 디렉토리: $(pwd)"
    echo "찾고 있는 파일들:"
    for req_file in "${REQ_FILES[@]}"; do
        echo "  - $req_file"
    done
    echo ""
    echo "기본 패키지만 설치하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "기본 패키지 설치 중..."
        pip install streamlit requests pandas numpy plotly Pillow
    else
        exit 1
    fi
else
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
        log_warning "누락된 패키지: ${missing_packages[*]}"
        echo "패키지를 설치합니다..."

        pip install -r "$REQ_FILE"

        if [[ $? -eq 0 ]]; then
            log_success "패키지 설치 완료"
        else
            log_error "패키지 설치 실패"
            echo "수동 설치를 시도하세요:"
            echo "pip install streamlit requests pandas numpy plotly Pillow"
            exit 1
        fi
    else
        log_success "모든 필수 패키지가 설치되어 있습니다"
    fi
fi

# Streamlit 버전 확인
STREAMLIT_VERSION=$(python -c "import streamlit; print(streamlit.__version__)" 2>/dev/null || echo "unknown")
echo "   Streamlit 버전: $STREAMLIT_VERSION"

# 6. 환경변수 설정
log_info "환경변수 설정..."

# .env 파일 로드 (프로젝트 루트 우선, 그 다음 frontend)
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    echo "   프로젝트 루트 .env 파일에서 설정 로드"
    set -a
    source "$PROJECT_ROOT/.env"
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

# 7. 백엔드 연결 확인
log_info "백엔드 서비스 연결 확인..."

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
    log_warning "백엔드 서버가 실행 중인지 확인하세요."
    echo "   백엔드 시작 방법:"
    echo "     1. 스크립트: ./backend/scripts/start_backend.sh"
    echo "     2. Docker: cd backend && docker-compose up -d"
    echo ""
    echo -e "${YELLOW}   백엔드 없이 프론트엔드만 시작하시겠습니까? (y/n)${NC}"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 8. Streamlit 설정 파일 처리
log_info "Streamlit 설정..."

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
    log_success "Streamlit 설정 파일 준비됨"
else
    echo "   기존 Streamlit 설정 파일 사용"
fi

# 9. 기존 프로세스 정리
log_info "기존 프로세스 정리..."

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
if command -v lsof &> /dev/null && lsof -i:$STREAMLIT_SERVER_PORT > /dev/null 2>&1; then
    echo -e "${YELLOW}사용 중${NC}"
    echo "   기존 프로세스를 종료하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        lsof -ti:$STREAMLIT_SERVER_PORT | xargs kill -9 2>/dev/null || true
        sleep 2
    else
        log_error "포트 충돌로 인해 시작할 수 없습니다."
        exit 1
    fi
else
    echo -e "${GREEN}사용 가능${NC}"
fi

# 10. 로그 디렉토리 생성
mkdir -p logs

# 11. 기본 앱 파일 생성 (필요한 경우)
if [[ ! -f "$STREAMLIT_APP" ]]; then
    log_warning "메인 앱 파일이 없습니다. 기본 파일을 생성합니다."

    # 디렉토리 생성
    mkdir -p "$(dirname "$STREAMLIT_APP")"

    # 기본 Streamlit 앱 생성
    cat > "$STREAMLIT_APP" << 'EOF'
import streamlit as st
import requests
import os

st.set_page_config(
    page_title="GTOne RAG",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 GTOne RAG - AI Document Assistant")

# API URL 설정
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:18000")

# 사이드바
with st.sidebar:
    st.header("🔧 System Status")

    # 백엔드 연결 상태 확인
    try:
        response = requests.get(f"{API_BASE_URL}/v1/health", timeout=5)
        if response.status_code == 200:
            st.success("✅ Backend Connected")
        else:
            st.error("❌ Backend Error")
    except:
        st.error("❌ Backend Disconnected")
        st.warning("Please start the backend service first")

# 메인 컨텐츠
st.write("## Welcome to GTOne RAG!")
st.write("This is a basic Streamlit application for GTOne RAG system.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📄 Document Upload")
    uploaded_file = st.file_uploader("Choose a file", type=['pdf', 'txt', 'docx'])
    if uploaded_file:
        st.success(f"File uploaded: {uploaded_file.name}")

with col2:
    st.subheader("💬 AI Chat")
    user_input = st.text_input("Ask a question:")
    if user_input:
        st.write(f"You asked: {user_input}")
        st.info("This is a demo response. Connect to the backend for real AI responses.")

# 정보
st.write("---")
st.write("**Instructions:**")
st.write("1. Start the backend service: `./backend/scripts/start_backend.sh`")
st.write("2. Upload documents using the sidebar")
st.write("3. Ask questions about your documents")
EOF

    log_success "기본 앱 파일이 생성되었습니다: $STREAMLIT_APP"
fi

# 12. Python path 설정
export PYTHONPATH="$FRONTEND_DIR:$PROJECT_ROOT:${PYTHONPATH:-}"

# 13. Streamlit 애플리케이션 시작
log_info "Streamlit 애플리케이션 시작..."

echo "   메인 앱 파일: $STREAMLIT_APP"
echo "   Conda 환경: $CONDA_ENV_NAME"

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

# 14. 서비스 준비 대기
log_info "Streamlit 서비스 준비 대기..."
echo -n "대기 중"

max_attempts=30
attempt=0
streamlit_ready=false

while [[ $attempt -lt $max_attempts ]] && [[ $streamlit_ready == false ]]; do
    sleep 2
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
    if [[ $((attempt % 10)) -eq 0 ]]; then
        echo -e "\n   진행 중... ($((attempt * 2))초 경과)"

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
    log_warning "Streamlit 서비스 시작이 지연되고 있습니다."
    echo "로그를 확인해보세요: tail -f $FRONTEND_DIR/logs/streamlit.log"

    if kill -0 "$STREAMLIT_PID" 2>/dev/null; then
        log_info "프로세스는 실행 중입니다. 브라우저에서 직접 접속해보세요."
        echo "URL: http://localhost:$STREAMLIT_SERVER_PORT"
    else
        log_error "프로세스가 종료되었습니다."
        echo "문제 해결 방법:"
        echo "  1. 로그 확인: tail -20 $FRONTEND_DIR/logs/streamlit.log"
        echo "  2. 수동 실행: cd $FRONTEND_DIR && $FULL_STREAMLIT_CMD"
        echo "  3. 패키지 재설치: pip install streamlit --upgrade"
    fi
fi

# 15. 최종 상태 확인 및 완료 메시지
log_info "프론트엔드 서비스 상태 확인..."

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
        OS_TYPE=$(uname -s)
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
END_TIME=$(date '+%Y-%m-%d %H:%M:%S')
log_success "GTOne RAG 프론트엔드 서비스 시작 완료!"

echo -e "\n${YELLOW}📌 서비스 정보:${NC}"
echo -e "   🐍 Conda 환경: $CONDA_ENV_NAME"
echo -e "   🌐 웹 UI: http://localhost:$STREAMLIT_SERVER_PORT"
echo -e "   📊 백엔드 API: $API_BASE_URL"
echo -e "   📁 로그 파일: $FRONTEND_DIR/logs/streamlit.log"
echo -e "   🔧 설정 파일: $FRONTEND_DIR/$STREAMLIT_CONFIG_FILE"

echo -e "\n${YELLOW}📋 유용한 명령어:${NC}"
echo -e "   📊 로그 확인: tail -f $FRONTEND_DIR/logs/streamlit.log"
echo -e "   🛑 서비스 종료: ./frontend/scripts/stop_frontend.sh"
echo -e "   🔄 환경 재활성화: conda activate $CONDA_ENV_NAME"
echo -e "   🔧 설정 확인: cat $FRONTEND_DIR/$STREAMLIT_CONFIG_FILE"

echo -e "\n${YELLOW}💡 사용 방법:${NC}"
echo -e "   1. 웹 브라우저에서 http://localhost:$STREAMLIT_SERVER_PORT 접속"
echo -e "   2. 시스템 상태 확인 (사이드바)"
echo -e "   3. 문서 업로드"
echo -e "   4. AI와 채팅 또는 문서 검색"

if [[ "$BACKEND_READY" == false ]]; then
    echo -e "\n${YELLOW}⚠️  참고: 백엔드 서버가 연결되지 않았습니다.${NC}"
    echo -e "   모든 기능을 사용하려면 백엔드를 먼저 시작하세요:"
    echo -e "   ./backend/scripts/start_backend.sh"
fi

echo -e "\n${BLUE}📊 시작 요약:${NC}"
echo "   시작 시간: $START_TIME"
echo "   완료 시간: $END_TIME"
echo "   프로젝트 루트: $PROJECT_ROOT"
echo "   프론트엔드 디렉토리: $FRONTEND_DIR"

echo -e "\n${GREEN}✨ 프론트엔드 서비스 실행 중! ✨${NC}"

# 서비스 정보 저장
cat > .frontend_info << EOF
# GTOne RAG Frontend Service Info
# Generated: $(date '+%Y-%m-%d %H:%M:%S')
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
START_TIME=$START_TIME
END_TIME=$END_TIME
EOF

log_info "서비스 정보가 .frontend_info에 저장되었습니다."