"""
KOBIS(영화진흥위원회) 일별 박스오피스 조회 앱
- Streamlit Cloud 배포용
- 인증키는 절대 코드에 적지 않고, Streamlit의 secrets(비밀 금고)에서 불러옵니다.
"""

import requests
import pandas as pd
import streamlit as st
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
# 5. 화면 구성
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

    # --- 5-2. 관객수 상위 5편 막대그래프 ---
    st.subheader("📊 관객수 상위 5편")
    top5 = df.sort_values("audiCnt", ascending=False).head(5)
    chart_data = top5.set_index("movieNm")[["audiCnt"]]
    chart_data.columns = ["관객수"]
    st.bar_chart(chart_data)

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


if __name__ == "__main__":
    main()
