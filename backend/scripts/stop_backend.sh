#!/bin/bash

# ==================================================
# GTOne RAG – 백엔드 서비스 종료 스크립트
# (backend/scripts/stop_backend.sh 위치에서 실행)
# ==================================================

set -euo pipefail

# ---------- 색상 정의 ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---------- 배너 ----------
echo -e "${RED}🛑 GTOne RAG - 백엔드 서비스 종료${NC}"
echo "================================"

STOP_START_TIME=$(date)
echo "종료 시작 시간: $STOP_START_TIME"

# ---------- 프로젝트 루트 이동 ----------
# 이 스크립트는 <프로젝트 루트>/backend/scripts/stop_backend.sh 에 위치한다.
# 루트 = SCRIPT_DIR/../..
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT" || { echo -e "${RED}❌ 프로젝트 루트로 이동 실패${NC}"; exit 1; }

echo -e "${BLUE}📁 프로젝트 루트: $(pwd)${NC}"

# ---------- 구조 확인 ----------
if [[ ! -f "backend/api/main.py" ]]; then
  echo -e "${RED}❌ backend/api/main.py 가 존재하지 않습니다. 경로를 확인하세요.${NC}"
  exit 1
fi

echo -e "${GREEN}✅ 프로젝트 구조 확인 완료${NC}"

# ---------- 함수: PID 기반 서비스 종료 ----------
stop_service() {
  local pidfile=$1
  local service_name=$2
  local timeout=${3:-10}

  if [[ -f "$pidfile" ]]; then
    local PID=$(cat "$pidfile")
    echo -n "   $service_name (PID: $PID) 종료 중... "

    if kill -0 "$PID" 2>/dev/null; then
      kill "$PID" 2>/dev/null  # 정상 종료 시도
      for _ in $(seq 1 $timeout); do
        if ! kill -0 "$PID" 2>/dev/null; then
          echo -e "${GREEN}완료${NC}"; break
        fi
        sleep 1
      done
      if kill -0 "$PID" 2>/dev/null; then
        echo -e "${YELLOW}강제 종료${NC}"; kill -9 "$PID" 2>/dev/null
      fi
    else
      echo -e "${YELLOW}이미 종료됨${NC}"
    fi
    rm -f "$pidfile"
  else
    echo "   $service_name PID 파일 없음"
  fi
}

# ---------- 서비스 종료 ----------
stop_service ".celery.pid" "Celery 워커" 15
stop_service ".api.pid" "FastAPI 서버" 10

# ---------- 포트 기반 정리 ----------
cleanup_port() {
  local port=$1; local name=$2
  echo -n "   포트 $port ($name) 확인... "
  if lsof -i:$port > /dev/null 2>&1; then
    echo -e "${YELLOW}사용 중${NC}"; echo "      프로세스 정리 중..."
    local PIDS=$(lsof -ti:$port)
    for PID in $PIDS; do
      echo "      PID $PID 종료 중..."; kill "$PID" 2>/dev/null; sleep 2
      kill -0 "$PID" 2>/dev/null && { echo "      PID $PID 강제 종료..."; kill -9 "$PID" 2>/dev/null; }
    done
  else
    echo -e "${GREEN}정리됨${NC}"
  fi
}

# FastAPI (18000)
cleanup_port 18000 "FastAPI"

# ---------- 프로세스 패턴 기반 추가 정리 ----------
kill_if_exists() {
  local pattern=$1; local desc=$2
  echo -n "   $desc 프로세스 확인... "
  local PIDS=$(pgrep -f "$pattern" 2>/dev/null || true)
  if [[ -n "$PIDS" ]]; then
    echo -e "${YELLOW}발견됨${NC}"
    for PID in $PIDS; do
      echo "      $desc PID $PID 종료..."; kill -9 "$PID" 2>/dev/null
    done
  else
    echo -e "${GREEN}없음${NC}"
  fi
}

kill_if_exists "uvicorn.*backend\.api\.main" "Uvicorn"
kill_if_exists "celery.*backend\.api\.main\.celery_app" "Celery"
kill_if_exists "python.*backend/api/" "Python 백엔드"

# ---------- 임시 파일 및 로그 정리 ----------
for pidfile in .api.pid .celery.pid; do [[ -f "$pidfile" ]] && { echo "   $pidfile 삭제..."; rm -f "$pidfile"; }; done

# 로그 삭제 여부 묻기
if [[ -d "logs" ]]; then
  LOG_CNT=$(find logs -name "*.log" 2>/dev/null | wc -l)
  if [[ $LOG_CNT -gt 0 ]]; then
    echo "   $LOG_CNT 개의 로그 파일이 있습니다. 삭제하시겠습니까? (y/n)"; read -r resp
    if [[ "$resp" =~ ^[Yy]$ ]]; then
      rm -f logs/*.log
      echo -e "   ${GREEN}로그 삭제 완료${NC}"
    else
      echo -e "   ${BLUE}로그 보존${NC}"
    fi
  fi
fi

# ---------- 최종 포트 상태 확인 ----------
all_ports_clear=true
lsof -i:18000 > /dev/null 2>&1 && all_ports_clear=false

if $all_ports_clear; then
  echo -e "\n${GREEN}🎉 GTOne RAG 백엔드 서비스가 완전히 종료되었습니다.${NC}"
else
  echo -e "\n${YELLOW}⚠️  일부 포트가 여전히 사용 중입니다.${NC}"
  echo "   sudo lsof -ti:18000 | xargs sudo kill -9"
fi

# ---------- 종료 요약 ----------
STOP_END_TIME=$(date)

echo -e "\n${BLUE}📊 종료 요약:${NC}"
echo "   종료 시작: $STOP_START_TIME"
echo "   종료 완료: $STOP_END_TIME"

echo -e "\n${GREEN}▶️ 다음 시작 명령: ./backend/scripts/start_backend.sh${NC}"

exit 0
