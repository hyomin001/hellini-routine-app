# -*- coding: utf-8 -*-
"""나만의 루틴, 운동 세션, 체형 기록, 확장 통계 화면."""
from __future__ import annotations

import datetime as dt

import streamlit as st

from utils import db
from utils.data import PARTS, PART_PRESETS
from utils.training import (
    estimate_one_rep_max,
    progression_recommendation,
    recommend_exercises,
    recommend_routine_for_minutes,
    volume_by_part,
    weekly_training_summary,
)


WEEKDAYS = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
PART_NAMES = {part["key"]: part["part"] for part in PARTS}


def _routine_label(routine: dict) -> str:
    return f"{routine.get('name', '루틴')} · {len(routine.get('items', []))}종목"


def _start_session(user: dict, routine: dict, date_str: str):
    session_id = db.start_workout_session(user["id"], routine, date_str)
    st.session_state["active_workout_session_id"] = session_id
    st.session_state["page"] = "session"
    st.rerun()


def render_today_routine_launcher(user: dict, date_str: str):
    """오늘 화면 상단에서 저장 루틴을 불러오거나 세션을 시작한다."""
    routines = db.list_routines(user["id"])
    active = db.get_active_workout_session(user["id"])
    plan = db.get_weekly_plan(user["id"])
    try:
        weekday = dt.date.fromisoformat(date_str).weekday()
    except ValueError:
        weekday = 0
    scheduled_id = plan.get(str(weekday))
    scheduled = next((r for r in routines if str(r["_id"]) == str(scheduled_id)), None)

    with st.container(border=True):
        st.markdown("**🧩 나만의 루틴**")
        if active:
            done = len(active.get("completed_indexes", []))
            total = len(active.get("items", []))
            st.caption(f"진행 중: {active.get('routine_name', '루틴')} · {done}/{total} 완료")
            if st.button("진행 중인 운동 계속하기", use_container_width=True, type="primary", key="today_resume_session"):
                st.session_state["active_workout_session_id"] = str(active["_id"])
                st.session_state["page"] = "session"
                st.rerun()
            return
        if scheduled:
            st.caption(f"📅 {WEEKDAYS[weekday]} 계획: {scheduled['name']}")
        if not routines:
            st.caption("저장한 루틴이 없어요. 루틴 메뉴에서 자주 하는 운동을 묶어보세요.")
            if st.button("첫 루틴 만들기", use_container_width=True, key="today_make_routine"):
                st.session_state["page"] = "routines"
                st.session_state["routine_section"] = "➕ 루틴 만들기"
                st.rerun()
            return

        ids = [str(r["_id"]) for r in routines]
        default_id = str(scheduled["_id"]) if scheduled else ids[0]
        selected_id = st.selectbox(
            "오늘 할 루틴",
            ids,
            index=ids.index(default_id),
            format_func=lambda rid: _routine_label(next(r for r in routines if str(r["_id"]) == rid)),
            key=f"today_routine_{date_str}",
        )
        routine = next(r for r in routines if str(r["_id"]) == selected_id)
        c1, c2 = st.columns(2)
        if c1.button("오늘 화면에 불러오기", use_container_width=True, key=f"load_routine_{date_str}"):
            st.session_state["quick_pick"] = [item["exercise_name"] for item in routine.get("items", [])]
            st.session_state["quick_filter_on"] = True
            st.session_state["loaded_routine_id"] = selected_id
            st.toast(f"{routine['name']}을 불러왔어요.", icon="✅")
            st.rerun()
        if c2.button("순서대로 시작", use_container_width=True, type="primary", key=f"start_routine_{date_str}"):
            _start_session(user, routine, date_str)


def _set_builder(routine: dict | None = None):
    routine = routine or {}
    st.session_state["routine_edit_id"] = str(routine.get("_id", "")) or None
    st.session_state["routine_draft_name"] = routine.get("name", "")
    st.session_state["routine_draft_items"] = [dict(item) for item in routine.get("items", [])]
    st.session_state["routine_builder_nonce"] = st.session_state.get("routine_builder_nonce", 0) + 1
    st.session_state["routine_pending_name"] = routine.get("name", "")
    st.session_state["routine_pending_catalog"] = [item["exercise_name"] for item in routine.get("items", [])]


def _apply_generated_rows(rows: list[dict], routine_name: str):
    """추천 결과를 루틴 초안(세션 상태)에 채워 넣고 화면을 새로고침한다."""
    st.session_state["routine_draft_items"] = [
        {
            "exercise_name": item["name"],
            "source": "official",
            "part": item.get("part", "PART1"),
            "sets": item.get("sets", 3),
            "target_reps": item.get("target_reps", 10),
        }
        for item in rows
    ]
    if not st.session_state.get("routine_draft_name"):
        st.session_state["routine_draft_name"] = routine_name
    st.session_state["routine_name_input"] = st.session_state["routine_draft_name"]
    st.session_state["routine_builder_nonce"] = st.session_state.get("routine_builder_nonce", 0) + 1
    # 추천 결과와 멀티셀렉트의 프론트엔드 상태를 함께 맞춰야
    # 세트/횟수 변경으로 재실행돼도 추천 카드가 사라지지 않는다.
    st.session_state["routine_catalog_select"] = [item["name"] for item in rows]
    st.rerun()


def _render_beginner_generator(catalog: list[dict]):
    """운동 부위·종목을 모르는 사용자가 목표(전신/상체/하체)만 골라 루틴 초안을 만든다.
    '오늘 뭐 할지 정하기'와 같은 추천 로직(recommend_routine_for_minutes)을 그대로 써서
    두 화면의 추천 방식이 갈라지지 않게 한다. 세밀하게 직접 고르고 싶으면 아래에서 펼칠 수 있다."""
    with st.container(border=True):
        st.markdown("**🎲 자동 추천으로 초안 만들기**")
        st.caption("몇 부위, 몇 종목 할지 몰라도 괜찮아요. 목표만 고르면 알아서 채워드려요.")
        preset_buttons = list(PART_PRESETS) + [
            {"key": "custom", "label": "부위 직접 선택", "emoji": "🛠", "minutes": None}
        ]
        for row_start in range(0, len(preset_buttons), 2):
            row = preset_buttons[row_start:row_start + 2]
            with st.container(key=f"evenrow_routine_preset_row{row_start // 2}"):
                row_cols = st.columns(2)
                for col, preset in zip(row_cols, row):
                    label = (
                        f"{preset['emoji']} {preset['label']} · ~{preset['minutes']}분"
                        if preset.get("minutes") else f"{preset['emoji']} {preset['label']}"
                    )
                    if col.button(label, key=f"routine_preset_{preset['key']}", use_container_width=True):
                        if preset["key"] == "custom":
                            st.session_state["routine_beginner_custom_open"] = not st.session_state.get(
                                "routine_beginner_custom_open", False
                            )
                        else:
                            rows = recommend_routine_for_minutes(catalog, preset["parts"], preset["minutes"])
                            _apply_generated_rows(rows, f"{preset['label']} 루틴")

        if st.session_state.get("routine_beginner_custom_open"):
            part_keys = [part["key"] for part in PARTS]
            selected_parts = st.multiselect(
                "오늘 운동할 부위",
                part_keys,
                default=[part_keys[0]],
                format_func=lambda key: PART_NAMES[key],
                key="beginner_recommend_parts",
            )
            available = [
                item for item in catalog
                if item.get("source") == "official" and item.get("active", True) and item.get("part") in selected_parts
            ]
            max_count = min(10, len(available))
            if max_count:
                exercise_count = st.number_input(
                    "몇 종목 할까요?",
                    min_value=1,
                    max_value=max_count,
                    value=min(4, max_count),
                    step=1,
                    help="처음이라면 한 부위당 3~4종목 정도로 시작해보세요.",
                )
                if st.button("이 조건으로 랜덤 추천받기", type="primary", use_container_width=True):
                    rows = recommend_exercises(catalog, selected_parts, int(exercise_count))
                    part_text = "·".join(PART_NAMES[key] for key in selected_parts)
                    _apply_generated_rows(rows, f"{part_text} 추천 루틴")
            else:
                st.info("운동할 부위를 하나 이상 선택해주세요.")


def _render_routine_builder(user: dict):
    if "routine_pending_name" in st.session_state:
        st.session_state["routine_name_input"] = st.session_state.pop("routine_pending_name")
    if "routine_pending_catalog" in st.session_state:
        st.session_state["routine_catalog_select"] = st.session_state.pop("routine_pending_catalog")
    catalog = db.get_exercise_catalog(user["id"])
    by_name = {item["name"]: item for item in catalog}
    draft = st.session_state.setdefault("routine_draft_items", [])
    edit_id = st.session_state.get("routine_edit_id")
    st.markdown(f"**{'✏️ 루틴 수정' if edit_id else '➕ 새 루틴'}**")
    _render_beginner_generator(catalog)
    st.session_state.setdefault("routine_name_input", st.session_state.get("routine_draft_name", ""))
    name = st.text_input("루틴 이름", placeholder="예: 가슴 루틴", key="routine_name_input")
    st.session_state["routine_draft_name"] = name

    labels = {}
    for item in catalog:
        badge = "공식" if item.get("source") == "official" else "내 운동"
        equipment = item.get("equip") or "기구 없음/미지정"
        labels[item["name"]] = f"{badge} · {PART_NAMES.get(item.get('part'), '기타')} · {item['name']} · {equipment}"
    current_names = [item["exercise_name"] for item in draft if item["exercise_name"] in by_name]
    select_args = {
        "label": "운동 선택",
        "options": list(by_name),
        "format_func": lambda n: labels[n],
        "key": "routine_catalog_select",
        "placeholder": "원하는 운동을 골라주세요",
    }
    if "routine_catalog_select" not in st.session_state:
        select_args["default"] = current_names
    selected_names = st.multiselect(**select_args)
    if selected_names != current_names:
        previous = {item["exercise_name"]: item for item in draft}
        draft = []
        for exercise_name in selected_names:
            item = by_name[exercise_name]
            draft.append(
                dict(
                    previous.get(exercise_name)
                    or {
                        "exercise_name": exercise_name,
                        "source": item.get("source", "official"),
                        "part": item.get("part", "PART1"),
                        "sets": item.get("sets", 3),
                        "target_reps": item.get("target_reps", 10),
                    }
                )
            )
        st.session_state["routine_draft_items"] = draft

    if draft:
        nonce = st.session_state.get("routine_builder_nonce", 0)
        configured = []
        for index, item in enumerate(draft, start=1):
            detail = by_name.get(item["exercise_name"], {})
            with st.container(border=True):
                badge = "공식 운동" if item.get("source") == "official" else "내 운동"
                st.markdown(f"**{index}. {item['exercise_name']}** · {badge}")
                st.caption(
                    f"부위: {PART_NAMES.get(item.get('part'), '기타')} · "
                    f"기구: {detail.get('equip') or '기구 없음/미지정'}"
                )
                if detail.get("howto") or detail.get("tip"):
                    with st.expander("운동 방법 보기"):
                        if detail.get("howto"):
                            st.markdown("\n".join(f"{i + 1}. {step}" for i, step in enumerate(detail["howto"])))
                        if detail.get("tip"):
                            st.info(detail["tip"])
                order = st.selectbox(
                    "운동 순서",
                    list(range(1, len(draft) + 1)),
                    index=index - 1,
                    key=f"routine_order_{nonce}_{item['exercise_name']}",
                )
                c1, c2 = st.columns(2)
                sets = c1.number_input(
                    "기본 세트",
                    1,
                    20,
                    int(item.get("sets", 3)),
                    key=f"routine_sets_{nonce}_{item['exercise_name']}",
                )
                target = c2.number_input(
                    "목표 횟수",
                    1,
                    1000,
                    int(item.get("target_reps", 10)),
                    key=f"routine_reps_{nonce}_{item['exercise_name']}",
                )
                configured.append((order, index, {**item, "sets": int(sets), "target_reps": int(target)}))
        save_items = [row for _, _, row in sorted(configured, key=lambda value: (value[0], value[1]))]
        configured_by_name = {row["exercise_name"]: row for _, _, row in configured}
        st.session_state["routine_draft_items"] = [configured_by_name[item["exercise_name"]] for item in draft]
    else:
        save_items = []
        st.caption("전체 운동 목록에서 원하는 운동을 선택하면 순서·세트·목표 횟수를 설정할 수 있어요.")

    c1, c2 = st.columns(2)
    if c1.button("루틴 저장", type="primary", use_container_width=True, key="save_routine_builder"):
        ok, msg, _ = db.save_routine(user["id"], name, save_items, edit_id)
        if ok:
            st.toast(msg, icon="✅")
            _set_builder()
            st.rerun()
        st.error(msg)
    if c2.button("입력 초기화", use_container_width=True, key="reset_routine_builder"):
        _set_builder()
        st.rerun()


def _render_routine_list(user: dict, date_str: str):
    routines = db.list_routines(user["id"])
    if not routines:
        st.info("아직 저장한 루틴이 없어요. 아래에서 첫 루틴을 만들어보세요.")
    for routine in routines:
        rid = str(routine["_id"])
        with st.container(border=True):
            st.markdown(f"**{routine['name']}** · {len(routine.get('items', []))}종목")
            st.caption(" → ".join(item["exercise_name"] for item in routine.get("items", [])))
            if st.button("순서대로 시작", key=f"routine_start_{rid}", use_container_width=True, type="primary"):
                _start_session(user, routine, date_str)
            c1, c2 = st.columns(2)
            if c2.button("오늘에 불러오기", key=f"routine_load_{rid}", use_container_width=True):
                st.session_state["quick_pick"] = [item["exercise_name"] for item in routine.get("items", [])]
                st.session_state["quick_filter_on"] = True
                st.session_state["loaded_routine_id"] = rid
                st.session_state["page"] = "today"
                st.rerun()
            if c1.button("수정", key=f"routine_edit_{rid}", use_container_width=True):
                _set_builder(routine)
                st.session_state["routine_section"] = "➕ 루틴 만들기"
                st.rerun()
            d1, d2 = st.columns(2)
            if d1.button("복제", key=f"routine_copy_{rid}", use_container_width=True):
                ok, msg, _ = db.duplicate_routine(rid, user["id"])
                (st.toast if ok else st.error)(msg)
                if ok:
                    st.rerun()
            confirm_key = f"routine_delete_confirm_{rid}"
            if st.session_state.get(confirm_key):
                if d2.button("정말 삭제", key=f"routine_delete_final_{rid}", use_container_width=True, type="primary"):
                    db.delete_routine(rid, user["id"])
                    st.session_state.pop(confirm_key, None)
                    st.rerun()
            elif d2.button("삭제", key=f"routine_delete_{rid}", use_container_width=True):
                st.session_state[confirm_key] = True
                st.rerun()


def _render_weekly_plan(user: dict):
    routines = db.list_routines(user["id"])
    if not routines:
        st.info("루틴을 먼저 하나 이상 저장해주세요.")
        return
    routine_map = {str(r["_id"]): r for r in routines}
    options = [""] + list(routine_map)
    current = db.get_weekly_plan(user["id"])
    schedule = {}
    for day, weekday_name in enumerate(WEEKDAYS):
        current_id = current.get(str(day), "")
        if current_id not in options:
            current_id = ""
        schedule[str(day)] = st.selectbox(
            weekday_name,
            options,
            index=options.index(current_id),
            format_func=lambda rid: "쉬는 날 / 미정" if not rid else routine_map[rid]["name"],
            key=f"weekly_plan_{day}",
        )
    if st.button("주간 계획 저장", type="primary", use_container_width=True):
        db.save_weekly_plan(user["id"], schedule)
        st.success("주간 계획을 저장했어요.")


def _render_custom_exercises(user: dict):
    catalog = db.get_exercise_catalog(user["id"], include_inactive=True)
    custom = [item for item in catalog if item.get("source") == "custom"]
    options = [""] + [item["name"] for item in custom]
    choice = st.selectbox("새 운동 만들기 / 기존 운동 수정", options, format_func=lambda x: "➕ 새 운동" if not x else f"✏️ {x}")
    selected = next((item for item in custom if item["name"] == choice), {})
    with st.form("custom_exercise_form"):
        name = st.text_input("운동 이름", value=selected.get("name", ""))
        part_keys = [p["key"] for p in PARTS]
        part = st.selectbox(
            "운동 부위",
            part_keys,
            index=part_keys.index(selected.get("part", "PART1")) if selected.get("part", "PART1") in part_keys else 0,
            format_func=lambda key: PART_NAMES[key],
        )
        c1, c2 = st.columns(2)
        sets = c1.number_input("기본 세트", 1, 20, int(selected.get("sets", 3)))
        target = c2.number_input("목표 횟수", 1, 1000, int(selected.get("target_reps", 10)))
        equip = st.text_input("필요 기구", value=selected.get("equip", ""))
        tip = st.text_area("방법·메모", value=selected.get("tip", ""))
        submitted = st.form_submit_button("내 운동 저장", use_container_width=True)
    if submitted:
        ok, msg, _ = db.save_catalog_exercise(
            "user",
            user["id"],
            {"name": name, "part": part, "sets": sets, "target_reps": target, "equip": equip, "tip": tip},
            selected.get("_db_id"),
        )
        if ok:
            st.success(msg)
            st.rerun()
        st.error(msg)
    if selected.get("_db_id") and st.button("이 운동 삭제", use_container_width=True):
        db.delete_catalog_exercise(selected["_db_id"], user["id"])
        st.rerun()


def render_routines_page(user: dict, date_str: str):
    st.subheader("🧩 나만의 루틴")
    st.caption("원하는 운동만 골라 저장하고, 지난 기록을 불러와 순서대로 운동해보세요.")
    routine_menu = st.selectbox(
        "루틴 메뉴",
        ["📋 저장 루틴", "➕ 루틴 만들기", "📅 주간 계획", "✍️ 내 운동"],
        key="routine_section",
    )
    if routine_menu == "📋 저장 루틴":
        _render_routine_list(user, date_str)
    if routine_menu == "➕ 루틴 만들기":
        _render_routine_builder(user)
    if routine_menu == "📅 주간 계획":
        _render_weekly_plan(user)
    if routine_menu == "✍️ 내 운동":
        _render_custom_exercises(user)


def render_workout_session(user: dict, date_str: str, render_timer):
    """현재 운동 하나에 집중하는 순차 진행 화면."""
    session_id = st.session_state.get("active_workout_session_id")
    session = db.get_workout_session(session_id, user["id"]) if session_id else db.get_active_workout_session(user["id"])
    if not session or session.get("status") != "active":
        st.warning("진행 중인 루틴이 없어요.")
        if st.button("루틴으로 이동", use_container_width=True):
            st.session_state["page"] = "routines"
            st.rerun()
        return
    session_id = str(session["_id"])
    st.session_state["active_workout_session_id"] = session_id
    date_str = session.get("date") or date_str
    items = session.get("items", [])
    if not items:
        st.error("이 루틴에는 운동이 없어요.")
        return
    index = min(max(0, int(session.get("current_index", 0))), len(items) - 1)
    completed = set(session.get("completed_indexes", []))
    item = items[index]
    name = item["exercise_name"]
    exercise = next((row for row in db.get_exercise_catalog(user["id"], include_inactive=True) if row["name"] == name), {})

    st.subheader(f"🏋️ {session.get('routine_name', '운동 세션')}")
    st.progress(len(completed) / len(items), text=f"{len(completed)}/{len(items)} 완료 · 현재 {index + 1}/{len(items)}")
    st.caption(" → ".join(("✅ " if i in completed else "") + row["exercise_name"] for i, row in enumerate(items)))
    st.markdown(f"### {index + 1}. {name}")
    st.caption(f"{PART_NAMES.get(item.get('part'), '기타')} · {item.get('sets', 3)}세트 · 목표 {item.get('target_reps', 10)}회")
    if exercise.get("img_path"):
        try:
            st.image(exercise["img_path"], width=260)
        except Exception:
            pass
    if exercise.get("howto"):
        with st.expander("동작 방법 보기"):
            st.markdown("\n".join(f"{i + 1}. {step}" for i, step in enumerate(exercise["howto"])))
            if exercise.get("caution"):
                st.warning(exercise["caution"])
            if exercise.get("tip"):
                st.info(exercise["tip"])

    previous = db.get_previous_exercise_log(user["id"], name, date_str)
    current = db.get_db().logs.find_one({"user_id": user["id"], "date": date_str, "exercise_name": name})
    prefix = f"session_{session_id}_{index}"
    if previous:
        prev_text = " / ".join(f"{s.get('w', '-')}kg×{s.get('r', '-')}회" for s in previous.get("sets", []))
        st.info(f"지난 기록 ({previous.get('date')}): {prev_text}")
        rec = progression_recommendation(
            previous.get("sets", []),
            item.get("target_reps", 10),
            expected_sets=int(item.get("sets", 3)),
        )
        st.caption("📈 " + rec["message"])
        if st.button("지난 기록 그대로 채우기", use_container_width=True, key=f"{prefix}_copy"):
            for set_index in range(int(item.get("sets", 3))):
                source = previous.get("sets", [])[set_index] if set_index < len(previous.get("sets", [])) else {"w": "", "r": ""}
                st.session_state[f"{prefix}_w_{set_index}"] = str(source.get("w", ""))
                st.session_state[f"{prefix}_r_{set_index}"] = str(source.get("r", ""))
            st.rerun()
    else:
        st.caption("이 운동의 지난 기록이 없어요. 오늘 기록부터 추천이 시작돼요.")

    existing_sets = current.get("sets", []) if current else []
    new_sets = []
    for set_index in range(int(item.get("sets", 3))):
        old = existing_sets[set_index] if set_index < len(existing_sets) else {"w": "", "r": ""}
        with st.container(key=f"setrow_session_{session_id}_{index}_{set_index}"):
            c1, c2, c3 = st.columns([0.8, 1.5, 1.5])
            c1.markdown(f"**{set_index + 1}세트**")
            weight = c2.text_input("무게", value=str(old.get("w", "")), key=f"{prefix}_w_{set_index}", label_visibility="collapsed", placeholder="kg")
            reps = c3.text_input("횟수", value=str(old.get("r", "")), key=f"{prefix}_r_{set_index}", label_visibility="collapsed", placeholder="회")
        new_sets.append({"w": weight, "r": reps})
    memo = st.text_input("메모", value=current.get("memo", "") if current else "", key=f"{prefix}_memo")
    render_timer()

    if st.button("기록 저장하고 완료", type="primary", use_container_width=True, key=f"{prefix}_save"):
        ok, message = db.validate_sets(new_sets)
        if not ok:
            st.error(message)
        elif not db.has_log_data(new_sets, memo):
            st.error("세트 기록이나 메모를 입력해주세요.")
        else:
            db.save_exercise_log(user["id"], date_str, name, new_sets, memo)
            next_index = min(index + 1, len(items) - 1)
            db.update_workout_session(session_id, user["id"], current_index=next_index, completed_index=index)
            st.toast(f"{name} 완료!", icon="✅")
            st.rerun()

    n1, n2 = st.columns(2)
    if n1.button("← 이전 운동", disabled=index == 0, use_container_width=True):
        db.update_workout_session(session_id, user["id"], current_index=index - 1)
        st.rerun()
    if n2.button("다음 운동 →", disabled=index >= len(items) - 1, use_container_width=True):
        db.update_workout_session(session_id, user["id"], current_index=index + 1)
        st.rerun()

    st.divider()
    confirm_key = f"finish_session_{session_id}"
    if st.session_state.get(confirm_key):
        st.warning(f"현재 {len(completed)}/{len(items)}종목 완료했어요. 세션을 종료할까요?")
        f1, f2 = st.columns(2)
        if f1.button("운동 세션 종료", type="primary", use_container_width=True):
            db.finish_workout_session(session_id, user["id"])
            st.session_state.pop(confirm_key, None)
            st.session_state.pop("active_workout_session_id", None)
            st.session_state["page"] = "mypage"
            st.toast("오늘 운동 세션을 종료했어요!", icon="🎉")
            st.rerun()
        if f2.button("계속 운동", use_container_width=True):
            st.session_state.pop(confirm_key, None)
            st.rerun()
    elif st.button("오늘 운동 종료", use_container_width=True):
        st.session_state[confirm_key] = True
        st.rerun()


def render_body_metrics(user: dict, date_str: str):
    st.markdown("**⚖️ 몸무게·체형 기록**")
    metric_date = st.date_input("측정일", value=dt.date.fromisoformat(date_str), key="body_metric_date")
    date_key = metric_date.isoformat()
    existing = db.get_body_metric(user["id"], date_key) or {}
    with st.form(f"body_metric_form_{date_key}"):
        weight = st.number_input(
            "체중(kg)", min_value=0.0, max_value=500.0, value=float(existing.get("weight") or 0), step=0.1,
            key=f"body_weight_{date_key}",
        )
        muscle = st.number_input(
            "골격근량(kg)", min_value=0.0, max_value=500.0, value=float(existing.get("muscle_mass") or 0), step=0.1,
            key=f"body_muscle_{date_key}",
        )
        body_fat = st.number_input(
            "체지방률(%)", min_value=0.0, max_value=100.0, value=float(existing.get("body_fat") or 0), step=0.1,
            key=f"body_fat_{date_key}",
        )
        memo = st.text_input(
            "메모", value=existing.get("memo", ""), placeholder="예: 아침 공복 측정",
            key=f"body_memo_{date_key}",
        )
        submitted = st.form_submit_button("체형 기록 저장", use_container_width=True)
    if submitted:
        ok, message = db.save_body_metric(
            user["id"], metric_date.isoformat(), weight or None, muscle or None, body_fat or None, memo
        )
        if ok:
            st.success(message)
            st.rerun()
        st.error(message)

    rows = db.get_body_metrics(user["id"])
    if not rows:
        st.caption("아직 체형 기록이 없어요.")
        return
    chart_data = [
        {
            "날짜": row["date"],
            "체중": row.get("weight"),
            "골격근량": row.get("muscle_mass"),
            "체지방률": row.get("body_fat"),
        }
        for row in rows
    ]
    st.line_chart(chart_data, x="날짜", y=["체중", "골격근량", "체지방률"])
    latest = rows[-1]
    st.caption(
        f"최근 측정 {latest['date']} · 체중 {latest.get('weight') or '-'}kg · "
        f"골격근량 {latest.get('muscle_mass') or '-'}kg · 체지방률 {latest.get('body_fat') or '-'}%"
    )
    if st.button("최근 체형 기록 삭제", use_container_width=True):
        db.delete_body_metric(user["id"], latest["date"])
        st.rerun()


def render_training_insights(user: dict, date_str: str):
    logs = db.get_all_logs(user["id"])
    cardio = db.get_all_cardio_logs(user["id"])
    summary = weekly_training_summary(logs, cardio, dt.date.fromisoformat(date_str))
    st.markdown("**📊 이번 주 vs 지난주**")
    c1, c2, c3 = st.columns(3)
    c1.metric("운동일", f"{summary['current_days']}일", delta=f"{summary['days_change']:+d}일")
    c2.metric("근력 볼륨", f"{summary['current_volume']:,.0f}kg", delta=f"{summary['volume_change']:+,.0f}kg")
    c3.metric("지난주 운동일", f"{summary['previous_days']}일")

    catalog = db.get_exercise_catalog(user["id"], include_inactive=True)
    part_map = {item["name"]: PART_NAMES.get(item.get("part"), "기타") for item in catalog}
    part_volumes = volume_by_part(logs, part_map)
    if part_volumes:
        st.markdown("**부위별 누적 볼륨**")
        st.bar_chart(
            [{"부위": part, "볼륨": value} for part, value in part_volumes.items()],
            x="부위",
            y="볼륨",
        )

    records = db.get_personal_records(user["id"])
    if records:
        one_rm_rows = []
        for name, record in records.items():
            one_rm_rows.append(
                {
                    "운동": name,
                    "최고 기록": f"{record['weight']:g}kg × {record['reps']}회",
                    "예상 1RM": round(estimate_one_rep_max(record["weight"], record["reps"]), 1),
                }
            )
        one_rm_rows.sort(key=lambda row: -row["예상 1RM"])
        st.markdown("**예상 1RM (Epley 공식)**")
        st.dataframe(one_rm_rows, use_container_width=True, hide_index=True)
        st.caption("예상값은 참고용이며, 무리해서 실제 1회 최대 중량을 시험하지 마세요.")


def render_admin_exercise_editor():
    """관리자가 JSON 수정 없이 공식 운동 정보를 추가·수정한다."""
    catalog = [item for item in db.get_exercise_catalog(None, include_inactive=True) if item.get("source") == "official"]
    options = [""] + [item["name"] for item in catalog]
    choice = st.selectbox("공식 운동 추가 / 수정", options, format_func=lambda x: "➕ 새 공식 운동" if not x else f"✏️ {x}")
    selected = next((item for item in catalog if item["name"] == choice), {})
    base_name = selected.get("base_name") if choice else None
    with st.form("admin_exercise_form"):
        name = st.text_input("운동 이름", value=selected.get("name", ""), disabled=bool(base_name))
        part_keys = [p["key"] for p in PARTS]
        current_part = selected.get("part", "PART1")
        part = st.selectbox("부위", part_keys, index=part_keys.index(current_part) if current_part in part_keys else 0, format_func=lambda key: PART_NAMES[key])
        c1, c2 = st.columns(2)
        sets = c1.number_input("기본 세트", 1, 20, int(selected.get("sets", 3)))
        target = c2.number_input("목표 횟수", 1, 1000, int(selected.get("target_reps", 10)))
        equip = st.text_input("기구", value=selected.get("equip", ""))
        img_path = st.text_input(
            "운동 이미지 경로 또는 URL",
            value=selected.get("img_path") or "",
            placeholder="assets/exercises/image1.jpg 또는 https://...",
        )
        uploaded_image = st.file_uploader("또는 이미지 직접 업로드", type=["jpg", "jpeg", "png", "webp"])
        howto = st.text_area("운동 방법 (한 줄에 한 단계)", value="\n".join(selected.get("howto", [])))
        caution = st.text_area("주의사항", value=selected.get("caution", ""))
        tip = st.text_area("팁", value=selected.get("tip", ""))
        active = st.checkbox("사용자에게 표시", value=selected.get("active", True))
        submitted = st.form_submit_button("공식 운동 저장", use_container_width=True)
    if submitted:
        image_value = img_path
        if uploaded_image is not None:
            try:
                image_value = "data:image/jpeg;base64," + db.compress_photo_to_b64(uploaded_image.getvalue())
            except Exception:
                st.error("이미지를 읽지 못했어요. JPG·PNG·WEBP 파일인지 확인해주세요.")
                return
        ok, message, _ = db.save_catalog_exercise(
            "official",
            None,
            {
                "name": name,
                "part": part,
                "sets": sets,
                "target_reps": target,
                "equip": equip,
                "img_path": image_value,
                "howto": howto.splitlines(),
                "caution": caution,
                "tip": tip,
                "active": active,
            },
            selected.get("_db_id"),
            base_name=base_name,
        )
        if ok:
            st.success(message)
            st.rerun()
        st.error(message)
