# -*- coding: utf-8 -*-
"""
기존 '헬린이 루틴' HTML 웹앱의 운동 데이터를 그대로 이식 (사진, 방법, 주의사항, 팁 포함).
같은 운동(name)이 여러 부위에 나올 수 있는데, 이 경우 하나의 동일한 운동으로 취급해서
개인 기록(PR)과 랭킹을 name 기준으로 합산한다 (기존 HTML의 EX_BY_NAME 방식과 동일).
"""
import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))
_ASSETS_DIR = os.path.join(os.path.dirname(_DIR), "assets", "exercises")

with open(os.path.join(_DIR, "exercises_data.json"), "r", encoding="utf-8") as f:
    EX = json.load(f)

# 이미지 파일 경로로 변환 (image1 -> assets/exercises/image1.jpg)
for _e in EX:
    _e["img_path"] = os.path.join(_ASSETS_DIR, f"{_e['img']}.jpg")

PARTS = [
    {"key": "PART1", "label": "부위 1", "part": "가슴·삼두·어깨"},
    {"key": "PART2", "label": "부위 2", "part": "등·이두·후면어깨"},
    {"key": "PART3", "label": "부위 3", "part": "하체·엉덩이·복근"},
    {"key": "PART4", "label": "부위 4", "part": "어깨·팔"},
]

EX_BY_NAME = {}
for _e in EX:
    EX_BY_NAME.setdefault(_e["name"], _e)  # 첫 등장 부위 기준 sets/reps/equip 대표값

ALL_EXERCISE_NAMES = list(EX_BY_NAME.keys())


def exercises_for_part(part_key: str):
    return [e for e in EX if e["part"] == part_key]


# ================= 유산소 =================
# 근력(세트×무게×횟수) 구조와 달리 유산소는 "시간 + (있으면) 거리" 구조라서
# PARTS 와는 별도의 카테고리로 취급한다 ('오늘' 화면에 부위1~4 탭 옆에 별도 탭으로 노출).
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


# 앱 업데이트 내역 (마이페이지 아니라, '오늘' 화면의 '업데이트 현황'에서 유저들에게 보여준다).
# 새 업데이트가 생기면 리스트 맨 위에 추가하면 된다 (최신순으로 그대로 렌더링됨).
UPDATE_LOG = [
    {
        "date": "2026-08-21",
        "items": [
            "🏃 유산소 카테고리 추가: 러닝 · 사이클링 · 줄넘기 · 수영 · 로잉머신 · 일립티컬 · "
            "계단 오르기 · 등산/하이킹 8종목 ('오늘' 화면 새 탭 '🏃 유산소'에서 확인)",
            "마이페이지에 유산소 누적 거리·시간 통계, 유산소 최고기록 탭 추가",
            "운동 종목 10개 추가: 팔굽혀펴기 · 플랫 벤치 프레스 · 딥스 · 펙 덱 플라이 · 풀업(턱걸이) · "
            "데드리프트 · 윗몸일으키기 · 플랭크 · 워킹 런지 · 오버헤드 트라이셉스 익스텐션",
            "'오늘' 화면에 업데이트 현황 칸 추가 (지금 보고 계신 이 칸이에요!)",
        ],
    },
    {
        "date": "2026-08-20",
        "items": [
            "마이페이지 연속 기록을 깃허브 잔디밭 스타일 → 실제 이번 달 달력 형태로 교체",
            "모바일 좁은 화면에서 상단 메뉴 버튼 · 마이페이지 통계 · 뱃지 · 댓글 버튼이 화면 밖으로 "
            "넘어가던 문제 수정",
        ],
    },
]

