# -*- coding: utf-8 -*-
import streamlit as st

from utils import db
from utils import ui
from utils.data import ALL_EXERCISE_NAMES

st.set_page_config(page_title="랭킹 - 헬린이 루틴", page_icon="🏆", layout="centered")

ui.inject_base_css()

user = ui.require_login()
ui.render_sidebar(user)

st.title("🏆 운동별 랭킹")
st.caption("가장 무거운 무게로, 같은 무게면 가장 많은 횟수로 든 사람이 1등이에요.")

my_nickname = user["nickname"]

tab_champs, tab_detail = st.tabs(["👑 전체 종목 1위", "📋 종목별 TOP 20"])

with tab_champs:
    st.caption("각 운동마다 현재 최고 기록 보유자예요. 이름 옆에 뜨고 싶다면 지금 기록을 남겨보세요 🔥")
    champs = db.get_champions(ALL_EXERCISE_NAMES)
    if not champs:
        st.info("아직 아무도 기록을 남기지 않았어요. 첫 챔피언이 되어보세요!")
    else:
        rows = []
        for name in ALL_EXERCISE_NAMES:
            c = champs.get(name)
            if not c:
                continue
            nickname = c["nickname"] + (" 👈 나" if c["nickname"] == my_nickname else "")
            rows.append(
                {
                    "운동": name,
                    "🥇 1위": nickname,
                    "무게(kg)": c["weight"],
                    "횟수": c["reps"],
                    "날짜": c["date"],
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
        missing = [n for n in ALL_EXERCISE_NAMES if n not in champs]
        if missing:
            st.caption("아직 기록이 없는 종목: " + ", ".join(missing))

with tab_detail:
    exercise = st.selectbox("운동 선택", ALL_EXERCISE_NAMES)
    rows = db.get_leaderboard(exercise, limit=20)

    if not rows:
        st.info("아직 이 운동에 대한 기록이 없어요. 가장 먼저 기록을 남겨보세요!")
    else:
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
