from abc import ABC, abstractmethod
from typing import List

from ..extractor import KeywordInfo  # 기존 모델 재사용

class BaseKeywordExtractor(ABC):
    """키워드 추출기 인터페이스"""

    @abstractmethod
    def extract_keywords(self, text: str, existing_keywords: List[str], top_k: int = 20) -> List[KeywordInfo]:
        """
        키워드 추출 메서드

        Args:
            text: 원본 문서 전체 텍스트
            existing_keywords: 기존 추출된 키워드 리스트 (LLM 입력에 활용 가능)
            top_k: 최대 키워드 수

        Returns:
            KeywordInfo 리스트
        """
        pass
