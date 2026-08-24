# -*- coding: utf-8 -*-
"""
헬린이 루틴 - 메인 엔트리 파일 (Streamlit 앱의 시작점).

이 앱은 서로 다른 화면(오늘의 루틴 / 마이페이지 / 랭킹 / 문의 / 관리자 / 게시판)을
별도의 pages/*.py 파일로 나누지 않고, 이 파일 하나에서 st.session_state["page"] 값에 따라
render_xxx() 함수를 골라 호출하는 방식(SPA처럼 동작)으로 화면을 전환한다.
자세한 이유는 README의 "화면 이동 방식" 섹션 참고.

파일 구성:
  1) KST 시간 처리 (today_kst)
  2) 휴식 타이머 위젯 (render_rest_timer) - 순수 HTML/JS 컴포넌트
  3) 커스텀 CSS 주입
  4) 로그인/회원가입 화면 (render_auth)
  5) 상단 네비게이션 (render_topnav)
  6) 오늘의 루틴 - 근력/유산소 (render_today, render_cardio_today)
  7) 마이페이지 (render_mypage)
  8) 랭킹 (render_ranking)
  9) 문의하기 (render_contact)
  10) 관리자 페이지 (render_admin)
  11) 게시판 - 자유/운동/정보/인증샷 (render_board)
  12) 파일 맨 아래: 실제 라우팅(현재 로그인 여부·페이지 값에 따라 위 함수 중 하나를 호출)

실제 데이터베이스 로직은 utils/db.py, 화면 조각 UI는 utils/ui.py,
운동 종류/부위 데이터는 utils/data.py, 인증샷 카드 이미지 생성은 utils/card.py에 있다.
"""
import base64
import datetime as dt
import random

import streamlit as st
import streamlit.components.v1 as components

from utils import db
from utils import ui
from utils import card
from utils import features_ui
from utils.data import (
    PARTS,
    EX_BY_NAME,
    alt_exercises_for,
    random_exercise_for_part,
    get_tier,
    ALL_EXERCISE_NAMES,
    UPDATE_LOG,
    CARDIO_EXERCISES,
    CARDIO_EX_BY_NAME,
    CARDIO_NOTE,
    format_pace,
    parse_duration,
    split_duration,
    format_duration,
)

# Streamlit Cloud 서버는 UTC 기준으로 동작하므로 dt.date.today()를 그대로 쓰면
# 한국시간(UTC+9) 새벽 0~9시 사이에는 아직 "어제" 날짜가 반환된다.
# 항상 한국시간(KST) 기준 오늘 날짜를 쓰도록 고정한다.
KST = dt.timezone(dt.timedelta(hours=9))


def today_kst() -> dt.date:
    """KST(한국시간, UTC+9) 기준 오늘 날짜를 반환한다. Streamlit Cloud 서버가 UTC로 동작하므로 이 함수를 통해서만 '오늘'을 구한다."""
    return dt.datetime.now(KST).date()

st.set_page_config(page_title="헬린이 루틴", page_icon="🏋️", layout="centered")

ui.inject_base_css()

# 사이드바(메뉴 버튼을 화면 안에서 쓰므로 사이드바 자체를 숨긴다)
st.markdown(
    """
    <style>
    [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

PART_COLORS = {
    "PART1": "#FF9F5A",
    "PART2": "#5AA9FF",
    "PART3": "#FF5A9F",
    "PART4": "#B15AFF",
    "PART5": "#5AFF9F",
    "PART6": "#FFC834",
}
CARDIO_COLOR = "#4ECDC4"


def render_rest_timer():
    """60/90/120초 휴식 타이머. 버튼 클릭도 이 위젯 안에서 순수 JS로 처리되므로
    Streamlit 새로고침 없이 그 자리에서 바로 카운트다운된다 (원본 HTML의 타이머와 동일 동작).

    개선: 종료 시각(endTime)을 localStorage에 저장해두기 때문에, 다른 운동을 저장하는 등
    화면이 다시 그려져서 이 위젯이 새로 로드되더라도(예전엔 여기서 타이머가 0으로 리셋됐음)
    남은 시간을 그대로 이어서 보여준다. 페이지 전체에서 하나만 렌더링해서 쓰는 공용 위젯이다."""
    html = """
    <style>
      body{margin:0;padding:0;background:transparent;font-family:'Inter',sans-serif;}
      .rt-row{display:flex; gap:8px; margin:4px 0;}
      .rt-btn{
        flex:1; min-width:0; background:#23262C; border:1px solid #33373F; color:#F2F1EC;
        font-family:'JetBrains Mono',monospace; font-size:12px; font-weight:600;
        padding:10px 2px; border-radius:8px; cursor:pointer;
      }
      .rt-btn:active{background:#2B2F36;}
      .rt-bar{display:none; margin-top:6px;}
      .rt-bar.show{display:block;}
      .rt-inner{
        background:#23262C; border:1px solid #FFC834; border-radius:999px;
        padding:8px 10px 8px 14px; display:flex; align-items:center; gap:8px;
      }
      .rt-time{font-family:'JetBrains Mono',monospace; font-weight:700; color:#FFC834; font-size:14px; min-width:38px;}
      .rt-track{flex:1; height:5px; border-radius:99px; background:#2B2F36; overflow:hidden;}
      .rt-fill{height:100%; background:#FFC834; border-radius:99px; width:100%; transition:width 1s linear;}
      .rt-round{
        width:26px; height:26px; border-radius:50%; border:none; background:#2B2F36; color:#F2F1EC;
        display:flex; align-items:center; justify-content:center; cursor:pointer; font-size:12px; flex-shrink:0;
      }
      .rt-msg{text-align:center; font-size:12px; color:#B9E6B9; margin-top:4px; min-height:14px;}
    </style>
    <div class="rt-row">
      <button class="rt-btn" data-rest="60">⏱ 60초 휴식</button>
      <button class="rt-btn" data-rest="90">⏱ 90초 휴식</button>
      <button class="rt-btn" data-rest="120">⏱ 120초 휴식</button>
    </div>
    <div class="rt-bar" id="restBar">
      <div class="rt-inner">
        <button class="rt-round" id="restMinus">-15</button>
        <div class="rt-time" id="restTime">0:00</div>
        <div class="rt-track"><div class="rt-fill" id="restFill"></div></div>
        <button class="rt-round" id="restPlus">+15</button>
        <button class="rt-round" id="restStop">×</button>
      </div>
      <div class="rt-msg" id="restMsg"></div>
    </div>
    <script>
      // endTime(목표 종료 시각)과 total(총 초)을 localStorage에 저장해서, 이 위젯이
      // 새로고침(다른 운동 저장 등)으로 다시 그려져도 남은 시간을 이어서 보여준다.
      const LS_END = 'hellini_rest_end';
      const LS_TOTAL = 'hellini_rest_total';
      const restTimer = {total:0, interval:null};

      document.querySelectorAll('[data-rest]').forEach(function(btn){
        btn.addEventListener('click', function(){ startRest(parseInt(btn.dataset.rest)); });
      });

      function startRest(seconds){
        const endTime = Date.now() + seconds*1000;
        try{
          localStorage.setItem(LS_END, String(endTime));
          localStorage.setItem(LS_TOTAL, String(seconds));
        }catch(e){}
        restTimer.total = seconds;
        document.getElementById('restBar').classList.add('show');
        document.getElementById('restMsg').textContent = '';
        tick();
        clearInterval(restTimer.interval);
        restTimer.interval = setInterval(tick, 1000);
      }

      function remainingSeconds(){
        let end = 0;
        try{ end = parseInt(localStorage.getItem(LS_END) || '0'); }catch(e){}
        return Math.max(0, Math.round((end - Date.now())/1000));
      }

      function tick(){
        const remaining = remainingSeconds();
        updateUI(remaining);
        if(remaining <= 0){
          clearInterval(restTimer.interval);
          onDone();
        }
      }

      function updateUI(remaining){
        const m = Math.floor(remaining/60);
        const s = remaining%60;
        document.getElementById('restTime').textContent = m+':'+String(s).padStart(2,'0');
        const pct = restTimer.total>0 ? Math.max(0, remaining/restTimer.total*100) : 0;
        document.getElementById('restFill').style.width = pct+'%';
      }

      function stopRest(){
        clearInterval(restTimer.interval);
        try{ localStorage.removeItem(LS_END); localStorage.removeItem(LS_TOTAL); }catch(e){}
        document.getElementById('restBar').classList.remove('show');
      }

      function adjustRest(delta){
        if(restTimer.total<=0) return;
        let end = 0;
        try{ end = parseInt(localStorage.getItem(LS_END) || '0'); }catch(e){}
        end += delta*1000;
        const newRemaining = Math.max(0, Math.round((end - Date.now())/1000));
        if(newRemaining > restTimer.total) restTimer.total = newRemaining;
        try{ localStorage.setItem(LS_END, String(end)); localStorage.setItem(LS_TOTAL, String(restTimer.total)); }catch(e){}
        updateUI(newRemaining);
      }

      function onDone(){
        document.getElementById('restMsg').textContent = '휴식 끝! 다음 세트 가보자 💪';
        if(navigator.vibrate) navigator.vibrate([200,100,200]);
        beep();
        setTimeout(stopRest, 2500);
      }

      function beep(){
        try{
          const ctx = new (window.AudioContext||window.webkitAudioContext)();
          const o = ctx.createOscillator();
          const g = ctx.createGain();
          o.type='sine'; o.frequency.value=880;
          o.connect(g); g.connect(ctx.destination);
          g.gain.setValueAtTime(0.0001, ctx.currentTime);
          g.gain.exponentialRampToValueAtTime(0.35, ctx.currentTime+0.02);
          g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime+0.6);
          o.start(); o.stop(ctx.currentTime+0.6);
        }catch(e){}
      }

      document.getElementById('restMinus').addEventListener('click', function(){ adjustRest(-15); });
      document.getElementById('restPlus').addEventListener('click', function(){ adjustRest(15); });
      document.getElementById('restStop').addEventListener('click', stopRest);

      // 위젯이 (다시) 로드됐을 때, 진행 중이던 타이머가 있으면 그대로 이어서 표시
      (function resumeIfActive(){
        let total = 0;
        try{ total = parseInt(localStorage.getItem(LS_TOTAL) || '0'); }catch(e){}
        const remaining = remainingSeconds();
        if(total > 0 && remaining > 0){
          restTimer.total = total;
          document.getElementById('restBar').classList.add('show');
          updateUI(remaining);
          restTimer.interval = setInterval(tick, 1000);
        }
      })();
    </script>
    """
    components.html(html, height=150, scrolling=False)

# ================= 커스텀 스타일 (원본 HTML 다크 테마 톤 맞춤) =================
st.markdown(
    """
    <style>
    .stApp { background-color: #121316; }

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

    .part-badge {
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

    .exercise-thumb {
        width: 100%;
        max-width: 220px;
        border-radius: 12px;
        margin-bottom: 8px;
    }

    /* ===== 이 페이지 전용 요소들의 모바일 폰트/여백 축소 ===== */
    @media (max-width: 480px) {
        .progress-chip { font-size: 11px; padding: 3px 9px; }
        .part-badge { font-size: 10.5px; padding: 2px 8px; }
        .exercise-thumb { max-width: 100%; }
    }
    /* st.metric (연속기록/총기록일/총볼륨, 관리자 대시보드 등) 좁은 화면에서 글자가
       칸을 넘어가거나 줄바꿈으로 어색해지는 것 방지 */
    div[data-testid="stMetric"] {
        background: #1B1D22;
        border: 1px solid #33373F;
        border-radius: 10px;
        padding: 8px 4px;
        text-align: center;
    }
    div[data-testid="stMetricLabel"] { justify-content: center; }
    div[data-testid="stMetricLabel"] p { font-size: 12px !important; white-space: normal !important; }
    div[data-testid="stMetricValue"] {
        justify-content: center;
        white-space: normal !important;
        overflow-wrap: anywhere !important;
        line-height: 1.15 !important;
    }
    @media (max-width: 480px) {
        div[data-testid="stMetricValue"] { font-size: 16px !important; }
        div[data-testid="stMetricLabel"] p { font-size: 10px !important; }
        div[data-testid="stMetric"] { padding: 6px 1px; }
    }
    @media (max-width: 360px) {
        div[data-testid="stMetricValue"] { font-size: 13.5px !important; }
        div[data-testid="stMetricLabel"] p { font-size: 9px !important; }
        div[data-testid="stMetric"] { padding: 4px 1px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def _init_once():
    """세션 최초 진입 시 한 번만 필요한 초기화(접속 현황 기록 등)를 처리한다."""
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
    """로그인 / 회원가입 / 비밀번호 찾기 화면을 그린다. 로그인에 성공하면 st.session_state['user']에 사용자 정보를 저장한다."""
    st.markdown("### 🏋️ 헬린이 루틴")
    st.caption("로그인하고 내 운동 기록을 저장해보세요.")

    tab_login, tab_signup, tab_forgot = st.tabs(["로그인", "회원가입", "비밀번호 찾기"])

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
                st.session_state["page"] = "today"
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 일치하지 않아요.")

    with tab_signup:
        with st.form("signup_form"):
            new_username = st.text_input("아이디", key="su_username")
            new_nickname = st.text_input("닉네임 (랭킹에 표시돼요)", key="su_nickname")
            new_password = st.text_input("비밀번호", type="password", key="su_password")
            new_password2 = st.text_input("비밀번호 확인", type="password", key="su_password2")
            st.markdown("**비밀번호를 잊었을 때 본인 확인용 질문이에요.**")
            new_question = st.selectbox("보안 질문", db.SECURITY_QUESTIONS, key="su_question")
            new_answer = st.text_input("답변", key="su_answer", placeholder="답변 (대소문자 구분 안 함)")
            submitted2 = st.form_submit_button("회원가입", use_container_width=True)
        if submitted2:
            if new_password != new_password2:
                st.error("비밀번호가 서로 달라요.")
            elif not new_answer.strip():
                st.error("보안 질문 답변을 입력해주세요.")
            else:
                ok, msg = db.create_user(
                    new_username, new_password, new_nickname, new_question, new_answer
                )
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    with tab_forgot:
        st.caption("아이디를 입력하면 가입할 때 설정한 보안 질문이 나와요.")
        forgot_username = st.text_input("아이디", key="forgot_username")
        question = db.get_security_question(forgot_username) if forgot_username.strip() else None

        if forgot_username.strip() and not question:
            st.info("보안 질문이 없거나 아직 등록하지 않은 계정이에요. 운영자에게 문의해주세요.")
        elif question:
            with st.form("forgot_form"):
                st.markdown(f"**Q. {question}**")
                answer = st.text_input("답변", key="forgot_answer")
                new_pw = st.text_input("새 비밀번호", type="password", key="forgot_new_pw")
                new_pw2 = st.text_input("새 비밀번호 확인", type="password", key="forgot_new_pw2")
                submitted3 = st.form_submit_button("비밀번호 재설정", use_container_width=True)
            if submitted3:
                if new_pw != new_pw2:
                    st.error("새 비밀번호가 서로 달라요.")
                else:
                    ok, msg = db.reset_password_with_security(forgot_username, answer, new_pw)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)


# ================= 상단 네비게이션 (버튼식) =================
# ================= 상단 네비게이션 (버튼식) =================
NAV_PAGES = [
    ("today", "🏠 오늘"),
    ("routines", "🧩 루틴"),
    ("mypage", "📖 기록"),
    ("board", "📋 게시판"),
    ("ranking", "🏆 랭킹"),
    ("contact", "💬 문의"),
]

def render_topnav(user: dict, admin: bool) -> str:
    """화면 상단의 페이지 이동 버튼(오늘 / 기록 / 랭킹 / 문의 / 관리)을 그리고, 사용자가 클릭한 버튼에 해당하는 페이지 키를 반환한다."""
    db.touch_presence(user["id"], user["username"], user["nickname"])

    # 1. 페이지 목록 마지막에 로그아웃을 추가합니다.
    pages = NAV_PAGES + ([("admin", "🛠️ 관리")] if admin else [])
    pages.append(("logout", "로그아웃")) 
    
    current = st.session_state.get("page", "today")

    chunk = 3
    for i in range(0, len(pages), chunk):
        row = pages[i : i + chunk]
        with st.container(key=f"evenrow_nav_{i}"):
            cols = st.columns(len(row))
            for col, (key, label) in zip(cols, row):
                # 2. 키값이 logout일 때만 삭제 로직을 실행하도록 분기 처리합니다.
                if key == "logout":
                    if col.button(label, key="nav_logout", use_container_width=True):
                        del st.session_state["user"]
                        st.session_state.pop("page", None)
                        st.rerun()
                else:
                    btn_type = "primary" if key == current else "secondary"
                    if col.button(label, key=f"nav_{key}", use_container_width=True, type=btn_type):
                        st.session_state["page"] = key
                        st.rerun()

    # 3. 버튼을 밀어내던 안내 문구는 가장 아래에 단독으로 넓게 배치합니다.
    total = db.get_total_user_count()
    active = db.get_active_user_count()
    stats = db.get_user_stats(user["id"], today_kst().isoformat())
    st.session_state["_header_stats"] = stats
    streak_txt = f" · 🔥 연속 {stats['streak']}일" if stats["streak"] > 0 else ""
    tier = get_tier(stats["workout_days"])
    tier_txt = f" · {tier['icon']} {tier['name']}"
    admin_tag = " · 🛡️ 관리자" if admin else ""
    st.caption(f"👋 {user['nickname']}님{admin_tag}{tier_txt} · 👥 총 가입자 {total}명 · 🟢 현재 접속 {active}명{streak_txt}")

    st.divider()
    return current

# ================= 오늘 뭐 할지 정하기 (퀵스타트) =================
def render_quick_start(user: dict):
    """운동 가는 길 / 웜업·스트레칭 중에 '오늘 뭐 하지' 고민을 풀어주는 칸.
    1) 직접 원하는 운동만 골라서 '오늘의 운동'으로 좁혀보기
    2) 부위만 고르면 그 부위 안에서 하나를 무작위로 추천 + 방법 설명
    선택 결과는 st.session_state["quick_pick"]에 저장되고, 아래 부위 탭에서
    '선택한 운동만 보기'를 켜면 그 운동들만 걸러서 보여준다."""
    st.session_state.setdefault("quick_pick", [])
    st.session_state.setdefault("quick_filter_on", False)
    available_exercise_names = [item["name"] for item in db.get_exercise_catalog(user["id"])]
    valid_quick_pick = [name for name in st.session_state["quick_pick"] if name in available_exercise_names]

    with st.expander("🎯 오늘 뭐 할지 아직 못 정했다면 (가는 길 / 웜업 중 추천)", expanded=False):
        mode = st.radio(
            "방법 선택", ["✅ 내가 직접 고르기", "🎲 부위 골라서 무작위 추천받기"],
            key="quick_mode", horizontal=False, label_visibility="collapsed",
        )

        if mode == "✅ 내가 직접 고르기":
            st.caption("오늘 할 운동만 체크하면, 아래 부위 탭에서 그 운동들만 골라서 보여줘요.")
            picked = st.multiselect(
                "오늘 할 운동", available_exercise_names,
                default=valid_quick_pick, key="quick_multiselect",
            )
            with st.container(key="evenrow_quickpick_btns"):
                c1, c2 = st.columns(2)
                if c1.button("이 운동들로 오늘 루틴 만들기", key="quick_apply", use_container_width=True, type="primary"):
                    st.session_state["quick_pick"] = picked
                    st.session_state["quick_filter_on"] = True
                    st.toast(f"{len(picked)}개 운동으로 오늘의 루틴을 만들었어요!", icon="🎯")
                    st.rerun()
                if c2.button("전체 다시 보기", key="quick_reset", use_container_width=True):
                    st.session_state["quick_pick"] = []
                    st.session_state["quick_filter_on"] = False
                    st.rerun()
        else:
            st.caption("부위만 고르면 그 안에서 하나를 무작위로 뽑아서 방법까지 설명해드려요.")
            part_labels = {f"{p['label']} · {p['part']}": p["key"] for p in PARTS}
            picked_label = st.selectbox("부위 선택", list(part_labels.keys()), key="quick_part_select")
            part_key = part_labels[picked_label]

            if st.button("🎲 랜덤 추천받기", key="quick_recommend_btn", use_container_width=True):
                rec = random_exercise_for_part(part_key)
                st.session_state["quick_recommend"] = rec["name"] if rec else None
                st.rerun()

            rec_name = st.session_state.get("quick_recommend")
            rec_ex = EX_BY_NAME.get(rec_name) if rec_name else None
            if rec_ex:
                color = PART_COLORS.get(rec_ex["part"], "#FFC834")
                st.markdown(
                    f"<div style='background:#1B1D22; border:1px solid {color}; border-radius:12px; "
                    f"padding:12px; margin-top:8px;'>"
                    f"<div class='part-badge' style='background:{color};'>오늘의 추천</div>"
                    f"<div style='font-size:16px; font-weight:800; color:#F2F1EC;'>{rec_ex['name']}</div>"
                    f"<div class='equip-line'>🎯 {rec_ex['sets']}세트 · {rec_ex['reps']}</div>"
                    f"<div class='equip-line'>🛠️ {rec_ex['equip']}</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )
                if rec_ex.get("howto"):
                    steps_md = "\n".join(f"{i+1}. {s}" for i, s in enumerate(rec_ex["howto"]))
                    st.markdown(steps_md)
                if rec_ex.get("caution"):
                    st.markdown(
                        f"<div class='caution-box'>⚠️ <b>주의사항</b><br>{rec_ex['caution']}</div>",
                        unsafe_allow_html=True,
                    )
                if rec_ex.get("tip"):
                    st.markdown(
                        f"<div class='tip-box'>💡 <b>팁</b><br>{rec_ex['tip']}</div>",
                        unsafe_allow_html=True,
                    )
                with st.container(key="evenrow_quickrec_btns"):
                    rc1, rc2 = st.columns(2)
                    if rc1.button("🔁 다른 운동 추천", key="quick_recommend_again", use_container_width=True):
                        rec = random_exercise_for_part(part_key)
                        st.session_state["quick_recommend"] = rec["name"] if rec else None
                        st.rerun()
                    if rc2.button("➕ 오늘 운동에 추가", key="quick_recommend_add", use_container_width=True, type="primary"):
                        if rec_ex["name"] not in st.session_state["quick_pick"]:
                            st.session_state["quick_pick"] = st.session_state["quick_pick"] + [rec_ex["name"]]
                        st.session_state["quick_filter_on"] = True
                        st.toast(f"{rec_ex['name']}을(를) 오늘의 루틴에 추가했어요!", icon="✅")
                        st.rerun()

    if st.session_state["quick_pick"]:
        names_txt = ", ".join(st.session_state["quick_pick"])
        st.markdown(
            f"<div class='tip-box'>🎯 <b>오늘의 선택 운동</b> ({len(st.session_state['quick_pick'])}개)<br>{names_txt}</div>",
            unsafe_allow_html=True,
        )
        st.session_state["quick_filter_on"] = st.toggle(
            "✅ 선택한 운동만 보기 (끄면 부위 전체 다시 보여요)",
            value=st.session_state["quick_filter_on"], key="quick_filter_toggle",
        )


# ================= 오늘의 루틴 =================
def render_today(user: dict):
    """'오늘의 루틴' 페이지. 날짜·부위 선택, 운동별 세트 입력 및 저장, 휴식 타이머, 오늘 인증 현황을 렌더링한다."""
    selected_date = st.date_input("날짜", value=today_kst(), key="today_date")
    date_str = selected_date.isoformat()

    st.markdown(
        "<div style='background:#1B1D22; border:1px solid #33373F; border-radius:8px; "
        "padding:10px 12px; font-size:12.5px; color:#9296A0; margin:10px 0 18px;'>"
        "✓ 모든 무게는 마지막 2~3개가 <b style='color:#FFC834;'>매우 힘들 정도</b>로 진행하세요. "
        "주 6회가 힘들면 부위 순서(사이클)만 지켜서 따라하면 됩니다."
        "</div>",
        unsafe_allow_html=True,
    )

    features_ui.render_today_routine_launcher(user, date_str)

    log_for_date = db.get_log_for_date(user["id"], date_str)
    pr_map = db.get_personal_records(user["id"])
    merged_catalog = db.get_exercise_catalog(user["id"], include_inactive=True)
    exercises_by_part = {
        part["key"]: db.get_exercises_for_part_catalog(user["id"], part["key"], merged_catalog)
        for part in PARTS
    }

    # ---- 이 날짜의 전체(부위 1~6 합산) 진행 요약 ----
    total_all, done_all = 0, 0
    for part in PARTS:
        for ex in exercises_by_part[part["key"]]:
            total_all += 1
            existing = log_for_date.get(ex["name"])
            sets_state = existing["sets"] if existing else [{"w": "", "r": ""} for _ in range(ex["sets"])]
            if existing is not None and all(
                s.get("w") not in (None, "") and s.get("r") not in (None, "") for s in sets_state
            ):
                done_all += 1
    overall_class = "progress-chip done" if total_all and done_all == total_all else "progress-chip"
    st.markdown(
        f"<div style='text-align:center; margin-bottom:10px;'>"
        f"<span class='{overall_class}'>이 날짜 전체 {done_all}/{total_all} 완료</span></div>",
        unsafe_allow_html=True,
    )

    st.caption("⏱ 휴식 타이머는 이제 각 운동의 '세트 기록' 칸 바로 위에 있어요 (스크롤해서 위로 안 올라와도 돼요)")

    render_quick_start(user)

    with st.expander(f"🔥 {date_str} 인증 현황 (누가 오늘 운동했나 보기)"):
        checkins = db.get_today_checkins(date_str, len(ALL_EXERCISE_NAMES))
        if not checkins:
            st.caption("아직 이 날짜에 기록을 남긴 사람이 없어요. 첫 인증을 남겨보세요!")
        else:
            for c in checkins:
                mine = " 👈 나" if c["nickname"] == user["nickname"] else ""
                st.markdown(f"💪 **{c['nickname']}**{mine} · {c['done_count']}종목 기록")

    with st.expander("🆕 업데이트 현황 (뭐가 바뀌었는지 보기)"):
        for log in UPDATE_LOG:
            st.markdown(f"**{log['date']}**")
            for item in log["items"]:
                st.markdown(f"- {item}")
            st.markdown("")

    part_by_key = {part["key"]: part for part in PARTS}
    section_options = list(part_by_key) + ["CARDIO"]
    selected_section = st.selectbox(
        "오늘 기록할 운동 부위",
        section_options,
        format_func=lambda key: "🏃 유산소" if key == "CARDIO" else f"{part_by_key[key]['label']} · {part_by_key[key]['part']}",
        key="today_training_section",
    )

    quick_pick = st.session_state.get("quick_pick", [])
    quick_filter_on = st.session_state.get("quick_filter_on", False) and bool(quick_pick)

    for part in PARTS:
        if selected_section != part["key"]:
            continue
        with st.container():
            all_exercises = exercises_by_part[part["key"]]
            exercises = (
                [e for e in all_exercises if e["name"] in quick_pick]
                if quick_filter_on else all_exercises
            )
            done_count = 0

            color = PART_COLORS.get(part["key"], "#FFC834")
            st.markdown(
                f"<span class='part-badge' style='background:{color};'>{part['label']} · {part['part']}</span>",
                unsafe_allow_html=True,
            )
            if quick_filter_on:
                st.caption("🎯 오늘 선택한 운동만 보여주고 있어요. (위 '오늘 뭐 할지 정하기'에서 끌 수 있어요)")
            if quick_filter_on and not exercises:
                st.info("이 부위에서 선택한 운동이 없어요.")
                continue

            for ex in exercises:
                existing = log_for_date.get(ex["name"])
                sets_state = existing["sets"] if existing else [{"w": "", "r": ""} for _ in range(ex["sets"])]
                is_complete = existing is not None and all(
                    s.get("w") not in (None, "") and s.get("r") not in (None, "") for s in sets_state
                )
                if is_complete:
                    done_count += 1

            chip_class = "progress-chip done" if exercises and done_count == len(exercises) else "progress-chip"
            st.markdown(
                f"<div style='text-align:right; margin-bottom:10px;'>"
                f"<span class='{chip_class}'>{done_count}/{len(exercises)} 완료</span></div>",
                unsafe_allow_html=True,
            )

            for ex in exercises:
                base_key = f"{date_str}_{part['key']}_{ex['name']}"

                # ---- 대체 운동: 기구 자리가 없을 때 같은 부위 다른 운동으로 바꿔서 기록 ----
                alt_list = alt_exercises_for(ex["name"])
                sub_options = [ex["name"]] + [a["name"] for a in alt_list]
                sub_key = f"{base_key}_sub"
                chosen_name = st.session_state.get(sub_key, ex["name"])
                if chosen_name not in sub_options:
                    chosen_name = ex["name"]
                active_ex = EX_BY_NAME.get(chosen_name, ex)
                is_substituted = chosen_name != ex["name"]

                existing = log_for_date.get(active_ex["name"])
                sets_state = existing["sets"] if existing else [{"w": "", "r": ""} for _ in range(active_ex["sets"])]
                memo_state = existing["memo"] if existing else ""
                is_complete = existing is not None and all(
                    s.get("w") not in (None, "") and s.get("r") not in (None, "") for s in sets_state
                )

                pr = pr_map.get(active_ex["name"])
                pr_txt = f" · 🏅 {pr['weight']:g}kg × {pr['reps']}회" if pr else ""
                sub_tag = " 🔄대체" if is_substituted else ""

                with st.expander(f"{'✅ ' if is_complete else ''}{active_ex['name']}{sub_tag}{pr_txt}"):
                    if is_substituted:
                        st.caption(f"원래 운동: {ex['name']} → 지금은 대체 운동으로 기록해요.")

                    if len(sub_options) > 1:
                        st.selectbox(
                            "🔄 기구 자리가 없나요? 같은 부위 운동으로 대체",
                            sub_options, key=sub_key,
                            index=sub_options.index(chosen_name),
                        )

                    try:
                        st.image(active_ex["img_path"], width=220)
                    except Exception:
                        pass
                    st.markdown(
                        f"<div class='equip-line'>🎯 {active_ex['sets']}세트 · {active_ex['reps']}</div>"
                        f"<div class='equip-line'>🛠️ {active_ex['equip']}</div>",
                        unsafe_allow_html=True,
                    )
                    if pr:
                        st.markdown(
                            f"<div class='pr-line'>🏅 최고기록 {pr['weight']:g}kg × {pr['reps']}회</div>",
                            unsafe_allow_html=True,
                        )

                    if active_ex.get("howto"):
                        with st.container():
                            st.markdown("**동작 방법**")
                            steps_md = "\n".join(f"{i+1}. {s}" for i, s in enumerate(active_ex["howto"]))
                            st.markdown(steps_md)

                    if active_ex.get("caution"):
                        st.markdown(
                            f"<div class='caution-box'>⚠️ <b>주의사항</b><br>{active_ex['caution']}</div>",
                            unsafe_allow_html=True,
                        )
                    if active_ex.get("tip"):
                        st.markdown(
                            f"<div class='tip-box'>💡 <b>팁</b><br>{active_ex['tip']}</div>",
                            unsafe_allow_html=True,
                        )

                    st.markdown("---")
                    st.markdown("**세트 기록**")
                    st.caption("⏱ 세트 사이 휴식 타이머 (바로 여기서 눌러요, 위로 스크롤 안 해도 돼요)")
                    render_rest_timer()

                    new_sets = []
                    for i in range(active_ex["sets"]):
                        s = sets_state[i] if i < len(sets_state) else {"w": "", "r": ""}
                        with st.container(key=f"setrow_{base_key}_{i}"):
                            c1, c2, c3 = st.columns([0.9, 1.5, 1.5])
                            c1.markdown(f"<div style='padding-top:10px; font-size:12px; color:#9296A0; white-space:nowrap;'>{i+1}세트</div>", unsafe_allow_html=True)
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
                        ok, err = db.validate_sets(new_sets)
                        if not ok:
                            st.error(err)
                        else:
                            db.save_exercise_log(user["id"], date_str, active_ex["name"], new_sets, memo_val)
                            st.toast(f"{active_ex['name']} 저장 완료!", icon="✅")
                            st.rerun()

    if selected_section == "CARDIO":
        render_cardio_today(user, date_str)


# ================= 오늘의 루틴 (유산소) =================
def render_cardio_today(user: dict, date_str: str):
    """'오늘의 루틴' 화면 중 유산소 탭. 유산소 운동을 선택해 시간/거리/칼로리를 입력하고 저장한다."""
    cardio_log_for_date = db.get_cardio_log_for_date(user["id"], date_str)
    cardio_pr_map = db.get_cardio_personal_records(user["id"])

    done_count = sum(1 for ex in CARDIO_EXERCISES if ex["name"] in cardio_log_for_date)

    st.markdown(
        f"<span class='part-badge' style='background:{CARDIO_COLOR};'>🏃 유산소</span>",
        unsafe_allow_html=True,
    )
    chip_class = "progress-chip done" if done_count == len(CARDIO_EXERCISES) else "progress-chip"
    st.markdown(
        f"<div style='text-align:right; margin-bottom:10px;'>"
        f"<span class='{chip_class}'>{done_count}/{len(CARDIO_EXERCISES)} 완료</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<div class='tip-box'>{CARDIO_NOTE}</div>", unsafe_allow_html=True)

    for ex in CARDIO_EXERCISES:
        base_key = f"{date_str}_CARDIO_{ex['key']}"

        existing = cardio_log_for_date.get(ex["name"])
        min_val, sec_val = split_duration(existing["duration_min"]) if existing else ("", "")
        distance_val = str(existing.get("distance_km")) if existing and existing.get("distance_km") not in (None, "") else ""
        calories_val = str(existing.get("calories")) if existing and existing.get("calories") not in (None, "") else ""
        memo_val = existing.get("memo", "") if existing else ""
        is_complete = existing is not None

        pr = cardio_pr_map.get(ex["name"])
        pr_bits = []
        if pr:
            if ex["has_distance"]:
                if pr.get("best_distance"):
                    pr_bits.append(f"최장 {pr['best_distance']:.2f}km")
                if pr.get("best_pace_sec"):
                    pr_bits.append(f"최고 {format_pace(pr['best_pace_sec'])}")
            elif pr.get("best_duration"):
                pr_bits.append(f"최장 {format_duration(pr['best_duration'])}")
        pr_txt = f" · 🏅 {' / '.join(pr_bits)}" if pr_bits else ""

        with st.expander(f"{'✅ ' if is_complete else ''}{ex['icon']} {ex['name']}{pr_txt}"):
            st.markdown(
                f"<div class='equip-line'>🎯 {ex['target']}</div>"
                f"<div class='equip-line'>🛠️ {ex['equip']}</div>",
                unsafe_allow_html=True,
            )
            if pr_bits:
                st.markdown(
                    f"<div class='pr-line'>🏅 최고기록 {' / '.join(pr_bits)}</div>",
                    unsafe_allow_html=True,
                )

            if ex.get("tips"):
                st.markdown("**진행 팁**")
                st.markdown("\n".join(f"- {t}" for t in ex["tips"]))

            if ex.get("caution"):
                st.markdown(
                    f"<div class='caution-box'>⚠️ <b>주의사항</b><br>{ex['caution']}</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("---")
            st.markdown("**유산소 기록**")

            label_cols_n = 3 if ex["has_distance"] else 2
            with st.container(key=f"evenrow_{base_key}_labels"):
                lc = st.columns(label_cols_n)
                lc[0].markdown(
                    "<div style='font-size:11px; color:#9296A0; text-align:center; font-weight:600;'>⏱ 분</div>",
                    unsafe_allow_html=True,
                )
                lc[1].markdown(
                    "<div style='font-size:11px; color:#9296A0; text-align:center; font-weight:600;'>⏱ 초</div>",
                    unsafe_allow_html=True,
                )
                if ex["has_distance"]:
                    lc[2].markdown(
                        "<div style='font-size:11px; color:#9296A0; text-align:center; font-weight:600;'>📏 거리(km)</div>",
                        unsafe_allow_html=True,
                    )

            with st.container(key=f"evenrow_{base_key}_inputs"):
                cols = st.columns(label_cols_n)
                new_min = cols[0].text_input(
                    "분", value=min_val, key=f"{base_key}_min",
                    label_visibility="collapsed", placeholder="분",
                )
                new_sec = cols[1].text_input(
                    "초", value=sec_val, key=f"{base_key}_sec",
                    label_visibility="collapsed", placeholder="초",
                )
                new_distance = ""
                if ex["has_distance"]:
                    new_distance = cols[2].text_input(
                        "거리(km)", value=distance_val, key=f"{base_key}_dist",
                        label_visibility="collapsed", placeholder="예: 5.25",
                    )

            if ex["has_distance"] and (new_min or new_sec) and new_distance:
                preview_dur, preview_err = parse_duration(new_min, new_sec)
                if not preview_err and preview_dur:
                    try:
                        dist_f = float(new_distance)
                        if preview_dur > 0 and dist_f > 0:
                            st.caption(f"⏱ 페이스: {format_pace(preview_dur * 60 / dist_f)}")
                    except (TypeError, ValueError):
                        pass

            new_calories = st.text_input(
                "칼로리(선택)", value=calories_val, key=f"{base_key}_cal",
                placeholder="칼로리 (선택, 러닝앱에서 옮겨적기)",
            )
            new_memo = st.text_input(
                "메모", value=memo_val, key=f"{base_key}_memo",
                placeholder="컨디션, 코스, 날씨 등 메모",
            )

            if st.button("이 기록 저장", key=f"{base_key}_save", use_container_width=True):
                new_duration, dur_err = parse_duration(new_min, new_sec)
                if dur_err:
                    st.error(dur_err)
                else:
                    ok, err = db.validate_cardio_log(new_duration, new_distance if ex["has_distance"] else None, new_calories)
                    if not ok:
                        st.error(err)
                    else:
                        db.save_cardio_log(
                            user["id"], date_str, ex["name"],
                            new_duration, new_distance if ex["has_distance"] else None,
                            new_calories, new_memo,
                        )
                        st.toast(f"{ex['name']} 저장 완료!", icon="✅")
                        st.rerun()


# ================= 마이페이지 =================
def render_mypage(user: dict):
    """마이페이지. 연속 기록일·총 기록일·총 볼륨 요약, 개인 최고기록(PR), 기록 히스토리, 계정 설정을 보여준다."""
    st.subheader("📖 마이페이지")
    st.caption(f"{user['nickname']}님의 운동 기록")

    stats = st.session_state.get("_header_stats") or db.get_user_stats(user["id"], today_kst().isoformat())
    with st.container(key="evenrow_mypage_stats"):
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 연속 기록", f"{stats['streak']}일")
        c2.metric("🗓️ 총 기록일", f"{stats['workout_days']}일")
        c3.metric("🏋️ 총 볼륨", f"{stats['total_volume']:,.0f}kg")

    ui.render_tier_card(stats["workout_days"])

    cardio_totals = db.get_cardio_totals(user["id"])
    if cardio_totals["total_distance_km"] > 0 or cardio_totals["total_duration_min"] > 0:
        with st.container(key="evenrow_mypage_cardio_stats"):
            d1, d2 = st.columns(2)
            d1.metric("🏃 누적 거리", f"{cardio_totals['total_distance_km']:.2f}km")
            d2.metric("⏱️ 누적 시간", f"{cardio_totals['total_duration_min']:.0f}분")

    ui.render_streak_heatmap(db.get_workout_dates(user["id"]))

    record_menu = st.selectbox(
        "기록 메뉴",
        ["🏅 개인 최고기록", "🏃 유산소 기록", "📈 훈련 통계", "⚖️ 체형", "🎖️ 뱃지", "🗓️ 기록", "⚙️ 설정"],
        key="mypage_section",
    )

    if record_menu == "🏅 개인 최고기록":
        pr_map = db.get_personal_records(user["id"])
        if not pr_map:
            st.info("아직 기록이 없어요. 오늘의 루틴에서 운동을 기록해보세요!")
        else:
            rows = [
                {"운동": name, "최고 무게(kg)": rec["weight"], "횟수": rec["reps"], "날짜": rec["date"]}
                for name, rec in sorted(pr_map.items(), key=lambda kv: -kv[1]["weight"])
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("**📈 운동별 무게 추이**")
            chart_ex = st.selectbox("운동 선택", sorted(pr_map.keys()), key="progress_chart_ex")
            history = db.get_weight_history(user["id"], chart_ex)
            if len(history) < 2:
                st.caption("기록이 2개 이상 쌓이면 추이 그래프가 나타나요.")
            else:
                chart_data = {h["date"]: h["weight"] for h in history}
                st.line_chart(chart_data)

    if record_menu == "🏃 유산소 기록":
        cardio_pr_map = db.get_cardio_personal_records(user["id"])
        if not cardio_pr_map:
            st.info("아직 유산소 기록이 없어요. '오늘' 화면 🏃 유산소 탭에서 기록해보세요!")
        else:
            rows = []
            for name, rec in sorted(cardio_pr_map.items()):
                ex_def = CARDIO_EX_BY_NAME.get(name, {})
                icon = ex_def.get("icon", "🏃")
                row = {"운동": f"{icon} {name}"}
                if ex_def.get("has_distance"):
                    row["최장거리(km)"] = f"{rec['best_distance']:.2f}" if rec.get("best_distance") else "-"
                    row["최고페이스"] = format_pace(rec["best_pace_sec"]) if rec.get("best_pace_sec") else "-"
                else:
                    row["최장시간"] = format_duration(rec["best_duration"]) if rec.get("best_duration") else "-"
                rows.append(row)
            st.dataframe(rows, use_container_width=True, hide_index=True)
            st.caption("거리가 있는 종목은 최장거리·최고페이스(가장 빠른 기록)를, 거리가 없는 종목은 최장시간을 보여줘요.")

    if record_menu == "📈 훈련 통계":
        features_ui.render_training_insights(user, today_kst().isoformat())

    if record_menu == "⚖️ 체형":
        features_ui.render_body_metrics(user, today_kst().isoformat())

    if record_menu == "🎖️ 뱃지":
        st.caption("꾸준함과 기록이 쌓이면 뱃지가 하나씩 열려요.")
        badges = db.get_badges(user["id"], user["nickname"], today_kst().isoformat(), len(ALL_EXERCISE_NAMES))
        earned = sum(1 for b in badges if b["achieved"])
        st.markdown(f"**{earned} / {len(badges)}개 달성**")
        ui.render_badges(badges)

    if record_menu == "🗓️ 기록":
        ui.render_history_tab(user)

    if record_menu == "⚙️ 설정":
        ui.render_account_settings(user)


# ================= 랭킹 =================
def render_ranking(user: dict):
    """랭킹 페이지. 종목별 TOP20 순위, 총 볼륨 랭킹, 종목별 챔피언 현황을 보여준다."""
    st.subheader("🏆 운동별 랭킹")
    st.caption("가장 무거운 무게로, 같은 무게면 가장 많은 횟수로 든 사람이 1등이에요.")

    my_nickname = user["nickname"]

    ranking_menu = st.selectbox(
        "랭킹 메뉴",
        ["👑 전체 종목 1위", "📋 종목별 TOP 20", "🏋️ 총 볼륨"],
        key="ranking_section",
    )

    if ranking_menu == "👑 전체 종목 1위":
        st.caption("각 운동마다 현재 최고 기록 보유자예요. 이름 옆에 뜨고 싶다면 지금 기록을 남겨보세요 🔥")
        champs = db.get_champions(ALL_EXERCISE_NAMES)
        if not champs:
            st.info("아직 아무도 기록을 남기지 않았어요. 첫 챔피언이 되어보세요!")
        else:
            rows = []
            for name in ALL_EXERCISE_NAMES:
                c = champs.get(name)
                if not c:
                    continue
                nickname = c["nickname"] + (" 👈 나" if c["nickname"] == my_nickname else "")
                rows.append(
                    {
                        "운동": name,
                        "🥇 1위": nickname,
                        "무게(kg)": c["weight"],
                        "횟수": c["reps"],
                        "날짜": c["date"],
                    }
                )
            st.dataframe(rows, use_container_width=True, hide_index=True)
            missing = [n for n in ALL_EXERCISE_NAMES if n not in champs]
            if missing:
                st.caption("아직 기록이 없는 종목: " + ", ".join(missing))

    if ranking_menu == "📋 종목별 TOP 20":
        exercise = st.selectbox("운동 선택", ALL_EXERCISE_NAMES)
        all_rows = db.get_leaderboard(exercise, limit=100000)
        rows = all_rows[:20]

        if not rows:
            st.info("아직 이 운동에 대한 기록이 없어요. 가장 먼저 기록을 남겨보세요!")
        else:
            my_rank = next(
                (index for index, row in enumerate(all_rows, start=1) if row.get("user_id") == user["id"]),
                None,
            )
            if my_rank is None:
                st.caption("아직 이 운동 기록이 없어요.")
            elif my_rank > 20:
                st.caption(f"📍 내 순위: {my_rank}위 (TOP 20 밖)")
            else:
                st.caption(f"📍 내 순위: {my_rank}위")
            table = []
            for i, r in enumerate(rows, start=1):
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}")
                nickname = r["nickname"] + (" (나)" if r["nickname"] == my_nickname else "")
                table.append(
                    {
                        "순위": medal,
                        "닉네임": nickname,
                        "무게(kg)": r["weight"],
                        "횟수": r["reps"],
                        "날짜": r["date"],
                    }
                )
            st.dataframe(table, use_container_width=True, hide_index=True)

    if ranking_menu == "🏋️ 총 볼륨":
        st.caption("모든 운동의 무게×횟수를 합친 총 볼륨 순위예요. 꾸준함이 쌓이면 순위가 올라가요 💪")
        all_rows = db.get_volume_leaderboard(limit=100000)
        rows = all_rows[:20]
        if not rows:
            st.info("아직 기록이 없어요.")
        else:
            my_vol_rank = next(
                (index for index, row in enumerate(all_rows, start=1) if row.get("user_id") == user["id"]),
                None,
            )
            if my_vol_rank and my_vol_rank > 20:
                st.caption(f"📍 내 순위: {my_vol_rank}위 (TOP 20 밖)")
            elif my_vol_rank:
                st.caption(f"📍 내 순위: {my_vol_rank}위")
            table = []
            for i, r in enumerate(rows, start=1):
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}")
                nickname = r["nickname"] + (" (나)" if r["nickname"] == my_nickname else "")
                table.append(
                    {"순위": medal, "닉네임": nickname, "총 볼륨(kg)": f"{r['total_volume']:,.0f}"}
                )
            st.dataframe(table, use_container_width=True, hide_index=True)


# ================= 문의하기 =================
def render_contact(user: dict):
    """문의하기 페이지. 사용자가 새 문의를 등록하고, 본인이 남긴 문의 내역과 관리자 답변을 확인한다."""
    st.subheader("💬 문의하기")
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
    st.markdown("**📋 모두의 문의**")

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
                if q.get("answer"):
                    st.markdown(
                        f"<div class='tip-box'>🛠️ <b>운영자 답변</b><br>{q['answer']}</div>",
                        unsafe_allow_html=True,
                    )


# ================= 관리자 =================
def render_admin(user: dict):
    """관리자 전용 페이지. 대시보드 통계, 회원 관리(검색/삭제/비밀번호 강제 초기화), 문의 관리(상태 변경/답변)를 제공한다."""
    st.subheader("🛠️ 관리자 페이지")
    st.caption(f"{user['nickname']}님, 어서오세요. 여기는 운영자만 볼 수 있어요.")

    admin_menu = st.selectbox(
        "관리 메뉴",
        ["📊 대시보드", "👥 회원 관리", "💬 문의 관리", "🏋️ 운동 관리"],
        key="admin_section",
    )

    if admin_menu == "📊 대시보드":
        stats = db.get_dashboard_stats()

        with st.container(key="evenrow_admin_stats"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("👥 총 가입자", f"{stats['total_users']}명")
            c2.metric("🟢 현재 접속자", f"{stats['active_users']}명")
            c3.metric("📝 총 운동 기록", f"{stats['total_logs']}건")
            c4.metric("💬 미처리 문의", f"{stats['open_inquiries']}건")

        st.divider()
        st.markdown("**🟢 지금 접속 중인 사람**")
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
        st.markdown("**👑 종목별 챔피언 요약**")
        champs = db.get_champions(ALL_EXERCISE_NAMES)
        if champs:
            rows = [
                {"운동": name, "1위": c["nickname"], "무게(kg)": c["weight"], "횟수": c["reps"]}
                for name, c in champs.items()
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("아직 기록이 없어요.")

        st.divider()
        st.markdown("**📈 최근 14일 가입 추이**")
        signup_rows = db.get_signup_counts_by_day(14)
        st.bar_chart({r["날짜"]: r["가입자 수"] for r in signup_rows})

    if admin_menu == "👥 회원 관리":
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

                if u["username"] != user["username"]:
                    reset_key = f"reset_pw_result_{u['_id']}"
                    if st.session_state.get(reset_key):
                        st.success(f"임시 비밀번호: `{st.session_state[reset_key]}` (본인에게 꼭 전달해주세요)")
                        if st.button("확인함", key=f"ack_{u['_id']}"):
                            st.session_state.pop(reset_key, None)
                            st.rerun()
                    else:
                        if st.button("🔑 비밀번호 강제 초기화", key=f"resetpw_{u['_id']}"):
                            temp_pw = db.admin_reset_password(str(u["_id"]))
                            st.session_state[reset_key] = temp_pw
                            st.rerun()

    if admin_menu == "💬 문의 관리":
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

                    answer_val = st.text_area(
                        "답변",
                        value=q.get("answer", ""),
                        key=f"answer_{q['_id']}",
                        placeholder="문의자에게 공개로 보여줄 답변을 남겨보세요.",
                        label_visibility="collapsed",
                    )
                    if st.button("답변 저장", key=f"save_answer_{q['_id']}", use_container_width=True):
                        db.answer_inquiry(q["_id"], answer_val)
                        st.toast("답변을 저장했어요.", icon="✅")
                        st.rerun()

    if admin_menu == "🏋️ 운동 관리":
        features_ui.render_admin_exercise_editor()


# ================= 게시판 (자유 / 운동 / 정보 / 인증샷) =================
# 목록에서는 게시판별 글 제목만 보이고, 클릭해서 상세로 들어가야 사진/본문/댓글을 볼 수 있다.
# st.session_state["board_view"]로 목록(list) / 글쓰기(write) / 상세(detail) / 수정(edit) 화면을 전환한다.

def render_board(user: dict):
    """게시판 페이지 진입점. 화면 상태에 따라 목록/글쓰기/상세/수정 중 하나를 그린다."""
    st.session_state.setdefault("board_view", "list")
    st.session_state.setdefault("board_category", "all")
    st.session_state.setdefault("board_post_id", None)

    is_admin = db.is_admin(user["username"])
    view = st.session_state["board_view"]

    if view == "write":
        _render_board_write(user)
    elif view == "edit" and st.session_state["board_post_id"]:
        _render_board_edit(user, is_admin)
    elif view == "detail" and st.session_state["board_post_id"]:
        _render_board_detail(user, is_admin)
    else:
        st.session_state["board_view"] = "list"
        _render_board_list(user, is_admin)


def _render_board_list(user: dict, is_admin: bool):
    """게시판 목록 화면. 게시판 종류 선택 + 검색 + 글쓰기 버튼 + 제목 목록."""
    st.subheader("📋 게시판")
    st.caption("자유롭게 이야기하고, 운동 정보도 나누고, 인증샷도 올려보세요.")

    counts = db.get_board_category_counts()
    total = sum(counts.values())
    cat_options = ["all"] + db.BOARD_CATEGORY_KEYS

    def _cat_label(k: str) -> str:
        if k == "all":
            return f"🗂️ 전체({total})"
        return f"{db.BOARD_CATEGORY_ICON[k]} {db.BOARD_CATEGORY_NAME[k]}({counts.get(k, 0)})"

    chunk = 3
    for i in range(0, len(cat_options), chunk):
        row = cat_options[i:i + chunk]
        with st.container(key=f"evenrow_boardcat_{i}"):
            cols = st.columns(len(row))
            for col, key in zip(cols, row):
                btn_type = "primary" if st.session_state["board_category"] == key else "secondary"
                if col.button(_cat_label(key), key=f"boardcat_{key}", use_container_width=True, type=btn_type):
                    st.session_state["board_category"] = key
                    st.rerun()

    with st.container(key="evenrow_boardtools"):
        s1, s2 = st.columns([3, 1])
        search = s1.text_input(
            "검색", key="board_search", placeholder="🔍 제목/내용/작성자 검색",
            label_visibility="collapsed",
        )
        if s2.button("✏️ 글쓰기", key="board_write_btn", use_container_width=True, type="primary"):
            st.session_state["board_view"] = "write"
            st.rerun()

    st.divider()

    category = st.session_state["board_category"]
    posts = db.get_posts(category=category, search=search, limit=100)

    if not posts:
        if search:
            st.info("검색 결과가 없어요.")
        else:
            st.info("아직 글이 없어요. 첫 글의 주인공이 되어보세요!")
        return

    for p in posts:
        post_id = str(p["_id"])
        cat = p.get("category", "cert")
        title = p.get("title") or p.get("caption") or "(제목 없음)"
        comment_count = len(p.get("comments", []))
        reaction_count = sum(len(v) for v in p.get("reactions", {}).values())
        photo_tag = " 📷" if p.get("photo_b64") else ""
        created = p.get("created_at")
        date_txt = created.strftime("%m/%d %H:%M") if created else p.get("date", "")
        mine_tag = " · 나" if p.get("user_id") == user["id"] else ""

        with st.container(border=True, key=f"boardrow_{post_id}"):
            icon = db.BOARD_CATEGORY_ICON.get(cat, "📌")
            if st.button(f"{icon} {title}{photo_tag}", key=f"boardopen_{post_id}", use_container_width=True):
                st.session_state["board_view"] = "detail"
                st.session_state["board_post_id"] = post_id
                st.rerun()
            st.caption(
                f"{db.BOARD_CATEGORY_NAME.get(cat, '게시판')} · {p.get('nickname', '')}{mine_tag} · "
                f"{date_txt} · 💬 {comment_count} · 👍 {reaction_count} · 조회 {p.get('views', 0)}"
            )


def _render_board_write(user: dict):
    """새 글쓰기 화면."""
    st.subheader("✏️ 새 글쓰기")
    if st.button("← 목록으로", key="board_write_back"):
        st.session_state["board_view"] = "list"
        st.rerun()

    default_cat = st.session_state.get("board_category")
    if default_cat not in db.BOARD_CATEGORY_KEYS:
        default_cat = db.DEFAULT_BOARD_CATEGORY
    cat_labels = [db.BOARD_CATEGORY_LABEL[k] for k in db.BOARD_CATEGORY_KEYS]

    with st.form("board_write_form", clear_on_submit=False):
        cat_choice = st.selectbox(
            "게시판 선택", cat_labels,
            index=db.BOARD_CATEGORY_KEYS.index(default_cat), key="board_new_cat",
        )
        title = st.text_input("제목", key="board_new_title", placeholder="제목을 입력하세요")
        content = st.text_area(
            "내용", key="board_new_content", placeholder="내용을 입력하세요",
            height=180,
        )
        photo = st.file_uploader("사진 첨부 (선택, jpg/png)", type=["jpg", "jpeg", "png"], key="board_new_photo")
        submitted = st.form_submit_button("게시하기", use_container_width=True)

    if submitted:
        if not title.strip():
            st.error("제목을 입력해주세요.")
        elif not content.strip() and not photo:
            st.error("내용이나 사진 중 하나는 입력해주세요.")
        else:
            cat_key = db.BOARD_CATEGORY_KEYS[cat_labels.index(cat_choice)]
            photo_bytes = photo.read() if photo else None
            db.create_post(user["id"], user["nickname"], cat_key, title, content, photo_bytes)
            st.toast("게시글을 올렸어요!", icon="📝")
            for k in ("board_new_title", "board_new_content"):
                st.session_state.pop(k, None)
            st.session_state["board_view"] = "list"
            st.session_state["board_category"] = cat_key
            st.rerun()


def _render_board_detail(user: dict, is_admin: bool):
    """게시글 상세 화면. 제목/사진/본문/리액션/댓글을 모두 보여준다."""
    post_id = st.session_state["board_post_id"]
    p = db.get_post_by_id(post_id)

    if not p:
        st.warning("게시글을 찾을 수 없어요 (삭제되었을 수 있어요).")
        if st.button("← 목록으로", key="board_detail_back_missing"):
            st.session_state["board_view"] = "list"
            st.session_state["board_post_id"] = None
            st.rerun()
        return

    if st.button("← 목록으로", key="board_detail_back"):
        st.session_state["board_view"] = "list"
        st.session_state["board_post_id"] = None
        st.rerun()

    viewed_key = f"board_viewed_{post_id}"
    if not st.session_state.get(viewed_key):
        db.increment_view(post_id)
        st.session_state[viewed_key] = True
        p["views"] = p.get("views", 0) + 1

    cat = p.get("category", "cert")
    title = p.get("title") or p.get("caption") or "(제목 없음)"
    is_mine = p.get("user_id") == user["id"]
    created = p.get("created_at")
    date_txt = created.strftime("%Y-%m-%d %H:%M") if created else p.get("date", "")

    st.markdown(f"#### {db.BOARD_CATEGORY_ICON.get(cat, '📌')} {title}")
    mine_tag = " · 나" if is_mine else ""
    st.caption(
        f"{db.BOARD_CATEGORY_NAME.get(cat, '게시판')} · {p.get('nickname', '')}{mine_tag} · "
        f"{date_txt} · 조회 {p.get('views', 0)}"
    )

    if p.get("photo_b64"):
        st.image(base64.b64decode(p["photo_b64"]), use_container_width=True)
    content = p.get("content") or p.get("caption") or ""
    if content:
        st.markdown(content)

    st.divider()

    reactions = p.get("reactions", {})
    with st.container(key=f"evenrow_react_{post_id}"):
        cols = st.columns(len(db.REACTION_EMOJIS))
        for emoji, rcol in zip(db.REACTION_EMOJIS, cols):
            users = reactions.get(emoji, [])
            reacted = user["id"] in users
            label = f"{emoji} {len(users)}" if users else emoji
            if rcol.button(label, key=f"react_{emoji}_{post_id}", use_container_width=True, type="primary" if reacted else "secondary"):
                db.toggle_reaction(p["_id"], user["id"], emoji)
                st.rerun()

    if is_mine or is_admin:
        with st.container(key=f"evenrow_postactions_{post_id}"):
            c1, c2 = st.columns(2)
            if c1.button("✏️ 수정", key=f"editpost_{post_id}", use_container_width=True):
                st.session_state["board_view"] = "edit"
                st.rerun()
            if c2.button("🗑️ 삭제", key=f"delpost_{post_id}", use_container_width=True):
                db.delete_post(p["_id"], user["id"], is_admin)
                st.toast("삭제했어요.", icon="🗑️")
                st.session_state["board_view"] = "list"
                st.session_state["board_post_id"] = None
                st.rerun()

    st.divider()
    comments = p.get("comments", [])
    st.markdown(f"**댓글 {len(comments)}**")
    for c in comments:
        with st.container(key=f"evenrow_comment_{post_id}_{c['_id']}"):
            cc1, cc2 = st.columns([5, 1])
            cc1.markdown(f"💬 **{c['nickname']}** {c['text']}")
            if (c.get("user_id") == user["id"] or is_admin) and cc2.button("삭제", key=f"delcm_{post_id}_{c['_id']}"):
                db.delete_comment(p["_id"], c["_id"], user["id"], is_admin)
                st.rerun()

    with st.form(f"comment_form_{post_id}", clear_on_submit=True):
        with st.container(key=f"evenrow_commentinput_{post_id}"):
            cco1, cco2 = st.columns([4, 1])
            comment_text = cco1.text_input("댓글", key=f"comment_{post_id}", placeholder="댓글 달기", label_visibility="collapsed")
            comment_submitted = cco2.form_submit_button("등록", use_container_width=True)
    if comment_submitted and comment_text.strip():
        db.add_comment(p["_id"], user["id"], user["nickname"], comment_text)
        st.rerun()


def _render_board_edit(user: dict, is_admin: bool):
    """게시글 수정 화면 (작성자 본인 또는 관리자만 진입 가능)."""
    post_id = st.session_state["board_post_id"]
    p = db.get_post_by_id(post_id)

    if not p:
        st.warning("게시글을 찾을 수 없어요.")
        st.session_state["board_view"] = "list"
        st.session_state["board_post_id"] = None
        return

    is_mine = p.get("user_id") == user["id"]
    if not (is_mine or is_admin):
        st.error("수정 권한이 없어요.")
        st.session_state["board_view"] = "detail"
        return

    st.subheader("✏️ 글 수정")
    if st.button("← 취소", key="board_edit_cancel"):
        st.session_state["board_view"] = "detail"
        st.rerun()

    remove_photo = False
    if p.get("photo_b64"):
        st.image(base64.b64decode(p["photo_b64"]), width=220, caption="현재 사진")
        remove_photo = st.checkbox("사진 삭제", key=f"remove_photo_{post_id}")

    with st.form(f"board_edit_form_{post_id}"):
        title = st.text_input(
            "제목", value=p.get("title") or p.get("caption") or "", key=f"edit_title_{post_id}",
        )
        content = st.text_area(
            "내용", value=p.get("content") or p.get("caption") or "", height=180,
            key=f"edit_content_{post_id}",
        )
        photo = st.file_uploader("사진 교체 (선택)", type=["jpg", "jpeg", "png"], key=f"edit_photo_{post_id}")
        submitted = st.form_submit_button("수정 완료", use_container_width=True)

    if submitted:
        if not title.strip():
            st.error("제목을 입력해주세요.")
        else:
            photo_bytes = photo.read() if photo else None
            db.update_post(
                post_id, user["id"], is_admin,
                title=title, content=content, file_bytes=photo_bytes, remove_photo=remove_photo,
            )
            st.toast("수정했어요.", icon="✏️")
            st.session_state["board_view"] = "detail"
            st.rerun()


# ================= 라우팅 =================
# 로그인이 안 되어 있으면 무조건 로그인/회원가입 화면.
# 로그인이 되어 있으면 render_topnav()가 반환한 페이지 키(_page)에 맞는
# render_xxx() 함수 하나만 호출한다. (pages/ 폴더 없이 이 if/elif로 화면을 전환)
if "user" not in st.session_state:
    render_auth()
else:
    _user = st.session_state["user"]
    _admin = db.is_admin(_user["username"])
    _page = render_topnav(_user, _admin)

    if _page == "mypage":
        render_mypage(_user)
    elif _page == "routines":
        features_ui.render_routines_page(_user, today_kst().isoformat())
    elif _page == "session":
        features_ui.render_workout_session(_user, today_kst().isoformat(), render_rest_timer)
    elif _page == "board":
        render_board(_user)
    elif _page == "ranking":
        render_ranking(_user)
    elif _page == "contact":
        render_contact(_user)
    elif _page == "admin" and _admin:
        render_admin(_user)
    else:
        st.session_state["page"] = "today"
        render_today(_user)
