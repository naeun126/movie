"""
KOBIS(영화진흥위원회) 일별 박스오피스 조회 앱
- Streamlit Cloud 배포용
- 인증키는 절대 코드에 적지 않고, Streamlit의 secrets(비밀 금고)에서 불러옵니다.
"""

import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# -----------------------------
# 1. 기본 설정
# -----------------------------
st.set_page_config(page_title="어제의 박스오피스", page_icon="🎬", layout="wide")

KOBIS_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

# 표에 보여줄 컬럼 이름을 한국어로 바꾸기 위한 매핑표
COLUMN_NAME_MAP = {
    "rank": "순위",
    "movieNm": "영화명",
    "openDt": "개봉일",
    "audiCnt": "관객수",
    "audiAcc": "누적관객",
    "scrnCnt": "스크린수",
}


# -----------------------------
# 2. '어제' 날짜 계산 (한국 시간 기준)
# -----------------------------
def get_yesterday_kst() -> str:
    """
    배포 서버의 시계가 한국 시간이 아닐 수 있으므로,
    항상 'Asia/Seoul' 시간대를 기준으로 오늘 날짜를 구한 뒤 하루를 뺍니다.
    반환값은 API가 요구하는 yyyymmdd 형식(8자리 문자열)입니다.
    """
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    yesterday_kst = now_kst - timedelta(days=1)
    return yesterday_kst.strftime("%Y%m%d")


# -----------------------------
# 3. KOBIS API 호출 및 오류 처리
# -----------------------------
def fetch_box_office(target_dt: str):
    """
    KOBIS API를 호출해서 박스오피스 목록(list[dict])을 반환합니다.
    문제가 생기면 (None, "사용자에게 보여줄 안내 문구") 형태로 반환합니다.
    """
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return None, (
            "🔑 인증키를 찾을 수 없습니다.\n\n"
            "Streamlit Cloud의 [Settings] → [Secrets]에 아래처럼 등록했는지 확인해 주세요.\n\n"
            '```\nKOBIS_KEY = "발급받은_인증키"\n```'
        )

    params = {"key": api_key, "targetDt": target_dt}

    # 3-1. 네트워크 요청 자체가 실패하는 경우 (타임아웃, 연결 끊김 등)
    try:
        response = requests.get(KOBIS_URL, params=params, timeout=10)
    except requests.exceptions.RequestException:
        return None, (
            "🌐 KOBIS 서버에 연결하지 못했습니다.\n\n"
            "인터넷 연결 상태나 KOBIS 서버 점검 여부를 확인해 주세요."
        )

    # 3-2. HTTP 상태코드가 200이 아닌 경우 (서버 오류 등)
    if response.status_code != 200:
        return None, (
            f"⚠️ 서버가 비정상 응답(상태코드 {response.status_code})을 반환했습니다.\n\n"
            "잠시 후 다시 시도해 주세요."
        )

    # 3-3. 응답이 JSON 형식이 아닌 경우 (HTML 오류 페이지 등이 올 수도 있음)
    try:
        data = response.json()
    except ValueError:
        return None, (
            "📄 서버 응답을 해석할 수 없습니다 (JSON 형식이 아님).\n\n"
            "요청 주소나 파라미터가 올바른지 다시 확인해 주세요."
        )

    # 3-4. 인증키가 틀렸을 때 오는 faultInfo 상자 확인
    if "faultInfo" in data:
        message = data["faultInfo"].get("message", "알 수 없는 오류")
        return None, (
            f"🔑 인증키 오류로 데이터를 가져오지 못했습니다. (메시지: {message})\n\n"
            "Streamlit Secrets에 등록한 KOBIS_KEY 값이 정확한지 확인해 주세요."
        )

    # 3-5. 정상 응답 구조인지 확인
    box_office_result = data.get("boxOfficeResult")
    if box_office_result is None:
        return None, (
            "❓ 예상하지 못한 응답 형식입니다 (boxOfficeResult 없음).\n\n"
            "targetDt 값이나 API 요청 방식이 KOBIS 문서와 일치하는지 확인해 주세요."
        )

    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    # 3-6. 영화 목록이 비어 있는 경우 (예: 아직 집계 전이거나 해당일 데이터 없음)
    if not movie_list:
        return None, (
            "📭 해당 날짜의 박스오피스 데이터가 비어 있습니다.\n\n"
            "조회 날짜가 너무 이르거나(집계 전), KOBIS 측 데이터 갱신이 늦어졌을 수 있습니다.\n"
            "잠시 후 새로고침해서 다시 시도해 주세요."
        )

    return movie_list, None


# -----------------------------
# 4. 데이터 가공 (문자열 숫자 -> 정수 변환)
# -----------------------------
def build_dataframe(movie_list: list) -> pd.DataFrame:
    """
    API가 내려주는 값은 전부 문자열이므로, 표시/계산에 쓸 숫자 컬럼은
    정수(int)로 바꿔 새로운 데이터프레임을 만듭니다.
    """
    df = pd.DataFrame(movie_list)

    numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
    for col in numeric_columns:
        # errors="coerce" : 변환 실패 시 NaN 처리 후 0으로 채워서 앱이 죽지 않게 함
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    return df


# -----------------------------
# 5. 영화 포스터 조회 (TMDB, 선택 사항)
# -----------------------------
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def fetch_poster_url(movie_title: str, tmdb_key: str):
    """
    TMDB(The Movie Database)에서 영화 제목으로 포스터 이미지 주소를 찾습니다.
    KOBIS API에는 포스터가 없기 때문에 별도로 조회하는 부분입니다.
    실패하거나 포스터가 없으면 None을 돌려주며, 이때 화면에서는 포스터를 생략합니다.
    """
    try:
        response = requests.get(
            TMDB_SEARCH_URL,
            params={"api_key": tmdb_key, "query": movie_title, "language": "ko-KR"},
            timeout=5,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return None
        poster_path = results[0].get("poster_path")
        if not poster_path:
            return None
        return f"https://image.tmdb.org/t/p/w200{poster_path}"
    except Exception:
        # 네트워크 오류, 키 오류 등 어떤 문제가 생기든 앱이 멈추지 않도록 None 처리
        return None


# -----------------------------
# 6. MBTI별 영화 추천 목록 (오늘의 박스오피스와는 무관한 고정 데이터)
# -----------------------------
MBTI_RECOMMENDATIONS = {
    "INTJ": [
        ("인터스텔라", "장기적인 계획과 큰 그림을 좋아하는 INTJ에게 잘 맞는 SF 대작이다."),
        ("셔터 아일랜드", "숨겨진 구조를 스스로 추리해 나가는 재미가 있는 미스터리다."),
        ("her", "논리적 사고와 인간관계에 대한 통찰이 함께 담긴 작품이다."),
    ],
    "INTP": [
        ("인셉션", "복잡한 규칙과 아이디어를 분석하는 재미가 있는 영화다."),
        ("이미테이션 게임", "논리와 암호 해독 과정을 좋아하는 INTP 취향의 실화다."),
        ("컨택트", "언어와 사고의 구조를 탐구하는 지적인 SF다."),
    ],
    "ENTJ": [
        ("설리: 허드슨강의 기적", "위기 속 냉철한 판단력을 보여주는 실화 기반 영화다."),
        ("포드 V 페라리", "목표 달성을 위한 전략과 리더십이 돋보이는 작품이다."),
        ("빅쇼트", "복잡한 상황을 꿰뚫어보는 통찰력을 다룬 영화다."),
    ],
    "ENTP": [
        ("나잇 크롤러", "기발한 아이디어와 논쟁적인 캐릭터가 흥미로운 작품이다."),
        ("빅 히어로", "창의적인 발상과 유쾌한 에너지가 돋보이는 애니메이션이다."),
        ("소셜 네트워크", "빠른 사고와 언쟁을 즐기는 ENTP에게 잘 맞는다."),
    ],
    "INFJ": [
        ("그린 북", "사람과 사람 사이의 이해를 깊이 있게 그린 작품이다."),
        ("이터널 선샤인", "기억과 감정을 섬세하게 다루는 영화다."),
        ("클라우드 아틀라스", "인생의 의미를 여러 시대에 걸쳐 탐구하는 대작이다."),
    ],
    "INFP": [
        ("리틀 포레스트", "잔잔한 일상 속에서 자기 자신을 돌아보게 하는 영화다."),
        ("월플라워", "섬세한 감정선을 지닌 청춘 성장담이다."),
        ("her", "고독과 사랑에 대한 내밀한 감정을 다룬 작품이다."),
    ],
    "ENFJ": [
        ("죽은 시인의 사회", "타인을 이끌고 영감을 주는 인물이 인상적인 영화다."),
        ("원더", "공감과 배려의 힘을 보여주는 따뜻한 작품이다."),
        ("헬프", "사람들을 연결하고 변화를 이끄는 이야기다."),
    ],
    "ENFP": [
        ("라라랜드", "꿈과 열정을 좇는 에너지가 가득한 뮤지컬 영화다."),
        ("월터의 상상은 현실이 된다", "즉흥적인 모험을 좋아하는 ENFP에게 잘 맞는다."),
        ("스쿨 오브 락", "자유분방한 에너지와 즉흥성이 돋보이는 코미디다."),
    ],
    "ISTJ": [
        ("킹스맨: 시크릿 에이전트", "원칙과 규율을 지키는 캐릭터가 매력적인 작품이다."),
        ("포드 V 페라리", "꼼꼼한 준비와 책임감이 돋보이는 실화 영화다."),
        ("아폴로 13", "체계적인 문제 해결 과정을 그린 실화다."),
    ],
    "ISFJ": [
        ("코코", "가족과 전통을 소중히 여기는 마음이 담긴 애니메이션이다."),
        ("마이 시스터즈 키퍼", "가족을 향한 헌신을 그린 감동적인 작품이다."),
        ("어바웃 타임", "일상의 소중함을 따뜻하게 전하는 영화다."),
    ],
    "ESTJ": [
        ("머니볼", "체계적인 관리와 성과 중심 사고가 돋보이는 실화다."),
        ("인빅터스", "명확한 목표와 리더십을 그린 작품이다."),
        ("설리: 허드슨강의 기적", "위기 상황에서의 침착한 대응을 다룬 영화다."),
    ],
    "ESFJ": [
        ("어바웃 타임", "가족과 주변 사람들을 따뜻하게 챙기는 이야기다."),
        ("맘마미아", "사람들과 함께 즐기는 흥겨운 뮤지컬이다."),
        ("리틀 미스 선샤인", "가족의 유대를 유쾌하게 그린 작품이다."),
    ],
    "ISTP": [
        ("매드맥스: 분노의 도로", "실전 감각과 즉각적인 대응이 돋보이는 액션이다."),
        ("본 아이덴티티", "냉철하고 독립적인 캐릭터가 매력적인 스릴러다."),
        ("듄", "낯선 환경에 적응해 나가는 실용적인 캐릭터가 인상적이다."),
    ],
    "ISFP": [
        ("리틀 포레스트", "자연 속에서 자신만의 속도를 찾아가는 영화다."),
        ("건축학개론", "섬세한 감성과 추억을 그린 멜로 영화다."),
        ("콜 미 바이 유어 네임", "감각적이고 섬세한 감정 표현이 돋보이는 작품이다."),
    ],
    "ESTP": [
        ("매드맥스: 분노의 도로", "즉흥적이고 스릴 넘치는 전개를 좋아하는 ESTP에게 맞는다."),
        ("분노의 질주", "속도감 있는 액션과 팀워크가 돋보이는 작품이다."),
        ("탑건: 매버릭", "과감한 도전과 실전 감각이 돋보이는 영화다."),
    ],
    "ESFP": [
        ("맘마미아", "흥과 에너지가 넘치는 뮤지컬로 ESFP에게 잘 맞는다."),
        ("보헤미안 랩소디", "무대 위 화려한 에너지를 느낄 수 있는 작품이다."),
        ("라라랜드", "열정적이고 낭만적인 분위기를 좋아하는 성향에 어울린다."),
    ],
}


# -----------------------------
# 7. 화면 구성
# -----------------------------
def main():
    st.title("🎬 어제의 박스오피스")

    target_dt = get_yesterday_kst()
    display_date = f"{target_dt[:4]}.{target_dt[4:6]}.{target_dt[6:]}"
    st.caption(f"기준일(한국시간 어제): {display_date} · 자료: 영화진흥위원회(KOBIS)")

    movie_list, error_message = fetch_box_office(target_dt)

    # 오류가 있으면 안내 문구만 보여주고 함수 종료 (빈 화면 방지)
    if error_message is not None:
        st.error(error_message)
        return

    df = build_dataframe(movie_list)

    # --- 5-1. 1위 영화 지표 카드 3장 ---
    top_movie = df.iloc[0]
    st.subheader(f"🥇 오늘의 1위: {top_movie['movieNm']}")

    card1, card2, card3 = st.columns(3)
    card1.metric("어제 관객수", f"{top_movie['audiCnt']:,}명")
    card2.metric("누적 관객수", f"{top_movie['audiAcc']:,}명")
    card3.metric("스크린수", f"{top_movie['scrnCnt']:,}개")

    st.divider()

    # --- 5-2. 관객수 상위 5편 막대그래프 (포스터 이미지 포함) ---
    st.subheader("📊 관객수 상위 5편")
    top5 = df.sort_values("audiCnt", ascending=False).head(5).reset_index(drop=True)
    max_count = int(top5["audiCnt"].max())

    # TMDB_KEY가 없어도 앱은 정상 작동하도록 선택 사항으로 처리
    tmdb_key = st.secrets.get("TMDB_KEY", None)

    fig = go.Figure(
        data=[
            go.Bar(
                x=list(range(len(top5))),
                y=top5["audiCnt"],
                marker_color="#4C78A8",
                text=[f"{v:,}명" for v in top5["audiCnt"]],
                textposition="outside",
            )
        ]
    )

    if tmdb_key:
        # 각 막대 위에 포스터 이미지를 작은 그림(도트)처럼 얹는다.
        for i, row in top5.iterrows():
            poster_url = fetch_poster_url(row["movieNm"], tmdb_key)
            if poster_url:
                fig.add_layout_image(
                    dict(
                        source=poster_url,
                        xref="x",
                        yref="y",
                        x=i,
                        y=row["audiCnt"] + max_count * 0.20,
                        sizex=0.8,
                        sizey=max_count * 0.35,
                        xanchor="center",
                        yanchor="middle",
                        layer="above",
                    )
                )
    else:
        st.info(
            "🖼️ 막대 위에 포스터를 표시하려면 Streamlit Secrets에 TMDB_KEY를 등록해 주세요.\n\n"
            "TMDB(https://www.themoviedb.org)에서 무료로 발급받을 수 있으며, "
            "등록하지 않아도 막대그래프는 정상적으로 표시됩니다."
        )

    fig.update_layout(
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(len(top5))),
            ticktext=top5["movieNm"],
        ),
        yaxis_title="관객수(명)",
        yaxis_range=[0, max_count * 1.6],
        height=520,
        margin=dict(t=100, b=40),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- 5-3. 전체 박스오피스 표 ---
    st.subheader("📋 전체 박스오피스 순위")
    table_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].rename(
        columns=COLUMN_NAME_MAP
    )
    # 숫자 컬럼에 천 단위 구분 쉼표를 붙여서 보기 좋게 표시
    st.dataframe(
        table_df,
        column_config={
            "관객수": st.column_config.NumberColumn(format="%d"),
            "누적관객": st.column_config.NumberColumn(format="%d"),
            "스크린수": st.column_config.NumberColumn(format="%d"),
        },
        hide_index=True,
        use_container_width=True,
    )

    st.divider()

    # --- 5-4. MBTI별 영화 추천 (오늘의 박스오피스와는 별개의 고정 추천 목록) ---
    st.subheader("🧭 MBTI로 영화 추천받기")
    st.caption("오늘의 박스오피스와는 무관하게, 성향별로 어울리는 영화를 추천해 드립니다.")

    mbti_types = list(MBTI_RECOMMENDATIONS.keys())
    selected_mbti = st.selectbox("당신의 MBTI를 선택하세요", mbti_types)

    recommend_cols = st.columns(3)
    for col, (movie_title, reason) in zip(recommend_cols, MBTI_RECOMMENDATIONS[selected_mbti]):
        with col:
            st.markdown(f"**🎬 {movie_title}**")
            st.caption(reason)


if __name__ == "__main__":
    main()
