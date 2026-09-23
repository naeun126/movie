import streamlit as st
from openai import OpenAI

# 페이지 기본 설정 (웹브라우저 탭 제목 및 아이콘)
st.set_page_config(
    page_title="정보 선생님 AI 채팅",
    page_icon="💬"
)

st.title("💬 친절한 정보 선생님과의 대화")
st.write("궁금한 점이 있다면 무엇이든 물어보세요!")

# -------------------------------------------------------------------
# 1. API 키 확인 및 OpenAI 클라이언트 초기화
# -------------------------------------------------------------------
# .streamlit/secrets.toml 파일의 GEMINI_API_KEY 존재 여부를 확인합니다.
if "GEMINI_API_KEY" not in st.secrets or not st.secrets["GEMINI_API_KEY"]:
    st.warning("비밀 금고(secrets.toml)에 GEMINI_API_KEY를 설정해 주세요.")
    st.stop()

# OpenAI 라이브러리를 사용해 Gemini API 호환 서버에 연결합니다.
client = OpenAI(
    api_key=st.secrets["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# 사용하려는 모델 이름을 지정합니다.
MODEL_NAME = "gemini-3.5-flash-lite"

# -------------------------------------------------------------------
# 2. 대화 기록(Session State) 초기화 및 프롬프트 설정
# -------------------------------------------------------------------
# AI에게 부여할 역할/성격 규칙 (화면에는 출력하지 않습니다)
SYSTEM_PROMPT = {
    "role": "system",
    "content": "너는 중고등학생에게 설명하는 친절한 정보 선생님이야. 어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해."
}

# st.session_state에 messages 항목이 없으면 새로 만들어 대화 기록을 저장합니다.
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# -------------------------------------------------------------------
# 3. 기존 대화 내용 화면에 출력
# -------------------------------------------------------------------
# 사용자가 이전에 주고받은 메시지들을 말풍선 형태로 화면에 다시 그려줍니다.
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# -------------------------------------------------------------------
# 4. 사용자 입력 처리 및 AI 응답 실시간 출력 (스트리밍)
# -------------------------------------------------------------------
# 채팅 입력창을 제공하고, 사용자가 메시지를 입력하면 아래 코드가 실행됩니다.
if prompt := st.chat_input("질문을 입력하세요..."):
    # 4-1. 사용자가 입력한 메시지를 화면에 말풍선으로 표시
    with st.chat_message("user"):
        st.write(prompt)
    
    # 4-2. 사용자 메시지를 대화 기록에 저장
    st.session_state["messages"].append({"role": "user", "content": prompt})

    # 4-3. AI 응답 처리
    with st.chat_message("assistant"):
        try:
            # system 메시지 + 그동안 acumul된 사용자/AI 대화 기록 전체를 API 전달용으로 구성합니다.
            api_messages = [SYSTEM_PROMPT] + st.session_state["messages"]

            # API 호출 (stream=True를 사용해 실시간으로 글자를 받아옵니다)
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=api_messages,
                stream=True
            )

            # st.write_stream을 사용하여 글자가 흘러나오듯 화면에 실시간 표시합니다.
            full_response = st.write_stream(response)
            
            # 완성된 AI의 응답을 대화 기록에 저장합니다.
            st.session_state["messages"].append({"role": "assistant", "content": full_response})

        except Exception:
            # API 연결 실패 등 오류가 발생하였을 때 친절한 안내 문구를 출력합니다.
            st.error("죄송합니다. 선생님과의 연결에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.")
