"""แบบขออนุมัติ / Drawing for Approval — SVG generator.

ไม่ต้องติดตั้งไลบรารีเพิ่ม: สร้าง SVG ด้วย string ล้วน แล้วเปิดในเบราว์เซอร์
เหมือนหน้าพิมพ์ใบเสนอราคาเดิม

รูปแบบหน้ากระดาษอ้างอิงแบบที่ผู้บริหารอนุมัติเมื่อ 26-08-2026
(A4 แนวนอน, หัวกระดาษ, ตารางสเปก, หมายเหตุ, ตารางลงนามด้านล่าง)
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field as dc_field
from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

# --- โทนสี (เปลี่ยนที่นี่ที่เดียว มีผลกับทุกประเภทสินค้า) ------------------
INK = "#183B5B"
DARK = "#293A49"
MID = "#657889"
LIGHT = "#E9EFF4"
PALE = "#F7F9FB"
MINF = "#FDEBD3"
MAXF = "#E4F0E2"

PAGE_W, PAGE_H = 841.89, 595.28   # A4 แนวนอน หน่วย pt
MARGIN = 18.0
HEADER_Y = 500.0
INFO_Y = 452.0
TITLEBLK_Y = 145.0
SPLIT_X = 585.0
HEADER_RX = 650.0

MM_PER_INCH = 25.4
FONT = "Arial, Helvetica, sans-serif"

COMPANY_NAME = "PANTONG THAI PACK CO., LTD."

# ประเภทสินค้าในโปรแกรมคำนวณราคา -> รูปที่ใช้วาด
PRODUCT_TO_SHAPE = {
    "flat": "flat_bag",
    "sleeve": "open_ended_sleeve",
    "gusset": "gusset_bag",
    "opaque": "plastic_sheet",
    "roll": "plastic_roll",
    "cover": "product_cover",
}

LENGTH_DATUM_TEXT = {
    "opening_to_seal": "OPENING TO SEAL",
    "opening_to_bottom": "OPENING TO BOTTOM",
}


class DrawingError(Exception):
    """ข้อมูลไม่พอหรือไม่ถูกต้องสำหรับการออกแบบ"""


@dataclass
class DimRow:
    item: str
    nominal: float
    lo: float | None
    hi: float | None
    unit: str
    decimals: int = 0
    bold: bool = False


@dataclass
class DrawingSpec:
    doc_no: str
    customer: str
    title: str
    shape: str                      # คีย์ในตาราง SHAPES
    revision: str = "A"
    date: str = ""
    part_no: str = "-"
    customer_code: str = ""
    material: str = "POLYETHYLENE"
    color: str = "-"
    printing: str = "-"
    # เก็บเป็นมิลลิเมตรเสมอ หน่วยที่ผู้ใช้เลือกเป็นแค่การแสดงผล
    width_mm: float = 0.0
    length_mm: float = 0.0
    height_mm: float = 0.0
    gusset_mm: float = 0.0
    thickness_mm: float = 0.0
    tol_dim_lo: float = -10.0
    tol_dim_hi: float = 10.0
    tol_thickness: float = 0.005
    length_datum: str = ""          # opening_to_seal | opening_to_bottom
    display_unit: str = "mm"        # mm | inch
    dimension_units: dict[str, str] = dc_field(default_factory=dict)
    holes_count: int = 0
    holes_dia: str = ""
    label_w: float = 0.0
    label_h: float = 0.0
    extra_notes: list[str] = dc_field(default_factory=list)
    drawing_view: str = "2d"

    def length_label(self) -> str:
        return LENGTH_DATUM_TEXT.get(self.length_datum, "LENGTH")


# --------------------------------------------------------------------------
# เครื่องมือวาด: แปลงแกน y จากระบบ PDF (ล่างขึ้นบน) เป็น SVG (บนลงล่าง)
# --------------------------------------------------------------------------
def _y(v: float) -> float:
    return PAGE_H - v


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


class Pen:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def svg(self) -> str:
        return "\n".join(self.parts)

    def txt(self, x, y, value, size=8.0, bold=False, align="left", color=DARK, angle=0.0):
        if value in ("", None):
            return
        anchor = {"left": "start", "center": "middle", "right": "end"}[align]
        transform = ""
        if angle:
            # แกน y กลับด้าน มุมหมุนจึงต้องกลับเครื่องหมาย
            transform = f' transform="rotate({-angle:.3f} {x:.2f} {_y(y):.2f})"'
        weight = ' font-weight="bold"' if bold else ""
        self.parts.append(
            f'<text x="{x:.2f}" y="{_y(y):.2f}" font-family="{FONT}" '
            f'font-size="{size:.2f}" fill="{color}" text-anchor="{anchor}"'
            f'{weight}{transform}>{_esc(value)}</text>'
        )

    def line(self, x1, y1, x2, y2, w=0.6, color=DARK, dash=None):
        d = f' stroke-dasharray="{",".join(str(v) for v in dash)}"' if dash else ""
        self.parts.append(
            f'<line x1="{x1:.2f}" y1="{_y(y1):.2f}" x2="{x2:.2f}" y2="{_y(y2):.2f}" '
            f'stroke="{color}" stroke-width="{w}"{d}/>'
        )

    def rect(self, x, y, w, h, lw=0.6, fill="none", color=DARK):
        self.parts.append(
            f'<rect x="{x:.2f}" y="{_y(y + h):.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'fill="{fill}" stroke="{color}" stroke-width="{lw}"/>'
        )

    def fill_rect(self, x, y, w, h, fill):
        self.parts.append(
            f'<rect x="{x:.2f}" y="{_y(y + h):.2f}" width="{w:.2f}" height="{h:.2f}" '
            f'fill="{fill}" stroke="none"/>'
        )

    def poly(self, pts, lw=1.4, fill="none", color=INK):
        chain = " ".join(f"{px:.2f},{_y(py):.2f}" for px, py in pts)
        self.parts.append(
            f'<polygon points="{chain}" fill="{fill}" stroke="{color}" stroke-width="{lw}"/>'
        )

    def ellipse(self, cx, cy, rx, ry, lw=1.0, color=INK):
        self.parts.append(
            f'<ellipse cx="{cx:.2f}" cy="{_y(cy):.2f}" rx="{rx:.2f}" ry="{ry:.2f}" '
            f'fill="none" stroke="{color}" stroke-width="{lw}"/>'
        )

    def arrow_head(self, x, y, tx, ty, size=6.0):
        a = math.atan2(ty - y, tx - x)
        for d in (-0.48, 0.48):
            self.line(x, y, x + size * math.cos(a + d), y + size * math.sin(a + d), 0.8, INK)

    def dim(self, x1, y1, x2, y2, label="", size=9.5, offset=9.0):
        """เส้นบอกขนาดสองหัวลูกศร ตัวอักษรวางขนานกับเส้น"""
        self.line(x1, y1, x2, y2, 0.9, INK)
        self.arrow_head(x1, y1, x2, y2)
        self.arrow_head(x2, y2, x1, y1)
        if not label:
            return
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if ang > 90 or ang < -90:
            ang += 180
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        nx, ny = -(y2 - y1), (x2 - x1)
        n = math.hypot(nx, ny) or 1.0
        self.txt(mx + nx / n * offset, my + ny / n * offset, label, size, True, "center", INK, ang)

    def ext(self, x1, y1, x2, y2):
        """เส้นต่อขนาด บางและสีจาง ตามหลักเขียนแบบ"""
        self.line(x1, y1, x2, y2, 0.45, MID)


class Box:
    """กล่องหน่วย -> พิกัดจริง คงสัดส่วน และอยู่กึ่งกลางพื้นที่วาดเสมอ"""

    def __init__(self, x0, y0, x1, y1, aspect):
        w, h = x1 - x0, y1 - y0
        if w / h > aspect:
            w = h * aspect
        else:
            h = w / aspect
        self.cx, self.cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.w, self.h = w, h

    def p(self, u, v):
        return (self.cx + (u - 0.5) * self.w, self.cy + (v - 0.5) * self.h)


# --------------------------------------------------------------------------
# ตารางรูปทรง: ประเภทสินค้าเป็นตัวเลือกวิธีวาด
# เพิ่มสินค้าใหม่ = เพิ่มฟังก์ชันหนึ่งตัว ไม่ต้องแก้ตัวสร้างหน้ากระดาษ
# --------------------------------------------------------------------------
SHAPES: dict[str, Callable] = {}


def shape(name):
    def wrap(fn):
        SHAPES[name] = fn
        return fn
    return wrap


@shape("flat_bag")
def _flat_bag(pen: Pen, area, spec: DrawingSpec):
    x0, y0, x1, y1 = area
    ratio = (spec.width_mm / spec.length_mm) if spec.length_mm else 0.7
    b = Box(x0 + 45, y0 + 55, x1 - 45, y1 - 45, max(0.35, min(1.6, ratio)))
    left, right = b.p(0, 0)[0], b.p(1, 0)[0]
    bottom, top = b.p(0, 0)[1], b.p(0, 1)[1]
    pen.rect(left, bottom, right - left, top - bottom, 1.7, PALE, INK)
    seal_y = bottom + 14
    # Solid seal band; its upper edge remains the opening-to-seal datum.
    pen.line(left, seal_y, right, seal_y, 1.0, INK)
    pen.line(left, seal_y - 3, right, seal_y - 3, 1.0, INK)
    pen.txt((left + right) / 2, top + 13, "BAG OPENING", 8.5, True, "center", INK)
    pen.txt((left + right) / 2, seal_y + 6, "SEAL LINE", 7.5, True, "center", INK)
    bot_ref = seal_y if spec.length_datum == "opening_to_seal" else bottom
    return [
        ("width", (left, bottom - 24), (right, bottom - 24), (left, bottom), (right, bottom)),
        ("length", (right + 32, bot_ref), (right + 32, top), (right, bot_ref), (right, top)),
    ]


@shape("gusset_bag")
def _gusset_bag(pen: Pen, area, spec: DrawingSpec):
    calls = _flat_bag(pen, area, spec)
    left, right = calls[0][1][0], calls[0][2][0]
    bottom, top = calls[0][3][1], calls[1][2][1]
    g = (right - left) * 0.14
    for x in (left + g, right - g):
        pen.line(x, bottom, x, top, 0.6, MID, [3, 3])
    pen.txt(left + g / 2 + 3, bottom + 30, "GUSSET", 6.5, True, "left", MID, 90)
    return calls


@shape("open_ended_sleeve")
def _open_ended_sleeve(pen: Pen, area, spec: DrawingSpec):
    """Tubular PE sleeve: two material layers, open at both ends, no seal."""
    x0, y0, x1, y1 = area
    ratio = (spec.width_mm / spec.length_mm) if spec.length_mm else 0.7
    b = Box(x0 + 45, y0 + 60, x1 - 45, y1 - 55, max(0.35, min(1.6, ratio)))
    left, right = b.p(0, 0)[0], b.p(1, 0)[0]
    bottom, top = b.p(0, 0)[1], b.p(0, 1)[1]
    pen.rect(left, bottom, right - left, top - bottom, 1.7, PALE, INK)
    pen.txt((left + right) / 2, top + 13, "OPEN TOP", 8.5, True, "center", INK)
    pen.txt((left + right) / 2, bottom - 13, "OPEN BOTTOM", 8.5, True, "center", INK)
    return [
        ("width", (left, bottom - 29), (right, bottom - 29), (left, bottom), (right, bottom)),
        ("length", (right + 32, bottom), (right + 32, top), (right, bottom), (right, top)),
    ]


@shape("plastic_sheet")
def _plastic_sheet(pen: Pen, area, spec: DrawingSpec):
    x0, y0, x1, y1 = area
    ratio = (spec.width_mm / spec.length_mm) if spec.length_mm else 1.2
    b = Box(x0 + 45, y0 + 55, x1 - 45, y1 - 45, max(0.35, min(1.8, ratio)))
    left, right = b.p(0, 0)[0], b.p(1, 0)[0]
    bottom, top = b.p(0, 0)[1], b.p(0, 1)[1]
    pen.rect(left, bottom, right - left, top - bottom, 1.7, PALE, INK)
    pen.txt((left + right) / 2, (bottom + top) / 2 - 4, "PLASTIC SHEET", 9, True, "center", INK)
    return [
        ("width", (left, bottom - 24), (right, bottom - 24), (left, bottom), (right, bottom)),
        ("length", (right + 32, bottom), (right + 32, top), (right, bottom), (right, top)),
    ]


@shape("plastic_roll")
def _plastic_roll(pen: Pen, area, spec: DrawingSpec):
    x0, y0, x1, y1 = area
    b = Box(x0 + 60, y0 + 62, x1 - 60, y1 - 50, 1.7)
    left, right = b.p(0, 0)[0], b.p(1, 0)[0]
    bottom, top = b.p(0, 0.18)[1], b.p(0, 0.82)[1]
    rx = (right - left) * 0.07
    pen.rect(left, bottom, right - left, top - bottom, 1.5, PALE, INK)
    pen.ellipse(right, (bottom + top) / 2, rx, (top - bottom) / 2, 1.5)
    pen.ellipse(left, (bottom + top) / 2, rx, (top - bottom) / 2, 0.7, MID)
    pen.txt((left + right) / 2, (bottom + top) / 2 - 4, "PLASTIC ROLL", 9, True, "center", INK)
    return [
        ("width", (left, bottom - 26), (right, bottom - 26), (left, bottom), (right, bottom)),
        ("length", (right + rx + 30, bottom), (right + rx + 30, top), (right + rx, bottom), (right + rx, top)),
    ]


@shape("product_cover")
def _product_cover(pen: Pen, area, spec: DrawingSpec):
    x0, y0, x1, y1 = area
    b = Box(x0 + 60, y0 + 62, x1 - 60, y1 - 50, 1.35)
    dx, dy = b.w * 0.24, b.h * 0.22
    fl, fr = b.p(0.0, 0)[0], b.p(0.70, 0)[0]
    fb, ft = b.p(0, 0.06)[1], b.p(0, 0.74)[1]
    pen.poly([(fl, ft), (fr, ft), (fr + dx, ft + dy), (fl + dx, ft + dy)], 1.5, LIGHT)
    pen.rect(fl, fb, fr - fl, ft - fb, 1.5, PALE, INK)
    pen.poly([(fr, ft), (fr + dx, ft + dy), (fr + dx, fb + dy), (fr, fb)], 1.5, PALE)
    pen.line(fl, fb, fl + dx, fb + dy, 0.6, MID, [3, 3])
    pen.line(fl + dx, fb + dy, fr + dx, fb + dy, 0.6, MID, [3, 3])
    pen.line(fl + dx, fb + dy, fl + dx, ft + dy, 0.6, MID, [3, 3])

    ox, oy = fr + dx * 0.5, fb + dy * 0.5
    tx, ty = ox + 30, fb - 24
    pen.line(ox, oy, tx, ty + 10, 0.8, INK)
    pen.arrow_head(ox, oy, tx, ty + 10)
    pen.txt(tx, ty, "ปากถุงเปิดด้านล่าง", 8.5, True, "center", INK)
    pen.txt(tx, ty - 12, "OPEN BOTTOM", 8.5, True, "center", INK)

    if spec.holes_count:
        span = fr - fl
        for i in range(spec.holes_count):
            pen.ellipse(fl + dx * 0.5 + span * (0.20 + 0.28 * i), ft + dy * 0.55, 7, 3.4)
        hx = fl + dx * 0.5 + span * 0.48
        pen.line(hx, ft + dy * 0.62, hx + span * 0.10, ft + dy + 24, 0.7, INK)
        pen.txt(hx + span * 0.10, ft + dy + 28,
                f"{spec.holes_count} x Ø{spec.holes_dia} mm HOLES", 9.5, True, "center", INK)

    if spec.label_w and spec.label_h:
        lw, lh = 48, 32
        lx, ly = fr - lw - 34, fb + 28
        pen.rect(lx, ly, lw, lh, 0.9)
        pen.txt(lx + lw / 2, ly - 11,
                f"LABEL {spec.label_w:g} x {spec.label_h:g} mm", 7.5, True, "center")

    return [
        ("width", (fl, fb - 28), (fr, fb - 28), (fl, fb), (fr, fb)),
        ("height", (fr + dx + 28, fb + dy), (fr + dx + 28, ft + dy), (fr + dx, fb + dy), (fr + dx, ft + dy)),
        ("length", (fl - 24, ft + 24), (fl + dx - 24, ft + dy + 24), (fl, ft), (fl + dx, ft + dy)),
    ]


# --------------------------------------------------------------------------
# ข้อความบนแบบสร้างจากข้อมูล ไม่พิมพ์มือ -> ตารางกับลูกศรใช้ตัวเลขชุดเดียวกัน
# --------------------------------------------------------------------------
def _word(k: int) -> str:
    return {1: "One", 2: "Two", 3: "Three", 4: "Four"}.get(k, str(k))


def _thick_dec(value: float) -> int:
    return 2 if value >= 0.1 else 3


def build_notes(spec: DrawingSpec) -> list[str]:
    notes: list[str] = []
    if spec.holes_count:
        notes.append(
            f"{_word(spec.holes_count)} holes, each measuring Ø{spec.holes_dia} mm in diameter, "
            f"shall be provided at any suitable location on the top panel of the {spec.title.lower()}."
        )
    if spec.label_w and spec.label_h:
        notes.append(
            f"One {spec.label_w:g} x {spec.label_h:g} mm label shall be affixed at any suitable "
            f"location near the opening of the {spec.title.lower()}."
        )
    if spec.length_datum:
        target = "seal line" if spec.length_datum == "opening_to_seal" else "bag bottom"
        notes.append(f"Length shall be measured from the bag opening to the {target}.")
    if spec.thickness_mm:
        dec = _thick_dec(spec.thickness_mm)
        notes.append(
            f"Thickness: {spec.thickness_mm:.{dec}f} mm per side; "
            f"tolerance: +/-{spec.tol_thickness:g} mm."
        )
    if spec.dimension_units:
        table_units = list(dict.fromkeys("mm" if unit == "inch" else unit
                                        for unit in spec.dimension_units.values()))
        tolerances = []
        for unit in table_units:
            factor = {"mm": 1, "cm": 10, "m": 1000}[unit]
            tolerances.append(f"{spec.tol_dim_hi / factor:+.2f} / {spec.tol_dim_lo / factor:+.2f} {unit}")
        notes.append("Dimension tolerance: " + "; ".join(tolerances) + ".")
        if "inch" in spec.dimension_units.values():
            notes.append("Inch dimensions: inspection table in mm (1 inch = 25.40 mm).")
    else:
        notes.append(f"Overall dimension tolerance: {spec.tol_dim_hi:+g} / {spec.tol_dim_lo:+g} mm.")
    notes.append(f"Material: {spec.material}. Unit: {spec.display_unit}. Scale: NTS.")
    return notes + [n for n in spec.extra_notes if n.strip()]


def build_dim_rows(spec: DrawingSpec) -> list[DimRow]:
    unit = "inch" if spec.display_unit == "inch" else "mm"
    to_unit = (lambda v: v / MM_PER_INCH) if unit == "inch" else (lambda v: v)
    dec = 2 if unit == "inch" else 0
    lo, hi = spec.tol_dim_lo, spec.tol_dim_hi
    rows: list[DimRow] = []
    if spec.width_mm:
        rows.append(DimRow("WIDTH", to_unit(spec.width_mm), to_unit(spec.width_mm + lo),
                           to_unit(spec.width_mm + hi), unit, dec))
    if spec.length_mm:
        rows.append(DimRow(spec.length_label(), to_unit(spec.length_mm),
                           to_unit(spec.length_mm + lo), to_unit(spec.length_mm + hi), unit, dec))
    if spec.height_mm:
        rows.append(DimRow("HEIGHT", to_unit(spec.height_mm), to_unit(spec.height_mm + lo),
                           to_unit(spec.height_mm + hi), unit, dec))
    if spec.gusset_mm:
        rows.append(DimRow("GUSSET", to_unit(spec.gusset_mm), None, None, unit, dec))
    if spec.thickness_mm:
        t = spec.thickness_mm
        # ความหนาเป็นมิลลิเมตรเสมอ แม้ขนาดจะแสดงเป็นนิ้ว
        # เพราะหน้างานวัดด้วยไมโครมิเตอร์หน่วยมิลลิเมตร
        rows.append(DimRow("THICKNESS", t, t - spec.tol_thickness, t + spec.tol_thickness,
                           "mm/side", _thick_dec(t), True))
    kinds = {"WIDTH": "width", spec.length_label(): "length", "HEIGHT": "height", "GUSSET": "gusset"}
    for row in rows:
        target = spec.dimension_units.get(kinds.get(row.item, ""))
        if target:
            target = "mm" if target == "inch" else target
            old_factor = MM_PER_INCH if unit == "inch" else 1
            factor = {"mm": 1, "cm": 10, "m": 1000}[target]
            row.nominal = row.nominal * old_factor / factor
            if row.lo is not None:
                row.lo = row.lo * old_factor / factor
            if row.hi is not None:
                row.hi = row.hi * old_factor / factor
            row.unit = target
            row.decimals = 2
    return rows


def dim_label(spec: DrawingSpec, kind: str) -> str:
    value = {"width": spec.width_mm, "length": spec.length_mm, "height": spec.height_mm}[kind]
    if not value:
        return ""
    name = spec.length_label() if kind == "length" else kind.upper()
    if kind in spec.dimension_units:
        unit = spec.dimension_units[kind]
        if unit == "inch":
            return f"{name} {value / MM_PER_INCH:.2f} inch ({value:.2f} mm)"
        factor = {"mm": 1, "cm": 10, "m": 1000}[unit]
        return f"{name} {value / factor:.2f} {unit}"
    if spec.display_unit == "inch":
        return f"{name} {value / MM_PER_INCH:g} in ({value:.1f} mm)"
    return f"{name} {value:,.0f} mm"


# --------------------------------------------------------------------------
# ความกว้างข้อความโดยประมาณ ใช้ตัดบรรทัดไม่ให้ล้นกรอบ
# --------------------------------------------------------------------------
_WIDE = set("MWmw@%")
_NARROW = set("iljItfr.,;:'\"|! ")


def text_width(text: str, size: float, bold: bool = False) -> float:
    total = 0.0
    for ch in text:
        if ch in _WIDE:
            total += 0.90
        elif ch in _NARROW:
            total += 0.32
        elif ch.isupper() or ch.isdigit():
            total += 0.62
        else:
            total += 0.52
    return total * size * (1.05 if bold else 1.0)


def wrap_text(text: str, max_pt: float, size: float, bold: bool = True) -> list[str]:
    out, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and text_width(candidate, size, bold) > max_pt:
            out.append(line)
            line = word
        else:
            line = candidate
    if line:
        out.append(line)
    return out


# --------------------------------------------------------------------------
# หน้ากระดาษ
# --------------------------------------------------------------------------
def _bounded_text(pen, x, top, bottom, width, value, size=9.0):
    """Wrap complete field values inside their cell; never silently truncate."""
    value = str(value)
    while size >= 6.5:
        lines, line = [], ""
        for word in value.split():
            candidate = (line + " " + word).strip()
            if text_width(candidate, size, False) <= width:
                line = candidate
                continue
            if line:
                lines.append(line)
                line = ""
            for char in word:
                if line and text_width(line + char, size, False) > width:
                    lines.append(line)
                    line = ""
                line += char
        if line:
            lines.append(line)
        lead = size + 2
        if not lines or top - (len(lines) - 1) * lead >= bottom:
            for i, chunk in enumerate(lines):
                pen.txt(x, top - i * lead, chunk, size, color=DARK)
            return
        size = round(size - 0.25, 2)
    raise DrawingError("ข้อความในช่องข้อมูลยาวเกินพื้นที่ กรุณาย่อข้อความ / Drawing field text does not fit")


def _field(pen: Pen, x1, x2, y1, y2, label, value):
    pen.rect(x1, y1, x2 - x1, y2 - y1, 0.7)
    pen.txt(x1 + 5, y2 - 12, label, 8.2, True)
    _bounded_text(pen, x1 + 5, y2 - 24, y1 + 4, x2 - x1 - 10, value)


def bag_perspective(pen, area, spec):
    """Illustrative open bag only: never infer a production depth."""
    x0, y0, x1, y1 = area
    w, h = x1 - x0, y1 - y0
    l, r = x0 + w * .18, x0 + w * .73
    b, t = y0 + h * .23, y0 + h * .70
    dx, dy = w * .09, h * .09
    pen.poly([(l,b),(r,b),(r,t),(l,t)], fill=PALE)
    pen.poly([(r,b),(r+dx,b+dy),(r+dx,t+dy),(r,t)], fill=PALE)
    pen.poly([(l,t),(l+dx,t+dy),(r+dx,t+dy),(r,t)], fill="white")
    pen.line(l,b+5,r,b+5,1,INK)
    if spec.shape == "gusset_bag":
        pen.line(l+w*.07,b+8,l+w*.07,t,0.7,MID,[3,3])
        pen.line(r-w*.07,b+8,r-w*.07,t,0.7,MID,[3,3])
    pen.txt((l+r)/2,t+dy+12,"BAG OPENING",7,True,"center",INK)
    pen.txt((x0+x1)/2,y0+h*.12,"3D / ILLUSTRATION ONLY",7,True,"center",INK)
    pen.txt((x0+x1)/2,y0+h*.06,"DIMENSIONS: SEE SPECIFICATION",6,False,"center",INK)


def render_svg(spec: DrawingSpec) -> str:
    if spec.shape not in SHAPES:
        raise DrawingError(f"ยังไม่มีแบบวาดสำหรับประเภทสินค้านี้: {spec.shape}")
    if not (spec.width_mm and spec.length_mm):
        raise DrawingError("ต้องมีความกว้างและความยาวก่อนจึงจะสร้างแบบได้")
    if spec.shape in ("flat_bag", "gusset_bag") and not spec.length_datum:
        raise DrawingError("ถุงต้องระบุจุดอ้างอิงความยาว (ปากถึงแนวซีล หรือ ปากถึงก้นถุง)")

    pen = Pen()
    x0, x1 = MARGIN, PAGE_W - MARGIN
    y0, y1 = MARGIN, PAGE_H - MARGIN

    pen.fill_rect(0, 0, PAGE_W, PAGE_H, "#ffffff")
    pen.rect(x0, y0, x1 - x0, y1 - y0, 1.35)
    pen.line(x0, HEADER_Y, x1, HEADER_Y, 0.95)
    pen.line(x0, TITLEBLK_Y, x1, TITLEBLK_Y, 0.95)
    pen.line(SPLIT_X, TITLEBLK_Y, SPLIT_X, HEADER_Y, 0.95)

    # หัวกระดาษ
    pen.line(HEADER_RX, HEADER_Y, HEADER_RX, y1, 0.75)
    pen.txt(x0 + 16, 548, COMPANY_NAME, 18, True, color=INK)
    pen.txt(x0 + 16, 523, "DRAWING FOR APPROVAL", 11.5, True, color=INK)
    hrow = (y1 - HEADER_Y) / 3
    for i in (1, 2):
        pen.line(HEADER_RX, HEADER_Y + i * hrow, x1, HEADER_Y + i * hrow, 0.7)
    for label, value, yy in (("DOCUMENT NO.", spec.doc_no, HEADER_Y + 2 * hrow),
                             ("REVISION", spec.revision, HEADER_Y + hrow),
                             ("DATE", spec.date, HEADER_Y)):
        pen.txt(HEADER_RX + 8, yy + 8, label, 6.8, True)
        pen.txt(x1 - 8, yy + 7, value, 8, True, "right", INK)

    # แถบข้อมูลแบบ
    info_bottom = INFO_Y - 12
    pen.line(x0, info_bottom, SPLIT_X, info_bottom, 0.7)
    pen.txt(x0 + 9, 486, "DRAWING INFORMATION", 7.2, True, color=INK)
    info = [("CUSTOMER", spec.customer), ("TITLE", spec.title),
            ("MATERIAL", spec.material), ("COLOR", spec.color), ("PRINTING", spec.printing)]
    starts = [x0 + 9, x0 + 219, x0 + 331, x0 + 431, x0 + 501]
    ends = starts[1:] + [SPLIT_X]
    for (label, value), sx, ex in zip(info, starts, ends):
        pen.txt(sx, 470, label, 7.4, True)
        _bounded_text(pen, sx, 458, info_bottom + 4, ex - sx - 8, value, 7.6)

    # พื้นที่วาด
    area = (x0, TITLEBLK_Y, SPLIT_X, info_bottom)
    view = spec.drawing_view if spec.shape in ("flat_bag", "gusset_bag") else "2d"
    if view not in ("2d", "3d", "both"):
        raise ValueError("Unsupported drawing view")
    if view == "3d":
        bag_perspective(pen, area, spec)
        callouts = []
    elif view == "both":
        split = x0 + (SPLIT_X - x0) * .62
        callouts = SHAPES[spec.shape](pen, (x0, TITLEBLK_Y, split, info_bottom), spec)
        bag_perspective(pen, (split, TITLEBLK_Y, SPLIT_X, info_bottom), spec)
    else:
        callouts = SHAPES[spec.shape](pen, area, spec)
    for kind, a, b, e1, e2 in callouts:
        if e1 and e2:
            pen.ext(e1[0], e1[1], a[0], a[1])
            pen.ext(e2[0], e2[1], b[0], b[1])
        pen.dim(a[0], a[1], b[0], b[1], dim_label(spec, kind))
    pen.txt((x0 + SPLIT_X) / 2, TITLEBLK_Y + 9, "NOT TO SCALE", 7, True, "center", MID)

    # ตารางสเปก
    rows = build_dim_rows(spec)
    notes = build_notes(spec)
    pen.txt(SPLIT_X + 9, 484, "DIMENSION SPECIFICATION", 8, True, color=INK)
    # หมายเหตุมากกว่าปกติให้ลดความสูงแถวตาราง เพื่อยกพื้นที่ให้หมายเหตุ
    # ก่อนจะไปลดขนาดตัวอักษร เพราะแถวเตี้ยลงยังอ่านง่ายกว่าตัวหนังสือเล็กลง
    rh = 26.0 if len(notes) <= 5 else 22.0
    th = rh * (len(rows) + 1)
    ty = INFO_Y - 8 - th
    tw = x1 - SPLIT_X
    cols = [SPLIT_X + tw * f for f in (0.0, 0.40, 0.555, 0.71, 0.865, 1.0)]
    ctr = [(cols[i] + cols[i + 1]) / 2 for i in range(5)]
    head_y = ty + th - rh
    pen.fill_rect(SPLIT_X, head_y, tw, rh, LIGHT)
    for i in range(len(rows)):
        yy = head_y - (i + 1) * rh
        pen.fill_rect(cols[2], yy, cols[3] - cols[2], rh, MINF)
        pen.fill_rect(cols[3], yy, cols[4] - cols[3], rh, MAXF)
    pen.rect(SPLIT_X, ty, tw, th, 0.7)
    for xx in cols[1:-1]:
        pen.line(xx, ty, xx, ty + th, 0.55, MID)
    for i in range(len(rows) + 1):
        pen.line(SPLIT_X, ty + i * rh, x1, ty + i * rh, 0.55, MID)
    for xx, value in zip(ctr, ["DIMENSION", "NOM.", "MIN.", "MAX.", "UNIT"]):
        pen.txt(xx, head_y + 9, value, 6.8, True, "center")
    for i, row in enumerate(rows):
        yy = head_y - (i + 1) * rh + 9
        fmt = f"%.{row.decimals}f"
        values = [row.item, fmt % row.nominal,
                  fmt % row.lo if row.lo is not None else "-",
                  fmt % row.hi if row.hi is not None else "-", row.unit]
        for k, (xx, value) in enumerate(zip(ctr, values)):
            pen.txt(xx, yy, value, 6.8 if k == 4 else 7.8, row.bold, "center", INK)

    # หมายเหตุ — ย่อขนาดอัตโนมัติจนกว่าจะไม่ชนตารางลงนาม
    top = ty - 20
    available = top - 17 - (TITLEBLK_Y + 8)
    inner = (x1 - 9) - (SPLIT_X + 26)
    # ย่อได้ถึง 7 pt เท่านั้น เล็กกว่านี้พิมพ์ออกมาแล้วอ่านไม่ชัด
    # ถ้ายังไม่พอให้แจ้งเตือน ห้ามตัดหมายเหตุทิ้งเงียบ ๆ
    # เพราะหมายเหตุคือข้อตกลงกับลูกค้า หายไปหนึ่งข้อคือผลิตผิดทั้งล็อต
    size, lead = 9.0, 12.0
    while True:
        used = sum(len(wrap_text(n, inner, size)) for n in notes) * lead + len(notes) * 3
        if used <= available:
            break
        if size <= 7.0:
            raise DrawingError(
                f"หมายเหตุยาวเกินหน้ากระดาษ ({len(notes)} ข้อ) "
                "ให้ย่อข้อความหรือแยกเป็นเอกสารแนบ / "
                "Notes do not fit on one page; shorten them or use an attachment"
            )
        size -= 0.4
        lead -= 0.5
    pen.txt(SPLIT_X + 9, top, "NOTES", 12.5, True, color=INK)
    ny = top - 17
    for i, note in enumerate(notes, 1):
        pen.txt(SPLIT_X + 10, ny, f"{i}.", size + 0.5, True)
        for chunk in wrap_text(note, inner, size):
            pen.txt(SPLIT_X + 26, ny, chunk, size, True)
            ny -= lead
        ny -= 3

    # ตารางลงนามด้านล่าง 8 คอลัมน์ 4 แถว
    grid = [x0 + (x1 - x0) * i / 8 for i in range(9)]
    ys = [y0, 50, 78, 108, TITLEBLK_Y]
    for a, b, label, value in [(0, 2, "DRAWING TITLE", spec.title),
                               (2, 5, "CUSTOMER", spec.customer),
                               (5, 7, "PART NO. / DRAWING NO.", spec.part_no),
                               (7, 8, "REVISION", spec.revision)]:
        _field(pen, grid[a], grid[b], ys[3], ys[4], label, value)
    for a, b, label, value in [(0, 3, "MATERIAL", spec.material),
                               (3, 4, "COLOR", spec.color),
                               (4, 8, "PRINTING / ARTWORK", spec.printing)]:
        _field(pen, grid[a], grid[b], ys[2], ys[3], label, value)
    for a, b, label, value in [(0, 2, "SCALE", "NTS"),
                               (2, 4, "PRIMARY UNIT", spec.display_unit),
                               (4, 8, "DOCUMENT NO.", spec.doc_no)]:
        _field(pen, grid[a], grid[b], ys[1], ys[2], label, value)
    for a, b, label, value in [(0, 2, "DRAWN BY", ""), (2, 4, "CHECKED BY", ""),
                               (4, 6, "APPROVED BY", ""), (6, 8, "DATE", spec.date)]:
        _field(pen, grid[a], grid[b], ys[0], ys[1], label, value)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PAGE_W:.2f} {PAGE_H:.2f}" '
        f'width="100%" preserveAspectRatio="xMidYMid meet">\n{pen.svg()}\n</svg>'
    )


def render_html(spec: DrawingSpec) -> str:
    """หน้าเว็บสำหรับดูตัวอย่างและสั่งพิมพ์ A4 แนวนอน"""
    svg = render_svg(spec)
    title = _esc(f"{spec.doc_no} — {spec.title}")
    stamp = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%d/%m/%Y %H:%M:%S")
    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  @page {{ size: A4 landscape; margin: 6mm; }}
  body {{ margin: 0; background: #eef2f5; font-family: {FONT}; }}
  .bar {{ padding: 12px 18px; background: {INK}; color: #fff; font-weight: 700; }}
  .bar button {{ float: right; font: inherit; padding: 6px 16px; margin-left: 8px; cursor: pointer; }}
  .sheet {{ background: #fff; margin: 16px auto; max-width: 1180px;
            box-shadow: 0 2px 12px rgba(0,0,0,.18); }}
  .print-footer {{ display: flex; justify-content: space-between; font-size: 8px;
                   border-top: 1px solid #999; padding: 2mm 6mm; }}
  @media print {{ .bar {{ display: none; }}
                  .sheet {{ margin: 0; max-width: none; box-shadow: none; }}
                  .sheet > svg {{ display: block; width: 100%; max-height: 190mm; }}
                  body {{ background: #fff; }} }}
</style>
</head>
<body>
<div class="bar">{title}
  <button onclick="history.back(); setTimeout(function(){{ if(history.length <= 1) window.close(); }}, 100)">ย้อนกลับ / Back</button>
  <button onclick="window.print()">พิมพ์ / Print</button>
</div>
<div class="sheet">{svg}<div class="print-footer"><span>PANTONG THAI PACK CO., LTD. • {_esc(spec.doc_no)}</span><span>Printed: {stamp} • Page 1 of 1</span></div></div>
</body>
</html>"""
