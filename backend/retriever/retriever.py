"""
벡터/하이브리드/재순위 검색 모듈 – Qdrant 의존성 주입 버전
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from qdrant_client.http import models as rest

from backend.core.qdrant import get_qdrant_client  # ← 중앙 싱글턴 사용

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────
# 내부 헬퍼
# ────────────────────────────────────────────────────────────────


def _client():
    return get_qdrant_client()


def _build_lang_filter(lang: Optional[str]) -> list[rest.FieldCondition]:
    if not lang or lang == "auto":
        return []

    if lang.lower().startswith("ko"):
        return [
            rest.FieldCondition(key="has_korean", match=rest.MatchValue(value=True))
        ]
    if lang.lower().startswith("en"):
        return [
            rest.FieldCondition(key="has_english", match=rest.MatchValue(value=True))
        ]
    return []


def _has_korean(text: str) -> bool:
    return bool(re.search(r"[가-힣]", text))


def _extract_keywords(text: str) -> List[str]:
    words = re.findall(r"\b\w+\b", text)
    return list({w for w in words if len(w) >= (1 if _has_korean(w) else 2)})


# ────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────


def search(
    qvec,
    *,
    top_k: int = 3,
    lang: str | None = None,
    filters: Dict[str, Any] | None = None,
    min_score: float = 0.3,
    qdrant=None,
):
    qdrant = qdrant or _client()

    filter_conditions: list[rest.FieldCondition] = _build_lang_filter(lang)

    if filters:
        # ex) {"file_type": "pdf"}
        for key, value in filters.items():
            filter_conditions.append(rest.FieldCondition(key=key, match=rest.MatchValue(value=value)))

    q_filter = rest.Filter(must=filter_conditions) if filter_conditions else None

    results = qdrant.search(
        collection_name="chunks",
        query_vector=qvec,
        limit=top_k * 2,
        query_filter=q_filter,
        score_threshold=min_score,
    )

    # 상위 top_k 만 반환
    return [r for r in results if r.score >= min_score][:top_k]


def hybrid_search(
    query_text: str,
    qvec,
    *,
    top_k: int = 3,
    lang: str | None = None,
    qdrant=None,
) -> List:
    vector_hits = search(qvec, top_k=top_k * 2, lang=lang, qdrant=qdrant)
    if not vector_hits:
        return []

    keywords = _extract_keywords(query_text)
    enhanced: list = []

    for hit in vector_hits:
        content = hit.payload.get("content", "")
        score = hit.score

        # 키워드 매칭 보너스
        for kw in keywords:
            if kw.lower() in content.lower():
                score += 0.05

        # 한-글 매칭 보너스
        if _has_korean(query_text) and hit.payload.get("has_korean"):
            score += 0.1

        hit.score = min(score, 1.0)
        enhanced.append(hit)

    enhanced.sort(key=lambda x: x.score, reverse=True)
    return enhanced[:top_k]


def search_with_rerank(
    query_text: str,
    qvec,
    *,
    top_k: int = 3,
    lang: str | None = None,
    qdrant=None,
):
    candidates = search(qvec, top_k=top_k * 3, lang=lang, min_score=0.15, qdrant=qdrant)
    if not candidates:
        return []

    for hit in candidates:
        content = hit.payload.get("content", "")
        hit.score = _rerank_score(query_text, content, hit.score, hit.payload)

    candidates.sort(key=lambda x: x.score, reverse=True)
    return candidates[:top_k]


# ────────────────────────────────────────────────────────────────
# 내부 - rerank
# ────────────────────────────────────────────────────────────────


def _rerank_score(query_text: str, content: str, base: float, meta: Dict) -> float:
    kw_score = sum(0.1 if kw in content else 0.05 for kw in _extract_keywords(query_text) if kw.lower() in content.lower())
    lang_bonus = 0.1 if _has_korean(query_text) and meta.get("has_korean") else 0.05 if not _has_korean(query_text) and meta.get("has_english") else 0
    length_bonus = 0.05 if 100 <= len(content) <= 1000 else 0.0
    return min(base + kw_score + lang_bonus + length_bonus, 1.0)
