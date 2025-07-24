"""
문서 관리 페이지 (개선 v5 - 오류 수정)
============================================================
- **강화된 API 응답 검증**: 다양한 응답 형태에 대한 견고한 처리
- **재시도 메커니즘**: 네트워크 오류 시 자동 재시도
- **상세한 로깅**: 문제 진단을 위한 상세 로그
- **사용자 친화적 오류 메시지**: 명확한 오류 원인과 해결 방법 제시
- **로딩 상태 표시**: 실시간 로딩 진행 상황 표시
- **완전한 통계 대시보드**: 인터랙티브 차트 및 분석 기능
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple, Optional
import logging
import time
import requests
import json

import pandas as pd
import streamlit as st

# Plotly imports (최적 통계 기능용)
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("⚠️ Plotly가 설치되지 않아 고급 차트 기능이 제한됩니다. `pip install plotly` 로 설치하세요.")

# ─────────────────────────────── Setup ────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from frontend.ui.utils.streamlit_helpers import rerun, set_page_config_safe
from frontend.ui.utils.client_manager import ClientManager
from frontend.ui.utils.file_utils import FileNameCleaner, FileUtils
from frontend.ui.components.uploader import (
    render_file_uploader,
    filter_and_sort_files,
    render_file_list_view,
    render_file_card_view,
    _reset_file_selection_state,
)
from frontend.ui.components.common import StatusIndicator, Constants

# 로깅 설정
logger = logging.getLogger(__name__)

# ───────────────────────────── Page Config ────────────────────────────
set_page_config_safe(
    page_title="문서 관리 · GTOne RAG",
    page_icon="📄",
    layout="wide",
)

api_client = ClientManager.get_client()

st.title("📄 문서 관리")
st.caption("업로드된 문서를 관리하고 새로운 문서를 추가합니다.")

# ── 탭 재배치 로직 ───────────────────────────────────
_ALL_TABS = ["📤 새 문서 업로드", "📁 문서 목록", "📊 통계"]
active_tab = st.session_state.get("active_docs_tab", _ALL_TABS[0])
if active_tab not in _ALL_TABS:
    active_tab = _ALL_TABS[0]
ordered = [active_tab] + [t for t in _ALL_TABS if t != active_tab]
_tabs = st.tabs(ordered)
TAB_MAP = {lbl: _tabs[i] for i, lbl in enumerate(ordered)}
TAB_UPLOAD = TAB_MAP["📤 새 문서 업로드"]
TAB_LIST   = TAB_MAP["📁 문서 목록"]
TAB_STATS  = TAB_MAP["📊 통계"]


# ───────────────────────────── Helpers ────────────────────────────────

NULL_EQUIV = {None, "", "none", "null", "None", "NULL"}

def _null_if_empty(val: Any):
    return None if val in NULL_EQUIV else val


def _parse_timestamp(ts_raw: Any) -> str:
    """다양한 형태(ISO/epoch/None) → 'YYYY‑MM‑DD HH:MM' 또는 '-'"""
    ts_raw = _null_if_empty(ts_raw)
    if ts_raw is None:
        return "-"
    try:
        # epoch in seconds
        if isinstance(ts_raw, (int, float)) and ts_raw > 1e10:
            ts_raw = ts_raw / 1000  # milliseconds → seconds
        ts = datetime.fromtimestamp(ts_raw) if isinstance(ts_raw, (int, float)) else pd.to_datetime(ts_raw)
        return ts.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts_raw)


def _format_size(size_raw: Any) -> str:
    """bytes/int/str → '?.? MB' or '-'."""
    size_raw = _null_if_empty(size_raw)
    if size_raw is None:
        return "-"
    try:
        if isinstance(size_raw, str) and size_raw.isdigit():
            size_raw = int(size_raw)
        if isinstance(size_raw, (int, float)):
            return FileUtils.format_file_size(size_raw)
        # 이미 '?.? MB' 형태면 그대로
        if any(unit in str(size_raw) for unit in ("KB", "MB", "GB")):
            return str(size_raw)
    except Exception:
        pass
    return str(size_raw)


def _normalize_server_files(files: Any) -> List[Dict[str, Any]]:
    """API 응답을 UI‑friendly 구조로 변환 (최적화된 오류 처리)"""

    # 상세 로깅
    logger.info(f"🔄 파일 정규화 시작: 입력 타입 {type(files)}")

    # 입력 타입 검증 및 정규화
    if files is None:
        logger.warning("⚠️ API 응답이 None입니다")
        return []

    if isinstance(files, str):
        logger.error(f"❌ API 응답이 문자열입니다 (길이: {len(files)})")
        logger.debug(f"📝 응답 내용: {files[:200]}...")

        # JSON 문자열인지 확인 시도
        try:
            parsed = json.loads(files)
            logger.info("✅ JSON 문자열을 성공적으로 파싱했습니다")
            return _normalize_server_files(parsed)
        except json.JSONDecodeError:
            logger.error("❌ JSON 파싱 실패 - 순수 문자열입니다")
            return []

    if isinstance(files, dict):
        logger.info(f"📊 dict 응답 - 키들: {list(files.keys())}")

        # 문서 목록을 찾기 위한 키 우선순위
        document_keys = ["documents", "items", "data", "files", "results"]

        for key in document_keys:
            if key in files and isinstance(files[key], list):
                logger.info(f"✅ '{key}' 키에서 문서 목록 발견: {len(files[key])}개")
                return _normalize_server_files(files[key])

        # 오류 메시지가 있는지 확인
        if "error" in files:
            logger.error(f"❌ API 오류 응답: {files['error']}")
            return []

        # dict 자체가 문서인지 확인 (단일 문서 응답)
        if "name" in files or "id" in files:
            logger.info("📄 단일 문서 응답으로 판단")
            return _normalize_server_files([files])

        logger.warning(f"⚠️ dict에서 문서 목록을 찾을 수 없습니다")
        logger.debug(f"📋 사용 가능한 키: {list(files.keys())}")
        return []

    if not isinstance(files, (list, tuple)):
        logger.error(f"❌ 지원하지 않는 응답 타입: {type(files)}")
        logger.debug(f"📝 응답 내용: {str(files)[:200]}...")
        return []

    if not files:
        logger.info("📋 빈 문서 목록")
        return []

    logger.info(f"📊 {len(files)}개 항목 정규화 시작")

    normalized: List[Dict[str, Any]] = []
    error_count = 0

    for idx, f in enumerate(files):
        try:
            # 개별 파일 항목 검증
            if f is None:
                logger.warning(f"⚠️ 파일 {idx}: None 값, 건너뜀")
                error_count += 1
                continue

            if not isinstance(f, dict):
                logger.warning(f"⚠️ 파일 {idx}: dict가 아님 ({type(f)}), 건너뜀")
                logger.debug(f"📝 내용: {str(f)[:100]}...")
                error_count += 1
                continue

            # 필수 필드 확인
            if not any(key in f for key in ["name", "id", "filename", "title"]):
                logger.warning(f"⚠️ 파일 {idx}: 식별 가능한 이름 필드 없음, 건너뜀")
                logger.debug(f"📋 사용 가능한 키: {list(f.keys())}")
                error_count += 1
                continue

            # 파일명 처리
            original_name = (
                f.get("name") or
                f.get("filename") or
                f.get("title") or
                f.get("id") or
                f"Unknown_File_{idx}"
            )

            display_name = (
                FileNameCleaner.clean_display_name(original_name)
                if hasattr(FileNameCleaner, "clean_display_name")
                else original_name
            )

            # 크기 정보 처리
            size_raw = _null_if_empty(
                f.get("size") or
                f.get("file_size") or
                f.get("filesize") or
                f.get("bytes")
            )
            size_display = _format_size(size_raw)

            # 시간 정보 처리
            uploaded_display = _parse_timestamp(
                f.get("uploaded_at") or
                f.get("time") or
                f.get("upload_time") or
                f.get("created_at")
            )

            created_display = _parse_timestamp(
                f.get("created_at") or
                f.get("created") or
                f.get("creation_time")
            )

            modified_display = _parse_timestamp(
                f.get("modified_at") or
                f.get("updated_at") or
                f.get("last_modified")
            )

            # 시간 정보 멀티라인 구성
            time_multiline = uploaded_display
            extra_parts = []

            if created_display != "-" and created_display != uploaded_display:
                extra_parts.append(f"생성 {created_display}")

            if modified_display != "-" and modified_display not in {uploaded_display, created_display}:
                extra_parts.append(f"수정 {modified_display}")

            if extra_parts:
                time_multiline += "\n" + "\n".join(extra_parts)

            # 청크 정보 처리
            chunks = max(0, int(f.get("chunks", 0) or 0))

            normalized_item = {
                **f,  # 원본 데이터 보존
                "original_name": original_name,
                "name": display_name,
                "size": size_display,
                "size_bytes": size_raw or 0,
                "chunks": chunks,
                "time": time_multiline,
                "uploaded": uploaded_display,
                "created": created_display,
                "modified": modified_display,
                "processing_status": "success"
            }

            normalized.append(normalized_item)

            if idx % 10 == 0:  # 진행 상황 로깅
                logger.debug(f"📊 진행 상황: {idx + 1}/{len(files)} 처리됨")

        except Exception as e:
            logger.error(f"❌ 파일 {idx} 처리 중 오류: {str(e)}")
            logger.debug(f"🏷️ 오류 타입: {type(e).__name__}")
            if hasattr(f, 'keys'):
                logger.debug(f"📋 문제 항목 키: {list(f.keys()) if isinstance(f, dict) else 'N/A'}")
            error_count += 1
            continue

    # 최종 결과 로깅
    success_count = len(normalized)
    logger.info(f"✅ 정규화 완료: 성공 {success_count}개, 오류 {error_count}개")

    if error_count > 0:
        logger.warning(f"⚠️ {error_count}개 항목 처리 실패 (전체 {len(files)}개 중)")

    return normalized


# ───────────────────────────── (1) 업로드 ─────────────────────────────
with TAB_UPLOAD:
    render_file_uploader(api_client)
    with st.expander("💡 업로드 팁"):
        st.markdown(
            """
- **PDF**는 *텍스트 기반* PDF가 가장 정확합니다.
- **이미지**는 OCR로 텍스트 추출 후 분석합니다.
- **50 MB 초과** 파일은 분할 업로드가 필요합니다.
            """
        )

# ───────────────────────────── (2) 목록 ──────────────────────────────
with TAB_LIST:
    st.header("📁 업로드된 문서")

    # 새로고침 버튼
    col_refresh, _ = st.columns([1, 9])
    with col_refresh:
        if st.button("🔄 새로고침", key="refresh_doc_list", use_container_width=True):
            _reset_file_selection_state()
            st.session_state.force_refresh = True
            st.session_state.active_docs_tab = "📁 문서 목록"
            # 세션 상태 완전 초기화
            if 'uploaded_files' in st.session_state:
                del st.session_state.uploaded_files
            if 'last_documents_error' in st.session_state:
                del st.session_state.last_documents_error
            rerun()

    # 문서 로드
    if (
            "uploaded_files" not in st.session_state
            or st.session_state.get("force_refresh", False)
    ):
        try:
            with st.spinner("📋 문서 목록을 불러오는 중..."):
                # 새로운 API 클라이언트 방식 사용
                if hasattr(api_client, 'list_documents'):
                    # 파라미터를 명시적으로 전달
                    response = api_client.list_documents(
                        stats_only=False,
                        include_details=True
                    )

                    # 응답이 dict 형태인 경우
                    if isinstance(response, dict):
                        server_files = response.get("documents", [])
                        if response.get("error"):
                            st.error(f"API 오류: {response['error']}")
                            st.session_state.uploaded_files = []
                            st.session_state.force_refresh = False
                            st.stop()
                    else:
                        # 응답이 직접 list인 경우
                        server_files = response
                else:
                    # 기존 방식 fallback
                    server_files = api_client.list_documents()

                # 안전한 정규화
                if isinstance(server_files, list):
                    st.session_state.uploaded_files = _normalize_server_files(server_files)
                elif isinstance(server_files, dict):
                    # dict에서 문서 목록 추출
                    documents = server_files.get("documents", server_files.get("items", []))
                    st.session_state.uploaded_files = _normalize_server_files(documents)
                else:
                    st.error(f"예상하지 못한 응답 형태: {type(server_files)}")
                    st.session_state.uploaded_files = []

                st.session_state.force_refresh = False

                # 성공 메시지
                doc_count = len(st.session_state.uploaded_files)
                if doc_count > 0:
                    st.success(f"✅ {doc_count}개 문서를 성공적으로 불러왔습니다!")
                else:
                    st.info("📋 업로드된 문서가 없습니다.")

        except Exception as e:
            st.error(f"❌ 문서 목록 로드 실패: {str(e)}")
            st.error(f"오류 타입: {type(e).__name__}")

            # 상세 오류 정보
            with st.expander("🔧 상세 오류 정보"):
                import traceback

                st.code(traceback.format_exc())

                # API 응답 테스트
                try:
                    st.write("### API 직접 테스트")
                    raw_response = api_client.list_documents() if hasattr(api_client, 'list_documents') else "메서드 없음"
                    st.write(f"원본 응답 타입: {type(raw_response)}")
                    st.write(f"원본 응답 (처음 200자): {str(raw_response)[:200]}...")
                except Exception as e2:
                    st.write(f"API 테스트 실패: {str(e2)}")

            st.session_state.uploaded_files = []
            st.session_state.force_refresh = False

    # 문서 목록 표시
    files = st.session_state.get("uploaded_files", [])

    if not files:
        st.info("표시할 문서가 없습니다.")
        st.markdown("### 📤 문서를 업로드해보세요!")
        if st.button("📤 업로드 페이지로 이동", use_container_width=True):
            st.session_state.active_docs_tab = "📤 새 문서 업로드"
            rerun()
    else:
        # 필터 및 정렬 UI
        col_search, col_sort, col_view = st.columns([3, 2, 2])

        with col_search:
            search_filter = st.text_input("🔍 문서명 검색", placeholder="파일명 입력")

        with col_sort:
            sort_option = st.selectbox(
                "정렬 기준",
                [
                    "최신 업로드순",
                    "최신 생성순",
                    "최신 수정순",
                    "이름순",
                    "크기순",
                    "청크순",
                    "타입순",
                ],
            )

        with col_view:
            view_mode = st.radio("표시 방식", ["목록", "카드"], horizontal=True)

        # 필터링 및 정렬
        filtered_files = files.copy()

        if search_filter:
            filtered_files = [f for f in filtered_files if search_filter.lower() in f.get("name", "").lower()]

        # 정렬 적용
        if sort_option == "최신 업로드순":
            filtered_files = sorted(filtered_files, key=lambda x: x.get("uploaded", ""), reverse=True)
        elif sort_option == "최신 생성순":
            filtered_files = sorted(filtered_files, key=lambda x: x.get("created", ""), reverse=True)
        elif sort_option == "최신 수정순":
            filtered_files = sorted(filtered_files, key=lambda x: x.get("modified", ""), reverse=True)
        else:
            filtered_files = filter_and_sort_files(filtered_files, "", sort_option)

        # 결과 표시
        if filtered_files:
            st.caption(f"총 {len(filtered_files)}개 문서 (전체 {len(files)}개 중)")

            if view_mode == "목록":
                render_file_list_view(filtered_files, api_client)
            else:
                render_file_card_view(filtered_files, api_client)
        else:
            if search_filter:
                st.info(f"'{search_filter}' 검색 결과가 없습니다.")
            else:
                st.info("표시할 문서가 없습니다.")


# ───────────────────────────── (3) 통계 ──────────────────────────────
with TAB_STATS:
    st.header("📊 문서 통계 대시보드")

    # 데이터 로드 확인
    files = st.session_state.get("uploaded_files", [])

    # 문서가 없는 경우 처리
    if not files:
        st.info("📋 통계를 표시할 문서가 없습니다.")
        st.markdown("### 📤 먼저 문서를 업로드해보세요!")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📤 업로드 페이지로 이동", use_container_width=True, key="stats_to_upload"):
                st.session_state.active_docs_tab = "📤 새 문서 업로드"
                rerun()
        with col2:
            if st.button("📁 문서 목록 보기", use_container_width=True, key="stats_to_list"):
                st.session_state.active_docs_tab = "📁 문서 목록"
                rerun()

        # 샘플 통계 보기 옵션
        with st.expander("👀 샘플 통계 미리보기"):
            st.markdown("""
            **통계 대시보드에서 제공하는 기능:**
            - 📈 실시간 문서 현황 모니터링
            - 📊 인터랙티브 차트 및 그래프
            - 📅 시간별 업로드 트렌드 분석
            - 📁 파일 타입별 상세 분포
            - 📏 크기 및 청크 분포 히스토그램
            - 🏆 상위 문서 순위 및 통계
            - 🔍 필터링 및 드릴다운 분석
            - 📥 상세 리포트 다운로드
            """)
    else:
        # 문서가 있는 경우 통계 대시보드 표시

        # 필터 옵션
        with st.expander("🔧 필터 및 설정", expanded=False):
            col1, col2, col3 = st.columns(3)

            with col1:
                # 날짜 범위 필터
                date_filter = st.selectbox(
                    "📅 기간 필터",
                    ["전체", "최근 7일", "최근 30일", "최근 90일", "사용자 정의"],
                    help="분석할 기간을 선택하세요"
                )

            with col2:
                # 파일 타입 필터
                all_types = set()
                for f in files:
                    name = f.get("name", "")
                    if "." in name:
                        all_types.add(name.split(".")[-1].lower())
                    else:
                        all_types.add("확장자 없음")

                selected_types = st.multiselect(
                    "📁 파일 타입",
                    sorted(all_types),
                    default=sorted(all_types),
                    help="분석할 파일 타입을 선택하세요"
                )

            with col3:
                # 크기 범위 필터
                size_filter = st.selectbox(
                    "📏 크기 범위",
                    ["전체", "1MB 미만", "1-10MB", "10MB 이상"],
                    help="분석할 파일 크기 범위를 선택하세요"
                )

        # 필터 적용
        filtered_files = files.copy()

        # 날짜 필터 적용
        if date_filter != "전체":
            now = datetime.now()
            if date_filter == "최근 7일":
                cutoff = now - timedelta(days=7)
            elif date_filter == "최근 30일":
                cutoff = now - timedelta(days=30)
            elif date_filter == "최근 90일":
                cutoff = now - timedelta(days=90)

            if date_filter != "사용자 정의":
                filtered_files = [
                    f for f in filtered_files
                    if _parse_timestamp(f.get("uploaded_at")) != "-" and
                       pd.to_datetime(_parse_timestamp(f.get("uploaded_at"))).replace(tzinfo=None) >= cutoff
                ]

        # 타입 필터 적용
        if selected_types:
            filtered_files = [
                f for f in filtered_files
                if (f.get("name", "").split(".")[-1].lower() in selected_types if "." in f.get("name", "")
                    else "확장자 없음" in selected_types)
            ]

        # 크기 필터 적용
        if size_filter != "전체":
            if size_filter == "1MB 미만":
                filtered_files = [f for f in filtered_files if f.get("size_bytes", 0) < 1024 * 1024]
            elif size_filter == "1-10MB":
                filtered_files = [f for f in filtered_files if 1024 * 1024 <= f.get("size_bytes", 0) <= 10 * 1024 * 1024]
            elif size_filter == "10MB 이상":
                filtered_files = [f for f in filtered_files if f.get("size_bytes", 0) > 10 * 1024 * 1024]

        # 필터 결과 표시
        if len(filtered_files) != len(files):
            st.info(f"🔍 필터 적용: {len(files)}개 문서 중 {len(filtered_files)}개 표시")

        if not filtered_files:
            st.warning("⚠️ 필터 조건에 맞는 문서가 없습니다.")
        else:
            # 기본 통계 계산
            total_docs = len(filtered_files)
            total_chunks = sum(f.get("chunks", 0) for f in filtered_files)
            total_size_bytes = sum(f.get("size_bytes", 0) for f in filtered_files)
            total_size_mb = total_size_bytes / (1024 * 1024) if total_size_bytes > 0 else 0

            avg_chunks = total_chunks / total_docs if total_docs > 0 else 0
            avg_size_mb = total_size_mb / total_docs if total_docs > 0 else 0

            # 실시간 메트릭 대시보드
            st.subheader("📈 실시간 현황")

            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric(
                    "📄 총 문서",
                    f"{total_docs:,}",
                    delta=f"전체 {len(files):,}개 중" if total_docs != len(files) else None,
                    help="필터링된 문서 수"
                )

            with col2:
                st.metric(
                    "🧩 총 청크",
                    f"{total_chunks:,}",
                    delta=f"평균 {avg_chunks:.1f}/문서",
                    help="인덱싱된 총 청크 수"
                )

            with col3:
                st.metric(
                    "💾 총 용량",
                    f"{total_size_mb:.1f} MB",
                    delta=f"평균 {avg_size_mb:.1f} MB/문서",
                    help="전체 문서의 총 크기"
                )

            with col4:
                # 최대 크기 문서
                max_size_doc = max(filtered_files, key=lambda x: x.get("size_bytes", 0))
                max_size_mb = max_size_doc.get("size_bytes", 0) / (1024 * 1024)
                st.metric(
                    "📊 최대 크기",
                    f"{max_size_mb:.1f} MB",
                    delta=max_size_doc.get("name", "Unknown")[:15] + "...",
                    help="가장 큰 문서"
                )

            with col5:
                # 최대 청크 문서
                max_chunk_doc = max(filtered_files, key=lambda x: x.get("chunks", 0))
                max_chunks = max_chunk_doc.get("chunks", 0)
                st.metric(
                    "🔥 최대 청크",
                    f"{max_chunks:,}",
                    delta=max_chunk_doc.get("name", "Unknown")[:15] + "...",
                    help="청크가 가장 많은 문서"
                )

            # 고급 차트 기능 (Plotly 사용 가능한 경우)
            if PLOTLY_AVAILABLE:
                # 탭으로 구분된 상세 분석
                tab1, tab2, tab3, tab4 = st.tabs(["📊 분포 분석", "📅 시간 분석", "🏆 순위", "📋 상세 데이터"])

                with tab1:
                    st.subheader("📊 분포 분석")

                    col1, col2 = st.columns(2)

                    with col1:
                        # 파일 타입별 분포 (파이 차트)
                        type_stats = {}
                        for f in filtered_files:
                            name = f.get("name", "")
                            ext = name.split(".")[-1].lower() if "." in name else "확장자 없음"
                            type_stats[ext] = type_stats.get(ext, 0) + 1

                        if type_stats:
                            fig_pie = px.pie(
                                values=list(type_stats.values()),
                                names=list(type_stats.keys()),
                                title="📁 파일 타입별 분포",
                                hole=0.4
                            )
                            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                            st.plotly_chart(fig_pie, use_container_width=True)

                    with col2:
                        # 크기 분포 히스토그램
                        sizes_mb = [f.get("size_bytes", 0) / (1024 * 1024) for f in filtered_files]

                        fig_hist = px.histogram(
                            x=sizes_mb,
                            title="📏 파일 크기 분포",
                            labels={"x": "크기 (MB)", "y": "문서 수"},
                            nbins=20
                        )
                        fig_hist.update_layout(showlegend=False)
                        st.plotly_chart(fig_hist, use_container_width=True)

                    # 청크 vs 크기 산점도
                    st.subheader("🔗 청크-크기 상관관계")

                    scatter_data = pd.DataFrame({
                        "크기 (MB)": [f.get("size_bytes", 0) / (1024 * 1024) for f in filtered_files],
                        "청크 수": [f.get("chunks", 0) for f in filtered_files],
                        "파일명": [f.get("name", "Unknown") for f in filtered_files]
                    })

                    fig_scatter = px.scatter(
                        scatter_data,
                        x="크기 (MB)",
                        y="청크 수",
                        hover_data=["파일명"],
                        title="파일 크기와 청크 수의 관계",
                        trendline="ols"  # 추세선 추가
                    )
                    st.plotly_chart(fig_scatter, use_container_width=True)

                with tab2:
                    st.subheader("📅 시간별 업로드 분석")

                    # 업로드 날짜별 분석
                    upload_dates = []
                    for f in filtered_files:
                        uploaded = f.get("uploaded", "-")
                        if uploaded != "-":
                            try:
                                date_obj = pd.to_datetime(uploaded).date()
                                upload_dates.append(date_obj)
                            except:
                                continue

                    if upload_dates:
                        # 날짜별 업로드 수 계산
                        date_counts = pd.Series(upload_dates).value_counts().sort_index()

                        # 시계열 차트
                        fig_timeline = px.line(
                            x=date_counts.index,
                            y=date_counts.values,
                            title="📈 일별 업로드 추이",
                            labels={"x": "날짜", "y": "업로드 수"}
                        )
                        fig_timeline.update_traces(mode='lines+markers')
                        st.plotly_chart(fig_timeline, use_container_width=True)

                        # 요일별 패턴
                        weekday_counts = pd.Series(upload_dates).apply(lambda x: x.strftime('%A')).value_counts()
                        weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                        weekday_counts = weekday_counts.reindex(weekday_order, fill_value=0)

                        col1, col2 = st.columns(2)

                        with col1:
                            fig_weekday = px.bar(
                                x=weekday_counts.index,
                                y=weekday_counts.values,
                                title="📅 요일별 업로드 패턴",
                                labels={"x": "요일", "y": "업로드 수"}
                            )
                            st.plotly_chart(fig_weekday, use_container_width=True)

                        with col2:
                            # 시간대별 분석 (시간 정보가 있는 경우)
                            hours = []
                            for f in filtered_files:
                                uploaded = f.get("uploaded", "-")
                                if uploaded != "-":
                                    try:
                                        hour = pd.to_datetime(uploaded).hour
                                        hours.append(hour)
                                    except:
                                        continue

                            if hours:
                                hour_counts = pd.Series(hours).value_counts().sort_index()
                                fig_hour = px.bar(
                                    x=hour_counts.index,
                                    y=hour_counts.values,
                                    title="🕐 시간대별 업로드 패턴",
                                    labels={"x": "시간", "y": "업로드 수"}
                                )
                                st.plotly_chart(fig_hour, use_container_width=True)
                    else:
                        st.info("📅 시간 분석을 위한 날짜 데이터가 충분하지 않습니다.")

                with tab3:
                    st.subheader("🏆 문서 순위")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("**📏 크기별 Top 10**")
                        top_size = sorted(filtered_files, key=lambda x: x.get("size_bytes", 0), reverse=True)[:10]

                        size_rank_data = []
                        for i, f in enumerate(top_size, 1):
                            size_mb = f.get("size_bytes", 0) / (1024 * 1024)
                            size_rank_data.append({
                                "순위": i,
                                "파일명": f.get("name", "Unknown"),
                                "크기": f"{size_mb:.1f} MB",
                                "청크": f.get("chunks", 0)
                            })

                        st.dataframe(pd.DataFrame(size_rank_data), hide_index=True)

                    with col2:
                        st.write("**🧩 청크별 Top 10**")
                        top_chunks = sorted(filtered_files, key=lambda x: x.get("chunks", 0), reverse=True)[:10]

                        chunk_rank_data = []
                        for i, f in enumerate(top_chunks, 1):
                            size_mb = f.get("size_bytes", 0) / (1024 * 1024)
                            chunk_rank_data.append({
                                "순위": i,
                                "파일명": f.get("name", "Unknown"),
                                "청크": f.get("chunks", 0),
                                "크기": f"{size_mb:.1f} MB"
                            })

                        st.dataframe(pd.DataFrame(chunk_rank_data), hide_index=True)

                    # 효율성 분석 (청크/MB 비율)
                    st.write("**⚡ 효율성 순위 (청크/MB)**")
                    efficiency_data = []
                    for f in filtered_files:
                        size_mb = f.get("size_bytes", 0) / (1024 * 1024)
                        chunks = f.get("chunks", 0)
                        if size_mb > 0:
                            efficiency = chunks / size_mb
                            efficiency_data.append({
                                "파일명": f.get("name", "Unknown"),
                                "청크/MB": f"{efficiency:.1f}",
                                "청크": chunks,
                                "크기": f"{size_mb:.1f} MB"
                            })

                    if efficiency_data:
                        efficiency_df = pd.DataFrame(efficiency_data)
                        efficiency_df["청크/MB"] = pd.to_numeric(efficiency_df["청크/MB"])
                        efficiency_df = efficiency_df.sort_values("청크/MB", ascending=False).head(10)
                        st.dataframe(efficiency_df, hide_index=True)

                with tab4:
                    st.subheader("📋 상세 데이터 테이블")

                    # 검색 기능
                    search_term = st.text_input("🔍 파일명 검색", placeholder="검색어를 입력하세요...")

                    # 데이터 준비
                    detailed_data = []
                    for f in filtered_files:
                        if not search_term or search_term.lower() in f.get("name", "").lower():
                            size_mb = f.get("size_bytes", 0) / (1024 * 1024)
                            detailed_data.append({
                                "파일명": f.get("name", "Unknown"),
                                "타입": f.get("name", "").split(".")[-1] if "." in f.get("name", "") else "없음",
                                "크기 (MB)": f"{size_mb:.2f}",
                                "청크 수": f.get("chunks", 0),
                                "청크/MB": f"{f.get('chunks', 0) / size_mb:.1f}" if size_mb > 0 else "N/A",
                                "업로드일": f.get("uploaded", "-"),
                                "생성일": f.get("created", "-"),
                                "수정일": f.get("modified", "-")
                            })

                    if detailed_data:
                        detailed_df = pd.DataFrame(detailed_data)

                        # 컬럼 선택
                        selected_columns = st.multiselect(
                            "표시할 컬럼 선택",
                            detailed_df.columns.tolist(),
                            default=["파일명", "타입", "크기 (MB)", "청크 수", "업로드일"]
                        )

                        if selected_columns:
                            st.dataframe(
                                detailed_df[selected_columns],
                                use_container_width=True,
                                hide_index=True
                            )

                        # CSV 다운로드
                        csv_data = detailed_df.to_csv(index=False)
                        st.download_button(
                            label="📥 상세 데이터 CSV 다운로드",
                            data=csv_data,
                            file_name=f"detailed_document_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("검색 조건에 맞는 문서가 없습니다.")

            else:
                # Plotly 없이 기본 통계만 표시
                st.subheader("📊 기본 통계")

                # 파일 타입별 통계
                type_stats = {}
                for f in filtered_files:
                    name = f.get("name", "")
                    if "." in name:
                        ext = name.split(".")[-1].lower()
                    else:
                        ext = "확장자 없음"

                    if ext not in type_stats:
                        type_stats[ext] = {"count": 0, "size": 0, "chunks": 0}

                    type_stats[ext]["count"] += 1
                    type_stats[ext]["size"] += f.get("size_bytes", 0)
                    type_stats[ext]["chunks"] += f.get("chunks", 0)

                # 타입별 통계 테이블
                type_data = []
                for ext, stats in type_stats.items():
                    type_data.append({
                        "파일 타입": f".{ext}" if ext != "확장자 없음" else ext,
                        "문서 수": stats["count"],
                        "총 용량 (MB)": f"{stats['size'] / (1024*1024):.1f}",
                        "총 청크": stats["chunks"],
                        "평균 청크/문서": f"{stats['chunks'] / stats['count']:.1f}"
                    })

                type_df = pd.DataFrame(type_data)
                type_df = type_df.sort_values("문서 수", ascending=False)
                st.dataframe(type_df, use_container_width=True, hide_index=True)

            # 하단 액션 버튼들
            st.divider()

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button("🔄 통계 새로고침", use_container_width=True):
                    st.session_state.force_refresh = True
                    st.session_state.active_docs_tab = "📊 통계"
                    rerun()

            with col2:
                if st.button("📤 업로드하기", use_container_width=True):
                    st.session_state.active_docs_tab = "📤 새 문서 업로드"
                    rerun()

            with col3:
                if st.button("📁 문서 목록", use_container_width=True):
                    st.session_state.active_docs_tab = "📁 문서 목록"
                    rerun()

            with col4:
                # 리포트 다운로드
                report_data = {
                    "통계_요약": {
                        "총_문서_수": total_docs,
                        "총_청크_수": total_chunks,
                        "총_용량_MB": round(total_size_mb, 2),
                        "평균_청크_문서": round(avg_chunks, 1),
                        "평균_크기_MB": round(avg_size_mb, 2)
                    },
                    "파일_목록": detailed_data if 'detailed_data' in locals() else []
                }

                report_json = json.dumps(report_data, ensure_ascii=False, indent=2)

                st.download_button(
                    label="📊 리포트 다운로드 (JSON)",
                    data=report_json,
                    file_name=f"document_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )