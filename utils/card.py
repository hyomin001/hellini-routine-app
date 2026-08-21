# -*- coding: utf-8 -*-
"""
그날의 운동 기록을 인스타 스토리 규격(1080x1920)의 예쁜 PNG 카드로 만들어주는 모듈.
'기록 히스토리'를 그냥 화면 캡처하면 잘리고 안 예쁜 문제를 해결하기 위해,
전용 요약 카드를 따로 그려서 다운로드할 수 있게 한다.
"""
import io
import os

from PIL import Image, ImageDraw, ImageFont

_DIR = os.path.dirname(os.path.abspath(__file__))
_FONT_DIR = os.path.join(os.path.dirname(_DIR), "assets", "fonts")
_REG_PATH = os.path.join(_FONT_DIR, "NanumGothic-Regular.ttf")
_BOLD_PATH = os.path.join(_FONT_DIR, "NanumGothic-Bold.ttf")

W, H = 1080, 1920
BG = (18, 19, 22)
CARD_BG = (27, 29, 34)
BORDER = (51, 55, 63)
ACCENT = (255, 200, 52)
TEXT = (242, 241, 236)
SUB = (146, 150, 160)
MINT = (78, 205, 196)

MAX_ROWS_SHOWN = 8


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """지정한 경로의 폰트 파일을 주어진 크기로 불러온다."""
    return ImageFont.truetype(path, size)


def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    """주어진 폰트 기준으로 텍스트를 그렸을 때의 픽셀 너비를 계산한다."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _center_text(draw, cx, y, text, font, fill):
    """텍스트를 기준 x좌표에 가운데 정렬로 그린다."""
    w = _text_w(draw, text, font)
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def generate_workout_card(
    nickname: str,
    date_str: str,
    rows: list,
    total_volume: float,
    streak: int,
) -> bytes:
    """rows: [{"exercise_name","weight","reps"}, ...]. 반환값은 PNG 바이트."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    title_f = _font(_BOLD_PATH, 54)
    date_f = _font(_REG_PATH, 32)
    nickname_f = _font(_BOLD_PATH, 60)
    tag_f = _font(_BOLD_PATH, 40)
    ex_name_f = _font(_BOLD_PATH, 38)
    ex_set_f = _font(_REG_PATH, 32)
    footer_label_f = _font(_BOLD_PATH, 36)
    footer_sub_f = _font(_REG_PATH, 30)
    brand_f = _font(_REG_PATH, 26)
    more_f = _font(_REG_PATH, 28)

    # ---- 헤더 ----
    _center_text(d, W / 2, 100, "🏋 헬린이 루틴", title_f, ACCENT)
    _center_text(d, W / 2, 175, date_str, date_f, SUB)

    # ---- 본문(닉네임 카드 + 운동 목록 + 통계 카드)을 남는 세로 공간에 맞춰 중앙 정렬 ----
    shown = rows[:MAX_ROWS_SHOWN]
    row_h = 118
    nickname_card_h = 170
    footer_card_h = 170
    gap = 40
    more_line_h = 56 if len(rows) > len(shown) else 0

    content_h = nickname_card_h + gap + len(shown) * row_h + more_line_h + gap + footer_card_h

    header_bottom = 230
    bottom_reserved = 130  # 맨 아래 브랜드 문구 자리
    available = H - header_bottom - bottom_reserved

    # 종목 수가 많아 고정 행 높이로는 다 안 들어갈 경우, 행 높이를 줄여서 항상 여백 안에 맞춘다
    fixed_h = nickname_card_h + gap + more_line_h + gap + footer_card_h
    if len(shown) > 0 and fixed_h + len(shown) * row_h > available:
        row_h = max(72, int((available - fixed_h) / len(shown)))
        content_h = fixed_h + len(shown) * row_h

    start_y = header_bottom + max(10, (available - content_h) / 2)
    if start_y + content_h > H - bottom_reserved:
        start_y = max(header_bottom + 10, H - bottom_reserved - content_h)

    y = start_y
    d.rounded_rectangle([80, y, W - 80, y + nickname_card_h], radius=28, fill=CARD_BG, outline=BORDER, width=2)
    _center_text(d, W / 2, y + 35, f"{nickname} 님의 오운완 🔥", nickname_f, TEXT)
    _center_text(d, W / 2, y + 115, f"오늘 {len(rows)}개 종목 완료", tag_f, MINT)
    y += nickname_card_h + gap

    for r in shown:
        d.rounded_rectangle([80, y, W - 80, y + row_h - 16], radius=20, fill=CARD_BG, outline=BORDER, width=1)
        d.text((120, y + 22), r["exercise_name"], font=ex_name_f, fill=TEXT)
        set_txt = f"{r['weight']:g}kg × {r['reps']}회"
        set_w = _text_w(d, set_txt, ex_set_f)
        d.text((W - 120 - set_w, y + 30), set_txt, font=ex_set_f, fill=ACCENT)
        y += row_h

    remaining = len(rows) - len(shown)
    if remaining > 0:
        _center_text(d, W / 2, y + 6, f"+ {remaining}개 종목 더", more_f, SUB)
        y += more_line_h
    y += gap

    # ---- 하단 통계 카드 ----
    footer_y = y
    d.rounded_rectangle([80, footer_y, W - 80, footer_y + footer_card_h], radius=28, fill=CARD_BG, outline=BORDER, width=2)

    col_w = (W - 160) / 3
    stats = [
        ("완료 종목", f"{len(rows)}개"),
        ("총 볼륨", f"{total_volume:,.0f}kg"),
        ("연속 기록", f"{streak}일"),
    ]
    for i, (label, value) in enumerate(stats):
        cx = 80 + col_w * i + col_w / 2
        _center_text(d, cx, footer_y + 35, value, footer_label_f, ACCENT if i != 2 else MINT)
        _center_text(d, cx, footer_y + 100, label, footer_sub_f, SUB)

    _center_text(d, W / 2, H - 70, "헬린이 루틴 · 같이 운동해요 💪", brand_f, SUB)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
