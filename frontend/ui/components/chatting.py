"""
채팅 인터페이스 컴포넌트 - 개선된 버전
통합된 시스템 상태 관리자를 사용하여 모델 설정과 상태 확인 개선
"""
import streamlit as st
from typing import Dict, List, Optional
from datetime import datetime
from frontend.ui.utils.streamlit_helpers import rerun
from frontend.ui.utils.system_health import SystemHealthManager


def get_model_settings():
    """설정 페이지에서 저장한 모델 설정을 가져오기"""
    return {
        'model': st.session_state.get('selected_model'),
        'temperature': st.session_state.get('temperature', 0.3),
        'system_prompt': st.session_state.get('system_prompt',
                                              "당신은 문서 기반 질의응답 시스템입니다. 제공된 문서의 내용만을 바탕으로 정확하고 도움이 되는 답변을 제공하세요."),
        'rag_top_k': st.session_state.get('rag_top_k', 3),
        'min_similarity': st.session_state.get('min_similarity', 0.5),
        'rag_timeout': st.session_state.get('rag_timeout', 300),
        'api_timeout': st.session_state.get('api_timeout', 300),
        'max_tokens': st.session_state.get('max_tokens', 1000),
        'top_p': st.session_state.get('top_p', 0.9),
        'frequency_penalty': st.session_state.get('frequency_penalty', 0.0),
        'context_window': st.session_state.get('context_window', 3000),
        'search_type': st.session_state.get('search_type', 'hybrid')
    }


def check_model_availability(api_client):
    """모델 사용 가능 여부 확인 - 통합 시스템 상태 관리자 사용"""
    return SystemHealthManager.check_model_availability(api_client)


def render_chat_history():
    """채팅 히스토리 렌더링"""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # 소스 문서 표시
            if message["role"] == "assistant" and "sources" in message:
                render_sources(message["sources"])

            # 메시지에 사용된 모델 정보 표시 (옵션)
            if message["role"] == "assistant" and "model_used" in message:
                with st.expander("🤖 생성 정보", expanded=False):
                    st.caption(f"사용된 모델: {message['model_used']}")
                    if "search_info" in message:
                        search_info = message["search_info"]
                        st.caption(f"검색된 문서: {search_info.get('total_results', 0)}개")
                        st.caption(f"검색 유형: {search_info.get('search_type', 'unknown')}")

                    # 설정 정보도 표시
                    if "settings_used" in message:
                        settings = message["settings_used"]
                        st.caption(f"Temperature: {settings.get('temperature', 'N/A')}")
                        st.caption(f"검색 문서 수: {settings.get('top_k', 'N/A')}")


def render_sources(sources: List[Dict]):
    """참조 문서 렌더링 - 개선된 버전"""
    if not sources:
        return

    with st.expander(f"📌 참조 문서 ({len(sources)}개)", expanded=False):
        for idx, source in enumerate(sources, 1):
            # 소스 정보 표시
            score = source.get('score', 0)
            source_name = source.get('source', 'Unknown')
            content = source.get('content', '')

            # 점수에 따른 색상 구분
            if score >= 0.8:
                score_color = "🟢"
            elif score >= 0.6:
                score_color = "🟡"
            else:
                score_color = "🔴"

            st.write(f"{score_color} **[문서 {idx}] {source_name}** (유사도: {score:.3f})")

            # 내용 미리보기 (길면 축약)
            if len(content) > 300:
                preview = content[:300] + "..."
                with st.expander(f"내용 미리보기", expanded=False):
                    st.text(preview)
                    st.text("--- 전체 내용 ---")
                    st.text(content)
            else:
                st.text(content)

            if idx < len(sources):
                st.divider()


def display_current_settings_sidebar(api_client):
    """사이드바에 현재 설정 표시 - 시스템 상태 통합"""
    with st.sidebar:
        st.header("🔧 현재 설정")

        settings = get_model_settings()

        # 모델 설정 표시
        if settings['model']:
            st.success(f"**모델**: {settings['model']}")
            st.write(f"**Temperature**: {settings['temperature']}")
            st.write(f"**검색 문서 수**: {settings['rag_top_k']}")
            st.write(f"**최소 유사도**: {settings['min_similarity']}")
            st.write(f"**타임아웃**: {settings['rag_timeout']}초")
        else:
            st.error("❌ 모델이 선택되지 않음")
            if st.button("⚙️ 설정 페이지로", key="go_to_settings"):
                st.switch_page("pages/99_Settings.py")

        st.divider()

        # 빠른 설정 변경
        st.subheader("빠른 설정")

        # 시스템 상태 확인 (통합 관리자 사용)
        if st.button("🔄 모델 상태 확인", key="check_model_status"):
            with st.spinner("모델 상태 확인 중..."):
                is_available, error_msg = SystemHealthManager.check_model_availability(api_client)

                if is_available:
                    st.success("✅ 모델 사용 가능")
                else:
                    st.error(f"❌ {error_msg}")

        # 빠른 검색 설정 조정
        st.subheader("빠른 조정")

        # 검색 문서 수 빠른 조정
        quick_top_k = st.slider(
            "검색 문서 수",
            min_value=1,
            max_value=10,
            value=settings['rag_top_k'],
            key="quick_top_k"
        )
        if quick_top_k != settings['rag_top_k']:
            st.session_state.rag_top_k = quick_top_k

        # 최소 유사도 빠른 조정
        quick_min_score = st.slider(
            "최소 유사도",
            min_value=0.0,
            max_value=1.0,
            value=settings['min_similarity'],
            step=0.1,
            key="quick_min_score"
        )
        if quick_min_score != settings['min_similarity']:
            st.session_state.min_similarity = quick_min_score

        # 전체 시스템 상태 표시 (간단)
        st.divider()
        display_system_status_compact(api_client)


def display_system_status_compact(api_client):
    """시스템 상태 간단 표시"""
    st.subheader("📊 시스템 상태")

    # 캐시된 상태 활용
    cached_status = SystemHealthManager.get_cached_status()

    if cached_status:
        # 전체 상태
        emoji, message, _ = SystemHealthManager.get_status_display_info(cached_status.overall_status)

        if cached_status.overall_status.value in ['healthy', 'degraded']:
            st.success(f"{emoji} 사용 가능")
        else:
            st.error(f"{emoji} 문제 있음")

        # 핵심 서비스 상태
        core_services = ['qdrant', 'ollama', 'embedder']
        service_status = []

        for service in core_services:
            if service in cached_status.services:
                service_info = cached_status.services[service]
                emoji, _ = SystemHealthManager.get_service_display_info(service_info.status)
                service_status.append(emoji)

        if service_status:
            st.caption(" ".join(service_status))

        st.caption(f"최종 확인: {cached_status.last_updated.strftime('%H:%M:%S')}")
    else:
        st.info("상태 미확인")
        if st.button("확인", key="check_status_compact"):
            SystemHealthManager.check_full_system_status(api_client, force_refresh=True)
            rerun()


def handle_chat_input(api_client):
    """채팅 입력 처리 - 통합 시스템 상태 관리 사용"""

    # 모델 사용 가능 여부 사전 확인 (통합 관리자 사용)
    is_model_available, model_error = SystemHealthManager.check_model_availability(api_client)

    if not is_model_available:
        st.error(f"🚫 {model_error}")
        st.info("💡 설정 페이지에서 모델을 선택한 후 사용해주세요.")
        return False  # 채팅 입력 비활성화

    if prompt := st.chat_input("질문을 입력하세요..."):
        # 현재 설정 가져오기
        settings = get_model_settings()

        # 실시간으로 모델 상태 재확인
        is_available, error_msg = SystemHealthManager.check_model_availability(api_client)
        if not is_available:
            st.error(f"🚫 {error_msg}")
            return False

        # 사용자 메시지 추가
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now().isoformat()
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        # AI 응답 생성
        with st.chat_message("assistant"):
            response_placeholder = st.empty()

            with st.spinner(f"'{settings['model']}'으로 답변 생성 중..."):
                try:
                    # API 클라이언트 타임아웃 설정
                    api_client.set_timeout(settings['api_timeout'])

                    # 설정 페이지의 모든 설정을 적용하여 RAG 답변 요청
                    result = api_client.generate_answer(
                        query=prompt,
                        model=settings['model'],  # ✅ 설정된 모델 사용
                        temperature=settings['temperature'],  # ✅ 설정된 온도 사용
                        system_prompt=settings['system_prompt'],  # ✅ 설정된 시스템 프롬프트 사용
                        top_k=settings['rag_top_k'],  # ✅ 설정된 검색 문서 수 사용
                        min_score=settings['min_similarity'],  # ✅ 설정된 최소 유사도 사용
                        search_type=settings['search_type'],  # ✅ 설정된 검색 타입 사용
                        timeout=settings['rag_timeout']  # ✅ 설정된 RAG 타임아웃 사용
                    )

                    if 'error' not in result:
                        # 답변 표시
                        answer = result.get('answer', '응답을 생성할 수 없습니다.')
                        response_placeholder.markdown(answer)

                        # 검색 정보 표시
                        search_info = result.get('search_info', {})
                        if search_info:
                            total_results = search_info.get('total_results', 0)
                            search_type_used = search_info.get('search_type', 'unknown')
                            contexts_used = search_info.get('contexts_used', 0)

                            # 검색 결과에 따른 메시지
                            if total_results > 0:
                                st.success(f"🔍 {total_results}개 문서에서 {contexts_used}개 컨텍스트 사용 (검색: {search_type_used})")
                            else:
                                st.warning(f"⚠️ 관련 문서를 찾지 못했습니다 (검색: {search_type_used})")

                            # 모델 정보 표시
                            st.caption(f"🤖 모델: {settings['model']} | 온도: {settings['temperature']}")

                        # 소스 문서 표시
                        sources = result.get('sources', [])
                        if sources:
                            render_sources(sources)

                        # 메시지 저장 (상세 정보 포함)
                        message_data = {
                            "role": "assistant",
                            "content": answer,
                            "timestamp": datetime.now().isoformat(),
                            "model_used": settings['model'],
                            "settings_used": {
                                "temperature": settings['temperature'],
                                "top_k": settings['rag_top_k'],
                                "min_similarity": settings['min_similarity'],
                                "search_type": settings['search_type']
                            }
                        }

                        # 소스와 검색 정보가 있으면 추가
                        if sources:
                            message_data['sources'] = sources
                        if search_info:
                            message_data['search_info'] = search_info

                        st.session_state.messages.append(message_data)

                    else:
                        # 에러 처리
                        error_msg = result.get('error', '알 수 없는 오류')
                        handle_error(error_msg, settings['model'])

                except Exception as e:
                    handle_error(str(e), settings['model'])

    return True


def handle_error(error_msg: str, model_used: str = None):
    """에러 처리 - 개선된 버전"""

    # 에러 유형별 메시지 커스터마이징
    if "timeout" in error_msg.lower() or "시간 초과" in error_msg:
        error_text = f"⏰ 응답 시간이 초과되었습니다. 더 간단한 질문을 시도해보세요.\n상세: {error_msg}"
        if model_used:
            error_text += f"\n사용된 모델: {model_used}"
    elif "연결" in error_msg or "connection" in error_msg.lower():
        error_text = f"🔌 서버 연결에 문제가 있습니다. 잠시 후 다시 시도해주세요.\n상세: {error_msg}"
    elif "모델" in error_msg or "model" in error_msg.lower():
        error_text = f"🤖 모델 관련 문제가 발생했습니다. 설정을 확인해주세요.\n상세: {error_msg}"
    else:
        error_text = f"❌ 오류가 발생했습니다: {error_msg}"
        if model_used:
            error_text += f"\n사용된 모델: {model_used}"

    st.error(error_text)

    # 에러 해결 제안
    with st.expander("💡 해결 방안"):
        st.markdown("""
        **일반적인 해결 방법:**
        1. **모델 상태 확인**: 설정 페이지에서 모델이 정상인지 확인
        2. **네트워크 연결**: API 서버 연결 상태 확인
        3. **타임아웃 조정**: 설정에서 타임아웃 시간을 늘려보세요
        4. **질문 단순화**: 더 간단하고 구체적인 질문으로 시도
        5. **시스템 재시작**: 문제가 지속되면 시스템 재시작
        """)

    # 에러 메시지도 히스토리에 추가
    st.session_state.messages.append({
        "role": "assistant",
        "content": error_text,
        "timestamp": datetime.now().isoformat(),
        "is_error": True,
        "model_used": model_used
    })


def clear_chat_history():
    """채팅 히스토리 초기화"""
    if st.session_state.get('messages'):
        st.session_state.messages = []
        st.success("✅ 대화 내역이 초기화되었습니다.")
        rerun()
    else:
        st.info("초기화할 대화 내역이 없습니다.")


def export_chat_history():
    """채팅 히스토리 내보내기 - 개선된 버전"""
    if st.session_state.get('messages'):
        import json

        # 현재 설정 정보도 함께 내보내기
        settings = get_model_settings()

        chat_data = {
            "exported_at": datetime.now().isoformat(),
            "export_settings": settings,
            "total_messages": len(st.session_state.messages),
            "messages": st.session_state.messages
        }

        st.download_button(
            label="💾 대화 내역 다운로드",
            data=json.dumps(chat_data, ensure_ascii=False, indent=2),
            file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            help="대화 내역과 사용된 설정을 JSON 파일로 다운로드합니다."
        )
    else:
        st.info("내보낼 대화 내역이 없습니다.")


def display_chat_stats():
    """채팅 통계 표시"""
    if st.session_state.get('messages'):
        messages = st.session_state.messages
        total_messages = len(messages)
        user_messages = len([m for m in messages if m['role'] == 'user'])
        assistant_messages = len([m for m in messages if m['role'] == 'assistant'])
        error_messages = len([m for m in messages if m.get('is_error', False)])

        # 사용된 모델들 집계
        models_used = set()
        for m in messages:
            if m['role'] == 'assistant' and 'model_used' in m:
                models_used.add(m['model_used'])

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("총 메시지", total_messages)

        with col2:
            st.metric("질문", user_messages)

        with col3:
            st.metric("답변", assistant_messages)

        with col4:
            st.metric("오류", error_messages, delta="문제" if error_messages > 0 else None)

        if models_used:
            st.caption(f"🤖 사용된 모델: {', '.join(models_used)}")


def display_model_change_notification():
    """모델 변경 알림 표시"""
    current_model = st.session_state.get('selected_model')
    previous_model = st.session_state.get('previous_chat_model')

    if previous_model and current_model and previous_model != current_model:
        st.info(f"🔄 모델이 '{previous_model}'에서 '{current_model}'로 변경되었습니다.")

    # 현재 모델을 이전 모델로 저장
    st.session_state.previous_chat_model = current_model


def render_chat_interface(api_client):
    """전체 채팅 인터페이스 렌더링"""

    # 설정 표시 사이드바
    display_current_settings_sidebar(api_client)

    # 모델 변경 알림
    display_model_change_notification()

    # 메인 채팅 영역
    st.title("💬 GTOne RAG Chat")

    # 상단 상태 표시
    render_chat_status_header(api_client)

    # 상단 컨트롤
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.write("### 대화")

    with col2:
        if st.button("🗑️ 대화 초기화"):
            clear_chat_history()

    with col3:
        export_chat_history()

    # 메시지 히스토리 표시
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if st.session_state.messages:
        render_chat_history()
    else:
        st.info("💡 질문을 입력하여 대화를 시작하세요.")

    # 채팅 입력 처리
    chat_active = handle_chat_input(api_client)

    # 하단 통계
    if st.session_state.messages:
        st.divider()
        display_chat_stats()

    return chat_active


def render_chat_status_header(api_client):
    """채팅 상단 상태 표시"""

    # 모델 상태 확인
    is_available, error_msg = SystemHealthManager.check_model_availability(api_client)

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        if is_available:
            model_name = st.session_state.get('selected_model', 'Unknown')
            st.success(f"🤖 {model_name} 사용 준비 완료")
        else:
            st.error(f"🚫 모델 사용 불가")
            st.caption(error_msg)

    with col2:
        # 시스템 상태 간단 표시
        cached_status = SystemHealthManager.get_cached_status()
        if cached_status:
            emoji, _, _ = SystemHealthManager.get_status_display_info(cached_status.overall_status)
            status_text = {
                'healthy': '정상',
                'degraded': '일부 문제',
                'unhealthy': '문제',
                'initializing': '초기화',
                'error': '오류'
            }.get(cached_status.overall_status.value, '알 수 없음')

            if cached_status.overall_status.value in ['healthy', 'degraded']:
                st.info(f"{emoji} 시스템 {status_text}")
            else:
                st.warning(f"{emoji} 시스템 {status_text}")
        else:
            st.info("🔄 상태 확인 필요")

    with col3:
        # 빠른 설정 버튼
        if st.button("⚙️ 설정", key="quick_settings"):
            st.switch_page("pages/99_Settings.py")


def render_enhanced_chat_input(api_client):
    """향상된 채팅 입력 (추가 기능)"""

    # 입력 전 상태 확인
    settings = get_model_settings()
    is_available, error_msg = SystemHealthManager.check_model_availability(api_client)

    # 입력 상태에 따른 플레이스홀더 및 비활성화
    if not is_available:
        placeholder = f"모델이 준비되지 않았습니다: {error_msg}"
        disabled = True
    elif not settings['model']:
        placeholder = "모델을 선택해주세요 (설정 페이지)"
        disabled = True
    else:
        placeholder = f"{settings['model']}에게 질문하세요..."
        disabled = False

    # 채팅 입력
    user_input = st.chat_input(
        placeholder=placeholder,
        disabled=disabled,
        key="enhanced_chat_input"
    )

    if user_input and not disabled:
        # 입력 처리는 기존 함수 활용
        process_user_input(user_input, api_client)


def process_user_input(user_input: str, api_client):
    """사용자 입력 처리 (분리된 함수)"""

    settings = get_model_settings()

    # 입력 검증
    if len(user_input.strip()) < 2:
        st.warning("⚠️ 더 구체적인 질문을 입력해주세요.")
        return

    # 사용자 메시지 추가
    st.session_state.messages.append({
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now().isoformat()
    })

    # 페이지 새로고침으로 메시지 표시
    rerun()


def get_chat_context_info():
    """채팅 컨텍스트 정보 반환"""
    if not st.session_state.get('messages'):
        return {
            'total_messages': 0,
            'conversation_length': 0,
            'last_model_used': None
        }

    messages = st.session_state.messages
    user_messages = [m for m in messages if m['role'] == 'user']
    assistant_messages = [m for m in messages if m['role'] == 'assistant']

    # 마지막 사용 모델
    last_model = None
    for msg in reversed(assistant_messages):
        if 'model_used' in msg:
            last_model = msg['model_used']
            break

    # 대화 길이 계산 (문자 수)
    total_chars = sum(len(msg['content']) for msg in messages)

    return {
        'total_messages': len(messages),
        'user_messages': len(user_messages),
        'assistant_messages': len(assistant_messages),
        'conversation_length': total_chars,
        'last_model_used': last_model
    }


def render_conversation_summary():
    """대화 요약 표시"""
    context = get_chat_context_info()

    if context['total_messages'] == 0:
        return

    with st.expander(f"📊 대화 요약 ({context['total_messages']}개 메시지)"):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("질문 수", context['user_messages'])

        with col2:
            st.metric("답변 수", context['assistant_messages'])

        with col3:
            st.metric("총 문자", f"{context['conversation_length']:,}")

        if context['last_model_used']:
            st.caption(f"마지막 사용 모델: {context['last_model_used']}")


# 호환성을 위한 기존 함수명 유지
def check_model_availability_legacy(api_client):
    """기존 호환성을 위한 함수 (deprecated)"""
    return SystemHealthManager.check_model_availability(api_client)