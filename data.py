# -*- coding: utf-8 -*-
"""
기존 '헬린이 루틴' HTML 웹앱의 운동 데이터를 그대로 이식.
같은 운동(name)이 여러 요일에 나올 수 있는데, 이 경우 하나의 동일한 운동으로 취급해서
개인 기록(PR)과 랭킹을 name 기준으로 합산한다 (기존 HTML의 EX_BY_NAME 방식과 동일).
"""

DAYS = [
    {"key": "DAY1", "label": "DAY 1", "part": "가슴·삼두·어깨"},
    {"key": "DAY2", "label": "DAY 2", "part": "등·이두·후면어깨"},
    {"key": "DAY3", "label": "DAY 3", "part": "하체·엉덩이·복근"},
    {"key": "DAY4", "label": "DAY 4", "part": "어깨·팔"},
]

EX = [
    # DAY 1 - 가슴・삼두・어깨
    {"day": "DAY1", "name": "인클라인 덤벨 프레스", "sets": 3, "reps": "8~12회", "equip": "인클라인 벤치 + 덤벨 2개"},
    {"day": "DAY1", "name": "체스트 머신 프레스", "sets": 3, "reps": "10~12회", "equip": "체스트 프레스 머신(고정형)"},
    {"day": "DAY1", "name": "케이블 크로스오버", "sets": 3, "reps": "12~15회", "equip": "케이블 크로스오버 머신"},
    {"day": "DAY1", "name": "덤벨 숄더 프레스", "sets": 3, "reps": "8~12회", "equip": "덤벨 2개 (벤치는 선택사항)"},
    {"day": "DAY1", "name": "사이드 레터럴 레이즈", "sets": 3, "reps": "12~15회", "equip": "덤벨 2개 (가벼운 무게)"},
    {"day": "DAY1", "name": "케이블 푸시다운", "sets": 3, "reps": "12~15회", "equip": "케이블 머신 + 로프/바 어태치먼트"},
    {"day": "DAY1", "name": "라잉 트라이셉스 익스텐션", "sets": 3, "reps": "10~12회", "equip": "평벤치 + EZ바 또는 덤벨"},
    # DAY 2 - 등・이두・후면어깨
    {"day": "DAY2", "name": "랫 풀 다운", "sets": 4, "reps": "10~12회", "equip": "랫풀다운 머신 + 긴 바"},
    {"day": "DAY2", "name": "벤트오버 바벨 로우", "sets": 3, "reps": "8~12회", "equip": "바벨 (원판 포함)"},
    {"day": "DAY2", "name": "시티드 케이블 로우", "sets": 3, "reps": "10~12회", "equip": "시티드 로우 머신 + 손잡이"},
    {"day": "DAY2", "name": "벤트오버 레터럴 레이즈", "sets": 3, "reps": "15~20회", "equip": "덤벨 2개 (가벼운 무게)"},
    {"day": "DAY2", "name": "바벨 컬", "sets": 3, "reps": "10~12회", "equip": "스트레이트 바벨 또는 EZ바"},
    {"day": "DAY2", "name": "덤벨 해머 컬", "sets": 3, "reps": "12~15회", "equip": "덤벨 2개"},
    # DAY 3 - 하체・엉덩이・복근
    {"day": "DAY3", "name": "바벨 스쿼트", "sets": 4, "reps": "8~12회", "equip": "스쿼트랙 + 바벨"},
    {"day": "DAY3", "name": "레그 프레스", "sets": 3, "reps": "10~12회", "equip": "레그프레스 머신"},
    {"day": "DAY3", "name": "레그 익스텐션", "sets": 3, "reps": "12~15회", "equip": "레그익스텐션 머신"},
    {"day": "DAY3", "name": "레그 컬", "sets": 3, "reps": "12~15회", "equip": "레그컬 머신"},
    {"day": "DAY3", "name": "힙 쓰러스트", "sets": 4, "reps": "10~15회", "equip": "벤치 + 바벨 (패드 권장)"},
    {"day": "DAY3", "name": "행잉 레그 레이즈", "sets": 3, "reps": "12~15회", "equip": "철봉(풀업바)"},
    {"day": "DAY3", "name": "케이블 크런치", "sets": 3, "reps": "15~20회", "equip": "케이블 머신 + 로프 어태치먼트"},
    # DAY 4 - 어깨・팔
    {"day": "DAY4", "name": "오버헤드 프레스", "sets": 4, "reps": "8~12회", "equip": "바벨 또는 스미스머신"},
    {"day": "DAY4", "name": "사이드 레터럴 레이즈", "sets": 3, "reps": "12~15회", "equip": "덤벨 2개 (가벼운 무게)"},
    {"day": "DAY4", "name": "프론트 레이즈", "sets": 3, "reps": "12~15회", "equip": "덤벨 2개"},
    {"day": "DAY4", "name": "벤트오버 레터럴 레이즈", "sets": 3, "reps": "15~20회", "equip": "덤벨 2개 (가벼운 무게)"},
    {"day": "DAY4", "name": "덤벨 컬", "sets": 3, "reps": "10~12회", "equip": "덤벨 2개"},
    {"day": "DAY4", "name": "케이블 푸시다운", "sets": 3, "reps": "12~15회", "equip": "케이블 머신 + 로프/바 어태치먼트"},
]

EX_BY_NAME = {}
for _e in EX:
    EX_BY_NAME.setdefault(_e["name"], _e)  # 첫 등장 요일 기준 sets/reps/equip 대표값

ALL_EXERCISE_NAMES = list(EX_BY_NAME.keys())


def exercises_for_day(day_key: str):
    return [e for e in EX if e["day"] == day_key]
