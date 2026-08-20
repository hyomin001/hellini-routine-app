# -*- coding: utf-8 -*-
import streamlit as st

from utils import db
from utils import ui

st.set_page_config(page_title="마이페이지 - 헬린이 루틴", page_icon="📖", layout="centered")

user = ui.require_login()
ui.render_sidebar(user)

st.title("📖 마이페이지")
st.caption(f"{user['nickname']}님의 운동 기록")

tab_pr, tab_history = st.tabs(["🏅 개인 최고기록", "🗓️ 기록 히스토리"])

with tab_pr:
    pr_map = db.get_personal_records(user["id"])
    if not pr_map:
        st.info("아직 기록이 없어요. 오늘의 루틴에서 운동을 기록해보세요!")
    else:
        rows = [
            {"운동": name, "최고 무게(kg)": rec["weight"], "횟수": rec["reps"], "날짜": rec["date"]}
            for name, rec in sorted(pr_map.items(), key=lambda kv: -kv[1]["weight"])
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

with tab_history:
    ui.render_history_tab(user)
