# -*- coding: utf-8 -*-
import datetime as dt

import streamlit as st
import streamlit.components.v1 as components

from utils import db
from utils.data import DAYS, exercises_for_day, ALL_EXERCISE_NAMES

st.set_page_config(page_title="헬린이 루틴", page_icon="🏋️", layout="centered")

# 사이드바(메뉴 버튼을 화면 안에서 쓰므로 사이드바 자체를 숨긴다)
st.markdown(
    """
    <style>
    [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

DAY_COLORS = {
    "DAY1": "#FF9F5A",
    "DAY2": "#5AA9FF",
    "DAY3": "#5AFF9F",
    "DAY4": "#FF5A9F",
}


def render_rest_timer():
    """60/90/120초 휴식 타이머. 버튼 클릭도 이 위젯 안에서 순수 JS로 처리되므로
    Streamlit 새로고침 없이 그 자리에서 바로 카운트다운된다 (원본 HTML의 타이머와 동일 동작)."""
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
      const restTimer = {total:0, remaining:0, interval:null};
      document.querySelectorAll('[data-rest]').forEach(function(btn){
        btn.addEventListener('click', function(){ startRest(parseInt(btn.dataset.rest)); });
      });
      function startRest(seconds){
        clearInterval(restTimer.interval);
        restTimer.total = seconds;
        restTimer.remaining = seconds;
        document.getElementById('restBar').classList.add('show');
        document.getElementById('restMsg').textContent = '';
        updateUI();
        restTimer.interval = setInterval(function(){
          restTimer.remaining--;
          if(restTimer.remaining<=0){
            clearInterval(restTimer.interval);
            restTimer.remaining = 0;
            updateUI();
            onDone();
            return;
          }
          updateUI();
        }, 1000);
      }
      function updateUI(){
        const m = Math.floor(restTimer.remaining/60);
        const s = restTimer.remaining%60;
        document.getElementById('restTime').textContent = m+':'+String(s).padStart(2,'0');
        const pct = restTimer.total>0 ? Math.max(0, restTimer.remaining/restTimer.total*100) : 0;
        document.getElementById('restFill').style.width = pct+'%';
      }
      function stopRest(){
        clearInterval(restTimer.interval);
        restTimer.remaining = 0;
        document.getElementById('restBar').classList.remove('show');
      }
      function adjustRest(delta){
        if(restTimer.total<=0) return;
        restTimer.remaining = Math.max(0, restTimer.remaining+delta);
        if(restTimer.remaining > restTimer.total) restTimer.total = restTimer.remaining;
        updateUI();
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

    .exercise-thumb {
        width: 100%;
        max-width: 220px;
        border-radius: 12px;
        margin-bottom: 8px;
    }

    /* ===== 모바일(폰 세로 화면) 최적화 ===== */
    @media (max-width: 480px) {
        .block-container {
            padding-left: 0.9rem !important;
            padding-right: 0.9rem !important;
            padding-top: 1.2rem !important;
        }
        /* 버튼 터치 영역 확보 */
        .stButton > button {
            min-height: 42px;
            font-size: 13.5px !important;
            padding: 6px 6px !important;
        }
        /* 상단 네비게이션/문구 폰트 축소로 줄바꿈 방지 */
        .stCaption, [data-testid="stCaptionContainer"] {
            font-size: 12px !important;
        }
        div[data-testid="stExpander"] summary {
            font-size: 14.5px;
            padding: 10px 12px;
        }
        .progress-chip { font-size: 11px; padding: 3px 9px; }
        .day-badge { font-size: 10.5px; padding: 2px 8px; }
        .exercise-thumb { max-width: 100%; }
        /* 텍스트 입력 인풋 여백 축소로 세트 입력 3열이 덜 답답하게 */
        div[data-testid="stTextInput"] input {
            padding: 6px 8px !important;
            font-size: 14px !important;
        }
        /* 컬럼 사이 간격 축소 (세트 입력, 상단 네비 버튼 등) */
        div[data-testid="stHorizontalBlock"] {
            gap: 0.5rem !important;
        }
        /* DAY 탭 라벨 축소 */
        button[data-baseweb="tab"] {
            font-size: 12.5px !important;
            padding: 8px 10px !important;
        }
    }

    /* ===== Streamlit이 좁은 화면에서 컬럼(가로배치)을 세로로 쌓아버리는 기본 동작을 막는다 =====
       (세트/무게/횟수, 상단 메뉴 버튼 등이 세로로 길게 쌓이는 걸 방지) */
    div[data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: flex-start !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        width: auto !important;
        min-width: 0 !important;
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


# ================= 상단 네비게이션 (버튼식) =================
NAV_PAGES = [
    ("today", "🏠 오늘"),
    ("mypage", "📖 기록"),
    ("ranking", "🏆 랭킹"),
    ("contact", "💬 문의"),
]


def render_topnav(user: dict, admin: bool) -> str:
    db.touch_presence(user["id"], user["username"], user["nickname"])

    pages = NAV_PAGES + ([("admin", "🛠️ 관리")] if admin else [])
    current = st.session_state.get("page", "today")

    chunk = 3
    for i in range(0, len(pages), chunk):
        row = pages[i : i + chunk]
        cols = st.columns(len(row))
        for col, (key, label) in zip(cols, row):
            btn_type = "primary" if key == current else "secondary"
            if col.button(label, key=f"nav_{key}", use_container_width=True, type=btn_type):
                st.session_state["page"] = key
                st.rerun()

    total = db.get_total_user_count()
    active = db.get_active_user_count()
    admin_tag = " · 🛡️ 관리자" if admin else ""
    c1, c2 = st.columns([3, 1])
    c1.caption(f"👋 {user['nickname']}님{admin_tag} · 👥 총 가입자 {total}명 · 🟢 현재 접속 {active}명")
    if c2.button("로그아웃", key="nav_logout", use_container_width=True):
        del st.session_state["user"]
        st.session_state.pop("page", None)
        st.rerun()

    st.divider()
    return current


# ================= 오늘의 루틴 =================
def render_today(user: dict):
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
                        c1, c2, c3 = st.columns([0.9, 1.5, 1.5])
                        c1.markdown(f"<div style='padding-top:8px; font-size:13px; color:#9296A0;'>{i+1}세트</div>", unsafe_allow_html=True)
                        w_val = c2.text_input(
                            "무게", value=str(s.get("w", "")), key=f"{base_key}_w_{i}",
                            label_visibility="collapsed", placeholder="kg",
                        )
                        r_val = c3.text_input(
                            "횟수", value=str(s.get("r", "")), key=f"{base_key}_r_{i}",
                            label_visibility="collapsed", placeholder="회",
                        )
                        new_sets.append({"w": w_val, "r": r_val})

                    render_rest_timer()

                    memo_val = st.text_input(
                        "메모", value=memo_state, key=f"{base_key}_memo",
                        placeholder="컨디션, 폼 체크 등 메모",
                    )

                    if st.button("이 운동 저장", key=f"{base_key}_save", use_container_width=True):
                        db.save_exercise_log(user["id"], date_str, ex["name"], new_sets, memo_val)
                        st.toast(f"{ex['name']} 저장 완료!", icon="✅")
                        st.rerun()


# ================= 마이페이지 =================
def render_mypage(user: dict):
    st.subheader("📖 마이페이지")
    st.caption(f"{user['nickname']}님의 운동 기록")

    tab_pr, tab_history = st.tabs(["🏅 개인 최고기록", "🗓️ 기록 히스토리"])

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

    with tab_history:
        logs = db.get_all_logs(user["id"])
        if not logs:
            st.info("아직 기록이 없어요.")
        else:
            by_date = {}
            for d in logs:
                by_date.setdefault(d["date"], []).append(d)

            for date_str in sorted(by_date.keys(), reverse=True):
                entries = by_date[date_str]
                with st.expander(f"{date_str} · 운동 {len(entries)}개"):
                    for e in entries:
                        valid = [s for s in e["sets"] if s.get("w") not in (None, "") and s.get("r") not in (None, "")]
                        sets_txt = " / ".join(f"{s['w']}kg×{s['r']}회" for s in valid) if valid else "기록 없음"
                        st.markdown(f"**{e['exercise_name']}**  \n{sets_txt}")
                        if e.get("memo"):
                            st.caption(f"메모: {e['memo']}")
                        if st.button("삭제", key=f"del_{e['_id']}"):
                            db.delete_log(user["id"], e["date"], e["exercise_name"])
                            st.rerun()
                        st.markdown("---")


# ================= 랭킹 =================
def render_ranking(user: dict):
    st.subheader("🏆 운동별 랭킹")
    st.caption("가장 무거운 무게로, 같은 무게면 가장 많은 횟수로 든 사람이 1등이에요.")

    my_nickname = user["nickname"]

    tab_champs, tab_detail = st.tabs(["👑 전체 종목 1위", "📋 종목별 TOP 20"])

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


# ================= 관리자 =================
def render_admin(user: dict):
    st.subheader("🛠️ 관리자 페이지")
    st.caption(f"{user['nickname']}님, 어서오세요. 여기는 운영자만 볼 수 있어요.")

    tab_dash, tab_users, tab_inquiries = st.tabs(["📊 대시보드", "👥 회원 관리", "💬 문의 관리"])

    with tab_dash:
        stats = db.get_dashboard_stats()

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


# ================= 라우팅 =================
if "user" not in st.session_state:
    render_auth()
else:
    _user = st.session_state["user"]
    _admin = db.is_admin(_user["username"])
    _page = render_topnav(_user, _admin)

    if _page == "mypage":
        render_mypage(_user)
    elif _page == "ranking":
        render_ranking(_user)
    elif _page == "contact":
        render_contact(_user)
    elif _page == "admin" and _admin:
        render_admin(_user)
    else:
        st.session_state["page"] = "today"
        render_today(_user)
