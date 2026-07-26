"""Generate a degraded, handwritten-style Devanagari khatauni / record-of-rights page.

WHY THIS EXISTS: no real scanned handwritten land record is publicly available that
is both (a) high enough resolution to extract from and (b) privacy-safe. Real
ownership records contain real people's names and must not be demoed. So we
generate SYNTHETIC CONTENT and apply REAL degradation, then photograph or use the
rendered file. Honest framing for judges:

    "Synthetic record content — no real person's data. The degradation is the
     hard part and it is real: fading, rotation, stamp occlusion, overwriting,
     ink bleed, fold, and shop-light noise."

Usage:
    py -3.12 scripts/make_register_page.py                 # default page
    py -3.12 scripts/make_register_page.py --seed 7 --out fixtures/private/page2.png
    py -3.12 scripts/make_register_page.py --clean         # undegraded control

BEST RESULT: run with --template to get a blank ruled form, HANDWRITE it yourself
in Devanagari, photograph it at an angle in room light, then run --degrade-photo
on that photo. Genuine handwriting + genuine capture conditions beats any font.
"""
from __future__ import annotations

import argparse
import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Devanagari faces present on this machine. Light weight reads most like pen ink.
# Verified available 2026-07-26; the old kokila/mangal names do NOT exist here.
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\NotoSansDevanagari-Light.ttf",
    r"C:\Windows\Fonts\NotoSansDevanagari-Regular.ttf",
    r"C:\Windows\Fonts\NotoSansDevanagari-Medium.ttf",
    r"C:\Windows\Fonts\Nirmala.ttc",
]
W, H = 1700, 2200
INK = (28, 32, 60)

ROWS = [
    # khata, plot/survey, owner (Devanagari), father, area, mutation ref
    ("१२", "SN-142/2", "रामय्या स.", "वेंकटय्या", "२ एकड़ १३ गुंठा", "म. १९९८/४७"),
    ("१३", "SN-143",   "सुशीला देवी", "रामय्या",   "१ एकड़ ०५ गुंठा", "म. २००४/११"),
    ("१४", "SN-144/1", "लक्ष्मम्मा",   "नरसय्या",   "३ एकड़ ०० गुंठा", "म. १९८७/०९"),
    ("१५", "SN-145",   "गोविंद राव",   "शंकर राव",  "०२ एकड़ ३० गुंठा", "म. २०११/०३"),
]
HEADERS = ["खाता", "सर्वे नं.", "मालिक का नाम", "पिता का नाम", "क्षेत्रफल", "फेरफार"]
COLS = [90, 260, 520, 900, 1220, 1500]


LATIN_FONT = r"C:\Windows\Fonts\arial.ttf"


def _load(path: str, size: int):
    try:
        return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    except (OSError, AttributeError):
        return ImageFont.truetype(path, size)


def _font(size: int):
    """Devanagari needs RAQM shaping for conjuncts/matras — PIL reports raqm=True here."""
    for p in FONT_CANDIDATES:
        try:
            return _load(p, size)
        except OSError:
            continue
    raise RuntimeError("No Devanagari font found — checked: " + ", ".join(FONT_CANDIDATES))


def _font_for(text: str, size: int):
    """Noto Devanagari carries no Latin glyphs, so ASCII cells would render as tofu.
    Mixed Latin survey numbers beside Devanagari names is a deliberate hard case
    (Document Intelligence L4/L5 names 'mixed scripts')."""
    if all(ord(c) < 128 for c in text):
        try:
            return _load(LATIN_FONT, size)
        except OSError:
            pass
    return _font(size)


def _paper(rng) -> Image.Image:
    img = Image.new("RGB", (W, H), (236, 226, 200))
    d = ImageDraw.Draw(img)
    for _ in range(2600):                       # fibre speckle
        x, y = rng.randrange(W), rng.randrange(H)
        v = rng.randint(-16, 10)
        base = img.getpixel((x, y))
        d.point((x, y), tuple(max(0, min(255, c + v)) for c in base))
    return img


def _grid(d, f_head):
    d.rectangle([60, 150, W - 60, H - 200], outline=(120, 90, 70), width=3)
    d.text((W // 2 - 300, 70), "ग्राम नमूना नं. ७/१२  —  अधिकार अभिलेख", font=_font(46), fill=(60, 50, 40))
    for i, h in enumerate(HEADERS):
        d.text((COLS[i], 175), h, font=f_head, fill=(70, 55, 45))
    d.line([60, 240, W - 60, 240], fill=(120, 90, 70), width=3)
    for c in COLS[1:]:
        d.line([c - 20, 150, c - 20, H - 200], fill=(150, 120, 95), width=2)


def _write_rows(img, rng, handwrite=True):
    d = ImageDraw.Draw(img)
    y = 300
    for r_i, row in enumerate(ROWS):
        for c_i, cell in enumerate(row):
            jx = rng.randint(-4, 4) if handwrite else 0
            jy = rng.randint(-6, 6) if handwrite else 0
            shade = tuple(min(255, c + rng.randint(-10, 45)) for c in INK)
            d.text((COLS[c_i] + jx, y + jy), cell, font=_font_for(cell, 40), fill=shade)
        d.line([60, y + 95, W - 60, y + 95], fill=(170, 145, 120), width=1)
        y += 130
    return img


def _overwrite(img, rng):
    """A struck-through correction rewritten above — a real register artefact."""
    d = ImageDraw.Draw(img)
    x, y = COLS[2] + 6, 300 + 130          # row 2, owner column
    d.line([x, y + 26, x + 250, y + 20], fill=(150, 30, 30), width=4)
    d.text((x + 20, y - 44), "सुशीला बाई", font=_font(38), fill=(140, 35, 35))
    return img


def _stamp(img, rng):
    """Rubber stamp partially occluding the area column — forces a refusal."""
    s = Image.new("RGBA", (330, 330), (0, 0, 0, 0))
    sd = ImageDraw.Draw(s)
    col = (70, 60, 150, 130)
    sd.ellipse([10, 10, 320, 320], outline=col, width=8)
    sd.ellipse([34, 34, 296, 296], outline=col, width=3)
    sd.text((92, 120), "तहसील", font=_font(44), fill=col)
    sd.text((78, 170), "कार्यालय", font=_font(38), fill=col)
    s = s.rotate(rng.randint(-25, 25), resample=Image.BICUBIC)
    img.paste(s, (COLS[4] - 40, 380), s)       # over area col, rows 1-2
    return img


def _fold_fade_bleed(img, rng):
    d = ImageDraw.Draw(img)
    for fx in (W // 3, 2 * W // 3):            # fold lines
        fx += rng.randint(-30, 30)
        d.line([fx, 0, fx + rng.randint(-12, 12), H], fill=(198, 186, 162), width=7)
    grad = Image.new("L", (W, H), 0)           # corner fade / damp stain
    gd = ImageDraw.Draw(grad)
    for r in range(520, 0, -12):
        gd.ellipse([W - r, H - r, W + r, H + r], fill=int(120 * (1 - r / 520)))
        gd.ellipse([-r // 2, -r // 2, r // 2, r // 2], fill=int(90 * (1 - r / 520)))
    img.paste(Image.new("RGB", (W, H), (222, 208, 176)), (0, 0), grad)
    return img.filter(ImageFilter.GaussianBlur(0.7))   # ink bleed


def _capture(img, rng):
    """Simulate a phone photo: skew, uneven shop light, sensor noise."""
    ang = rng.uniform(-3.2, 3.2)
    img = img.rotate(ang, resample=Image.BICUBIC, expand=True, fillcolor=(60, 58, 54))
    w, h = img.size
    light = Image.new("L", (w, h), 0)
    ld = ImageDraw.Draw(light)
    cx, cy = int(w * rng.uniform(0.25, 0.5)), int(h * rng.uniform(0.15, 0.4))
    for r in range(max(w, h), 0, -20):
        ld.ellipse([cx - r, cy - r, cx + r, cy + r],
                   fill=int(105 * (1 - r / max(w, h))))
    img.paste(Image.new("RGB", (w, h), (25, 22, 18)), (0, 0),
              Image.eval(light, lambda v: 105 - v))
    px = img.load()
    for _ in range(int(w * h * 0.02)):
        x, y = rng.randrange(w), rng.randrange(h)
        v = rng.randint(-22, 22)
        px[x, y] = tuple(max(0, min(255, c + v)) for c in px[x, y])
    return img.resize((int(w * 0.62), int(h * 0.62)), Image.LANCZOS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="fixtures/private/register_page.png")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--clean", action="store_true", help="no degradation (control)")
    ap.add_argument("--template", action="store_true", help="blank ruled form to handwrite")
    a = ap.parse_args()

    rng = random.Random(a.seed)
    img = _paper(rng)
    _grid(ImageDraw.Draw(img), _font(38))

    if not a.template:
        img = _write_rows(img, rng)
        img = _overwrite(img, rng)
        img = _stamp(img, rng)
    if not (a.clean or a.template):
        img = _fold_fade_bleed(img, rng)
        img = _capture(img, rng)

    import pathlib
    p = pathlib.Path(a.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p, quality=88)
    print(f"wrote {p}  ({img.size[0]}x{img.size[1]})")
    if not a.template:
        print("hard cases present: stamp over area col (rows 1-2), struck-through "
              "owner correction (row 2), fold lines, corner fade, skew, uneven light")


if __name__ == "__main__":
    main()
