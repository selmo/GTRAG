#!/bin/bash

echo "🚀 GTOne RAG - 전체 시스템 시작"
echo "==============================="

# 공통 함수 로드
if [[ -f "scripts/common.sh" ]]; then
    source "scripts/common.sh"
    init_common
else
    # 공통 함수가 없는 경우 기본 색상만 정의
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    PURPLE='\033[0;35m'
    CYAN='\033[0;36m'
    NC='\033[0m'

    log_info() { echo -e "${BLUE}ℹ️ $1${NC}"; }
    log_success() { echo -e "${GREEN}✅ $1${NC}"; }
    log_warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }
    log_error() { echo -e "${RED}❌ $1${NC}"; }
fi

# 시작 시간 기록
OVERALL_START_TIME=$(date)
echo "전체 시작 시간: $OVERALL_START_TIME"

# 프로젝트 루트 디렉토리 확인
if [[ ! -d "infrastructure" || ! -d "backend" || ! -d "frontend" ]]; then
    log_error "프로젝트 루트 디렉토리에서 실행해주세요."
    echo "현재 위치: $(pwd)"
    echo "필요한 디렉토리: infrastructure/, backend/, frontend/"
    ls -la | grep -E "(infrastructure|backend|frontend)" || echo "관련 디렉토리가 없습니다."
    exit 1
fi

log_success "프로젝트 루트 디렉토리 확인됨"

# 1. 시스템 환경 확인
log_info "시스템 환경 확인..."

# 필수 도구 확인
required_tools=("docker" "python" "curl")
missing_tools=()

for tool in "${required_tools[@]}"; do
    if ! command -v $tool &> /dev/null; then
        missing_tools+=("$tool")
    fi
done

if [[ ${#missing_tools[@]} -gt 0 ]]; then
    log_error "필수 도구가 설치되지 않았습니다: ${missing_tools[*]}"
    exit 1
fi

log_success "필수 도구 확인 완료"

# Docker 데몬 확인
if ! docker info > /dev/null 2>&1; then
    log_error "Docker 데몬이 실행되지 않았습니다."
    exit 1
fi

log_success "Docker 데몬 실행 중"

# 2. 시작 옵션 확인
log_info "시작 옵션..."

# 기본 옵션
SKIP_INFRA=false
SKIP_BACKEND=false
SKIP_FRONTEND=false
PARALLEL_START=false
VERBOSE=false

# 명령행 인자 처리
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-infra)
            SKIP_INFRA=true
            shift
            ;;
        --skip-backend)
            SKIP_BACKEND=true
            shift
            ;;
        --skip-frontend)
            SKIP_FRONTEND=true
            shift
            ;;
        --parallel)
            PARALLEL_START=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            echo "사용법: $0 [옵션]"
            echo "옵션:"
            echo "  --skip-infra      인프라 서비스 건너뛰기"
            echo "  --skip-backend    백엔드 서비스 건너뛰기"
            echo "  --skip-frontend   프론트엔드 서비스 건너뛰기"
            echo "  --parallel        병렬 시작 (실험적)"
            echo "  --verbose         상세 로그 표시"
            echo "  --help            도움말 표시"
            exit 0
            ;;
        *)
            log_warning "알 수 없는 옵션: $1"
            shift
            ;;
    esac
done

# 시작 계획 표시
echo "시작 계획:"
echo "   인프라: $(if $SKIP_INFRA; then echo "건너뛰기"; else echo "시작"; fi)"
echo "   백엔드: $(if $SKIP_BACKEND; then echo "건너뛰기"; else echo "시작"; fi)"
echo "   프론트엔드: $(if $SKIP_FRONTEND; then echo "건너뛰기"; else echo "시작"; fi)"
echo "   병렬 처리: $(if $PARALLEL_START; then echo "활성화"; else echo "순차 처리"; fi)"

# 3. 기존 프로세스 정리 (선택적)
log_info "기존 프로세스 정리..."

cleanup_existing() {
    echo "기존 GTOne RAG 프로세스를 정리하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "전체 시스템 정리 중..."

        # 각 레이어별 정리 스크립트 실행
        if [[ -f "frontend/scripts/stop_frontend.sh" ]]; then
            echo "   프론트엔드 정리 중..."
            cd frontend && ./scripts/stop_frontend.sh > /dev/null 2>&1 && cd ..
        fi

        if [[ -f "backend/scripts/stop_backend.sh" ]]; then
            echo "   백엔드 정리 중..."
            cd backend && ./scripts/stop_backend.sh > /dev/null 2>&1 && cd ..
        fi

        if [[ -f "infrastructure/scripts/stop_infra.sh" ]]; then
            echo "   인프라 정리 중..."
            cd infrastructure && ./scripts/stop_infra.sh > /dev/null 2>&1 && cd ..
        fi

        log_success "기존 프로세스 정리 완료"
        sleep 2
    fi
}

# 실행 중인 서비스 확인
running_services=()
if lsof -i:6333 > /dev/null 2>&1; then running_services+=("Qdrant:6333"); fi
if lsof -i:6379 > /dev/null 2>&1; then running_services+=("Redis:6379"); fi
if lsof -i:18000 > /dev/null 2>&1; then running_services+=("API:18000"); fi
if lsof -i:8501 > /dev/null 2>&1; then running_services+=("UI:8501"); fi

if [[ ${#running_services[@]} -gt 0 ]]; then
    log_warning "실행 중인 서비스 발견: ${running_services[*]}"
    cleanup_existing
fi

# 4. 인프라 서비스 시작
if [[ $SKIP_INFRA == false ]]; then
    echo -e "\n${PURPLE}🏗️ [1/3] 인프라 서비스 시작...${NC}"
    echo "======================================"

    if [[ -f "infrastructure/scripts/start_infra.sh" ]]; then
        cd infrastructure

        if $VERBOSE; then
            ./scripts/start_infra.sh
        else
            ./scripts/start_infra.sh > /tmp/infra_start.log 2>&1
        fi

        infra_exit_code=$?
        cd ..

        if [[ $infra_exit_code -eq 0 ]]; then
            log_success "인프라 서비스 시작 완료"
        else
            log_error "인프라 서비스 시작 실패"
            if [[ ! $VERBOSE ]]; then
                echo "로그 확인: cat /tmp/infra_start.log"
            fi
            exit 1
        fi
    else
        log_error "인프라 시작 스크립트를 찾을 수 없습니다"
        exit 1
    fi

    # 인프라 준비 대기
    echo -n "인프라 서비스 안정화 대기"
    for i in {1..10}; do
        echo -n "."
        sleep 1
    done
    echo -e " ${GREEN}완료${NC}"
else
    echo -e "\n${YELLOW}⏭️ [1/3] 인프라 서비스 건너뛰기${NC}"
fi

# 5. 백엔드 서비스 시작
if [[ $SKIP_BACKEND == false ]]; then
    echo -e "\n${CYAN}🔧 [2/3] 백엔드 서비스 시작...${NC}"
    echo "====================================="

    if [[ -f "backend/scripts/start_backend.sh" ]]; then
        cd backend

        if $VERBOSE; then
            ./scripts/start_backend.sh  # ✅ 수정된 파일명
        else
            ./scripts/start_backend.sh > /tmp/backend_start.log 2>&1  # ✅ 수정된 파일명
        fi

        backend_exit_code=$?
        cd ..

        if [[ $backend_exit_code -eq 0 ]]; then
            log_success "백엔드 서비스 시작 완료"
        else
            log_error "백엔드 서비스 시작 실패"
            if [[ ! $VERBOSE ]]; then
                echo "로그 확인: cat /tmp/backend_start.log"
            fi
            exit 1
        fi
    else
        log_error "백엔드 시작 스크립트를 찾을 수 없습니다"
        exit 1
    fi

    # 백엔드 API 준비 대기
    echo -n "백엔드 API 준비 대기"
    max_attempts=30
    attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        if curl -s http://localhost:18000/docs > /dev/null 2>&1; then
            echo -e " ${GREEN}완료${NC}"
            break
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    if [[ $attempt -eq $max_attempts ]]; then
        echo -e " ${YELLOW}시간 초과 (계속 진행)${NC}"
    fi
else
    echo -e "\n${YELLOW}⏭️ [2/3] 백엔드 서비스 건너뛰기${NC}"
fi

# 6. 프론트엔드 서비스 시작
if [[ $SKIP_FRONTEND == false ]]; then
    echo -e "\n${BLUE}🎨 [3/3] 프론트엔드 서비스 시작...${NC}"
    echo "======================================"

    if [[ -f "frontend/scripts/start_frontend.sh" ]]; then
        cd frontend

        if $VERBOSE; then
            ./scripts/start_frontend.sh
        else
            ./scripts/start_frontend.sh > /tmp/frontend_start.log 2>&1
        fi

        frontend_exit_code=$?
        cd ..

        if [[ $frontend_exit_code -eq 0 ]]; then
            log_success "프론트엔드 서비스 시작 완료"
        else
            log_error "프론트엔드 서비스 시작 실패"
            if [[ ! $VERBOSE ]]; then
                echo "로그 확인: cat /tmp/frontend_start.log"
            fi
            exit 1
        fi
    else
        log_error "프론트엔드 시작 스크립트를 찾을 수 없습니다"
        exit 1
    fi

    # 프론트엔드 UI 준비 대기
    echo -n "프론트엔드 UI 준비 대기"
    max_attempts=20
    attempt=0

    while [[ $attempt -lt $max_attempts ]]; do
        if curl -s http://localhost:8501 > /dev/null 2>&1; then
            echo -e " ${GREEN}완료${NC}"
            break
        fi
        echo -n "."
        sleep 3
        attempt=$((attempt + 1))
    done

    if [[ $attempt -eq $max_attempts ]]; then
        echo -e " ${YELLOW}시간 초과 (계속 진행)${NC}"
    fi
else
    echo -e "\n${YELLOW}⏭️ [3/3] 프론트엔드 서비스 건너뛰기${NC}"
fi

# 7. 전체 시스템 상태 확인
echo -e "\n${BLUE}📊 전체 시스템 상태 확인...${NC}"
echo "==============================="

# 서비스별 상태 확인
services=(
    "Qdrant:6333:🗄️"
    "Redis:6379:🔴"
    "API:18000:🔧"
    "UI:8501:🎨"
)

all_services_running=true

for service_info in "${services[@]}"; do
    IFS=':' read -r name port icon <<< "$service_info"
    echo -n "   $icon $name (포트 $port): "

    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 실행 중${NC}"

        # 추가 연결 테스트
        case $port in
            6333)
                if curl -s http://localhost:6333/health > /dev/null 2>&1; then
                    echo -e "      ${GREEN}→ 헬스체크 통과${NC}"
                fi
                ;;
            18000)
                if curl -s http://localhost:18000/docs > /dev/null 2>&1; then
                    echo -e "      ${GREEN}→ API 문서 접근 가능${NC}"
                fi
                ;;
            8501)
                if curl -s http://localhost:8501 > /dev/null 2>&1; then
                    echo -e "      ${GREEN}→ UI 접근 가능${NC}"
                fi
                ;;
        esac
    else
        echo -e "${RED}❌ 실행되지 않음${NC}"
        all_services_running=false
    fi
done

# 8. 외부 서비스 확인
echo -e "\n   🤖 외부 서비스:"
OLLAMA_HOST=${OLLAMA_HOST:-"http://172.16.15.112:11434"}
echo -n "   - Ollama ($OLLAMA_HOST): "
if curl -s --connect-timeout 5 "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 연결됨${NC}"
else
    echo -e "${YELLOW}⚠️ 연결 안됨${NC}"
fi

# 9. 최종 결과 및 접속 정보
log_success "GTOne RAG 시스템 시작 완료!"
echo "==============================="

# 시작 시간 정보
OVERALL_END_TIME=$(date)
echo "시작 시간: $OVERALL_START_TIME"
echo "완료 시간: $OVERALL_END_TIME"

# 접속 정보
echo -e "\n${YELLOW}📌 서비스 접속 정보:${NC}"
echo -e "   🌐 웹 UI:           http://localhost:8501"
echo -e "   📚 API 문서:        http://localhost:18000/docs"
echo -e "   📊 API 헬스체크:    http://localhost:18000/v1/health"
echo -e "   🗄️ Qdrant 대시보드: http://localhost:6333/dashboard"

# 사용 가이드
echo -e "\n${YELLOW}🚀 빠른 시작 가이드:${NC}"
echo "   1. 웹 브라우저에서 http://localhost:8501 접속"
echo "   2. 사이드바에서 PDF 문서 업로드"
echo "   3. 채팅으로 AI와 대화하거나 검색 페이지에서 문서 검색"

# 관리 명령어
echo -e "\n${YELLOW}📋 시스템 관리 명령어:${NC}"
echo -e "   🛑 전체 종료:       ./scripts/stop_all.sh"
echo -e "   📊 로그 확인:"
echo -e "      - 인프라:       cd infrastructure && docker logs qdrant-service"
echo -e "      - 백엔드:       tail -f backend/logs/api.log"
echo -e "      - 프론트엔드:   tail -f frontend/logs/streamlit.log"

# 문제 해결
if [[ $all_services_running == false ]]; then
    echo -e "\n${YELLOW}💡 문제 해결:${NC}"
    echo "   일부 서비스가 시작되지 않았습니다."
    echo "   개별 서비스 로그를 확인하세요:"
    echo "   - cat /tmp/infra_start.log"
    echo "   - cat /tmp/backend_start.log"
    echo "   - cat /tmp/frontend_start.log"
fi

# 브라우저 자동 열기 (선택적)
if $all_services_running; then
    echo -e "\n${YELLOW}🌐 브라우저에서 웹 UI를 여시겠습니까? (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        # OS별 브라우저 열기
        if [[ "$(uname -s)" == "Darwin" ]]; then
            open "http://localhost:8501"
        elif [[ "$(uname -s)" == "Linux" ]]; then
            xdg-open "http://localhost:8501" 2>/dev/null
        fi
        echo "브라우저에서 웹 UI를 열었습니다."
    fi
fi

echo -e "\n${GREEN}✨ 즐거운 AI 문서 분석 되세요! ✨${NC}"

# 시스템 정보 저장
cat > .system_info << EOF
# GTOne RAG System Info
# Generated: $(date)
OVERALL_START_TIME=$OVERALL_START_TIME
OVERALL_END_TIME=$OVERALL_END_TIME
ALL_SERVICES_RUNNING=$all_services_running
SKIPPED_INFRA=$SKIP_INFRA
SKIPPED_BACKEND=$SKIP_BACKEND
SKIPPED_FRONTEND=$SKIP_FRONTEND
EOF