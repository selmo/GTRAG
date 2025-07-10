#!/bin/bash

echo "🔧 GTOne RAG System 수정 및 재빌드"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 1. 현재 컨테이너 중지 및 제거
echo -e "${YELLOW}🛑 기존 컨테이너 중지 및 제거 중...${NC}"
docker compose -f docker/development/docker-compose.yml down -v

# 2. 이미지 제거 (선택적)
echo -e "${YELLOW}🗑️ 기존 이미지 제거 중...${NC}"
docker rmi development-gtrag-dev 2>/dev/null || true

# 3. Docker 캐시 정리
echo -e "${YELLOW}🧹 Docker 캐시 정리 중...${NC}"
docker builder prune -f

# 4. 새 이미지 빌드 및 시작
echo -e "${BLUE}🔨 새 이미지 빌드 및 시작 중...${NC}"
docker compose -f docker/development/docker-compose.yml up --build -d

# 5. 서비스 준비 대기 (더 긴 시간)
echo -e "${BLUE}⏳ 서비스 준비 중 (최대 3분 대기)...${NC}"
echo -n "대기 중"

for i in {1..36}; do
    sleep 5
    echo -n "."

    # 모든 서비스 확인
    if curl -s http://localhost:8501 > /dev/null 2>&1; then
        if docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev curl -s http://localhost:18000/v1/health > /dev/null 2>&1; then
            if docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev redis-cli ping > /dev/null 2>&1; then
                echo -e "\n${GREEN}✅ 모든 서비스가 준비되었습니다!${NC}"
                break
            fi
        fi
    fi

    if [ $i -eq 36 ]; then
        echo -e "\n${YELLOW}⚠️ 일부 서비스가 아직 시작 중일 수 있습니다.${NC}"
    fi
done

# 6. 최종 상태 확인
echo -e "\n${BLUE}📊 최종 서비스 상태 확인...${NC}"

# 컨테이너 상태
echo -e "\n${YELLOW}컨테이너 상태:${NC}"
docker compose -f docker/development/docker-compose.yml ps

# Supervisor 상태
echo -e "\n${YELLOW}Supervisor 프로세스 상태:${NC}"
docker compose -f docker/development/docker-compose.yml exec gtrag-dev supervisorctl status || echo "Supervisor 접속 실패"

# 개별 서비스 테스트
echo -e "\n${YELLOW}서비스 연결 테스트:${NC}"

# Streamlit
if curl -s http://localhost:8501 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Streamlit UI: 정상 작동${NC}"
else
    echo -e "${RED}❌ Streamlit UI: 연결 실패${NC}"
fi

# API 서버
if docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev curl -s http://localhost:18000/v1/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API 서버: 정상 작동${NC}"
else
    echo -e "${RED}❌ API 서버: 연결 실패${NC}"
fi

# Qdrant
if docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev curl -s http://localhost:6333/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Qdrant: 정상 작동${NC}"
else
    echo -e "${RED}❌ Qdrant: 연결 실패${NC}"
fi

# Redis
if docker compose -f docker/development/docker-compose.yml exec -T gtrag-dev redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis: 정상 작동${NC}"
else
    echo -e "${RED}❌ Redis: 연결 실패${NC}"
fi

echo -e "\n${GREEN}🎉 재빌드 완료!${NC}"
echo -e "\n${YELLOW}📌 접속 정보:${NC}"
echo -e "   🌐 Web UI: http://localhost:8501"

echo -e "\n${YELLOW}🔧 문제 해결:${NC}"
echo -e "   📋 로그 확인: docker compose -f docker/development/docker-compose.yml logs -f"
echo -e "   🐚 컨테이너 접속: docker compose -f docker/development/docker-compose.yml exec gtrag-dev /bin/bash"
echo -e "   📊 프로세스 상태: docker compose -f docker/development/docker-compose.yml exec gtrag-dev supervisorctl status"