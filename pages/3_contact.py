# -*- coding: utf-8 -*-
import streamlit as st

from utils import db
from utils import ui

st.set_page_config(page_title="문의하기 - 헬린이 루틴", page_icon="💬", layout="centered")

ui.inject_base_css()

user = ui.require_login()
ui.render_sidebar(user)

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
