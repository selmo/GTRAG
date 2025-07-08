"""
문서 관리 페이지
"""
import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent.parent))

from ui.utils.api_client import APIClient
from ui.components.uploader import render_file_uploader, get_upload_summary

# 페이지 설정
st.set_page_config(
    page_title="문서 관리 - GTOne RAG",
    page_icon="📄",
    layout="wide"
)

# API 클라이언트 초기화
api_client = APIClient()

# 헤더
st.title("📄 문서 관리")
st.markdown("업로드된 문서를 관리하고 새로운 문서를 추가합니다.")

# 탭 생성
tab1, tab2, tab3 = st.tabs(["📤 새 문서 업로드", "📁 문서 목록", "📊 통계"])

with tab1:
    # 업로드 컴포넌트
    render_file_uploader(api_client)
    
    # 업로드 팁
    with st.expander("💡 업로드 팁"):
        st.write("""
        - **PDF 문서**: 텍스트 기반 PDF가 가장 정확합니다
        - **이미지 파일**: OCR을 통해 텍스트를 추출합니다
        - **대용량 파일**: 50MB 이하로 분할하여 업로드하세요
        - **언어**: 한국어, 영어 모두 지원됩니다
        """)

with tab2:
    st.header("📁 업로드된 문서")
    
    # 필터 옵션
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        search_filter = st.text_input(
            "🔍 문서명 검색",
            placeholder="파일명으로 검색..."
        )
    
    with col2:
        date_filter = st.date_input(
            "📅 날짜 필터",
            value=None,
            help="특정 날짜의 문서만 표시"
        )
    
    with col3:
        if st.button("🔄 새로고침", use_container_width=True):
            st.experimental_rerun()
    
    # 문서 목록 표시
    if 'uploaded_files' in st.session_state and st.session_state.uploaded_files:
        # 필터링
        files = st.session_state.uploaded_files
        
        if search_filter:
            files = [f for f in files if search_filter.lower() in f['name'].lower()]
        
        if date_filter:
            date_str = date_filter.strftime("%Y-%m-%d")
            files = [f for f in files if f['time'].startswith(date_str)]
        
        if files:
            # 데이터프레임으로 표시
            df = pd.DataFrame(files)
            
            # 선택 가능한 데이터프레임
            selected_indices = st.multiselect(
                "문서 선택 (다중 선택 가능)",
                options=list(range(len(df))),
                format_func=lambda x: df.iloc[x]['name']
            )
            
            # 선택된 문서에 대한 액션
            if selected_indices:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("🗑️ 선택 삭제", type="secondary"):
                        for idx in sorted(selected_indices, reverse=True):
                            del st.session_state.uploaded_files[idx]
                        st.success(f"{len(selected_indices)}개 문서가 삭제되었습니다.")
                        st.experimental_rerun()
                
                with col2:
                    if st.button("📥 메타데이터 다운로드"):
                        selected_files = [df.iloc[idx].to_dict() for idx in selected_indices]
                        import json
                        st.download_button(
                            label="다운로드",
                            data=json.dumps(selected_files, ensure_ascii=False, indent=2),
                            file_name=f"metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                
                with col3:
                    if st.button("🔍 선택 문서로 검색"):
                        st.info("검색 페이지에서 선택한 문서들을 검색할 수 있습니다.")
            
            # 문서 목록 테이블
            st.dataframe(
                df[['name', 'time', 'chunks', 'size']].rename(columns={
                    'name': '파일명',
                    'time': '업로드 시간',
                    'chunks': '청크 수',
                    'size': '크기'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # 개별 문서 상세 정보
            if st.checkbox("📋 상세 정보 보기"):
                selected_file = st.selectbox(
                    "문서 선택",
                    options=range(len(files)),
                    format_func=lambda x: files[x]['name']
                )
                
                if selected_file is not None:
                    file_info = files[selected_file]
                    
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.metric("파일명", file_info['name'])
                        st.metric("업로드 시간", file_info['time'])
                        st.metric("청크 수", file_info['chunks'])
                        st.metric("파일 크기", file_info['size'])
                    
                    with col2:
                        # 여기에 실제 청크 내용을 표시할 수 있음
                        st.info("청크 내용을 보려면 검색 기능을 사용하세요.")
                        
                        # 문서 관련 액션
                        if st.button("🔍 이 문서에서 검색"):
                            st.session_state.selected_document = file_info['name']
                            st.info("검색 페이지로 이동하여 이 문서 내에서 검색하세요.")
        else:
            st.info("필터 조건에 맞는 문서가 없습니다.")
    else:
        st.info("아직 업로드된 문서가 없습니다.")

with tab3:
    st.header("📊 문서 통계")
    
    # 전체 통계
    stats = get_upload_summary()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "총 문서 수",
            stats['total_files'],
            help="업로드된 전체 문서 수"
        )
    
    with col2:
        st.metric(
            "총 청크 수",
            stats['total_chunks'],
            help="모든 문서의 청크 합계"
        )
    
    with col3:
        st.metric(
            "총 용량",
            f"{stats['total_size']:.1f} MB",
            help="모든 문서의 용량 합계"
        )
    
    with col4:
        avg_chunks = stats['total_chunks'] / max(stats['total_files'], 1)
        st.metric(
            "평균 청크/문서",
            f"{avg_chunks:.1f}",
            help="문서당 평균 청크 수"
        )
    
    # 시간별 업로드 통계
    if 'uploaded_files' in st.session_state and st.session_state.uploaded_files:
        st.divider()
        
        # 날짜별 업로드 수
        df = pd.DataFrame(st.session_state.uploaded_files)
        df['date'] = pd.to_datetime(df['time']).dt.date
        daily_uploads = df.groupby('date').size()
        
        st.subheader("📈 일별 업로드 추이")
        st.line_chart(daily_uploads)
        
        # 파일 타입별 통계
        df['extension'] = df['name'].str.split('.').str[-1].str.lower()
        type_stats = df.groupby('extension').size()
        
        st.subheader("📊 파일 타입별 분포")
        st.bar_chart(type_stats)
        
        # 크기 분포
        df['size_mb'] = df['size'].str.extract(r'([\d.]+)').astype(float)
        
        st.subheader("📏 파일 크기 분포")
        size_bins = [0, 1, 5, 10, 20, 50]
        size_labels = ['0-1MB', '1-5MB', '5-10MB', '10-20MB', '20-50MB']
        df['size_category'] = pd.cut(df['size_mb'], bins=size_bins, labels=size_labels)
        size_dist = df['size_category'].value_counts()
        
        st.bar_chart(size_dist)

# 푸터
st.divider()
st.caption("💡 팁: 문서를 업로드한 후 채팅 페이지에서 질문하거나 검색 페이지에서 내용을 찾을 수 있습니다.")
