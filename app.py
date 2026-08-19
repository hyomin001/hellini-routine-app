# -*- coding: utf-8 -*-
import datetime as dt

import streamlit as st

from utils import db
from utils.data import DAYS, exercises_for_day

st.set_page_config(page_title="헬린이 루틴", page_icon="🏋️", layout="centered")


@st.cache_resource(show_spinner=False)
def _init_once():
    db.init_indexes()
    return True


try:
    _init_once()
except Exception as e:
    st.error("데이터베이스 연결에 실패했어요. .streamlit/secrets.toml 의 MONGO_URI 설정을 확인해주세요.")
    st.exception(e)
    st.stop()


# ================= 로그인 / 회원가입 =================
def render_auth():
    st.title("🏋️ 헬린이 루틴")
    st.caption("로그인하고 내 운동 기록을 저장해보세요.")

    tab_login, tab_signup = st.tabs(["로그인", "회원가입"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("아이디")
            password = st.text_input("비밀번호", type="password")
            submitted = st.form_submit_button("로그인", use_container_width=True)
        if submitted:
            user = db.authenticate(username, password)
            if user:
                st.session_state["user"] = {
                    "id": str(user["_id"]),
                    "username": user["username"],
                    "nickname": user["nickname"],
                }
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 일치하지 않아요.")

    with tab_signup:
        with st.form("signup_form"):
            new_username = st.text_input("아이디", key="su_username")
            new_nickname = st.text_input("닉네임 (랭킹에 표시돼요)", key="su_nickname")
            new_password = st.text_input("비밀번호", type="password", key="su_password")
            new_password2 = st.text_input("비밀번호 확인", type="password", key="su_password2")
            submitted2 = st.form_submit_button("회원가입", use_container_width=True)
        if submitted2:
            if new_password != new_password2:
                st.error("비밀번호가 서로 달라요.")
            else:
                ok, msg = db.create_user(new_username, new_password, new_nickname)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)


# ================= 오늘의 루틴 =================
def render_today(user: dict):
    st.title("🏋️ 헬린이 루틴")

    with st.sidebar:
        st.markdown(f"### 👋 {user['nickname']}님")
        st.caption(f"@{user['username']}")
        if st.button("로그아웃", use_container_width=True):
            del st.session_state["user"]
            st.rerun()
        st.divider()
        st.page_link("app.py", label="🏠 오늘의 루틴")
        st.page_link("pages/1_마이페이지.py", label="📖 마이페이지")
        st.page_link("pages/2_랭킹.py", label="🏆 랭킹")
        st.page_link("pages/3_문의하기.py", label="💬 문의하기")

    selected_date = st.date_input("날짜", value=dt.date.today(), key="today_date")
    date_str = selected_date.isoformat()

    day_labels = [f"{d['label']} · {d['part']}" for d in DAYS]
    tab_objs = st.tabs(day_labels)

    log_for_date = db.get_log_for_date(user["id"], date_str)
    pr_map = db.get_personal_records(user["id"])

    for tab, day in zip(tab_objs, DAYS):
        with tab:
            exercises = exercises_for_day(day["key"])
            done_count = 0

            for ex in exercises:
                existing = log_for_date.get(ex["name"])
                sets_state = existing["sets"] if existing else [{"w": "", "r": ""} for _ in range(ex["sets"])]
                memo_state = existing["memo"] if existing else ""
                is_complete = existing is not None and all(
                    s.get("w") not in (None, "") and s.get("r") not in (None, "") for s in sets_state
                )
                if is_complete:
                    done_count += 1

                pr = pr_map.get(ex["name"])
                pr_txt = f" · 🏅 최고기록 {pr['weight']:g}kg × {pr['reps']}회" if pr else ""

                with st.expander(f"{'✅ ' if is_complete else ''}{ex['name']}{pr_txt}"):
                    st.caption(f"목표 {ex['sets']}세트 · {ex['reps']} · {ex['equip']}")

                    new_sets = []
                    cols_header = st.columns([1, 2, 2])
                    cols_header[0].markdown("**세트**")
                    cols_header[1].markdown("**무게(kg)**")
                    cols_header[2].markdown("**횟수**")
                    for i in range(ex["sets"]):
                        s = sets_state[i] if i < len(sets_state) else {"w": "", "r": ""}
                        c1, c2, c3 = st.columns([1, 2, 2])
                        c1.markdown(f"{i+1}세트")
                        w_val = c2.text_input(
                            "무게", value=str(s.get("w", "")), key=f"{date_str}_{ex['name']}_w_{i}",
                            label_visibility="collapsed", placeholder="kg",
                        )
                        r_val = c3.text_input(
                            "횟수", value=str(s.get("r", "")), key=f"{date_str}_{ex['name']}_r_{i}",
                            label_visibility="collapsed", placeholder="회",
                        )
                        new_sets.append({"w": w_val, "r": r_val})

                    memo_val = st.text_input(
                        "메모", value=memo_state, key=f"{date_str}_{ex['name']}_memo",
                        placeholder="컨디션, 폼 체크 등 메모",
                    )

                    if st.button("이 운동 저장", key=f"{date_str}_{ex['name']}_save"):
                        db.save_exercise_log(user["id"], date_str, ex["name"], new_sets, memo_val)
                        st.toast(f"{ex['name']} 저장 완료!", icon="✅")
                        st.rerun()

            st.caption(f"진행 상황: {done_count} / {len(exercises)} 완료")


# ================= 라우팅 =================
if "user" not in st.session_state:
    render_auth()
else:
    render_today(st.session_state["user"])
