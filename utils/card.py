# -*- coding: utf-8 -*-
"""
그날의 운동 기록을 인스타 스토리 규격(1080x1920)의 예쁜 PNG 카드로 만들어주는 모듈.
'기록 히스토리'를 그냥 화면 캡처하면 잘리고 안 예쁜 문제를 해결하기 위해,
전용 요약 카드를 따로 그려서 다운로드할 수 있게 한다.

rows 포맷 (utils/db.py::get_date_summary 참고):
  {"type": "strength", "exercise_name": str, "sets": [{"weight": float, "reps": int}, ...]}
  {"type": "cardio", "exercise_name": str, "duration_min": float|None,
   "distance_km": float|None, "calories": float|None}
"""
import io
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_DIR = os.path.dirname(os.path.abspath(__file__))
_FONT_DIR = os.path.join(os.path.dirname(_DIR), "assets", "fonts")
_REG_PATH = os.path.join(_FONT_DIR, "NanumGothic-Regular.ttf")
_BOLD_PATH = os.path.join(_FONT_DIR, "NanumGothic-Bold.ttf")

W, H = 1080, 1920

# ---- 팔레트: 다크 + 골드 액센트의 "운동 포스터" 톤 ----
BG_TOP = (14, 15, 18)
BG_BOTTOM = (24, 22, 26)
CARD_BG = (26, 27, 32)
CARD_BG_2 = (31, 32, 38)
BORDER = (54, 57, 66)
ACCENT = (255, 196, 40)       # 골드 (근력)
ACCENT_DIM = (110, 92, 40)
MINT = (66, 214, 200)         # 민트 (유산소 / 스트릭)
TEXT = (245, 244, 239)
SUB = (150, 154, 165)
CHIP_BG = (40, 42, 49)

MAX_ROWS_SHOWN = 10


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _center_text(draw, cx, y, text, font, fill):
    w = _text_w(draw, text, font)
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def _gradient_bg(w, h, top, bottom):
    """세로 방향 다크 그라데이션 배경."""
    img = Image.new("RGB", (w, h), top)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (w, y)], fill=color)
    return img


def _add_glow(img, cx, cy, rx, ry, color, alpha, blur):
    """지정한 위치에 은은한 색 조명(글로우) 효과를 얹는다."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(*color, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def _add_speed_lines(img, corner, color, alpha, count):
    """포스터 느낌을 살리는 대각선 스피드 라인(코너 장식)."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    span = 460
    for i in range(count):
        off = i * 34
        if corner == "tl":
            ld.line([(-40, off), (span - off, -40)], fill=(*color, alpha), width=6)
        else:
            ld.line([(W + 40, H - off), (W - span + off, H + 40)], fill=(*color, alpha), width=6)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def _wrap_text(draw, text, font, max_width, max_lines):
    """일반 텍스트(메모)를 max_width 안에 들어가도록 줄바꿈. max_lines를 넘으면 말줄임표 처리."""
    lines, cur = [], ""
    truncated = False
    consumed = 0
    for ch in text:
        test = cur + ch
        if cur and _text_w(draw, test, font) > max_width:
            lines.append(cur)
            consumed += len(cur)
            cur = ch
            if len(lines) == max_lines:
                truncated = True
                break
        else:
            cur = test
    else:
        if cur:
            lines.append(cur)
            consumed += len(cur)

    if truncated or consumed < len(text):
        if len(lines) < max_lines:
            lines.append(cur)
        lines = lines[:max_lines]
        last = lines[-1] if lines else ""
        while last and _text_w(draw, last + "…", font) > max_width:
            last = last[:-1]
        lines[-1] = last + "…" if lines else "…"
    return lines


def _wrap_chips(draw, chips, font, max_width, pad_x=18, gap=12):
    """chips: [(text, fg, bg), ...]. max_width 안에 들어가도록 줄바꿈해서
    [[(text,fg,bg,w), ...], ...] 형태의 줄(line) 목록을 반환한다."""
    lines, cur, cur_w = [], [], 0.0
    for text, fg, bg in chips:
        w = _text_w(draw, text, font) + pad_x * 2
        if cur and cur_w + gap + w > max_width:
            lines.append(cur)
            cur, cur_w = [], 0.0
        cur.append((text, fg, bg, w))
        cur_w += w + gap
    if cur:
        lines.append(cur)
    return lines


def _draw_chip_line(draw, x, y, line, font, chip_h, gap=12, pad_x=18):
    for text, fg, bg, w in line:
        draw.rounded_rectangle([x, y, x + w, y + chip_h], radius=chip_h / 2, fill=bg)
        draw.text((x + pad_x, y + (chip_h - font.size) / 2 - 2), text, font=font, fill=fg)
        x += w + gap
    return x


def _build_row_chips(row):
    """row 하나(근력/유산소)를 칩 목록으로 변환. [(text, fg, bg), ...]"""
    if row["type"] == "cardio":
        chips = []
        dur = row.get("duration_min")
        dist = row.get("distance_km")
        cal = row.get("calories")
        if dist not in (None, 0, ""):
            chips.append((f"{float(dist):g}km", TEXT, CHIP_BG))
        if dur not in (None, 0, ""):
            chips.append((f"{float(dur):g}분", TEXT, CHIP_BG))
        if cal not in (None, 0, ""):
            chips.append((f"{float(cal):g}kcal", TEXT, CHIP_BG))
        if not chips:
            chips.append(("완료", TEXT, CHIP_BG))
        return chips
    return [(f"{s['weight']:g}kg×{s['reps']}회", (20, 18, 16), ACCENT) for s in row["sets"]]


def generate_workout_card(
    nickname: str,
    date_str: str,
    rows: list,
    total_volume: float,
    streak: int,
) -> bytes:
    """rows: utils/db.py::get_date_summary() 형식. 반환값은 PNG 바이트."""
    base = _gradient_bg(W, H, BG_TOP, BG_BOTTOM)
    base = _add_glow(base, W / 2, 60, 520, 260, ACCENT, 46, 90)
    base = _add_speed_lines(base, "tl", ACCENT, 22, 6)
    base = _add_speed_lines(base, "br", MINT, 18, 5)
    img = base
    d = ImageDraw.Draw(img)

    # ---- 프레임 ----
    d.rounded_rectangle([22, 22, W - 22, H - 22], radius=44, outline=ACCENT_DIM, width=3)

    title_f = _font(_BOLD_PATH, 58)
    kicker_f = _font(_BOLD_PATH, 26)
    date_f = _font(_REG_PATH, 30)
    nickname_f = _font(_BOLD_PATH, 56)
    tag_f = _font(_BOLD_PATH, 34)
    badge_num_f = _font(_BOLD_PATH, 30)
    type_tag_f = _font(_BOLD_PATH, 21)
    footer_label_f = _font(_BOLD_PATH, 42)
    footer_sub_f = _font(_BOLD_PATH, 24)
    brand_f = _font(_REG_PATH, 26)
    more_f = _font(_REG_PATH, 28)

    # ---- 헤더 ----
    _center_text(d, W / 2, 66, "WORKOUT COMPLETE", kicker_f, MINT)
    _center_text(d, W / 2, 104, "🏋 오운완 인증", title_f, ACCENT)
    _center_text(d, W / 2, 182, date_str, date_f, SUB)
    d.rounded_rectangle([W / 2 - 60, 226, W / 2 + 60, 230], radius=2, fill=ACCENT)

    card_left, card_right = 80, W - 80
    card_w = card_right - card_left
    content_x = card_left + 100          # 이름/칩 시작 x
    content_max_w = card_right - 40 - content_x

    nickname_card_h = 168
    footer_card_h = 176
    gap = 34
    header_bottom = 254
    bottom_reserved = 128
    available = H - header_bottom - bottom_reserved

    # ---- 스케일을 줄여가며 각 종목 블록을 구성 (다 안 들어가면 폰트/줄 수를 줄여서 맞춘다) ----
    def build_blocks(shown_rows, scale):
        chip_h = max(34, int(46 * scale))
        line_gap = max(8, int(12 * scale))
        name_f = _font(_BOLD_PATH, max(24, int(38 * scale)))
        c_f = _font(_REG_PATH, max(20, int(27 * scale)))
        pad_top, pad_bottom = max(12, int(18 * scale)), max(12, int(16 * scale))
        name_line_h = max(30, int(46 * scale))
        max_chip_lines = 2 if scale > 0.7 else 1
        memo_f = _font(_REG_PATH, max(18, int(25 * scale)))
        memo_line_h = max(24, int(32 * scale))
        memo_gap = max(6, int(10 * scale))
        max_memo_lines = 2 if scale > 0.8 else 1

        blocks = []
        for row in shown_rows:
            chips = _build_row_chips(row)
            lines = _wrap_chips(d, chips, c_f, content_max_w)
            truncated = len(lines) > max_chip_lines
            if truncated:
                lines = lines[:max_chip_lines]
            block_h = pad_top + name_line_h + len(lines) * chip_h + max(0, len(lines) - 1) * line_gap + pad_bottom

            memo_lines = []
            memo_text = (row.get("memo") or "").strip()
            if memo_text:
                memo_lines = _wrap_text(d, f"“{memo_text}”", memo_f, content_max_w, max_memo_lines)
                block_h += memo_gap + len(memo_lines) * memo_line_h

            blocks.append({
                "row": row, "lines": lines, "h": block_h, "truncated": truncated,
                "name_f": name_f, "c_f": c_f, "chip_h": chip_h, "line_gap": line_gap,
                "pad_top": pad_top, "name_line_h": name_line_h,
                "memo_lines": memo_lines, "memo_f": memo_f,
                "memo_line_h": memo_line_h, "memo_gap": memo_gap,
            })
        return blocks

    shown = rows[:MAX_ROWS_SHOWN]
    scale = 1.0
    blocks = build_blocks(shown, scale)
    more_line_h = 50

    def total_h(blocks, has_more):
        return (nickname_card_h + gap + sum(b["h"] + 18 for b in blocks)
                + (more_line_h if has_more else 0) + gap + footer_card_h)

    # 1) 폰트/칩 스케일을 줄여본다
    while total_h(blocks, len(rows) > len(shown)) > available and scale > 0.62:
        scale -= 0.08
        blocks = build_blocks(shown, scale)

    # 2) 그래도 안 들어가면 보여주는 종목 수 자체를 줄인다
    while total_h(blocks, True) > available and len(shown) > 1:
        shown = shown[:-1]
        blocks = build_blocks(shown, scale)

    content_h = total_h(blocks, len(rows) > len(shown))
    start_y = header_bottom + max(10, (available - content_h) / 2)
    if start_y + content_h > H - bottom_reserved:
        start_y = max(header_bottom + 10, H - bottom_reserved - content_h)

    y = start_y

    # ---- 닉네임 카드 ----
    d.rounded_rectangle([card_left, y, card_right, y + nickname_card_h], radius=28,
                         fill=CARD_BG, outline=BORDER, width=2)
    d.rounded_rectangle([card_left, y, card_left + 10, y + nickname_card_h], radius=5, fill=ACCENT)
    _center_text(d, W / 2, y + 32, f"{nickname} 님의 오늘 🔥", nickname_f, TEXT)
    _center_text(d, W / 2, y + 112, f"{len(rows)}개 종목 완료 · 연속 {streak}일째", tag_f, MINT)
    y += nickname_card_h + gap

    # ---- 종목 블록들 ----
    for idx, b in enumerate(blocks):
        row = b["row"]
        block_h = b["h"]
        is_cardio = row["type"] == "cardio"
        badge_color = MINT if is_cardio else ACCENT

        d.rounded_rectangle([card_left, y, card_right, y + block_h], radius=22,
                             fill=CARD_BG_2, outline=BORDER, width=1)

        # 번호 배지
        bcx, bcy, br = card_left + 46, y + block_h / 2, 30
        d.ellipse([bcx - br, bcy - br, bcx + br, bcy + br], fill=badge_color)
        num_txt = str(idx + 1)
        nw = _text_w(d, num_txt, badge_num_f)
        d.text((bcx - nw / 2, bcy - badge_num_f.size / 2 - 3), num_txt, font=badge_num_f, fill=(20, 18, 16))

        ty = y + b["pad_top"]
        # 종목 타입 태그 + 이름
        type_txt = "CARDIO" if is_cardio else "STRENGTH"
        d.text((content_x, ty + 6), type_txt, font=type_tag_f, fill=badge_color)
        tag_w = _text_w(d, type_txt, type_tag_f)
        d.text((content_x + tag_w + 14, ty - 5), row["exercise_name"], font=b["name_f"], fill=TEXT)
        ty += b["name_line_h"]

        for line in b["lines"]:
            _draw_chip_line(d, content_x, ty, line, b["c_f"], b["chip_h"])
            ty += b["chip_h"] + b["line_gap"]

        if b["memo_lines"]:
            ty += b["memo_gap"] - b["line_gap"]
            for ml in b["memo_lines"]:
                d.text((content_x, ty), ml, font=b["memo_f"], fill=SUB)
                ty += b["memo_line_h"]

        y += block_h + 18

    remaining = len(rows) - len(shown)
    if remaining > 0:
        _center_text(d, W / 2, y + 4, f"+ {remaining}개 종목 더", more_f, SUB)
        y += more_line_h
    y += gap

    # ---- 하단 통계 카드 ----
    footer_y = y
    d.rounded_rectangle([card_left, footer_y, card_right, footer_y + footer_card_h], radius=28,
                         fill=CARD_BG, outline=BORDER, width=2)
    div_y0, div_y1 = footer_y + 30, footer_y + footer_card_h - 30
    col_w = card_w / 3
    stats = [
        ("종목", f"{len(rows)}", ACCENT),
        ("총 볼륨(kg)", f"{total_volume:,.0f}", ACCENT),
        ("연속 기록", f"{streak}일", MINT),
    ]
    for i, (label, value, color) in enumerate(stats):
        cx = card_left + col_w * i + col_w / 2
        _center_text(d, cx, footer_y + 34, value, footer_label_f, color)
        _center_text(d, cx, footer_y + 100, label.upper(), footer_sub_f, SUB)
        if i < 2:
            x_div = card_left + col_w * (i + 1)
            d.line([(x_div, div_y0), (x_div, div_y1)], fill=BORDER, width=2)

    _center_text(d, W / 2, H - 76, "헬린이 루틴 · 같이 운동해요 💪", brand_f, SUB)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
