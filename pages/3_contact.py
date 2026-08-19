# -*- coding: utf-8 -*-
import streamlit as st

from utils import db

st.set_page_config(page_title="문의하기 - 헬린이 루틴", page_icon="💬", layout="centered")

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
    st.page_link("pages/1_mypage.py", label="📖 마이페이지")
    st.page_link("pages/2_ranking.py", label="🏆 랭킹")
    st.page_link("pages/3_contact.py", label="💬 문의하기")

st.title("💬 문의하기")
st.caption("추가했으면 하는 운동, 기능 개선 아이디어, 버그 제보 등 자유롭게 남겨주세요.")

with st.form("inquiry_form", clear_on_submit=True):
    category = st.selectbox("종류", db.CATEGORIES)
    content = st.text_area("내용", placeholder="예) 데드리프트도 추가해주세요! / 타이머 기능이 있으면 좋겠어요.")
    submitted = st.form_submit_button("제출", use_container_width=True)

if submitted:
    if not content.strip():
        st.error("내용을 입력해주세요.")
    else:
        db.add_inquiry(user["id"], user["nickname"], category, content)
        st.success("문의가 접수됐어요. 감사합니다!")
        st.rerun()

st.divider()
st.subheader("📋 모두의 문의")

only_mine = st.toggle("내 문의만 보기")
inquiries = db.get_inquiries()
if only_mine:
    inquiries = [q for q in inquiries if q["user_id"] == user["id"]]

if not inquiries:
    st.info("아직 등록된 문의가 없어요.")
else:
    for q in inquiries:
        date_str = q["created_at"].strftime("%Y-%m-%d %H:%M")
        with st.container(border=True):
            st.markdown(f"**[{q['category']}]** {q['content']}")
            st.caption(f"{q['nickname']} · {date_str} · 상태: {q.get('status', '접수')}")
