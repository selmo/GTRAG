"""
파일 업로드 컴포넌트 (수정됨)
"""
import streamlit as st
from datetime import datetime
from typing import List, Dict, Optional
import os
from ui.utils.streamlit_helpers import rerun


ALLOWED_EXTENSIONS = ['pdf', 'txt', 'png', 'jpg', 'jpeg', 'docx', 'doc']
MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '50'))


import re

def _size_to_mb(size_str: str) -> float:
    """
    '12.34 MB' → 12.34
    '—'·'' 등 숫자가 없으면 0.0
    """
    try:
        return float(re.search(r'[\d.]+', size_str).group())
    except Exception:
        return 0.0

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
    """파일 업로드 처리 (수정됨)"""
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

            # 파일 내용을 바이트로 읽기
            file_bytes = uploaded_file.getvalue()

            # requests를 사용하여 직접 multipart/form-data 요청 생성
            import requests

            # API 서버 URL
            upload_url = f"{api_client.base_url}/v1/documents"

            # 파일 데이터 준비 (중요: 파라미터 이름을 'file'로 맞춤)
            files = {
                'file': (uploaded_file.name, file_bytes, uploaded_file.type)
            }

            status_text.text("서버로 전송 중...")
            progress_bar.progress(50)

            # POST 요청 (Content-Type 헤더는 자동으로 설정됨)
            # ① env → 기본 180 초
            UPLOAD_TIMEOUT = int(os.getenv("UPLOAD_TIMEOUT", "180"))
            # ② 연결 5 초 + 응답 175 초로 분리할 수도 있음
            response = requests.post(
                 upload_url,
                 files = files,
                 timeout = (5, UPLOAD_TIMEOUT)
            )

            status_text.text("응답 처리 중...")
            progress_bar.progress(75)

            # 응답 처리
            if response.status_code == 200:
                result = response.json()

                # 완료
                progress_bar.progress(100)
                status_text.empty()

                st.success(f"✅ 성공! {result.get('uploaded', 0)}개 청크로 분할되었습니다.")

                # 업로드 기록 저장
                if 'uploaded_files' not in st.session_state:
                    st.session_state.uploaded_files = []

                st.session_state.uploaded_files.append({
                    'name': uploaded_file.name,
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    'chunks': result.get('uploaded', 0),
                    'size': f"{uploaded_file.size / 1024 / 1024:.2f} MB"
                })

                # 통계 표시
                show_upload_stats(result)

                # 성공 시 페이지 새로고침
                rerun()

            else:
                # 오류 응답 처리
                try:
                    error_detail = response.json()
                    st.error(f"업로드 실패 ({response.status_code}): {error_detail}")
                except:
                    st.error(f"업로드 실패 ({response.status_code}): {response.text}")

                # 디버그 정보 표시
                with st.expander("🐛 디버그 정보"):
                    st.write(f"**상태 코드**: {response.status_code}")
                    st.write(f"**응답 헤더**: {dict(response.headers)}")
                    st.write(f"**요청 URL**: {upload_url}")
                    st.write(f"**파일명**: {uploaded_file.name}")
                    st.write(f"**파일 타입**: {uploaded_file.type}")
                    st.write(f"**파일 크기**: {uploaded_file.size} bytes")

                    if response.text:
                        st.code(response.text)

        except requests.exceptions.ConnectionError:
            st.error("❌ API 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
            st.info("API 서버 상태를 확인하려면 http://localhost:18000/docs 에 접속해보세요.")

        except requests.exceptions.Timeout:
            st.error("❌ 요청 시간이 초과되었습니다. 파일 크기가 너무 크거나 서버가 응답하지 않습니다.")

        except Exception as e:
            st.error(f"❌ 예상치 못한 오류가 발생했습니다: {str(e)}")

            # 상세 디버그 정보
            with st.expander("🐛 오류 세부사항"):
                import traceback
                st.code(traceback.format_exc())

        finally:
            progress_bar.empty()
            status_text.empty()


def show_upload_stats(result: Dict):
    """업로드 통계 표시"""
    with st.expander("📊 처리 통계", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("청크 수", result.get('uploaded', 0))

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


def render_uploaded_files(api_client):
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
            files.sort(key=lambda x: _size_to_mb(x.get('size', '0')), reverse=True)
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
                        # ① 서버-측 문서 삭제
                        try:
                            api_client.delete_document(file["name"])  # ← REST DELETE /v1/documents/{id}
                        except Exception as e:
                            st.error(f"서버 삭제 실패: {e}")
                            return
                        # ② 클라이언트 상태 동기화
                        st.session_state.uploaded_files.remove(file)
                        rerun()

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
    total_size = sum(_size_to_mb(f.get('size', '0')) for f in files)

    return {
        'total_files': len(files),
        'total_chunks': total_chunks,
        'total_size': total_size
    }


def test_api_connection(api_client):
    """API 연결 테스트"""
    try:
        import requests
        response = requests.get(f"{api_client.base_url}/v1/health", timeout=5)
        if response.status_code == 200:
            return True, "API 서버 연결 성공"
        else:
            return False, f"API 서버 오류 ({response.status_code})"
    except requests.exceptions.ConnectionError:
        return False, "API 서버에 연결할 수 없습니다"
    except Exception as e:
        return False, f"연결 테스트 실패: {str(e)}"