"""
고급 인터랙티브 레퍼런스 시스템 - 최적 개선 버전
- 전역 설정 연동 시스템
- 중복 슬라이더 제거
- 실시간 필터링 구현
- 설정값 자동 동기화
"""
import re
import json
import time
import uuid
from typing import Dict, List, Tuple, Optional
import streamlit as st
from datetime import datetime

# 설정 관리자 클래스
class SettingsManager:
    """전역 설정 관리자"""

    @staticmethod
    def get_rag_settings() -> Dict:
        """RAG 설정 가져오기 (우선순위: 세션 > 백엔드 > 기본값)"""
        from frontend.ui.core.config import Constants

        # 백엔드 설정 시도
        backend_settings = {}
        try:
            if hasattr(st.session_state, 'api_client') and st.session_state.api_client:
                backend_settings = st.session_state.api_client.get_settings().get('rag', {})
        except:
            pass

        return {
            'min_similarity': (
                st.session_state.get('min_similarity') or
                st.session_state.get('backend_min_similarity') or
                backend_settings.get('min_score') or
                Constants.Defaults.MIN_SIMILARITY
            ),
            'top_k': (
                st.session_state.get('rag_top_k') or
                st.session_state.get('backend_rag_top_k') or
                backend_settings.get('top_k') or
                Constants.Defaults.TOP_K
            ),
            'context_window': (
                st.session_state.get('context_window') or
                st.session_state.get('backend_context_window') or
                backend_settings.get('context_window') or
                Constants.Defaults.CONTEXT_WINDOW
            )
        }

    @staticmethod
    def sync_settings_from_backend():
        """백엔드에서 설정 동기화"""
        try:
            if hasattr(st.session_state, 'api_client') and st.session_state.api_client:
                current_settings = st.session_state.api_client.get_settings()

                if current_settings and 'rag' in current_settings:
                    rag_settings = current_settings['rag']

                    # 백엔드 설정을 세션에 반영 (덮어쓰지 않고 backup으로 저장)
                    param_mapping = {
                        'min_score': 'backend_min_similarity',
                        'top_k': 'backend_rag_top_k',
                        'context_window': 'backend_context_window'
                    }

                    for backend_key, session_key in param_mapping.items():
                        if backend_key in rag_settings:
                            st.session_state[session_key] = rag_settings[backend_key]

                    return True
        except Exception as e:
            st.warning(f"백엔드 설정 동기화 실패: {str(e)}")

        return False


class InteractiveReferenceSystem:
    """인터랙티브 레퍼런스 시스템 메인 클래스 - 설정 연동 최적화"""

    def __init__(self):
        self.reference_patterns = [
            # 인용 패턴들
            r'(따르면|의하면|에서는|에 따르면|문서에서|자료에서)',
            r'(보고서|문서|자료|연구|조사|분석)에서',
            r'(설명|언급|기술|서술|명시)된?(바와 같이|대로)',
            r'(참고|참조|확인)하면',
        ]

        # 🔧 키 관리자 초기화
        self._init_key_manager()

        # 🔧 설정 동기화 초기화
        self._init_settings_sync()

    def _init_key_manager(self):
        """키 관리자 초기화"""
        # 세션별 고유 ID 생성
        if 'ref_system_session_id' not in st.session_state:
            st.session_state.ref_system_session_id = str(uuid.uuid4())[:8]

        # 키 카운터 초기화
        if 'ref_system_key_counter' not in st.session_state:
            st.session_state.ref_system_key_counter = {}

        self.session_id = st.session_state.ref_system_session_id
        self.key_counter = st.session_state.ref_system_key_counter

    def _init_settings_sync(self):
        """설정 동기화 초기화"""
        # 페이지 로드시 한 번만 동기화
        if 'ref_system_settings_synced' not in st.session_state:
            SettingsManager.sync_settings_from_backend()
            st.session_state.ref_system_settings_synced = True

    def _generate_unique_key(self, base_key: str, context: str = "") -> str:
        """고유 키 생성 (중복 방지 보장)"""
        # 컨텍스트가 있으면 포함
        if context:
            full_base = f"{base_key}_{context}"
        else:
            full_base = base_key

        # 카운터 증가
        if full_base not in self.key_counter:
            self.key_counter[full_base] = 0
        self.key_counter[full_base] += 1

        # 타임스탬프와 세션 ID 포함한 완전 고유 키
        timestamp = int(time.time() * 1000000) % 1000000  # 마이크로초 단위
        unique_key = f"{full_base}_{self.session_id}_{self.key_counter[full_base]}_{timestamp}"

        return unique_key

    def filter_sources_by_settings(self, sources: List[Dict]) -> List[Dict]:
        """설정에 따른 소스 필터링 (실시간 적용)"""
        if not sources:
            return sources

        # 현재 설정 가져오기
        rag_settings = SettingsManager.get_rag_settings()
        min_similarity = rag_settings['min_similarity']
        top_k = rag_settings['top_k']

        # 유사도 필터링
        filtered_sources = []
        for source in sources:
            score = source.get('score', 0)
            confidence = source.get('confidence', score)

            # 유사도 임계값 적용
            if score >= min_similarity or confidence >= min_similarity:
                filtered_sources.append(source)

        # top_k 제한 적용
        filtered_sources = filtered_sources[:top_k]

        return filtered_sources

    def render_settings_control_panel(self, sources: List[Dict]) -> List[Dict]:
        """설정 제어 패널 (Settings 연동) - expander 중첩 방지"""
        # # 🎯 expander 중첩 검사
        # is_nested = self._check_if_nested_context()
        #
        # if is_nested:
        #     # 중첩된 경우 간단한 컨테이너 사용
        #     self._render_simple_control_panel(sources)
        # else:
        #     # 독립적인 경우 full expander 사용
        #     self._render_full_control_panel(sources)

        # 실시간 필터링 적용
        return self._apply_realtime_filtering(sources)

    def _check_if_nested_context(self) -> bool:
        """현재 expander 내부 또는 사이드바 내부인지 확인"""
        # 🔧 사이드바 컨텍스트 체크
        if self._is_in_sidebar():
            return True  # 사이드바에서는 간단한 버전 사용

        # 🔧 expander 중첩 체크 (안전하게 간단한 버전 사용)
        return True  # 안전을 위해 항상 간단한 버전 사용

    def _is_in_sidebar(self) -> bool:
        """현재 사이드바 컨텍스트인지 확인"""
        try:
            # Streamlit의 내부 컨텍스트 확인
            # 사이드바에서 실행 중인지 간접적으로 체크
            import streamlit as st

            # 컨텍스트 매니저 스택 확인
            if hasattr(st, '_get_script_run_ctx'):
                ctx = st._get_script_run_ctx()
                if ctx and hasattr(ctx, 'widgets_manager'):
                    # 현재 활성 컨테이너가 사이드바인지 확인하는 간접적 방법
                    # 안전하게 False 반환 (추후 더 정확한 방법으로 개선 가능)
                    pass

            # 간단한 플래그 기반 체크
            return st.session_state.get('_in_sidebar_context', False)
        except:
            return False

    def _render_simple_control_panel(self, sources: List[Dict]):
        """간단한 제어 패널 (expander 없이)"""
        # 구분선과 헤더
        st.markdown("---")
        st.markdown("#### 🔧 근거 필터링 설정 1")
        st.caption("💡 **Settings 페이지**에서 기본값을 설정할 수 있습니다")

        # 현재 설정 가져오기
        rag_settings = SettingsManager.get_rag_settings()

        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            # 🔧 실시간 최소 유사도 슬라이더 (세션 임시값)
            current_min_sim = st.session_state.get('temp_min_similarity', rag_settings['min_similarity'])

            temp_min_similarity = st.slider(
                "최소 유사도 (임시 조정)",
                min_value=0.0,
                max_value=1.0,
                value=float(current_min_sim),
                step=0.05,
                help="이 값은 현재 세션에만 적용됩니다. 영구 설정은 Settings 페이지에서 하세요",
                key=self._generate_unique_key("temp_min_similarity", "simple_panel")
            )

            # 세션 임시값 저장
            st.session_state.temp_min_similarity = temp_min_similarity

        with col2:
            # 설정 정보 표시
            st.caption("**현재 설정값**")
            st.caption(f"기본값: {rag_settings['min_similarity']:.2f}")
            st.caption(f"임시값: {temp_min_similarity:.2f}")
            st.caption(f"Top-K: {rag_settings['top_k']}")

        with col3:
            # 설정 액션 버튼
            if st.button("🔄 기본값 복원", key=self._generate_unique_key("reset_temp", "simple"), help="임시 조정값을 초기화합니다"):
                if 'temp_min_similarity' in st.session_state:
                    del st.session_state.temp_min_similarity
                st.rerun()

            if st.button("⚙️ Settings", key=self._generate_unique_key("open_settings", "simple"), help="Settings 페이지로 이동합니다"):
                st.switch_page("pages/99_Settings.py")

        # 현재 사용할 최소 유사도 (임시값 우선)
        effective_min_similarity = st.session_state.get('temp_min_similarity', rag_settings['min_similarity'])

        # 필터링된 소스 개수 표시
        if sources:
            original_count = len(sources)
            filtered_count = len([s for s in sources if s.get('score', 0) >= effective_min_similarity])

            if filtered_count != original_count:
                st.info(f"📊 {original_count}개 중 {filtered_count}개 근거가 표시됩니다 (임계값: {effective_min_similarity:.2f})")
            else:
                st.success(f"✅ 모든 {original_count}개 근거가 표시됩니다")

    def _render_full_control_panel(self, sources: List[Dict]):
        """전체 제어 패널 (expander 포함)"""
        # 🎯 Settings 페이지와 연동된 제어 패널
        with st.expander("🔧 근거 필터링 설정 2", expanded=False):
            st.info("💡 **Settings 페이지**에서 기본값을 설정할 수 있습니다")

            # 현재 설정 가져오기
            rag_settings = SettingsManager.get_rag_settings()

            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                # 🔧 실시간 최소 유사도 슬라이더 (세션 임시값)
                current_min_sim = st.session_state.get('temp_min_similarity', rag_settings['min_similarity'])

                temp_min_similarity = st.slider(
                    "최소 유사도 (임시 조정)",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(current_min_sim),
                    step=0.05,
                    help="이 값은 현재 세션에만 적용됩니다. 영구 설정은 Settings 페이지에서 하세요",
                    key=self._generate_unique_key("temp_min_similarity", "full_panel")
                )

                # 세션 임시값 저장
                st.session_state.temp_min_similarity = temp_min_similarity

            with col2:
                # 설정 정보 표시
                st.caption("**현재 설정값**")
                st.caption(f"기본값: {rag_settings['min_similarity']:.2f}")
                st.caption(f"임시값: {temp_min_similarity:.2f}")
                st.caption(f"Top-K: {rag_settings['top_k']}")

            with col3:
                # 설정 액션 버튼
                if st.button("🔄 기본값 복원", key=self._generate_unique_key("reset_temp", "full")):
                    if 'temp_min_similarity' in st.session_state:
                        del st.session_state.temp_min_similarity
                    st.rerun()

                if st.button("⚙️ Settings 열기", key=self._generate_unique_key("open_settings", "full")):
                    st.switch_page("pages/99_Settings.py")

            # 현재 사용할 최소 유사도 (임시값 우선)
            effective_min_similarity = st.session_state.get('temp_min_similarity', rag_settings['min_similarity'])

            # 필터링된 소스 개수 표시
            if sources:
                original_count = len(sources)
                filtered_count = len([s for s in sources if s.get('score', 0) >= effective_min_similarity])

                if filtered_count != original_count:
                    st.info(f"📊 {original_count}개 중 {filtered_count}개 근거가 표시됩니다 (임계값: {effective_min_similarity:.2f})")
                else:
                    st.success(f"✅ 모든 {original_count}개 근거가 표시됩니다")

    def _apply_realtime_filtering(self, sources: List[Dict]) -> List[Dict]:
        """실시간 필터링 적용"""
        if not sources:
            return sources

        # 임시 설정값 우선 사용
        rag_settings = SettingsManager.get_rag_settings()
        effective_min_similarity = st.session_state.get('temp_min_similarity', rag_settings['min_similarity'])
        top_k = rag_settings['top_k']

        # 필터링 적용
        filtered_sources = []
        for source in sources:
            score = source.get('score', 0)
            confidence = source.get('confidence', score)

            # 유사도 임계값 적용
            if max(score, confidence) >= effective_min_similarity:
                filtered_sources.append(source)

        # Top-K 제한
        return filtered_sources[:top_k]

    def insert_smart_references(self, answer: str, sources: List[Dict]) -> str:
        """문맥에 맞는 스마트 레퍼런스 삽입"""
        if not sources or not answer:
            return answer

        # 문장 단위로 분할
        sentences = self._split_into_sentences(answer)

        # 각 문장에 대해 최적의 레퍼런스 찾기
        referenced_answer = ""
        used_references = set()

        for sentence in sentences:
            best_ref_idx = self._find_best_reference(sentence, sources, used_references)

            if best_ref_idx is not None:
                referenced_sentence = self._insert_reference(sentence, best_ref_idx + 1)
                used_references.add(best_ref_idx)
            else:
                referenced_sentence = sentence

            referenced_answer += referenced_sentence + " "

        return referenced_answer.strip()

    def _split_into_sentences(self, text: str) -> List[str]:
        """텍스트를 문장 단위로 분할"""
        # 한국어 문장 분할 패턴
        pattern = r'[.!?](?=\s|$)|[。！？](?=\s|$)'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]

    def _find_best_reference(self, sentence: str, sources: List[Dict], used_refs: set) -> Optional[int]:
        """문장에 가장 적합한 레퍼런스 찾기"""
        best_score = 0
        best_idx = None

        for idx, source in enumerate(sources):
            if idx in used_refs:
                continue

            score = self._calculate_relevance_score(sentence, source)

            if score > best_score and score > 0.3:  # 최소 임계값
                best_score = score
                best_idx = idx

        return best_idx

    def _calculate_relevance_score(self, sentence: str, source: Dict) -> float:
        """문장과 소스의 관련성 점수 계산"""
        content = source.get("content", "").lower()
        sentence_lower = sentence.lower()

        # 키워드 매칭 점수
        keyword_score = 0
        sentence_words = set(re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', sentence_lower))
        content_words = set(re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}', content))

        if sentence_words and content_words:
            common_words = sentence_words.intersection(content_words)
            keyword_score = len(common_words) / len(sentence_words)

        # 패턴 매칭 점수 (인용 표현 포함 여부)
        pattern_score = 0
        for pattern in self.reference_patterns:
            if re.search(pattern, sentence_lower):
                pattern_score = 0.3
                break

        # 기본 소스 점수
        base_score = source.get("score", 0) * 0.3

        return keyword_score * 0.5 + pattern_score + base_score

    def _insert_reference(self, sentence: str, ref_num: int) -> str:
        """문장에 레퍼런스 삽입 - CSS 호환 버전"""
        # 임시 마커 사용 (나중에 CSS 버전으로 변환됨)
        ref_marker = f'[{ref_num}]'

        if sentence.endswith('.'):
            return f"{sentence[:-1]} {ref_marker}."
        else:
            return f"{sentence} {ref_marker}"

    def render_interactive_answer(self, answer: str, sources: List[Dict], message_id: str = None, placeholder=None):
        """CSS 전용 호버 미리보기 - Streamlit 호환 버전"""
        if not message_id:
            message_id = self._generate_unique_key("msg", "answer")

        # 스마트 레퍼런스 삽입
        referenced_answer = self.insert_smart_references(answer, sources)

        # CSS 전용 스타일 먼저 적용
        self._render_css_only_styles()

        # 레퍼런스를 CSS 호환 형태로 변환
        enhanced_answer = self._convert_to_css_references(referenced_answer, sources)

        # 답변 렌더링
        if placeholder:
            placeholder.markdown(enhanced_answer, unsafe_allow_html=True)
        else:
            st.markdown(enhanced_answer, unsafe_allow_html=True)

        return enhanced_answer

    def _render_css_only_styles(self):
        """CSS 전용 스타일 (JavaScript 불필요)"""
        st.markdown("""
        <style>
        /* 🎯 CSS 전용 참조 링크 with 호버 미리보기 */
        .css-ref-link {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            text-decoration: none !important;
            padding: 3px 8px !important;
            border-radius: 12px !important;
            font-size: 0.85em !important;
            font-weight: bold !important;
            margin: 0 3px !important;
            display: inline-block !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 2px 6px rgba(102, 126, 234, 0.4) !important;
            cursor: pointer !important;
            position: relative !important;
        }
        
        .css-ref-link:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 16px rgba(102, 126, 234, 0.6) !important;
            background: linear-gradient(135deg, #764ba2 0%, #667eea 100%) !important;
        }
        
        /* 🎨 CSS 전용 툴팁 - 호버시 표시 */
        .css-ref-link::before {
            content: attr(data-tooltip) !important;
            position: absolute !important;
            bottom: 100% !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            background: white !important;
            border: 2px solid #667eea !important;
            border-radius: 10px !important;
            padding: 15px !important;
            min-width: 280px !important;
            max-width: 400px !important;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2) !important;
            z-index: 9999 !important;
            opacity: 0 !important;
            visibility: hidden !important;
            transition: all 0.3s ease !important;
            margin-bottom: 10px !important;
            font-size: 0.9em !important;
            font-weight: normal !important;
            color: #333 !important;
            line-height: 1.6 !important;
            white-space: pre-line !important;
            text-align: left !important;
        }
        
        .css-ref-link:hover::before {
            opacity: 1 !important;
            visibility: visible !important;
        }
        
        /* 🔻 툴팁 화살표 */
        .css-ref-link::after {
            content: '' !important;
            position: absolute !important;
            bottom: 100% !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            border: 8px solid transparent !important;
            border-top: 8px solid #667eea !important;
            opacity: 0 !important;
            visibility: hidden !important;
            transition: all 0.3s ease !important;
            margin-bottom: 2px !important;
        }
        
        .css-ref-link:hover::after {
            opacity: 1 !important;
            visibility: visible !important;
        }
        
        /* 📱 반응형 디자인 */
        @media (max-width: 768px) {
            .css-ref-link::before {
                min-width: 250px !important;
                max-width: 320px !important;
                font-size: 0.85em !important;
                padding: 12px !important;
            }
        }
        </style>
        """, unsafe_allow_html=True)

    def _convert_to_css_references(self, answer: str, sources: List[Dict]) -> str:
        """참조 링크를 CSS 전용 버전으로 변환"""
        # 각 소스에 대해 CSS 참조 링크 생성
        for i, source in enumerate(sources, 1):
            # 툴팁 텍스트 생성
            tooltip_text = self._generate_tooltip_text(source, i)

            # HTML 이스케이프
            tooltip_escaped = tooltip_text.replace('"', '&quot;').replace('\n', '&#10;')

            # 기존 참조 패턴들을 CSS 버전으로 교체
            patterns = [
                f'<a href="#ref-{i}" class="reference-link" data-ref="{i}"[^>]*>\\[{i}\\]</a>',
                f'<span class="reference-link" data-ref="{i}"[^>]*>\\[{i}\\]</span>',
                f'\\[{i}\\]'  # 단순 텍스트 패턴
            ]

            css_link = f'<span class="css-ref-link" data-tooltip="{tooltip_escaped}" data-ref="{i}">[{i}]</span>'

            for pattern in patterns:
                answer = re.sub(pattern, css_link, answer)

        return answer

    def _generate_tooltip_text(self, source: Dict, ref_num: int) -> str:
        """툴팁 텍스트 생성"""
        title = source.get('source', f'문서 {ref_num}')
        content = source.get('content', '')
        score = source.get('score', 0)
        confidence = source.get('confidence', source.get('score', 0) * 0.9)  # 기본값 설정

        # 내용 요약 (120자 제한)
        if len(content) > 120:
            content_preview = content[:120] + "..."
        else:
            content_preview = content

        # 이모지와 함께 구조화된 툴팁
        tooltip = f"""📄 {title}

💬 내용:
{content_preview}

📊 품질 정보:
• 유사도: {score:.1%}
• 신뢰도: {int(confidence * 100)}%

💡 클릭하면 상세 내용으로 이동합니다"""

        return tooltip

    def render_enhanced_sources(self, sources: List[Dict], search_info: Optional[Dict] = None):
        """향상된 근거 표시 - 설정 연동 버전 (사이드바 컨텍스트 방지)"""
        if not sources:
            st.info("표시할 근거가 없습니다.")
            return

        # 🚨 사이드바에서 호출된 경우 기본 렌더링만 수행
        if self._is_in_sidebar():
            self._render_sidebar_safe_sources(sources, search_info)
            return

        # 🎯 메인 컨텐츠 영역에서만 설정 제어 패널 렌더링
        filtered_sources = self.render_settings_control_panel(sources)

        # 필터링 결과가 없는 경우
        if not filtered_sources:
            st.warning("설정된 임계값에 맞는 근거가 없습니다. 임계값을 낮춰보세요.")
            return

        # 검색 정보 표시
        if search_info:
            self._render_search_summary(search_info, len(sources), len(filtered_sources))

        # 소스 카드들 렌더링 (필터링된 소스만)
        self._render_source_cards(filtered_sources)

    def _render_sidebar_safe_sources(self, sources: List[Dict], search_info: Optional[Dict] = None):
        """사이드바 안전 버전 - 설정 제어 패널 없이 기본 렌더링만"""
        # 🔧 Settings에서 설정값 가져와서 필터링만 적용
        filtered_sources = self._apply_realtime_filtering(sources)

        if not filtered_sources:
            st.info("필터 조건에 맞는 근거가 없습니다.")
            return

        # 검색 정보 (간단 버전)
        if search_info:
            st.caption(f"🔍 검색 시간: {search_info.get('search_time', 0):.2f}초")
            if len(filtered_sources) != len(sources):
                st.caption(f"📊 {len(sources)}개 중 {len(filtered_sources)}개 표시")

        # 소스 카드들 렌더링
        self._render_source_cards(filtered_sources)

    def render_enhanced_sources_no_search_info(self, sources: List[Dict]):
        """검색 정보 없이 소스만 렌더링 - 설정 연동 버전 (사이드바 컨텍스트 방지)"""
        if not sources:
            return

        # 🚨 사이드바에서 호출된 경우 기본 렌더링만 수행
        if self._is_in_sidebar():
            filtered_sources = self._apply_realtime_filtering(sources)
            if filtered_sources:
                self._render_source_cards(filtered_sources)
            return

        # 🎯 설정 제어 패널과 필터링 적용
        filtered_sources = self.render_settings_control_panel(sources)

        if not filtered_sources:
            st.warning("설정된 임계값에 맞는 근거가 없습니다.")
            return

        # 소스 카드들만 렌더링
        self._render_source_cards(filtered_sources)

    def _render_source_cards(self, sources: List[Dict]):
        """소스 카드들 렌더링 (공통 로직 분리) - 키 관리 최적화"""
        # 고유 ID를 가진 소스 카드들 렌더링
        for idx, source in enumerate(sources, 1):
            # 🔧 고유 ID 부여 (키 관리자 사용)
            source_id = self._generate_unique_key("source_card", f"ref_{idx}")

            with st.container():
                # HTML anchor 추가
                st.markdown(f'<div id="ref-{idx}" class="source-card">', unsafe_allow_html=True)

                # 향상된 소스 카드 렌더링 (키 컨텍스트 전달)
                self._render_enhanced_source_card(source, idx, context=f"card_{idx}")

                st.markdown('</div>', unsafe_allow_html=True)

                # 카드 간 간격
                if idx < len(sources):
                    st.divider()

    def _render_enhanced_source_card(self, source: Dict, ref_num: int, context: str = ""):
        """개선된 소스 카드 렌더링 - 고유 키 보장"""
        score = source.get("score", 0)
        confidence = source.get("confidence", 0)
        name = source.get("source", "Unknown")
        content = source.get("content", "")

        # 🔧 키 컨텍스트 설정
        key_context = f"{context}_ref{ref_num}" if context else f"ref{ref_num}"

        # 🔧 간소화된 헤더 섹션 (참조 번호와 문서명만)
        st.markdown(f"##### [{ref_num}] \"{name}\"")

        # 🚀 탭을 사용한 내용 표시 - 고유 키 적용
        preview_length = 150
        if len(content) > preview_length:
            preview = content[:preview_length] + "..."

            # 🔧 탭 생성 (고유 키 사용)
            tab_key = self._generate_unique_key("tabs", key_context)
            tab1, tab2 = st.tabs(["📄 요약", "📖 전체 내용"])

            with tab1:
                # 요약 탭 - 내용만 깔끔하게
                st.markdown(f"**💬 요약:** {preview}")

            with tab2:
                # 전체 내용 탭 - 메타데이터 포함

                # 상단에 메타데이터 표시
                meta_col1, meta_col2, meta_col3 = st.columns(3)

                with meta_col1:
                    st.caption(f"**유사도:** {score:.3f}")

                with meta_col2:
                    st.caption(f"**길이:** {len(content):,}자")

                with meta_col3:
                    # 신뢰도 바와 수치
                    confidence_color = "#22c55e" if confidence >= 0.8 else "#f59e0b" if confidence >= 0.6 else "#ef4444"
                    st.markdown(f"""
                    <div style="background-color: #e5e5e5; border-radius: 10px; height: 8px; margin: 5px 0;">
                        <div style="background-color: {confidence_color}; width: {int(confidence * 100)}%; height: 100%; 
                                    border-radius: 10px; transition: width 0.3s ease;"></div>
                    </div>
                    <small style="color: {confidence_color}; font-weight: bold;">신뢰도: {int(confidence * 100)}%</small>
                    """, unsafe_allow_html=True)

                st.divider()

                # 추가 메타데이터 (있는 경우)
                metadata = source.get("metadata", {})
                if metadata:
                    st.caption("📋 **문서 정보**")
                    meta_info_cols = st.columns(2)

                    meta_items = [(k, v) for k, v in metadata.items() if v]
                    for i, (key, value) in enumerate(meta_items[:4]):  # 최대 4개까지
                        with meta_info_cols[i % 2]:
                            st.caption(f"**{key}:** {value}")

                    if meta_items:
                        st.divider()

                # 🔧 전체 내용 - 고유 키 적용
                content_key = self._generate_unique_key("content_full", key_context)
                st.markdown("**📄 전체 내용**")
                st.text_area(
                    "전체 내용",
                    content,
                    height=200,
                    key=content_key,  # 고유 키 사용
                    disabled=True,
                    label_visibility="collapsed"
                )
        else:
            # 내용이 짧은 경우 - 단일 탭으로 표시 (고유 키 적용)
            short_tab_key = self._generate_unique_key("short_tabs", key_context)
            tab1, tab2 = st.tabs(["📄 내용", "📊 상세 정보"])

            with tab1:
                st.markdown(f"**💬 내용:** {content}")
                st.caption("✅ 전체 내용이 표시되었습니다.")

            with tab2:
                # 메타데이터만 표시
                meta_col1, meta_col2, meta_col3 = st.columns(3)

                with meta_col1:
                    st.metric("유사도", f"{score:.3f}")

                with meta_col2:
                    st.metric("길이", f"{len(content):,}자")

                with meta_col3:
                    st.metric("신뢰도", f"{int(confidence * 100)}%")

                # 추가 메타데이터
                metadata = source.get("metadata", {})
                if metadata:
                    st.divider()
                    st.caption("📋 **문서 정보**")

                    for key, value in metadata.items():
                        if value:
                            st.caption(f"**{key}:** {value}")

    def _render_search_summary(self, search_info: Dict, original_count: int, filtered_count: int) -> None:
        """검색 요약 정보 표시 - 필터링 정보 포함"""
        if not search_info:
            return

        # 🔧 expander 대신 일반 컨테이너 사용 (중첩 문제 해결)
        st.markdown("#### 🔍 검색 정보")

        cols = st.columns([1, 1, 1, 1])

        with cols[0]:
            st.metric("검색 시간", f"{search_info.get('search_time', 0):.2f}초")

        with cols[1]:
            st.metric("검색 방식", search_info.get('search_type', 'hybrid'))

        with cols[2]:
            st.metric("발견된 근거", f"{original_count}개")

        with cols[3]:
            if filtered_count != original_count:
                st.metric("표시된 근거", f"{filtered_count}개", delta=f"{filtered_count - original_count}")
            else:
                st.metric("표시된 근거", f"{filtered_count}개")

        st.divider()

    def get_current_settings_summary(self) -> Dict:
        """현재 설정 요약 반환"""
        rag_settings = SettingsManager.get_rag_settings()
        temp_min_sim = st.session_state.get('temp_min_similarity')

        return {
            "min_similarity_base": rag_settings['min_similarity'],
            "min_similarity_current": temp_min_sim or rag_settings['min_similarity'],
            "top_k": rag_settings['top_k'],
            "context_window": rag_settings['context_window'],
            "has_temp_override": temp_min_sim is not None,
            "settings_synced": st.session_state.get('ref_system_settings_synced', False)
        }

    # 🚀 사이드바 전용 설정 관리 함수들
    @staticmethod
    def render_sidebar_settings_panel():
        """사이드바 전용 설정 패널 (중복 방지)"""
        # 🔧 사이드바 전용 설정 상태 키
        sidebar_settings_key = 'sidebar_rag_settings_rendered'

        # 이미 렌더링되었으면 건너뛰기 (중복 방지)
        if st.session_state.get(sidebar_settings_key, False):
            return

        st.session_state[sidebar_settings_key] = True

        # 사이드바 전용 간단한 설정 패널
        st.subheader("🔧 근거 설정")

        # 현재 설정 가져오기
        rag_settings = SettingsManager.get_rag_settings()

        # 간단한 정보 표시
        col1, col2 = st.columns(2)

        with col1:
            st.metric("최소 유사도", f"{rag_settings['min_similarity']:.2f}")

        with col2:
            st.metric("근거 개수", rag_settings['top_k'])

        # Settings 페이지로 이동 버튼
        if st.button("⚙️ 설정 변경", key="sidebar_goto_settings", use_container_width=True):
            st.switch_page("pages/99_Settings.py")

        # 임시 조정 (최소한의 컨트롤)
        if st.checkbox("🎛️ 임시 조정", key="sidebar_enable_temp_adjust"):
            temp_min_sim = st.slider(
                "임시 최소 유사도",
                min_value=0.0,
                max_value=1.0,
                value=float(rag_settings['min_similarity']),
                step=0.05,
                key="sidebar_temp_min_similarity",
                help="현재 세션에만 적용됩니다"
            )

            # 전역 세션 상태에 저장
            st.session_state.temp_min_similarity = temp_min_sim

            # 리셋 버튼
            if st.button("🔄 리셋", key="sidebar_reset_temp"):
                if 'temp_min_similarity' in st.session_state:
                    del st.session_state.temp_min_similarity
                st.rerun()

    @staticmethod
    def clear_sidebar_settings_state():
        """사이드바 설정 상태 초기화 (대화 초기화시 호출)"""
        sidebar_keys = [
            'sidebar_rag_settings_rendered',
            'temp_min_similarity'
        ]

        for key in sidebar_keys:
            if key in st.session_state:
                del st.session_state[key]


# 추가 유틸리티 함수들
def _calculate_confidence_score(source: Dict) -> float:
    """근거 신뢰도 점수 계산 - 수정된 버전"""
    base_score = source.get("score", 0.0)
    content = source.get("content", "")
    content_length = len(content)

    # 기본 점수가 이미 1.0 이상이면 정규화
    if base_score >= 1.0:
        confidence = base_score / max(base_score, 1.2)  # 최대 기준점으로 정규화
    else:
        confidence = base_score

    # 보정 팩터들 (곱셈 방식으로 변경)
    length_factor = 1.0
    if 100 <= content_length <= 1000:
        length_factor = 1.05  # 5% 증가
    elif content_length > 1000:
        length_factor = 1.02  # 2% 증가
    elif content_length < 50:
        length_factor = 0.9   # 10% 감소

    # 메타데이터 품질 팩터
    metadata_factor = 1.0
    metadata = source.get("metadata", {})
    if metadata.get("title"):
        metadata_factor *= 1.03  # 3% 증가
    if metadata.get("section"):
        metadata_factor *= 1.02  # 2% 증가

    # 최종 계산 (곱셈 방식)
    final_confidence = confidence * length_factor * metadata_factor

    # 상한선 적용 (0.95로 제한하여 100% 방지)
    result = min(final_confidence, 0.95)

    return result


def calculate_overall_confidence(sources: List[Dict]) -> float:
    """전체 근거의 종합 신뢰도 계산"""
    if not sources:
        return 0.0

    # 가중 평균 계산 (상위 근거에 더 높은 가중치)
    total_weight = 0
    weighted_sum = 0

    for i, source in enumerate(sources[:5]):  # 상위 5개만 고려
        confidence = _calculate_confidence_score(source)
        weight = 1.0 / (i + 1)  # 순위가 높을수록 높은 가중치

        weighted_sum += confidence * weight
        total_weight += weight

    return weighted_sum / total_weight if total_weight > 0 else 0.0


def get_source_quality_grade(confidence: float) -> str:
    """근거 품질 등급 반환"""
    if confidence >= 0.9:
        return "A+ (매우 높음)"
    elif confidence >= 0.8:
        return "A (높음)"
    elif confidence >= 0.7:
        return "B+ (양호)"
    elif confidence >= 0.6:
        return "B (보통)"
    elif confidence >= 0.5:
        return "C+ (낮음)"
    elif confidence >= 0.4:
        return "C (매우 낮음)"
    else:
        return "D (부적절)"


def filter_sources_by_quality(sources: List[Dict], min_confidence: float = 0.5) -> List[Dict]:
    """품질 기준으로 근거 필터링"""
    filtered = []
    for source in sources:
        confidence = _calculate_confidence_score(source)
        if confidence >= min_confidence:
            filtered.append({**source, "confidence": confidence})

    return sorted(filtered, key=lambda x: x["confidence"], reverse=True)


# 글로벌 인스턴스
reference_system = InteractiveReferenceSystem()