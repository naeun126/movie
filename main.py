"""
KOBIS(영화진흥위원회) 오픈API를 활용한 영화 대시보드
- Streamlit Cloud 배포용
- 인증키는 절대 코드에 적지 않고, Streamlit의 secrets(비밀 금고)에서 불러옵니다.

구성:
1) 어제의 일별 박스오피스 (searchDailyBoxOfficeList.json)
2) MBTI 맞춤 최신 영화 추천 (searchMovieList.json)
3) 장르별 영화 검색 - 다중 장르 AND 조건 (searchMovieList.json)

※ 2)·3)에서 쓰는 '영화목록 조회(searchMovieList.json)'는 사용자가 준 박스오피스 문서에는
   없지만, 같은 KOBIS 오픈API 서비스의 공식 엔드포인트입니다. 응답 구조가 문서와 다르면
   KOBIS 개발자센터(https://www.kobis.or.kr/kobisopenapi)의 최신 문서를 함께 확인해 주세요.
"""

import requests
import calendar
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# =========================================================
# 1. 기본 설정
# =========================================================
st.set_page_config(page_title="무비 인사이트", page_icon="🎬", layout="wide")

DAILY_BOX_OFFICE_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
)
MOVIE_LIST_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/searchMovieList.json"

COLUMN_NAME_MAP = {
    "rank": "순위",
    "movieNm": "영화명",
    "openDt": "개봉일",
    "audiCnt": "관객수",
    "audiAcc": "누적관객",
    "scrnCnt": "스크린수",
}

# 장르 검색 탭에서 고를 수 있는 장르 목록 (KOBIS에서 쓰는 장르 표기 기준)
GENRE_OPTIONS = [
    "액션", "SF", "가족", "공연", "공포(호러)", "다큐멘터리", "드라마",
    "멜로/로맨스", "뮤지컬", "미스터리", "범죄", "사극", "서부극(웨스턴)",
    "스릴러", "애니메이션", "어드벤처", "전쟁", "코미디", "판타지",
]

# MBTI 유형별로 잘 어울릴 만한 장르 조합 (추천 로직에 사용)
MBTI_GENRE_MAP = {
    "INTJ": ["SF", "미스터리"],
    "INTP": ["SF", "다큐멘터리"],
    "ENTJ": ["범죄", "드라마"],
    "ENTP": ["코미디", "액션"],
    "INFJ": ["드라마", "판타지"],
    "INFP": ["멜로/로맨스", "드라마"],
    "ENFJ": ["드라마", "가족"],
    "ENFP": ["코미디", "뮤지컬"],
    "ISTJ": ["다큐멘터리", "드라마"],
    "ISFJ": ["가족", "멜로/로맨스"],
    "ESTJ": ["액션", "범죄"],
    "ESFJ": ["코미디", "가족"],
    "ISTP": ["액션", "스릴러"],
    "ISFP": ["멜로/로맨스", "판타지"],
    "ESTP": ["액션", "어드벤처"],
    "ESFP": ["뮤지컬", "코미디"],
}


def inject_custom_css():
    """전체적인 화면 톤을 다듬는 CSS를 주입합니다."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');

        html, body, [class*="css"]  {
            font-family: 'Noto Sans KR', sans-serif;
        }

        .main-title {
            font-size: 2.3rem;
            font-weight: 900;
            background: linear-gradient(90deg, #4C6FFF, #9B5CFF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.2rem;
        }
        .sub-caption {
            color: #8a8a8a;
            font-size: 0.95rem;
            margin-bottom: 1.6rem;
        }
        .section-title {
            font-size: 1.25rem;
            font-weight: 700;
            margin: 0.4rem 0 0.6rem 0;
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(135deg, #f4f6ff, #eef1ff);
            border-radius: 16px;
            padding: 1rem 1.1rem;
            box-shadow: 0 2px 10px rgba(76, 111, 255, 0.10);
        }
        .genre-tag {
            display: inline-block;
            background: #eef1ff;
            color: #4C6FFF;
            border-radius: 999px;
            padding: 2px 10px;
            font-size: 0.78rem;
            margin-right: 4px;
            margin-bottom: 4px;
            font-weight: 500;
        }
        .movie-card {
            background: #ffffff;
            border: 1px solid #eee;
            border-radius: 14px;
            padding: 14px 16px;
            margin-bottom: 12px;
            box-shadow: 0 1px 8px rgba(0,0,0,0.05);
        }
        .movie-card .movie-title {
            font-weight: 700;
            font-size: 1.02rem;
            margin-bottom: 4px;
        }
        .movie-card .movie-date {
            color: #999;
            font-size: 0.82rem;
            margin-bottom: 6px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# 2. 공통 유틸 - '어제' 날짜, 인증키
# =========================================================
def get_yesterday_kst() -> str:
    """
    배포 서버 시계가 한국 시간이 아닐 수 있으므로, 항상 'Asia/Seoul' 기준으로
    오늘 날짜를 구한 뒤 하루를 뺍니다. 반환값은 yyyymmdd 형식(8자리 문자열)입니다.
    """
    now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    yesterday_kst = now_kst - timedelta(days=1)
    return yesterday_kst.strftime("%Y%m%d")


def get_kobis_key():
    """secrets에서 인증키를 꺼내옵니다. 없으면 (None, 안내문구)를 반환합니다."""
    try:
        return st.secrets["KOBIS_KEY"], None
    except Exception:
        return None, (
            "🔑 인증키를 찾을 수 없습니다.\n\n"
            "Streamlit Cloud의 [Settings] → [Secrets]에 아래처럼 등록했는지 확인해 주세요.\n\n"
            '```\nKOBIS_KEY = "발급받은_인증키"\n```'
        )


# =========================================================
# 3. 일별 박스오피스 조회
# =========================================================
@st.cache_data(show_spinner=False, ttl=60 * 30)
def fetch_box_office(api_key: str, target_dt: str):
    """
    KOBIS 일별 박스오피스 API를 호출합니다.
    성공하면 (영화 목록, None), 문제가 있으면 (None, "안내 문구")를 반환합니다.
    """
    params = {"key": api_key, "targetDt": target_dt}

    try:
        response = requests.get(DAILY_BOX_OFFICE_URL, params=params, timeout=10)
    except requests.exceptions.RequestException:
        return None, "🌐 KOBIS 서버에 연결하지 못했습니다.\n\n인터넷 연결 상태나 KOBIS 서버 점검 여부를 확인해 주세요."

    if response.status_code != 200:
        return None, f"⚠️ 서버가 비정상 응답(상태코드 {response.status_code})을 반환했습니다.\n\n잠시 후 다시 시도해 주세요."

    try:
        data = response.json()
    except ValueError:
        return None, "📄 서버 응답을 해석할 수 없습니다 (JSON 형식이 아님).\n\n요청 주소나 파라미터가 올바른지 다시 확인해 주세요."

    if "faultInfo" in data:
        message = data["faultInfo"].get("message", "알 수 없는 오류")
        return None, (
            f"🔑 인증키 오류로 데이터를 가져오지 못했습니다. (메시지: {message})\n\n"
            "Streamlit Secrets에 등록한 KOBIS_KEY 값이 정확한지 확인해 주세요."
        )

    box_office_result = data.get("boxOfficeResult")
    if box_office_result is None:
        return None, "❓ 예상하지 못한 응답 형식입니다 (boxOfficeResult 없음).\n\ntargetDt 값이나 요청 방식이 KOBIS 문서와 일치하는지 확인해 주세요."

    movie_list = box_office_result.get("dailyBoxOfficeList", [])
    if not movie_list:
        return None, (
            "📭 해당 날짜의 박스오피스 데이터가 비어 있습니다.\n\n"
            "조회 날짜가 너무 이르거나(집계 전), KOBIS 측 데이터 갱신이 늦어졌을 수 있습니다.\n"
            "잠시 후 새로고침해서 다시 시도해 주세요."
        )

    return movie_list, None


def build_dataframe(movie_list: list) -> pd.DataFrame:
    """문자열로 오는 숫자 컬럼을 정수(int)로 바꿔 데이터프레임을 만듭니다."""
    df = pd.DataFrame(movie_list)
    numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df


@st.cache_data(show_spinner="연간 누적 박스오피스를 집계하는 중입니다...", ttl=60 * 60 * 12)
def fetch_yearly_cumulative_top(api_key: str, year: int, yesterday_dt: str, top_n: int = 10):
    """
    그 해(year)에 개봉한 영화들의 '누적 관객수' 순위를 근사치로 계산합니다.

    ※ KOBIS 오픈API에는 연간 박스오피스 전용 엔드포인트가 없어서, 이미 검증된
      일별 박스오피스 API(searchDailyBoxOfficeList.json)의 TOP10 스냅샷을
      매달 말일 + 어제 날짜 기준으로 모아서 계산합니다.
      일별 박스오피스의 audiAcc는 '그 영화가 개봉한 뒤 해당 날짜까지의 누적 관객수'이므로,
      개봉일이 그 해(year)인 영화라면 스냅샷에서 본 가장 큰 audiAcc 값이 곧 그 해의
      누적 관객수와 사실상 같습니다.
      다만 TOP10 밖으로 완전히 밀려난 뒤 다시 등장하지 않은 영화는 값이 실제보다
      낮게 잡힐 수 있는 근사치라는 점을 참고해 주세요.
    """
    yesterday = datetime.strptime(yesterday_dt, "%Y%m%d")

    # 이미 끝난 달은 말일, 이번 달은 어제 날짜로 스냅샷을 잡습니다.
    snapshot_dates = []
    for month in range(1, yesterday.month):
        last_day = calendar.monthrange(year, month)[1]
        snapshot_dates.append(f"{year}{month:02d}{last_day:02d}")
    snapshot_dates.append(yesterday_dt)

    best_by_movie = {}

    for target_dt in snapshot_dates:
        movie_list, error_message = fetch_box_office(api_key, target_dt)
        if error_message is not None:
            continue  # 스냅샷 하나가 실패해도 전체 집계는 계속 진행합니다.

        for movie in movie_list:
            open_dt = movie.get("openDt", "")
            if not (len(open_dt) == 8 and open_dt.startswith(str(year))):
                continue

            movie_key = movie.get("movieCd") or movie.get("movieNm", "")
            audi_acc = pd.to_numeric(movie.get("audiAcc", "0"), errors="coerce")
            audi_acc = 0 if pd.isna(audi_acc) else int(audi_acc)

            if movie_key not in best_by_movie or audi_acc > best_by_movie[movie_key]["audiAcc"]:
                best_by_movie[movie_key] = {
                    "movieNm": movie.get("movieNm", ""),
                    "openDt": open_dt,
                    "audiAcc": audi_acc,
                }

    if not best_by_movie:
        return [], f"📭 {year}년 개봉작의 누적 박스오피스 데이터를 찾지 못했습니다.\n\n잠시 후 다시 시도해 주세요."

    ranked = sorted(best_by_movie.values(), key=lambda m: m["audiAcc"], reverse=True)
    return ranked[:top_n], None


# =========================================================
# 4. 영화 목록 조회 (MBTI 추천 · 장르 검색에서 공용으로 사용)
# =========================================================
@st.cache_data(show_spinner="최근 영화 목록을 불러오는 중입니다...", ttl=60 * 60 * 6)
def fetch_recent_movie_list(api_key: str, open_start_year: str, open_end_year: str, max_pages: int = 8):
    """
    지정한 개봉연도(YYYY) 범위의 영화 목록을 여러 페이지에 걸쳐 가져와 하나로 합칩니다.
    ※ KOBIS 영화목록 조회 API의 openStartDt/openEndDt는 날짜(yyyymmdd)가 아니라
      '연도 4자리(YYYY)'만 받습니다. 실제 정확한 개봉일 필터링은 이 함수 밖에서
      응답에 담긴 openDt(전체 날짜) 값을 가지고 따로 처리합니다.
    성공하면 (영화 목록, None), 문제가 있으면 ([], "안내 문구")를 반환합니다.
    """
    all_movies = []

    for page in range(1, max_pages + 1):
        params = {
            "key": api_key,
            "curPage": page,
            "itemPerPage": 100,
            "openStartDt": open_start_year,
            "openEndDt": open_end_year,
        }
        try:
            response = requests.get(MOVIE_LIST_URL, params=params, timeout=10)
        except requests.exceptions.RequestException:
            return [], "🌐 영화 목록을 불러오는 중 네트워크 오류가 발생했습니다.\n\n인터넷 연결 상태를 확인하고 다시 시도해 주세요."

        if response.status_code != 200:
            return [], f"⚠️ 영화 목록 서버가 비정상 응답(상태코드 {response.status_code})을 반환했습니다."

        try:
            data = response.json()
        except ValueError:
            return [], "📄 영화 목록 응답을 해석할 수 없습니다 (JSON 형식이 아님)."

        if "faultInfo" in data:
            message = data["faultInfo"].get("message", "알 수 없는 오류")
            return [], f"🔑 인증키 오류로 영화 목록을 가져오지 못했습니다. (메시지: {message})"

        movie_list_result = data.get("movieListResult")
        if movie_list_result is None:
            return [], "❓ 예상하지 못한 영화 목록 응답 형식입니다 (movieListResult 없음)."

        page_movies = movie_list_result.get("movieList", [])
        if not page_movies:
            break

        all_movies.extend(page_movies)

        # 이번 페이지가 100건보다 적게 왔다면 마지막 페이지라는 뜻이므로 그만 가져옵니다.
        if len(page_movies) < 100:
            break

    if not all_movies:
        return [], "📭 해당 기간에 개봉한 영화 데이터를 찾지 못했습니다.\n\n조회 기간을 넓히거나 잠시 후 다시 시도해 주세요."

    return all_movies, None


def filter_movies_within_days(movies: list, end_dt: str, days: int) -> list:
    """
    응답에 담긴 실제 개봉일(openDt, yyyymmdd 8자리)을 기준으로,
    end_dt로부터 최근 days일 이내에 개봉한 영화만 남깁니다.
    yyyymmdd 형식은 문자열 그대로 크기 비교가 가능합니다.
    """
    end_date = datetime.strptime(end_dt, "%Y%m%d")
    start_dt = (end_date - timedelta(days=days)).strftime("%Y%m%d")

    result = []
    for m in movies:
        open_dt = m.get("openDt", "")
        if len(open_dt) == 8 and open_dt.isdigit() and start_dt <= open_dt <= end_dt:
            result.append(m)
    return result


def parse_genres(genre_alt: str) -> list:
    """API가 콤마로 이어 주는 장르 문자열('드라마,코미디')을 리스트로 쪼갭니다."""
    if not genre_alt:
        return []
    return [g.strip() for g in genre_alt.split(",") if g.strip()]


def render_movie_card(movie: dict):
    """영화 한 편을 카드 형태(HTML)로 예쁘게 보여줍니다."""
    open_dt = movie.get("openDt", "")
    if len(open_dt) == 8 and open_dt.isdigit():
        open_dt_display = f"{open_dt[:4]}.{open_dt[4:6]}.{open_dt[6:]}"
    else:
        open_dt_display = "개봉일 미상"

    genres = parse_genres(movie.get("genreAlt", ""))
    genre_tags_html = "".join(f"<span class='genre-tag'>{g}</span>" for g in genres)

    st.markdown(
        f"""
        <div class="movie-card">
            <div class="movie-title">🎬 {movie.get('movieNm', '')}</div>
            <div class="movie-date">개봉일 · {open_dt_display}</div>
            <div>{genre_tags_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# 5. 탭 1 - 어제의 박스오피스
# =========================================================
def render_box_office_tab(api_key: str):
    target_dt = get_yesterday_kst()
    display_date = f"{target_dt[:4]}.{target_dt[4:6]}.{target_dt[6:]}"
    st.caption(f"기준일(한국시간 어제): {display_date} · 자료: 영화진흥위원회(KOBIS)")

    movie_list, error_message = fetch_box_office(api_key, target_dt)
    if error_message is not None:
        st.error(error_message)
        return

    df = build_dataframe(movie_list)

    # --- 1위 영화 지표 카드 3장 ---
    top_movie = df.iloc[0]
    st.markdown(f"<div class='section-title'>🥇 오늘의 1위 · {top_movie['movieNm']}</div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("어제 관객수", f"{top_movie['audiCnt']:,}명")
    c2.metric("누적 관객수", f"{top_movie['audiAcc']:,}명")
    c3.metric("스크린수", f"{top_movie['scrnCnt']:,}개")

    st.write("")

    # --- 관객수 상위 5편 가로 막대그래프 ---
    st.markdown("<div class='section-title'>📊 관객수 상위 5편</div>", unsafe_allow_html=True)
    top5 = df.sort_values("audiCnt", ascending=False).head(5).sort_values("audiCnt")  # 그래프에서 위로 갈수록 높게

    fig = go.Figure(
        go.Bar(
            x=top5["audiCnt"],
            y=top5["movieNm"],
            orientation="h",
            marker=dict(color=top5["audiCnt"], colorscale=[[0, "#C6D0FF"], [1, "#4C6FFF"]]),
            text=[f"{v:,}명" for v in top5["audiCnt"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        height=320,
        margin=dict(l=10, r=70, t=10, b=10),
        xaxis_title="관객수(명)",
        yaxis_title=None,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Noto Sans KR, sans-serif"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.write("")

    # --- 전체 박스오피스 표 ---
    st.markdown("<div class='section-title'>📋 전체 박스오피스 순위</div>", unsafe_allow_html=True)
    table_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].rename(columns=COLUMN_NAME_MAP)
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


# =========================================================
# 6. 탭 2 - MBTI 맞춤 최신 영화 추천
# =========================================================
def render_mbti_tab(api_key: str):
    st.markdown("<div class='section-title'>🧭 MBTI에 맞는 최신 영화 추천</div>", unsafe_allow_html=True)
    st.caption("최근 1년 안에 개봉한 영화 중에서, 성향에 맞는 최신작을 찾아 드립니다.")

    selected_mbti = st.selectbox("당신의 MBTI를 선택하세요", list(MBTI_GENRE_MAP.keys()))

    end_dt = get_yesterday_kst()
    start_year = str(int(end_dt[:4]) - 1)
    end_year = end_dt[:4]

    movies, error_message = fetch_recent_movie_list(api_key, start_year, end_year)
    if error_message is not None:
        st.error(error_message)
        return

    movies = filter_movies_within_days(movies, end_dt, days=365)
    if not movies:
        st.info("😢 최근 1년 안에 개봉한 영화 데이터를 찾지 못했습니다. 잠시 후 다시 시도해 주세요.")
        return

    preferred_genres = set(MBTI_GENRE_MAP[selected_mbti])
    matched = [m for m in movies if set(parse_genres(m.get("genreAlt", ""))) & preferred_genres]
    matched.sort(key=lambda m: m.get("openDt", ""), reverse=True)
    matched = matched[:3]

    if not matched:
        st.info("😢 조건에 맞는 최신 영화를 찾지 못했습니다. 잠시 후 다시 시도해 주세요.")
        return

    st.caption(f"{selected_mbti} 추천 장르 · " + " / ".join(sorted(preferred_genres)))

    cols = st.columns(len(matched))
    for col, movie in zip(cols, matched):
        with col:
            render_movie_card(movie)


# =========================================================
# 7. 탭 3 - 장르별 영화 검색 (다중 장르 AND 조건)
# =========================================================
def render_genre_search_tab(api_key: str):
    st.markdown("<div class='section-title'>🎞️ 장르별 영화 검색</div>", unsafe_allow_html=True)
    st.caption("장르를 여러 개 고르면, 선택한 장르를 모두 포함하는 최근 1년 개봉작만 찾아 드립니다.")

    selected_genres = st.multiselect("장르 선택 (여러 개 선택 가능)", GENRE_OPTIONS)

    if not selected_genres:
        st.info("👆 장르를 한 개 이상 선택해 주세요.")
        return

    end_dt = get_yesterday_kst()
    start_year = str(int(end_dt[:4]) - 1)
    end_year = end_dt[:4]

    movies, error_message = fetch_recent_movie_list(api_key, start_year, end_year)
    if error_message is not None:
        st.error(error_message)
        return

    movies = filter_movies_within_days(movies, end_dt, days=365)
    if not movies:
        st.info("😢 최근 1년 안에 개봉한 영화 데이터를 찾지 못했습니다. 잠시 후 다시 시도해 주세요.")
        return

    selected_set = set(selected_genres)
    matched = [m for m in movies if selected_set.issubset(set(parse_genres(m.get("genreAlt", ""))))]
    matched.sort(key=lambda m: m.get("openDt", ""), reverse=True)

    if not matched:
        st.warning("🔍 선택한 장르를 모두 포함하는 영화를 찾지 못했습니다. 장르 수를 줄여서 다시 시도해 보세요.")
        return

    st.success(f"✅ 조건에 맞는 영화 {len(matched)}편을 찾았습니다. (최근 1년 개봉작 기준, 최대 30편 표시)")

    for movie in matched[:30]:
        render_movie_card(movie)


# =========================================================
# 8. 전체 화면 구성
# =========================================================
def main():
    inject_custom_css()

    st.markdown("<div class='main-title'>🎬 무비 인사이트</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='sub-caption'>어제의 박스오피스부터 MBTI 맞춤 추천, 장르 검색까지 한 번에</div>",
        unsafe_allow_html=True,
    )

    api_key, key_error = get_kobis_key()
    if key_error is not None:
        st.error(key_error)
        return

    tab1, tab2, tab3 = st.tabs(["📅 어제의 박스오피스", "🧭 MBTI 영화 추천", "🎞️ 장르별 영화 검색"])

    with tab1:
        render_box_office_tab(api_key)

    with tab2:
        render_mbti_tab(api_key)

    with tab3:
        render_genre_search_tab(api_key)


if __name__ == "__main__":
    main()
