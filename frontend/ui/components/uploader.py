"""
파일 업로드 컴포넌트 - 개선된 버전
- Import 경로 통일
- 공통 컴포넌트 적용
- 설정 중앙화
- 에러 처리 표준화
"""
import logging

import streamlit as st
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import requests

from frontend.ui.utils.streamlit_helpers import rerun
from frontend.ui.core.config import config, Constants
from frontend.ui.components.common import (
    StatusIndicator, MetricCard, ErrorDisplay, ActionButton,
    FileDisplay, LoadingSpinner
)
from frontend.ui.utils.error_handler import (
    ErrorContext
)

# 조건부 import (표준 패턴)
try:
    from frontend.ui.utils.file_utils import (
        FileUploadManager, FileNameCleaner, MultiFileProcessor,
        get_supported_file_formats
    )
    HAS_FILE_UTILS = True
except ImportError:
    FileUploadManager = None
    FileNameCleaner = None
    MultiFileProcessor = None
    HAS_FILE_UTILS = False

# 설정값을 config에서 가져오기
ALLOWED_EXTENSIONS = config.file.allowed_extensions
MAX_FILE_SIZE_MB = config.file.max_file_size_mb
MAX_ARCHIVE_SIZE_MB = config.file.max_archive_size_mb

# 파일 업로드 매니저 초기화
if HAS_FILE_UTILS:
    upload_manager = FileUploadManager(MAX_FILE_SIZE_MB, MAX_ARCHIVE_SIZE_MB)
else:
    upload_manager = None


logger = logging.getLogger(__name__)


def render_file_uploader(api_client):
    """파일 업로더 렌더링 + 완료상태 처리 - 개선된 버전"""
    _init_upload_state()
    st.header(f'{Constants.Icons.UPLOAD} 문서 업로드')

    # 완료상태면 업로드 UI 숨김
    if st.session_state.upload_complete:
        StatusIndicator.render_status(
            "success",
            "최근 업로드가 완료되었습니다",
        )

        if st.button(f'{Constants.Icons.UPLOAD} 추가 파일 업로드',
                    key='upload_reset', use_container_width=True):
            st.session_state.upload_complete = False
            _clear_uploader_widgets()
            rerun()
        return

    # 업로드 방식 선택
    upload_mode = st.radio(
        '업로드 방식 선택',
        ['단일 파일', '다중 파일', '압축 파일'],
        horizontal=True,
        help='압축 파일은 자동 추출되어 개별 문서로 처리됩니다.'
    )

    # 지원 형식 안내 - 설정에서 가져오기
    render_supported_formats_info()

    # 파일 업로드 UI
    uploaded_files = []

    if upload_mode == '단일 파일':
        f = st.file_uploader(
            '단일 파일 선택',
            type=ALLOWED_EXTENSIONS,
            accept_multiple_files=False,
            key='single_file_uploader'
        )
        if f:
            uploaded_files = [f]

    elif upload_mode == '다중 파일':
        uploaded_files = st.file_uploader(
            '다중 파일 선택',
            type=ALLOWED_EXTENSIONS,
            accept_multiple_files=True,
            help=f'각 파일은 최대 {MAX_FILE_SIZE_MB}MB까지 가능합니다.',
            key='multi_file_uploader'
        )

    else:  # 압축 파일
        archive_extensions = config.file.allowed_archive_extensions
        f = st.file_uploader(
            '압축 파일 선택',
            type=archive_extensions,
            help=f'최대 {MAX_ARCHIVE_SIZE_MB}MB까지 업로드 가능. 자동 추출됩니다.',
            key='archive_file_uploader'
        )
        if f:
            uploaded_files = [f]

    if uploaded_files:
        render_upload_preview_and_process(uploaded_files, api_client, upload_mode)


def render_supported_formats_info():
    """지원 파일 형식 정보 표시 - 설정 기반"""
    with st.expander(f'{Constants.Icons.STATUS_INFO} 지원 파일 형식', expanded=False):
        col1, col2, col3 = st.columns(3)

        # 문서 파일
        with col1:
            st.write('**문서 파일**')
            doc_extensions = ['pdf', 'txt', 'docx', 'doc', 'md', 'rtf']
            for ext in doc_extensions:
                if ext in config.file.allowed_extensions:
                    icon = Constants.Icons.FILE_ICONS.get(ext, Constants.Icons.FILE_ICONS['default'])
                    st.write(f'• {icon} {ext.upper()} (.{ext})')

        # 이미지 파일
        with col2:
            st.write('**이미지 파일**')
            img_extensions = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff']
            for ext in img_extensions:
                if ext in config.file.allowed_extensions:
                    icon = Constants.Icons.FILE_ICONS.get(ext, Constants.Icons.FILE_ICONS['default'])
                    st.write(f'• {icon} {ext.upper()} (.{ext})')

        # 압축 파일
        with col3:
            st.write('**압축 파일**')
            for ext in config.file.allowed_archive_extensions:
                icon = Constants.Icons.FILE_ICONS.get(ext, Constants.Icons.FILE_ICONS['default'])
                st.write(f'• {icon} {ext.upper()} (.{ext})')
            st.caption("압축 파일은 자동 추출됩니다")


def render_upload_preview_and_process(uploaded_files, api_client, upload_mode):
    """업로드 전 미리보기 + 실행 - 개선된 버전"""
    _init_upload_state()
    st.subheader(f'{Constants.Icons.DOCUMENT} 업로드 요약')

    if not isinstance(uploaded_files, list):
        uploaded_files = list(uploaded_files)

    # 파일 정보 표시
    total_size = 0
    file_info_list = []

    for f in uploaded_files:
        # 파일명 정리
        if HAS_FILE_UTILS and FileNameCleaner:
            display_name = FileNameCleaner.clean_display_name(f.name)
        else:
            display_name = f.name

        file_info = {
            'display_name': display_name,
            'original_name': f.name,
            'size': f.size,
            'type': getattr(f, 'type', ''),
            'size_mb': f.size / 1024 / 1024 if f.size else 0
        }

        file_info_list.append(file_info)
        total_size += getattr(f, 'size', 0)

    with st.expander("📄 업로드 파일 상세 목록", expanded=False):
        for file_info in file_info_list:  # 파일 목록은 필요할 때만 펼쳐서 본다
            FileDisplay.render_file_card(file_info)

    # 총 크기 표시
    total_size_mb = total_size / 1024 / 1024 if total_size else 0

    # 크기 검증
    size_valid = True
    error_messages = []

    if upload_mode == '압축 파일' and total_size_mb > MAX_ARCHIVE_SIZE_MB:
        size_valid = False
        error_messages.append(f'압축 파일 크기가 {MAX_ARCHIVE_SIZE_MB}MB 초과')

    elif upload_mode != '압축 파일':
        oversized_files = [f for f in file_info_list if f['size_mb'] > MAX_FILE_SIZE_MB]
        if oversized_files:
            size_valid = False
            error_messages.append(f'일부 파일이 {MAX_FILE_SIZE_MB}MB 초과')

    # 에러 표시
    if error_messages:
        ErrorDisplay.render_validation_errors(error_messages)

    # 액션 버튼
    actions = [
        {
            "label": f"{Constants.Icons.UPLOAD} {len(uploaded_files)}개 파일 업로드",
            "key": "preview_upload_button",
            "type": "primary",
            "disabled": not size_valid or st.session_state.get('uploading', False),
            "callback": lambda: process_multiple_file_upload(uploaded_files, api_client, upload_mode)
        },
        {
            "label": f"{Constants.Icons.DELETE} 취소",
            "key": "preview_cancel_button",
            "type": "secondary",
            "callback": _cancel_upload
        }
    ]

    ActionButton.render_action_row(actions)

    # 메트릭 표시
    metrics = [
        {"title": "파일 수", "value": len(uploaded_files)},
        {"title": "총 크기", "value": f"{total_size_mb:.1f} MB"},
        {"title": "상태", "value": "준비됨" if size_valid else "오류"}
    ]

    MetricCard.render_metric_grid(metrics, columns=3)


def _cancel_upload():
    """업로드 취소"""
    st.session_state.upload_complete = False
    _clear_uploader_widgets()
    rerun()


def process_multiple_file_upload(uploaded_files, api_client, upload_mode):
    """파일 업로드(단일/다중/압축) - 개선된 버전"""
    _init_upload_state()
    st.session_state.uploading = True

    # 로딩 표시
    LoadingSpinner.render_loading_screen(
        "파일 업로드 진행 중",
        f"{len(uploaded_files)}개 파일을 처리하고 있습니다..."
    )

    with ErrorContext("파일 업로드 처리") as ctx:
        try:
            p = st.progress(0)
            msg = st.empty()
            success_count = 0
            total_chunks = 0
            errors = []

            if HAS_FILE_UTILS and upload_manager:
                # 개선된 파일 처리
                results = upload_manager.process_uploaded_files(uploaded_files)

                # 성공 파일들 업로드
                total_files = len(results['success_files'])

                for i, info in enumerate(results['success_files']):
                    progress = i / max(total_files, 1)
                    p.progress(progress)

                    if info['type'] == 'document':
                        fo = info['file_obj']
                        msg.text(f'업로드 중: {fo.name}')

                        with ErrorContext(f"파일 업로드: {fo.name}", show_errors=False) as file_ctx:
                            try:
                                r = upload_single_file(fo, api_client)
                                if 'error' not in r:
                                    success_count += 1
                                    total_chunks += r.get('uploaded', 0)
                                    add_to_session_files(info.get('display_name') or fo.name, fo, r)
                                else:
                                    errors.append(f"{fo.name}: {r['error']}")
                            except Exception as e:
                                file_ctx.add_error(e)
                                errors.append(f"{fo.name}: {str(e)}")

                    else:  # extracted
                        fo = info['file_obj']
                        msg.text(f'업로드 중(압축해제): {fo.name}')

                        with ErrorContext(f"압축 파일 업로드: {fo.name}", show_errors=False) as file_ctx:
                            try:
                                r = upload_single_file(fo, api_client)
                                if 'error' not in r:
                                    success_count += 1
                                    total_chunks += r.get('uploaded', 0)
                                    add_to_session_extracted_file(info, r)
                                else:
                                    errors.append(f"{fo.name}(압축): {r['error']}")
                            except Exception as e:
                                file_ctx.add_error(e)
                                errors.append(f"{fo.name}(압축): {str(e)}")

                # 실패 파일들 추가
                for fail in results['failed_files']:
                    errors.append(f"{fail['name']}: {fail['error']}")

            else:
                # Fallback: 기본 처리
                for i, f in enumerate(uploaded_files):
                    progress = i / len(uploaded_files)
                    p.progress(progress)
                    msg.text(f'업로드 중: {f.name}')

                    with ErrorContext(f"기본 파일 업로드: {f.name}", show_errors=False) as file_ctx:
                        try:
                            r = upload_single_file(f, api_client)
                            if 'error' not in r:
                                success_count += 1
                                total_chunks += r.get('uploaded', 0)
                                add_to_session_files(f.name, f, r)
                            else:
                                errors.append(f"{f.name}: {r['error']}")
                        except Exception as e:
                            file_ctx.add_error(e)
                            errors.append(f"{f.name}: {str(e)}")

            # 완료 처리
            p.progress(1.0)
            msg.empty()

            if success_count > 0:
                StatusIndicator.render_status(
                    "success",
                    f"{success_count}개 파일 업로드 완료!",
                    f"총 {total_chunks}개 청크 생성"
                )
                show_upload_stats({
                    'uploaded': total_chunks,
                    'files_processed': success_count,
                    'errors': len(errors)
                })

            if errors:
                ErrorDisplay.render_validation_errors(errors[:5])  # 최대 5개만 표시

        except Exception as e:
            ctx.add_error(e)

        finally:
            st.session_state.uploading = False
            if success_count > 0:
                st.session_state.upload_complete = True
                _clear_uploader_widgets()
                rerun()


def upload_single_file(uploaded_file, api_client):
    """단일 파일 업로드 - 에러 처리 개선"""
    with ErrorContext("단일 파일 업로드", show_errors=False) as ctx:
        try:
            files = {
                'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
            }

            response = requests.post(
                f"{api_client.base_url}/v1/documents",
                files=files,
                timeout=(5, config.file.upload_timeout)
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_detail = response.json()
                    return {"error": f"업로드 실패 ({response.status_code}): {error_detail}"}
                except:
                    return {"error": f"업로드 실패 ({response.status_code}): {response.text}"}

        except Exception as e:
            ctx.add_error(e)
            return {"error": str(e)}


def add_to_session_files(display_name, uploaded_file, result):
    """세션에 업로드된 파일 정보 추가 - 개선된 버전"""
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []

    file_info = {
        'name': display_name,  # 정리된 표시명 사용
        'original_name': uploaded_file.name,  # 원본명 보존
        'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'chunks': result.get('uploaded', 0),
        'size': f"{uploaded_file.size / 1024 / 1024:.2f} MB",
        'type': 'document'
    }

    st.session_state.uploaded_files.append(file_info)


def add_to_session_extracted_file(extracted_file, result):
    """압축 파일에서 추출된 파일을 세션에 추가"""
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []

    # 파일명 정리
    if HAS_FILE_UTILS and FileNameCleaner:
        display_name = FileNameCleaner.clean_display_name(extracted_file['name'])
    else:
        display_name = extracted_file['name']

    file_info = {
        'name': display_name,
        'original_name': extracted_file['name'],
        'time': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'chunks': result.get('uploaded', 0),
        'size': f"{extracted_file['size'] / 1024 / 1024:.2f} MB",
        'type': 'extracted',
        'archive_path': extracted_file.get('path_in_archive', '')
    }

    st.session_state.uploaded_files.append(file_info)


def render_uploaded_files(api_client):
    """업로드된 파일 목록 렌더링 - 개선된 버전"""
    if 'uploaded_files' in st.session_state and st.session_state.uploaded_files:
        st.divider()
        st.header(f"{Constants.Icons.DOCUMENT} 업로드된 문서")

        # 필터 및 정렬 옵션
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            # 검색 필터
            search_filter = st.text_input(
                f"{Constants.Icons.SEARCH} 문서명 검색",
                placeholder="파일명으로 검색...",
                key="file_search_filter"
            )

        with col2:
            # 정렬 옵션
            sort_option = st.selectbox(
                "정렬 기준",
                ["최신순", "이름순", "크기순", "청크순", "타입순"],
                key="file_sort_option"
            )

        with col3:
            # 표시 모드
            view_mode = st.radio(
                "표시 방식",
                ["목록", "카드"],
                horizontal=True,
                key="file_view_mode"
            )

        # 파일 목록 필터링 및 정렬
        files = filter_and_sort_files(
            st.session_state.uploaded_files,
            search_filter,
            sort_option
        )

        # 파일 목록 표시
        if files:
            st.caption(f"총 {len(files)}개 문서 (전체: {len(st.session_state.uploaded_files)}개)")

            if view_mode == "목록":
                render_file_list_view(files, api_client)
            else:
                render_file_card_view(files, api_client)
        else:
            if search_filter:
                StatusIndicator.render_status("info", f"'{search_filter}'에 대한 검색 결과가 없습니다")
            else:
                StatusIndicator.render_status("info", "업로드된 문서가 없습니다")


def filter_and_sort_files(files, search_filter, sort_option):
    """파일 목록 필터링 및 정렬"""
    filtered_files = files.copy()

    # 검색 필터 적용
    if search_filter:
        filtered_files = [f for f in filtered_files
                         if search_filter.lower() in f.get('name', '').lower()]

    # 정렬 적용
    if sort_option == "최신순":
        filtered_files = sorted(filtered_files, key=_file_time_key, reverse=True)
    elif sort_option == "이름순":
        filtered_files = sorted(filtered_files, key=lambda x: x.get('name', '').lower())
    elif sort_option == "크기순":
        filtered_files = sorted(filtered_files, key=lambda x: _size_to_mb(x.get('size', '0')), reverse=True)
    elif sort_option == "청크순":
        filtered_files = sorted(filtered_files, key=lambda x: x.get('chunks', 0), reverse=True)
    elif sort_option == "타입순":
        filtered_files = sorted(filtered_files, key=lambda x: x.get('type', ''))

    return filtered_files


def render_file_list_view(files, api_client):
    """파일 목록을 리스트 형태로 표시 (업로드/생성/수정 시간 별도 열)"""
    import streamlit as st
    from frontend.ui.core.config import config, Constants

    # ── Header ────────────────────────────────────────────────────────
    col_select, col_name, col_type, col_uploaded, col_created, col_modified, col_size, col_chunks, col_action = st.columns(
        [0.5, 3, 1, 1.3, 1.3, 1.3, 1, 1, 1]
    )

    with col_select:
        select_all = st.checkbox("전체선택", key="select_all_files", label_visibility="visible")
    with col_name:
        st.write("**파일명**")
    with col_type:
        st.write("**타입**")
    with col_uploaded:
        st.write("**업로드**")
    with col_created:
        st.write("**생성**")
    with col_modified:
        st.write("**수정**")
    with col_size:
        st.write("**크기**")
    with col_chunks:
        st.write("**청크**")
    with col_action:
        st.write("**작업**")

    st.divider()

    # ── Pagination helpers ────────────────────────────────────────────
    files_per_page = config.ui.default_page_size
    total_pages = (len(files) + files_per_page - 1) // files_per_page
    page = (
        st.number_input("페이지", 1, total_pages if total_pages else 1, 1) - 1
        if total_pages > 1
        else 0
    )

    start_idx = page * files_per_page
    end_idx = min(start_idx + files_per_page, len(files))

    selected_files = []

    for idx, file in enumerate(files[start_idx:end_idx]):
        (
            col_select,
            col_name,
            col_type,
            col_uploaded,
            col_created,
            col_modified,
            col_size,
            col_chunks,
            col_action,
        ) = st.columns([0.5, 3, 1, 1.3, 1.3, 1.3, 1, 1, 1])

        # 선택 체크박스
        with col_select:
            import hashlib
            import re
            file_key = file.get("original_name") or file.get("name")

            # 1️⃣ 깨끗한 basename
            base = re.sub(r"[^0-9a-zA-Z_]", "_", file_key)  # 특수문자→_
            base = re.sub(r"_+", "_", base).strip("_")[:40]  # 40자 제한
            # 2️⃣ 충돌 방지를 위한 6-글자 MD5 해시
            digest = hashlib.md5(file_key.encode()).hexdigest()[:6]
            # 3️⃣ 페이지 내 인덱스까지 붙여 완전 고유화
            checkbox_key = f"select_file_{base}_{digest}_{start_idx + idx}"

            is_selected = st.checkbox(
                "선택",
                key=checkbox_key,
                value=select_all,
                label_visibility="collapsed",
            )

            if is_selected:
                selected_files.append(file)

        # 파일명 + 아이콘
        with col_name:
            icon = get_file_type_icon(file.get("name", ""))
            display_name = file.get("name", "Unknown")
            st.write(f"{icon} **{display_name}**")

            original_name = file.get("original_name", "")
            if original_name and original_name != display_name:
                st.caption(f"원본: {original_name}")

            if file.get("type") == "extracted" and file.get("archive_path"):
                st.caption(f"{Constants.Icons.FILE_ICONS['zip']} {file['archive_path']}")

        # 타입
        with col_type:
            file_type = file.get("type", "document")
            type_display = {
                "document": f"{Constants.Icons.DOCUMENT} 문서",
                "extracted": f"{Constants.Icons.FILE_ICONS['zip']} 추출",
                "image": f"{Constants.Icons.FILE_ICONS['png']} 이미지",
            }.get(file_type, f"{Constants.Icons.FILE_ICONS['default']} 파일")
            st.write(type_display)

        # 개별 시간 컬럼
        with col_uploaded:
            st.write(file.get("uploaded", "-"))
        with col_created:
            st.write(file.get("created", "-"))
        with col_modified:
            st.write(file.get("modified", "-"))

        # 크기
        with col_size:
            st.write(file.get("size", "-"))

        # 청크
        with col_chunks:
            chunks = file.get("chunks", 0)
            st.success(f"{chunks}") if chunks else st.warning("0")

        # 액션 버튼
        with col_action:
            if st.button(Constants.Icons.DELETE, key=f"delete_file_{start_idx + idx}", help="삭제"):
                delete_file_from_session_and_server(file, api_client)

    # 하단 페이지네이션 정보
    if total_pages > 1:
        st.caption(f"페이지 {page + 1} / {total_pages}")

    # 일괄 작업
    if selected_files:
        render_bulk_actions(selected_files, api_client)


import streamlit as _st
if "_narrow_row_css" not in _st.session_state:
    _st.session_state["_narrow_row_css"] = True
    _st.markdown(
        """
        <style>
        div[data-testid="column"] > div {
            margin-top: 0.15rem !important;
            margin-bottom: 0.15rem !important;
        }
        label[data-testid="stCheckboxLabel"] { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_file_card_view(files, api_client):
    """파일 목록을 카드 형태로 표시"""
    cards_per_row = 3

    for i in range(0, len(files), cards_per_row):
        cols = st.columns(cards_per_row)

        for j in range(cards_per_row):
            if i + j < len(files):
                file = files[i + j]

                with cols[j]:
                    # 파일 액션 정의
                    actions = [
                        {
                            "icon": f"{Constants.Icons.STATUS_INFO}",
                            "help": "상세보기",
                            "key": f"view_card_{i+j}",
                            "callback": lambda f=file: show_file_details(f)
                        },
                        {
                            "icon": f"{Constants.Icons.DELETE}",
                            "help": "삭제",
                            "key": f"delete_card_{i+j}",
                            "callback": lambda f=file: delete_file_from_session_and_server(f, api_client)
                        }
                    ]

                    FileDisplay.render_file_card(file, actions)


def render_bulk_actions(selected_files, api_client):
    """일괄 작업 UI"""
    st.divider()
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.write(f"**{len(selected_files)}개 파일 선택됨**")

    with col2:
        if st.button(f"{Constants.Icons.STATUS_INFO} 통계 보기", key="show_selected_stats"):
            show_selected_files_stats(selected_files)

    with col3:
        if st.button(f"{Constants.Icons.DELETE} 선택 삭제", key="delete_selected_files"):
            delete_selected_files(selected_files, api_client)


def show_selected_files_stats(selected_files):
    """선택된 파일들의 통계 표시"""
    total_chunks = sum(f.get('chunks', 0) for f in selected_files)
    total_size_mb = sum(_size_to_mb(f.get('size', '0')) for f in selected_files)

    file_types = {}
    for f in selected_files:
        ftype = f.get('type', 'document')
        file_types[ftype] = file_types.get(ftype, 0) + 1

    with st.expander(f"{Constants.Icons.STATUS_INFO} 선택된 파일 통계", expanded=True):
        metrics = [
            {"title": "선택된 파일", "value": len(selected_files)},
            {"title": "총 청크", "value": total_chunks},
            {"title": "총 크기", "value": f"{total_size_mb:.1f} MB"}
        ]

        MetricCard.render_metric_grid(metrics, columns=3)

        if file_types:
            st.write("**타입별 분포:**")
            for ftype, count in file_types.items():
                st.write(f"• {ftype}: {count}개")


def delete_file_from_session_and_server(file, api_client):
    """파일을 세션과 서버에서 삭제 - 에러 처리 개선"""
    with ErrorContext("파일 삭제") as ctx:
        try:
            # 서버에서 삭제 (원본명 사용)
            file_name_for_deletion = file.get('original_name', file.get('name'))
            api_client.delete_document(file_name_for_deletion)

            # 세션에서 제거
            st.session_state.uploaded_files.remove(file)
            _reset_file_selection_state()
            StatusIndicator.render_status("success", f"'{file.get('name')}' 파일이 삭제되었습니다")
            rerun()

        except Exception as e:
            ctx.add_error(e)


def delete_selected_files(selected_files, api_client):
    """선택된 파일들을 일괄 삭제 - 개선된 버전"""
    if not selected_files:
        return

    # 확인 다이얼로그
    if st.session_state.get('confirm_delete_selected') != True:
        st.session_state.confirm_delete_selected = True
        StatusIndicator.render_status(
            "warning",
            f"{len(selected_files)}개 파일을 삭제하시겠습니까?",
            "다시 클릭하여 확인하세요"
        )
        return

    success_count = 0
    error_count = 0

    with st.spinner(f"{len(selected_files)}개 파일 삭제 중..."):
        for file in selected_files:
            with ErrorContext(f"파일 삭제: {file.get('name')}", show_errors=False) as ctx:
                try:
                    # 서버에서 삭제
                    file_name_for_deletion = file.get('original_name', file.get('name'))
                    api_client.delete_document(file_name_for_deletion)

                    # 세션에서 제거
                    if file in st.session_state.uploaded_files:
                        st.session_state.uploaded_files.remove(file)

                    success_count += 1

                except Exception as e:
                    ctx.add_error(e)
                    error_count += 1

    # 확인 플래그 리셋
    if 'confirm_delete_selected' in st.session_state:
        del st.session_state.confirm_delete_selected

    # 결과 표시
    if success_count > 0:
        StatusIndicator.render_status("success", f"{success_count}개 파일이 삭제되었습니다")

    if error_count > 0:
        ErrorDisplay.render_error_with_suggestions(
            f"{error_count}개 파일 삭제에 실패했습니다",
            ["네트워크 연결을 확인하세요", "서버 상태를 확인하세요"]
        )

    _reset_file_selection_state()
    rerun()


def get_upload_summary(api_client=None, sync_with_server: bool = True) -> Dict:
    """
    업로드 요약 정보 반환 - 서버 동기화 지원 버전

    Args:
        api_client: API 클라이언트 (서버 동기화용)
        sync_with_server: 서버와 동기화 여부

    Returns:
        업로드 요약 정보
    """
    try:
        # 서버와 동기화 옵션
        if sync_with_server and api_client:
            try:
                # 서버 동기화 실행
                sync_result = api_client.sync_local_with_server_documents()

                if sync_result.get("status") == "success":
                    # 동기화된 문서로 세션 상태 업데이트
                    synced_docs = sync_result.get("synced_documents", [])
                    if 'uploaded_files' not in st.session_state:
                        st.session_state.uploaded_files = []

                    st.session_state.uploaded_files = synced_docs

                    logger.info(f"📊 서버 동기화 완료: {len(synced_docs)}개 문서")

                    # 동기화된 데이터로 통계 계산
                    total_chunks = sum(doc.get('chunks', 0) for doc in synced_docs)
                    total_size = sum(_size_to_mb(doc.get('size', '0')) for doc in synced_docs)

                    return {
                        'total_files': len(synced_docs),
                        'total_chunks': total_chunks,
                        'total_size': total_size,
                        'source': 'server_sync',
                        'last_sync': sync_result.get('sync_time'),
                        'server_total': sync_result.get('server_total', 0),
                        'server_chunks': sync_result.get('server_chunks', 0)
                    }
                else:
                    logger.warning(f"⚠️ 서버 동기화 실패: {sync_result.get('message', 'Unknown error')}")

            except Exception as e:
                logger.warning(f"⚠️ 서버 동기화 실패: {str(e)}, 로컬 데이터 사용")

        # 로컬 세션 데이터 사용 (기존 로직)
        if 'uploaded_files' not in st.session_state:
            return {
                'total_files': 0,
                'total_chunks': 0,
                'total_size': 0,
                'source': 'local',
                'last_sync': None
            }

        files = st.session_state.uploaded_files
        total_chunks = sum(f.get('chunks', 0) for f in files)
        total_size = sum(_size_to_mb(f.get('size', '0')) for f in files)

        return {
            'total_files': len(files),
            'total_chunks': total_chunks,
            'total_size': total_size,
            'source': 'local',
            'last_sync': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ 업로드 요약 생성 오류: {str(e)}")
        return {
            'total_files': 0,
            'total_chunks': 0,
            'total_size': 0,
            'source': 'error',
            'error': str(e)
        }


def show_upload_stats(result: Dict):
    """업로드 통계 표시 - 메트릭 카드 사용"""
    with st.expander(f"{Constants.Icons.STATUS_INFO} 처리 통계", expanded=True):
        metrics = [
            {
                "title": "처리된 파일",
                "value": result.get('files_processed', 0),
                "help": "성공적으로 업로드된 파일 수"
            },
            {
                "title": "생성된 청크",
                "value": result.get('uploaded', 0),
                "help": "문서에서 생성된 총 청크 수"
            },
            {
                "title": "오류",
                "value": result.get('errors', 0),
                "delta": "문제" if result.get('errors', 0) > 0 else None,
                "help": "처리 중 발생한 오류 수"
            }
        ]

        MetricCard.render_metric_grid(metrics, columns=3)

        # 추가 정보
        if result.get('avg_chunk_size'):
            st.caption(f"평균 청크 크기: {result['avg_chunk_size']:.0f} 문자")

        if result.get('processing_time'):
            st.caption(f"처리 시간: {result['processing_time']:.2f} 초")


def show_file_details(file):
    """파일 상세 정보 표시 - 개선된 버전"""
    with st.expander(f"{Constants.Icons.DOCUMENT} {file.get('name', 'Unknown')} 상세 정보", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.write("**기본 정보**")
            st.write(f"표시명: {file.get('name', 'Unknown')}")
            if file.get('original_name') != file.get('name'):
                st.write(f"원본명: {file.get('original_name', 'Unknown')}")
            st.write(f"업로드 시간: {file.get('time', 'Unknown')}")
            st.write(f"파일 크기: {file.get('size', 'Unknown')}")

        with col2:
            st.write("**처리 정보**")
            chunks = file.get('chunks', 0)
            if chunks > 0:
                st.metric("청크 수", chunks)
            else:
                st.warning("청크 수: 0 (처리 실패)")

            st.write(f"파일 타입: {file.get('type', 'document')}")
            if file.get('archive_path'):
                st.write(f"압축 내 경로: {file.get('archive_path')}")

        # 파일 아이콘 표시
        icon = get_file_type_icon(file.get('name', ''))
        st.write(f"파일 아이콘: {icon}")


def get_file_type_icon(filename):
    """파일 타입에 따른 아이콘 반환 - 설정 기반"""
    if not filename:
        return Constants.Icons.FILE_ICONS['default']

    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    return Constants.Icons.FILE_ICONS.get(ext, Constants.Icons.FILE_ICONS['default'])


def _size_to_mb(size_str: str) -> float:
    """크기 문자열을 MB로 변환"""
    try:
        import re
        match = re.search(r'([\d.]+)', str(size_str))
        return float(match.group()) if match else 0.0
    except:
        return 0.0


def _file_time_key(f):
    """파일 시간 정렬 키"""
    t = f.get('time')
    # 이미 datetime 객체라면 그대로
    if isinstance(t, datetime):
        return t
    # 문자열이라면 시도해 보기
    if isinstance(t, str) and t:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(t, fmt)
            except ValueError:
                pass
    # 파싱 실패 또는 None → 가장 오래된 값으로
    return datetime.min


def _reset_file_selection_state():
    """행 삭제 후 남아있는 체크박스 상태를 모두 없앤다."""
    for k in list(st.session_state.keys()):
        if k.startswith("select_file_") or k == "select_all_files":
            del st.session_state[k]


def _fmt_timestamp(ts):
    """Return local‑time formatted string for various timestamp encodings."""
    if not ts:
        return "-"
    try:
        if isinstance(ts, (int, float)):
            # epoch milliseconds or seconds
            ts = ts / 1000 if ts > 1e12 else ts
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            # ISO‑8601 string; allow trailing Z
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)


def _init_upload_state():
    """업로드 상태 초기화"""
    if 'upload_complete' not in st.session_state:
        st.session_state.upload_complete = False
    if 'uploading' not in st.session_state:
        st.session_state.uploading = False


def _normalize_server_files(server_files: List[Dict[str, Any]]):
    """Convert raw API data to front‑end friendly dictionaries.

    Adds human‑readable time fields (uploaded/created/modified) that the list‑view
    uses as separate columns. Keeps original keys intact so that older UI parts
    depending on them continue to work.
    """
    normalized = []
    for f in server_files:
        item = dict(f)  # shallow copy
        item["uploaded"] = _fmt_timestamp(f.get("uploaded_at") or f.get("uploaded"))
        item["created"] = _fmt_timestamp(f.get("created_at") or f.get("created"))
        item["modified"] = _fmt_timestamp(f.get("modified_at") or f.get("modified"))
        # keep legacy multiline field for backward compatibility
        item["time"] = "\n".join(filter(None, [item["uploaded"], item["created"], item["modified"]]))
        normalized.append(item)
    return normalized


def _clear_uploader_widgets():
    """업로더 위젯 상태 초기화"""
    widget_keys = ['single_file_uploader', 'multi_file_uploader', 'archive_file_uploader']
    for key in widget_keys:
        if key in st.session_state:
            st.session_state.pop(key, None)


# 업로드된 파일에서 추출된 파일 업로드 (기존 함수 유지)
def upload_extracted_file(extracted_file, api_client):
    """압축 파일에서 추출된 파일 업로드"""
    with ErrorContext("압축 추출 파일 업로드", show_errors=False) as ctx:
        try:
            files = {
                'file': (extracted_file['name'], extracted_file['content'], extracted_file['type'])
            }

            response = requests.post(
                f"{api_client.base_url}/v1/documents",
                files=files,
                timeout=(5, config.file.upload_timeout)
            )

            if response.status_code == 200:
                return response.json()
            else:
                try:
                    error_detail = response.json()
                    return {"error": f"업로드 실패 ({response.status_code}): {error_detail}"}
                except:
                    return {"error": f"업로드 실패 ({response.status_code}): {response.text}"}

        except Exception as e:
            ctx.add_error(e)
            return {"error": str(e)}


# 호환성을 위한 기존 함수명 유지
render_file_uploader_original = render_file_uploader
render_uploaded_files_original = render_uploaded_files


# 추가 유틸리티 함수
def get_upload_progress_info():
    """현재 업로드 진행 상황 정보 반환"""
    return {
        'is_uploading': st.session_state.get('uploading', False),
        'upload_complete': st.session_state.get('upload_complete', False),
        'total_uploaded': len(st.session_state.get('uploaded_files', [])),
        'total_chunks': sum(f.get('chunks', 0) for f in st.session_state.get('uploaded_files', []))
    }


def clear_all_uploaded_files(api_client):
    """모든 업로드된 파일 삭제"""
    if 'uploaded_files' not in st.session_state or not st.session_state.uploaded_files:
        StatusIndicator.render_status("info", "삭제할 파일이 없습니다")
        return

    # 확인 다이얼로그
    if st.session_state.get('confirm_clear_all') != True:
        st.session_state.confirm_clear_all = True
        StatusIndicator.render_status(
            "warning",
            f"모든 파일({len(st.session_state.uploaded_files)}개)을 삭제하시겠습니까?",
            "다시 클릭하여 확인하세요"
        )
        return

    # 모든 파일 삭제
    delete_selected_files(st.session_state.uploaded_files.copy(), api_client)

    # 확인 플래그 리셋
    if 'confirm_clear_all' in st.session_state:
        del st.session_state.confirm_clear_all


def export_uploaded_files_list():
    """업로드된 파일 목록 내보내기"""
    if 'uploaded_files' not in st.session_state or not st.session_state.uploaded_files:
        StatusIndicator.render_status("info", "내보낼 파일 목록이 없습니다")
        return

    import json

    export_data = {
        "exported_at": datetime.now().isoformat(),
        "total_files": len(st.session_state.uploaded_files),
        "files": st.session_state.uploaded_files,
        "summary": get_upload_summary()
    }

    st.download_button(
        label=f"{Constants.Icons.DOWNLOAD} 파일 목록 다운로드",
        data=json.dumps(export_data, ensure_ascii=False, indent=2),
        file_name=f"uploaded_files_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        help="업로드된 파일 목록을 JSON으로 내보냅니다"
    )


def render_upload_actions_panel(api_client):  # ✅ api_client 추가
    """업로드 관련 액션 패널"""
    st.subheader(f"{Constants.Icons.SETTINGS} 파일 관리")

    # 기존 actions 배열과 ActionButton.render_action_row 삭제하고 아래 코드로 교체
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(
                f"{Constants.Icons.STATUS_INFO} 통계 보기",
                key="show_upload_stats_panel",
                type="secondary",
                use_container_width=True
        ):
            show_upload_summary_panel()

    with col2:
        if st.button(
                f"{Constants.Icons.DOWNLOAD} 목록 내보내기",
                key="export_files_panel",
                type="secondary",
                use_container_width=True
        ):
            export_uploaded_files_list()

    with col3:
        if st.button(
                f"{Constants.Icons.DELETE} 전체 삭제",
                key="clear_all_files_panel",
                type="secondary",
                use_container_width=True
        ):
            clear_all_uploaded_files(api_client)


def show_upload_summary_panel():
    """업로드 요약 패널 표시"""
    summary = get_upload_summary()

    with st.expander(f"{Constants.Icons.STATUS_INFO} 업로드 요약", expanded=True):
        metrics = [
            {"title": "총 파일", "value": summary['total_files']},
            {"title": "총 청크", "value": summary['total_chunks']},
            {"title": "총 크기", "value": f"{summary['total_size']:.1f} MB"}
        ]

        MetricCard.render_metric_grid(metrics, columns=3)

        # 파일 타입별 분포
        if st.session_state.get('uploaded_files'):
            file_types = {}
            for f in st.session_state.uploaded_files:
                ftype = f.get('type', 'document')
                file_types[ftype] = file_types.get(ftype, 0) + 1

            if file_types:
                st.write("**파일 타입별 분포:**")
                for ftype, count in file_types.items():
                    percentage = (count / summary['total_files']) * 100
                    st.write(f"• {ftype}: {count}개 ({percentage:.1f}%)")


# 메인 업로드 인터페이스 함수 (선택적 사용)
def render_complete_upload_interface(api_client):
    """완전한 업로드 인터페이스 렌더링"""
    st.title(f"{Constants.Icons.UPLOAD} 문서 업로드 시스템")

    # 시스템 상태 확인
    if HAS_FILE_UTILS:
        StatusIndicator.render_status("success", "고급 파일 처리 기능 활성화됨")
    else:
        StatusIndicator.render_status("warning", "기본 파일 처리 모드",
                                    "file_utils 모듈을 설치하면 더 많은 기능을 사용할 수 있습니다")

    # 설정 정보 표시
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("최대 파일 크기", f"{MAX_FILE_SIZE_MB} MB")
    with col2:
        st.metric("최대 압축 파일", f"{MAX_ARCHIVE_SIZE_MB} MB")
    with col3:
        st.metric("지원 확장자", len(ALLOWED_EXTENSIONS))

    st.divider()

    # 메인 업로드 인터페이스
    render_file_uploader(api_client)

    # 업로드된 파일 관리
    render_uploaded_files(api_client)

    # 추가 액션 패널
    if st.session_state.get('uploaded_files'):
        st.divider()
        render_upload_actions_panel(api_client)