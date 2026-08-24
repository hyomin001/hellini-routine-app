# -*- coding: utf-8 -*-
"""
기존 '헬린이 루틴' HTML 웹앱의 운동 데이터를 그대로 이식 (사진, 방법, 주의사항, 팁 포함).
같은 운동(name)이 여러 부위에 나올 수 있는데, 이 경우 하나의 동일한 운동으로 취급해서
개인 기록(PR)과 랭킹을 name 기준으로 합산한다 (기존 HTML의 EX_BY_NAME 방식과 동일).
"""
import json
import os
import random as _random

_DIR = os.path.dirname(os.path.abspath(__file__))
_ASSETS_DIR = os.path.join(os.path.dirname(_DIR), "assets", "exercises")

with open(os.path.join(_DIR, "exercises_data.json"), "r", encoding="utf-8") as f:
    EX = json.load(f)

# 이미지 파일 경로로 변환 (image1 -> assets/exercises/image1.jpg)
for _e in EX:
    _e["img_path"] = os.path.join(_ASSETS_DIR, f"{_e['img']}.jpg")

PARTS = [
    {"key": "PART1", "label": "부위 1", "part": "가슴"},
    {"key": "PART2", "label": "부위 2", "part": "등"},
    {"key": "PART3", "label": "부위 3", "part": "어깨"},
    {"key": "PART4", "label": "부위 4", "part": "팔(이두·삼두)"},
    {"key": "PART5", "label": "부위 5", "part": "하체·엉덩이"},
    {"key": "PART6", "label": "부위 6", "part": "복근·코어"},
]

EX_BY_NAME = {}
for _e in EX:
    EX_BY_NAME.setdefault(_e["name"], _e)  # 첫 등장 부위 기준 sets/reps/equip 대표값

ALL_EXERCISE_NAMES = list(EX_BY_NAME.keys())


def exercises_for_part(part_key: str):
    """특정 부위(PART) 키에 해당하는 운동 목록을 반환한다."""
    return [e for e in EX if e["part"] == part_key]


# ================= 대체 운동 (기구가 없을 때) =================

def alt_exercises_for(exercise_name: str):
    """주어진 운동과 같은 부위(part)에 속한 '다른' 운동들을 순서 그대로 반환한다.
    (같은 운동이 여러 부위에 걸쳐 있으면 그 부위들을 모두 고려)
    기구 사용중이라 자리가 없을 때 같은 부위 운동으로 바로 대체할 수 있게 하기 위한 목록."""
    parts = {e["part"] for e in EX if e["name"] == exercise_name}
    seen = {exercise_name}
    out = []
    for e in EX:
        if e["part"] in parts and e["name"] not in seen:
            out.append(e)
            seen.add(e["name"])
    return out


def random_exercise_for_part(part_key: str):
    """해당 부위 운동 중 하나를 무작위로 추천한다 (가는 길/웜업 중 '오늘 뭐하지' 고민 해결용)."""
    pool = exercises_for_part(part_key)
    if not pool:
        return None
    return _random.choice(pool)


# ================= 헬린이 등급제 (총 기록일 기반) =================
# 누적 운동 기록일(총 기록일) 수를 기준으로 등급을 나눈다. 0일은 흰색, 이후 구간마다 색이
# 바뀌며 1년(365일) 이상은 최고 등급.
TIER_DEFS = [
    {"id": "t0", "min": 0, "max": 0, "name": "시작 전", "icon": "⚪", "color": "#F2F1EC", "text": "#121316"},
    {"id": "t1", "min": 1, "max": 10, "name": "새싹", "icon": "🌱", "color": "#8BD46E", "text": "#121316"},
    {"id": "t2", "min": 11, "max": 30, "name": "성장중", "icon": "💧", "color": "#5AA9FF", "text": "#121316"},
    {"id": "t3", "min": 31, "max": 100, "name": "숙련자", "icon": "🔥", "color": "#B15AFF", "text": "#F2F1EC"},
    {"id": "t4", "min": 101, "max": 200, "name": "베테랑", "icon": "⚡", "color": "#FF9F5A", "text": "#121316"},
    {"id": "t5", "min": 201, "max": 365, "name": "마스터", "icon": "👑", "color": "#FFC834", "text": "#121316"},
    {
        "id": "t6", "min": 366, "max": None, "name": "레전드", "icon": "🏆",
        "color": "linear-gradient(90deg,#FF5A9F,#FFC834,#5AA9FF)", "text": "#121316",
    },
]


def get_tier(total_days: int) -> dict:
    """총 기록일(누적 운동일수)에 해당하는 등급 정보를 반환한다.
    반환값에 'next'(다음 등급, 없으면 None)를 함께 담아서 진행률 표시에 바로 쓸 수 있게 한다."""
    total_days = max(0, int(total_days or 0))
    tier, idx = TIER_DEFS[0], 0
    for i, t in enumerate(TIER_DEFS):
        if total_days >= t["min"]:
            tier, idx = t, i
        else:
            break
    nxt = TIER_DEFS[idx + 1] if idx + 1 < len(TIER_DEFS) else None
    return {**tier, "next": nxt}


# ================= 유산소 =================
# 근력(세트×무게×횟수) 구조와 달리 유산소는 "시간 + (있으면) 거리" 구조라서
# PARTS 와는 별도의 카테고리로 취급한다 ('오늘' 화면에 부위1~6 탭 옆에 별도 탭으로 노출).
#
# has_distance=True  : 거리 입력을 받고, PR은 최장거리 + 최고페이스(가장 빠른 기록) 둘 다 추적
# has_distance=False : 시간만 입력받고, PR은 최장시간만 추적
CARDIO_EXERCISES = [
    {
        "key": "running",
        "name": "러닝 (달리기)",
        "icon": "🏃",
        "target": "20~40분 또는 3~10km",
        "equip": "필요한 것 없음 (러닝화 정도)",
        "has_distance": True,
        "tips": [
            "처음 5분은 가볍게 걷거나 천천히 뛰며 워밍업",
            "대화 가능한 정도의 속도로 페이스 유지가 기본, 숨이 너무 차면 걷기와 번갈아도 OK",
            "마지막엔 5분 정도 천천히 걸으며 마무리",
        ],
        "caution": "갑자기 페이스를 확 올리지 않기 · 무릎/발목 통증 있으면 바로 중단",
    },
    {
        "key": "cycling",
        "name": "사이클링 (실내/실외)",
        "icon": "🚴",
        "target": "30~60분 또는 10~20km",
        "equip": "자전거 (실내 스피닝 바이크도 가능)",
        "has_distance": True,
        "tips": [
            "안장 높이는 페달이 가장 아래에 왔을 때 무릎이 살짝 굽혀지는 정도로",
            "오르막/저항 구간과 평지 구간을 섞으면 운동 효과가 더 좋음",
        ],
        "caution": "실외는 헬멧 필수 · 무릎 통증 있으면 안장 높이부터 점검",
    },
    {
        "key": "jump_rope",
        "name": "줄넘기",
        "icon": "🪢",
        "target": "10~20분 (또는 500~1000회)",
        "equip": "줄넘기",
        "has_distance": False,
        "tips": [
            "무릎을 살짝 굽힌 채 발목 힘으로 가볍게 뛰기 (높이 뛰지 않기)",
            "1~2분 뛰고 30초 쉬는 식으로 인터벌로 진행하면 오래 할 수 있음",
        ],
        "caution": "맨발/딱딱한 바닥 피하기 (매트나 쿠셔닝 있는 신발 권장) · 종아리 뭉치면 스트레칭",
    },
    {
        "key": "swimming",
        "name": "수영",
        "icon": "🏊",
        "target": "30분 또는 500m~1500m",
        "equip": "수영장",
        "has_distance": True,
        "tips": [
            "자유형/평영 등 영법을 섞으면 지루하지 않고 골고루 자극됨",
            "25m 레인 기준 왕복 횟수로 거리 계산하면 편함",
        ],
        "caution": "준비운동 없이 바로 입수하지 않기 · 무리해서 숨 참지 않기",
    },
    {
        "key": "rowing",
        "name": "로잉머신 (로잉)",
        "icon": "🚣",
        "target": "15~20분 또는 2000~5000m",
        "equip": "로잉머신",
        "has_distance": True,
        "tips": [
            "다리 → 허리 → 팔 순서로 당기고, 팔 → 허리 → 다리 순서로 되돌아오기 (순서가 핵심)",
            "팔 힘으로만 당기지 않고 다리 힘을 주로 쓰기",
        ],
        "caution": "허리를 둥글게 말지 않고 곧게 유지 · 처음엔 저항(강도)을 낮게 시작",
    },
    {
        "key": "elliptical",
        "name": "일립티컬 (크로스트레이너)",
        "icon": "🏃‍♂️",
        "target": "20~30분",
        "equip": "일립티컬 머신",
        "has_distance": False,
        "tips": [
            "손잡이를 너무 세게 밀지 말고 다리 중심으로 움직이기",
            "경사/저항을 올리면 하체 자극이 더 커짐",
        ],
        "caution": "발이 페달에서 붕 뜨지 않게 체중을 고르게 싣기",
    },
    {
        "key": "stairs",
        "name": "계단 오르기 (스텝밀 / 실제 계단)",
        "icon": "🪜",
        "target": "10~20분",
        "equip": "스텝밀 머신 또는 건물 계단",
        "has_distance": False,
        "tips": [
            "발 전체를 계단에 딛고 뒤꿈치까지 올리기 (앞꿈치만 딛으면 종아리에 부담)",
            "난간을 잡는 힘을 줄여갈수록 하체 운동 효과가 커짐",
        ],
        "caution": "무릎 통증 있으면 속도부터 줄이기 · 내려갈 땐 특히 천천히 (부상 위험)",
    },
    {
        "key": "hiking",
        "name": "등산 / 하이킹",
        "icon": "⛰️",
        "target": "1~3시간 또는 3~10km",
        "equip": "등산화, 물",
        "has_distance": True,
        "tips": [
            "오르막에서는 보폭을 작게, 일정한 속도 유지가 체력 안배에 좋음",
            "내리막에서 무릎 부담이 크니 등산스틱 활용 추천",
        ],
        "caution": "날씨/일몰 시간 확인 · 물 충분히 챙기기 · 무리한 완주보다 컨디션에 맞게 조절",
    },
]

CARDIO_EX_BY_NAME = {e["name"]: e for e in CARDIO_EXERCISES}
CARDIO_NOTE = (
    "🏃 유산소는 기구가 따로 필요 없어서 사진 없이 안내만 담았어요.<br>"
    "실시간 측정은 아직 지원하지 않아서, 스트라바·삼성헬스·나이키런클럽 등 쓰시던 앱으로 "
    "뛰고 결과만 여기 옮겨 적어주시면 돼요!"
)


def format_pace(sec_per_km: float) -> str:
    """초/km 값을 '5'36"/km' 형태의 페이스 문자열로 변환."""
    m = int(sec_per_km // 60)
    s = int(round(sec_per_km % 60))
    if s == 60:
        m += 1
        s = 0
    return f"{m}'{s:02d}\"/km"


def parse_duration(min_val, sec_val):
    """운동시간 입력창의 '분'/'초' 두 값을 분 단위 float 하나로 합친다.
    (예: 19분 30초 -> 19.5) 러닝 페이스처럼 초 단위까지 정확해야 하는 계산에 필요.
    둘 다 비어있으면 (None, None), 값이 있는데 형식이 잘못되면 (None, 에러메시지)."""
    min_val = min_val.strip() if isinstance(min_val, str) else min_val
    sec_val = sec_val.strip() if isinstance(sec_val, str) else sec_val
    if min_val in (None, "") and sec_val in (None, ""):
        return None, None
    try:
        m = float(min_val) if min_val not in (None, "") else 0.0
        s = float(sec_val) if sec_val not in (None, "") else 0.0
    except (TypeError, ValueError):
        return None, "시간은 숫자로 입력해주세요."
    if m < 0 or s < 0:
        return None, "시간은 0 이상이어야 해요."
    if s >= 60:
        return None, "초는 0~59 사이로 입력해주세요."
    return m + s / 60.0, None


def split_duration(total_min):
    """분 단위 값(float)을 (분 문자열, 초 문자열) 입력창 표시용으로 쪼갠다."""
    try:
        total_sec = round(float(total_min) * 60)
    except (TypeError, ValueError):
        return "", ""
    m, s = divmod(total_sec, 60)
    return str(m), str(s)


def format_duration(total_min) -> str:
    """분 단위 값(float)을 '19분 30초' 같은 표시용 문자열로 변환."""
    try:
        total_sec = round(float(total_min) * 60)
    except (TypeError, ValueError):
        return "-"
    m, s = divmod(total_sec, 60)
    return f"{m}분 {s:02d}초" if s else f"{m}분"


# 앱 업데이트 내역 (마이페이지 아니라, '오늘' 화면의 '업데이트 현황'에서 유저들에게 보여준다).
# 새 업데이트가 생기면 리스트 맨 위에 추가하면 된다 (최신순으로 그대로 렌더링됨).
UPDATE_LOG = [
    {
        "date": "2026-08-24",
        "items": [
            "🧩 나만의 루틴 추가: 가슴 루틴·출장용 루틴처럼 여러 루틴을 저장하고 복제·수정·삭제 가능",
            "루틴에서 원하는 공식/개인 운동을 고르고 순서·기본 세트·목표 횟수를 직접 설정 가능",
            "오늘 화면에서 저장 루틴을 한 번에 불러오거나 순차 운동 세션으로 바로 시작 가능",
            "🏋️ 운동 세션 추가: 현재 운동 기록 → 휴식 타이머 → 다음 운동 순서로 진행하고 완료 종목과 전체 진행률 표시",
            "지난번 무게·횟수 자동 표시 및 '지난 기록 그대로 채우기' 버튼 추가",
            "📈 목표 횟수를 모든 세트에서 달성하면 다음 운동에 2.5kg 증량을 제안하는 점진적 과부하 추천 추가",
            "📅 월요일부터 일요일까지 요일별 저장 루틴을 지정하는 주간 계획 추가",
            "⚖️ 체중·골격근량·체지방률 기록과 변화 그래프 추가",
            "📊 최근 7일 운동 횟수·근력 볼륨, 지난주 대비 변화, 부위별 볼륨, 예상 1RM 통계 추가",
            "✍️ 사용자가 목록에 없는 개인 운동을 만들 수 있으며 공식 운동과 구분해서 표시",
            "🛠️ 관리자가 JSON 수정 없이 공식 운동·설명·이미지·기본 세트·목표 횟수·노출 여부를 편집 가능",
            "💾 루틴·주간 계획·체형·개인 운동·운동 세션·유산소·게시글까지 자동 백업/복원 범위 확장",
            "💪 부위 탭 6개로 세분화 및 중복 제거: 기존 4개 부위(가슴·삼두·어깨 / 등·이두·후면어깨 / "
            "하체·엉덩이·복근 / 어깨·팔)에서 어깨·삼두 등이 겹치던 부분을 정리해서 "
            "가슴 · 등 · 어깨 · 팔(이두·삼두) · 하체·엉덩이 · 복근·코어 6개 부위로 재구성",
            "부위별 운동을 실제 타깃 근육 기준으로 재배치 (예: 사이드 레터럴 레이즈·벤트오버 레터럴 레이즈는 "
            "어깨 부위로, 케이블 푸시다운·라잉/오버헤드 트라이셉스 익스텐션은 팔 부위로 통합)",
            "딥스(가슴+삼두), 데드리프트(등+하체)처럼 여러 부위를 동시에 자극하는 운동은 "
            "해당 부위 모두에서 볼 수 있도록 유지 (기록·PR은 동일 운동으로 합산됨)",
        ],
    },
    {
        "date": "2026-08-23",
        "items": [
            "📋 게시판 전면 개편: '인증샷 게시판' 하나였던 걸 자유·운동·정보·인증샷 4개 게시판으로 "
            "확장하고, 게시판마다 원하는 만큼 자유롭게 글쓰기 가능 (하루 1개 제한 없어짐)",
            "게시판 목록에서는 제목만 보이고, 눌러서 들어가야 사진·본문·댓글을 볼 수 있는 구조로 변경",
            "게시판 검색(제목/내용/작성자) 및 게시판별 글 개수·조회수 표시 추가",
            "본인이 쓴 글 수정 기능 추가 (기존엔 삭제만 가능했음)",
        ],
    },
]
