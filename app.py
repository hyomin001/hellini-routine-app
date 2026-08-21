# -*- coding: utf-8 -*-
import base64
import datetime as dt

import streamlit as st
import streamlit.components.v1 as components

from utils import db
from utils import ui
from utils import card
from utils.data import PARTS, exercises_for_part, ALL_EXERCISE_NAMES, UPDATE_LOG

# Streamlit Cloud 서버는 UTC 기준으로 동작하므로 dt.date.today()를 그대로 쓰면
# 한국시간(UTC+9) 새벽 0~9시 사이에는 아직 "어제" 날짜가 반환된다.
# 항상 한국시간(KST) 기준 오늘 날짜를 쓰도록 고정한다.
KST = dt.timezone(dt.timedelta(hours=9))


def today_kst() -> dt.date:
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
    "PART3": "#5AFF9F",
    "PART4": "#FF5A9F",
}


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
    ("mypage", "📖 기록"),
    ("feed", "📸 인증"),
    ("ranking", "🏆 랭킹"),
    ("contact", "💬 문의"),
]

def render_topnav(user: dict, admin: bool) -> str:
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
    streak_txt = f" · 🔥 연속 {stats['streak']}일" if stats["streak"] > 0 else ""
    admin_tag = " · 🛡️ 관리자" if admin else ""
    st.caption(f"👋 {user['nickname']}님{admin_tag} · 👥 총 가입자 {total}명 · 🟢 현재 접속 {active}명{streak_txt}")

    st.divider()
    return current

# ================= 오늘의 루틴 =================
def render_today(user: dict):
    selected_date = st.date_input("날짜", value=today_kst(), key="today_date")
    date_str = selected_date.isoformat()

    st.markdown(
        "<div style='background:#1B1D22; border:1px solid #33373F; border-radius:8px; "
        "padding:10px 12px; font-size:12.5px; color:#9296A0; margin:10px 0 18px;'>"
        "✓ 모든 무게는 마지막 2~3개가 <b style='color:#FFC834;'>매우 힘들 정도</b>로 진행하세요. "
        "주 4회가 힘들면 부위 순서(사이클)만 지켜서 따라하면 됩니다."
        "</div>",
        unsafe_allow_html=True,
    )

    log_for_date = db.get_log_for_date(user["id"], date_str)
    pr_map = db.get_personal_records(user["id"])

    # ---- 이 날짜의 전체(부위 1~4 합산) 진행 요약 ----
    total_all, done_all = 0, 0
    for part in PARTS:
        for ex in exercises_for_part(part["key"]):
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

    st.caption("⏱ 세트 사이 휴식 타이머 (운동 하나 저장하고 다시 열어도 이어서 흘러가요)")
    render_rest_timer()

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

    part_labels = [f"{p['label']} · {p['part']}" for p in PARTS]
    tab_objs = st.tabs(part_labels)

    for tab, part in zip(tab_objs, PARTS):
        with tab:
            exercises = exercises_for_part(part["key"])
            done_count = 0

            color = PART_COLORS.get(part["key"], "#FFC834")
            st.markdown(
                f"<span class='part-badge' style='background:{color};'>{part['label']} · {part['part']}</span>",
                unsafe_allow_html=True,
            )

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
                base_key = f"{date_str}_{part['key']}_{ex['name']}"

                existing = log_for_date.get(ex["name"])
                sets_state = existing["sets"] if existing else [{"w": "", "r": ""} for _ in range(ex["sets"])]
                memo_state = existing["memo"] if existing else ""
                is_complete = existing is not None and all(
                    s.get("w") not in (None, "") and s.get("r") not in (None, "") for s in sets_state
                )

                pr = pr_map.get(ex["name"])
                pr_txt = f" · 🏅 {pr['weight']:g}kg × {pr['reps']}회" if pr else ""

                with st.expander(f"{'✅ ' if is_complete else ''}{ex['name']}{pr_txt}"):
                    try:
                        st.image(ex["img_path"], width=220)
                    except Exception:
                        pass
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
                    for i in range(ex["sets"]):
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
                            db.save_exercise_log(user["id"], date_str, ex["name"], new_sets, memo_val)
                            st.toast(f"{ex['name']} 저장 완료!", icon="✅")
                            st.rerun()


# ================= 마이페이지 =================
def render_mypage(user: dict):
    st.subheader("📖 마이페이지")
    st.caption(f"{user['nickname']}님의 운동 기록")

    stats = db.get_user_stats(user["id"], today_kst().isoformat())
    with st.container(key="evenrow_mypage_stats"):
        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 연속 기록", f"{stats['streak']}일")
        c2.metric("🗓️ 총 기록일", f"{stats['workout_days']}일")
        c3.metric("🏋️ 총 볼륨", f"{stats['total_volume']:,.0f}kg")

    ui.render_streak_heatmap(db.get_workout_dates(user["id"]))

    tab_pr, tab_badges, tab_history, tab_settings = st.tabs(
        ["🏅 개인 최고기록", "🎖️ 뱃지", "🗓️ 기록 히스토리", "⚙️ 계정 설정"]
    )

    with tab_pr:
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

    with tab_badges:
        st.caption("꾸준함과 기록이 쌓이면 뱃지가 하나씩 열려요.")
        badges = db.get_badges(user["id"], user["nickname"], today_kst().isoformat(), len(ALL_EXERCISE_NAMES))
        earned = sum(1 for b in badges if b["achieved"])
        st.markdown(f"**{earned} / {len(badges)}개 달성**")
        ui.render_badges(badges)

    with tab_history:
        ui.render_history_tab(user)

    with tab_settings:
        ui.render_account_settings(user)


# ================= 랭킹 =================
def render_ranking(user: dict):
    st.subheader("🏆 운동별 랭킹")
    st.caption("가장 무거운 무게로, 같은 무게면 가장 많은 횟수로 든 사람이 1등이에요.")

    my_nickname = user["nickname"]

    tab_champs, tab_detail, tab_volume = st.tabs(["👑 전체 종목 1위", "📋 종목별 TOP 20", "🏋️ 총 볼륨"])

    with tab_champs:
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

    with tab_detail:
        exercise = st.selectbox("운동 선택", ALL_EXERCISE_NAMES)
        rows = db.get_leaderboard(exercise, limit=20)

        if not rows:
            st.info("아직 이 운동에 대한 기록이 없어요. 가장 먼저 기록을 남겨보세요!")
        else:
            my_rank = db.get_my_exercise_rank(exercise, user["id"])
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

    with tab_volume:
        st.caption("모든 운동의 무게×횟수를 합친 총 볼륨 순위예요. 꾸준함이 쌓이면 순위가 올라가요 💪")
        rows = db.get_volume_leaderboard(limit=20)
        if not rows:
            st.info("아직 기록이 없어요.")
        else:
            my_vol_rank = db.get_my_volume_rank(user["id"])
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
    st.subheader("🛠️ 관리자 페이지")
    st.caption(f"{user['nickname']}님, 어서오세요. 여기는 운영자만 볼 수 있어요.")

    tab_dash, tab_users, tab_inquiries = st.tabs(["📊 대시보드", "👥 회원 관리", "💬 문의 관리"])

    with tab_dash:
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


# ================= 인증샷 게시판 =================
def render_feed(user: dict):
    st.subheader("📸 인증샷 게시판")
    st.caption("오늘 운동한 인증샷을 올리고, 서로 댓글과 리액션으로 응원해줘요.")

    today_str = today_kst().isoformat()
    existing = db.get_post_by_user_date(user["id"], today_str)

    with st.expander("📷 오늘 인증샷 올리기 / 수정하기", expanded=existing is None):
        if existing and existing.get("photo_b64"):
            st.image(base64.b64decode(existing["photo_b64"]), width=220, caption="현재 등록된 사진")
        with st.form("post_form", clear_on_submit=False):
            photo = st.file_uploader("사진 선택 (jpg/png)", type=["jpg", "jpeg", "png"], key="post_photo")
            caption = st.text_area(
                "한마디",
                value=existing.get("caption", "") if existing else "",
                placeholder="오늘 하체데이 죽는 줄... 다들 화이팅!",
                key="post_caption",
            )
            submitted = st.form_submit_button("게시하기", use_container_width=True)
        if submitted:
            if not photo and not existing:
                st.error("사진을 선택해주세요.")
            else:
                photo_bytes = photo.read() if photo else None
                db.create_or_update_post(user["id"], user["nickname"], today_str, photo_bytes, caption)
                st.toast("인증샷을 올렸어요!", icon="📸")
                st.rerun()

    st.divider()
    posts = db.get_feed_posts(limit=50)
    if not posts:
        st.info("아직 올라온 인증샷이 없어요. 첫 인증샷의 주인공이 되어보세요!")
        return

    is_admin = db.is_admin(user["username"])

    for p in posts:
        post_id = str(p["_id"])
        is_mine = p["user_id"] == user["id"]
        with st.container(border=True):
            mine_tag = " · 나" if is_mine else ""
            st.markdown(f"**{p['nickname']}**{mine_tag} · {p['date']}")
            if p.get("photo_b64"):
                st.image(base64.b64decode(p["photo_b64"]), use_container_width=True)
            if p.get("caption"):
                st.markdown(p["caption"])

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

            comments = p.get("comments", [])
            if comments:
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

            if is_mine or is_admin:
                if st.button("🗑️ 게시물 삭제", key=f"delpost_{post_id}"):
                    db.delete_post(p["_id"], user["id"], is_admin)
                    st.toast("삭제했어요.", icon="🗑️")
                    st.rerun()


# ================= 라우팅 =================
if "user" not in st.session_state:
    render_auth()
else:
    _user = st.session_state["user"]
    _admin = db.is_admin(_user["username"])
    _page = render_topnav(_user, _admin)

    if _page == "mypage":
        render_mypage(_user)
    elif _page == "feed":
        render_feed(_user)
    elif _page == "ranking":
        render_ranking(_user)
    elif _page == "contact":
        render_contact(_user)
    elif _page == "admin" and _admin:
        render_admin(_user)
    else:
        st.session_state["page"] = "today"
        render_today(_user)
