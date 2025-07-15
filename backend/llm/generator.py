"""
LLM 생성 모듈: Ollama를 사용한 텍스트 생성
"""
import os
import requests
import logging
from typing import List, Dict, Optional

# 로깅 설정
logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://172.16.15.112:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:27b")


def generate_answer(query: str, contexts: List[str], model: str = None, system_prompt: str = None) -> str:
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

    # 🔍 디버그 로그 1: 입력 데이터 확인
    logger.info(f"=== OLLAMA GENERATION DEBUG ===")
    logger.info(f"Query: '{query}'")
    logger.info(f"Model: {model}")
    logger.info(f"Host: {OLLAMA_HOST}")
    logger.info(f"Context count: {len(contexts)}")

    # 컨텍스트 상세 로그
    for i, ctx in enumerate(contexts):
        preview = ctx[:100] + "..." if len(ctx) > 100 else ctx
        logger.info(f"  Context {i + 1}: {len(ctx)} chars - '{preview}'")

    if not contexts:
        logger.warning("No contexts provided!")
        return "죄송합니다. 참고할 문서가 없습니다."

    # 프롬프트 구성
    context_text = "\n---\n".join(contexts)

    # 컨텍스트 길이 제한 (Ollama 토큰 제한 고려)
    max_context_length = 3000  # 약 4000토큰 제한
    if len(context_text) > max_context_length:
        context_text = context_text[:max_context_length] + "\n...(내용 생략)"
        logger.info(f"Context truncated to {max_context_length} characters")

    # 🔧 개선된 프롬프트 (한국어 특화)
    if system_prompt:
        prompt = f"""{system_prompt}

참고 문서:
{context_text}

질문: {query}

답변: """
    else:
        prompt = f"""당신은 한국어 문서 분석 전문가입니다. 주어진 문서의 내용만을 바탕으로 질문에 정확하게 답변해주세요.

참고 문서:
{context_text}

질문: {query}

답변을 작성할 때 다음 규칙을 따라주세요:
1. 문서에 명시된 내용만 사용하세요
2. 추측하거나 외부 지식을 사용하지 마세요
3. 한국어로 자연스럽게 답변해주세요
4. 구체적인 정보가 있다면 정확히 인용해주세요

답변:"""

    # 🔍 디버그 로그 2: 프롬프트 확인
    logger.info(f"Prompt: {prompt}")
    logger.info(f"Prompt length: {len(prompt)} characters")
    logger.info(f"Prompt preview: {prompt[:200]}...")

    # Ollama API 호출
    try:
        # 🔍 디버그 로그 3: API 요청 데이터
        request_data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "num_predict": 500,  # max_tokens 대신 num_predict 사용
                "stop": ["\n\n질문:", "\n\n참고 문서:"]  # 중지 토큰 추가
            }
        }

        logger.info(f"Ollama request: {OLLAMA_HOST}/api/generate")
        logger.info(f"Request options: {request_data['options']}")

        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json=request_data,
            timeout=300  # 타임아웃 늘림
        )

        # 🔍 디버그 로그 4: API 응답 상세
        logger.info(f"Ollama response status: {response.status_code}")
        logger.info(f"Ollama response headers: {dict(response.headers)}")

        if response.status_code == 200:
            response_data = response.json()
            logger.info(f"Ollama response keys: {list(response_data.keys())}")

            generated_text = response_data.get("response", "")
            logger.info(f"Generated text length: {len(generated_text)}")
            logger.info(f"Generated text preview: {generated_text[:200]}...")

            # 빈 응답 확인
            if not generated_text.strip():
                logger.warning("Ollama returned empty response!")
                return "죄송합니다. AI가 빈 응답을 반환했습니다. 다른 질문을 시도해보세요."

            # 응답 후처리
            cleaned_response = generated_text.strip()

            # 불필요한 부분 제거
            if "답변:" in cleaned_response:
                cleaned_response = cleaned_response.split("답변:")[-1].strip()

            logger.info(f"Final answer: {cleaned_response[:100]}...")
            return cleaned_response

        else:
            # 🔍 디버그 로그 5: 오류 응답 상세
            error_text = response.text
            logger.error(f"Ollama error response: {error_text}")
            return f"오류: Ollama 서버 응답 실패 (상태코드: {response.status_code}) - {error_text[:200]}"

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Ollama connection error: {e}")
        return f"오류: Ollama 서버 ({OLLAMA_HOST})에 연결할 수 없습니다. - {str(e)}"
    except requests.exceptions.Timeout as e:
        logger.error(f"Ollama timeout error: {e}")
        return f"오류: Ollama 서버 응답 시간 초과 - {str(e)}"
    except Exception as e:
        logger.error(f"Ollama unexpected error: {e}")
        return f"오류: 예상치 못한 오류 발생 - {str(e)}"


def check_ollama_connection() -> Dict[str, any]:
    """Ollama 서버 연결 상태 확인 (디버그 강화)"""
    try:
        logger.info(f"Checking Ollama connection: {OLLAMA_HOST}")

        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        logger.info(f"Ollama tags response: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            model_names = [m.get("name", "unknown") for m in models]

            logger.info(f"Available models: {model_names}")

            # 기본 모델 확인
            default_model_available = OLLAMA_MODEL in model_names
            logger.info(f"Default model '{OLLAMA_MODEL}' available: {default_model_available}")

            return {
                "status": "connected",
                "host": OLLAMA_HOST,
                "models": model_names,
                "total_models": len(model_names),
                "default_model_available": default_model_available
            }
    except Exception as e:
        logger.error(f"Ollama connection check failed: {e}")

    return {
        "status": "disconnected",
        "host": OLLAMA_HOST,
        "error": "Cannot connect to Ollama server"
    }


# 🔍 간단한 테스트 함수 추가
def test_ollama_simple():
    """Ollama 간단 테스트"""
    test_query = "안녕하세요"
    test_contexts = ["테스트 문서입니다."]

    logger.info("=== OLLAMA SIMPLE TEST ===")
    result = generate_answer(test_query, test_contexts)
    logger.info(f"Test result: {result}")
    return result
