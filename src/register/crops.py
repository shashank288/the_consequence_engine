"""Field-level crop generation — the Delight moment (card 87).

A refusal that says "area: unreadable" is a claim. A refusal that shows the
1.5 cm of paper the seal is sitting on is *evidence*: the judge looks at the
crop and agrees the field genuinely cannot be read. So every refused field on
a page we hold gets its own image, not a link to the whole page.

Pillow is imported lazily: a case assembled without any page image (the fixture
demo path) must never depend on an imaging library being importable.
"""
from __future__ import annotations

import hashlib
import pathlib

# 8% of the cell's own size, so a wide area cell gets wide padding and a narrow
# khata cell gets narrow padding. Enough to show the ruling lines either side —
# that context is what makes a crop legible as "a cell of a form".
DEFAULT_PAD = 0.08
MIN_PAD_PX = 6

WEB_DIR = pathlib.Path(__file__).resolve().parents[2] / "web"
DEFAULT_OUT = "web/crops"


class CropUnavailable(RuntimeError):
    """Raised when the crop cannot be produced. Callers must degrade to a
    quote-only refusal — the refusal itself is never conditional on an image."""


def crop_id(image_path: str, bbox: list[float], name: str | None = None) -> str:
    """Deterministic filename: the same field on the same page always writes to
    the same file, so re-running the demo cannot accumulate stale crops."""
    stem = pathlib.Path(image_path).stem[:24]
    digest = hashlib.sha1(
        f"{stem}|{['%.4f' % c for c in bbox]}".encode("utf-8")
    ).hexdigest()[:8]
    label = "".join(c if c.isalnum() or c in "-_" else "_" for c in (name or "field"))
    return f"{stem}-{label}-{digest}.png"


def crop_field(image_path: str, bbox: list[float], out_dir: str = DEFAULT_OUT,
               name: str | None = None, pad: float = DEFAULT_PAD) -> str:
    """Crop the normalised `bbox` out of `image_path` and return a WEB path.

    `bbox` is [x0, y0, x1, y1] normalised 0-1 exactly as `SourceRef.bbox`
    carries it. The returned string is what goes into `SourceRef.crop_path`:
    `crops/<id>.png`, servable by the StaticFiles mount on web/ in src/app.py.
    """
    try:
        from PIL import Image
    except ImportError as exc:                       # pragma: no cover - env issue
        raise CropUnavailable(f"Pillow not available: {exc}") from exc

    src = pathlib.Path(image_path)
    if not src.exists():
        raise CropUnavailable(f"page image not found: {image_path}")
    if not bbox or len(bbox) != 4:
        raise CropUnavailable(f"bbox must be [x0,y0,x1,y1], got {bbox!r}")

    x0, y0, x1, y1 = (float(v) for v in bbox)
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        raise CropUnavailable(f"degenerate bbox: {bbox!r}")

    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        px0, py0, px1, py1 = x0 * w, y0 * h, x1 * w, y1 * h
        pad_x = max(MIN_PAD_PX, (px1 - px0) * pad)
        pad_y = max(MIN_PAD_PX, (py1 - py0) * pad)
        box = (max(0, int(px0 - pad_x)), max(0, int(py0 - pad_y)),
               min(w, int(px1 + pad_x)), min(h, int(py1 + pad_y)))
        if box[2] - box[0] < 2 or box[3] - box[1] < 2:
            raise CropUnavailable(f"bbox lands outside the page: {bbox!r}")
        out = pathlib.Path(out_dir)
        if not out.is_absolute():
            out = pathlib.Path(__file__).resolve().parents[2] / out
        out.mkdir(parents=True, exist_ok=True)
        fname = crop_id(image_path, [x0, y0, x1, y1], name)
        im.crop(box).save(out / fname)

    # Web path, not a filesystem path: app.py mounts web/ at "/", so a crop
    # written to web/crops/x.png is served at /crops/x.png.
    try:
        rel = out.resolve().relative_to(WEB_DIR)
        return f"{rel.as_posix()}/{fname}"
    except ValueError:
        return f"crops/{fname}"
