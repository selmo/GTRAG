import streamlit as st
from frontend.ui.utils.client_manager import ClientManager
from frontend.ui.components.chat import ChatInterface  # Chat UI 재사용

# 페이지 설정 - 인터랙티브 레퍼런스 시스템 소개
st.set_page_config(
    page_title="GTOne RAG Chat - Interactive References",
    page_icon="🔗",
    layout="wide",
    menu_items={
        'About': """
        # GTOne RAG Chat - Interactive References

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

# 사이드바에 기능 안내
with st.sidebar:
    st.markdown("### 🔗 인터랙티브 레퍼런스")
    st.markdown("""
    **✨ 새로운 기능!**
    - 답변 속 참조 번호 클릭
    - 호버 시 미리보기 팝업
    - 양방향 네비게이션
    - 키보드 단축키 (Ctrl+숫자)
    """)

    st.markdown("### 🎯 근거 표시 설정")
    st.markdown("""
    **신뢰도 필터**: 낮은 품질의 근거 제외
    **정렬 방식**: 근거 표시 순서 조정
    **상세 표시**: 메타데이터 및 통계 확인
    """)

    st.divider()

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

# 메인 채팅 인터페이스
# 🔧 클라이언트 캐싱으로 불필요한 재생성 방지
if 'api_client_cached' not in st.session_state:
    st.session_state.api_client_cached = ClientManager.get_client()

api_client = st.session_state.api_client_cached

# 🔧 클라이언트 유효성 검사 (10분마다)
if not ClientManager.is_client_valid():
    st.session_state.api_client_cached = ClientManager.get_client(force_refresh=True)
    api_client = st.session_state.api_client_cached

chat_interface = ChatInterface(api_client)

# 🚀 레퍼런스 시스템 소개 (첫 방문 시)
if 'reference_intro_shown' not in st.session_state:
    st.session_state.reference_intro_shown = True

    st.info("""
    🔗 **새로운 인터랙티브 레퍼런스 시스템이 적용되었습니다!**

    이제 AI 답변 속 참조 번호 [1], [2]를 클릭하면 해당 근거로 바로 이동할 수 있고, 
    마우스를 올리면 미리보기 팝업을 확인할 수 있습니다. 

    더 자세한 사용법은 사이드바의 "📖 레퍼런스 가이드 보기"를 확인해주세요.
    """)

# 성능 모니터링을 위한 메트릭
if 'chat_metrics' not in st.session_state:
    st.session_state.chat_metrics = {
        'total_queries': 0,
        'high_quality_responses': 0,
        'avg_response_time': 0,
        'reference_clicks': 0  # 🚀 레퍼런스 클릭 수 추가
    }

# 채팅 인터페이스 렌더링
chat_interface.render()

# 하단에 성능 지표 표시 (선택적)
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

# 피드백 수집
st.divider()
feedback_col1, feedback_col2 = st.columns([3, 1])

with feedback_col1:
    st.markdown("**💬 인터랙티브 레퍼런스 시스템에 대한 피드백을 남겨주세요**")

with feedback_col2:
    if st.button("📝 피드백 제출"):
        st.info("피드백이 개발팀에 전달됩니다. 감사합니다!")