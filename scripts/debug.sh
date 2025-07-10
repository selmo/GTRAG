#!/bin/bash
# GTOne RAG System 디버깅 스크립트

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== GTOne RAG System 디버깅 ===${NC}"
echo ""

# 1. Docker 환경 확인
echo -e "${YELLOW}[1. Docker 환경 확인]${NC}"
echo "Docker 버전:"
docker --version
echo "Docker Compose 버전:"
docker compose version
echo ""

# 2. 컨테이너 상태
echo -e "${YELLOW}[2. 컨테이너 상태]${NC}"
docker compose ps
echo ""

# 3. 네트워크 확인
echo -e "${YELLOW}[3. 네트워크 정보]${NC}"
docker network ls | grep gtrag
echo ""
echo "네트워크 상세:"
docker network inspect gtrag_gtrag-network 2>/dev/null | jq '.[] | {Name, Driver, Containers: .Containers | keys}' 2>/dev/null || echo "jq가 설치되지 않아 JSON 포맷팅을 할 수 없습니다."
echo ""

# 4. 볼륨 확인
echo -e "${YELLOW}[4. Docker 볼륨]${NC}"
docker volume ls | grep gtrag
echo ""

# 5. 환경변수 확인
echo -e "${YELLOW}[5. 환경변수 확인]${NC}"
if [ -f .env ]; then
    echo ".env 파일 존재 ✓"
    echo "주요 설정:"
    grep -E "OLLAMA_HOST|QDRANT_HOST|API_BASE_URL" .env | sed 's/^/  /'
else
    echo -e "${RED}.env 파일이 없습니다!${NC}"
fi
echo ""

# 6. 포트 사용 확인
echo -e "${YELLOW}[6. 포트 사용 상태]${NC}"
for port in 18000 8501 6333 6379; do
    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "포트 $port: ${GREEN}사용 중${NC}"
        lsof -i:$port | grep LISTEN | head -1
    else
        echo -e "포트 $port: ${RED}미사용${NC}"
    fi
done
echo ""

# 7. API 연결 테스트
echo -e "${YELLOW}[7. API 연결 테스트]${NC}"
echo -n "API 서버 (localhost:18000): "
if curl -s http://localhost:18000/docs > /dev/null 2>&1; then
    echo -e "${GREEN}연결 성공${NC}"
else
    echo -e "${RED}연결 실패${NC}"
    echo "  컨테이너 내부에서 테스트:"
    docker compose exec api curl -s http://localhost:18000/docs > /dev/null 2>&1 && echo -e "  ${GREEN}내부 연결 성공${NC}" || echo -e "  ${RED}내부 연결도 실패${NC}"
fi

echo -n "Streamlit UI (localhost:8501): "
if curl -s http://localhost:8501 > /dev/null 2>&1; then
    echo -e "${GREEN}연결 성공${NC}"
else
    echo -e "${RED}연결 실패${NC}"
fi

echo -n "Qdrant (localhost:6333): "
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo -e "${GREEN}연결 성공${NC}"
else
    echo -e "${RED}연결 실패${NC}"
fi
echo ""

# 8. 최근 로그 확인
echo -e "${YELLOW}[8. 최근 에러 로그]${NC}"
echo "API 서버 에러:"
docker compose logs api 2>&1 | grep -i error | tail -5 | sed 's/^/  /'
echo ""
echo "Streamlit 에러:"
docker compose logs streamlit 2>&1 | grep -i error | tail -5 | sed 's/^/  /'
echo ""

# 9. 리소스 사용량
echo -e "${YELLOW}[9. 리소스 사용량]${NC}"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
echo ""

# 10. Python 패키지 확인
echo -e "${YELLOW}[10. Python 패키지 설치 확인]${NC}"
echo "API 컨테이너 패키지:"
docker compose exec -T api pip list | grep -E "fastapi|qdrant-client|sentence-transformers" | sed 's/^/  /'
echo ""

# 11. 파일 구조 확인
echo -e "${YELLOW}[11. 프로젝트 구조 확인]${NC}"
echo "UI 구조:"
if [ -d "ui" ]; then
    tree ui -L 2 2>/dev/null || find ui -type d -not -path '*/\.*' | sort | sed 's/^/  /'
else
    echo -e "${RED}ui 디렉토리가 없습니다!${NC}"
fi
echo ""

# 12. 권한 확인
echo -e "${YELLOW}[12. 파일 권한 확인]${NC}"
echo "실행 권한이 있는 스크립트:"
find . -name "*.sh" -type f -executable 2>/dev/null | sed 's/^/  /'
echo ""

# 문제 진단
echo -e "${BLUE}=== 문제 진단 ===${NC}"
problems=0

# API 서버 확인
if ! docker compose ps | grep -q "api.*Up"; then
    echo -e "${RED}• API 서버가 실행되지 않았습니다.${NC}"
    echo "  해결: docker compose up -d api"
    ((problems++))
fi

# Streamlit 확인
if ! docker compose ps | grep -q "streamlit.*Up"; then
    echo -e "${RED}• Streamlit UI가 실행되지 않았습니다.${NC}"
    echo "  해결: docker compose up -d streamlit"
    ((problems++))
fi

# .env 파일 확인
if [ ! -f .env ]; then
    echo -e "${RED}• .env 파일이 없습니다.${NC}"
    echo "  해결: cp .env.example .env"
    ((problems++))
fi

# ui 디렉토리 확인
if [ ! -d "ui" ]; then
    echo -e "${RED}• ui 디렉토리가 없습니다.${NC}"
    echo "  해결: 프로젝트 구조를 다시 설정하세요."
    ((problems++))
fi

if [ $problems -eq 0 ]; then
    echo -e "${GREEN}✅ 문제가 발견되지 않았습니다.${NC}"
else
    echo -e "${YELLOW}⚠️  $problems개의 문제가 발견되었습니다.${NC}"
fi

echo ""
echo -e "${BLUE}=== 유용한 디버깅 명령어 ===${NC}"
echo "• 실시간 로그: docker compose logs -f [서비스명]"
echo "• 컨테이너 접속: docker compose exec [서비스명] /bin/bash"
echo "• 환경변수 확인: docker compose exec [서비스명] env"
echo "• 네트워크 테스트: docker compose exec api ping qdrant"
echo "• Python 경로 확인: docker compose exec api python -c 'import sys; print(sys.path)'"
echo ""