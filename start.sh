#!/bin/bash

echo "🚀 GTOne RAG System 시작 중..."

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Docker 설치 확인
echo "🐳 Docker 확인 중..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker가 설치되어 있지 않습니다. Docker를 먼저 설치해주세요.${NC}"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose가 설치되어 있지 않습니다.${NC}"
    exit 1
fi

# 2. 프로젝트 구조 확인 및 생성
echo "📁 프로젝트 구조 확인 중..."
mkdir -p api ingestion embedding retriever scripts llm
mkdir -p ui/pages ui/components ui/utils
mkdir -p .streamlit

# __init__.py 파일 생성
touch api/__init__.py ingestion/__init__.py embedding/__init__.py retriever/__init__.py llm/__init__.py
touch ui/__init__.py ui/components/__init__.py ui/utils/__init__.py ui/pages/__init__.py

# 3. 환경 파일 확인
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env 파일이 없습니다. .env.example에서 복사합니다...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ .env 파일이 생성되었습니다. 필요한 설정을 수정해주세요.${NC}"
    else
        echo -e "${RED}❌ .env.example 파일도 없습니다. 환경 설정이 필요합니다.${NC}"
        exit 1
    fi
fi

# 4. 기존 컨테이너 정리 (선택적)
if [ "$1" == "--clean" ]; then
    echo "🧹 기존 컨테이너 정리 중..."
    docker compose down -v
fi

# 5. Docker Compose 빌드 및 시작
echo "🐳 Docker 컨테이너 빌드 및 시작 중..."
docker compose up --build -d

# 6. 서비스 준비 대기
echo "⏳ 서비스 준비 중..."
echo -n "대기 중"

# 최대 60초 대기
for i in {1..12}; do
    sleep 5
    echo -n "."

    # API 서버 확인
    if curl -s http://localhost:18000/v1/health > /dev/null 2>&1; then
        api_ready=true
    else
        api_ready=false
    fi

    # Streamlit 확인
    if curl -s http://localhost:8501 > /dev/null 2>&1; then
        ui_ready=true
    else
        ui_ready=false
    fi

    # 모두 준비되면 종료
    if [ "$api_ready" = true ] && [ "$ui_ready" = true ]; then
        echo ""
        break
    fi
done
echo ""

# 7. 서비스 상태 확인
echo "✅ 서비스 상태 확인 중..."

# API 상태
if curl -s http://localhost:18000/v1/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API 서버: 정상 작동${NC}"
else
    echo -e "${RED}❌ API 서버: 연결 실패${NC}"
    echo "   로그 확인: docker compose logs api"
fi

# Streamlit 상태
if curl -s http://localhost:8501 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Web UI: 정상 작동${NC}"
else
    echo -e "${RED}❌ Web UI: 연결 실패${NC}"
    echo "   로그 확인: docker compose logs streamlit"
fi

# Qdrant 상태
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Qdrant: 정상 작동${NC}"
else
    echo -e "${YELLOW}⚠️  Qdrant: 시작 중...${NC}"
fi

# Redis 상태
if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis: 정상 작동${NC}"
else
    echo -e "${YELLOW}⚠️  Redis: 시작 중...${NC}"
fi

# 8. 컨테이너 상태 표시
echo ""
echo "📊 실행 중인 컨테이너:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "🎉 GTOne RAG System이 준비되었습니다!"
echo ""
echo "📌 접속 정보:"
echo "   - Web UI: http://localhost:8501"
echo "   - API Docs: http://localhost:18000/docs"
echo "   - Qdrant Dashboard: http://localhost:6333/dashboard"
echo ""
echo "💡 유용한 명령어:"
echo "   - 로그 확인: docker compose logs -f [서비스명]"
echo "   - 시스템 종료: docker compose down"
echo "   - 데이터 포함 종료: docker compose down -v"
echo "   - 상태 확인: docker compose ps"
echo ""
echo "📚 문서: https://github.com/selmo/gtrag"

# 9. 브라우저 자동 열기 (선택적)
if [ "$2" == "--open" ]; then
    echo "🌐 브라우저 열기 중..."
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8501
    elif command -v open &> /dev/null; then
        open http://localhost:8501
    fi
fi