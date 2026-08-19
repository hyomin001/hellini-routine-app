# -*- coding: utf-8 -*-
"""
기존 '헬린이 루틴' HTML 웹앱의 운동 데이터를 그대로 이식 (사진, 방법, 주의사항, 팁 포함).
같은 운동(name)이 여러 요일에 나올 수 있는데, 이 경우 하나의 동일한 운동으로 취급해서
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

DAYS = [
    # key는 DB에 이미 저장된 기록과의 호환을 위해 "DAY1"~"DAY4" 형태를 그대로 유지하고,
    # 화면에 보이는 label만 "DAY"(요일 느낌) 대신 부위 중심 이름으로 바꾼다.
    {"key": "DAY1", "label": "부위 1", "part": "가슴·삼두·어깨"},
    {"key": "DAY2", "label": "부위 2", "part": "등·이두·후면어깨"},
    {"key": "DAY3", "label": "부위 3", "part": "하체·엉덩이·복근"},
    {"key": "DAY4", "label": "부위 4", "part": "어깨·팔"},
]

EX_BY_NAME = {}
for _e in EX:
    EX_BY_NAME.setdefault(_e["name"], _e)  # 첫 등장 요일 기준 sets/reps/equip 대표값

ALL_EXERCISE_NAMES = list(EX_BY_NAME.keys())


def exercises_for_day(day_key: str):
    return [e for e in EX if e["day"] == day_key]
