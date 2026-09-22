#!/usr/bin/env python3
"""Generate per-message OG cards + Discord preview pages.

Reads chat.json (ja) and chat_en.json (en), then for every interaction writes:
  og/<short>-<lang>.png   1200x630 card: light-blue chat background + LINE bubbles
  m/<short>/<lang>.html   preview page with og:title/description/image + JS redirect

Run:  python3 generate_previews.py
"""
import html
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
BASE = "https://line.hikaru.monster"

W, H = 1200, 630
BG = (113, 149, 189)
GREEN = (76, 199, 100)
WHITE = (255, 255, 255)
INK = (20, 20, 20)

FONT_SIZE = 44
PAD = 64
BUBBLE_PAD_X = 36
BUBBLE_PAD_Y = 26
MAX_BUBBLE_W = 780
RADIUS = 34
PHOTO_MAX_W = 440
PHOTO_MAX_H = 280

IMG_RE = re.compile(r"^img_[a-z0-9_-]+(\.webp)?$", re.IGNORECASE)
SHORT_RE = re.compile(r"^interaction[_-]?(.+)$", re.IGNORECASE)

TITLES = {"ja": "ヒカル,よしき", "en": '"Hikaru" and Yoshiki'}


def find_font(candidates):
    for name in candidates:
        p = Path(f"C:/Windows/Fonts/{name}")
        if p.exists():
            return str(p)
    raise SystemExit("No Japanese font found in C:/Windows/Fonts")


FONT_MED = find_font(["YuGothM.ttc", "YuGothR.ttc", "msgothic.ttc"])
FONT_BOLD = find_font(["YuGothB.ttc", "YuGothM.ttc", "msgothic.ttc"])


def short_key(key):
    m = SHORT_RE.match(str(key))
    return m.group(1) if m else str(key)


def sort_num(key):
    m = re.search(r"(\d+)(?!.*\d)", str(key))
    return (0, int(m.group(1)), str(key)) if m else (1, 0, str(key))


def as_list(v):
    if isinstance(v, list):
        return v
    return [v] if v is not None else []


def load_chat(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for key, item in data.items():
        if not isinstance(item, dict):
            continue
        trigger = item.get("trigger") if isinstance(item.get("trigger"), str) else ""
        answers = [str(a).strip() for a in as_list(item.get("answers"))]
        answers = [a for a in answers if a]
        if (trigger or "").strip() or answers:
            out[key] = {"trigger": (trigger or "").strip(), "answers": answers}
    return out


def wrap(text, font, draw, max_w):
    stripped = text.strip()
    if not stripped:
        return []
    if " " in stripped or "\u3000" in stripped:
        raw = re.findall(r"\S+\s*", stripped)
        toks = []
        for t in raw:
            if draw.textlength(t, font=font) <= max_w:
                toks.append(t)
            else:
                toks.extend(list(t.strip()))
                toks.append(" ")
    else:
        toks = list(stripped)
    lines, cur = [], ""
    for t in toks:
        if not cur or draw.textlength(cur + t, font=font) <= max_w:
            cur += t
        else:
            lines.append(cur.strip())
            cur = t if t.strip() else ""
    if cur.strip():
        lines.append(cur.strip())
    return lines


def cap(text, n):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n].rstrip() + "…"


def open_photo(name, lang):
    base = name[:-5] if name.lower().endswith(".webp") else name
    for folder in ([f"assets/{lang}", "assets"] if lang == "en" else ["assets"]):
        p = ROOT / folder / f"{base}.webp"
        if p.exists():
            img = Image.open(p).convert("RGB")
            img.thumbnail((PHOTO_MAX_W, PHOTO_MAX_H), Image.LANCZOS)
            return img
    return None


def round_photo(img, radius=24, border=8):
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
    card = Image.new("RGB", (w + border * 2, h + border * 2), WHITE)
    card.paste(img, (border, border), mask)
    outer = Image.new("L", card.size, 0)
    ImageDraw.Draw(outer).rounded_rectangle([0, 0, card.size[0], card.size[1]], radius=radius, fill=255)
    return card, outer


SIZES = [56, 52, 48, 44, 40, 36, 32, 28, 24]
AVAIL = H - PAD * 2
_measure = ImageDraw.Draw(Image.new("RGB", (8, 8), BG))
_fonts = {}


def get_fonts(size):
    if size not in _fonts:
        _fonts[size] = (
            ImageFont.truetype(FONT_BOLD, size),
            ImageFont.truetype(FONT_MED, size),
        )
    return _fonts[size]


def line_h(font, size):
    tb = _measure.textbbox((0, 0), "あA", font=font)
    return (tb[3] - tb[1]) + max(14, size // 2)


def render_card(trigger, answers, lang):
    items = []
    if trigger:
        items.append(("text", "right", cap(trigger, 140), True))
    for a in answers:
        if IMG_RE.match(a):
            photo = open_photo(a, lang)
            if photo is not None:
                items.append(("photo", "left", photo, False))
        elif a.strip():
            items.append(("text", "left", cap(a, 110), False))

    def probe(size):
        font_b, font_m = get_fonts(size)
        gap = max(12, int(size * 0.45))
        photo_box = (PHOTO_MAX_W, max(120, int(PHOTO_MAX_H * size / 44)))
        ops, total = [], 0
        for kind, side, payload, bold in items:
            font = font_b if bold else font_m
            if kind == "photo":
                thumb = payload.copy()
                thumb.thumbnail(photo_box, Image.LANCZOS)
                card, _mask = round_photo(thumb)
                ops.append(("photo", side, card, _mask))
                total += card.size[1] + gap
            else:
                lh = line_h(font, size)
                lines = wrap(payload, font, _measure, MAX_BUBBLE_W - BUBBLE_PAD_X * 2)
                if not lines:
                    continue
                bw = min(
                    MAX_BUBBLE_W,
                    max(int(_measure.textlength(li, font=font)) for li in lines)
                    + BUBBLE_PAD_X * 2,
                )
                bh = len(lines) * lh + BUBBLE_PAD_Y * 2
                ops.append(("bubble", side, lines, font, lh, bw, bh))
                total += bh + gap
        if ops:
            total -= gap
        return ops, total, gap

    size = SIZES[-1]
    ops, total, gap = probe(size)
    for s in SIZES:
        o, t, g = probe(s)
        if o and t <= AVAIL:
            size, ops, total, gap = s, o, t, g
            break

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    font_m = get_fonts(size)[1]
    y = PAD + max(0, (AVAIL - total) // 2)
    bottom = H - PAD
    drawn = 0
    for op in ops:
        if op[0] == "photo":
            _, side, card, pmask = op
            bw, bh = card.size
            if y + bh > bottom:
                break
            x = PAD if side == "left" else W - PAD - bw
            img.paste(card, (x, y), pmask)
            y += bh + gap
            drawn += 1
        else:
            _, side, lines, font, lh, bw, bh = op
            if y + bh > bottom and len(lines) > 1:
                fit = max(1, (bottom - y - BUBBLE_PAD_Y * 2) // lh)
                if fit <= 0:
                    break
                lines = lines[:fit]
                lines[-1] = lines[-1].rstrip() + "…"
                bw = min(
                    MAX_BUBBLE_W,
                    max(int(draw.textlength(li, font=font)) for li in lines)
                    + BUBBLE_PAD_X * 2,
                )
                bh = len(lines) * lh + BUBBLE_PAD_Y * 2
            if y + bh > bottom:
                break
            x = PAD if side == "left" else W - PAD - bw
            draw.rounded_rectangle([x, y, x + bw, y + bh], radius=RADIUS, fill=GREEN if side == "right" else WHITE)
            ty = y + BUBBLE_PAD_Y + (lh - size) // 2 - 4
            for li in lines:
                draw.text((x + BUBBLE_PAD_X, ty), li, font=font, fill=INK)
                ty += lh
            y += bh + gap
            drawn += 1

    if drawn < len(ops):
        lh = line_h(font_m, size)
        bh = lh + BUBBLE_PAD_Y * 2
        if y + bh <= bottom:
            draw.rounded_rectangle([PAD, y, PAD + 120, y + bh], radius=RADIUS, fill=WHITE)
            draw.text((PAD + BUBBLE_PAD_X, y + BUBBLE_PAD_Y - 2), "…", font=font_m, fill=INK)

    return img


def preview_html(short, lang, trigger, answers):
    texts = [a for a in answers if not IMG_RE.match(a)]
    title = trigger or (texts[0][:60] if texts else TITLES[lang])
    desc = "\n".join(texts) or trigger or ("Photo message" if lang == "en" else "写真")
    if len(desc) > 500:
        desc = desc[:500].rstrip() + "…"
    target = f"/?lang={lang}&m={short}"
    img_url = f"{BASE}/og/{short}-{lang}.png"
    e = html.escape
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<title>{e(title)}</title>
<link rel="canonical" href="{BASE}{target}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="HGSN Line Bot">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:image" content="{img_url}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:url" content="{BASE}/m/{short}/{lang}.html">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{img_url}">
<meta name="theme-color" content="#7195bd">
<script>window.location.replace({json.dumps(target)});</script>
<style>body{{margin:0;display:flex;align-items:center;justify-content:center;height:100vh;background:#7195bd;color:#fff;font-family:sans-serif}}a{{color:#fff}}</style>
</head>
<body><p><a href="{target}">Open in HGSN Line Bot</a></p></body>
</html>
"""


def main():
    ja = load_chat(ROOT / "chat.json")
    en = load_chat(ROOT / "chat_en.json")
    keys = sorted(set(ja) | set(en), key=sort_num)
    (ROOT / "og").mkdir(exist_ok=True)
    n_html = n_png = 0
    for key in keys:
        short = short_key(key)
        for lang, data in (("ja", ja), ("en", en)):
            item = data.get(key, {"trigger": "", "answers": []})
            trigger, answers = item["trigger"], item["answers"]
            card = render_card(trigger, answers, lang)
            card.save(ROOT / "og" / f"{short}-{lang}.png", optimize=True)
            n_png += 1
            page = ROOT / "m" / short / f"{lang}.html"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(preview_html(short, lang, trigger, answers), encoding="utf-8")
            n_html += 1
    print(f"interactions={len(keys)} html={n_html} png={n_png}")


if __name__ == "__main__":
    main()
