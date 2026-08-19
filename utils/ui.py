# -*- coding: utf-8 -*-
"""
페이지마다 반복되던 사이드바(네비게이션 + 로그아웃 + 접속 현황)를 한 곳에 모아둔 공용 컴포넌트.
"""
import streamlit as st

from utils import db


def require_login() -> dict:
    """로그인 안 돼있으면 안내하고 멈춘다. 로그인 돼있으면 user dict 반환 + 접속 하트비트 갱신."""
    if "user" not in st.session_state:
        st.warning("먼저 로그인해주세요.")
        st.page_link("app.py", label="🏠 로그인하러 가기")
        st.stop()

    user = st.session_state["user"]
    db.touch_presence(user["id"], user["username"], user["nickname"])
    return user


def render_sidebar(user: dict):
    admin = db.is_admin(user["username"])

    with st.sidebar:
        st.markdown(f"### 👋 {user['nickname']}님")
        if admin:
            st.caption("🛡️ 관리자 계정")
        else:
            st.caption(f"@{user['username']}")

        if st.button("로그아웃", use_container_width=True):
            del st.session_state["user"]
            st.rerun()

        st.divider()
        st.page_link("app.py", label="🏠 오늘의 루틴")
        st.page_link("pages/1_mypage.py", label="📖 마이페이지")
        st.page_link("pages/2_ranking.py", label="🏆 랭킹")
        st.page_link("pages/3_contact.py", label="💬 문의하기")
        if admin:
            st.page_link("pages/4_admin.py", label="🛠️ 관리자 페이지")

        st.divider()
        total = db.get_total_user_count()
        active = db.get_active_user_count()
        st.markdown(
            f"<div style='font-size:12.5px; color:#9296A0; line-height:1.7;'>"
            f"👥 총 가입자 <b style='color:#F2F1EC;'>{total}</b>명<br>"
            f"🟢 현재 접속 <b style='color:#4ECDC4;'>{active}</b>명"
            f"</div>",
            unsafe_allow_html=True,
        )

    return admin


def render_log_entry_editable(user: dict, e: dict):
    """마이페이지 '기록 히스토리'의 운동 기록 한 줄.

    기본은 보기 모드(수정/삭제 버튼)이고, '수정'을 누르면 그 자리에서 바로
    세트/메모를 고쳐서 저장할 수 있다. 잘못 입력했을 때 삭제 후 처음부터
    다시 기록할 필요 없이 값만 바로잡으면 된다.
    """
    entry_id = str(e["_id"])
    edit_key = f"editing_log_{entry_id}"
    editing = st.session_state.get(edit_key, False)

    if not editing:
        valid = [s for s in e["sets"] if s.get("w") not in (None, "") and s.get("r") not in (None, "")]
        sets_txt = " / ".join(f"{s['w']}kg×{s['r']}회" for s in valid) if valid else "기록 없음"
        st.markdown(f"**{e['exercise_name']}**  \n{sets_txt}")
        if e.get("memo"):
            st.caption(f"메모: {e['memo']}")

        c1, c2 = st.columns(2)
        if c1.button("✏️ 수정", key=f"edit_{entry_id}", use_container_width=True):
            st.session_state[edit_key] = True
            st.rerun()
        if c2.button("🗑️ 삭제", key=f"del_{entry_id}", use_container_width=True):
            db.delete_log(user["id"], e["date"], e["exercise_name"])
            st.rerun()
    else:
        st.markdown(f"**{e['exercise_name']}** 수정 중")
        new_sets = []
        for i, s in enumerate(e["sets"]):
            sc1, sc2, sc3 = st.columns([0.9, 1.5, 1.5])
            sc1.markdown(
                f"<div style='padding-top:10px; font-size:12px; color:#9296A0; white-space:nowrap;'>{i+1}세트</div>",
                unsafe_allow_html=True,
            )
            w_val = sc2.text_input(
                "무게", value=str(s.get("w", "")), key=f"edit_w_{entry_id}_{i}",
                label_visibility="collapsed", placeholder="kg",
            )
            r_val = sc3.text_input(
                "횟수", value=str(s.get("r", "")), key=f"edit_r_{entry_id}_{i}",
                label_visibility="collapsed", placeholder="회",
            )
            new_sets.append({"w": w_val, "r": r_val})

        memo_val = st.text_input("메모", value=e.get("memo", ""), key=f"edit_memo_{entry_id}")

        c1, c2 = st.columns(2)
        if c1.button("💾 저장", key=f"save_{entry_id}", use_container_width=True, type="primary"):
            db.save_exercise_log(user["id"], e["date"], e["exercise_name"], new_sets, memo_val)
            st.session_state[edit_key] = False
            st.toast(f"{e['exercise_name']} 수정 완료!", icon="✅")
            st.rerun()
        if c2.button("취소", key=f"cancel_{entry_id}", use_container_width=True):
            st.session_state[edit_key] = False
            st.rerun()

    st.markdown("---")
