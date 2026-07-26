"""Page-evidence reader for the handwritten mutation-register page.

This module reads *physical* facts off the photograph — where the ruled form
sits on the sensor, and which cells are covered by seal ink or crossed out by a
correction stroke. It deliberately reads NO text: transcription is
feat/extraction's job (Sarvam Doc-Intelligence). What lives here is the thing a
transcription model cannot give us — a second, independent opinion on whether
the paper under a value was legible at all.

Why that matters: an OCR that returns "२ एकड़ १३ गुंठा" at 0.91 confidence for a
cell with a tehsil seal across it is confidently wrong, and confidence alone
will never catch it. The pixels will. `policy.py` uses this to overrule a
high-confidence reading, which is the whole L4→L5 move for Document
Intelligence.

Pure local work: Pillow only, no network, no key, deterministic.
"""
from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass
from dataclasses import field as dc_field

# --- the ruled form's own geometry ------------------------------------------
# These are the FORM's coordinates (scripts/make_register_page.py draws the
# blank template at 1700x2200), not the photograph's. `register_page()` maps
# them onto whatever the camera actually produced. Handwriting the blank
# template and photographing it therefore still lands on the right cells.
FORM_W, FORM_H = 1700, 2200
FORM_COLS = [90, 260, 520, 900, 1220, 1500]      # x of each column's text origin
FORM_COL_END = FORM_W - 60                        # right edge of the last column
FORM_ROW0, FORM_ROW_H = 300, 130                  # y of the first entry's baseline
FORM_CELL_TOP, FORM_CELL_H = -14, 66              # cell box around that baseline
FORM_ROWS = 4                                     # entry rows the register carries

# Column index -> the field name a reading of that column carries.
COLUMN_FIELDS = ["khata_no", "survey_no", "owner_name", "father_name", "area",
                 "mutation_ref"]

# --- colour tests ------------------------------------------------------------
# Tuned on the seed-42/seed-7 pages, verified (not tuned) on the held-out page.
# Stamp ink composites to a light blue-violet; the correction stroke is a
# saturated red. Ordinary iron-gall-ish writing ink is dark and near-neutral,
# and paper is warm (R>G>B) — both are excluded by the margins below.
SEAL_MIN_B_OVER_R = 10
SEAL_MIN_B_OVER_G = 6
SEAL_MIN_LUM = 96
STRIKE_MIN_R_OVER_G = 42
STRIKE_MIN_R_OVER_B = 42
INK_MAX_LUM = 112               # writing: dark and near-neutral
PAPER_MIN_LUM = 95              # anything darker at the border is camera fill

SCAN_WIDTH = 640                # defect scan resolution; crops use full res
TILE = 8                        # scan tile edge, in scan-resolution pixels
TILE_HIT = 0.10                 # share of a tile's pixels that must be defect
# Writing is THIN — a pen stroke at scan resolution is a pixel or two wide, so
# the bar for "there are words here" has to sit well below the bar for "there
# is a rubber stamp here", which is a broad wash of colour.
INK_TILE_HIT = 0.05
INK_BAND_MARGIN = 0             # tiles of slack around the writing, for matras
MIN_BLOB_TILES = 4              # smaller than this is ink bleed, not a defect
BLOB_GAP = 2                    # tiles this close belong to one obstruction
# Sensor noise flips isolated pixels into any colour class, so a defect only
# counts where it survives tiling. This is the share of the WRITING BAND — not
# of the cell — that an obstruction must cover before it counts as reaching the
# words. Deliberately low: measured against both visible demo pages it catches
# every genuinely buried cell, and over-refuses one where the stamp's arc grazes
# the line above the text. That bias is the intended one — a wrong refusal costs
# a glance at the crop, a wrong reading costs a rejected mutation — but it is a
# bias, and `defects_over` reports the measured coverage so a human can see how
# marginal a given call was. See docs/handoff/feat-register.md.
MIN_WRITING_COVER = 0.06


@dataclass
class Defect:
    """A physical obstruction found on the page, in normalised page coords."""
    kind: str                                # "seal" | "strike"
    bbox: list[float]
    tiles: int
    note: str


@dataclass
class Cell:
    """One cell of the ruled form, located on the photograph."""
    row: int
    col: int
    field: str
    bbox: list[float]
    defects: list[Defect] = dc_field(default_factory=list)

    @property
    def occlusion(self) -> str | None:
        return self.defects[0].kind if self.defects else None


@dataclass
class PageAudit:
    image_path: str
    size: tuple[int, int]
    registered: bool                         # False => corners not found, coords approximate
    corners: dict
    defects: list[Defect]
    cells: list[Cell]
    scan: tuple[int, int] = (0, 0)           # resolution the masks were built at
    tiles: dict = dc_field(default_factory=dict)   # kind -> {(tx,ty): hit count}

    def cell(self, row: int, col: int) -> Cell | None:
        return next((c for c in self.cells if c.row == row and c.col == col), None)

    def cell_at(self, bbox: list[float]) -> Cell | None:
        """The form cell a reading's bbox sits in — highest overlap wins."""
        best, best_ov = None, 0.0
        for c in self.cells:
            ov = _overlap(c.bbox, bbox)
            if ov > best_ov:
                best, best_ov = c, ov
        return best if best_ov > 0.15 else None

    def _hot(self, kind: str) -> set[tuple[int, int]]:
        floor = TILE * TILE * (INK_TILE_HIT if kind == "ink" else TILE_HIT)
        return {t for t, n in self.tiles.get(kind, {}).items() if n >= floor}

    def _tile_span(self, bbox: list[float]) -> tuple[int, int, int, int]:
        sw, sh = self.scan
        return (int(bbox[0] * sw) // TILE, int(bbox[1] * sh) // TILE,
                max(int(bbox[0] * sw) // TILE, (int(bbox[2] * sw) - 1) // TILE),
                max(int(bbox[1] * sh) // TILE, (int(bbox[3] * sh) - 1) // TILE))

    def writing_band(self, bbox: list[float]) -> list[float]:
        """The part of a cell the writing actually occupies.

        Found from the ink itself rather than assumed from the ruling, because
        what matters is whether an obstruction crosses the WORDS. Falls back to
        the whole cell when no ink is found — an empty cell has nothing to read
        either way.
        """
        if not self.scan[0]:
            return list(bbox)
        tx0, ty0, tx1, ty1 = self._tile_span(bbox)
        rows = sorted({ty for (tx, ty) in self._hot("ink")
                       if tx0 <= tx <= tx1 and ty0 <= ty <= ty1})
        if not rows:
            return list(bbox)
        sh = self.scan[1]
        top = max(ty0, rows[0] - INK_BAND_MARGIN) * TILE / sh
        bottom = (min(ty1, rows[-1] + INK_BAND_MARGIN) + 1) * TILE / sh
        return [bbox[0], top, bbox[2], bottom]

    def cover(self, bbox: list[float], kind: str) -> float:
        """Share of `bbox` that surviving `kind` tiles occupy."""
        if not self.scan[0]:
            return 0.0
        tx0, ty0, tx1, ty1 = self._tile_span(bbox)
        n = sum(1 for (tx, ty) in self._hot(kind)
                if tx0 <= tx <= tx1 and ty0 <= ty <= ty1)
        span = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
        return n / span if span else 0.0

    def obstructions(self, bbox: list[float]) -> list[tuple[Defect, float]]:
        """(defect, share of the writing band it covers), worst first.

        Touching the cell is not enough. The test is whether the obstruction
        reaches the words, measured on the noise-filtered tile mask — and the
        share is carried out with it, so a refusal can say how badly the cell
        was covered instead of only that it was.
        """
        band = self.writing_band(bbox)
        hits = []
        for d in self.defects:
            if _overlap(band, d.bbox) <= 0:
                continue
            cover = self.cover(band, d.kind)
            if cover >= MIN_WRITING_COVER:
                hits.append((d, cover))
        return sorted(hits, key=lambda t: -t[1])

    def defects_over(self, bbox: list[float]) -> list[Defect]:
        return [d for d, _ in self.obstructions(bbox)]


def _overlap(a: list[float], b: list[float]) -> float:
    """Share of `a` that `b` covers."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    area = (a[2] - a[0]) * (a[3] - a[1])
    return (ix * iy / area) if area > 0 else 0.0


def _lum(p) -> float:
    return 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]


def is_seal(p) -> bool:
    return (p[2] - p[0] >= SEAL_MIN_B_OVER_R and p[2] - p[1] >= SEAL_MIN_B_OVER_G
            and _lum(p) >= SEAL_MIN_LUM)


def is_strike(p) -> bool:
    return (p[0] - p[1] >= STRIKE_MIN_R_OVER_G
            and p[0] - p[2] >= STRIKE_MIN_R_OVER_B)


# --- page registration -------------------------------------------------------

def _paper_corners(im) -> dict | None:
    """Locate the sheet's four corners on the sensor.

    A photographed page arrives rotated inside a darker frame (camera fill or
    desk). Scanning for the extreme paper pixels gives the sheet's quad, which
    is all we need to put form coordinates onto the photograph. Perspective is
    not modelled — a flat-on phone photo is the stated demo input.
    """
    w, h = im.size
    px = im.load()
    step = max(1, min(w, h) // 400)
    run_needed = 3
    extremes = {"top": None, "bottom": None, "left": None, "right": None}

    def paper_run(x, y, dx, dy) -> bool:
        for k in range(run_needed):
            xx, yy = x + dx * k, y + dy * k
            if not (0 <= xx < w and 0 <= yy < h) or _lum(px[xx, yy]) < PAPER_MIN_LUM:
                return False
        return True

    for y in range(0, h, step):                      # left / right extremes
        for x in range(0, w):
            if paper_run(x, y, 1, 0):
                if extremes["left"] is None or x < extremes["left"][0]:
                    extremes["left"] = (x, y)
                break
        for x in range(w - 1, -1, -1):
            if paper_run(x, y, -1, 0):
                if extremes["right"] is None or x > extremes["right"][0]:
                    extremes["right"] = (x, y)
                break
    for x in range(0, w, step):                      # top / bottom extremes
        for y in range(0, h):
            if paper_run(x, y, 0, 1):
                if extremes["top"] is None or y < extremes["top"][1]:
                    extremes["top"] = (x, y)
                break
        for y in range(h - 1, -1, -1):
            if paper_run(x, y, 0, -1):
                if extremes["bottom"] is None or y > extremes["bottom"][1]:
                    extremes["bottom"] = (x, y)
                break
    if any(v is None for v in extremes.values()):
        return None
    return extremes


def _fit_quad(ext: dict, w: int, h: int) -> dict | None:
    """Label the four extreme points as TL/TR/BL of the form.

    The sheet may be tilted either way, giving two possible labelings. Pick the
    one whose edge-length ratio matches the form's own aspect ratio; if neither
    does, registration failed and we say so rather than cropping the wrong cell.
    """
    t, r, b, l = ext["top"], ext["right"], ext["bottom"], ext["left"]
    want = FORM_W / FORM_H
    best, best_err = None, None
    for tl, tr, bl in ((t, r, l), (l, t, b)):        # tilt one way, then the other
        top_len = math.dist(tl, tr)
        side_len = math.dist(tl, bl)
        if top_len < w * 0.4 or side_len < h * 0.4:
            continue
        err = abs(top_len / side_len - want) / want
        if best_err is None or err < best_err:
            best, best_err = {"tl": tl, "tr": tr, "bl": bl}, err
    if best is None or best_err > 0.12:
        return None
    return best


def _mapper(quad: dict | None, w: int, h: int):
    """form (u,v) -> normalised photograph (x,y)."""
    if quad is None:                                  # degrade: assume flat-on
        return lambda u, v: (u / FORM_W, v / FORM_H)
    (x0, y0), (x1, y1), (x2, y2) = quad["tl"], quad["tr"], quad["bl"]

    def to_page(u: float, v: float) -> tuple[float, float]:
        fu, fv = u / FORM_W, v / FORM_H
        x = x0 + fu * (x1 - x0) + fv * (x2 - x0)
        y = y0 + fu * (y1 - y0) + fv * (y2 - y0)
        return (x / w, y / h)
    return to_page


# --- defect detection --------------------------------------------------------

def _blobs(tiles: set[tuple[int, int]], gap: int = BLOB_GAP) -> list[list[tuple[int, int]]]:
    """Tile groups, tolerating a `gap`-tile break.

    A rubber stamp is a RING: its centre is bare paper, and the ring itself
    breaks up wherever the impression is faint. Strict adjacency would report
    one seal as eight unrelated smudges, so tiles within `gap` of each other
    join the same defect — one physical obstruction, one crop. Scattered single
    tiles (ink bleed at a stroke edge) still fall below MIN_BLOB_TILES.
    """
    seen, out = set(), []
    for start in sorted(tiles):
        if start in seen:
            continue
        stack, group = [start], []
        seen.add(start)
        while stack:
            tx, ty = stack.pop()
            group.append((tx, ty))
            for dx in range(-gap, gap + 1):
                for dy in range(-gap, gap + 1):
                    nb = (tx + dx, ty + dy)
                    if nb in tiles and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        out.append(group)
    return out


def is_ink(p) -> bool:
    return _lum(p) <= INK_MAX_LUM and not is_strike(p) and not is_seal(p)


def _scan_page(im):
    """One pass over the page: classify every pixel, accumulate per-tile counts,
    then read the obstructions off the tile mask. Tiling is what makes this
    robust to sensor noise, which flips isolated pixels into any colour class."""
    w, h = im.size
    scale = min(1.0, SCAN_WIDTH / w)
    sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
    px = im.resize((sw, sh)).load()

    counts: dict[str, dict[tuple[int, int], int]] = {"seal": {}, "strike": {}, "ink": {}}
    for y in range(sh):
        ty = y // TILE
        for x in range(sw):
            p = px[x, y]
            if is_strike(p):
                kind = "strike"
            elif is_seal(p):
                kind = "seal"
            elif _lum(p) <= INK_MAX_LUM:
                kind = "ink"
            else:
                continue
            key = (x // TILE, ty)
            counts[kind][key] = counts[kind].get(key, 0) + 1

    out: list[Defect] = []
    for kind in ("seal", "strike"):
        hot = {k for k, n in counts[kind].items() if n >= TILE * TILE * TILE_HIT}
        for group in _blobs(hot):
            if len(group) < MIN_BLOB_TILES:
                continue
            xs = [t[0] for t in group]
            ys = [t[1] for t in group]
            bbox = [min(xs) * TILE / sw, min(ys) * TILE / sh,
                    (max(xs) + 1) * TILE / sw, (max(ys) + 1) * TILE / sh]
            note = ("an office seal is stamped across this cell"
                    if kind == "seal" else
                    "the entry is struck through and rewritten")
            out.append(Defect(kind=kind, bbox=bbox, tiles=len(group), note=note))
    out.sort(key=lambda d: -d.tiles)
    return out, counts, (sw, sh)


def find_defects(im) -> list[Defect]:
    """Seal blobs and correction strokes, in normalised page coordinates."""
    return _scan_page(im)[0]


# --- the audit ---------------------------------------------------------------

def audit_page(image_path: str) -> PageAudit:
    """Register the form on the photograph and mark every obstructed cell.

    Reads no text and invents no values — every field it reports is either a
    measured coordinate or a colour statistic.
    """
    from PIL import Image

    path = pathlib.Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"page image not found: {image_path}")
    with Image.open(path) as opened:
        im = opened.convert("RGB")
        w, h = im.size
        ext = _paper_corners(im)
        quad = _fit_quad(ext, w, h) if ext else None
        to_page = _mapper(quad, w, h)
        defects, tiles, scan = _scan_page(im)

    cells: list[Cell] = []
    for row in range(FORM_ROWS):
        v0 = FORM_ROW0 + row * FORM_ROW_H + FORM_CELL_TOP
        v1 = v0 + FORM_CELL_H
        if v1 > FORM_H:
            break
        for col, fname in enumerate(COLUMN_FIELDS):
            u0 = FORM_COLS[col] - 24
            u1 = (FORM_COLS[col + 1] if col + 1 < len(FORM_COLS) else FORM_COL_END) - 24
            corners = [to_page(u0, v0), to_page(u1, v0), to_page(u0, v1), to_page(u1, v1)]
            xs = [c[0] for c in corners]
            ys = [c[1] for c in corners]
            bbox = [max(0.0, min(xs)), max(0.0, min(ys)),
                    min(1.0, max(xs)), min(1.0, max(ys))]
            cell = Cell(row=row, col=col, field=fname, bbox=bbox)
            cells.append(cell)

    audit = PageAudit(image_path=str(path), size=(w, h), registered=quad is not None,
                      corners=quad or {}, defects=defects, cells=cells,
                      scan=scan, tiles=tiles)
    for cell in cells:
        cell.defects = audit.defects_over(cell.bbox)
    return audit


# --- attaching the audit to what a model read --------------------------------

ROW_QUALIFIER = "@"


def qualified_name(field_name: str, plot: str) -> str:
    """`area@SN-144/1` — the same field, on a row this obligation is not about.

    Qualified readings still get policy, refusals and crops (the seal covers
    three rows and a human should be told so); they just do not pretend to be
    this obligation's own identity.
    """
    return f"{field_name}{ROW_QUALIFIER}{plot}"


def base_name(field_name: str) -> str:
    return (field_name or "").split(ROW_QUALIFIER)[0]

def draft_from_page(image_path: str, doc_id: str, rows: list[dict],
                    obligation_id: str = "R1", asked_what: str = "",
                    asked_by: str = "") -> "ObligationDraft":
    """Build an ObligationDraft whose readings carry this page's real geometry.

    THE VALUES ARE THE CALLER'S. In the live pipeline they come from Sarvam
    Doc-Intelligence via feat/extraction, which supplies its own bboxes and this
    function is not needed. It exists so the register branch can be exercised —
    and demonstrated — on a page with no API key in the room: geometry,
    occlusion and every resulting refusal are measured from the image you pass,
    while the transcribed text is whatever the caller hands over.

    `rows` is [{"row": 0, "survey_no": ("SN-142/2", 0.93), ...}, ...] where each
    value is (text, confidence) and the key is a column name in COLUMN_FIELDS.
    The FIRST row is the one the obligation is about; every later row is
    qualified as `<field>@<plot>` (see `qualified_name`), because a register page
    lists several plots and the sequencer — rightly — reads two readings of
    plain `owner_name` on one obligation as a contradiction about one person.
    """
    from ..contracts import FieldReading, ObligationDraft, SourceRef

    audit = audit_page(image_path)
    fields: list[FieldReading] = []
    for i, spec in enumerate(rows):
        row = int(spec.get("row", 0))
        plot = (spec.get("survey_no") or spec.get("plot_no") or (f"row {row + 1}",))[0]
        for col_name, reading in spec.items():
            if col_name == "row" or col_name not in COLUMN_FIELDS:
                continue
            value, confidence = reading
            cell = audit.cell(row, COLUMN_FIELDS.index(col_name))
            if cell is None:
                continue
            fields.append(FieldReading(
                name=col_name if i == 0 else qualified_name(col_name, plot),
                value=value, confidence=float(confidence), status="read",
                source=SourceRef(doc_id=doc_id, page=1, bbox=cell.bbox,
                                 quote=value)))
    return ObligationDraft(
        id=obligation_id, doc_id=doc_id, doc_type="mutation_register_page",
        asked_what=asked_what or ("File record-correction application at the tehsil so "
                                  "the register entry matches the heir's ID"),
        asked_by=asked_by or "Tehsil office",
        provides=["record_name_matches_id"], identity_fields=fields,
        raw_excerpt=f"Handwritten record-of-rights page ({len(rows)} entry rows read).")
