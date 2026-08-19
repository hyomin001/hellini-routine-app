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
