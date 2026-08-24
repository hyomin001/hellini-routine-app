# -*- coding: utf-8 -*-
"""루틴·점진적 과부하·운동 통계에 쓰는 순수 계산 함수.

Streamlit이나 MongoDB에 의존하지 않아 단위 테스트에서 바로 검증할 수 있다.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Optional


def parse_target_reps(value, default: int = 10) -> int:
    """``8~12회`` 같은 문자열에서 목표 반복수(상단값)를 추출한다."""
    if isinstance(value, (int, float)):
        return max(1, min(1000, int(value)))
    text = str(value or "")
    nums = []
    current = ""
    for ch in text:
        if ch.isdigit():
            current += ch
        elif current:
            nums.append(int(current))
            current = ""
    if current:
        nums.append(int(current))
    return max(1, min(1000, max(nums) if nums else default))


def normalize_routine_items(items: Iterable[dict]) -> list[dict]:
    """루틴 항목을 저장 가능한 안정된 형태로 정리한다."""
    out = []
    seen = set()
    for raw in items or []:
        name = str(raw.get("exercise_name") or raw.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        try:
            sets = max(1, min(20, int(raw.get("sets") or 3)))
        except (TypeError, ValueError):
            sets = 3
        out.append(
            {
                "exercise_name": name,
                "source": raw.get("source", "official"),
                "part": raw.get("part", "PART1"),
                "sets": sets,
                "target_reps": parse_target_reps(raw.get("target_reps") or raw.get("reps")),
            }
        )
    return out


def valid_sets(sets: Iterable[dict]) -> list[tuple[float, int]]:
    """저장된 세트 중 계산 가능한 (무게, 횟수)만 반환한다."""
    rows = []
    for item in sets or []:
        try:
            weight = float(item.get("w", item.get("weight")))
            reps = int(item.get("r", item.get("reps")))
        except (TypeError, ValueError):
            continue
        if weight >= 0 and reps > 0:
            rows.append((weight, reps))
    return rows


def estimate_one_rep_max(weight: float, reps: int) -> float:
    """Epley 공식으로 예상 1RM을 계산한다. 1회 기록은 실제 무게를 그대로 쓴다."""
    weight = max(0.0, float(weight or 0))
    reps = max(1, int(reps or 1))
    if reps == 1:
        return weight
    return weight * (1 + reps / 30.0)


def progression_recommendation(previous_sets: Iterable[dict], target_reps: int, increment: float = 2.5) -> dict:
    """직전 기록과 목표 횟수를 비교해 다음 운동 제안을 만든다."""
    rows = valid_sets(previous_sets)
    target = parse_target_reps(target_reps)
    if not rows:
        return {"ready": False, "suggested_weight": None, "message": "첫 기록을 남기면 다음 중량을 추천해드려요."}
    max_weight = max(w for w, _ in rows)
    all_hit = all(r >= target for _, r in rows)
    if all_hit and max_weight > 0:
        suggested = round((max_weight + increment) * 2) / 2
        return {
            "ready": True,
            "suggested_weight": suggested,
            "message": f"모든 세트에서 목표 {target}회를 달성했어요. 다음에는 {suggested:g}kg에 도전해보세요.",
        }
    if all_hit:
        return {
            "ready": True,
            "suggested_weight": 0,
            "message": f"목표 {target}회를 달성했어요. 맨몸 운동은 다음에 세트당 1~2회를 더해보세요.",
        }
    return {
        "ready": False,
        "suggested_weight": max_weight,
        "message": f"현재 중량을 유지하며 모든 세트에서 {target}회를 먼저 채워보세요.",
    }


def weekly_training_summary(logs: Iterable[dict], cardio_logs: Iterable[dict], today: Optional[date] = None) -> dict:
    """최근 7일과 직전 7일의 운동일·볼륨을 비교한다."""
    today = today or date.today()
    current_start = today - timedelta(days=6)
    previous_start = current_start - timedelta(days=7)
    previous_end = current_start - timedelta(days=1)
    current_dates, previous_dates = set(), set()
    current_volume = previous_volume = 0.0

    for log in logs or []:
        try:
            day = date.fromisoformat(str(log.get("date")))
        except (TypeError, ValueError):
            continue
        volume = sum(w * r for w, r in valid_sets(log.get("sets", [])))
        if current_start <= day <= today:
            current_dates.add(day)
            current_volume += volume
        elif previous_start <= day <= previous_end:
            previous_dates.add(day)
            previous_volume += volume

    for log in cardio_logs or []:
        try:
            day = date.fromisoformat(str(log.get("date")))
        except (TypeError, ValueError):
            continue
        if current_start <= day <= today:
            current_dates.add(day)
        elif previous_start <= day <= previous_end:
            previous_dates.add(day)

    return {
        "current_days": len(current_dates),
        "previous_days": len(previous_dates),
        "days_change": len(current_dates) - len(previous_dates),
        "current_volume": current_volume,
        "previous_volume": previous_volume,
        "volume_change": current_volume - previous_volume,
    }


def volume_by_part(logs: Iterable[dict], exercise_parts: dict[str, str]) -> dict[str, float]:
    """근력 기록의 볼륨을 운동 부위별로 합산한다."""
    result = {}
    for log in logs or []:
        part = exercise_parts.get(log.get("exercise_name"), "기타")
        result[part] = result.get(part, 0.0) + sum(w * r for w, r in valid_sets(log.get("sets", [])))
    return result
