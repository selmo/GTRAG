"""
LLM 생성 모듈: Ollama를 사용한 텍스트 생성
"""
import os
import requests
from typing import List, Dict, Optional

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://172.16.15.112:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:8b-instruct")


def generate_answer(query: str, contexts: List[str], model: str = None) -> str:
    """
    검색된 컨텍스트를 기반으로 답변 생성

    Args:
        query: 사용자 질문
        contexts: 검색된 관련 문서들
        model: 사용할 모델 (기본값: 환경변수의 OLLAMA_MODEL)

    Returns:
        생성된 답변
    """
    if not model:
        model = OLLAMA_MODEL

    # 프롬프트 구성
    context_text = "\n---\n".join(contexts)
    prompt = f"""다음 문서들을 참고하여 질문에 답하세요. 문서에 없는 내용은 답하지 마세요.

문서:
{context_text}

질문: {query}

답변:"""

    # Ollama API 호출
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "max_tokens": 500
                }
            },
            timeout=30
        )

        if response.status_code == 200:
            return response.json().get("response", "답변을 생성할 수 없습니다.")
        else:
            return f"오류: Ollama 서버 응답 실패 ({response.status_code})"

    except requests.exceptions.ConnectionError:
        return f"오류: Ollama 서버 ({OLLAMA_HOST})에 연결할 수 없습니다."
    except Exception as e:
        return f"오류: {str(e)}"


def check_ollama_connection() -> Dict[str, any]:
    """Ollama 서버 연결 상태 확인"""
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            return {
                "status": "connected",
                "host": OLLAMA_HOST,
                "models": [m["name"] for m in models]
            }
    except:
        pass

    return {
        "status": "disconnected",
        "host": OLLAMA_HOST,
        "error": "Cannot connect to Ollama server"
    }


def pull_model(model_name: str) -> bool:
    """Ollama 모델 다운로드"""
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/pull",
            json={"name": model_name},
            stream=True,
            timeout=600  # 10분 타임아웃
        )

        if response.status_code == 200:
            for line in response.iter_lines():
                if line:
                    print(line.decode('utf-8'))
            return True
    except Exception as e:
        print(f"Model pull failed: {e}")

    return False