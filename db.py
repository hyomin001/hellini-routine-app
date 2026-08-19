# -*- coding: utf-8 -*-
"""
MongoDB 데이터 계층.
연결 정보는 st.secrets["MONGO_URI"] 에서 읽는다 (.streamlit/secrets.toml 참고).
"""
from datetime import datetime
from typing import Optional

import streamlit as st
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId

from utils.auth import hash_password, verify_password


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


# ================= INQUIRIES =================

CATEGORIES = ["운동 추가 요청", "기능 개선 제안", "버그 신고", "기타"]


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
