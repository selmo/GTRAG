"""
UI 헬퍼 함수들
공통적으로 사용되는 유틸리티 함수 모음
"""
import streamlit as st
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import re
import hashlib
import mimetypes
from pathlib import Path


def format_file_size(size_bytes: int) -> str:
    """파일 크기를 읽기 쉬운 형식으로 변환"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def format_timestamp(timestamp: str, format: str = "relative") -> str:
    """타임스탬프 포맷팅"""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        if format == "relative":
            now = datetime.now()
            diff = now - dt.replace(tzinfo=None)
            
            if diff < timedelta(minutes=1):
                return "방금 전"
            elif diff < timedelta(hours=1):
                minutes = int(diff.total_seconds() / 60)
                return f"{minutes}분 전"
            elif diff < timedelta(days=1):
                hours = int(diff.total_seconds() / 3600)
                return f"{hours}시간 전"
            elif diff < timedelta(days=7):
                days = diff.days
                return f"{days}일 전"
            else:
                return dt.strftime("%Y-%m-%d")
        
        elif format == "full":
            return dt.strftime("%Y년 %m월 %d일 %H:%M:%S")
        
        elif format == "short":
            return dt.strftime("%m/%d %H:%M")
        
        else:
            return dt.strftime(format)
            
    except:
        return timestamp


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """텍스트를 지정된 길이로 자르기"""
    if len(text) <= max_length:
        return text
    
    # 단어 단위로 자르기
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > 0:
        truncated = truncated[:last_space]
    
    return truncated + suffix


def highlight_text(text: str, query: str, color: str = "yellow") -> str:
    """검색어 하이라이트"""
    if not query:
        return text
    
    # 대소문자 구분 없이 검색
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    
    # HTML 태그로 감싸기
    highlighted = pattern.sub(
        lambda m: f'<mark style="background-color: {color};">{m.group()}</mark>',
        text
    )
    
    return highlighted


def validate_file(file, allowed_extensions: List[str], max_size_mb: float = 50) -> Tuple[bool, str]:
    """파일 유효성 검사"""
    # 파일 확장자 확인
    file_extension = Path(file.name).suffix.lower().lstrip('.')
    if file_extension not in allowed_extensions:
        return False, f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(allowed_extensions)}"
    
    # 파일 크기 확인
    file_size_mb = file.size / (1024 * 1024)
    if file_size_mb > max_size_mb:
        return False, f"파일 크기가 너무 큽니다. 최대 {max_size_mb}MB까지 지원됩니다."
    
    # MIME 타입 확인 (추가 보안)
    mime_type = mimetypes.guess_type(file.name)[0]
    if mime_type and not any(mime_type.startswith(t) for t in ['text/', 'application/', 'image/']):
        return False, "잘못된 파일 형식입니다."
    
    return True, "OK"


def generate_file_hash(file_content: bytes) -> str:
    """파일 해시 생성 (중복 확인용)"""
    return hashlib.sha256(file_content).hexdigest()


def parse_search_query(query: str) -> Dict[str, Any]:
    """검색 쿼리 파싱 (고급 검색 지원)"""
    # 특수 검색 연산자 파싱
    operators = {
        'title:': 'title',
        'content:': 'content',
        'date:': 'date',
        'type:': 'file_type',
        'size:': 'size'
    }
    
    parsed = {
        'query': query,
        'filters': {}
    }
    
    # 연산자 추출
    for op, field in operators.items():
        pattern = rf'{op}([^\s]+)'
        matches = re.findall(pattern, query)
        if matches:
            parsed['filters'][field] = matches[0]
            query = re.sub(pattern, '', query).strip()
    
    # 따옴표로 묶인 정확한 구문 추출
    exact_phrases = re.findall(r'"([^"]+)"', query)
    if exact_phrases:
        parsed['exact_phrases'] = exact_phrases
        query = re.sub(r'"[^"]+"', '', query).strip()
    
    # 나머지 쿼리
    parsed['query'] = query.strip()
    
    return parsed


def create_progress_bar(current: int, total: int, label: str = "") -> None:
    """커스텀 프로그레스 바 생성"""
    if total == 0:
        progress = 0
    else:
        progress = current / total
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.progress(progress)
    
    with col2:
        st.write(f"{current}/{total}")
    
    if label:
        st.caption(label)


def show_toast(message: str, type: str = "info", duration: int = 3):
    """토스트 메시지 표시"""
    if type == "success":
        st.success(message)
    elif type == "error":
        st.error(message)
    elif type == "warning":
        st.warning(message)
    else:
        st.info(message)
    
    # duration 초 후 자동으로 사라지게 하려면 JavaScript 필요
    # Streamlit의 제한으로 인해 완전한 구현은 어려움


def create_download_link(data: str, filename: str, mime_type: str = "text/plain") -> str:
    """다운로드 링크 생성"""
    import base64
    
    b64 = base64.b64encode(data.encode()).decode()
    href = f'<a href="data:{mime_type};base64,{b64}" download="{filename}">📥 {filename} 다운로드</a>'
    return href


def estimate_reading_time(text: str, wpm: int = 200) -> int:
    """텍스트 읽기 시간 추정 (분)"""
    # 한글과 영어를 구분하여 계산
    korean_chars = len(re.findall(r'[가-힣]', text))
    english_words = len(re.findall(r'\b[a-zA-Z]+\b', text))
    
    # 한글은 분당 300자, 영어는 분당 200단어로 계산
    korean_time = korean_chars / 300
    english_time = english_words / wpm
    
    total_time = korean_time + english_time
    return max(1, int(total_time))


def sanitize_filename(filename: str) -> str:
    """파일명 정규화 (안전한 파일명으로 변환)"""
    # 위험한 문자 제거
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # 공백을 언더스코어로 변경
    filename = filename.replace(' ', '_')
    
    # 연속된 언더스코어 제거
    filename = re.sub(r'_+', '_', filename)
    
    # 앞뒤 언더스코어 제거
    filename = filename.strip('_')
    
    # 최대 길이 제한 (255자)
    name, ext = Path(filename).stem, Path(filename).suffix
    if len(filename) > 255:
        max_name_length = 255 - len(ext)
        name = name[:max_name_length]
        filename = name + ext
    
    return filename


def get_file_icon(file_extension: str) -> str:
    """파일 확장자에 따른 아이콘 반환"""
    icons = {
        'pdf': '📄',
        'doc': '📝',
        'docx': '📝',
        'txt': '📃',
        'png': '🖼️',
        'jpg': '🖼️',
        'jpeg': '🖼️',
        'gif': '🖼️',
        'mp4': '🎥',
        'mp3': '🎵',
        'zip': '📦',
        'csv': '📊',
        'xlsx': '📊',
        'json': '🔧',
        'py': '🐍',
        'js': '🟨',
        'html': '🌐',
        'css': '🎨'
    }
    
    return icons.get(file_extension.lower(), '📎')


def format_number(number: int) -> str:
    """숫자를 읽기 쉬운 형식으로 변환"""
    if number < 1000:
        return str(number)
    elif number < 1000000:
        return f"{number/1000:.1f}K"
    elif number < 1000000000:
        return f"{number/1000000:.1f}M"
    else:
        return f"{number/1000000000:.1f}B"


def create_breadcrumb(items: List[str]) -> None:
    """브레드크럼 네비게이션 생성"""
    breadcrumb_html = " > ".join(
        f'<span style="color: #666;">{item}</span>' for item in items
    )
    st.markdown(breadcrumb_html, unsafe_allow_html=True)


def calculate_similarity_color(score: float) -> str:
    """유사도 점수에 따른 색상 반환"""
    if score >= 0.8:
        return "#28a745"  # 녹색
    elif score >= 0.6:
        return "#ffc107"  # 노란색
    elif score >= 0.4:
        return "#fd7e14"  # 주황색
    else:
        return "#dc3545"  # 빨간색


def create_metric_card(title: str, value: Any, delta: Optional[Any] = None, 
                      delta_color: str = "normal") -> None:
    """커스텀 메트릭 카드 생성"""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.metric(title, value, delta, delta_color=delta_color)
    
    with col2:
        # 추가 액션 버튼이나 아이콘을 여기에 추가 가능
        pass


def paginate_results(items: List[Any], page_size: int = 10, 
                    page_key: str = "page") -> Tuple[List[Any], int, int]:
    """결과 페이지네이션"""
    total_pages = (len(items) + page_size - 1) // page_size
    
    # 현재 페이지 가져오기
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    
    current_page = st.session_state[page_key]
    
    # 페이지 범위 계산
    start_idx = (current_page - 1) * page_size
    end_idx = min(start_idx + page_size, len(items))
    
    # 현재 페이지 아이템
    page_items = items[start_idx:end_idx]
    
    return page_items, current_page, total_pages


def render_pagination_controls(current_page: int, total_pages: int, 
                              page_key: str = "page") -> None:
    """페이지네이션 컨트롤 렌더링"""
    if total_pages <= 1:
        return
    
    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
    
    with col1:
        if st.button("⏮️", disabled=current_page == 1, key=f"first_{page_key}"):
            st.session_state[page_key] = 1
            st.experimental_rerun()
    
    with col2:
        if st.button("◀️", disabled=current_page == 1, key=f"prev_{page_key}"):
            st.session_state[page_key] = current_page - 1
            st.experimental_rerun()
    
    with col3:
        st.write(f"페이지 {current_page} / {total_pages}")
    
    with col4:
        if st.button("▶️", disabled=current_page == total_pages, key=f"next_{page_key}"):
            st.session_state[page_key] = current_page + 1
            st.experimental_rerun()
    
    with col5:
        if st.button("⏭️", disabled=current_page == total_pages, key=f"last_{page_key}"):
            st.session_state[page_key] = total_pages
            st.experimental_rerun()
