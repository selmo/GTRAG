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

# 프로젝트 루트로 이동
cd "$PROJECT_ROOT"

# 1. Docker 확인
echo -e "${BLUE}🐳 Docker 환경 확인 중...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker가 설치되지 않았습니다.${NC}"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose가 설치되지 않았습니다.${NC}"
    exit 1
fi

# 2. 환경 파일 확인
echo -e "${BLUE}⚙️ 환경 설정 확인 중...${NC}"
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

# 3. Ollama 서버 연결 확인
echo -e "${BLUE}🤖 Ollama 서버 연결 확인 중...${NC}"
OLLAMA_HOST=$(grep OLLAMA_HOST .env | cut -d'=' -f2)
if [ -n "$OLLAMA_HOST" ]; then
    if curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama 서버 연결 성공: $OLLAMA_HOST${NC}"
    else
        echo -e "${YELLOW}⚠️ Ollama 서버 연결 실패: $OLLAMA_HOST${NC}"
        echo -e "${YELLOW}   계속 진행하지만 LLM 기능이 제한될 수 있습니다.${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ OLLAMA_HOST가 설정되지 않았습니다.${NC}"
fi

# 4. 기존 컨테이너 정리 (선택적)
if [ "$1" == "--clean" ]; then
    echo -e "${YELLOW}🧹 기존 컨테이너 정리 중...${NC}"
    docker compose -f docker/development/docker-compose.yml down -v
fi

# 5. 개발환경 빌드 및 시작
echo -e "${BLUE}🔨 개발환경 빌드 및 시작 중...${NC}"
docker compose -f docker/development/docker-compose.yml up --build -d

# 6. 서비스 준비 대기
echo -e "${BLUE}⏳ 서비스 준비 중...${NC}"
echo -n "대기 중"

# 최대 120초 대기 (단일 컨테이너는 시작 시간이 더 걸림)
for i in {1..24}; do
    sleep 5
    echo -n "."

    # Streamlit 확인
    if curl -s http://localhost:8501 > /dev/null 2>&1; then
        echo -e "\n${GREEN}✅ 서비스가 준비되었습니다!${NC}"
        break
    fi

    if [ $i -eq 24 ]; then
        echo -e "\n${YELLOW}⚠️ 서비스 시작이 지연되고 있습니다.${NC}"
        echo -e "${YELLOW}   로그를 확인하세요: docker compose -f docker/development/docker-compose.yml logs${NC}"
    fi
done

# 7. 서비스 상태 확인
echo -e "\n${BLUE}📊 서비스 상태 확인 중...${NC}"

# 컨테이너 상태
echo -e "\n${YELLOW}컨테이너 상태:${NC}"
docker compose -f docker/development/docker-compose.yml ps

# 웹 UI 상태
if curl -s http://localhost:8501 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Web UI: 정상 작동 (http://localhost:8501)${NC}"
else
    echo -e "${RED}❌ Web UI: 연결 실패${NC}"
fi

# 내부 서비스 상태 (컨테이너 내부에서 확인)
echo -e "\n${YELLOW}내부 서비스 상태:${NC}"
docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev curl -s http://localhost:18000/v1/health > /dev/null 2>&1 && \
    echo -e "${GREEN}✅ API 서버: 정상 작동${NC}" || \
    echo -e "${RED}❌ API 서버: 연결 실패${NC}"

docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev curl -s http://localhost:6333/health > /dev/null 2>&1 && \
    echo -e "${GREEN}✅ Qdrant: 정상 작동${NC}" || \
    echo -e "${RED}❌ Qdrant: 연결 실패${NC}"

docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev redis-cli ping > /dev/null 2>&1 && \
    echo -e "${GREEN}✅ Redis: 정상 작동${NC}" || \
    echo -e "${RED}❌ Redis: 연결 실패${NC}"

# 8. 최종 결과
echo -e "\n${GREEN}🎉 GTOne RAG System 개발환경이 시작되었습니다!${NC}"
echo -e "\n${YELLOW}📌 접속 정보:${NC}"
echo -e "   🌐 Web UI: http://localhost:8501"
echo -e "   📚 API 문서: http://localhost:18000/docs (컨테이너 내부)"
echo -e "   🗄️ Qdrant: http://localhost:6333/dashboard (컨테이너 내부)"

echo -e "\n${YELLOW}💡 유용한 명령어:${NC}"
echo -e "   📋 로그 확인: docker compose -f docker/development/docker-compose.yml logs -f"
echo -e "   🐚 컨테이너 접속: docker compose -f docker/development/docker-compose.yml exec gtrag-dev /bin/bash"
echo -e "   🛑 서비스 종료: docker compose -f docker/development/docker-compose.yml down"
echo -e "   🗑️ 완전 정리: docker compose -f docker/development/docker-compose.yml down -v"

echo -e "\n${YELLOW}🔧 디버깅:${NC}"
echo -e "   🐛 상세 로그: docker compose -f docker/development/docker-compose.yml logs gtrag-dev"
echo -e "   📊 컨테이너 상태: docker compose -f docker/development/docker-compose.yml ps"
echo -e "   🔍 내부 프로세스: docker compose -f docker/development/docker-compose.yml exec gtrag-dev supervisorctl status"

# 9. 브라우저 자동 열기 (선택적)
if [ "$2" == "--open" ] || [ "$1" == "--open" ]; then
    echo -e "\n${BLUE}🌐 브라우저 열기 중...${NC}"
    sleep 3
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:8501
    elif command -v open &> /dev/null; then
        open http://localhost:8501
    else
        echo -e "${YELLOW}   수동으로 http://localhost:8501 을 열어주세요.${NC}"
    fi
fi

echo -e "\n${GREEN}✨ 개발 환경 준비 완료! 즐거운 개발 되세요! ✨${NC}"