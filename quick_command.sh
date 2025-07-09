#!/bin/bash
# GTOne RAG System - 빠른 명령어 모음

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

function show_menu() {
    echo -e "${BLUE}=== GTOne RAG System 관리 메뉴 ===${NC}"
    echo "1. 시스템 시작"
    echo "2. 시스템 중지"
    echo "3. 시스템 재시작"
    echo "4. 로그 보기"
    echo "5. 상태 확인"
    echo "6. 데이터 백업"
    echo "7. 데이터 복원"
    echo "8. 컨테이너 쉘 접속"
    echo "9. 시스템 정리 (주의!)"
    echo "0. 종료"
    echo ""
}

function start_system() {
    echo -e "${GREEN}시스템을 시작합니다...${NC}"
    ./start.sh
}

function stop_system() {
    echo -e "${YELLOW}시스템을 중지합니다...${NC}"
    docker compose down
}

function restart_system() {
    echo -e "${YELLOW}시스템을 재시작합니다...${NC}"
    docker compose down
    docker compose up -d
}

function show_logs() {
    echo "어떤 서비스의 로그를 보시겠습니까?"
    echo "1. 모든 서비스"
    echo "2. API"
    echo "3. Worker"
    echo "4. Streamlit"
    echo "5. Qdrant"
    echo "6. Redis"
    read -p "선택: " log_choice

    case $log_choice in
        1) docker compose logs -f ;;
        2) docker compose logs -f api ;;
        3) docker compose logs -f worker ;;
        4) docker compose logs -f streamlit ;;
        5) docker compose logs -f qdrant ;;
        6) docker compose logs -f redis ;;
        *) echo "잘못된 선택입니다." ;;
    esac
}

function check_status() {
    echo -e "${BLUE}=== 시스템 상태 ===${NC}"

    # 컨테이너 상태
    echo -e "\n${YELLOW}컨테이너 상태:${NC}"
    docker compose ps

    # 서비스 헬스 체크
    echo -e "\n${YELLOW}서비스 헬스 체크:${NC}"

    if curl -s http://localhost:18000/v1/health > /dev/null 2>&1; then
        echo -e "API 서버: ${GREEN}✅ 정상${NC}"
    else
        echo -e "API 서버: ${RED}❌ 오류${NC}"
    fi

    if curl -s http://localhost:8501 > /dev/null 2>&1; then
        echo -e "Streamlit UI: ${GREEN}✅ 정상${NC}"
    else
        echo -e "Streamlit UI: ${RED}❌ 오류${NC}"
    fi

    if curl -s http://localhost:6333/health > /dev/null 2>&1; then
        echo -e "Qdrant: ${GREEN}✅ 정상${NC}"
    else
        echo -e "Qdrant: ${RED}❌ 오류${NC}"
    fi

    if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "Redis: ${GREEN}✅ 정상${NC}"
    else
        echo -e "Redis: ${RED}❌ 오류${NC}"
    fi

    # 리소스 사용량
    echo -e "\n${YELLOW}리소스 사용량:${NC}"
    docker stats --no-stream
}

function backup_data() {
    echo -e "${BLUE}데이터를 백업합니다...${NC}"

    # 백업 디렉토리 생성
    backup_dir="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p $backup_dir

    # Qdrant 데이터 백업
    echo "Qdrant 데이터 백업 중..."
    docker run --rm -v gtrag_qdrant_data:/data -v $(pwd)/$backup_dir:/backup alpine tar czf /backup/qdrant_backup.tar.gz -C /data .

    # Redis 데이터 백업
    echo "Redis 데이터 백업 중..."
    docker compose exec -T redis redis-cli SAVE
    docker run --rm -v gtrag_redis_data:/data -v $(pwd)/$backup_dir:/backup alpine tar czf /backup/redis_backup.tar.gz -C /data .

    echo -e "${GREEN}백업 완료: $backup_dir${NC}"
}

function restore_data() {
    echo "사용 가능한 백업:"
    ls -la backups/

    read -p "복원할 백업 폴더명을 입력하세요: " backup_name

    if [ -d "backups/$backup_name" ]; then
        echo -e "${YELLOW}주의: 현재 데이터가 모두 삭제됩니다!${NC}"
        read -p "계속하시겠습니까? (y/N): " confirm

        if [ "$confirm" = "y" ]; then
            # 서비스 중지
            docker compose down

            # Qdrant 데이터 복원
            echo "Qdrant 데이터 복원 중..."
            docker run --rm -v gtrag_qdrant_data:/data -v $(pwd)/backups/$backup_name:/backup alpine sh -c "rm -rf /data/* && tar xzf /backup/qdrant_backup.tar.gz -C /data"

            # Redis 데이터 복원
            echo "Redis 데이터 복원 중..."
            docker run --rm -v gtrag_redis_data:/data -v $(pwd)/backups/$backup_name:/backup alpine sh -c "rm -rf /data/* && tar xzf /backup/redis_backup.tar.gz -C /data"

            # 서비스 재시작
            docker compose up -d

            echo -e "${GREEN}복원 완료${NC}"
        fi
    else
        echo -e "${RED}백업을 찾을 수 없습니다.${NC}"
    fi
}

function shell_access() {
    echo "어떤 컨테이너에 접속하시겠습니까?"
    echo "1. API"
    echo "2. Worker"
    echo "3. Streamlit"
    echo "4. Qdrant"
    echo "5. Redis"
    read -p "선택: " shell_choice

    case $shell_choice in
        1) docker compose exec api /bin/bash ;;
        2) docker compose exec worker /bin/bash ;;
        3) docker compose exec streamlit /bin/bash ;;
        4) docker compose exec qdrant /bin/sh ;;
        5) docker compose exec redis /bin/sh ;;
        *) echo "잘못된 선택입니다." ;;
    esac
}

function cleanup_system() {
    echo -e "${RED}경고: 모든 데이터가 삭제됩니다!${NC}"
    read -p "정말로 시스템을 정리하시겠습니까? (yes 입력): " confirm

    if [ "$confirm" = "yes" ]; then
        echo "시스템을 정리합니다..."
        docker compose down -v
        docker system prune -a -f
        echo -e "${GREEN}정리 완료${NC}"
    else
        echo "취소되었습니다."
    fi
}

# 메인 루프
while true; do
    show_menu
    read -p "선택: " choice

    case $choice in
        1) start_system ;;
        2) stop_system ;;
        3) restart_system ;;
        4) show_logs ;;
        5) check_status ;;
        6) backup_data ;;
        7) restore_data ;;
        8) shell_access ;;
        9) cleanup_system ;;
        0) echo "종료합니다."; exit 0 ;;
        *) echo "잘못된 선택입니다." ;;
    esac

    echo ""
    read -p "계속하려면 Enter를 누르세요..."
    clear
done