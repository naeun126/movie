import streamlit as st
from openai import OpenAI

# 페이지 기본 설정 (브라우저 탭 제목 및 아이콘)
st.set_page_config(
    page_title="배우 톰 홀랜드 AI 채팅",
    page_icon="🎬"
)

st.title("🎬 배우 톰 홀랜드와의 대화")
st.write("안녕하세요! 배우 톰 홀랜드입니다. 영화 촬영이나 일상에 대해 편하게 이야기 나눠요!")

# -------------------------------------------------------------------
# 1. API 키 확인 및 OpenAI 클라이언트 초기화
# -------------------------------------------------------------------
# Streamlit 비밀 금고(secrets.toml)에 GEMINI_API_KEY가 있는지 확인합니다.
if "GEMINI_API_KEY" not in st.secrets or not st.secrets["GEMINI_API_KEY"]:
    st.warning("비밀 금고(secrets.toml)에 GEMINI_API_KEY를 설정해 주세요.")
    st.stop()

# openai 라이브러리를 사용해 Gemini API 호환 서버 주소로 연결을 설정합니다.
client = OpenAI(
    api_key=st.secrets["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# 요구사항에 명시된 모델 이름을 그대로 사용합니다.
MODEL_NAME = "gemini-3.5-flash-lite"

# -------------------------------------------------------------------
# 2. 대화 기록(Session State) 및 배우 톰 홀랜드 페르소나(시스템 프롬프트) 설정
# -------------------------------------------------------------------
# AI에게 부여할 역할 및 성격 (화면에는 표시하지 않고 API에만 전달합니다)
# 인터뷰에서 보여주는 유쾌함, 스포일러 실수에 대한 너스레, 친근하고 솔직한 입담 반영
SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "너는 배우 톰홀랜드야. "
        "어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해. "
        "인터뷰나 예능에서 보여준 것처럼 항상 밝고 에너지 넘치며, 솔직하고 친근하게 이야기해 줘. "
        "가끔 촬영장 비하인드 이야기나 실수로 스포일러를 말할 뻔했던 경험을 위트 있게 언급해도 좋아."
    )
}

# st.session_state를 사용해 대화 내역을 저장하는 리스트를 만듭니다.
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# -------------------------------------------------------------------
# 3. 이전 대화 기록 화면에 표시
# -------------------------------------------------------------------
# 사용자와 AI가 주고받았던 이전 메시지들을 말풍선 형태로 화면에 다시 그려줍니다.
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# -------------------------------------------------------------------
# 4. 사용자 입력 처리 및 실시간 응답(스트리밍) 출력
# -------------------------------------------------------------------
# 채팅 입력창을 만들고, 메시지가 입력되면 코드가 실행됩니다.
if prompt := st.chat_input("톰 홀랜드에게 궁금한 점을 물어보세요..."):
    # 4-1. 사용자가 입력한 메시지를 사용자 말풍선으로 출력
    with st.chat_message("user"):
        st.write(prompt)
    
    # 4-2. 사용자 메시지를 대화 기록 리스트에 추가
    st.session_state["messages"].append({"role": "user", "content": prompt})

    # 4-3. AI 응답 생성 및 실시간 스트리밍 출력
    with st.chat_message("assistant"):
        try:
            # 시스템 역할(페르소나) 지시문과 지금까지의 대화 기록을 합쳐서 API에 전달합니다.
            api_messages = [SYSTEM_PROMPT] + st.session_state["messages"]

            # Gemini API 호출 (stream=True로 설정하여 글자가 실시간으로 나오게 합니다)
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=api_messages,
                stream=True
            )

            # st.write_stream을 사용하여 답변이 한 글자씩 실시간으로 화면에 출력되게 합니다.
            full_response = st.write_stream(response)
            
            # completed AI 답변을 대화 기록에 저장하여 이전 문맥을 계속 기억하도록 합니다.
            st.session_state["messages"].append({"role": "assistant", "content": full_response})

        except Exception:
            # 오류가 발생했을 때 빨간 에러 화면 대신 깔끔한 한국어 안내문 한 줄만 표시합니다.
            st.error("죄송해요, 통신 연결에 문제가 생겨서 답변을 불러오지 못했어요. 잠시 후 다시 시도해 주세요!")
