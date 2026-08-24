# -*- coding: utf-8 -*-
"""
MongoDB 데이터 계층.
연결 정보는 st.secrets["MONGO_URI"] 에서 읽는다 (.streamlit/secrets.toml 참고).
"""
import base64
import io
import secrets as _secrets
import string as _string
from datetime import datetime, timedelta
from typing import Optional

import streamlit as st
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from PIL import Image, ImageOps

from utils.auth import hash_password, verify_password
from utils.training import normalize_routine_items, parse_target_reps

# 비밀번호 찾기용 보안 질문 목록 (회원가입 시 하나 선택)
SECURITY_QUESTIONS = [
    "어릴 적 별명은?",
    "가장 좋아하는 음식은?",
    "첫 반려동물(또는 갖고 싶은 동물) 이름은?",
    "태어난 도시는?",
]

# 몇 분 동안 활동(하트비트)이 없으면 '접속 종료'로 볼지
ACTIVE_WINDOW_MINUTES = 5


@st.cache_resource(show_spinner=False)
def get_client() -> MongoClient:
    """MongoDB 클라이언트를 생성해 캐시한다(st.cache_resource로 앱 실행 중 커넥션을 재사용)."""
    uri = st.secrets["MONGO_URI"]
    return MongoClient(uri)


def get_db():
    """기본 데이터베이스 객체를 반환한다."""
    client = get_client()
    return client[st.secrets.get("MONGO_DB_NAME", "hellini_routine")]


def init_indexes():
    """자주 조회하는 컬렉션들에 필요한 인덱스를 생성한다(이미 있으면 무시된다)."""
    db = get_db()
    db.users.create_index("username", unique=True)
    db.users.create_index("nickname", unique=True)
    db.logs.create_index(
        [("user_id", ASCENDING), ("date", ASCENDING), ("exercise_name", ASCENDING)],
        unique=True,
    )
    db.logs.create_index([("exercise_name", ASCENDING)])
    db.cardio_logs.create_index(
        [("user_id", ASCENDING), ("date", ASCENDING), ("exercise_name", ASCENDING)],
        unique=True,
    )
    db.cardio_logs.create_index([("exercise_name", ASCENDING)])
    db.inquiries.create_index([("created_at", DESCENDING)])
    db.presence.create_index("user_id", unique=True)
    db.presence.create_index("last_seen")
    db.routines.create_index([("user_id", ASCENDING), ("name", ASCENDING)], unique=True)
    db.routines.create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)])
    db.weekly_plans.create_index("user_id", unique=True)
    db.body_metrics.create_index([("user_id", ASCENDING), ("date", ASCENDING)], unique=True)
    db.exercise_catalog.create_index([("scope", ASCENDING), ("user_id", ASCENDING), ("name", ASCENDING)])
    db.workout_sessions.create_index([("user_id", ASCENDING), ("status", ASCENDING), ("started_at", DESCENDING)])

    # ---- 게시판 스키마 변경 (v2) ----
    # 예전에는 "하루 1인 1게시글(인증샷)" 구조라 (user_id, date) 유니크 인덱스가 있었지만,
    # 이제는 자유/운동/정보/인증샷 등 여러 게시판에 자유롭게 여러 글을 쓸 수 있게 바뀌어서
    # 더 이상 유니크 제약이 맞지 않는다. 예전에 이미 생성된 인덱스가 남아있으면 새 글 작성이
    # 막혀버리므로, 있으면 지우고 새 인덱스 구성으로 교체한다.
    try:
        db.posts.drop_index("user_id_1_date_1")
    except Exception:
        pass
    db.posts.create_index([("category", ASCENDING), ("created_at", DESCENDING)])
    db.posts.create_index([("created_at", DESCENDING)])

    # 예전 인증샷 게시글(카테고리/제목 필드가 없는 문서)을 새 스키마로 한 번만 이관.
    # 이미 이관된 문서는 category 필드가 있어서 조건에 안 걸리므로 매번 실행돼도 비용이 거의 없다.
    db.posts.update_many(
        {"category": {"$exists": False}},
        [
            {
                "$set": {
                    "category": "cert",
                    "title": {"$ifNull": ["$caption", "인증샷"]},
                    "content": {"$ifNull": ["$caption", ""]},
                    "views": {"$ifNull": ["$views", 0]},
                }
            }
        ],
    )


# ================= USERS =================

def username_exists(username: str) -> bool:
    """해당 아이디로 가입된 회원이 이미 있는지 확인한다."""
    return get_db().users.find_one({"username": username}) is not None


def nickname_exists(nickname: str) -> bool:
    """해당 닉네임을 사용 중인 회원이 이미 있는지 확인한다."""
    return get_db().users.find_one({"nickname": nickname}) is not None


def create_user(
    username: str,
    password: str,
    nickname: str,
    security_question: Optional[str] = None,
    security_answer: Optional[str] = None,
):
    """신규 회원을 생성한다. 비밀번호 해시 처리와 보안 질문 저장을 포함한다."""
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
    doc = {
        "username": username,
        "salt": salt,
        "pw_hash": pw_hash,
        "nickname": nickname,
        "created_at": datetime.utcnow(),
    }
    if security_question and security_answer and security_answer.strip():
        ans_salt, ans_hash = hash_password(security_answer.strip().lower())
        doc["security_question"] = security_question
        doc["security_answer_salt"] = ans_salt
        doc["security_answer_hash"] = ans_hash
    get_db().users.insert_one(doc)
    return True, "회원가입 완료! 이제 로그인해주세요."


def authenticate(username: str, password: str) -> Optional[dict]:
    """아이디/비밀번호로 로그인 인증을 수행하고, 성공하면 사용자 문서를 반환한다(실패 시 None)."""
    user = get_db().users.find_one({"username": username.strip()})
    if not user:
        return None
    if verify_password(password, user["salt"], user["pw_hash"]):
        return user
    return None


def get_user_by_id(user_id: str) -> Optional[dict]:
    """user_id로 사용자 문서를 조회한다."""
    try:
        return get_db().users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


def get_total_user_count() -> int:
    """전체 가입자 수를 반환한다."""
    return get_db().users.count_documents({})


def list_all_users(limit: int = 1000) -> list:
    """관리자 페이지에서 쓰는 전체 회원 목록을 반환한다."""
    return list(get_db().users.find().sort("created_at", DESCENDING).limit(limit))


def delete_user(user_id: str):
    """해당 유저 계정 + 운동 기록을 함께 삭제 (문의 글은 기록으로 남겨둠)."""
    db = get_db()
    db.users.delete_one({"_id": ObjectId(user_id)})
    db.logs.delete_many({"user_id": user_id})
    db.cardio_logs.delete_many({"user_id": user_id})
    db.presence.delete_one({"user_id": user_id})
    db.routines.delete_many({"user_id": user_id})
    db.weekly_plans.delete_one({"user_id": user_id})
    db.body_metrics.delete_many({"user_id": user_id})
    db.exercise_catalog.delete_many({"scope": "user", "user_id": user_id})
    db.workout_sessions.delete_many({"user_id": user_id})


# ================= 비밀번호 찾기 (보안 질문) =================

def get_security_question(username: str) -> Optional[str]:
    """해당 아이디에 등록된 보안 질문을 반환. 아이디가 없거나 질문이 없으면 None."""
    user = get_db().users.find_one({"username": username.strip()})
    if not user:
        return None
    return user.get("security_question")


def reset_password_with_security(username: str, answer: str, new_password: str):
    """보안 질문에 대한 답을 확인한 뒤 비밀번호를 재설정한다."""
    user = get_db().users.find_one({"username": username.strip()})
    if not user or not user.get("security_answer_hash"):
        return False, "본인 확인 정보가 없는 계정이에요. 운영자에게 문의해주세요."
    if len(new_password) < 4:
        return False, "새 비밀번호는 4자 이상이어야 해요."
    ok = verify_password(
        (answer or "").strip().lower(),
        user["security_answer_salt"],
        user["security_answer_hash"],
    )
    if not ok:
        return False, "답변이 일치하지 않아요."
    salt, pw_hash = hash_password(new_password)
    get_db().users.update_one({"_id": user["_id"]}, {"$set": {"salt": salt, "pw_hash": pw_hash}})
    return True, "비밀번호를 재설정했어요. 새 비밀번호로 로그인해주세요."


def admin_reset_password(user_id: str) -> str:
    """관리자가 회원의 비밀번호를 임시 비밀번호로 강제 초기화하고, 그 임시 비밀번호를 반환한다."""
    alphabet = _string.ascii_letters + _string.digits
    temp_password = "".join(_secrets.choice(alphabet) for _ in range(8))
    salt, pw_hash = hash_password(temp_password)
    get_db().users.update_one({"_id": ObjectId(user_id)}, {"$set": {"salt": salt, "pw_hash": pw_hash}})
    return temp_password


# ================= 관리자 =================

def _admin_usernames() -> set:
    """secrets의 ADMIN_USERNAMES 값에 등록된 관리자 아이디 집합을 반환한다."""
    raw = st.secrets.get("ADMIN_USERNAMES", "")
    return {u.strip() for u in raw.split(",") if u.strip()}


def is_admin(username: str) -> bool:
    """해당 아이디가 관리자로 지정되어 있는지 여부를 반환한다."""
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
    """최근 N분 이내 활동(하트비트)이 감지된 접속자 수를 반환한다."""
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    return get_db().presence.count_documents({"last_seen": {"$gte": cutoff}})


def get_active_users(minutes: int = ACTIVE_WINDOW_MINUTES) -> list:
    """최근 N분 이내 접속 중인 사용자 목록을 반환한다."""
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    return list(
        get_db().presence.find({"last_seen": {"$gte": cutoff}}).sort("last_seen", DESCENDING)
    )


# ================= LOGS =================

def _clean_sets(sets: list) -> list:
    """빈 값 정리 + 숫자 검증 통과한 세트만 남긴 사본을 반환 (원본 표시용은 그대로 두고 저장은 정리본 사용)"""
    return sets


def has_log_data(sets: list, memo: str = "") -> bool:
    """세트 기록이나 메모 중 실제로 저장할 값이 있는지 확인한다(빈 기록 저장 방지용)."""
    if memo and memo.strip():
        return True
    for s in sets:
        if s.get("w") not in (None, "") and s.get("r") not in (None, ""):
            return True
    return False


def save_exercise_log(user_id: str, date_str: str, exercise_name: str, sets: list, memo: str = ""):
    """해당 날짜·운동의 세트 기록과 메모를 저장한다(있으면 갱신, 없으면 새로 생성)."""
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
    """특정 날짜, 특정 운동의 기록 하나를 조회한다."""
    docs = get_db().logs.find({"user_id": user_id, "date": date_str})
    return {d["exercise_name"]: {"sets": d["sets"], "memo": d.get("memo", "")} for d in docs}


def get_all_logs(user_id: str) -> list:
    """해당 사용자의 모든 근력 운동(비유산소) 기록을 조회한다."""
    return list(get_db().logs.find({"user_id": user_id}).sort("date", DESCENDING))


def delete_log(user_id: str, date_str: str, exercise_name: str):
    """특정 날짜의 특정 운동 기록을 삭제한다."""
    get_db().logs.delete_one({"user_id": user_id, "date": date_str, "exercise_name": exercise_name})


# ================= 유산소 기록 (CARDIO LOGS) =================
# 근력(logs)과 별도 컬렉션에 저장한다. 구조가 세트×무게×횟수가 아니라
# "시간(분) + (있으면) 거리(km) + (선택) 칼로리 + 메모"라서 근력 로직을 그대로 못 쓴다.

def has_cardio_log_data(duration_min, memo: str = "") -> bool:
    """유산소 기록(시간·메모)에 실제로 저장할 값이 있는지 확인한다."""
    if memo and memo.strip():
        return True
    return duration_min not in (None, "")


def validate_cardio_log(duration_min, distance_km=None, calories=None):
    """시간(분)은 필수, 거리/칼로리는 입력됐을 때만 숫자인지 확인."""
    if duration_min in (None, ""):
        return False, "시간(분)을 입력해주세요."
    try:
        dur = float(duration_min)
    except (TypeError, ValueError):
        return False, "시간(분)은 숫자로 입력해주세요."
    if dur <= 0:
        return False, "시간(분)은 0보다 커야 해요."

    if distance_km not in (None, ""):
        try:
            dist = float(distance_km)
        except (TypeError, ValueError):
            return False, "거리(km)는 숫자로 입력해주세요."
        if dist < 0:
            return False, "거리(km)는 0 이상이어야 해요."

    if calories not in (None, ""):
        try:
            cal = float(calories)
        except (TypeError, ValueError):
            return False, "칼로리는 숫자로 입력해주세요."
        if cal < 0:
            return False, "칼로리는 0 이상이어야 해요."

    return True, ""


def save_cardio_log(
    user_id: str,
    date_str: str,
    exercise_name: str,
    duration_min,
    distance_km=None,
    calories=None,
    memo: str = "",
):
    """해당 날짜·유산소 운동의 시간/거리/칼로리 기록을 저장한다(있으면 갱신, 없으면 새로 생성)."""
    db = get_db()
    if not has_cardio_log_data(duration_min, memo):
        db.cardio_logs.delete_one({"user_id": user_id, "date": date_str, "exercise_name": exercise_name})
        return
    db.cardio_logs.update_one(
        {"user_id": user_id, "date": date_str, "exercise_name": exercise_name},
        {
            "$set": {
                "duration_min": duration_min,
                "distance_km": distance_km if distance_km not in (None, "") else None,
                "calories": calories if calories not in (None, "") else None,
                "memo": memo,
                "updated_at": datetime.utcnow(),
            },
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )


def get_cardio_log_for_date(user_id: str, date_str: str) -> dict:
    """특정 날짜, 특정 유산소 운동의 기록 하나를 조회한다."""
    docs = get_db().cardio_logs.find({"user_id": user_id, "date": date_str})
    return {
        d["exercise_name"]: {
            "duration_min": d.get("duration_min"),
            "distance_km": d.get("distance_km"),
            "calories": d.get("calories"),
            "memo": d.get("memo", ""),
        }
        for d in docs
    }


def get_all_cardio_logs(user_id: str) -> list:
    """해당 사용자의 모든 유산소 운동 기록을 조회한다."""
    return list(get_db().cardio_logs.find({"user_id": user_id}).sort("date", DESCENDING))


def delete_cardio_log(user_id: str, date_str: str, exercise_name: str):
    """특정 날짜의 특정 유산소 운동 기록을 삭제한다."""
    get_db().cardio_logs.delete_one({"user_id": user_id, "date": date_str, "exercise_name": exercise_name})


def get_cardio_personal_records(user_id: str) -> dict:
    """{운동명: {...}} 유산소 개인 최고기록.
    거리 있는 종목: best_distance(최장거리) + best_pace_sec(최고페이스=가장 빠른 기록, 초/km)
    거리 없는 종목: best_duration(최장시간)만 추적."""
    pr = {}
    for d in get_all_cardio_logs(user_id):
        name = d["exercise_name"]
        cur = pr.setdefault(name, {})
        date = d["date"]

        try:
            dur_f = float(d.get("duration_min")) if d.get("duration_min") not in (None, "") else None
        except (TypeError, ValueError):
            dur_f = None
        try:
            dist_f = float(d.get("distance_km")) if d.get("distance_km") not in (None, "") else None
        except (TypeError, ValueError):
            dist_f = None

        if dur_f is not None and (cur.get("best_duration") is None or dur_f > cur["best_duration"]):
            cur["best_duration"] = dur_f
            cur["best_duration_date"] = date

        if dist_f is not None and dist_f > 0:
            if cur.get("best_distance") is None or dist_f > cur["best_distance"]:
                cur["best_distance"] = dist_f
                cur["best_distance_date"] = date
            if dur_f is not None and dur_f > 0:
                pace = dur_f * 60 / dist_f
                if cur.get("best_pace_sec") is None or pace < cur["best_pace_sec"]:
                    cur["best_pace_sec"] = pace
                    cur["best_pace_date"] = date
    return pr


def get_cardio_totals(user_id: str) -> dict:
    """마이페이지 통계용: 총 누적 거리(km) / 총 누적 시간(분). (근력 '총 볼륨'과는 별도 지표)"""
    total_distance = 0.0
    total_duration = 0.0
    for d in get_all_cardio_logs(user_id):
        try:
            total_duration += float(d.get("duration_min") or 0)
        except (TypeError, ValueError):
            pass
        try:
            total_distance += float(d.get("distance_km") or 0)
        except (TypeError, ValueError):
            pass
    return {"total_distance_km": total_distance, "total_duration_min": total_duration}


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


def get_my_exercise_rank(exercise_name: str, user_id: str) -> Optional[int]:
    """TOP20 제한 없이 전체 순위에서 내 등수를 찾는다 (1부터 시작). 기록 없으면 None."""
    rows = get_leaderboard(exercise_name, limit=100000)
    for i, r in enumerate(rows, start=1):
        if r.get("user_id") == user_id:
            return i
    return None


def get_my_volume_rank(user_id: str) -> Optional[int]:
    """전체 회원 중 내 총 볼륨(무게×횟수 합) 순위를 반환한다."""
    rows = get_volume_leaderboard(limit=100000)
    for i, r in enumerate(rows, start=1):
        if r.get("user_id") == user_id:
            return i
    return None


def get_champions(exercise_names: list) -> dict:
    """운동별 1위를 한 번의 기록 조회와 한 번의 회원 조회로 계산한다."""
    names = list(dict.fromkeys(exercise_names or []))
    if not names:
        return {}
    database = get_db()
    best_by_exercise = {}
    for doc in database.logs.find(
        {"exercise_name": {"$in": names}},
        {"exercise_name": 1, "user_id": 1, "date": 1, "sets": 1},
    ):
        best = _best_from_sets(doc.get("sets", []))
        if best is None:
            continue
        weight, reps = best
        name = doc["exercise_name"]
        current = best_by_exercise.get(name)
        candidate = {
            "weight": weight,
            "reps": reps,
            "date": doc.get("date", ""),
            "user_id": doc["user_id"],
        }
        if current is None or weight > current["weight"] or (
            weight == current["weight"] and reps > current["reps"]
        ):
            best_by_exercise[name] = candidate

    user_ids = []
    for uid in {row["user_id"] for row in best_by_exercise.values()}:
        try:
            user_ids.append(ObjectId(uid))
        except Exception:
            pass
    users = {str(row["_id"]): row["nickname"] for row in database.users.find({"_id": {"$in": user_ids}})}
    return {
        name: {**record, "nickname": users.get(record["user_id"], "알수없음")}
        for name, record in best_by_exercise.items()
    }


# ================= INQUIRIES =================

CATEGORIES = ["운동 추가 요청", "기능 개선 제안", "버그 신고", "기타"]
STATUS_OPTIONS = ["접수", "처리중", "완료"]


def add_inquiry(user_id: str, nickname: str, category: str, content: str):
    """새 문의를 등록한다."""
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
    """관리자 페이지에서 쓰는 전체 문의 목록을 조회한다."""
    return list(get_db().inquiries.find().sort("created_at", DESCENDING).limit(limit))


def update_inquiry_status(inquiry_id, status: str):
    """문의 처리 상태를 변경한다(접수 → 처리중 → 완료)."""
    get_db().inquiries.update_one({"_id": ObjectId(inquiry_id)}, {"$set": {"status": status}})


def delete_inquiry(inquiry_id):
    """문의를 삭제한다."""
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
        if wf < 0 or ri <= 0:
            return False, f"{i}세트: 무게는 0 이상, 횟수는 1 이상이어야 해요."
    return True, ""


# ================= 계정 설정 (닉네임/비밀번호 변경, 탈퇴) =================

def change_nickname(user_id: str, new_nickname: str):
    """닉네임을 변경한다(중복 확인 포함)."""
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
    """현재 비밀번호를 확인한 뒤 새 비밀번호로 변경한다."""
    if len(new_password) < 4:
        return False, "새 비밀번호는 4자 이상이어야 해요."
    user = get_user_by_id(user_id)
    if not user or not verify_password(current_password, user["salt"], user["pw_hash"]):
        return False, "현재 비밀번호가 일치하지 않아요."
    salt, pw_hash = hash_password(new_password)
    get_db().users.update_one({"_id": ObjectId(user_id)}, {"$set": {"salt": salt, "pw_hash": pw_hash}})
    return True, "비밀번호를 변경했어요."


def set_security_question(user_id: str, question: str, answer: str):
    """비밀번호 찾기에 쓸 보안 질문과 답을 설정/변경한다."""
    if not question or not answer or not answer.strip():
        return False, "질문과 답변을 모두 입력해주세요."
    ans_salt, ans_hash = hash_password(answer.strip().lower())
    get_db().users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "security_question": question,
                "security_answer_salt": ans_salt,
                "security_answer_hash": ans_hash,
            }
        },
    )
    return True, "비밀번호 찾기용 보안 질문을 설정했어요."


def delete_own_account(user_id: str, password: str):
    """본인 비밀번호를 확인한 뒤 회원 탈퇴를 처리한다(계정 및 관련 기록 삭제)."""
    user = get_user_by_id(user_id)
    if not user or not verify_password(password, user["salt"], user["pw_hash"]):
        return False, "비밀번호가 일치하지 않아요."
    delete_user(user_id)
    return True, "계정을 삭제했어요. 그동안 함께해줘서 고마워요!"


# ================= 개인 통계 (볼륨/스트릭) =================

def get_user_stats(user_id: str, today_str: str) -> dict:
    """총 볼륨(무게×횟수 합, 근력 전용), 총 기록일 수, 오늘 기준 연속 기록일(스트릭).
    기록일/스트릭은 근력이든 유산소든 그 날 기록을 남겼으면 카운트한다."""
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

    for d in get_db().cardio_logs.find({"user_id": user_id}, {"date": 1}):
        dates.add(d["date"])

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
    """관리자 대시보드용 전체 통계(가입자 수, 접속자 수, 기록 수 등)를 계산한다."""
    db = get_db()
    return {
        "total_users": db.users.count_documents({}),
        "active_users": get_active_user_count(),
        "total_logs": db.logs.count_documents({}),
        "total_inquiries": db.inquiries.count_documents({}),
        "open_inquiries": db.inquiries.count_documents({"status": {"$ne": "완료"}}),
    }


def get_signup_counts_by_day(days: int = 14) -> list:
    """최근 N일간 일별 가입자 수. 관리자 대시보드 추이 차트용."""
    database = get_db()
    since = datetime.utcnow() - timedelta(days=days - 1)
    counts = {}
    for u in database.users.find({"created_at": {"$gte": since}}, {"created_at": 1}):
        day = u["created_at"].strftime("%m-%d")
        counts[day] = counts.get(day, 0) + 1
    ordered = []
    for i in range(days - 1, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).strftime("%m-%d")
        ordered.append({"날짜": day, "가입자 수": counts.get(day, 0)})
    return ordered


# ================= 오늘 인증 현황 (커뮤니티 동기부여) =================

def get_today_checkins(date_str: str, total_exercise_count: int) -> list:
    """오늘 하나라도 기록을 남긴 사람들을, 완료한 종목 수 기준 내림차순으로 반환.
    근력(logs) + 유산소(cardio_logs) 기록을 모두 합쳐서 집계한다 (유산소만 한 사람도 보이도록).
    [{nickname, done_count, total, updated_at}]"""
    database = get_db()
    docs = list(database.logs.find({"date": date_str}, {"user_id": 1, "updated_at": 1}))
    docs += list(database.cardio_logs.find({"date": date_str}, {"user_id": 1, "updated_at": 1}))
    if not docs:
        return []
    per_user = {}
    for d in docs:
        uid = d["user_id"]
        cur = per_user.setdefault(uid, {"count": 0, "updated_at": d.get("updated_at")})
        cur["count"] += 1
        if d.get("updated_at") and (not cur["updated_at"] or d["updated_at"] > cur["updated_at"]):
            cur["updated_at"] = d["updated_at"]

    user_ids = []
    for uid in per_user:
        try:
            user_ids.append(ObjectId(uid))
        except Exception:
            pass
    users = {str(u["_id"]): u["nickname"] for u in database.users.find({"_id": {"$in": user_ids}})}

    rows = [
        {
            "nickname": users.get(uid, "알수없음"),
            "done_count": v["count"],
            "total": total_exercise_count,
            "updated_at": v["updated_at"],
        }
        for uid, v in per_user.items()
    ]
    rows.sort(key=lambda r: (-r["done_count"], r["updated_at"] or datetime.min))
    return rows


# ================= 운동별 무게 추이 (진행 그래프) =================

def get_weight_history(user_id: str, exercise_name: str) -> list:
    """해당 운동의 날짜별 최고 무게 기록을 날짜 오름차순으로 반환. [{date, weight, reps}]"""
    docs = list(
        get_db()
        .logs.find({"user_id": user_id, "exercise_name": exercise_name})
        .sort("date", ASCENDING)
    )
    rows = []
    for d in docs:
        best = _best_from_sets(d["sets"])
        if best is None:
            continue
        w, r = best
        rows.append({"date": d["date"], "weight": w, "reps": r})
    return rows


# ================= 스트릭 히트맵용 기록일 집합 =================

def get_workout_dates(user_id: str) -> set:
    """기록이 있는 날짜 문자열(YYYY-MM-DD) 집합. 근력이든 유산소든 기록을 남긴 날은 모두 포함."""
    dates = {d["date"] for d in get_db().logs.find({"user_id": user_id}, {"date": 1})}
    dates |= {d["date"] for d in get_db().cardio_logs.find({"user_id": user_id}, {"date": 1})}
    return dates


# ================= 오운완 인증카드용 날짜 요약 =================

def get_date_summary(user_id: str, date_str: str):
    """해당 날짜에 기록한 운동 전체(근력 + 유산소) 요약 + 그 날의 총 볼륨.

    반환: (rows, total_volume)
    rows = [
        {"type": "strength", "exercise_name": str, "sets": [{"weight": float, "reps": int}, ...],
         "memo": str},
        {"type": "cardio", "exercise_name": str, "duration_min": float|None,
         "distance_km": float|None, "calories": float|None, "memo": str},
    ]
    기록 없으면 ([], 0.0). 근력은 세트를 지운 최고기록 하나가 아니라 그날 친 세트 전부를 담는다.
    """
    docs = list(get_db().logs.find({"user_id": user_id, "date": date_str}))
    rows = []
    total_volume = 0.0
    for d in docs:
        sets = []
        for s in d["sets"]:
            try:
                w = float(s["w"])
                r = int(s["r"])
            except (KeyError, TypeError, ValueError):
                continue
            sets.append({"weight": w, "reps": r})
            total_volume += w * r
        if not sets:
            continue
        rows.append({
            "type": "strength", "exercise_name": d["exercise_name"], "sets": sets,
            "memo": (d.get("memo") or "").strip(),
        })

    cardio_docs = list(get_db().cardio_logs.find({"user_id": user_id, "date": date_str}))
    for d in cardio_docs:
        rows.append({
            "type": "cardio",
            "exercise_name": d["exercise_name"],
            "duration_min": d.get("duration_min"),
            "distance_km": d.get("distance_km"),
            "calories": d.get("calories"),
            "memo": (d.get("memo") or "").strip(),
        })
    return rows, total_volume


# ================= 뱃지 / 업적 =================

BADGE_DEFS = [
    {"id": "streak3", "icon": "🔥", "name": "3일 연속", "need": "연속 기록 3일"},
    {"id": "streak7", "icon": "🔥", "name": "7일 연속", "need": "연속 기록 7일"},
    {"id": "streak30", "icon": "🔥", "name": "30일 연속", "need": "연속 기록 30일"},
    {"id": "days10", "icon": "🗓️", "name": "총 10일", "need": "누적 기록 10일"},
    {"id": "days50", "icon": "🗓️", "name": "총 50일", "need": "누적 기록 50일"},
    {"id": "days100", "icon": "🗓️", "name": "총 100일", "need": "누적 기록 100일"},
    {"id": "vol1000", "icon": "🏋️", "name": "볼륨 1,000kg", "need": "총 볼륨 1,000kg"},
    {"id": "vol5000", "icon": "🏋️", "name": "볼륨 5,000kg", "need": "총 볼륨 5,000kg"},
    {"id": "vol10000", "icon": "🏋️", "name": "볼륨 10,000kg", "need": "총 볼륨 10,000kg"},
    {"id": "champion", "icon": "👑", "name": "챔피언", "need": "한 종목 이상 1위"},
    {"id": "allrounder", "icon": "🎯", "name": "올라운더", "need": "모든 종목 1회 이상 기록"},
]


def get_champion_count(user_id: str, nickname: str) -> int:
    """이 유저가 1위(챔피언)인 종목 수. 본인이 PR을 가진 종목만 확인해서 조회량을 줄인다."""
    pr_map = get_personal_records(user_id)
    count = 0
    for name in pr_map:
        top = get_leaderboard(name, limit=1)
        if top and top[0]["nickname"] == nickname:
            count += 1
    return count


def get_badges(user_id: str, nickname: str, today_str: str, all_exercise_count: int) -> list:
    """[{icon, name, need, achieved}] BADGE_DEFS 순서대로."""
    stats = get_user_stats(user_id, today_str)
    pr_map = get_personal_records(user_id)
    champ_count = get_champion_count(user_id, nickname)

    achieved = {
        "streak3": stats["streak"] >= 3,
        "streak7": stats["streak"] >= 7,
        "streak30": stats["streak"] >= 30,
        "days10": stats["workout_days"] >= 10,
        "days50": stats["workout_days"] >= 50,
        "days100": stats["workout_days"] >= 100,
        "vol1000": stats["total_volume"] >= 1000,
        "vol5000": stats["total_volume"] >= 5000,
        "vol10000": stats["total_volume"] >= 10000,
        "champion": champ_count >= 1,
        "allrounder": len(pr_map) >= all_exercise_count,
    }
    return [dict(b, achieved=achieved.get(b["id"], False)) for b in BADGE_DEFS]


# ================= 커뮤니티 게시판 =================
# 예전에는 "인증샷 게시판" 하나뿐이었지만(하루 1인 1게시글), 이제는 여러 종류의
# 게시판(자유/운동/정보/인증샷)에 제목+내용(+선택적 사진)으로 자유롭게 여러 글을 쓸 수 있다.
# 목록에서는 제목만 보이고, 클릭해서 상세로 들어가야 사진/본문을 볼 수 있는 구조.

BOARD_CATEGORIES = [
    ("free", "자유", "💬"),
    ("workout", "운동", "💪"),
    ("info", "정보", "📚"),
    ("cert", "인증샷", "📸"),
]
BOARD_CATEGORY_KEYS = [c[0] for c in BOARD_CATEGORIES]
BOARD_CATEGORY_NAME = {k: n for k, n, i in BOARD_CATEGORIES}
BOARD_CATEGORY_ICON = {k: i for k, n, i in BOARD_CATEGORIES}
BOARD_CATEGORY_LABEL = {k: f"{i} {n}게시판" for k, n, i in BOARD_CATEGORIES}
DEFAULT_BOARD_CATEGORY = "free"

REACTION_EMOJIS = ["🔥", "💪", "👏"]
MAX_PHOTO_WIDTH = 1000
_JPEG_QUALITY = 72


def compress_photo_to_b64(file_bytes: bytes) -> str:
    """업로드된 이미지를 리사이즈 + JPEG 압축해서 base64 문자열로 반환 (DB 용량 절약)."""
    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img)  # 휴대폰 세로사진 회전 방향 보정
    img = img.convert("RGB")
    if img.width > MAX_PHOTO_WIDTH:
        ratio = MAX_PHOTO_WIDTH / img.width
        img = img.resize((MAX_PHOTO_WIDTH, int(img.height * ratio)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def create_post(user_id: str, nickname: str, category: str, title: str, content: str,
                 file_bytes: Optional[bytes] = None):
    """새 게시글을 작성한다 (자유/운동/정보/인증샷 게시판 공통)."""
    if category not in BOARD_CATEGORY_KEYS:
        category = DEFAULT_BOARD_CATEGORY
    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "nickname": nickname,
        "category": category,
        "title": (title or "").strip() or "(제목 없음)",
        "content": (content or "").strip(),
        "created_at": now,
        "updated_at": now,
        "comments": [],
        "reactions": {},
        "views": 0,
    }
    if file_bytes:
        doc["photo_b64"] = compress_photo_to_b64(file_bytes)
    result = get_db().posts.insert_one(doc)
    return result.inserted_id


def update_post(post_id, user_id: str, is_admin: bool = False, title: Optional[str] = None,
                 content: Optional[str] = None, file_bytes: Optional[bytes] = None,
                 remove_photo: bool = False) -> bool:
    """게시글을 수정한다 (작성자 본인 또는 관리자만 가능)."""
    database = get_db()
    q = {"_id": ObjectId(post_id)}
    if not is_admin:
        q["user_id"] = user_id
    update = {"updated_at": datetime.utcnow()}
    if title is not None:
        update["title"] = title.strip() or "(제목 없음)"
    if content is not None:
        update["content"] = content.strip()
    if file_bytes:
        update["photo_b64"] = compress_photo_to_b64(file_bytes)
    op = {"$set": update}
    if remove_photo and not file_bytes:
        op["$unset"] = {"photo_b64": ""}
    result = database.posts.update_one(q, op)
    return result.matched_count > 0


def get_posts(category: Optional[str] = None, search: Optional[str] = None, limit: int = 100) -> list:
    """게시판 글 목록을 최신순으로 조회한다. category가 None/'all'이면 전체 게시판 통합."""
    import re
    q = {}
    if category and category != "all":
        q["category"] = category
    search = (search or "").strip()
    if search:
        pattern = re.compile(re.escape(search), re.IGNORECASE)
        q["$or"] = [{"title": pattern}, {"content": pattern}, {"nickname": pattern}]
    return list(get_db().posts.find(q).sort("created_at", DESCENDING).limit(limit))


def get_post_by_id(post_id) -> Optional[dict]:
    """게시글 하나를 id로 조회한다."""
    try:
        return get_db().posts.find_one({"_id": ObjectId(post_id)})
    except Exception:
        return None


def increment_view(post_id):
    """게시글 조회수를 1 올린다."""
    try:
        get_db().posts.update_one({"_id": ObjectId(post_id)}, {"$inc": {"views": 1}})
    except Exception:
        pass


def get_board_category_counts() -> dict:
    """게시판(카테고리)별 게시글 개수를 반환한다."""
    pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
    return {row["_id"]: row["count"] for row in get_db().posts.aggregate(pipeline)}


def delete_post(post_id, user_id: str, is_admin: bool = False):
    """게시글을 삭제한다(작성자 본인 또는 관리자만 가능)."""
    database = get_db()
    q = {"_id": ObjectId(post_id)}
    if not is_admin:
        q["user_id"] = user_id
    database.posts.delete_one(q)


def add_comment(post_id, user_id: str, nickname: str, text: str):
    """게시글에 댓글을 추가한다."""
    text = (text or "").strip()
    if not text:
        return
    get_db().posts.update_one(
        {"_id": ObjectId(post_id)},
        {
            "$push": {
                "comments": {
                    "_id": ObjectId(),
                    "user_id": user_id,
                    "nickname": nickname,
                    "text": text,
                    "created_at": datetime.utcnow(),
                }
            }
        },
    )


def delete_comment(post_id, comment_id, user_id: str, is_admin: bool = False):
    """댓글을 삭제한다(작성자 본인 또는 관리자만 가능)."""
    database = get_db()
    post = database.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        return
    comments = post.get("comments", [])
    new_comments = [
        c for c in comments
        if not (str(c.get("_id")) == str(comment_id) and (is_admin or c.get("user_id") == user_id))
    ]
    database.posts.update_one({"_id": ObjectId(post_id)}, {"$set": {"comments": new_comments}})


def toggle_reaction(post_id, user_id: str, emoji: str):
    """이미 누른 리액션이면 취소, 아니면 추가."""
    database = get_db()
    post = database.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        return
    reactions = post.get("reactions", {})
    users = set(reactions.get(emoji, []))
    if user_id in users:
        users.discard(user_id)
    else:
        users.add(user_id)
    reactions[emoji] = list(users)
    database.posts.update_one({"_id": ObjectId(post_id)}, {"$set": {"reactions": reactions}})


# ================= 나만의 루틴 =================

def list_routines(user_id: str) -> list:
    """사용자가 저장한 루틴을 최근 수정 순으로 반환한다."""
    return list(get_db().routines.find({"user_id": user_id}).sort("updated_at", DESCENDING))


def get_routine(routine_id, user_id: Optional[str] = None) -> Optional[dict]:
    """루틴 하나를 조회한다. user_id가 있으면 소유권도 함께 확인한다."""
    try:
        query = {"_id": ObjectId(routine_id)}
    except Exception:
        return None
    if user_id is not None:
        query["user_id"] = user_id
    return get_db().routines.find_one(query)


def save_routine(user_id: str, name: str, items: list, routine_id=None):
    """루틴을 새로 만들거나 수정한다."""
    name = (name or "").strip()
    clean_items = normalize_routine_items(items)
    if not name:
        return False, "루틴 이름을 입력해주세요.", None
    if not clean_items:
        return False, "운동을 하나 이상 선택해주세요.", None
    now = datetime.utcnow()
    database = get_db()
    try:
        if routine_id:
            query = {"_id": ObjectId(routine_id), "user_id": user_id}
            result = database.routines.update_one(
                query,
                {"$set": {"name": name, "items": clean_items, "updated_at": now}},
            )
            if not result.matched_count:
                return False, "수정할 루틴을 찾을 수 없어요.", None
            return True, "루틴을 수정했어요.", str(routine_id)
        result = database.routines.insert_one(
            {"user_id": user_id, "name": name, "items": clean_items, "created_at": now, "updated_at": now}
        )
        return True, "루틴을 저장했어요.", str(result.inserted_id)
    except DuplicateKeyError:
        return False, "같은 이름의 루틴이 이미 있어요.", None
    except (TypeError, ValueError):
        return False, "루틴 데이터 형식을 확인해주세요.", None


def duplicate_routine(routine_id, user_id: str):
    """루틴을 '복사본' 이름으로 복제한다."""
    routine = get_routine(routine_id, user_id)
    if not routine:
        return False, "복제할 루틴을 찾을 수 없어요.", None
    existing = {r["name"] for r in list_routines(user_id)}
    base = f"{routine['name']} 복사본"
    name = base
    number = 2
    while name in existing:
        name = f"{base} {number}"
        number += 1
    return save_routine(user_id, name, routine.get("items", []))


def delete_routine(routine_id, user_id: str) -> bool:
    """본인의 루틴을 삭제하고 주간 계획의 연결도 제거한다."""
    try:
        rid = ObjectId(routine_id)
    except Exception:
        return False
    result = get_db().routines.delete_one({"_id": rid, "user_id": user_id})
    if result.deleted_count:
        plan = get_weekly_plan(user_id)
        schedule = {k: v for k, v in plan.items() if str(v) != str(routine_id)}
        save_weekly_plan(user_id, schedule)
        return True
    return False


# ================= 주간 루틴 계획 =================

def get_weekly_plan(user_id: str) -> dict:
    """요일 번호 문자열('0'=월요일) -> routine_id 매핑을 반환한다."""
    doc = get_db().weekly_plans.find_one({"user_id": user_id})
    return dict(doc.get("schedule", {})) if doc else {}


def save_weekly_plan(user_id: str, schedule: dict):
    """사용자의 요일별 루틴 계획을 저장한다."""
    clean = {
        str(day): str(routine_id)
        for day, routine_id in (schedule or {}).items()
        if str(day) in {str(i) for i in range(7)} and routine_id
    }
    get_db().weekly_plans.update_one(
        {"user_id": user_id},
        {"$set": {"schedule": clean, "updated_at": datetime.utcnow()}},
        upsert=True,
    )
    return clean


# ================= 체형 기록 =================

def save_body_metric(user_id: str, date_str: str, weight=None, muscle_mass=None, body_fat=None, memo: str = ""):
    """같은 날짜의 체중·골격근량·체지방률을 저장 또는 수정한다."""
    values = {}
    for key, value in (("weight", weight), ("muscle_mass", muscle_mass), ("body_fat", body_fat)):
        if value in (None, ""):
            values[key] = None
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False, "체형 수치는 숫자로 입력해주세요."
        maximum = 100 if key == "body_fat" else 500
        if number <= 0 or number > maximum:
            return False, "체형 수치의 입력 범위를 확인해주세요."
        values[key] = number
    if all(values[k] is None for k in values):
        return False, "체중·골격근량·체지방률 중 하나 이상 입력해주세요."
    now = datetime.utcnow()
    get_db().body_metrics.update_one(
        {"user_id": user_id, "date": date_str},
        {"$set": {**values, "memo": (memo or "").strip(), "updated_at": now}, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return True, "체형 기록을 저장했어요."


def get_body_metrics(user_id: str, limit: int = 365) -> list:
    """최근 체형 기록을 날짜 오름차순으로 반환한다."""
    rows = list(get_db().body_metrics.find({"user_id": user_id}).sort("date", DESCENDING).limit(limit))
    rows.reverse()
    return rows


def get_body_metric(user_id: str, date_str: str) -> Optional[dict]:
    """특정 날짜의 체형 기록 하나를 반환한다."""
    return get_db().body_metrics.find_one({"user_id": user_id, "date": date_str})


def delete_body_metric(user_id: str, date_str: str) -> bool:
    return get_db().body_metrics.delete_one({"user_id": user_id, "date": date_str}).deleted_count > 0


# ================= 공식/사용자 운동 카탈로그 =================

def _base_exercise_catalog() -> list:
    """JSON 기본 운동을 이름 기준으로 중복 제거해 반환한다."""
    from utils.data import EX_BY_NAME
    rows = []
    for name, item in EX_BY_NAME.items():
        rows.append(
            {
                "name": name,
                "part": item.get("part", "PART1"),
                "sets": int(item.get("sets") or 3),
                "target_reps": parse_target_reps(item.get("reps")),
                "reps": item.get("reps", "10회"),
                "equip": item.get("equip", ""),
                "howto": item.get("howto", []),
                "caution": item.get("caution", ""),
                "tip": item.get("tip", ""),
                "img_path": item.get("img_path"),
                "source": "official",
                "base_name": name,
                "active": True,
            }
        )
    return rows


def get_exercise_catalog(user_id: Optional[str] = None, include_inactive: bool = False) -> list:
    """기본 JSON + 관리자 추가/수정 + 개인 운동을 하나의 목록으로 합친다."""
    database = get_db()
    rows = _base_exercise_catalog()
    by_name = {item["name"]: item for item in rows}
    query = {"$or": [{"scope": "official"}]}
    if user_id:
        query["$or"].append({"scope": "user", "user_id": user_id})
    for doc in database.exercise_catalog.find(query):
        clean = {k: v for k, v in doc.items() if k != "_id"}
        clean["_db_id"] = str(doc["_id"])
        clean.setdefault("active", True)
        clean.setdefault("source", "official" if doc.get("scope") == "official" else "custom")
        base_name = doc.get("base_name")
        if base_name and base_name in by_name:
            by_name[base_name].update(clean)
            by_name[base_name]["name"] = base_name
        else:
            by_name[clean["name"]] = clean
    result = list(by_name.values())
    if not include_inactive:
        result = [item for item in result if item.get("active", True)]
    return sorted(result, key=lambda item: (item.get("source") != "official", item.get("part", ""), item["name"]))


def get_exercises_for_part_catalog(user_id: Optional[str], part_key: str, catalog: Optional[list] = None) -> list:
    """Return the merged catalog for a body part while preserving JSON cross-part entries."""
    from utils.data import exercises_for_part

    # Inactive overrides must stay visible here so a disabled base exercise does
    # not fall back to its original JSON entry.
    catalog = catalog if catalog is not None else get_exercise_catalog(user_id, include_inactive=True)
    by_name = {item["name"]: item for item in catalog}
    rows = []
    seen = set()
    for base in exercises_for_part(part_key):
        merged = dict(base)
        override = by_name.get(base["name"])
        if override:
            merged.update(override)
            # A base exercise can intentionally belong to more than one JSON section.
            merged["part"] = part_key
        if merged.get("active", True):
            rows.append(merged)
            seen.add(merged["name"])
    rows.extend(
        item for item in catalog
        if item.get("part") == part_key and item["name"] not in seen and item.get("active", True)
    )
    return rows


def save_catalog_exercise(scope: str, user_id: Optional[str], data: dict, exercise_id=None, base_name=None):
    """개인 운동 또는 관리자 공식 운동/수정분을 저장한다."""
    if scope not in {"official", "user"}:
        return False, "운동 구분이 올바르지 않아요.", None
    name = (data.get("name") or base_name or "").strip()
    if not name:
        return False, "운동 이름을 입력해주세요.", None
    try:
        sets = max(1, min(20, int(data.get("sets") or 3)))
        target_reps = max(1, min(1000, int(data.get("target_reps") or 10)))
    except (TypeError, ValueError):
        return False, "세트와 목표 횟수는 숫자로 입력해주세요.", None
    doc = {
        "scope": scope,
        "user_id": user_id if scope == "user" else None,
        "name": name,
        "part": data.get("part", "PART1"),
        "sets": sets,
        "target_reps": target_reps,
        "reps": f"{target_reps}회",
        "equip": (data.get("equip") or "").strip(),
        "howto": [str(x).strip() for x in data.get("howto", []) if str(x).strip()],
        "caution": (data.get("caution") or "").strip(),
        "tip": (data.get("tip") or "").strip(),
        "img_path": (data.get("img_path") or "").strip() or None,
        "source": "official" if scope == "official" else "custom",
        "active": bool(data.get("active", True)),
        "updated_at": datetime.utcnow(),
    }
    if base_name:
        doc["base_name"] = base_name
        doc["name"] = base_name
    database = get_db()
    if not exercise_id:
        base_names = {item["name"] for item in _base_exercise_catalog()}
        if not base_name and doc["name"] in base_names:
            return False, "기본 운동과 같은 이름은 사용할 수 없어요.", None
        duplicate_query = {"scope": scope, "name": doc["name"]}
        duplicate_query["user_id"] = doc["user_id"]
        if database.exercise_catalog.find_one(duplicate_query):
            return False, "같은 이름의 운동이 이미 있어요.", None
    try:
        if exercise_id:
            query = {"_id": ObjectId(exercise_id)}
            if scope == "user":
                query["user_id"] = user_id
            result = database.exercise_catalog.update_one(query, {"$set": doc})
            if not result.matched_count:
                return False, "수정할 운동을 찾을 수 없어요.", None
            return True, "운동을 수정했어요.", str(exercise_id)
        doc["created_at"] = datetime.utcnow()
        result = database.exercise_catalog.insert_one(doc)
        return True, "운동을 저장했어요.", str(result.inserted_id)
    except Exception:
        return False, "운동을 저장하지 못했어요.", None


def delete_catalog_exercise(exercise_id: str, user_id: Optional[str] = None, is_admin: bool = False) -> bool:
    """DB에 추가된 운동을 권한에 맞게 삭제한다."""
    try:
        query = {"_id": ObjectId(exercise_id)}
    except Exception:
        return False
    if not is_admin:
        query.update({"scope": "user", "user_id": user_id})
    return get_db().exercise_catalog.delete_one(query).deleted_count > 0


# ================= 루틴 운동 세션 =================

def get_previous_exercise_log(user_id: str, exercise_name: str, before_date: Optional[str] = None) -> Optional[dict]:
    """선택 날짜보다 이전의 가장 최근 근력 기록을 반환한다."""
    query = {"user_id": user_id, "exercise_name": exercise_name}
    if before_date:
        query["date"] = {"$lt": before_date}
    return get_db().logs.find_one(query, sort=[("date", DESCENDING), ("updated_at", DESCENDING)])


def start_workout_session(user_id: str, routine: dict, date_str: str) -> str:
    """루틴 스냅샷으로 새로운 진행 세션을 만든다."""
    items = normalize_routine_items(routine.get("items", []))
    database = get_db()
    database.workout_sessions.update_many(
        {"user_id": user_id, "status": "active"},
        {"$set": {"status": "replaced", "finished_at": datetime.utcnow()}},
    )
    doc = {
        "user_id": user_id,
        "routine_id": str(routine.get("_id", "")),
        "routine_name": routine.get("name", "나만의 루틴"),
        "date": date_str,
        "items": items,
        "completed_indexes": [],
        "current_index": 0,
        "status": "active",
        "started_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = database.workout_sessions.insert_one(doc)
    return str(result.inserted_id)


def get_workout_session(session_id, user_id: str) -> Optional[dict]:
    try:
        return get_db().workout_sessions.find_one({"_id": ObjectId(session_id), "user_id": user_id})
    except Exception:
        return None


def get_active_workout_session(user_id: str) -> Optional[dict]:
    return get_db().workout_sessions.find_one(
        {"user_id": user_id, "status": "active"}, sort=[("started_at", DESCENDING)]
    )


def update_workout_session(session_id, user_id: str, current_index=None, completed_index=None):
    """세션의 현재 운동과 완료 운동을 원자적으로 갱신한다."""
    try:
        query = {"_id": ObjectId(session_id), "user_id": user_id, "status": "active"}
    except Exception:
        return False
    update = {"$set": {"updated_at": datetime.utcnow()}}
    if current_index is not None:
        update["$set"]["current_index"] = max(0, int(current_index))
    if completed_index is not None:
        update["$addToSet"] = {"completed_indexes": int(completed_index)}
    return get_db().workout_sessions.update_one(query, update).matched_count > 0


def finish_workout_session(session_id, user_id: str) -> bool:
    try:
        query = {"_id": ObjectId(session_id), "user_id": user_id, "status": "active"}
    except Exception:
        return False
    result = get_db().workout_sessions.update_one(
        query,
        {"$set": {"status": "completed", "completed_at": datetime.utcnow(), "updated_at": datetime.utcnow()}},
    )
    return result.matched_count > 0
