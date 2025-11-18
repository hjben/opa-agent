import streamlit as st
import requests
from markdown import markdown

# -------------------------------
# 초기 세션 상태 설정
# -------------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# -------------------------------
# 페이지 설정
# -------------------------------
st.set_page_config(
    page_title="OPA Chat",
    page_icon="🤖",
    layout="wide"
)

st.title("OPA Policy Agent Chat")

# -------------------------------
# 채팅 영역
# -------------------------------
chat_container = st.container()
with chat_container:
    for msg in st.session_state.chat_history:
        role = msg["role"]
        content = msg["content"]

        # 왼쪽/오른쪽 구분
        if role == "user":
            align = "right"
            bg_color = "#DCF8C6"
        else:
            align = "left"
            bg_color = "#F1F0F0"

        st.markdown(
            f"""
            <div style='
                background-color: {bg_color};
                padding: 10px 15px;
                border-radius: 10px;
                margin: 5px;
                text-align: {align};
                max-width: 80%;
                display: inline-block;
                word-wrap: break-word;
            '>{content}</div>
            """,
            unsafe_allow_html=True
        )

# -------------------------------
# 입력 영역
# -------------------------------
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_area("Your message", value="", key="input", height=80)
    submit_button = st.form_submit_button(label="Send")

if submit_button and user_input.strip():
    # 유저 메시지 추가
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # -------------------------------
    # MCP 서버 호출
    # -------------------------------
    try:
        response = requests.post(
            "http://localhost:8000/opa_request",
            json={"query": user_input},
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            content = data.get("content", "")
        else:
            content = f"Error: {response.status_code} - {response.text}"
    except Exception as e:
        content = f"Request failed: {str(e)}"

    # 봇 응답 추가
    st.session_state.chat_history.append({"role": "bot", "content": content})

    # 스크롤 맨 아래로 이동
    st.experimental_rerun()
