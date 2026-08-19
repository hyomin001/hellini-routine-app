# -*- coding: utf-8 -*-
import datetime as dt

import streamlit as st

from utils import db
from utils import ui
from utils.data import DAYS, exercises_for_day

st.set_page_config(page_title="헬린이 루틴", page_icon="🏋️", layout="centered")

DAY_COLORS = {
    "DAY1": "#FF9F5A",
    "DAY2": "#5AA9FF",
    "DAY3": "#5AFF9F",
    "DAY4": "#FF5A9F",
}

# ================= 커스텀 스타일 (원본 HTML 다크 테마 톤 맞춤) =================
st.markdown(
    """
    <style>
    .stApp { background-color: #121316; }

    /* 운동 카드 느낌 나는 expander */
    div[data-testid="stExpander"] {
        background-color: #1B1D22;
        border: 1px solid #33373F;
        border-radius: 14px;
        margin-bottom: 10px;
    }
    div[data-testid="stExpander"] summary {
        font-weight: 600;
        font-size: 15.5px;
    }

    /* 진행상황 chip */
    .progress-chip {
        font-family: monospace;
        font-size: 12.5px;
        padding: 4px 12px;
        border-radius: 999px;
        background: #23262C;
        color: #9296A0;
        border: 1px solid #33373F;
        display: inline-block;
    }
    .progress-chip.done {
        color: #121316;
        background: #4ECDC4;
        border-color: #4ECDC4;
    }

    /* 요일 뱃지 */
    .day-badge {
        display:inline-block; padding:2px 10px; border-radius:999px;
        font-size:11px; font-weight:700; letter-spacing:0.03em;
        color:#121316; margin-bottom:6px;
    }

    .equip-line { color:#9296A0; font-size:13px; margin-bottom:4px;}
    .pr-line { color:#FFC834; font-size:13px; font-weight:600; }
    .caution-box {
        background:#2B1B1B; border:1px solid #4A2A2A; color:#FF9B9B;
        border-radius:10px; padding:10px 12px; font-size:13px; margin:8px 0;
    }
    .tip-box {
        background:#1E241E; border:1px solid #2E3E2E; color:#B9E6B9;
        border-radius:10px; padding:10px 12px; font-size:13px; margin:8px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


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
    st.markdown("### 🏋️ 헬린이 루틴")
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
    db.touch_presence(user["id"], user["username"], user["nickname"])
    ui.render_sidebar(user)

    st.markdown("### 🏋️ 헬린이 루틴")

    selected_date = st.date_input("날짜", value=dt.date.today(), key="today_date")
    date_str = selected_date.isoformat()

    st.markdown(
        "<div style='background:#1B1D22; border:1px solid #33373F; border-radius:8px; "
        "padding:10px 12px; font-size:12.5px; color:#9296A0; margin:10px 0 18px;'>"
        "✓ 모든 무게는 마지막 2~3개가 <b style='color:#FFC834;'>매우 힘들 정도</b>로 진행하세요. "
        "주 4회가 힘들면 DAY 순서(사이클)만 지켜서 따라하면 됩니다."
        "</div>",
        unsafe_allow_html=True,
    )

    day_labels = [f"{d['label']} · {d['part']}" for d in DAYS]
    tab_objs = st.tabs(day_labels)

    log_for_date = db.get_log_for_date(user["id"], date_str)
    pr_map = db.get_personal_records(user["id"])

    for tab, day in zip(tab_objs, DAYS):
        with tab:
            exercises = exercises_for_day(day["key"])
            done_count = 0

            color = DAY_COLORS.get(day["key"], "#FFC834")
            st.markdown(
                f"<span class='day-badge' style='background:{color};'>{day['label']} · {day['part']}</span>",
                unsafe_allow_html=True,
            )

            # 먼저 완료 개수 계산
            for ex in exercises:
                existing = log_for_date.get(ex["name"])
                sets_state = existing["sets"] if existing else [{"w": "", "r": ""} for _ in range(ex["sets"])]
                is_complete = existing is not None and all(
                    s.get("w") not in (None, "") and s.get("r") not in (None, "") for s in sets_state
                )
                if is_complete:
                    done_count += 1

            chip_class = "progress-chip done" if done_count == len(exercises) else "progress-chip"
            st.markdown(
                f"<div style='text-align:right; margin-bottom:10px;'>"
                f"<span class='{chip_class}'>{done_count}/{len(exercises)} 완료</span></div>",
                unsafe_allow_html=True,
            )

            for ex in exercises:
                # 날짜 + 요일 + 운동이름으로 고유 키 구성 (요일 간 동일 운동명 중복 방지)
                base_key = f"{date_str}_{day['key']}_{ex['name']}"

                existing = log_for_date.get(ex["name"])
                sets_state = existing["sets"] if existing else [{"w": "", "r": ""} for _ in range(ex["sets"])]
                memo_state = existing["memo"] if existing else ""
                is_complete = existing is not None and all(
                    s.get("w") not in (None, "") and s.get("r") not in (None, "") for s in sets_state
                )

                pr = pr_map.get(ex["name"])
                pr_txt = f" · 🏅 {pr['weight']:g}kg × {pr['reps']}회" if pr else ""

                with st.expander(f"{'✅ ' if is_complete else ''}{ex['name']}{pr_txt}"):
                    img_col, info_col = st.columns([1, 2])
                    with img_col:
                        try:
                            st.image(ex["img_path"], use_container_width=True)
                        except Exception:
                            pass
                    with info_col:
                        st.markdown(
                            f"<div class='equip-line'>🎯 {ex['sets']}세트 · {ex['reps']}</div>"
                            f"<div class='equip-line'>🛠️ {ex['equip']}</div>",
                            unsafe_allow_html=True,
                        )
                        if pr:
                            st.markdown(
                                f"<div class='pr-line'>🏅 최고기록 {pr['weight']:g}kg × {pr['reps']}회</div>",
                                unsafe_allow_html=True,
                            )

                    if ex.get("howto"):
                        with st.container():
                            st.markdown("**동작 방법**")
                            steps_md = "\n".join(f"{i+1}. {s}" for i, s in enumerate(ex["howto"]))
                            st.markdown(steps_md)

                    if ex.get("caution"):
                        st.markdown(
                            f"<div class='caution-box'>⚠️ <b>주의사항</b><br>{ex['caution']}</div>",
                            unsafe_allow_html=True,
                        )
                    if ex.get("tip"):
                        st.markdown(
                            f"<div class='tip-box'>💡 <b>팁</b><br>{ex['tip']}</div>",
                            unsafe_allow_html=True,
                        )

                    st.markdown("---")
                    st.markdown("**세트 기록**")

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
                            "무게", value=str(s.get("w", "")), key=f"{base_key}_w_{i}",
                            label_visibility="collapsed", placeholder="kg",
                        )
                        r_val = c3.text_input(
                            "횟수", value=str(s.get("r", "")), key=f"{base_key}_r_{i}",
                            label_visibility="collapsed", placeholder="회",
                        )
                        new_sets.append({"w": w_val, "r": r_val})

                    memo_val = st.text_input(
                        "메모", value=memo_state, key=f"{base_key}_memo",
                        placeholder="컨디션, 폼 체크 등 메모",
                    )

                    if st.button("이 운동 저장", key=f"{base_key}_save", use_container_width=True):
                        db.save_exercise_log(user["id"], date_str, ex["name"], new_sets, memo_val)
                        st.toast(f"{ex['name']} 저장 완료!", icon="✅")
                        st.rerun()


# ================= 라우팅 =================
if "user" not in st.session_state:
    render_auth()
else:
    render_today(st.session_state["user"])
