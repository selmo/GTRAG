#!/bin/bash

echo "🚀 Starting development environment (multi-container)..."

# 기존 컨테이너 정리
docker-compose -f docker/development/docker-compose.yml down

# 개발 환경 시작
docker-compose -f docker/development/docker-compose.yml up --build

echo "✅ Single-container environment started!"
echo "🌐 Web UI (only external access): http://localhost:8501"