"""
파일 업로드 컴포넌트
"""
import streamlit as st
from datetime import datetime
from typing import List, Dict, Optional
import os


ALLOWED_EXTENSIONS = ['pdf', 'txt', 'png', 'jpg', 'jpeg', 'docx', 'doc']
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '50'))


def render_file_uploader(api_client):
    """파일 업로더 렌더링"""
    st.header("📄 문서 업로드")
    
    # 파일 타입 정보
    with st.expander("ℹ️ 지원 파일 형식"):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**문서 파일**")
            st.write("• PDF (.pdf)")
            st.write("• Word (.docx, .doc)")
            st.write("• 텍스트 (.txt)")
        with col2:
            st.write("**이미지 파일**")
            st.write("• PNG (.png)")
            st.write("• JPEG (.jpg, .jpeg)")
            st.write("• TIFF (.tif, .tiff)")
    
    # 파일 업로더
    uploaded_file = st.file_uploader(
        "파일 선택",
        type=ALLOWED_EXTENSIONS,
        help=f"최대 {MAX_FILE_SIZE_MB}MB까지 업로드 가능합니다."
    )
    
    if uploaded_file is not None:
        # 파일 정보 표시
        file_details = {
            "파일명": uploaded_file.name,
            "파일 타입": uploaded_file.type,
            "파일 크기": f"{uploaded_file.size / 1024 / 1024:.2f} MB"
        }
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            for key, value in file_details.items():
                st.write(f"**{key}**: {value}")
        
        with col2:
            if st.button("📤 업로드", type="primary"):
                process_upload(uploaded_file, api_client)


def process_upload(uploaded_file, api_client):
    """파일 업로드 처리"""
    # 파일 크기 검증
    if uploaded_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        st.error(f"파일 크기가 {MAX_FILE_SIZE_MB}MB를 초과합니다.")
        return
    
    with st.spinner("문서 처리 중..."):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # 업로드 시작
            status_text.text("문서 업로드 중...")
            progress_bar.progress(25)
            
            result = api_client.upload_document(uploaded_file)
            
            if 'error' not in result:
                # 처리 중
                status_text.text("문서 분석 중...")
                progress_bar.progress(50)
                
                # 벡터화
                status_text.text("벡터 생성 중...")
                progress_bar.progress(75)
                
                # 완료
                progress_bar.progress(100)
                status_text.empty()
                
                st.success(f"✅ 성공! {result['uploaded']}개 청크로 분할되었습니다.")
                
                # 업로드 기록 저장
                if 'uploaded_files' not in st.session_state:
                    st.session_state.uploaded_files = []
                
                st.session_state.uploaded_files.append({
                    'name': uploaded_file.name,
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    'chunks': result['uploaded'],
                    'size': f"{uploaded_file.size / 1024 / 1024:.2f} MB"
                })
                
                # 통계 표시
                show_upload_stats(result)
                
            else:
                st.error(f"업로드 실패: {result['error']}")
                
        except Exception as e:
            st.error(f"오류 발생: {str(e)}")
        finally:
            progress_bar.empty()
            status_text.empty()


def show_upload_stats(result: Dict):
    """업로드 통계 표시"""
    with st.expander("📊 처리 통계", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("청크 수", result['uploaded'])
        
        with col2:
            avg_chunk_size = result.get('avg_chunk_size', 'N/A')
            if isinstance(avg_chunk_size, (int, float)):
                st.metric("평균 청크 크기", f"{avg_chunk_size:.0f} 자")
            else:
                st.metric("평균 청크 크기", avg_chunk_size)
        
        with col3:
            processing_time = result.get('processing_time', 'N/A')
            if isinstance(processing_time, (int, float)):
                st.metric("처리 시간", f"{processing_time:.2f} 초")
            else:
                st.metric("처리 시간", processing_time)


def render_uploaded_files():
    """업로드된 파일 목록 렌더링"""
    if 'uploaded_files' in st.session_state and st.session_state.uploaded_files:
        st.divider()
        st.header("📁 업로드된 문서")
        
        # 정렬 옵션
        sort_option = st.selectbox(
            "정렬 기준",
            ["최신순", "이름순", "크기순", "청크순"],
            label_visibility="collapsed"
        )
        
        # 파일 목록 정렬
        files = st.session_state.uploaded_files.copy()
        
        if sort_option == "최신순":
            files.reverse()
        elif sort_option == "이름순":
            files.sort(key=lambda x: x['name'])
        elif sort_option == "크기순":
            files.sort(key=lambda x: float(x['size'].split()[0]), reverse=True)
        elif sort_option == "청크순":
            files.sort(key=lambda x: x['chunks'], reverse=True)
        
        # 파일 목록 표시
        for idx, file in enumerate(files[:10]):  # 최대 10개만 표시
            with st.container():
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**{file['name']}**")
                    st.caption(f"📅 {file['time']} | 📦 {file['chunks']} chunks | 💾 {file['size']}")
                
                with col2:
                    if st.button("🗑️", key=f"delete_{idx}", help="삭제"):
                        # 실제 구현에서는 API 호출하여 삭제
                        st.session_state.uploaded_files.remove(file)
                        st.experimental_rerun()
        
        if len(files) > 10:
            st.info(f"최근 10개 파일만 표시됩니다. (전체: {len(files)}개)")


def get_upload_summary() -> Dict:
    """업로드 요약 정보 반환"""
    if 'uploaded_files' not in st.session_state:
        return {
            'total_files': 0,
            'total_chunks': 0,
            'total_size': 0
        }
    
    files = st.session_state.uploaded_files
    total_chunks = sum(f['chunks'] for f in files)
    total_size = sum(float(f['size'].split()[0]) for f in files)
    
    return {
        'total_files': len(files),
        'total_chunks': total_chunks,
        'total_size': total_size
    }
