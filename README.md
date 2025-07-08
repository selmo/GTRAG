# GTOne RAG System

📚 문서 기반 질의응답을 위한 RAG(Retrieval-Augmented Generation) 시스템

## 📋 목차

- [개요](#개요)
- [주요 기능](#주요-기능)
- [시스템 아키텍처](#시스템-아키텍처)
- [기술 스택](#기술-스택)
- [폴더 구조](#폴더-구조)
- [설치 및 실행](#설치-및-실행)
  - [Docker 실행 (권장)](#docker-실행-권장)
  - [로컬 실행](#로컬-실행)
- [사용 가이드](#사용-가이드)
- [API 문서](#api-문서)
- [환경 설정](#환경-설정)
- [문제 해결](#문제-해결)

## 개요

GTOne RAG System은 문서를 업로드하고, 자연어 질문을 통해 관련 정보를 찾아 답변을 생성하는 시스템입니다. 벡터 검색과 LLM을 결합하여 정확하고 맥락에 맞는 답변을 제공합니다.

### 🎯 주요 특징

- **다양한 문서 지원**: PDF, 이미지(OCR), 텍스트 파일
- **다국어 지원**: 한국어, 영어 동시 지원
- **실시간 처리**: 비동기 문서 처리 및 즉시 검색
- **웹 UI**: 사용하기 쉬운 Streamlit 인터페이스
- **확장 가능**: 모듈화된 구조로 쉬운 확장

## 주요 기능

### 1. 📄 문서 처리
- PDF 파싱 및 청크 분할
- 이미지 OCR (Azure Vision / Tesseract)
- 자동 텍스트 추출 및 전처리

### 2. 🔍 벡터 검색
- E5-large 다국어 임베딩 모델
- Qdrant 벡터 데이터베이스
- 유사도 기반 문서 검색

### 3. 🤖 답변 생성
- Ollama LLM 통합
- RAG 기반 답변 생성
- 소스 문서 참조 제공

### 4. 💻 웹 인터페이스
- 파일 업로드 UI
- 대화형 채팅 인터페이스
- 문서 검색 도구
- 시스템 상태 모니터링

## 시스템 아키텍처

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Streamlit UI  │────▶│   FastAPI Server │────▶│  Qdrant Vector  │
│   (Port 8501)   │     │   (Port 8000)    │     │  (Port 6333)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │                           │
                               ▼                           │
                        ┌──────────────┐                   │
                        │ Celery Worker│                   │
                        │   (Redis)    │                   │
                        └──────────────┘                   │
                               │                           │
                               ▼                           ▼
                        ┌──────────────┐           ┌──────────────┐
                        │    Ollama    │           │   Embedder   │
                        │(External LLM)│           │ (E5-large)   │
                        └──────────────┘           └──────────────┘
```

## 기술 스택

### Backend
- **FastAPI**: REST API 서버
- **Celery + Redis**: 비동기 작업 처리
- **Qdrant**: 벡터 데이터베이스
- **Sentence Transformers**: 임베딩 생성

### Frontend
- **Streamlit**: 웹 UI 프레임워크

### AI/ML
- **Ollama**: LLM 추론
- **E5-large**: 다국어 임베딩 모델
- **Tesseract/Azure Vision**: OCR

### Infrastructure
- **Docker & Docker Compose**: 컨테이너화
- **Python 3.11**: 런타임

## 폴더 구조

```
GTRAG/
│
├── api/                    # API 모듈
│   ├── main.py            # FastAPI 앱, Celery 설정
│   ├── routes.py          # API 라우트
│   └── schemas.py         # Pydantic 모델
│
├── ingestion/             # 문서 처리
│   ├── parser.py          # PDF/문서 파싱
│   └── ocr.py            # OCR 처리
│
├── embedding/             # 임베딩
│   └── embedder.py       # E5 임베딩 생성
│
├── retriever/             # 검색
│   └── retriever.py      # Qdrant 벡터 검색
│
├── llm/                   # LLM 연동
│   └── generator.py      # Ollama API 클라이언트
│
├── docker-compose.yml     # Docker 구성
├── Dockerfile            # Docker 이미지
├── requirements.txt      # Python 의존성
├── streamlit_app.py      # 웹 UI
├── .env                  # 환경 변수
└── start.sh             # 시작 스크립트
```

## 설치 및 실행

### Docker 실행 (권장)

#### 1. 전제 조건
- Docker & Docker Compose 설치
- 8GB 이상의 RAM
- 10GB 이상의 디스크 공간

#### 2. 프로젝트 클론
```bash
git clone https://github.com/your-org/gtrag.git
cd gtrag
```

#### 3. 환경 설정
`.env` 파일 생성:
```bash
# Qdrant
QDRANT__URL=http://qdrant:6333
QDRANT__API_KEY=

# Ollama (외부 서버)
OLLAMA_HOST=http://172.16.15.112:11434
OLLAMA_MODELS=llama3:8b-instruct

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

#### 4. 실행
```bash
# 실행 권한 부여
chmod +x start.sh

# 시스템 시작
./start.sh
```

#### 5. 접속
- 웹 UI: http://localhost:8501
- API 문서: http://localhost:8000/docs
- Qdrant Dashboard: http://localhost:6333/dashboard

### 로컬 실행

#### 1. 전제 조건
- Python 3.11+
- Qdrant 서버
- Redis 서버
- Tesseract OCR

#### 2. 의존성 설치
```bash
# 가상환경 생성
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 패키지 설치
pip install -r requirements.txt
```

#### 3. 서비스 시작
```bash
# Qdrant 시작 (별도 터미널)
docker run -p 6333:6333 qdrant/qdrant

# Redis 시작 (별도 터미널)
redis-server

# 환경변수 설정
export OLLAMA_HOST=http://172.16.15.112:11434

# 서비스 실행 (각각 별도 터미널)
# API 서버
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Celery Worker
celery -A api.main.celery_app worker -l info

# Streamlit UI
streamlit run streamlit_app.py
```

## 사용 가이드

### 1. 문서 업로드
1. 왼쪽 사이드바에서 "문서 업로드" 섹션 찾기
2. PDF, 이미지, 텍스트 파일 선택
3. "업로드" 버튼 클릭
4. 문서가 자동으로 처리되고 인덱싱됨

### 2. 질문하기
1. "채팅" 탭에서 질문 입력
2. 예: "계약서의 주요 조건은 무엇인가요?"
3. AI가 관련 문서를 찾아 답변 생성
4. 참조된 문서 확인 가능

### 3. 문서 검색
1. "문서 검색" 탭으로 이동
2. 검색어 입력 (예: "납품 기한")
3. 유사도 점수와 함께 관련 문서 확인

## API 문서

### 주요 엔드포인트

#### 문서 업로드
```bash
POST /v1/documents
Content-Type: multipart/form-data

curl -X POST http://localhost:8000/v1/documents \
  -F "file=@document.pdf"
```

#### 문서 검색
```bash
GET /v1/search?q={query}&top_k={number}

curl "http://localhost:8000/v1/search?q=계약조건&top_k=3"
```

#### RAG 답변 생성
```bash
POST /v1/rag/answer?q={query}

curl -X POST "http://localhost:8000/v1/rag/answer?q=주요 내용 요약"
```

#### 시스템 상태
```bash
GET /v1/health

curl http://localhost:8000/v1/health
```

전체 API 문서는 http://localhost:8000/docs 에서 확인 가능합니다.

## 환경 설정

### 주요 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `QDRANT_HOST` | Qdrant 서버 주소 | `qdrant` |
| `QDRANT_PORT` | Qdrant 포트 | `6333` |
| `OLLAMA_HOST` | Ollama 서버 주소 | `http://172.16.15.112:11434` |
| `OLLAMA_MODEL` | 사용할 LLM 모델 | `llama3:8b-instruct` |
| `CELERY_BROKER_URL` | Celery 브로커 URL | `redis://redis:6379/0` |

### OCR 설정

Azure Vision 사용 시:
```bash
AZURE_AI_KEY=your-azure-key
AZURE_AI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
```

## 문제 해결

### Docker 관련

**문제**: `Dockerfile not found` 오류
```bash
# Dockerfile이 루트 디렉토리에 있는지 확인
ls -la Dockerfile
```

**문제**: 포트 충돌
```bash
# 사용 중인 포트 확인
lsof -i:8000
lsof -i:8501
lsof -i:6333
```

### 연결 오류

**문제**: Ollama 연결 실패
```bash
# Ollama 서버 상태 확인
curl http://172.16.15.112:11434/api/tags
```

**문제**: Qdrant 연결 실패
```bash
# Qdrant 상태 확인
curl http://localhost:6333/health
```

### 성능 문제

**문제**: 느린 임베딩 생성
- GPU 사용 확인
- 배치 크기 조정 (`embedding/embedder.py`)

**문제**: 메모리 부족
- Docker 메모리 제한 증가
- 청크 크기 축소

## 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 문의

- 프로젝트 관리자: [your-email@example.com]
- 프로젝트 링크: [https://github.com/your-org/gtrag]

---

Made with ❤️ by GTOne Team