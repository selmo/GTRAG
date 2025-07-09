# 🚀 GTOne RAG - 빠른 시작 가이드

5분 안에 시작하기!

## 1️⃣ 사전 준비

- Docker & Docker Compose 설치
- Git 설치

## 2️⃣ 설치 (1분)

```bash
# 프로젝트 클론
git clone https://github.com/your-org/gtrag.git
cd gtrag

# 환경 파일 생성
cp .env.example .env
```

## 3️⃣ 환경 설정 (1분)

`.env` 파일 편집:
```bash
# 외부 Ollama 서버 주소 설정
OLLAMA_HOST=http://172.16.15.112:11434
```

## 4️⃣ 실행 (2분)

```bash
# 시작 스크립트 실행
chmod +x start.sh
./start.sh
```

## 5️⃣ 사용 (1분)

1. 브라우저에서 http://localhost:8501 접속
2. 왼쪽 사이드바에서 PDF 파일 업로드
3. 채팅창에 질문 입력
4. AI 답변 확인!

## 🎯 주요 URL

- 💬 **웹 UI**: http://localhost:8501
- 📚 **API 문서**: http://localhost:18000/docs
- 🗄️ **Qdrant**: http://localhost:6333/dashboard

## 🛑 종료

```bash
docker compose down
```

## ❓ 도움말

문제가 있나요?
- 전체 문서: [README.md](README.md)
- 로그 확인: `docker compose logs -f`
- 시스템 상태: 웹 UI 사이드바의 "시스템 상태 확인" 클릭

---
**💡 팁**: 첫 실행 시 Docker 이미지 다운로드로 시간이 걸릴 수 있습니다.