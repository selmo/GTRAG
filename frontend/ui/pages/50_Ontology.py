"""
온톨로지 관리 페이지 - 키워드, 메타데이터, 컨텍스트 탐색
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# 기존 시스템 임포트
from frontend.ui.utils.client_manager import ClientManager
from frontend.ui.utils.streamlit_helpers import rerun
from frontend.ui.components.common import StatusIndicator
from frontend.ui.utils.api_utils import OntologyAPIManager, safe_api_call, display_api_response

# 페이지 설정
st.set_page_config(
    page_title="온톨로지 관리 - GTOne RAG",
    page_icon="🧠",
    layout="wide"
)

# CSS 스타일
st.markdown("""
<style>
.metric-card {
    background-color: #f8f9fa;
    padding: 1rem;
    border-radius: 8px;
    border-left: 4px solid #007acc;
    margin: 0.5rem 0;
}

.keyword-tag {
    background-color: #e3f2fd;
    color: #1976d2;
    padding: 0.2rem 0.5rem;
    border-radius: 12px;
    font-size: 0.8rem;
    margin: 0.1rem;
    display: inline-block;
}

.entity-tag {
    background-color: #f3e5f5;
    color: #7b1fa2;
    padding: 0.2rem 0.5rem;
    border-radius: 12px;
    font-size: 0.8rem;
    margin: 0.1rem;
    display: inline-block;
}

.domain-badge {
    background-color: #e8f5e8;
    color: #2e7d32;
    padding: 0.3rem 0.6rem;
    border-radius: 16px;
    font-weight: bold;
    font-size: 0.9rem;
}

.search-results {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 1rem;
    margin: 0.5rem 0;
    background-color: #fafafa;
}

.similarity-score {
    background: linear-gradient(90deg, #4caf50, #ffeb3b, #f44336);
    padding: 0.2rem 0.5rem;
    border-radius: 12px;
    color: white;
    font-weight: bold;
    font-size: 0.8rem;
}
</style>
""", unsafe_allow_html=True)


def get_ontology_statistics(client) -> Optional[Dict]:
    """온톨로지 통계 조회 - 개선된 버전"""
    try:
        response = ontology_api.get_ontology_statistics()

        if response.success:
            return response.data
        else:
            st.error(f"통계 조회 실패: {response.error_message}")
            return None

    except Exception as e:
        st.error(f"통계 조회 중 예외 발생: {e}")
        return None


def search_by_keyword(client, keyword: str, limit: int = 10) -> List[Dict]:
    """키워드 검색 - 개선된 버전"""
    try:
        response = ontology_api.search_by_keyword(keyword, limit, min_score=0.7)

        if response.success:
            # 응답이 리스트인지 확인하고 안전하게 처리
            data = response.data
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # 딕셔너리에서 리스트 추출
                return data.get("results", data.get("keywords", data.get("data", [])))
            else:
                st.warning(f"예상하지 못한 응답 형식: {type(data)}")
                return []
        else:
            st.error(f"키워드 검색 실패: {response.error_message}")
            return []

    except Exception as e:
        st.error(f"키워드 검색 중 예외 발생: {e}")
        return []


def search_by_domain(client, domain: str, limit: int = 20) -> List[Dict]:
    """도메인별 검색 - 개선된 버전"""
    try:
        response = ontology_api.search_by_domain(domain, limit)

        if response.success:
            # 응답이 리스트인지 확인하고 안전하게 처리
            data = response.data
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # 딕셔너리에서 리스트 추출
                return data.get("results", data.get("documents", data.get("data", [])))
            else:
                st.warning(f"예상하지 못한 응답 형식: {type(data)}")
                return []
        else:
            st.error(f"도메인 검색 실패: {response.error_message}")
            return []

    except Exception as e:
        st.error(f"도메인 검색 중 예외 발생: {e}")
        return []


def get_top_keywords(client, limit: int = 50, category: str = None, domain: str = None) -> List[Dict]:
    """상위 키워드 조회 - 개선된 버전"""
    try:
        response = ontology_api.get_top_keywords(limit, category, domain)

        if response.success:
            # 응답이 리스트인지 확인하고 안전하게 처리
            data = response.data
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # 딕셔너리에서 리스트 추출 (다양한 키 시도)
                for key in ["keywords", "data", "results", "items"]:
                    if key in data and isinstance(data[key], list):
                        return data[key]
                # 키를 찾지 못한 경우
                st.warning(f"키워드 데이터를 찾을 수 없습니다. 사용 가능한 키: {list(data.keys())}")
                return []
            else:
                st.warning(f"예상하지 못한 응답 형식: {type(data)}")
                return []
        else:
            st.error(f"키워드 조회 실패: {response.error_message}")
            return []

    except Exception as e:
        st.error(f"키워드 조회 중 예외 발생: {e}")
        return []


def get_document_ontology(client, doc_id: str) -> Optional[Dict]:
    """문서별 온톨로지 조회 - 개선된 버전"""
    try:
        response = ontology_api.get_document_ontology(doc_id)

        if response.success:
            return response.data
        else:
            # 404 오류는 조용히 처리 (문서가 없을 수 있음)
            if "404" not in response.error_message and "not found" not in response.error_message.lower():
                st.error(f"문서 온톨로지 조회 실패: {response.error_message}")
            return None

    except Exception as e:
        st.error(f"문서 온톨로지 조회 중 예외 발생: {e}")
        return None


def get_similar_documents(client, doc_id: str, limit: int = 5) -> List[Dict]:
    """유사 문서 검색 - 개선된 버전"""
    try:
        response = ontology_api.get_similar_documents(doc_id, limit, min_similarity=0.6)

        if response.success:
            # 응답이 리스트인지 확인하고 안전하게 처리
            data = response.data
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # 딕셔너리에서 리스트 추출
                return data.get("results", data.get("documents", data.get("data", [])))
            else:
                st.warning(f"예상하지 못한 응답 형식: {type(data)}")
                return []
        else:
            # 유사 문서가 없는 경우는 정상적인 상황
            if "not found" not in response.error_message.lower():
                st.error(f"유사 문서 검색 실패: {response.error_message}")
            return []

    except Exception as e:
        st.error(f"유사 문서 검색 중 예외 발생: {e}")
        return []


def render_statistics_dashboard(client):
    """통계 대시보드 렌더링 - 개선된 버전"""
    st.subheader("📊 온톨로지 통계 대시보드")

    # 로딩 상태와 함께 통계 조회
    with st.spinner("통계를 불러오는 중..."):
        stats = get_ontology_statistics(client)

    if not stats:
        st.warning("온톨로지 통계를 불러올 수 없습니다.")

        # 재시도 버튼 제공
        if st.button("🔄 다시 시도"):
            st.rerun()
        return

    # 전체 통계 카드 (기존 코드 유지)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("총 문서 수", stats.get("total_documents", 0))

    with col2:
        st.metric("총 키워드 수", stats.get("total_keywords", 0))

    with col3:
        avg_keywords = stats.get("avg_keywords_per_doc", 0)
        st.metric("문서당 평균 키워드", f"{avg_keywords:.1f}")

    with col4:
        total_docs = stats.get("total_documents", 0)
        coverage = (total_docs / max(total_docs, 1)) * 100 if total_docs > 0 else 0
        st.metric("온톨로지 커버리지", f"{coverage:.1f}%")

    # 차트 영역 (기존 코드 유지하되 데이터 안전성 검사 추가)
    col1, col2 = st.columns(2)

    with col1:
        domain_dist = stats.get("domain_distribution", {})
        if domain_dist and isinstance(domain_dist, dict) and len(domain_dist) > 0:
            try:
                fig_domain = px.pie(
                    values=list(domain_dist.values()),
                    names=list(domain_dist.keys()),
                    title="도메인별 문서 분포"
                )
                fig_domain.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_domain, use_container_width=True)
            except Exception as e:
                st.error(f"도메인 분포 차트 생성 실패: {e}")
        else:
            st.info("도메인 분포 데이터가 없습니다.")

    with col2:
        doc_type_dist = stats.get("document_type_distribution", {})
        if doc_type_dist and isinstance(doc_type_dist, dict) and len(doc_type_dist) > 0:
            try:
                fig_doctype = px.bar(
                    x=list(doc_type_dist.keys()),
                    y=list(doc_type_dist.values()),
                    title="문서 유형별 분포"
                )
                fig_doctype.update_layout(xaxis_title="문서 유형", yaxis_title="문서 수")
                st.plotly_chart(fig_doctype, use_container_width=True)
            except Exception as e:
                st.error(f"문서 유형 차트 생성 실패: {e}")
        else:
            st.info("문서 유형 분포 데이터가 없습니다.")

    # 키워드 카테고리 분포
    keyword_cat_dist = stats.get("keyword_category_distribution", {})
    if keyword_cat_dist and isinstance(keyword_cat_dist, dict) and len(keyword_cat_dist) > 0:
        st.subheader("키워드 카테고리별 분포")
        try:
            fig_keyword_cat = px.bar(
                x=list(keyword_cat_dist.values()),
                y=list(keyword_cat_dist.keys()),
                orientation='h',
                title="키워드 카테고리별 분포"
            )
            fig_keyword_cat.update_layout(xaxis_title="키워드 수", yaxis_title="카테고리")
            st.plotly_chart(fig_keyword_cat, use_container_width=True)
        except Exception as e:
            st.error(f"키워드 카테고리 차트 생성 실패: {e}")


def render_keyword_explorer(client):
    """키워드 탐색기 렌더링 - DuplicateWidgetID 오류 수정"""
    st.subheader("🔍 키워드 탐색기")

    # 검색 인터페이스
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        search_term = st.text_input("키워드 검색", placeholder="검색할 키워드를 입력하세요...")

    with col2:
        category_filter = st.selectbox(
            "카테고리 필터",
            ["전체", "technical", "person", "organization", "location", "general"]
        )

    with col3:
        limit = st.number_input("결과 수", min_value=5, max_value=50, value=10)

    # 검색 실행
    if search_term and search_term.strip():
        st.write(f"**'{search_term}' 검색 결과:**")

        results = search_by_keyword(client, search_term.strip(), limit)

        if results and len(results) > 0:
            for idx, result in enumerate(results):
                if not isinstance(result, dict):
                    st.warning(f"결과 {idx + 1}: 데이터 형식 오류")
                    continue

                with st.container():
                    st.markdown(f"""
                    <div class="search-results">
                        <h4>📄 {result.get('source', 'Unknown')}</h4>
                        <p><strong>키워드:</strong> <span class="keyword-tag">{result.get('keyword', '')}</span></p>
                        <p><strong>유사도:</strong> {result.get('score', 0):.3f}</p>
                        <p><strong>카테고리:</strong> {result.get('category', 'unknown')}</p>
                        <p><strong>도메인:</strong> <span class="domain-badge">{result.get('estimated_domain', 'unknown')}</span></p>
                        <p><strong>문서 유형:</strong> {result.get('document_type', 'unknown')}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    # 🔧 수정: 고유한 키 생성
                    doc_id = result.get('doc_id', f'unknown_{idx}')
                    unique_key = f"keyword_detail_{search_term}_{idx}_{doc_id}"

                    if st.button("상세 보기", key=unique_key):
                        if doc_id and doc_id != f'unknown_{idx}':
                            st.session_state.selected_doc_id = doc_id
                            st.session_state.page_mode = 'document_detail'
                            rerun()
                        else:
                            st.warning("문서 ID를 찾을 수 없습니다.")
        else:
            st.info("검색 결과가 없습니다.")

            # 검색 제안 제공
            if len(search_term.strip()) < 2:
                st.caption("💡 2글자 이상 입력해보세요.")
            elif search_term.strip().isdigit():
                st.caption("💡 숫자만으로는 검색하기 어려울 수 있습니다. 의미있는 단어를 추가해보세요.")

    # 상위 키워드 랭킹
    st.subheader("🏆 인기 키워드 랭킹")

    col1, col2 = st.columns(2)
    with col1:
        domain_filter = st.selectbox(
            "도메인 필터 (랭킹)",
            ["전체", "technology", "finance", "legal", "medical", "business", "academic"]
        )

    with col2:
        ranking_limit = st.number_input("랭킹 수", min_value=10, max_value=100, value=20)

    if st.button("키워드 랭킹 조회"):
        domain_param = None if domain_filter == "전체" else domain_filter
        top_keywords = get_top_keywords(client, ranking_limit, domain=domain_param)

        if top_keywords and len(top_keywords) > 0:
            processed_keywords = []
            for idx, kw in enumerate(top_keywords):
                if isinstance(kw, dict):
                    processed_keywords.append({
                        "순위": idx + 1,
                        "키워드": kw.get("keyword", "Unknown"),
                        "문서 수": kw.get("document_count", 0),
                        "총 빈도": kw.get("total_frequency", 0),
                        "평균 점수": f"{kw.get('avg_score', 0):.3f}",
                        "카테고리": ", ".join(kw.get("categories", [])) if kw.get("categories") else "없음",
                        "도메인": ", ".join(kw.get("domains", [])) if kw.get("domains") else "없음"
                    })
                else:
                    st.warning(f"키워드 {idx + 1}: 데이터 형식 오류")

            if processed_keywords:
                df_keywords = pd.DataFrame(processed_keywords)
                st.dataframe(df_keywords, use_container_width=True)

                if len(processed_keywords) >= 10:
                    try:
                        top_10_data = processed_keywords[:10]
                        fig_top = px.bar(
                            x=[item["문서 수"] for item in top_10_data],
                            y=[item["키워드"] for item in top_10_data],
                            orientation='h',
                            title="상위 10개 키워드 (문서 수 기준)"
                        )
                        fig_top.update_layout(yaxis={'categoryorder': 'total ascending'})
                        st.plotly_chart(fig_top, use_container_width=True)
                    except Exception as e:
                        st.error(f"차트 생성 실패: {e}")
            else:
                st.warning("처리 가능한 키워드 데이터가 없습니다.")
        else:
            st.info(f"{domain_filter} 도메인에서 키워드를 찾을 수 없습니다.")


def render_domain_explorer(client):
    """도메인 탐색기 렌더링 - DuplicateWidgetID 오류 수정"""
    st.subheader("🏢 도메인별 문서 탐색")

    col1, col2 = st.columns(2)

    with col1:
        selected_domain = st.selectbox(
            "도메인 선택",
            ["technology", "finance", "legal", "medical", "business", "academic", "general"]
        )

    with col2:
        domain_limit = st.number_input("조회할 문서 수", min_value=5, max_value=50, value=15)

    if st.button("도메인별 문서 조회"):
        results = search_by_domain(client, selected_domain, domain_limit)

        if results and len(results) > 0:
            st.write(f"**{selected_domain} 도메인 문서 ({len(results)}개):**")

            for idx, doc in enumerate(results, 1):
                if not isinstance(doc, dict):
                    st.warning(f"문서 {idx}: 데이터 형식 오류")
                    continue

                with st.expander(f"{idx}. {doc.get('source', 'Unknown')}"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"**문서 유형:** {doc.get('document_type', 'unknown')}")
                        st.write(f"**키워드 수:** {doc.get('keyword_count', 0)}")
                        st.write(f"**추출 시간:** {doc.get('extracted_at', 'Unknown')}")

                    with col2:
                        keywords = doc.get('top_keywords', [])
                        if keywords and isinstance(keywords, list):
                            st.write("**주요 키워드:**")
                            keyword_html = " ".join([
                                f'<span class="keyword-tag">{kw}</span>'
                                for kw in keywords[:8] if isinstance(kw, str)
                            ])
                            if keyword_html:
                                st.markdown(keyword_html, unsafe_allow_html=True)

                        topics = doc.get('main_topics', [])
                        if topics and isinstance(topics, list):
                            st.write("**주요 주제:**")
                            for topic in topics[:3]:
                                if isinstance(topic, str):
                                    st.write(f"• {topic}")

                    # 🔧 수정: 고유한 키 생성
                    doc_id = doc.get('doc_id', f'unknown_{idx}')
                    unique_key = f"domain_detail_{selected_domain}_{idx}_{doc_id}"

                    if st.button("상세 분석", key=unique_key):
                        if doc_id and doc_id != f'unknown_{idx}':
                            st.session_state.selected_doc_id = doc_id
                            st.session_state.page_mode = 'document_detail'
                            rerun()
                        else:
                            st.warning("문서 ID를 찾을 수 없습니다.")
        else:
            st.info(f"{selected_domain} 도메인에 해당하는 문서가 없습니다.")

            # 다른 도메인 제안
            st.caption("💡 다른 도메인을 선택해보세요:")
            alternative_domains = ["general", "technology", "business"]
            for i, alt_domain in enumerate(alternative_domains):
                if alt_domain != selected_domain:
                    # 🔧 수정: 고유한 키 생성
                    unique_key = f"alt_domain_{alt_domain}_{i}"
                    if st.button(f"🔍 {alt_domain} 도메인 탐색", key=unique_key):
                        st.session_state.temp_domain = alt_domain
                        st.rerun()


def render_document_detail(client, doc_id: str):
    """문서 상세 온톨로지 보기 - DuplicateWidgetID 오류 수정"""
    st.subheader(f"📄 문서 상세 온톨로지 분석")

    if st.button("← 뒤로 가기"):
        st.session_state.page_mode = 'main'
        rerun()

    with st.spinner("문서 온톨로지를 불러오는 중..."):
        ontology = get_document_ontology(client, doc_id)

    if not ontology:
        st.error("문서의 온톨로지 정보를 찾을 수 없습니다.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 다시 시도"):
                st.rerun()
        with col2:
            if st.button("📋 문서 목록으로"):
                st.session_state.page_mode = 'main'
                st.rerun()
        return

    # 문서 기본 정보
    st.write(f"**문서명:** {ontology.get('source', 'Unknown')}")
    st.write(f"**문서 ID:** {doc_id}")

    col1, col2, col3 = st.columns(3)

    with col1:
        metadata = ontology.get('metadata', {})
        st.write(f"**언어:** {metadata.get('language', 'unknown')}")
        st.write(f"**문서 유형:** {metadata.get('document_type', 'unknown')}")
        st.write(f"**추정 도메인:** {metadata.get('estimated_domain', 'unknown')}")

    with col2:
        text_stats = metadata.get('text_statistics', {})
        st.write(f"**총 문자 수:** {text_stats.get('total_length', 0):,}")
        st.write(f"**단어 수:** {text_stats.get('words', 0):,}")
        st.write(f"**문장 수:** {text_stats.get('sentences', 0):,}")

    with col3:
        processing_stats = ontology.get('processing_stats', {})
        st.write(f"**처리 시간:** {processing_stats.get('total_time', 0):.2f}초")
        st.write(f"**키워드 수:** {processing_stats.get('keywords_count', 0)}")
        st.write(f"**개체명 수:** {processing_stats.get('entities_count', 0)}")

    # 탭으로 구분된 상세 정보
    tab1, tab2, tab3, tab4 = st.tabs(["키워드", "개체명", "컨텍스트", "유사 문서"])

    with tab1:
        keywords = ontology.get('keywords', [])
        if keywords and isinstance(keywords, list):
            st.write(f"**추출된 키워드 ({len(keywords)}개):**")

            keyword_by_category = {}
            for kw in keywords:
                if isinstance(kw, dict):
                    category = kw.get('category', 'unknown')
                    if category not in keyword_by_category:
                        keyword_by_category[category] = []
                    keyword_by_category[category].append(kw)

            for category, kw_list in keyword_by_category.items():
                if kw_list:
                    st.write(f"**{category.title()} ({len(kw_list)}개):**")

                    try:
                        keyword_data = []
                        for kw in sorted(kw_list, key=lambda x: x.get('score', 0), reverse=True):
                            if isinstance(kw, dict):
                                keyword_data.append({
                                    "키워드": kw.get("term", "Unknown"),
                                    "점수": kw.get("score", 0),
                                    "빈도": kw.get("frequency", 0)
                                })

                        if keyword_data:
                            keyword_df = pd.DataFrame(keyword_data)
                            st.dataframe(keyword_df, use_container_width=True)
                    except Exception as e:
                        st.error(f"키워드 테이블 생성 실패: {e}")
        else:
            st.info("추출된 키워드가 없습니다.")

    with tab2:
        entities = metadata.get('key_entities', [])
        if entities and isinstance(entities, list):
            st.write(f"**인식된 개체명 ({len(entities)}개):**")

            try:
                entity_data = []
                for ent in entities:
                    if isinstance(ent, dict):
                        entity_data.append({
                            "개체명": ent.get("text", "Unknown"),
                            "타입": ent.get("label", "Unknown"),
                            "신뢰도": f"{ent.get('confidence', 0):.3f}"
                        })

                if entity_data:
                    entity_df = pd.DataFrame(entity_data)
                    st.dataframe(entity_df, use_container_width=True)

                    entity_types = [ent.get("label", "unknown") for ent in entities if isinstance(ent, dict)]
                    if entity_types:
                        entity_counts = pd.Series(entity_types).value_counts()
                        fig_entities = px.pie(
                            values=entity_counts.values,
                            names=entity_counts.index,
                            title="개체명 타입별 분포"
                        )
                        st.plotly_chart(fig_entities, use_container_width=True)
            except Exception as e:
                st.error(f"개체명 시각화 실패: {e}")
        else:
            st.info("인식된 개체명이 없습니다.")

    with tab3:
        context = ontology.get('context', {})

        main_topics = context.get('main_topics', [])
        if main_topics and isinstance(main_topics, list):
            st.write("**주요 주제:**")
            for topic in main_topics:
                if isinstance(topic, str):
                    st.write(f"• {topic}")

        related_concepts = context.get('related_concepts', [])
        if related_concepts and isinstance(related_concepts, list):
            st.write("**관련 개념:**")
            concept_html = " ".join([
                f'<span class="keyword-tag">{concept}</span>'
                for concept in related_concepts if isinstance(concept, str)
            ])
            if concept_html:
                st.markdown(concept_html, unsafe_allow_html=True)

        domain_indicators = context.get('domain_indicators', [])
        if domain_indicators and isinstance(domain_indicators, list):
            st.write("**도메인 지시어:**")
            for indicator in domain_indicators:
                if isinstance(indicator, str):
                    st.write(f"• {indicator}")

        clusters = context.get('semantic_clusters', [])
        if clusters and isinstance(clusters, list):
            st.write(f"**의미적 클러스터 ({len(clusters)}개):**")
            for cluster in clusters:
                if isinstance(cluster, dict):
                    with st.expander(f"클러스터 {cluster.get('cluster_id', 0)} (크기: {cluster.get('size', 0)})"):
                        st.write(f"**대표 청크:** {cluster.get('representative_chunk', '')}")
                        st.write(f"**평균 유사도:** {cluster.get('avg_similarity', 0):.3f}")

    with tab4:
        st.write("**유사한 문서들:**")

        with st.spinner("유사 문서를 찾는 중..."):
            similar_docs = get_similar_documents(client, doc_id)

        if similar_docs and len(similar_docs) > 0:
            for idx, sim_doc in enumerate(similar_docs):
                if not isinstance(sim_doc, dict):
                    continue

                similarity = sim_doc.get('similarity_score', 0)

                if similarity >= 0.8:
                    color = "#4caf50"
                elif similarity >= 0.7:
                    color = "#ff9800"
                else:
                    color = "#f44336"

                st.markdown(f"""
                <div class="search-results">
                    <h4>📄 {sim_doc.get('source', 'Unknown')}</h4>
                    <p><strong>유사도:</strong> 
                        <span style="background-color: {color}; color: white; padding: 0.2rem 0.5rem; border-radius: 12px; font-weight: bold;">
                            {similarity:.3f}
                        </span>
                    </p>
                    <p><strong>문서 유형:</strong> {sim_doc.get('document_type', 'unknown')}</p>
                    <p><strong>도메인:</strong> <span class="domain-badge">{sim_doc.get('estimated_domain', 'unknown')}</span></p>
                </div>
                """, unsafe_allow_html=True)

                keywords = sim_doc.get('top_keywords', [])
                if keywords and isinstance(keywords, list):
                    keyword_html = " ".join([
                        f'<span class="keyword-tag">{kw}</span>'
                        for kw in keywords[:5] if isinstance(kw, str)
                    ])
                    if keyword_html:
                        st.markdown(f"**키워드:** {keyword_html}", unsafe_allow_html=True)

                # 🔧 수정: 고유한 키 생성
                similar_doc_id = sim_doc.get('doc_id', f'unknown_{idx}')
                unique_key = f"similar_doc_{doc_id}_{idx}_{similar_doc_id}"

                if st.button("이 문서 보기", key=unique_key):
                    if similar_doc_id and similar_doc_id != f'unknown_{idx}':
                        st.session_state.selected_doc_id = similar_doc_id
                        rerun()
                    else:
                        st.warning("문서 ID를 찾을 수 없습니다.")
        else:
            st.info("유사한 문서를 찾을 수 없습니다.")

            st.caption("💡 다른 문서들을 탐색해보세요:")
            if st.button("🔍 전체 문서 목록 보기"):
                st.session_state.page_mode = 'main'
                st.rerun()


# 2. 전역 API 매니저 인스턴스 생성 (main() 함수 앞에 추가)
ontology_api = OntologyAPIManager()


def main():
    """메인 함수"""
    st.title("🧠 온톨로지 관리")
    st.write("문서에서 추출된 키워드, 메타데이터, 컨텍스트를 탐색하고 관리합니다.")

    # API 클라이언트 초기화
    client = ClientManager.get_client()

    # 온톨로지 시스템 상태 확인
    try:
        health_response = client.request("GET", "/v1/ontology/health")

        # 응답 형식 확인 및 처리
        if isinstance(health_response, dict):
            if health_response.get("error"):
                st.error("온톨로지 시스템에 연결할 수 없습니다.")
                st.write("가능한 원인:")
                st.write("• 온톨로지 모듈이 설치되지 않음")
                st.write("• API 서버가 실행되지 않음")
                st.write("• 네트워크 연결 문제")
                return

            # 시스템 상태 표시
            if not health_response.get("ontology_collections_status", {}).get("ontology", False):
                st.warning("온톨로지 컬렉션이 초기화되지 않았습니다. 문서를 업로드하면 자동으로 생성됩니다.")
        else:
            st.error(f"예상하지 못한 헬스체크 응답 형식: {type(health_response)}")
            return

    except Exception as e:
        st.error(f"온톨로지 시스템 상태 확인 실패: {e}")
        return

    # 세션 상태 초기화
    if 'page_mode' not in st.session_state:
        st.session_state.page_mode = 'main'

    if 'selected_doc_id' not in st.session_state:
        st.session_state.selected_doc_id = None

    # 페이지 모드에 따른 렌더링
    if st.session_state.page_mode == 'document_detail' and st.session_state.selected_doc_id:
        render_document_detail(client, st.session_state.selected_doc_id)
    else:
        # 메인 페이지
        st.session_state.page_mode = 'main'

        # 탭으로 기능 구분
        tab1, tab2, tab3 = st.tabs(["📊 대시보드", "🔍 키워드 탐색", "🏢 도메인 탐색"])

        with tab1:
            render_statistics_dashboard(client)

        with tab2:
            render_keyword_explorer(client)

        with tab3:
            render_domain_explorer(client)


if __name__ == "__main__":
    main()