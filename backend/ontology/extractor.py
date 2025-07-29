"""
Ontology 추출 엔진 - 저비용 고효율 버전
KeyBERT + spaCy + 기존 임베딩 모델 활용
"""
import re
import logging
from typing import Dict, List, Tuple, Optional, Any
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np

# 기존 시스템 임포트
from backend.embedding.embedder import get_model, embed_texts

logger = logging.getLogger(__name__)

# ────────────────────── 데이터 모델 ──────────────────────

@dataclass
class KeywordInfo:
    term: str
    score: float
    frequency: int
    category: str  # 'technical', ...
    positions: List[int]
    description: str = ""  # 🔍 새 필드 추가


@dataclass
class EntityInfo:
    """개체 정보"""
    text: str
    label: str  # PERSON, ORG, GPE, DATE, MONEY, etc.
    start: int
    end: int
    confidence: float


@dataclass
class DocumentMetadata:
    """문서 메타데이터"""
    language: str
    document_type: str
    estimated_domain: str
    key_entities: List[EntityInfo]
    text_statistics: Dict[str, Any]
    structure_info: Dict[str, Any]


@dataclass
class ContextInfo:
    """문서 컨텍스트"""
    main_topics: List[str]
    semantic_clusters: List[Dict[str, Any]]
    related_concepts: List[str]
    domain_indicators: List[str]


@dataclass
class OntologyResult:
    """온톨로지 추출 결과"""
    doc_id: str
    source: str
    keywords: List[KeywordInfo]
    metadata: DocumentMetadata
    context: ContextInfo
    extracted_at: datetime
    processing_stats: Dict[str, float]


# ────────────────────── 키워드 추출기 ──────────────────────

class KeywordExtractor:
    """KeyBERT 기반 키워드 추출"""

    def __init__(self):
        self.model = None
        self._setup_keybert()

    def _setup_keybert(self):
        """KeyBERT 설정"""
        try:
            from keybert import KeyBERT
            # 기존 임베딩 모델 재사용
            embedding_model = get_model()
            self.model = KeyBERT(model=embedding_model)
            logger.info("KeyBERT initialized with existing embedding model")
        except ImportError:
            logger.warning("KeyBERT not available, falling back to TF-IDF")
            self.model = None

    def extract_keywords(self, text: str, existing_keywords: List[str] = None, top_k: int = 20) -> List[KeywordInfo]:
        existing_keywords = existing_keywords or []

        if not text or len(text.strip()) < 10:
            return []

        keywords = []
        if self.model:
            keywords.extend(self._extract_with_keybert(text, top_k))
        else:
            keywords.extend(self._extract_with_tfidf(text, top_k))

        keywords.extend(self._extract_statistical(text, top_k // 2))

        return self._deduplicate_keywords(keywords, top_k)


    def _extract_with_keybert(self, text: str, top_k: int) -> List[KeywordInfo]:
        """KeyBERT로 키워드 추출"""
        try:
            # KeyBERT 최신 API 호환성 확인 및 다양한 n-gram 조합 추출
            kwargs_base = {
                'docs': text,
                'keyphrase_ngram_range': (1, 1),
                'stop_words': 'english'
            }

            # KeyBERT 버전별 파라미터 호환성 처리
            try:
                # 최신 KeyBERT: top_k 파라미터 사용
                keywords_1gram = self.model.extract_keywords(**kwargs_base, top_k=top_k//2)
            except TypeError:
                try:
                    # 구버전 KeyBERT: top_k 대신 다른 파라미터 사용
                    keywords_1gram = self.model.extract_keywords(**kwargs_base)[:top_k//2]
                except Exception:
                    # 기본 추출
                    keywords_1gram = self.model.extract_keywords(text)[:top_k//2]

            try:
                kwargs_base['keyphrase_ngram_range'] = (2, 2)
                keywords_2gram = self.model.extract_keywords(**kwargs_base, top_k=top_k//3)
            except TypeError:
                try:
                    keywords_2gram = self.model.extract_keywords(**kwargs_base)[:top_k//3]
                except Exception:
                    keywords_2gram = self.model.extract_keywords(text, keyphrase_ngram_range=(2, 2))[:top_k//3]

            try:
                kwargs_base['keyphrase_ngram_range'] = (3, 3)
                keywords_3gram = self.model.extract_keywords(**kwargs_base, top_k=top_k//6)
            except TypeError:
                try:
                    keywords_3gram = self.model.extract_keywords(**kwargs_base)[:top_k//6]
                except Exception:
                    keywords_3gram = self.model.extract_keywords(text, keyphrase_ngram_range=(3, 3))[:top_k//6]

            results = []
            for keyword, score in keywords_1gram + keywords_2gram + keywords_3gram:
                # 키워드 위치 찾기
                positions = [m.start() for m in re.finditer(re.escape(keyword.lower()), text.lower())]
                frequency = len(positions)

                if frequency > 0:
                    results.append(KeywordInfo(
                        term=keyword,
                        score=float(score),
                        frequency=frequency,
                        category=self._classify_keyword(keyword),
                        positions=positions[:5],
                        description=self._generate_description(keyword, text)
                    ))

            return results

        except Exception as e:
            logger.warning(f"KeyBERT extraction failed: {e}")
            return []

    def _extract_with_tfidf(self, text: str, top_k: int) -> List[KeywordInfo]:
        """TF-IDF 폴백 추출"""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

            # 한국어 불용어 추가
            korean_stop_words = set(['이', '그', '저', '것', '수', '등', '및', '또는', '그리고', '하지만', '그러나'])
            stop_words = list(ENGLISH_STOP_WORDS) + list(korean_stop_words)

            # 문장 단위로 분할
            sentences = re.split(r'[.!?]\s+', text)
            if len(sentences) < 2:
                sentences = [text]

            vectorizer = TfidfVectorizer(
                max_features=top_k * 2,
                stop_words=stop_words,
                ngram_range=(1, 3),
                min_df=1,
                max_df=0.95
            )

            tfidf_matrix = vectorizer.fit_transform(sentences)
            feature_names = vectorizer.get_feature_names_out()

            # 평균 TF-IDF 스코어 계산
            mean_scores = np.mean(tfidf_matrix.toarray(), axis=0)

            results = []
            for idx, score in enumerate(mean_scores):
                if score > 0.1:  # 임계값
                    keyword = feature_names[idx]
                    positions = [m.start() for m in re.finditer(re.escape(keyword.lower()), text.lower())]
                    frequency = len(positions)

                    if frequency > 0:
                        results.append(KeywordInfo(
                            term=keyword,
                            score=float(score),
                            frequency=frequency,
                            category=self._classify_keyword(keyword),
                            positions=positions[:5],
                            description=self._generate_description(keyword, text)
                        ))

            return sorted(results, key=lambda x: x.score, reverse=True)[:top_k]

        except Exception as e:
            logger.warning(f"TF-IDF extraction failed: {e}")
            return []

    def _extract_statistical(self, text: str, top_k: int) -> List[KeywordInfo]:
        """통계 기반 키워드 추출"""
        # 단어 빈도 기반
        words = re.findall(r'\b[가-힣a-zA-Z]{2,}\b', text.lower())
        word_freq = Counter(words)

        results = []
        for word, freq in word_freq.most_common(top_k):
            if freq >= 2:  # 최소 2번 이상 등장
                positions = [m.start() for m in re.finditer(re.escape(word), text.lower())]
                results.append(KeywordInfo(
                    term=word,
                    score=freq / len(words),  # 정규화된 빈도
                    frequency=freq,
                    category=self._classify_keyword(word),
                    positions=positions[:5],
                    description=self._generate_description(word, text)
                ))

        return results

    def _classify_keyword(self, keyword: str) -> str:
        """키워드 분류"""
        keyword_lower = keyword.lower()

        # 기술 용어 패턴
        if any(pattern in keyword_lower for pattern in ['api', 'system', 'data', 'model', 'algorithm', 'tech']):
            return 'technical'

        # 조직 패턴
        if any(pattern in keyword_lower for pattern in ['company', 'corp', 'inc', '회사', '기업', '단체']):
            return 'organization'

        # 위치 패턴
        if any(pattern in keyword_lower for pattern in ['city', 'country', '시', '구', '동', '로', '국']):
            return 'location'

        # 사람 이름 패턴 (한국어)
        if re.match(r'^[가-힣]{2,4}$', keyword) and len(keyword) <= 4:
            return 'person'

        return 'general'

    def _deduplicate_keywords(self, keywords: List[KeywordInfo], top_k: int) -> List[KeywordInfo]:
        """키워드 중복 제거 및 정렬"""
        # 유사한 키워드 통합
        seen = {}
        for kw in keywords:
            key = kw.term.lower().strip()
            if key not in seen or seen[key].score < kw.score:
                seen[key] = kw

        # 스코어 순으로 정렬하여 상위 k개 반환
        return sorted(seen.values(), key=lambda x: x.score, reverse=True)[:top_k]

    def _generate_description(self, keyword: str, context: str) -> str:
        """키워드 설명 생성 - 단순 규칙 기반"""
        # 문장에서 키워드가 포함된 첫 문장을 찾아 설명으로 사용
        import re
        sentences = re.split(r'[.!?]\s+', context)
        for sent in sentences:
            if keyword.lower() in sent.lower():
                return sent.strip()[:200]  # 너무 길면 자름
        return f"'{keyword}'는 문서에서 중요한 개념입니다."


# ────────────────────── 메타데이터 추출기 ──────────────────────

class MetadataExtractor:
    """spaCy 기반 메타데이터 추출"""

    def __init__(self):
        self.nlp = None
        self._setup_spacy()

    def _setup_spacy(self):
        """spaCy 설정"""
        try:
            import spacy

            # 사용 가능한 모델 시도
            models_to_try = ['ko_core_news_sm', 'en_core_web_sm', 'xx_core_web_sm']

            for model_name in models_to_try:
                try:
                    self.nlp = spacy.load(model_name)
                    logger.info(f"Loaded spaCy model: {model_name}")
                    break
                except OSError:
                    continue

            if not self.nlp:
                logger.warning("No spaCy model available, using basic extraction")

        except ImportError:
            logger.warning("spaCy not available")

    def extract_metadata(self, text: str, source: str) -> DocumentMetadata:
        """메타데이터 추출"""
        # 기본 통계
        text_stats = self._analyze_text_statistics(text)

        # 언어 감지
        language = self._detect_language(text)

        # 문서 유형 추정
        doc_type = self._estimate_document_type(text, source)

        # 도메인 추정
        domain = self._estimate_domain(text)

        # 개체명 인식
        entities = self._extract_entities(text) if self.nlp else []

        # 구조 분석
        structure = self._analyze_structure(text)

        return DocumentMetadata(
            language=language,
            document_type=doc_type,
            estimated_domain=domain,
            key_entities=entities,
            text_statistics=text_stats,
            structure_info=structure
        )

    def _analyze_text_statistics(self, text: str) -> Dict[str, Any]:
        """텍스트 통계 분석"""
        lines = text.split('\n')
        words = re.findall(r'\b\w+\b', text)
        sentences = re.split(r'[.!?]+', text)

        korean_chars = len(re.findall(r'[가-힣]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        numbers = len(re.findall(r'\d+', text))

        return {
            'total_length': len(text),
            'lines': len([line for line in lines if line.strip()]),
            'words': len(words),
            'sentences': len([s for s in sentences if s.strip()]),
            'korean_chars': korean_chars,
            'english_chars': english_chars,
            'numbers': numbers,
            'avg_word_length': sum(len(w) for w in words) / len(words) if words else 0,
            'avg_sentence_length': len(words) / len(sentences) if sentences else 0
        }

    def _detect_language(self, text: str) -> str:
        """언어 감지"""
        korean_chars = len(re.findall(r'[가-힣]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        total_chars = korean_chars + english_chars

        if total_chars == 0:
            return 'unknown'

        korean_ratio = korean_chars / total_chars

        if korean_ratio > 0.3:
            return 'korean'
        elif korean_ratio < 0.1:
            return 'english'
        else:
            return 'mixed'

    def _estimate_document_type(self, text: str, source: str) -> str:
        """문서 유형 추정"""
        source_lower = source.lower()
        text_lower = text.lower()

        # 파일명 기반
        if any(ext in source_lower for ext in ['.pdf', '.doc']):
            if any(word in source_lower for word in ['contract', '계약', 'agreement']):
                return 'contract'
            elif any(word in source_lower for word in ['report', '보고서', 'analysis']):
                return 'report'
            elif any(word in source_lower for word in ['manual', '매뉴얼', 'guide']):
                return 'manual'

        # 내용 기반
        if any(pattern in text_lower for pattern in ['article', '조', '항', '부칙']):
            return 'legal'
        elif any(pattern in text_lower for pattern in ['abstract', '요약', 'conclusion']):
            return 'academic'
        elif any(pattern in text_lower for pattern in ['procedure', '절차', 'step']):
            return 'procedure'

        return 'general'

    def _estimate_domain(self, text: str) -> str:
        """도메인 추정"""
        text_lower = text.lower()

        domain_keywords = {
            'technology': ['api', 'system', 'software', 'algorithm', 'data', 'ai', 'ml', '인공지능'],
            'finance': ['money', 'investment', 'financial', 'budget', '예산', '투자', '금융'],
            'legal': ['law', 'regulation', 'legal', 'court', '법률', '규정', '법원'],
            'medical': ['health', 'medical', 'patient', 'treatment', '의료', '환자', '치료'],
            'business': ['business', 'management', 'strategy', 'market', '비즈니스', '경영', '전략'],
            'academic': ['research', 'study', 'analysis', 'theory', '연구', '분석', '이론']
        }

        domain_scores = {}
        for domain, keywords in domain_keywords.items():
            score = sum(text_lower.count(keyword) for keyword in keywords)
            if score > 0:
                domain_scores[domain] = score

        if domain_scores:
            return max(domain_scores, key=domain_scores.get)

        return 'general'

    def _extract_entities(self, text: str) -> List[EntityInfo]:
        """개체명 추출"""
        if not self.nlp:
            return []

        try:
            doc = self.nlp(text)
            entities = []

            for ent in doc.ents:
                entities.append(EntityInfo(
                    text=ent.text,
                    label=ent.label_,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=1.0  # spaCy는 신뢰도를 제공하지 않음
                ))

            return entities

        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return []

    def _analyze_structure(self, text: str) -> Dict[str, Any]:
        """문서 구조 분석"""
        lines = text.split('\n')

        # 제목 라인 감지 (짧고 대문자가 많은 라인)
        potential_headers = []
        for i, line in enumerate(lines):
            line = line.strip()
            if line and len(line) < 100:
                upper_ratio = sum(1 for c in line if c.isupper()) / len(line)
                if upper_ratio > 0.3:
                    potential_headers.append((i, line))

        # 목록 감지
        list_items = []
        for i, line in enumerate(lines):
            line = line.strip()
            if re.match(r'^\d+\.|\*|\-|•', line):
                list_items.append((i, line))

        return {
            'total_lines': len(lines),
            'empty_lines': len([line for line in lines if not line.strip()]),
            'potential_headers': len(potential_headers),
            'list_items': len(list_items),
            'has_numbered_sections': bool(re.search(r'\d+\.\d+', text)),
            'has_bullet_points': bool(re.search(r'[•\*\-]\s+', text))
        }


# ────────────────────── 컨텍스트 추출기 ──────────────────────

class ContextExtractor:
    """임베딩 기반 컨텍스트 추출"""

    def __init__(self):
        self.embedding_model = get_model()

    def extract_context(self, text: str, chunks: List[str] = None) -> ContextInfo:
        """컨텍스트 추출"""
        if not chunks:
            chunks = self._split_into_chunks(text)

        # 주요 토픽 추출
        main_topics = self._extract_topics(chunks)

        # 의미적 클러스터링
        semantic_clusters = self._cluster_chunks(chunks)

        # 관련 개념 추출
        related_concepts = self._extract_related_concepts(text)

        # 도메인 지시자 추출
        domain_indicators = self._extract_domain_indicators(text)

        return ContextInfo(
            main_topics=main_topics,
            semantic_clusters=semantic_clusters,
            related_concepts=related_concepts,
            domain_indicators=domain_indicators
        )

    def _split_into_chunks(self, text: str, chunk_size: int = 300) -> List[str]:
        """텍스트를 청크로 분할"""
        words = text.split()
        chunks = []

        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i + chunk_size])
            if len(chunk.strip()) > 50:  # 너무 짧은 청크 제외
                chunks.append(chunk)

        return chunks

    def _extract_topics(self, chunks: List[str], top_k: int = 5) -> List[str]:
        """주요 토픽 추출"""
        if len(chunks) < 2:
            return []

        try:
            from sklearn.cluster import KMeans
            from sklearn.feature_extraction.text import TfidfVectorizer

            # TF-IDF 벡터화
            vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(chunks)

            # 클러스터링
            n_clusters = min(top_k, len(chunks))
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(tfidf_matrix)

            # 각 클러스터의 대표 용어 추출
            feature_names = vectorizer.get_feature_names_out()
            topics = []

            for cluster_id in range(n_clusters):
                # 클러스터 중심의 상위 용어들
                center = kmeans.cluster_centers_[cluster_id]
                top_indices = center.argsort()[-3:][::-1]  # 상위 3개
                topic_terms = [feature_names[i] for i in top_indices]
                topics.append(' '.join(topic_terms))

            return topics

        except Exception as e:
            logger.warning(f"Topic extraction failed: {e}")
            return []

    def _cluster_chunks(self, chunks: List[str]) -> List[Dict[str, Any]]:
        """청크를 의미적으로 클러스터링"""
        if len(chunks) < 2:
            return []

        try:
            # 임베딩 생성
            embeddings = embed_texts(chunks, prefix="passage")

            from sklearn.cluster import KMeans
            from sklearn.metrics.pairwise import cosine_similarity

            # 클러스터링
            n_clusters = min(5, len(chunks))
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(embeddings)

            # 클러스터 정보 구성
            clusters = []
            for cluster_id in range(n_clusters):
                cluster_chunks = [chunks[i] for i, label in enumerate(cluster_labels) if label == cluster_id]
                cluster_embeddings = embeddings[cluster_labels == cluster_id]

                # 클러스터 중심과의 유사도 계산
                center = kmeans.cluster_centers_[cluster_id].reshape(1, -1)
                similarities = cosine_similarity(cluster_embeddings, center).flatten()

                # 대표 청크 선택
                representative_idx = similarities.argmax()
                representative_chunk = cluster_chunks[representative_idx]

                clusters.append({
                    'cluster_id': cluster_id,
                    'size': len(cluster_chunks),
                    'representative_chunk': representative_chunk[:200] + '...' if len(representative_chunk) > 200 else representative_chunk,
                    'avg_similarity': float(similarities.mean()),
                    'chunk_indices': [i for i, label in enumerate(cluster_labels) if label == cluster_id]
                })

            return clusters

        except Exception as e:
            logger.warning(f"Chunk clustering failed: {e}")
            return []

    def _extract_related_concepts(self, text: str) -> List[str]:
        """관련 개념 추출"""
        # 명사구 패턴 매칭
        noun_phrases = re.findall(r'[가-힣a-zA-Z]+(?:\s+[가-힣a-zA-Z]+){1,3}', text)

        # 빈도 기반 필터링
        phrase_freq = Counter(noun_phrases)
        related_concepts = [phrase for phrase, freq in phrase_freq.most_common(10) if freq >= 2]

        return related_concepts[:8]

    def _extract_domain_indicators(self, text: str) -> List[str]:
        """도메인 지시어 추출"""
        text_lower = text.lower()

        # 도메인별 지시어 패턴
        domain_patterns = {
            'technical': [r'\b\w*api\w*\b', r'\b\w*system\w*\b', r'\b\w*data\w*\b'],
            'business': [r'\b\w*business\w*\b', r'\b\w*market\w*\b', r'\b\w*strategy\w*\b'],
            'legal': [r'\b\w*law\w*\b', r'\b\w*regulation\w*\b', r'\b\w*contract\w*\b'],
            'academic': [r'\b\w*research\w*\b', r'\b\w*study\w*\b', r'\b\w*analysis\w*\b']
        }

        indicators = []
        for domain, patterns in domain_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                if matches:
                    # set을 list로 변환한 후 슬라이싱
                    unique_matches = list(set(matches))[:2]
                    indicators.extend([f"{domain}:{match}" for match in unique_matches])

        return indicators[:10]


# ────────────────────── 메인 온톨로지 추출기 ──────────────────────

class OntologyExtractor:
    """통합 온톨로지 추출기"""

    def __init__(self):
        self.keyword_extractor = KeywordExtractor()
        self.metadata_extractor = MetadataExtractor()
        self.context_extractor = ContextExtractor()

    def _merge_keywords(self, keywords_by_method: Dict[str, List[KeywordInfo]], top_k: int = 20) -> List[KeywordInfo]:
        """다중 추출기 결과를 통합"""
        merged = {}
        priority = ["keybert", "llm", "tfidf", "stat"]

        for method in priority:
            for kw in keywords_by_method.get(method, []):
                key = kw.term.lower()
                if key not in merged:
                    merged[key] = kw

        return list(merged.values())[:top_k]


    def extract_ontology(self, text: str, doc_id: str, source: str, chunks: List[str] = None,
                         keyword_methods: List[str] = ["keybert"]) -> OntologyResult:
        """전체 온톨로지 추출"""
        import time
        start_time = time.time()

        logger.info(f"Starting ontology extraction for: {source}")

        try:
            # ────────────── 키워드 추출 ──────────────
            keywords_start = time.time()

            # 1차 추출: 통계 기반 키워드 (기존 키워드 목록으로 활용)
            fallback_keywords = self.keyword_extractor._extract_statistical(text, top_k=15)
            existing_terms = [kw.term for kw in fallback_keywords]

            # 추출기별 결과
            keywords_by_method = {}

            for method in keyword_methods:
                if method == "keybert":
                    keywords_by_method["keybert"] = self.keyword_extractor.extract_keywords(
                        text, existing_keywords=existing_terms
                    )
                elif method == "llm":
                    from .extractors.llm_keyword_extractor import LLMKeywordExtractor
                    llm_extractor = LLMKeywordExtractor()
                    keywords_by_method["llm"] = llm_extractor.extract_keywords(
                        text, existing_keywords=existing_terms
                    )

            merged_keywords = self._merge_keywords(keywords_by_method, top_k=20)
            keywords_time = time.time() - keywords_start

            # ────────────── 메타데이터 추출 ──────────────
            metadata_start = time.time()
            metadata = self.metadata_extractor.extract_metadata(text, source)
            metadata_time = time.time() - metadata_start

            # ────────────── 컨텍스트 추출 ──────────────
            context_start = time.time()
            context = self.context_extractor.extract_context(text, chunks)
            context_time = time.time() - context_start

            # ────────────── 결과 구성 ──────────────
            total_time = time.time() - start_time

            processing_stats = {
                'total_time': total_time,
                'keywords_time': keywords_time,
                'metadata_time': metadata_time,
                'context_time': context_time,
                'keywords_count': len(merged_keywords),
                'entities_count': len(metadata.key_entities),
                'topics_count': len(context.main_topics)
            }

            return OntologyResult(
                doc_id=doc_id,
                source=source,
                keywords=merged_keywords,
                metadata=metadata,
                context=context,
                extracted_at=datetime.now(),
                processing_stats=processing_stats
            )

        except Exception as e:
            logger.error(f"Ontology extraction failed: {e}")
            raise

    def to_dict(self, result: OntologyResult) -> Dict[str, Any]:
        """결과를 딕셔너리로 변환"""
        return {
            'doc_id': result.doc_id,
            'source': result.source,
            'keywords': [asdict(kw) for kw in result.keywords],
            'metadata': asdict(result.metadata),
            'context': asdict(result.context),
            'extracted_at': result.extracted_at.isoformat(),
            'processing_stats': result.processing_stats
        }


# ────────────────────── 유틸리티 함수 ──────────────────────

def extract_ontology_from_chunks(chunks: List[Dict], doc_id: str, source: str) -> OntologyResult:
    """청크들로부터 온톨로지 추출"""
    # 모든 청크의 텍스트 결합
    full_text = '\n\n'.join(chunk['content'] for chunk in chunks if chunk.get('content'))
    chunk_texts = [chunk['content'] for chunk in chunks if chunk.get('content')]

    extractor = OntologyExtractor()
    return extractor.extract_ontology(full_text, doc_id, source, chunk_texts)


# 테스트용 메인 함수
if __name__ == "__main__":
    # 테스트 코드
    test_text = """
    인공지능 기반 문서 분석 시스템은 자연어 처리 기술을 활용하여 
    대용량 문서에서 의미 있는 정보를 추출합니다. 
    이 시스템은 KeyBERT와 spaCy를 사용하여 키워드와 개체명을 인식하며,
    사용자에게 정확한 검색 결과를 제공합니다.
    """

    extractor = OntologyExtractor()
    result = extractor.extract_ontology(test_text, "test-001", "test_document.txt")

    print("=== 온톨로지 추출 결과 ===")
    print(f"키워드 수: {len(result.keywords)}")
    print(f"개체 수: {len(result.metadata.key_entities)}")
    print(f"주제 수: {len(result.context.main_topics)}")

    print("\n주요 키워드:")
    for kw in result.keywords[:5]:
        print(f"  - {kw.term} (score: {kw.score:.3f}, freq: {kw.frequency})")

    print(f"\n문서 유형: {result.metadata.document_type}")
    print(f"추정 도메인: {result.metadata.estimated_domain}")
    print(f"언어: {result.metadata.language}")