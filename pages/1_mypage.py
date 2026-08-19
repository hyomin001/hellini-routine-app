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
    logs = db.get_all_logs(user["id"])
    if not logs:
        st.info("아직 기록이 없어요.")
    else:
        by_date = {}
        for d in logs:
            by_date.setdefault(d["date"], []).append(d)

        for date_str in sorted(by_date.keys(), reverse=True):
            entries = by_date[date_str]
            with st.expander(f"{date_str} · 운동 {len(entries)}개"):
                for e in entries:
                    valid = [s for s in e["sets"] if s.get("w") not in (None, "") and s.get("r") not in (None, "")]
                    sets_txt = " / ".join(f"{s['w']}kg×{s['r']}회" for s in valid) if valid else "기록 없음"
                    st.markdown(f"**{e['exercise_name']}**  \n{sets_txt}")
                    if e.get("memo"):
                        st.caption(f"메모: {e['memo']}")
                    if st.button("삭제", key=f"del_{e['_id']}"):
                        db.delete_log(user["id"], e["date"], e["exercise_name"])
                        st.rerun()
                    st.markdown("---")
