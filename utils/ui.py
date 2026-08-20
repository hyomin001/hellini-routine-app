# -*- coding: utf-8 -*-
"""
페이지마다 반복되던 사이드바(네비게이션 + 로그아웃 + 접속 현황)와,
모바일에서 버튼/입력창이 화면 밖으로 넘어가는 걸 막는 공통 CSS를 한 곳에 모아둔 공용 컴포넌트.

중요: app.py와 pages/*.py는 Streamlit 멀티페이지 구조상 서로 "다른 스크립트"라서
app.py에 넣은 <style>은 다른 페이지(마이페이지/랭킹/문의/관리자)에는 전혀 적용되지 않는다.
그래서 반드시 inject_base_css()를 모든 페이지(app.py 포함) 맨 앞에서 호출해야
버튼 넘침 방지 스타일이 어느 페이지에서든 똑같이 적용된다.

== 새로운 가로배치(컬럼) 줄을 만들 때 지켜야 하는 규칙 ==
버튼 2개짜리 줄(예: 수정/삭제, 저장/취소)처럼 "여러 요소를 폭 안에서 균등하게 배치"하고
싶으면, 반드시 st.container(key=f"evenrow_...")로 감싸기만 하면 된다. 아래 CSS가
"st-key-evenrow_"로 시작하는 컨테이너는 전부 자동으로 CSS Grid 균등분할 + 버튼 축소를
적용해주기 때문에, 매번 새 CSS 룰을 추가할 필요가 없다.

"N세트 · 무게 · 횟수"처럼 첫 칸은 좁고 나머지 두 칸은 입력창인 줄은
st.container(key=f"setrow_...")로 감싸면 동일하게 자동 처리된다.
"""
import streamlit as st

from utils import db

BASE_CSS = """
<style>
/* ===== 모바일(폰 세로 화면) 최적화 : 모든 페이지 공통 ===== */
@media (max-width: 480px) {
    .block-container {
        padding-left: 0.9rem !important;
        padding-right: 0.9rem !important;
        padding-top: 1.2rem !important;
    }
    .stButton > button {
        min-height: 42px;
        font-size: 13.5px !important;
        padding: 6px 6px !important;
    }
    .stCaption, [data-testid="stCaptionContainer"] {
        font-size: 12px !important;
    }
    div[data-testid="stExpander"] summary {
        font-size: 14.5px;
        padding: 10px 12px;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] {
        padding: 6px 8px !important;
        font-size: 14px !important;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 0.5rem !important;
    }
    button[data-baseweb="tab"] {
        font-size: 12.5px !important;
        padding: 8px 10px !important;
    }
}

/* ===== Streamlit이 좁은 화면에서 컬럼(가로배치)을 세로로 쌓아버리는 기본 동작을 막는다 =====
   (세트/무게/횟수, 버튼 줄 등이 세로로 길게 쌓이는 걸 방지) */
div[data-testid="stHorizontalBlock"] {
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    align-items: flex-start !important;
    width: 100% !important;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    min-width: 0 !important;
    flex-shrink: 1 !important;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div {
    min-width: 0 !important;
}
/* 인풋/버튼/셀렉트박스가 내부에서 컬럼 폭을 넘어가지 않도록 (사이트 전체 공통) */
div[data-testid="stTextInput"] input,
div[data-testid="stTextInput"],
div[data-testid="stSelectbox"],
.stButton, .stButton > button {
    min-width: 0 !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
/* 만에 하나 안쪽에서 넘치는 요소가 있어도 화면 자체가
   가로로 스크롤되지 않게 최종 안전장치 */
html, body, .stApp, section.main, .main .block-container {
    overflow-x: hidden !important;
}

/* ===== 공용 규칙 1: st.container(key=f"evenrow_...") 로 감싼 줄은
   요소 개수와 상관없이 항상 폭 안에서 균등하게 나뉜다 (버튼 2개, 3개, 4개 다 동일 동작).
   새로 버튼 줄을 추가할 때마다 CSS를 새로 안 만들어도 되게 하기 위한 범용 규칙. ===== */
div[class*="st-key-evenrow_"] div[data-testid="stHorizontalBlock"] {
    display: grid !important;
    grid-auto-flow: column !important;
    grid-auto-columns: minmax(0, 1fr) !important;
    gap: 8px !important;
    width: 100% !important;
}
div[class*="st-key-evenrow_"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    width: auto !important;
    min-width: 0 !important;
}
div[class*="st-key-evenrow_"] .stButton > button {
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    font-size: 12.5px !important;
    padding: 5px 4px !important;
    min-height: 36px !important;
}

/* ===== 공용 규칙 2: st.container(key=f"setrow_...") 로 감싼 줄은
   "번호 칸(46px) + 입력창 2개"로 고정 분할 (운동 세트 입력용, 원본/수정 모드 공통). ===== */
div[class*="st-key-setrow_"] div[data-testid="stHorizontalBlock"] {
    display: grid !important;
    grid-template-columns: 46px minmax(0, 1fr) minmax(0, 1fr) !important;
    gap: 8px !important;
    width: 100% !important;
}
div[class*="st-key-setrow_"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    width: auto !important;
    min-width: 0 !important;
}
</style>
"""


def inject_base_css():
    """모바일 화면에서 버튼/입력창이 넘치지 않게 하는 공통 CSS를 주입한다.

    app.py를 포함한 모든 페이지 스크립트 맨 앞에서 반드시 호출해야 한다
    (Streamlit 멀티페이지는 페이지마다 별도 스크립트라 공유가 안 되기 때문).
    """
    st.markdown(BASE_CSS, unsafe_allow_html=True)


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

        with st.container(key=f"evenrow_logbtns_{entry_id}"):
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
            with st.container(key=f"setrow_edit_{entry_id}_{i}"):
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

        with st.container(key=f"evenrow_logeditbtns_{entry_id}"):
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


def render_history_tab(user: dict):
    """마이페이지의 '기록 히스토리' 탭 전체(날짜별 그룹).

    app.py(내부 탭 방식)와 pages/1_mypage.py(실제 페이지 경로) 양쪽에서 똑같이 호출해서,
    어느 경로로 들어오든 버튼 크기/줄바꿈이 항상 같게 맞춘다.
    """
    logs = db.get_all_logs(user["id"])
    if not logs:
        st.info("아직 기록이 없어요.")
        return

    by_date = {}
    for d in logs:
        by_date.setdefault(d["date"], []).append(d)

    for date_str in sorted(by_date.keys(), reverse=True):
        entries = by_date[date_str]
        with st.expander(f"{date_str} · 운동 {len(entries)}개"):
            for e in entries:
                render_log_entry_editable(user, e)
