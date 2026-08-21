# -*- coding: utf-8 -*-
"""
모바일에서 버튼/입력창이 화면 밖으로 넘어가는 걸 막는 공통 CSS와,
여러 화면(마이페이지 등)에서 재사용되는 UI 조각들을 모아둔 공용 컴포넌트.

app.py는 pages/ 폴더 없이 단일 스크립트 + st.session_state 라우팅 구조이므로,
반드시 inject_base_css()를 app.py 맨 앞에서 한 번만 호출하면 전체 화면에 적용된다.

== 새로운 가로배치(컬럼) 줄을 만들 때 지켜야 하는 규칙 ==
버튼 2개짜리 줄(예: 수정/삭제, 저장/취소)처럼 "여러 요소를 폭 안에서 균등하게 배치"하고
싶으면, 반드시 st.container(key=f"evenrow_...")로 감싸기만 하면 된다. 아래 CSS가
"st-key-evenrow_"로 시작하는 컨테이너는 전부 자동으로 CSS Grid 균등분할 + 버튼 축소를
적용해주기 때문에, 매번 새 CSS 룰을 추가할 필요가 없다.

"N세트 · 무게 · 횟수"처럼 첫 칸은 좁고 나머지 두 칸은 입력창인 줄은
st.container(key=f"setrow_...")로 감싸면 동일하게 자동 처리된다.
"""
import calendar as _calendar
import csv
import datetime as _dt
import io

import streamlit as st

from utils import db
from utils.data import CARDIO_EX_BY_NAME, parse_duration, split_duration, format_duration

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
    overflow: hidden !important;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="column"] * {
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
   가로로 스크롤되지 않게 최종 안전장치.
   (구버전 셀렉터 section.main/.main 뿐 아니라, 최신 Streamlit이 쓰는
   data-testid 기반 셀렉터도 같이 걸어둬야 버전이 올라가도 계속 먹힌다) */
html, body, .stApp,
section.main, .main .block-container, .block-container,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="stBottomBlockContainer"] {
    overflow-x: hidden !important;
    max-width: 100vw !important;
}
* {
    box-sizing: border-box !important;
}
/* 사진(st.image)이 고정 px 폭(width=220 등)으로 지정돼 있어도,
   화면이 그보다 좁아지면 이미지가 컬럼/화면 폭을 뚫고 나가지 않게 한다 */
[data-testid="stImage"] img {
    max-width: 100% !important;
    height: auto !important;
}
/* 문의 내용 / 댓글 / 인증샷 한마디처럼 사용자가 자유롭게 입력한 텍스트는
   공백 없이 긴 문자열(예: 링크, 이어붙인 영단어)이 들어오면 줄바꿈이
   안 돼서 화면 폭을 뚫고 나갈 수 있다. 강제로 단어 중간에서도 줄바꿈되게 처리 */
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
.stCaption, [data-testid="stCaptionContainer"] {
    overflow-wrap: anywhere !important;
    word-break: break-word !important;
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
    overflow: hidden !important;
}
div[class*="st-key-evenrow_"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"] * {
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
/* 상단 네비게이션(오늘/기록/인증/랭킹/문의/관리/로그아웃)처럼 버튼이
   5~7개까지 한 줄 그룹으로 몰릴 수 있는 곳은, 좁은 화면(480px 이하)에서
   한 번 더 줄여서 절대 폭을 넘어가지 않게 여유를 둔다 */
@media (max-width: 480px) {
    div[class*="st-key-evenrow_"] div[data-testid="stHorizontalBlock"] {
        gap: 4px !important;
    }
    div[class*="st-key-evenrow_"] .stButton > button {
        font-size: 10.5px !important;
        padding: 4px 1px !important;
        min-height: 32px !important;
    }
}
@media (max-width: 360px) {
    div[class*="st-key-evenrow_"] div[data-testid="stHorizontalBlock"] {
        gap: 3px !important;
    }
    div[class*="st-key-evenrow_"] .stButton > button {
        font-size: 9.5px !important;
        padding: 3px 0px !important;
        min-height: 30px !important;
    }
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
    overflow: hidden !important;
}
div[class*="st-key-setrow_"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"] * {
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


def render_account_settings(user: dict):
    """마이페이지 '계정 설정' 탭: 닉네임/비밀번호 변경, 회원 탈퇴.

    닉네임은 랭킹/문의 게시판에 조회 시점에 users 컬렉션에서 다시 join해서 표시하므로
    (기록에 닉네임을 박아두지 않음) 여기서 바꿔도 과거 기록/랭킹에 그대로 반영된다.
    """
    st.markdown("**✏️ 닉네임 변경**")
    with st.form("nickname_form"):
        new_nick = st.text_input("새 닉네임", value=user["nickname"], label_visibility="collapsed")
        submitted = st.form_submit_button("닉네임 변경", use_container_width=True)
    if submitted:
        ok, msg = db.change_nickname(user["id"], new_nick)
        if ok:
            st.session_state["user"]["nickname"] = new_nick.strip()
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

    st.markdown("---")
    st.markdown("**🔒 비밀번호 변경**")
    with st.form("password_form"):
        cur_pw = st.text_input("현재 비밀번호", type="password", placeholder="현재 비밀번호")
        new_pw = st.text_input("새 비밀번호", type="password", placeholder="새 비밀번호 (4자 이상)")
        new_pw2 = st.text_input("새 비밀번호 확인", type="password", placeholder="새 비밀번호 확인")
        submitted2 = st.form_submit_button("비밀번호 변경", use_container_width=True)
    if submitted2:
        if new_pw != new_pw2:
            st.error("새 비밀번호가 서로 달라요.")
        else:
            ok, msg = db.change_password(user["id"], cur_pw, new_pw)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.markdown("---")
    st.markdown("**🔑 비밀번호 찾기 설정**")
    st.caption("비밀번호를 잊었을 때 본인 확인에 쓸 질문/답변이에요. 아직 안 정해뒀다면 꼭 설정해두세요.")
    with st.form("security_q_form"):
        q = st.selectbox("보안 질문", db.SECURITY_QUESTIONS, key="sec_q_select")
        a = st.text_input("답변", key="sec_q_answer", placeholder="답변 (대소문자 구분 안 함)")
        submitted3 = st.form_submit_button("보안 질문 저장", use_container_width=True)
    if submitted3:
        ok, msg = db.set_security_question(user["id"], q, a)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

    st.markdown("---")
    st.markdown("**⬇️ 내 기록 CSV 다운로드**")
    logs = db.get_all_logs(user["id"])
    cardio_logs = db.get_all_cardio_logs(user["id"])
    if logs or cardio_logs:
        st.download_button(
            "내 운동 기록 CSV 받기",
            data=build_logs_csv(logs, cardio_logs),
            file_name=f"헬린이루틴_{user['nickname']}_기록.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.caption("아직 다운로드할 기록이 없어요.")

    st.markdown("---")
    st.markdown("**🚪 회원 탈퇴**")
    st.caption("탈퇴하면 내 운동 기록이 모두 삭제되고 되돌릴 수 없어요.")
    pw_for_delete = st.text_input("비밀번호 확인", type="password", key="del_acc_pw", placeholder="비밀번호 확인")

    confirm_key = "confirm_self_delete"
    if st.session_state.get(confirm_key):
        if st.button("정말 탈퇴할까요? (되돌릴 수 없어요)", key="final_self_delete", type="primary", use_container_width=True):
            ok, msg = db.delete_own_account(user["id"], pw_for_delete)
            if ok:
                st.session_state.pop(confirm_key, None)
                del st.session_state["user"]
                st.session_state.pop("page", None)
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
        if st.button("취소", key="cancel_self_delete", use_container_width=True):
            st.session_state.pop(confirm_key, None)
            st.rerun()
    else:
        if st.button("회원 탈퇴", key="start_self_delete", use_container_width=True):
            if not pw_for_delete:
                st.error("비밀번호를 입력해주세요.")
            else:
                st.session_state[confirm_key] = True
                st.rerun()


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
                ok, err = db.validate_sets(new_sets)
                if not ok:
                    st.error(err)
                else:
                    db.save_exercise_log(user["id"], e["date"], e["exercise_name"], new_sets, memo_val)
                    st.session_state[edit_key] = False
                    st.toast(f"{e['exercise_name']} 수정 완료!", icon="✅")
                    st.rerun()
            if c2.button("취소", key=f"cancel_{entry_id}", use_container_width=True):
                st.session_state[edit_key] = False
                st.rerun()

    st.markdown("---")


def render_cardio_log_entry_editable(user: dict, c: dict):
    """마이페이지 '기록 히스토리'의 유산소 기록 한 줄. 근력과 동일하게 그 자리에서 수정/삭제 가능."""
    entry_id = str(c["_id"])
    edit_key = f"editing_cardio_{entry_id}"
    editing = st.session_state.get(edit_key, False)
    ex_def = CARDIO_EX_BY_NAME.get(c["exercise_name"], {})
    has_distance = ex_def.get("has_distance", False)
    icon = ex_def.get("icon", "🏃")

    if not editing:
        bits = [format_duration(c.get("duration_min"))]
        if c.get("distance_km") not in (None, ""):
            bits.append(f"{c['distance_km']}km")
        if c.get("calories") not in (None, ""):
            bits.append(f"{c['calories']}kcal")
        st.markdown(f"**{icon} {c['exercise_name']}**  \n{' / '.join(bits)}")
        if c.get("memo"):
            st.caption(f"메모: {c['memo']}")

        with st.container(key=f"evenrow_cardiobtns_{entry_id}"):
            b1, b2 = st.columns(2)
            if b1.button("✏️ 수정", key=f"cedit_{entry_id}", use_container_width=True):
                st.session_state[edit_key] = True
                st.rerun()
            if b2.button("🗑️ 삭제", key=f"cdel_{entry_id}", use_container_width=True):
                db.delete_cardio_log(user["id"], c["date"], c["exercise_name"])
                st.rerun()
    else:
        st.markdown(f"**{icon} {c['exercise_name']}** 수정 중")

        min_val, sec_val = split_duration(c.get("duration_min"))
        with st.container(key=f"evenrow_cardioedit_{entry_id}"):
            cols = st.columns(3 if has_distance else 2)
            new_min = cols[0].text_input(
                "분", value=min_val, key=f"cedit_min_{entry_id}",
                label_visibility="collapsed", placeholder="분",
            )
            new_sec = cols[1].text_input(
                "초", value=sec_val, key=f"cedit_sec_{entry_id}",
                label_visibility="collapsed", placeholder="초",
            )
            dist_val = ""
            if has_distance:
                dist_val = cols[2].text_input(
                    "거리(km)", value=str(c.get("distance_km") or ""), key=f"cedit_dist_{entry_id}",
                    label_visibility="collapsed", placeholder="거리(km)",
                )

        cal_val = st.text_input(
            "칼로리(선택)", value=str(c.get("calories") or ""), key=f"cedit_cal_{entry_id}",
            placeholder="칼로리(선택, kcal)",
        )
        memo_val = st.text_input("메모", value=c.get("memo", ""), key=f"cedit_memo_{entry_id}")

        with st.container(key=f"evenrow_cardioeditbtns_{entry_id}"):
            b1, b2 = st.columns(2)
            if b1.button("💾 저장", key=f"csave_{entry_id}", use_container_width=True, type="primary"):
                dur_val, dur_err = parse_duration(new_min, new_sec)
                if dur_err:
                    st.error(dur_err)
                else:
                    ok, err = db.validate_cardio_log(dur_val, dist_val if has_distance else None, cal_val)
                    if not ok:
                        st.error(err)
                    else:
                        db.save_cardio_log(
                            user["id"], c["date"], c["exercise_name"],
                            dur_val, dist_val if has_distance else None, cal_val, memo_val,
                        )
                        st.session_state[edit_key] = False
                        st.toast(f"{c['exercise_name']} 수정 완료!", icon="✅")
                        st.rerun()
            if b2.button("취소", key=f"ccancel_{entry_id}", use_container_width=True):
                st.session_state[edit_key] = False
                st.rerun()

    st.markdown("---")


def build_logs_csv(logs: list, cardio_logs: list = None) -> str:
    """기록 리스트를 CSV 문자열로 변환 (엑셀에서 바로 열리도록 UTF-8 BOM 포함).
    근력/유산소 기록을 한 파일에 같이 담되, '종류' 컬럼으로 구분한다."""
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(["날짜", "종류", "운동", "세트/시간(분)", "무게(kg)/거리(km)", "횟수/칼로리(kcal)", "메모"])
    for d in logs:
        valid = [s for s in d["sets"] if s.get("w") not in (None, "") and s.get("r") not in (None, "")]
        if not valid:
            writer.writerow([d["date"], "근력", d["exercise_name"], "", "", "", d.get("memo", "")])
            continue
        for i, s in enumerate(valid, start=1):
            writer.writerow([
                d["date"], "근력", d["exercise_name"], i, s.get("w", ""), s.get("r", ""),
                d.get("memo", "") if i == 1 else "",
            ])
    for d in cardio_logs or []:
        writer.writerow([
            d["date"], "유산소", d["exercise_name"], d.get("duration_min", ""),
            d.get("distance_km", "") or "", d.get("calories", "") or "", d.get("memo", ""),
        ])
    return buf.getvalue()


def render_streak_heatmap(workout_dates: set):
    """운동 기록을 진짜 달력(이번 달)처럼 보여준다. 기록 남긴 날은 민트색으로 색칠,
    오늘 날짜엔 노란 테두리를 둘러서 한눈에 봐도 '몇일에 뭐 했는지'가 바로 보이게 한다.
    (예전 깃허브 잔디밭 스타일 그리드는 모바일 좁은 화면에서 옆으로 스크롤해야만
    최근 며칠이 보이는 구조라 뭘 나타내는지 애매했음 → 스크롤 없이 한 화면에 다 보이는
    7칸(월~일) 달력으로 교체)"""
    today = _dt.date.today()
    year, month = today.year, today.month
    cal = _calendar.Calendar(firstweekday=0)  # 월요일 시작
    weeks = cal.monthdatescalendar(year, month)

    day_labels = ["월", "화", "수", "목", "금", "토", "일"]
    grid = (
        "<div style='display:grid; grid-template-columns:repeat(7, minmax(0, 1fr)); "
        "gap:4px; margin-bottom:4px;'>"
    )
    for lbl in day_labels:
        grid += (
            f"<div style='text-align:center; font-size:10.5px; color:#6B6F78; "
            f"font-weight:600;'>{lbl}</div>"
        )
    grid += "</div>"

    for week in weeks:
        grid += (
            "<div style='display:grid; grid-template-columns:repeat(7, minmax(0, 1fr)); "
            "gap:4px; margin-bottom:4px;'>"
        )
        for d in week:
            in_month = d.month == month
            active = d.isoformat() in workout_dates
            is_today = d == today
            if not in_month:
                bg, txt_color, opacity = "transparent", "#4B4F58", "0.4"
            elif active:
                bg, txt_color, opacity = "#4ECDC4", "#101214", "1"
            else:
                bg, txt_color, opacity = "#23262C", "#9296A0", "1"
            border = "box-shadow:inset 0 0 0 1.5px #FFC834;" if (is_today and in_month) else ""
            grid += (
                f"<div title='{d.isoformat()}' style='aspect-ratio:1; display:flex; "
                f"align-items:center; justify-content:center; border-radius:7px; "
                f"background:{bg}; color:{txt_color}; opacity:{opacity}; {border} "
                f"font-size:11.5px; font-weight:600;'>{d.day}</div>"
            )
        grid += "</div>"

    st.markdown(grid, unsafe_allow_html=True)
    st.caption(f"📅 {month}월 운동 달력이에요. 민트색 칸이 그날 기록을 남긴 날, 노란 테두리는 오늘이에요.")


def render_badges(badges: list):
    """뱃지 목록을 카드 그리드로 렌더링 (달성 여부에 따라 색 다르게)."""
    with st.container(key="evenrow_badges"):
        cols = st.columns(3)
        for i, b in enumerate(badges):
            with cols[i % 3]:
                if b["achieved"]:
                    bg, border, opacity = "#1E241E", "#4ECDC4", "1"
                else:
                    bg, border, opacity = "#1B1D22", "#33373F", "0.45"
                st.markdown(
                    f"<div style='background:{bg}; border:1px solid {border}; border-radius:12px; "
                    f"padding:10px 6px; text-align:center; margin-bottom:8px; opacity:{opacity}; "
                    f"overflow:hidden;'>"
                    f"<div style='font-size:22px;'>{b['icon']}</div>"
                    f"<div style='font-size:12px; font-weight:700; color:#F2F1EC; margin-top:2px; "
                    f"overflow-wrap:break-word; word-break:break-word;'>{b['name']}</div>"
                    f"<div style='font-size:10px; color:#9296A0; overflow-wrap:break-word; word-break:break-word;'>{b['need']}</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )


def render_history_tab(user: dict):
    """마이페이지의 '기록 히스토리' 탭 전체(날짜별 그룹).

    app.py(내부 탭 방식)와 pages/1_mypage.py(실제 페이지 경로) 양쪽에서 똑같이 호출해서,
    어느 경로로 들어오든 버튼 크기/줄바꿈이 항상 같게 맞춘다.
    """
    logs = db.get_all_logs(user["id"])
    cardio_logs = db.get_all_cardio_logs(user["id"])
    if not logs and not cardio_logs:
        st.info("아직 기록이 없어요.")
        return

    by_date = {}
    for d in logs:
        by_date.setdefault(d["date"], {"strength": [], "cardio": []})["strength"].append(d)
    for d in cardio_logs:
        by_date.setdefault(d["date"], {"strength": [], "cardio": []})["cardio"].append(d)

    for date_str in sorted(by_date.keys(), reverse=True):
        entries = by_date[date_str]
        total_count = len(entries["strength"]) + len(entries["cardio"])
        with st.expander(f"{date_str} · 운동 {total_count}개"):
            render_card_download_button(user, date_str)
            for e in entries["strength"]:
                render_log_entry_editable(user, e)
            for c in entries["cardio"]:
                render_cardio_log_entry_editable(user, c)


def render_card_download_button(user: dict, date_str: str):
    """그 날짜의 기록을 예쁜 인스타 스토리용 PNG 카드로 만들어 다운로드하는 버튼."""
    from utils import card as _card

    cache_key = f"card_png_{user['id']}_{date_str}"
    if st.button("🎴 오운완 인증카드 만들기", key=f"makecard_{date_str}", use_container_width=True):
        rows, total_volume = db.get_date_summary(user["id"], date_str)
        stats = db.get_user_stats(user["id"], date_str)
        png_bytes = _card.generate_workout_card(
            user["nickname"], date_str, rows, total_volume, stats["streak"]
        )
        st.session_state[cache_key] = png_bytes

    if st.session_state.get(cache_key):
        st.image(st.session_state[cache_key], width=200)
        st.download_button(
            "⬇️ 카드 이미지 다운로드",
            data=st.session_state[cache_key],
            file_name=f"헬린이루틴_오운완_{date_str}.png",
            mime="image/png",
            key=f"dlcard_{date_str}",
            use_container_width=True,
        )
    st.markdown("---")
