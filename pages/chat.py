import streamlit as st
from openai import OpenAI

# 페이지 기본 설정 (웹브라우저 탭 제목 및 아이콘)
st.set_page_config(
    page_title="스파이더맨 AI 채팅",
    page_icon="🕷️"
)

st.title("🕷️ 친절한 이웃 스파이더맨과의 대화")
st.write("안녕! 나는 뉴욕의 친절한 이웃 스파이더맨 피터 파커야! 궁금한 게 있다면 뭐든지 물어봐!")

# -------------------------------------------------------------------
# 1. API 키 확인 및 OpenAI 클라이언트 초기화
# -------------------------------------------------------------------
# Streamlit의 비밀 금고(secrets.toml)에 GEMINI_API_KEY가 있는지 확인합니다.
if "GEMINI_API_KEY" not in st.secrets or not st.secrets["GEMINI_API_KEY"]:
    st.warning("비밀 금고(secrets.toml)에 GEMINI_API_KEY를 설정해 주세요.")
    st.stop()

# openai 라이브러리를 사용해 Gemini API 호환 주소로 연결을 설정합니다.
client = OpenAI(
    api_key=st.secrets["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# 지정해주신 모델 이름을 정확히 사용합니다.
MODEL_NAME = "gemini-3.5-flash-lite"

# -------------------------------------------------------------------
# 2. 대화 기록(Session State) 초기화 및 시스템 성격(프롬프트) 설정
# -------------------------------------------------------------------
# AI에게 부여할 역할/성격 설정 (화면에는 출력하지 않고 API 호출 시에만 사용합니다)
SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "너는 스파이더맨 피터파커야. "
        "어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해."
    )
}

# st.session_state를 이용해 사용자와 AI가 주고받은 대화 내역을 저장합니다.
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# -------------------------------------------------------------------
# 3. 기존 대화 기록 화면에 표시
# -------------------------------------------------------------------
# 새로고침이나 메시지 송신 시 기존 대화 내역이 사라지지 않도록 말풍선으로 다시 보여줍니다.
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# -------------------------------------------------------------------
# 4. 사용자 입력 처리 및 AI 실시간 응답(스트리밍)
# -------------------------------------------------------------------
# 화면 하단에 채팅 입력창을 만듭니다.
if prompt := st.chat_input("피터에게 할 말을 입력하세요..."):
    # 4-1. 사용자가 작성한 메시지를 사용자 말풍선으로 화면에 출력
    with st.chat_message("user"):
        st.write(prompt)
    
    # 4-2. 사용자 메시지를 대화 기록 리스트에 추가
    st.session_state["messages"].append({"role": "user", "content": prompt})

    # 4-3. AI 응답 출력
    with st.chat_message("assistant"):
        try:
            # 시스템 성격 지시문과 지금까지 저장된 대화 기록을 하나로 합쳐서 API에 넘깁니다.
            api_messages = [SYSTEM_PROMPT] + st.session_state["messages"]

            # Gemini API 호출 (stream=True 옵션으로 실시간 글자 출력 설정)
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=api_messages,
                stream=True
            )

            # st.write_stream을 사용하여 AI의 답을 실시간 타자 치듯 화면에 출력합니다.
            full_response = st.write_stream(response)
            
            # 생성된 최종 AI 응답을 대화 기록에 저장해 다음 대화에서도 기억하게 합니다.
            st.session_state["messages"].append({"role": "assistant", "content": full_response})

        except Exception:
            # 예외나 오류 발생 시 빨간색 에러 창 대신 지정된 한국어 안내 문구만 보여줍니다.
            st.error("아차, 웹 슈터에 문제가 생겼나 봐! 연결이 잠시 끊겼으니 다시 시도해 줘.")
