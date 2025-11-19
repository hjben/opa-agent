import streamlit as st
import requests
import threading
import queue

from config.url_config import MCP_CLIENT_URL
from streamlit_autorefresh import st_autorefresh

# -------------------------------------------------
# 페이지 설정
# -------------------------------------------------
st.set_page_config(page_title="OPA Chat", layout="centered")

# -------------------------------------------------
# 세션 상태 초기화
# -------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "loading" not in st.session_state:
    st.session_state.loading = False

if "response_queue" not in st.session_state:
    st.session_state.response_queue = queue.Queue()

if "thread_running" not in st.session_state:
    st.session_state.thread_running = False

# -------------------------------------------------
# 백엔드 비동기 호출 스레드 (대화 컨텍스트 포함)
# -------------------------------------------------
def call_backend_with_context(user_text: str, messages: list, q: queue.Queue):
    """백엔드를 비동기로 호출하여 응답 내용을 Queue에 넣음"""
    try:
        # 스레드에서는 st.session_state 접근하지 않고, messages 복사본 사용
        payload = {
            "messages": messages + [{"role": "user", "content": user_text}]
        }

        res = requests.post(
            f"{MCP_CLIENT_URL}/chat",  # 백엔드 엔드포인트
            json=payload,
            timeout=60
        )
        if res.status_code == 200:
            data = res.json()
            q.put(data.get("content", "빈 응답"))
        else:
            q.put(f"❌ 서버 오류: {res.status_code}")
    except Exception as e:
        q.put(f"❌ 예외 발생: {str(e)}")
    finally:
        # UI 스레드에서 상태 변경
        q.put("__THREAD_DONE__")

# -------------------------------------------------
# 메시지 렌더링 (Markdown 코드블록 완전 지원)
# -------------------------------------------------
def render_messages():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# -------------------------------------------------
# autorefresh: 1초마다 새로고침
# -------------------------------------------------
st_autorefresh(interval=1000, key="refresh_tick")

# -------------------------------------------------
# UI 렌더링
# -------------------------------------------------
st.title("🔵 OPA Policy Chat")
render_messages()

# 로딩 표시
if st.session_state.loading:
    with st.chat_message("assistant"):
        st.write("⌛ 처리 중...")

# -------------------------------------------------
# 사용자 입력 → 백엔드 요청 처리
# -------------------------------------------------
user_input = st.chat_input("메시지를 입력하세요")

if user_input and not st.session_state.loading:
    # 사용자 메시지 저장
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.loading = True

    # messages 복사본 전달
    messages_copy = st.session_state.messages.copy()

    # 비동기 백엔드 호출
    t = threading.Thread(
        target=call_backend_with_context,
        args=(user_input, messages_copy, st.session_state.response_queue),
        daemon=True
    )
    st.session_state.thread_running = True
    t.start()
    st.rerun()

# -------------------------------------------------
# 백엔드 응답 수신: Queue 확인
# -------------------------------------------------
try:
    while True:
        response = st.session_state.response_queue.get_nowait()
        if response == "__THREAD_DONE__":
            st.session_state.thread_running = False
        else:
            # assistant 메시지 추가
            st.session_state.messages.append(
                {"role": "assistant", "content": response}
            )
            st.session_state.loading = False
            st.rerun()
except queue.Empty:
    pass
