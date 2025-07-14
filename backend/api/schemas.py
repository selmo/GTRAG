from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from uuid import UUID


# ---------- 공용 모델 ----------
class Chunk(BaseModel):
    chunk_id: UUID
    content: str = Field(..., description="텍스트 청크")
    score: Optional[float] = Field(None, description="검색 점수")


# ---------- 요청 / 응답 ----------
class UploadResponse(BaseModel):
    uploaded: int = Field(..., description="저장된 청크 개수")


class SearchRequest(BaseModel):
    q: str = Field(..., min_length=1, description="검색어")
    top_k: int = Field(3, ge=1, le=20, description="top‑k 갯수")
    lang: Optional[str] = Field(None, description="언어 필터 (ISO‑639‑1)")


class SearchHit(BaseModel):
    chunk_id: UUID
    content: str
    score: float


class SearchResponse(BaseModel):
    items: List[SearchHit]
