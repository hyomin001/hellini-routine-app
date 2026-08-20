# -*- coding: utf-8 -*-
import streamlit as st

from utils import db
from utils import ui
from utils.data import ALL_EXERCISE_NAMES

st.set_page_config(page_title="관리자 - 헬린이 루틴", page_icon="🛠️", layout="centered")

ui.inject_base_css()

user = ui.require_login()
ui.render_sidebar(user)

if not db.is_admin(user["username"]):
    st.title("🛠️ 관리자 페이지")
    st.error("이 페이지는 관리자만 볼 수 있어요.")
    st.caption(
        "관리자로 지정되고 싶다면 `.streamlit/secrets.toml` (배포 환경이면 Streamlit Cloud "
        "Secrets)에 `ADMIN_USERNAMES = \"내아이디\"` 를 추가해주세요. "
        "여러 명이면 쉼표로 구분하면 돼요. 예) `ADMIN_USERNAMES = \"hyomin,friend_id\"`"
    )
    st.stop()

st.title("🛠️ 관리자 페이지")
st.caption(f"{user['nickname']}님, 어서오세요. 여기는 운영자만 볼 수 있어요.")

tab_dash, tab_users, tab_inquiries = st.tabs(["📊 대시보드", "👥 회원 관리", "💬 문의 관리"])

# ================= 대시보드 =================
with tab_dash:
    stats = db.get_dashboard_stats()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👥 총 가입자", f"{stats['total_users']}명")
    c2.metric("🟢 현재 접속자", f"{stats['active_users']}명")
    c3.metric("📝 총 운동 기록", f"{stats['total_logs']}건")
    c4.metric("💬 미처리 문의", f"{stats['open_inquiries']}건")

    st.divider()
    st.subheader("🟢 지금 접속 중인 사람")
    active = db.get_active_users()
    if not active:
        st.info("현재 활동 중인 사람이 없어요.")
    else:
        st.dataframe(
            [
                {
                    "닉네임": a["nickname"],
                    "아이디": a["username"],
                    "마지막 활동": a["last_seen"].strftime("%Y-%m-%d %H:%M:%S"),
                }
                for a in active
            ],
            use_container_width=True,
            hide_index=True,
        )
    st.caption(f"최근 {db.ACTIVE_WINDOW_MINUTES}분 이내 활동한 사람을 '접속 중'으로 집계해요.")

    st.divider()
    st.subheader("👑 종목별 챔피언 요약")
    champs = db.get_champions(ALL_EXERCISE_NAMES)
    if champs:
        rows = [
            {"운동": name, "1위": c["nickname"], "무게(kg)": c["weight"], "횟수": c["reps"]}
            for name, c in champs.items()
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("아직 기록이 없어요.")

# ================= 회원 관리 =================
with tab_users:
    users = db.list_all_users()
    st.caption(f"총 {len(users)}명")

    search = st.text_input("아이디/닉네임 검색", placeholder="검색어 입력")
    if search:
        s = search.strip().lower()
        users = [u for u in users if s in u["username"].lower() or s in u["nickname"].lower()]

    for u in users:
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                admin_tag = " · 🛡️ 관리자" if db.is_admin(u["username"]) else ""
                st.markdown(f"**{u['nickname']}**  (@{u['username']}){admin_tag}")
                st.caption(f"가입일: {u['created_at'].strftime('%Y-%m-%d %H:%M')}")
            with c2:
                if u["username"] == user["username"]:
                    st.caption("나")
                elif db.is_admin(u["username"]):
                    st.caption("관리자")
                else:
                    confirm_key = f"confirm_del_{u['_id']}"
                    if st.session_state.get(confirm_key):
                        if st.button("정말 삭제?", key=f"final_{u['_id']}", type="primary"):
                            db.delete_user(str(u["_id"]))
                            st.session_state.pop(confirm_key, None)
                            st.toast(f"{u['nickname']} 계정을 삭제했어요.", icon="🗑️")
                            st.rerun()
                    else:
                        if st.button("삭제", key=f"del_{u['_id']}"):
                            st.session_state[confirm_key] = True
                            st.rerun()

# ================= 문의 관리 =================
with tab_inquiries:
    inquiries = db.get_inquiries(limit=500)
    st.caption(f"총 {len(inquiries)}건")

    status_filter = st.selectbox("상태 필터", ["전체"] + db.STATUS_OPTIONS)
    if status_filter != "전체":
        inquiries = [q for q in inquiries if q.get("status", "접수") == status_filter]

    if not inquiries:
        st.info("해당하는 문의가 없어요.")
    else:
        for q in inquiries:
            date_str = q["created_at"].strftime("%Y-%m-%d %H:%M")
            with st.container(border=True):
                st.markdown(f"**[{q['category']}]** {q['content']}")
                st.caption(f"{q['nickname']} · {date_str}")

                c1, c2 = st.columns([3, 1])
                with c1:
                    new_status = st.selectbox(
                        "상태",
                        db.STATUS_OPTIONS,
                        index=db.STATUS_OPTIONS.index(q.get("status", "접수")),
                        key=f"status_{q['_id']}",
                        label_visibility="collapsed",
                    )
                    if new_status != q.get("status", "접수"):
                        db.update_inquiry_status(q["_id"], new_status)
                        st.toast("상태를 업데이트했어요.", icon="✅")
                        st.rerun()
                with c2:
                    if st.button("삭제", key=f"del_inq_{q['_id']}"):
                        db.delete_inquiry(q["_id"])
                        st.rerun()
