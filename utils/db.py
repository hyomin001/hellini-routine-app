# -*- coding: utf-8 -*-
"""
MongoDB 데이터 계층.
연결 정보는 st.secrets["MONGO_URI"] 에서 읽는다 (.streamlit/secrets.toml 참고).
"""
from datetime import datetime, timedelta
from typing import Optional

import streamlit as st
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId

from utils.auth import hash_password, verify_password

# 몇 분 동안 활동(하트비트)이 없으면 '접속 종료'로 볼지
ACTIVE_WINDOW_MINUTES = 5


@st.cache_resource(show_spinner=False)
def get_client() -> MongoClient:
    uri = st.secrets["MONGO_URI"]
    return MongoClient(uri)


def get_db():
    client = get_client()
    return client[st.secrets.get("MONGO_DB_NAME", "hellini_routine")]


def init_indexes():
    db = get_db()
    db.users.create_index("username", unique=True)
    db.users.create_index("nickname", unique=True)
    db.logs.create_index(
        [("user_id", ASCENDING), ("date", ASCENDING), ("exercise_name", ASCENDING)],
        unique=True,
    )
    db.logs.create_index([("exercise_name", ASCENDING)])
    db.inquiries.create_index([("created_at", DESCENDING)])
    db.presence.create_index("user_id", unique=True)
    db.presence.create_index("last_seen")


# ================= USERS =================

def username_exists(username: str) -> bool:
    return get_db().users.find_one({"username": username}) is not None


def nickname_exists(nickname: str) -> bool:
    return get_db().users.find_one({"nickname": nickname}) is not None


def create_user(username: str, password: str, nickname: str):
    username = username.strip()
    nickname = nickname.strip()
    if not username or not password or not nickname:
        return False, "아이디, 비밀번호, 닉네임을 모두 입력해주세요."
    if len(password) < 4:
        return False, "비밀번호는 4자 이상이어야 해요."
    if username_exists(username):
        return False, "이미 사용 중인 아이디예요."
    if nickname_exists(nickname):
        return False, "이미 사용 중인 닉네임이에요."
    salt, pw_hash = hash_password(password)
    get_db().users.insert_one(
        {
            "username": username,
            "salt": salt,
            "pw_hash": pw_hash,
            "nickname": nickname,
            "created_at": datetime.utcnow(),
        }
    )
    return True, "회원가입 완료! 이제 로그인해주세요."


def authenticate(username: str, password: str) -> Optional[dict]:
    user = get_db().users.find_one({"username": username.strip()})
    if not user:
        return None
    if verify_password(password, user["salt"], user["pw_hash"]):
        return user
    return None


def get_user_by_id(user_id: str) -> Optional[dict]:
    try:
        return get_db().users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


def get_total_user_count() -> int:
    return get_db().users.count_documents({})


def list_all_users(limit: int = 1000) -> list:
    return list(get_db().users.find().sort("created_at", DESCENDING).limit(limit))


def delete_user(user_id: str):
    """해당 유저 계정 + 운동 기록을 함께 삭제 (문의 글은 기록으로 남겨둠)."""
    db = get_db()
    db.users.delete_one({"_id": ObjectId(user_id)})
    db.logs.delete_many({"user_id": user_id})
    db.presence.delete_one({"user_id": user_id})


# ================= 관리자 =================

def _admin_usernames() -> set:
    raw = st.secrets.get("ADMIN_USERNAMES", "")
    return {u.strip() for u in raw.split(",") if u.strip()}


def is_admin(username: str) -> bool:
    return username in _admin_usernames()


# ================= 접속 현황 (presence) =================

def touch_presence(user_id: str, username: str, nickname: str):
    """페이지가 로드될 때마다 호출해서 '마지막 활동 시각'을 갱신 (현재 접속자 집계용)."""
    get_db().presence.update_one(
        {"user_id": user_id},
        {"$set": {"username": username, "nickname": nickname, "last_seen": datetime.utcnow()}},
        upsert=True,
    )


def get_active_user_count(minutes: int = ACTIVE_WINDOW_MINUTES) -> int:
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    return get_db().presence.count_documents({"last_seen": {"$gte": cutoff}})


def get_active_users(minutes: int = ACTIVE_WINDOW_MINUTES) -> list:
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    return list(
        get_db().presence.find({"last_seen": {"$gte": cutoff}}).sort("last_seen", DESCENDING)
    )


# ================= LOGS =================

def _clean_sets(sets: list) -> list:
    """빈 값 정리 + 숫자 검증 통과한 세트만 남긴 사본을 반환 (원본 표시용은 그대로 두고 저장은 정리본 사용)"""
    return sets


def has_log_data(sets: list, memo: str = "") -> bool:
    if memo and memo.strip():
        return True
    for s in sets:
        if s.get("w") not in (None, "") and s.get("r") not in (None, ""):
            return True
    return False


def save_exercise_log(user_id: str, date_str: str, exercise_name: str, sets: list, memo: str = ""):
    db = get_db()
    if not has_log_data(sets, memo):
        db.logs.delete_one({"user_id": user_id, "date": date_str, "exercise_name": exercise_name})
        return
    db.logs.update_one(
        {"user_id": user_id, "date": date_str, "exercise_name": exercise_name},
        {
            "$set": {"sets": sets, "memo": memo, "updated_at": datetime.utcnow()},
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )


def get_log_for_date(user_id: str, date_str: str) -> dict:
    docs = get_db().logs.find({"user_id": user_id, "date": date_str})
    return {d["exercise_name"]: {"sets": d["sets"], "memo": d.get("memo", "")} for d in docs}


def get_all_logs(user_id: str) -> list:
    return list(get_db().logs.find({"user_id": user_id}).sort("date", DESCENDING))


def delete_log(user_id: str, date_str: str, exercise_name: str):
    get_db().logs.delete_one({"user_id": user_id, "date": date_str, "exercise_name": exercise_name})


def _best_from_sets(sets: list):
    """세트 목록 중 최고 기록(무게 우선, 같으면 횟수) 하나를 반환"""
    best = None
    for s in sets:
        try:
            w = float(s["w"])
            r = int(s["r"])
        except (KeyError, TypeError, ValueError):
            continue
        if best is None or w > best[0] or (w == best[0] and r > best[1]):
            best = (w, r)
    return best


def get_personal_records(user_id: str) -> dict:
    """{운동명: {weight, reps, date}} - 운동별 개인 최고 기록"""
    pr = {}
    for d in get_all_logs(user_id):
        best = _best_from_sets(d["sets"])
        if best is None:
            continue
        w, r = best
        cur = pr.get(d["exercise_name"])
        if cur is None or w > cur["weight"] or (w == cur["weight"] and r > cur["reps"]):
            pr[d["exercise_name"]] = {"weight": w, "reps": r, "date": d["date"]}
    return pr


# ================= RANKING =================

def get_leaderboard(exercise_name: str, limit: int = 20) -> list:
    """해당 운동에서 유저별 최고 기록을 뽑아 무게→횟수 순으로 정렬한 랭킹"""
    db = get_db()
    docs = list(db.logs.find({"exercise_name": exercise_name}))
    best_per_user = {}
    for d in docs:
        best = _best_from_sets(d["sets"])
        if best is None:
            continue
        w, r = best
        cur = best_per_user.get(d["user_id"])
        if cur is None or w > cur["weight"] or (w == cur["weight"] and r > cur["reps"]):
            best_per_user[d["user_id"]] = {"weight": w, "reps": r, "date": d["date"], "user_id": d["user_id"]}

    if not best_per_user:
        return []

    user_ids = []
    for uid in best_per_user.keys():
        try:
            user_ids.append(ObjectId(uid))
        except Exception:
            pass
    users = {str(u["_id"]): u["nickname"] for u in db.users.find({"_id": {"$in": user_ids}})}

    rows = []
    for uid, rec in best_per_user.items():
        rows.append({"nickname": users.get(uid, "알수없음"), **rec})
    rows.sort(key=lambda r: (-r["weight"], -r["reps"]))
    return rows[:limit]


def get_champions(exercise_names: list) -> dict:
    """운동명 -> 그 운동 1위(최고 무게, 동률이면 최고 횟수) 기록. 기록 없는 운동은 제외."""
    result = {}
    for name in exercise_names:
        top = get_leaderboard(name, limit=1)
        if top:
            result[name] = top[0]
    return result


# ================= INQUIRIES =================

CATEGORIES = ["운동 추가 요청", "기능 개선 제안", "버그 신고", "기타"]
STATUS_OPTIONS = ["접수", "처리중", "완료"]


def add_inquiry(user_id: str, nickname: str, category: str, content: str):
    get_db().inquiries.insert_one(
        {
            "user_id": user_id,
            "nickname": nickname,
            "category": category,
            "content": content.strip(),
            "created_at": datetime.utcnow(),
            "status": "접수",
        }
    )


def get_inquiries(limit: int = 200) -> list:
    return list(get_db().inquiries.find().sort("created_at", DESCENDING).limit(limit))


def update_inquiry_status(inquiry_id, status: str):
    get_db().inquiries.update_one({"_id": ObjectId(inquiry_id)}, {"$set": {"status": status}})


def delete_inquiry(inquiry_id):
    get_db().inquiries.delete_one({"_id": ObjectId(inquiry_id)})


def answer_inquiry(inquiry_id, answer: str):
    """관리자가 문의에 남긴 답변을 저장 (공개 게시판에 함께 노출됨)."""
    get_db().inquiries.update_one(
        {"_id": ObjectId(inquiry_id)},
        {"$set": {"answer": answer.strip(), "answered_at": datetime.utcnow()}},
    )


# ================= 세트 값 검증 =================

def validate_sets(sets: list):
    """무게/횟수가 숫자 형태인지 확인. 하나만 채워진 경우, 숫자가 아닌 경우, 음수인 경우를 걸러낸다."""
    for i, s in enumerate(sets, start=1):
        w, r = s.get("w", ""), s.get("r", "")
        w_filled = w not in (None, "")
        r_filled = r not in (None, "")
        if not w_filled and not r_filled:
            continue
        if w_filled != r_filled:
            return False, f"{i}세트: 무게와 횟수를 둘 다 입력해주세요."
        try:
            wf = float(w)
            ri = int(r)
        except (TypeError, ValueError):
            return False, f"{i}세트: 무게/횟수는 숫자로 입력해주세요."
        if wf < 0 or ri < 0:
            return False, f"{i}세트: 무게/횟수는 0 이상이어야 해요."
    return True, ""


# ================= 계정 설정 (닉네임/비밀번호 변경, 탈퇴) =================

def change_nickname(user_id: str, new_nickname: str):
    new_nickname = new_nickname.strip()
    if not new_nickname:
        return False, "닉네임을 입력해주세요."
    database = get_db()
    other = database.users.find_one({"nickname": new_nickname})
    if other and str(other["_id"]) != user_id:
        return False, "이미 사용 중인 닉네임이에요."
    database.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"nickname": new_nickname}})
    return True, "닉네임을 변경했어요."


def change_password(user_id: str, current_password: str, new_password: str):
    if len(new_password) < 4:
        return False, "새 비밀번호는 4자 이상이어야 해요."
    user = get_user_by_id(user_id)
    if not user or not verify_password(current_password, user["salt"], user["pw_hash"]):
        return False, "현재 비밀번호가 일치하지 않아요."
    salt, pw_hash = hash_password(new_password)
    get_db().users.update_one({"_id": ObjectId(user_id)}, {"$set": {"salt": salt, "pw_hash": pw_hash}})
    return True, "비밀번호를 변경했어요."


def delete_own_account(user_id: str, password: str):
    user = get_user_by_id(user_id)
    if not user or not verify_password(password, user["salt"], user["pw_hash"]):
        return False, "비밀번호가 일치하지 않아요."
    delete_user(user_id)
    return True, "계정을 삭제했어요. 그동안 함께해줘서 고마워요!"


# ================= 개인 통계 (볼륨/스트릭) =================

def get_user_stats(user_id: str, today_str: str) -> dict:
    """총 볼륨(무게×횟수 합), 총 기록일 수, 오늘 기준 연속 기록일(스트릭)."""
    logs = get_all_logs(user_id)
    total_volume = 0.0
    dates = set()
    for d in logs:
        dates.add(d["date"])
        for s in d["sets"]:
            try:
                w = float(s["w"])
                r = int(s["r"])
            except (KeyError, TypeError, ValueError):
                continue
            total_volume += w * r

    streak = 0
    if dates:
        from datetime import date as _date, timedelta as _td

        cur = _date.fromisoformat(today_str)
        if today_str not in dates:
            cur -= _td(days=1)
        while cur.isoformat() in dates:
            streak += 1
            cur -= _td(days=1)

    return {"total_volume": total_volume, "workout_days": len(dates), "streak": streak}


# ================= 총 볼륨 랭킹 =================

def get_volume_leaderboard(limit: int = 20) -> list:
    """전체 유저의 총 볼륨(모든 운동의 무게×횟수 합) 순위."""
    database = get_db()
    totals = {}
    for d in database.logs.find({}, {"user_id": 1, "sets": 1}):
        uid = d["user_id"]
        vol = 0.0
        for s in d["sets"]:
            try:
                w = float(s["w"])
                r = int(s["r"])
            except (KeyError, TypeError, ValueError):
                continue
            vol += w * r
        if vol <= 0:
            continue
        totals[uid] = totals.get(uid, 0.0) + vol

    if not totals:
        return []

    user_ids = []
    for uid in totals:
        try:
            user_ids.append(ObjectId(uid))
        except Exception:
            pass
    users = {str(u["_id"]): u["nickname"] for u in database.users.find({"_id": {"$in": user_ids}})}

    rows = [
        {"user_id": uid, "nickname": users.get(uid, "알수없음"), "total_volume": vol}
        for uid, vol in totals.items()
    ]
    rows.sort(key=lambda r: -r["total_volume"])
    return rows[:limit]


# ================= 전체 통계 (관리자 대시보드) =================

def get_dashboard_stats() -> dict:
    db = get_db()
    return {
        "total_users": db.users.count_documents({}),
        "active_users": get_active_user_count(),
        "total_logs": db.logs.count_documents({}),
        "total_inquiries": db.inquiries.count_documents({}),
        "open_inquiries": db.inquiries.count_documents({"status": {"$ne": "완료"}}),
    }
