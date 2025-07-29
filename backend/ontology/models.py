"""
Ontology API 모델들 - FastAPI용 Pydantic 모델 정의
extractor.py의 dataclass들을 API 친화적으로 변환
"""
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, validator
from pydantic.config import ConfigDict


# ────────────────────── 기본 열거형 ──────────────────────

class KeywordCategory(str, Enum):
    """키워드 카테고리"""
    TECHNICAL = "technical"
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    GENERAL = "general"
    STATISTICAL = "statistical"


class DocumentType(str, Enum):
    """문서 유형"""
    CONTRACT = "contract"
    REPORT = "report"
    MANUAL = "manual"
    LEGAL = "legal"
    ACADEMIC = "academic"
    PROCEDURE = "procedure"
    GENERAL = "general"


class Domain(str, Enum):
    """도메인 분류"""
    TECHNOLOGY = "technology"
    FINANCE = "finance"
    LEGAL = "legal"
    MEDICAL = "medical"
    BUSINESS = "business"
    ACADEMIC = "academic"
    GENERAL = "general"


class Language(str, Enum):
    """언어"""
    KOREAN = "korean"
    ENGLISH = "english"
    MIXED = "mixed"
    UNKNOWN = "unknown"


# ────────────────────── 핵심 데이터 모델 ──────────────────────

class KeywordInfoModel(BaseModel):
    """키워드 정보 모델"""
    model_config = ConfigDict(from_attributes=True)

    term: str = Field(..., description="키워드 용어")
    score: float = Field(..., ge=0.0, le=1.0, description="중요도 점수")
    frequency: int = Field(..., ge=1, description="문서 내 출현 빈도")
    category: KeywordCategory = Field(..., description="키워드 카테고리")
    positions: List[int] = Field(default_factory=list, description="문서 내 위치 (최대 5개)")
    description: str = Field(default="", description="키워드 설명")  # 🔍 추가

    @validator('positions')
    def validate_positions(cls, v):
        if len(v) > 5:
            return v[:5]  # 최대 5개로 제한
        return v


class EntityInfoModel(BaseModel):
    """개체명 정보 모델"""
    model_config = ConfigDict(from_attributes=True)

    text: str = Field(..., description="개체명 텍스트")
    label: str = Field(..., description="개체명 라벨 (PERSON, ORG, GPE 등)")
    start: int = Field(..., ge=0, description="시작 위치")
    end: int = Field(..., ge=0, description="종료 위치")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="신뢰도")

    @validator('end')
    def validate_end_position(cls, v, values):
        if 'start' in values and v <= values['start']:
            raise ValueError('end position must be greater than start position')
        return v


class TextStatisticsModel(BaseModel):
    """텍스트 통계 모델"""
    model_config = ConfigDict(from_attributes=True)

    total_length: int = Field(..., ge=0, description="총 문자 수")
    lines: int = Field(..., ge=0, description="줄 수")
    words: int = Field(..., ge=0, description="단어 수")
    sentences: int = Field(..., ge=0, description="문장 수")
    korean_chars: int = Field(..., ge=0, description="한글 문자 수")
    english_chars: int = Field(..., ge=0, description="영문 문자 수")
    numbers: int = Field(..., ge=0, description="숫자 개수")
    avg_word_length: float = Field(..., ge=0, description="평균 단어 길이")
    avg_sentence_length: float = Field(..., ge=0, description="평균 문장 길이")


class StructureInfoModel(BaseModel):
    """문서 구조 정보 모델"""
    model_config = ConfigDict(from_attributes=True)

    total_lines: int = Field(..., ge=0, description="총 줄 수")
    empty_lines: int = Field(..., ge=0, description="빈 줄 수")
    potential_headers: int = Field(..., ge=0, description="제목 가능 줄 수")
    list_items: int = Field(..., ge=0, description="목록 항목 수")
    has_numbered_sections: bool = Field(default=False, description="번호 섹션 여부")
    has_bullet_points: bool = Field(default=False, description="불릿 포인트 여부")


class DocumentMetadataModel(BaseModel):
    """문서 메타데이터 모델"""
    model_config = ConfigDict(from_attributes=True)

    language: Language = Field(..., description="문서 언어")
    document_type: DocumentType = Field(..., description="문서 유형")
    estimated_domain: Domain = Field(..., description="추정 도메인")
    key_entities: List[EntityInfoModel] = Field(default_factory=list, description="주요 개체명")
    text_statistics: TextStatisticsModel = Field(..., description="텍스트 통계")
    structure_info: StructureInfoModel = Field(..., description="문서 구조 정보")


class SemanticClusterModel(BaseModel):
    """의미적 클러스터 모델"""
    model_config = ConfigDict(from_attributes=True)

    cluster_id: int = Field(..., ge=0, description="클러스터 ID")
    size: int = Field(..., ge=1, description="클러스터 크기")
    representative_chunk: str = Field(..., description="대표 청크")
    avg_similarity: float = Field(..., ge=0.0, le=1.0, description="평균 유사도")
    chunk_indices: List[int] = Field(default_factory=list, description="포함된 청크 인덱스")


class ContextInfoModel(BaseModel):
    """컨텍스트 정보 모델"""
    model_config = ConfigDict(from_attributes=True)

    main_topics: List[str] = Field(default_factory=list, description="주요 주제")
    semantic_clusters: List[SemanticClusterModel] = Field(default_factory=list, description="의미적 클러스터")
    related_concepts: List[str] = Field(default_factory=list, description="관련 개념")
    domain_indicators: List[str] = Field(default_factory=list, description="도메인 지시어")


class ProcessingStatsModel(BaseModel):
    """처리 통계 모델"""
    model_config = ConfigDict(from_attributes=True)

    total_time: float = Field(..., ge=0, description="총 처리 시간(초)")
    keywords_time: float = Field(..., ge=0, description="키워드 추출 시간(초)")
    metadata_time: float = Field(..., ge=0, description="메타데이터 추출 시간(초)")
    context_time: float = Field(..., ge=0, description="컨텍스트 추출 시간(초)")
    keywords_count: int = Field(..., ge=0, description="추출된 키워드 수")
    entities_count: int = Field(..., ge=0, description="추출된 개체명 수")
    topics_count: int = Field(..., ge=0, description="추출된 주제 수")


class OntologyResultModel(BaseModel):
    """온톨로지 추출 결과 모델"""
    model_config = ConfigDict(from_attributes=True)

    doc_id: str = Field(..., description="문서 ID")
    source: str = Field(..., description="원본 파일명")
    keywords: List[KeywordInfoModel] = Field(default_factory=list, description="추출된 키워드")
    metadata: DocumentMetadataModel = Field(..., description="문서 메타데이터")
    context: ContextInfoModel = Field(..., description="문서 컨텍스트")
    extracted_at: datetime = Field(..., description="추출 시각")
    processing_stats: ProcessingStatsModel = Field(..., description="처리 통계")


# ────────────────────── API 요청 모델 ──────────────────────

class KeywordSearchRequest(BaseModel):
    """키워드 검색 요청"""
    keyword: str = Field(..., min_length=1, max_length=100, description="검색할 키워드")
    limit: int = Field(default=10, ge=1, le=100, description="결과 수 제한")
    min_score: float = Field(default=0.7, ge=0.0, le=1.0, description="최소 유사도 점수")
    category: Optional[KeywordCategory] = Field(default=None, description="키워드 카테고리 필터")
    domain: Optional[Domain] = Field(default=None, description="도메인 필터")


class DomainSearchRequest(BaseModel):
    """도메인별 검색 요청"""
    domain: Domain = Field(..., description="검색할 도메인")
    limit: int = Field(default=20, ge=1, le=100, description="결과 수 제한")
    document_type: Optional[DocumentType] = Field(default=None, description="문서 유형 필터")
    language: Optional[Language] = Field(default=None, description="언어 필터")


class SimilarDocumentsRequest(BaseModel):
    """유사 문서 검색 요청"""
    doc_id: str = Field(..., description="기준 문서 ID")
    limit: int = Field(default=5, ge=1, le=20, description="결과 수 제한")
    min_similarity: float = Field(default=0.6, ge=0.0, le=1.0, description="최소 유사도")
    same_domain_only: bool = Field(default=False, description="동일 도메인만 검색")


class TopKeywordsRequest(BaseModel):
    """상위 키워드 조회 요청"""
    limit: int = Field(default=50, ge=1, le=200, description="결과 수 제한")
    category: Optional[KeywordCategory] = Field(default=None, description="카테고리 필터")
    domain: Optional[Domain] = Field(default=None, description="도메인 필터")
    min_doc_count: int = Field(default=1, ge=1, description="최소 문서 출현 수")
    sort_by: str = Field(default="document_count", pattern="^(document_count|total_frequency|avg_score)$",
                        description="정렬 기준")


# ────────────────────── API 응답 모델 ──────────────────────

class KeywordSearchResult(BaseModel):
    """키워드 검색 결과"""
    keyword: str = Field(..., description="찾은 키워드")
    score: float = Field(..., description="유사도 점수")
    doc_id: str = Field(..., description="문서 ID")
    source: str = Field(..., description="원본 파일명")
    category: KeywordCategory = Field(..., description="키워드 카테고리")
    document_type: DocumentType = Field(..., description="문서 유형")
    estimated_domain: Domain = Field(..., description="추정 도메인")


class DocumentSummary(BaseModel):
    """문서 요약 정보"""
    doc_id: str = Field(..., description="문서 ID")
    source: str = Field(..., description="원본 파일명")
    document_type: DocumentType = Field(..., description="문서 유형")
    estimated_domain: Domain = Field(..., description="추정 도메인")
    language: Language = Field(..., description="언어")
    keyword_count: int = Field(..., description="키워드 수")
    entity_count: int = Field(..., description="개체명 수")
    top_keywords: List[str] = Field(default_factory=list, description="상위 키워드")
    main_topics: List[str] = Field(default_factory=list, description="주요 주제")
    extracted_at: datetime = Field(..., description="추출 시각")


class SimilarDocumentResult(BaseModel):
    """유사 문서 검색 결과"""
    doc_id: str = Field(..., description="문서 ID")
    source: str = Field(..., description="원본 파일명")
    similarity_score: float = Field(..., description="유사도 점수")
    document_type: DocumentType = Field(..., description="문서 유형")
    estimated_domain: Domain = Field(..., description="추정 도메인")
    top_keywords: List[str] = Field(default_factory=list, description="상위 키워드")
    main_topics: List[str] = Field(default_factory=list, description="주요 주제")


class TopKeywordResult(BaseModel):
    """상위 키워드 결과"""
    keyword: str = Field(..., description="키워드")
    total_frequency: int = Field(..., description="총 출현 빈도")
    avg_score: float = Field(..., description="평균 중요도 점수")
    document_count: int = Field(..., description="출현 문서 수")
    categories: List[KeywordCategory] = Field(default_factory=list, description="카테고리들")
    domains: List[Domain] = Field(default_factory=list, description="도메인들")
    sample_documents: List[str] = Field(default_factory=list, description="샘플 문서들")


class OntologyStatistics(BaseModel):
    """온톨로지 통계"""
    total_documents: int = Field(..., description="총 문서 수")
    total_keywords: int = Field(..., description="총 키워드 수")
    domain_distribution: Dict[str, int] = Field(default_factory=dict, description="도메인별 분포")
    document_type_distribution: Dict[str, int] = Field(default_factory=dict, description="문서 유형별 분포")
    language_distribution: Dict[str, int] = Field(default_factory=dict, description="언어별 분포")
    keyword_category_distribution: Dict[str, int] = Field(default_factory=dict, description="키워드 카테고리별 분포")
    avg_keywords_per_doc: float = Field(..., description="문서당 평균 키워드 수")


# ────────────────────── 배치 처리 모델 ──────────────────────

class BatchExtractionRequest(BaseModel):
    """배치 추출 요청"""
    doc_ids: List[str] = Field(..., min_items=1, max_items=50, description="문서 ID 리스트")
    force_reextract: bool = Field(default=False, description="기존 결과 무시하고 재추출")


class BatchExtractionResult(BaseModel):
    """배치 추출 결과"""
    total_requested: int = Field(..., description="요청된 문서 수")
    successful: int = Field(..., description="성공한 문서 수")
    failed: int = Field(..., description="실패한 문서 수")
    skipped: int = Field(..., description="건너뛴 문서 수")
    processing_time: float = Field(..., description="총 처리 시간(초)")
    failed_doc_ids: List[str] = Field(default_factory=list, description="실패한 문서 ID들")


# ────────────────────── 설정 모델 ──────────────────────

class ExtractionConfig(BaseModel):
    """추출 설정"""
    max_keywords: int = Field(default=20, ge=5, le=100, description="최대 키워드 수")
    keyword_score_threshold: float = Field(default=0.1, ge=0.0, le=1.0, description="키워드 점수 임계값")
    use_keybert: bool = Field(default=True, description="KeyBERT 사용 여부")
    use_spacy: bool = Field(default=True, description="spaCy 사용 여부")
    chunk_size: int = Field(default=300, ge=100, le=1000, description="청크 크기")
    max_topics: int = Field(default=5, ge=3, le=10, description="최대 주제 수")


class SystemHealthModel(BaseModel):
    """시스템 상태 모델"""
    ontology_collections_status: Dict[str, bool] = Field(default_factory=dict, description="컬렉션 상태")
    embedding_model_status: bool = Field(..., description="임베딩 모델 상태")
    keybert_available: bool = Field(..., description="KeyBERT 사용 가능 여부")
    spacy_available: bool = Field(..., description="spaCy 사용 가능 여부")
    total_documents: int = Field(..., description="총 온톨로지 문서 수")
    total_keywords: int = Field(..., description="총 키워드 수")
    last_extraction: Optional[datetime] = Field(default=None, description="마지막 추출 시간")


# ────────────────────── 에러 모델 ──────────────────────

class OntologyError(BaseModel):
    """온톨로지 오류 모델"""
    error_code: str = Field(..., description="오류 코드")
    error_message: str = Field(..., description="오류 메시지")
    error_details: Optional[Dict[str, Any]] = Field(default=None, description="오류 상세 정보")
    timestamp: datetime = Field(default_factory=datetime.now, description="오류 발생 시간")


# ────────────────────── 성공 응답 모델 ──────────────────────

class SuccessResponse(BaseModel):
    """성공 응답"""
    success: bool = Field(default=True, description="성공 여부")
    message: str = Field(..., description="성공 메시지")
    data: Optional[Any] = Field(default=None, description="응답 데이터")


class PaginatedResponse(BaseModel):
    """페이지네이션 응답"""
    items: List[Any] = Field(..., description="결과 아이템들")
    total: int = Field(..., description="총 결과 수")
    page: int = Field(..., description="현재 페이지")
    per_page: int = Field(..., description="페이지당 아이템 수")
    has_next: bool = Field(..., description="다음 페이지 존재 여부")
    has_prev: bool = Field(..., description="이전 페이지 존재 여부")


# ────────────────────── 유틸리티 함수 ──────────────────────

def convert_ontology_result_to_model(result) -> OntologyResultModel:
    """extractor의 OntologyResult를 Pydantic 모델로 변환"""
    from .extractor import OntologyResult

    if isinstance(result, OntologyResult):
        return OntologyResultModel(
            doc_id=result.doc_id,
            source=result.source,
            keywords=[
                KeywordInfoModel(
                    term=kw.term,
                    score=kw.score,
                    frequency=kw.frequency,
                    category=kw.category,
                    positions=kw.positions
                ) for kw in result.keywords
            ],
            metadata=DocumentMetadataModel(
                language=result.metadata.language,
                document_type=result.metadata.document_type,
                estimated_domain=result.metadata.estimated_domain,
                key_entities=[
                    EntityInfoModel(
                        text=ent.text,
                        label=ent.label,
                        start=ent.start,
                        end=ent.end,
                        confidence=ent.confidence
                    ) for ent in result.metadata.key_entities
                ],
                text_statistics=TextStatisticsModel(**result.metadata.text_statistics),
                structure_info=StructureInfoModel(**result.metadata.structure_info)
            ),
            context=ContextInfoModel(
                main_topics=result.context.main_topics,
                semantic_clusters=[
                    SemanticClusterModel(**cluster) for cluster in result.context.semantic_clusters
                ],
                related_concepts=result.context.related_concepts,
                domain_indicators=result.context.domain_indicators
            ),
            extracted_at=result.extracted_at,
            processing_stats=ProcessingStatsModel(**result.processing_stats)
        )

    raise ValueError("Invalid result type for conversion")


# 타입 별칭
OntologyData = Union[OntologyResultModel, DocumentSummary]
SearchResults = List[Union[KeywordSearchResult, SimilarDocumentResult]]