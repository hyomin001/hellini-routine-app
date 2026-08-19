# -*- coding: utf-8 -*-
import streamlit as st

from utils import db
from utils.data import ALL_EXERCISE_NAMES

st.set_page_config(page_title="랭킹 - 헬린이 루틴", page_icon="🏆", layout="centered")

if "user" not in st.session_state:
    st.warning("먼저 로그인해주세요.")
    st.page_link("app.py", label="🏠 로그인하러 가기")
    st.stop()

user = st.session_state["user"]

with st.sidebar:
    st.markdown(f"### 👋 {user['nickname']}님")
    if st.button("로그아웃", use_container_width=True):
        del st.session_state["user"]
        st.rerun()
    st.divider()
    st.page_link("app.py", label="🏠 오늘의 루틴")
    st.page_link("pages/1_마이페이지.py", label="📖 마이페이지")
    st.page_link("pages/2_랭킹.py", label="🏆 랭킹")
    st.page_link("pages/3_문의하기.py", label="💬 문의하기")

st.title("🏆 운동별 랭킹")
st.caption("가장 무거운 무게로, 같은 무게면 가장 많은 횟수로 든 사람이 1등이에요.")

exercise = st.selectbox("운동 선택", ALL_EXERCISE_NAMES)

rows = db.get_leaderboard(exercise, limit=20)

if not rows:
    st.info("아직 이 운동에 대한 기록이 없어요. 가장 먼저 기록을 남겨보세요!")
else:
    my_nickname = user["nickname"]
    table = []
    for i, r in enumerate(rows, start=1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}")
        nickname = r["nickname"] + (" (나)" if r["nickname"] == my_nickname else "")
        table.append(
            {
                "순위": medal,
                "닉네임": nickname,
                "무게(kg)": r["weight"],
                "횟수": r["reps"],
                "날짜": r["date"],
            }
        )
    st.dataframe(table, use_container_width=True, hide_index=True)
