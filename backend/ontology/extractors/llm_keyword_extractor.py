import logging
import json
from typing import List

from .keyword_interface import BaseKeywordExtractor
from ..extractor import KeywordInfo
from ...llm.ollama_client import get_ollama_client  # 경로는 실제 프로젝트에 맞게 조정

logger = logging.getLogger(__name__)

class LLMKeywordExtractor(BaseKeywordExtractor):
    """Ollama 기반 LLM 키워드 추출기"""

    def __init__(self, model: str = "gemma3:27b"):
        self.client = get_ollama_client()
        self.model = model

    def extract_keywords(self, text: str, existing_keywords: List[str], top_k: int = 20) -> List[KeywordInfo]:
        """LLM을 사용해 키워드 + 설명 + 카테고리를 추출"""
        prompt = self._build_prompt(text, existing_keywords, top_k)

        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                system="너는 한국어 문서 분석 전문가이자 키워드 요약기다.",
                options={"temperature": 0.3, "top_p": 0.9, "num_predict": 500},
                stream=False
            )

            raw = response.get("response", "").strip()
            logger.debug(f"LLM raw response: {raw[:300]}...")

            # JSON 파싱
            data = json.loads(raw)
            results = []
            for item in data:
                results.append(KeywordInfo(
                    term=item.get("term", "").strip(),
                    score=1.0,  # LLM은 점수 미제공
                    frequency=1,
                    category=item.get("category", "general"),
                    positions=[]  # 위치 정보 없음
                ))
            return results

        except Exception as e:
            logger.error(f"LLM 키워드 추출 실패: {e}")
            return []

    def _build_prompt(self, text: str, existing_keywords: List[str], top_k: int) -> str:
        """LLM 프롬프트 구성"""
        prefix = "다음 문서를 분석하여 중요 키워드를 추출하세요.\n"
        prefix += f"최대 {top_k}개, 각 키워드마다 설명과 카테고리를 포함해주세요.\n"
        prefix += "출력은 JSON 배열로 하세요. 형식:\n"
        prefix += """[
  { "term": "키워드", "description": "간단한 설명", "category": "technical|person|organization|location|general" },
  ...
]\n"""

        if existing_keywords:
            prefix += f"\n기존 키워드 (참고용): {', '.join(existing_keywords[:10])}\n"

        # 텍스트 길이 제한
        max_len = 3000
        if len(text) > max_len:
            text = text[:max_len] + "\n...(생략됨)"

        return prefix + f"\n문서 내용:\n{text}"
