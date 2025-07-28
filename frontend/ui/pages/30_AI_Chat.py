import streamlit as st
from frontend.ui.utils.client_manager import ClientManager
from frontend.ui.utils.session import SessionManager  # 🚀 추가
from frontend.ui.components.chat import ChatInterface  # Chat UI 재사용
import logging
import time  # 🔧 추가

# 페이지 설정 - 인터랙티브 레퍼런스 시스템 소개
st.set_page_config(
    page_title="AI Chat - Interactive References",
    page_icon="🔗",
    layout="wide",
    menu_items={
        'About': """
        # AI Chat - Interactive References

        ## 🚀 인터랙티브 레퍼런스 시스템
        - **스마트 레퍼런스**: AI 답변에 자동으로 참조 번호 삽입
        - **호버 미리보기**: 참조 번호에 마우스 올려 즉시 확인
        - **클릭 네비게이션**: 참조 번호 클릭으로 해당 근거로 이동
        - **양방향 이동**: 근거에서 본문으로 돌아가는 ↑ 버튼
        - **키보드 단축키**: Ctrl+숫자로 빠른 근거 이동

        ## 🎯 근거 표시 강화
        - **신뢰도 점수**: 관련도 분석 및 인용문 추출
        - **스마트 필터링**: 신뢰도 기준 필터링, 품질 등급 분류
        - **시각적 효과**: 하이라이팅 및 부드러운 애니메이션
        - **세션 분석**: 대화 품질 분석 및 근거 품질 검토

        ## 💡 사용 팁
        1. 답변 속 [1], [2] 등의 참조 번호에 마우스를 올려 미리보기 확인
        2. 참조 번호를 클릭하여 상세 근거로 이동
        3. 근거 카드의 ↑ 버튼으로 읽던 위치로 돌아가기
        4. Ctrl+1~9 키로 해당 번호의 근거로 빠른 이동
        5. 사이드바에서 신뢰도 기준과 정렬 방식 조정
        """
    }
)

# 🚀 페이지 진입 시 설정 동기화 (서버 설정 우선)
try:
    # 1단계: 기본 세션 상태 초기화 (기본값 로드)
    if 'ai_settings' not in st.session_state:
        st.session_state.ai_settings = SessionManager.get_default_ai_settings()

    # 2단계: 서버 설정 동기화 (서버 설정이 있으면 덮어쓰기)
    with st.spinner("서버 설정 동기화 중..."):
        settings_loaded = SessionManager.sync_ai_settings_from_server(force_refresh=True)

        if settings_loaded:
            st.success("✅ 서버에서 저장된 설정을 불러왔습니다")
        else:
            st.info("💡 저장된 설정이 없어 기본값을 사용합니다")

    # 3단계: 페이지별 설정 보장
    page_settings_ok = SessionManager.ensure_page_settings_loaded("AI Chat")

    if not page_settings_ok:
        st.warning("⚠️ 일부 설정을 로드하지 못했습니다.")

    # 🔧 필수 설정 검증
    selected_model = st.session_state.get('selected_model')

    if not selected_model:
        st.error("❌ AI 모델이 설정되지 않았습니다.")
        st.info("💡 설정 페이지에서 모델을 선택하거나 자동 설정을 시도해보세요.")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("⚙️ 설정 페이지로 이동", type="primary"):
                st.switch_page("pages/99_Settings.py")
        with col2:
            if st.button("🔄 설정 다시 로드"):
                SessionManager.clear_settings_cache()
                st.rerun()
        with col3:
            if st.button("🤖 자동 모델 설정"):
                try:
                    # 자동으로 첫 번째 사용 가능한 모델 선택
                    api_client = ClientManager.get_client()
                    available_models = api_client.get_available_models()
                    if available_models:
                        auto_model = available_models[0]
                        st.session_state.selected_model = auto_model
                        st.session_state.ai_settings['llm']['model'] = auto_model
                        st.success(f"✅ 자동으로 '{auto_model}' 모델을 선택했습니다")
                        st.rerun()
                    else:
                        st.error("❌ 사용 가능한 모델이 없습니다")
                except Exception as e:
                    st.error(f"❌ 자동 설정 실패: {e}")

        st.stop()  # 설정이 없으면 페이지 중단

# AI Chat 페이지의 클라이언트 초기화 에러 처리 개선 부분

except Exception as e:
    client_error = str(e)
    logging.error(f"❌ API 클라이언트 초기화 실패: {e}")

    # 사용자 친화적 에러 메시지
    st.error("❌ AI 서비스 연결에 실패했습니다.")

    # 오류 유형별 맞춤 메시지
    if "connection" in client_error.lower() or "연결" in client_error:
        st.warning("🔌 서버 연결 문제가 발생했습니다.")
        st.info("💡 Ollama 서버가 실행 중인지 확인해주세요.")
    elif "timeout" in client_error.lower():
        st.warning("⏱️ 서버 응답 시간이 초과되었습니다.")
        st.info("💡 잠시 후 다시 시도하거나 관리자에게 문의해주세요.")
    elif "permission" in client_error.lower() or "권한" in client_error:
        st.warning("🔐 접근 권한 문제가 발생했습니다.")
        st.info("💡 관리자에게 권한 설정을 문의해주세요.")
    else:
        st.warning("⚠️ 예상치 못한 오류가 발생했습니다.")
        st.info("💡 아래의 해결 방법을 시도해보세요.")

    # 상세 오류 정보 (선택적 표시)
    with st.expander("🔧 기술적 오류 정보", expanded=False):
        st.code(f"오류 유형: {type(e).__name__}")
        st.code(f"오류 메시지: {client_error}")

        # 클라이언트 상태 진단
        st.write("**클라이언트 상태 진단:**")
        st.write(f"- api_client: {type(api_client)}")
        st.write(f"- 세션 캐시: {type(st.session_state.get('api_client_cached'))}")

        client_info = ClientManager.get_client_info()
        st.write("**ClientManager 정보:**")
        for key, value in client_info.items():
            st.write(f"- {key}: {value}")

    # 단계별 문제 해결 가이드
    st.subheader("🛠️ 단계별 문제 해결")

    with st.expander("1단계: 기본 확인사항", expanded=True):
        st.markdown("""
        **먼저 확인해주세요:**
        - 인터넷 연결 상태가 정상인가요?
        - 다른 브라우저 탭에서도 같은 문제가 발생하나요?
        - 최근에 설정을 변경하셨나요?
        """)

        col_check1, col_check2 = st.columns(2)
        with col_check1:
            if st.button("🔄 페이지 새로고침", type="primary", key="refresh_page"):
                st.rerun()
        with col_check2:
            if st.button("🏠 홈으로 이동", key="go_home"):
                st.switch_page("Home.py")

    with st.expander("2단계: 서비스 재시작", expanded=False):
        st.markdown("""
        **서비스 재시작을 시도해보세요:**
        - 클라이언트 연결을 초기화합니다
        - 캐시된 설정을 새로고침합니다
        - 서버와의 연결을 재설정합니다
        """)

        col_restart1, col_restart2 = st.columns(2)
        with col_restart1:
            if st.button("🔄 클라이언트 재시작", key="restart_client"):
                with st.spinner("클라이언트 재시작 중..."):
                    ClientManager.reset_client()
                    if 'api_client_cached' in st.session_state:
                        del st.session_state['api_client_cached']
                    SessionManager.clear_settings_cache()
                    time.sleep(1)
                st.success("✅ 클라이언트 재시작 완료")
                st.info("🔄 페이지를 새로고침하여 다시 시도해주세요.")

        with col_restart2:
            if st.button("⚙️ 설정 초기화", key="reset_settings"):
                with st.spinner("설정 초기화 중..."):
                    SessionManager.clear_settings_cache()
                    # 기본 설정으로 재설정
                    st.session_state.ai_settings = SessionManager.get_default_ai_settings()
                    time.sleep(1)
                st.success("✅ 설정 초기화 완료")
                st.info("⚙️ 설정 페이지에서 다시 구성해주세요.")

    with st.expander("3단계: 고급 해결책", expanded=False):
        st.markdown("""
        **고급 문제 해결:**
        - 서버 상태를 확인합니다
        - 시스템 설정을 점검합니다
        - 관리자 도구를 사용합니다
        """)

        col_advanced1, col_advanced2, col_advanced3 = st.columns(3)

        with col_advanced1:
            if st.button("🔧 서버 상태 확인", key="check_server"):
                st.switch_page("pages/99_Settings.py")

        with col_advanced2:
            if st.button("📊 시스템 진단", key="system_diagnosis"):
                st.info("시스템 진단 기능은 설정 페이지에서 이용할 수 있습니다.")

        with col_advanced3:
            if st.button("📞 관리자 문의", key="contact_admin"):
                st.info("""
                **관리자 문의 시 포함할 정보:**
                - 오류가 발생한 시간
                - 위의 기술적 오류 정보
                - 시도해본 해결 방법
                """)

    # 임시 해결책 제안
    st.divider()
    st.subheader("🚀 임시 해결책")

    col_temp1, col_temp2 = st.columns(2)

    with col_temp1:
        st.markdown("""
        **📄 문서 검색만 사용하기**

        AI 채팅 기능에 문제가 있어도 문서 검색은 사용할 수 있습니다.
        """)
        if st.button("🔍 문서 검색으로 이동", key="go_search"):
            st.switch_page("pages/03_Search.py")

    with col_temp2:
        st.markdown("""
        **⚙️ 설정 확인하기**

        서버 설정과 연결 상태를 확인하여 문제를 해결해보세요.
        """)
        if st.button("⚙️ 설정 페이지로 이동", key="go_settings_final"):
            st.switch_page("pages/99_Settings.py")

    st.stop()  # 클라이언트 없이는 진행 불가

# 사이드바에 기능 안내
with st.sidebar:
    # st.markdown("### 🔗 인터랙티브 레퍼런스")
    # st.markdown("""
    # **✨ 새로운 기능!**
    # - 답변 속 참조 번호 클릭
    # - 호버 시 미리보기 팝업
    # - 양방향 네비게이션
    # - 키보드 단축키 (Ctrl+숫자)
    # """)
    #
    # st.markdown("### 🎯 근거 표시 설정")
    # st.markdown("""
    # **신뢰도 필터**: 낮은 품질의 근거 제외
    # **정렬 방식**: 근거 표시 순서 조정
    # **상세 표시**: 메타데이터 및 통계 확인
    # """)
    #
    # # 🚀 현재 설정 상태 표시 (동기화 정보 포함)
    # st.divider()
    #
    with st.expander("⚙️ 현재 설정", expanded=False):
        current_model = st.session_state.get('selected_model', '미설정')
        st.write(f"**모델**: {current_model}")

        ai_settings = st.session_state.get('ai_settings', {})
        llm_settings = ai_settings.get('llm', {})

        st.write(f"**온도**: {llm_settings.get('temperature', 'N/A')}")
        st.write(f"**최대 토큰**: {llm_settings.get('max_tokens', 'N/A')}")

        rag_settings = ai_settings.get('rag', {})
        st.write(f"**검색 개수**: {rag_settings.get('top_k', 'N/A')}")

        # 🚀 동기화 상태 정보
        st.caption("**동기화 상태**:")

        # 캐시 정보
        cache_info = SessionManager._cache_timestamp.get("ai_settings")
        if cache_info:
            cache_age = time.time() - cache_info
            st.caption(f"• 캐시 나이: {cache_age:.0f}초 전")
        else:
            st.caption("• 캐시: 없음")

        # 설정 소스 추적
        if st.session_state.get('settings_source'):
            st.caption(f"• 소스: {st.session_state.settings_source}")

        # 설정 새로고침 버튼
        col_refresh1, col_refresh2 = st.columns(2)
        with col_refresh1:
            if st.button("🔄 설정 새로고침", key="refresh_settings"):
                SessionManager.clear_settings_cache()
                st.rerun()

        with col_refresh2:
            if st.button("💾 서버 동기화", key="force_sync_settings"):
                with st.spinner("서버와 동기화 중..."):
                    success = SessionManager.sync_ai_settings_from_server(force_refresh=True)
                    if success:
                        st.success("✅ 동기화 완료")
                    else:
                        st.warning("⚠️ 동기화 실패")
                    st.rerun()

    # 레퍼런스 시스템 가이드 링크
    if st.button("📖 레퍼런스 가이드 보기"):
        # 가이드 모달 또는 expander로 표시
        with st.expander("🔗 인터랙티브 레퍼런스 시스템 가이드", expanded=True):
            st.markdown("""
            #### 🎯 주요 기능

            **📍 스마트 레퍼런스**
            - 답변에 자동으로 참조 번호 [1], [2] 삽입
            - 문맥에 맞는 최적 위치 선택

            **🖱️ 인터랙션**
            - 참조 번호 **호버**: 미리보기 팝업
            - 참조 번호 **클릭**: 해당 근거로 이동
            - 근거의 **↑ 버튼**: 본문으로 돌아가기

            **⌨️ 키보드 단축키**
            - `Ctrl + 1~9`: 해당 번호 근거로 빠른 이동

            **💡 사용 팁**
            1. 참조 번호에 마우스 올려 빠른 확인
            2. 클릭으로 상세 근거 탐색  
            3. ↑ 버튼으로 읽던 위치로 복귀
            4. 키보드로 빠른 네비게이션
            """)

    # 도움말 섹션
    with st.expander("❓ 사용 도움말", expanded=False):
        st.markdown("""
        **근거 신뢰도 이해**
        - 🟢 80% 이상: 매우 신뢰할 만한 근거
        - 🟡 60-80%: 적절한 근거
        - 🔴 40-60%: 주의해서 참고
        - ⚪ 40% 미만: 낮은 신뢰도

        **근거 품질 등급**
        - A+/A: 우수한 품질
        - B+/B: 양호한 품질  
        - C+/C: 개선 필요

        **레퍼런스 네비게이션**
        - 참조 번호 클릭: 해당 근거로 이동
        - 호버 미리보기: 빠른 내용 확인
        - 양방향 이동: 본문 ↔ 근거 자유 탐색
        """)

# 🚀 안전한 API 클라이언트 초기화
api_client = None
client_error = None

try:
    # 1단계: 기본 클라이언트 생성 시도
    if 'api_client_cached' not in st.session_state or st.session_state.api_client_cached is None:
        logging.info("🔄 새 API 클라이언트 생성 중...")
        st.session_state.api_client_cached = ClientManager.get_client()

    api_client = st.session_state.api_client_cached

    # 2단계: 클라이언트 유효성 검사
    if api_client is None:
        raise Exception("ClientManager가 None을 반환했습니다.")

    # 3단계: 클라이언트 기능 테스트
    if not hasattr(api_client, 'get_available_models'):
        raise Exception("API 클라이언트에 get_available_models 메서드가 없습니다.")

    # 4단계: 클라이언트 유효성 재검사 (10분마다)
    if not ClientManager.is_client_valid():
        logging.info("🔄 만료된 클라이언트 갱신 중...")
        st.session_state.api_client_cached = ClientManager.get_client(force_refresh=True)
        api_client = st.session_state.api_client_cached

        if api_client is None:
            raise Exception("클라이언트 갱신 후에도 None이 반환되었습니다.")

except Exception as e:
    client_error = str(e)
    logging.error(f"❌ API 클라이언트 초기화 실패: {e}")

    st.error("❌ API 클라이언트 초기화에 실패했습니다.")
    st.error(f"**오류 상세**: {client_error}")

    # 진단 정보 표시
    with st.expander("🔧 진단 정보", expanded=True):
        st.write("**클라이언트 상태**:")
        st.write(f"- api_client: {type(api_client)}")
        st.write(f"- 세션 캐시: {type(st.session_state.get('api_client_cached'))}")

        client_info = ClientManager.get_client_info()
        st.write("**ClientManager 정보**:")
        for key, value in client_info.items():
            st.write(f"- {key}: {value}")

    # 복구 옵션 제공
    st.subheader("🛠️ 문제 해결 방법")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 클라이언트 초기화", type="primary"):
            # 완전 초기화
            ClientManager.reset_client()
            if 'api_client_cached' in st.session_state:
                del st.session_state['api_client_cached']
            SessionManager.clear_settings_cache()
            st.rerun()

    with col2:
        if st.button("🏠 홈으로 돌아가기"):
            st.switch_page("Home.py")

    with col3:
        if st.button("⚙️ 설정 페이지"):
            st.switch_page("pages/99_Settings.py")

    st.stop()  # 클라이언트 없이는 진행 불가

# 🚀 모델 사용 가능성 검증
try:
    # 사용 가능한 모델 목록 가져오기
    available_models = api_client.get_available_models()
    selected_model = st.session_state.get('selected_model')

    if not available_models:
        st.error("❌ 사용 가능한 AI 모델이 없습니다.")
        st.info("💡 Ollama 서버가 실행 중인지 확인해주세요.")

        # 서버 상태 확인 링크
        if st.button("🔧 서버 상태 확인"):
            st.switch_page("pages/99_Settings.py")
        st.stop()

    # 선택된 모델 검증 및 자동 복구
    if not selected_model or selected_model not in available_models:
        if selected_model:
            st.warning(f"⚠️ 선택된 모델 '{selected_model}'을 찾을 수 없습니다.")

        # 자동으로 첫 번째 모델 선택
        new_model = available_models[0]
        st.session_state.selected_model = new_model

        # AI 설정에도 반영
        if 'ai_settings' in st.session_state:
            st.session_state.ai_settings['llm']['model'] = new_model

        st.success(f"🔄 자동으로 '{new_model}' 모델을 선택했습니다.")
        st.info("💡 다른 모델을 원하시면 설정 페이지에서 변경할 수 있습니다.")

        time.sleep(1)  # 사용자가 메시지를 읽을 시간
        st.rerun()

    # ChatInterface 생성
    chat_interface = ChatInterface(api_client)

except Exception as e:
    st.error(f"❌ 모델 검증 실패: {e}")

    # 상세 오류 정보
    with st.expander("🔧 오류 상세 정보"):
        st.exception(e)
        st.write("**현재 설정:**")
        st.write(f"- 선택된 모델: {st.session_state.get('selected_model', '없음')}")
        st.write(f"- AI 설정 존재: {'✅' if st.session_state.get('ai_settings') else '❌'}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 다시 시도"):
            st.rerun()
    with col2:
        if st.button("⚙️ 설정으로 이동"):
            st.switch_page("pages/99_Settings.py")
    st.stop()

# # 🚀 레퍼런스 시스템 소개 (첫 방문 시) - 기존 로직 유지
# if 'reference_intro_shown' not in st.session_state:
#     st.session_state.reference_intro_shown = True
#
#     st.info("""
#     🔗 **새로운 인터랙티브 레퍼런스 시스템이 적용되었습니다!**
#
#     이제 AI 답변 속 참조 번호 [1], [2]를 클릭하면 해당 근거로 바로 이동할 수 있고,
#     마우스를 올리면 미리보기 팝업을 확인할 수 있습니다.
#
#     더 자세한 사용법은 사이드바의 "📖 레퍼런스 가이드 보기"를 확인해주세요.
#     """)

# 성능 모니터링을 위한 메트릭 - 기존 로직 유지
if 'chat_metrics' not in st.session_state:
    st.session_state.chat_metrics = {
        'total_queries': 0,
        'high_quality_responses': 0,
        'avg_response_time': 0,
        'reference_clicks': 0  # 🚀 레퍼런스 클릭 수 추가
    }

# 🚀 설정 동기화 성공 알림 (디버깅용, 운영 시 제거 가능)
if st.session_state.get('show_debug_info', False):
    with st.expander("🔧 디버그 정보", expanded=False):
        st.write("**설정 동기화 상태**:", "✅ 완료" if settings_loaded else "❌ 실패")
        st.write("**선택된 모델**:", st.session_state.get('selected_model', '없음'))
        st.write("**AI 설정 존재**:", "✅" if st.session_state.get('ai_settings') else "❌")

        client_info = ClientManager.get_client_info()
        st.write("**클라이언트 상태**:", client_info)

# 채팅 인터페이스 렌더링
chat_interface.render()

# 하단에 성능 지표 표시 (선택적) - 기존 로직 유지
if st.session_state.get('messages', []):
    with st.expander("📈 세션 성능 지표", expanded=False):
        metrics = st.session_state.chat_metrics

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("총 질문 수", metrics['total_queries'])
        with col2:
            st.metric("고품질 응답", metrics['high_quality_responses'])
        with col3:
            st.metric("평균 응답시간", f"{metrics['avg_response_time']:.1f}초")
        with col4:
            st.metric("레퍼런스 활용", metrics.get('reference_clicks', 0))

# 피드백 수집 - 기존 로직 유지
# st.divider()
# feedback_col1, feedback_col2 = st.columns([3, 1])
#
# with feedback_col1:
#     st.markdown("**💬 인터랙티브 레퍼런스 시스템에 대한 피드백을 남겨주세요**")
#
# with feedback_col2:
#     if st.button("📝 피드백 제출"):
#         st.info("피드백이 개발팀에 전달됩니다. 감사합니다!")