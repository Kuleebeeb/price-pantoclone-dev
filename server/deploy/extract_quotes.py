# -*- coding: utf-8 -*-
"""Extract structured pricing specs from the factory's FR-MA-005 quotation books.

READS Z:\\Quotation-... AND NEVER WRITES THERE. People work in those files live
(~$ lock files exist) - this script opens read-only copies and writes results to
the --out folder only.

WHAT IT PRODUCES per customer-letter folder:
    manifest.csv   every file seen and what became of it (the "nothing missed" ledger)
    rows.jsonl     one candidate row per quoted item, in import_quotations shape
    review.csv     items the machine refuses to guess - for a human, with reasons
    report.md      the reconciliation summary

WHY VERIFICATION USES THE CALCULATOR. A parsed "8'' x 12'' x 80 MIC" is only a
guess until something checks it. The one thing history gives us is the price the
customer actually paid. So: compute grams from the parsed geometry with the
byte-identical desktop calculator, derive the implied THB/kg from a per-piece
price, and accept the parse only when that lands in the plausible resin band.
A wrong unit guess (cm read as inch) lands far outside the band - the same 11%
class of error the whole system exists to prevent, caught by arithmetic instead
of by a human eye. Items that cannot be cross-checked are exported as "parsed",
never upgraded to "verified".

STATUS LADDER (each row carries exactly one):
    verified   geometry computed AND the paid per-piece price confirms it
    parsed     spec extracted; nothing available to cross-check it against
               (kg-priced rows are complete price records without geometry)
    partial    some spec extracted (e.g. dims but no thickness on a piece price)
    review     the machine refuses to guess: ambiguous units, cover/foam branch,
               or price outside every honest reading
    trading    bought-for-resale wording - the calculator's "does not apply" branch
    name_only  no dimensions found in the text at all

NO REFS ARE ISSUED AND NOTHING IS IMPORTED HERE. The printed REF NO on the sheet
is copied as-is; matching against the rows already in the server's database is a
separate, later step - deciding that mapping inside the extractor would hide it
from review.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import calculator  # noqa: E402

DENSITY = {"LLDPE": 0.92, "LDPE": 0.92, "PE": 0.92, "HDPE": 0.95, "PP": 0.905}
DENSITY_DEFAULT = 0.92

# Resin detection - order matters (LLDPE before LDPE before PE). "PS" is NOT
# matched: the books are full of part numbers like PS304 that are not polystyrene.
RESIN_RULES = [
    ("LLDPE", re.compile(r"\bLLDPE\b", re.I)),
    ("LDPE", re.compile(r"\bLDPE\b|แอลดีพีอี|ถุงเย็น", re.I)),
    ("HDPE", re.compile(r"\bHDPE\b|\bHD\b|เอชดี|ไฮเดน", re.I)),
    ("PP", re.compile(r"\bPP\b|พีพี|ถุงร้อน", re.I)),
    ("EPE", re.compile(r"\bEPE\b|FOAM|โฟม", re.I)),
    ("PVC", re.compile(r"\bPVC\b", re.I)),
    ("PE", re.compile(r"\bPE\b|พีอี|POLYETHYLENE|POLY\s?BAG", re.I)),
]
# (?![A-Za-z]) instead of \b: "PIR35%" has no word boundary before the digit
RECYCLED_RULES = [
    ("PIR", re.compile(r"\bPIR(?![A-Za-z])", re.I)),
    ("PCR", re.compile(r"\bPCR(?![A-Za-z])", re.I)),
]
# Selling-price band, THB per kg. Resin cost ran 66-78 THB/kg over the period;
# quotes sit above cost and below roughly triple it (print/special jobs).
PLAUSIBLE_THB_PER_KG = (35.0, 300.0)

DIM_UNIT_TO_THAI = {
    "''": "นิ้ว", '"': "นิ้ว", "IN": "นิ้ว", "INCH": "นิ้ว", "นิ้ว": "นิ้ว",
    "CM": "ซม.", "ซม": "ซม.",
    "MM": "มม.", "มม": "มม.",
    "M": "เมตร", "เมตร": "เมตร",
}

# NOTE the first alternative REQUIRES a comma group: without the "+" it used
# to match the first 3 digits of "1140" and silently shrink a sheet tenfold.
NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
UNIT = r"(?:''|\"|นิ้ว|ซม\.?|มม\.?|เมตร|CM\.?|MM\.?|MC\.?|M\.?|IN(?:CH)?\.?|MIC(?:RON)?\.?|ไมครอน)?"
SEP = r"\s*[xX×]\s*"

# The books mix "MM." and "mm." freely - every dimension regex is case-blind.
TRIPLE = re.compile(rf"({NUM})\s*({UNIT})\s*{SEP}({NUM})\s*({UNIT})\s*{SEP}\s*T?\s*\.?\s*:?\s*({NUM})\s*({UNIT})", re.I)
LABELED = re.compile(
    rf"W\s*:?\s*({NUM})\s*({UNIT})\s*{SEP}\s*L\s*:?\s*({NUM})\s*({UNIT})"
    rf"(?:.*?{SEP}\s*T?\s*:?\s*({NUM})\s*({UNIT}))?",
    re.I,
)
# same labels written length-first: "L: 550 x W: 520" (colon required, so the
# no-colon part-list shorthand below keeps its own territory)
LABELED_LW = re.compile(
    rf"L\s*:\s*({NUM})\s*({UNIT})\s*{SEP}\s*W\s*:\s*({NUM})\s*({UNIT})"
    rf"(?:.*?{SEP}\s*T?\s*:?\s*({NUM})\s*({UNIT}))?",
    re.I,
)
# part-list shorthand: L430xW290xT0.04 (always mm scale)
COMPACT = re.compile(rf"L\s*({NUM})\s*[xX×]\s*W\s*({NUM})(?:\s*[xX×]\s*T\s*:?\s*({NUM}))?", re.I)
DOUBLE = re.compile(rf"({NUM})\s*({UNIT})\s*{SEP}({NUM})\s*({UNIT})", re.I)
# gusset written as 65 CM.+(23 CM.) x 95 CM. - the plus-group must sit BEFORE
# the first x, otherwise "W x L + flap" bags were wrongly flipped to gusset
GUSSET_PLUS = re.compile(rf"({NUM})\s*({UNIT})\s*\+\s*\(?\s*({NUM})\s*({UNIT})\s*\)?(?=\s*[xX×])", re.I)
# thickness written outside the x-chain
PAREN_THICK = re.compile(rf"\(\s*({NUM})\s*(MC\.?|MIC\.?|MICRON|ไมครอน|MM\.?|มม\.?|มิล)\s*(?:/[^)]*)?\)", re.I)
THICK_LABEL = re.compile(rf"(?:ความหนา|หนา)\s*:?\s*({NUM})\s*({UNIT})", re.I)
X_THICK = re.compile(rf"[xX×]\s*T?\s*\.?\s*:?\s*({NUM})\s*({UNIT})", re.I)
THICK_RANGE = re.compile(rf"({NUM})\s*[-–]\s*({NUM})\s*(?:MM\.?|มม\.?|MIC\.?|ไมครอน)", re.I)
# per-side vs per-pair notation. Thai "/ด้าน" = per side, "/2 ด้าน" and "/คู่"
# = the folded pair - confusing them silently halves or doubles the weight.
PAIR_HINT = re.compile(r"/\s*2\s*ด้าน|/\s*คู่|ต่อคู่", re.I)
SIDE_HINT = re.compile(r"/\s*SIDE\b|/\s*SHEET\b|/\s*S\b|/\s*ด้าน|ต่อด้าน", re.I)


def normalize_numbers(text: str) -> str:
    """Fold the books' fraction spellings into decimals before any regex runs.

    15"3/4 means fifteen-and-three-quarter inch; Thai books also write
    40.1/2 นิ้ว for forty and a half. Left alone, the denominator becomes
    the extracted value.
    """
    def frac_inch(m):
        return f"{int(m.group(1)) + int(m.group(2)) / int(m.group(3))}''"

    text = re.sub(r"(\d+)\s*(?:''|\")\s*(\d)\s*/\s*(\d)", frac_inch, text)
    text = re.sub(r"(\d+)\.\s*1\s*/\s*2", lambda m: m.group(1) + ".5", text)
    return text


PRODUCT_RULES = [
    # the two no-branch laminates come first: "EPE FOAM SHEET" must not fall
    # into the SHEET rule, and "AIR BUBBLE BAG" must not fall into BAG
    (re.compile(r"FOAM|โฟม|EPE"), None, "EPE foam has no calculator branch -> review"),
    (re.compile(r"AIR\s*BUBBLE|บับเบิ"), None, "air-bubble laminate has no calculator branch -> review"),
    (re.compile(r"GUSSET|พับข้าง|ขยายข้าง"), "gusset", ""),
    (re.compile(r"SHEET\s*ROLL|ROLL|ม้วน"), "roll", ""),
    (re.compile(r"SHEET|แผ่น"), "opaque", ""),
    (re.compile(r"COVER|คลุม"), None, "cover: desktop cover = sewn roof/mesh, film covers do not fit -> review"),
    (re.compile(r"ZIP"), "flat", "zipper bag priced as flat-bag geometry"),
    (re.compile(r"TUBE"), "flat", "tube open two sides, flat-bag geometry (two faces)"),
    (re.compile(r"BAG|ถุง|ซอง"), "flat", ""),
]

PIECE_UNITS = {"PC", "PCS", "ใบ", "ชิ้น", "PIECE", "EA"}
KG_UNITS = {"KG", "KGS", "กก", "กิโลกรัม"}
TRADING_HINT = re.compile(r"PALLET|พาเลท|TAPE|เทป|กล่อง|CARTON|STICKER|สติ", re.I)


def n(v: str) -> float:
    return float(v.replace(",", ""))


def dim_unit(raw: str) -> str | None:
    key = (raw or "").strip().upper().rstrip(".")
    return DIM_UNIT_TO_THAI.get(key)


def norm_sale_unit(raw: str) -> str:
    key = (raw or "").strip().upper().rstrip(".").rstrip("S")
    if key in {u.rstrip("S") for u in PIECE_UNITS}:
        return "piece"
    if key in {u.rstrip("S") for u in KG_UNITS}:
        return "kg"
    return ""


def normalize_thickness(value: float, raw_unit: str, reasons: list[str]) -> tuple[float, str] | None:
    """Return (value, thai_unit) in a physically possible reading, else None.

    Books mix 'MM', 'MIC', 'MC' and nothing at all, and sometimes the token
    contradicts the number (0.03 micron does not exist as a film). Magnitude
    decides: film thickness is 0.01-1.5 mm, i.e. 10-1500 micron.
    """
    key = (raw_unit or "").strip().upper().rstrip(".")
    if key in {"MIC", "MICRON", "ไมครอน"}:
        if value >= 5:
            return value, "ไมครอน"
        reasons.append(f"unit says micron but {value} micron is no film - read as mm")
        return value, "มม."
    if key in {"MM", "มม", "MC", "มิล"}:
        if value <= 1.5:
            return value, "มม."
        if value >= 10:
            reasons.append(f"unit says mm but {value} mm is no film - read as micron")
            return value, "ไมครอน"
        return None
    # no unit written: decide by magnitude alone
    if value <= 1.5:
        return value, "มม."
    if value >= 10:
        return value, "ไมครอน"
    return None


@dataclass
class Item:
    description: str
    quantity: str = ""
    unit: str = ""
    price: float | None = None
    previous_price: float | None = None
    product_key: str | None = None
    product_note: str = ""
    product_name: str = ""
    part_code: str = ""
    resin: str = ""
    width: float | None = None
    width_unit: str | None = None
    length: float | None = None
    length_unit: str | None = None
    gusset: float | None = None
    gusset_unit: str | None = None
    thickness: float | None = None
    thickness_unit: str | None = None
    thickness_mode_hint: str = ""
    sold_length_m: float | None = None
    status: str = "name_only"
    reasons: list[str] = field(default_factory=list)
    grams: float | None = None
    implied_thb_per_kg: float | None = None
    thickness_mode: str = ""
    density: float = DENSITY_DEFAULT


@dataclass
class Sheet:
    file: Path
    sheet: str
    ref: str = ""
    ref_text: str = ""  # the whole REF NO cell, e.g. "2564/10 REV.1"
    date_iso: str = ""
    customer: str = ""
    items: list[Item] = field(default_factory=list)
    layout: str = "fr-ma-005"
    error: str = ""


def thai_date_to_iso(text: str) -> str:
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
    if not m:
        return ""
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y > 2400:
        y -= 543
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return ""


def _late_thickness(item: Item, text: str) -> None:
    """Thickness written outside the main x-chain: '(40 MC./SIDE)', 'หนา 0.28',
    a trailing 'x T.0.03 MM.'. Magnitude-guarded so a length can never be
    mistaken for a film thickness."""
    if item.thickness is not None:
        return
    for rx in (PAREN_THICK, THICK_LABEL, X_THICK):
        for m in rx.finditer(text):
            val, raw = n(m.group(1)), (m.group(2) or "").strip().upper().rstrip(".")
            micronish = raw in {"MIC", "MICRON", "ไมครอน", "MC"}
            if val <= 1.5 or (micronish and val >= 5):
                t = normalize_thickness(val, m.group(2) or "", item.reasons)
                if t and (item.length is None or t[0] != item.length):
                    item.thickness, item.thickness_unit = t
                    return


def parse_dimensions(item: Item) -> None:
    text = normalize_numbers(item.description)
    if PAIR_HINT.search(text):
        item.thickness_mode_hint = "pair"
    elif SIDE_HINT.search(text):
        item.thickness_mode_hint = "side"

    matched = False
    m = GUSSET_PLUS.search(text)
    if m:
        item.width, item.width_unit = n(m.group(1)), dim_unit(m.group(2))
        item.gusset, item.gusset_unit = n(m.group(3)), dim_unit(m.group(4)) or item.width_unit
        rest = text[m.end():]  # remaining "x 95 CM. x 0.04 MM./Side"
        m2 = re.search(rf"[xX×]\s*({NUM})\s*({UNIT})\s*[xX×]\s*T?\s*:?\s*({NUM})\s*({UNIT})", rest, re.I)
        if m2:
            item.length, item.length_unit = n(m2.group(1)), dim_unit(m2.group(2))
            t = normalize_thickness(n(m2.group(3)), m2.group(4), item.reasons)
            if t:
                item.thickness, item.thickness_unit = t
        else:
            m2 = re.search(rf"[xX×]\s*({NUM})\s*({UNIT})", rest, re.I)
            if m2:
                item.length, item.length_unit = n(m2.group(1)), dim_unit(m2.group(2))
        matched = True

    if not matched:
        m = COMPACT.search(text)
        if m:
            # part-list shorthand is always millimetres
            item.length, item.length_unit = n(m.group(1)), "มม."
            item.width, item.width_unit = n(m.group(2)), "มม."
            if m.group(3):
                t = normalize_thickness(n(m.group(3)), "MM", item.reasons)
                if t:
                    item.thickness, item.thickness_unit = t
            matched = True

    if not matched:
        for rx, w_first in ((LABELED, True), (LABELED_LW, False)):
            m = rx.search(text)
            if not m:
                continue
            a, au = n(m.group(1)), dim_unit(m.group(2))
            b, bu = n(m.group(3)), dim_unit(m.group(4))
            if w_first:
                item.width, item.width_unit, item.length, item.length_unit = a, au, b, bu
            else:
                item.length, item.length_unit, item.width, item.width_unit = a, au, b, bu
            if m.group(5):
                t = normalize_thickness(n(m.group(5)), m.group(6), item.reasons)
                if t:
                    item.thickness, item.thickness_unit = t
            matched = True
            break

    if not matched:
        m = TRIPLE.search(text)
        if m:
            item.width, item.width_unit = n(m.group(1)), dim_unit(m.group(2))
            item.length, item.length_unit = n(m.group(3)), dim_unit(m.group(4))
            t = normalize_thickness(n(m.group(5)), m.group(6), item.reasons)
            if t:
                item.thickness, item.thickness_unit = t
            matched = True

    if not matched:
        m = DOUBLE.search(text)
        if m:
            a, au = n(m.group(1)), dim_unit(m.group(2))
            b, bu_raw = n(m.group(3)), m.group(4)
            # "HD ROLL 24'' x 0.03" - nothing is 0.03 long; small second number
            # with a big first one is width x thickness, not width x length
            if b <= 1.5 and a >= 5:
                item.width, item.width_unit = a, au
                t = normalize_thickness(b, bu_raw, item.reasons)
                if t:
                    item.thickness, item.thickness_unit = t
            else:
                item.width, item.width_unit = a, au
                item.length, item.length_unit = b, dim_unit(bu_raw)

    _late_thickness(item, text)

    # "500 x 800 MM." writes the unit once for the whole pair - propagate it
    if item.width is not None and item.length is not None:
        if item.width_unit is None and item.length_unit is not None:
            item.width_unit = item.length_unit
        elif item.length_unit is None and item.width_unit is not None:
            item.length_unit = item.width_unit

    m = THICK_RANGE.search(text)
    if m and item.thickness is not None and item.thickness == float(m.group(1).replace(",", "")):
        item.reasons.append(f"thickness range {m.group(1)}-{m.group(2)}: lower bound used")

    if item.gusset is not None and item.product_key in {None, "flat"}:
        # a captured gusset panel on a flat key would compute the weight
        # without the panel - the W+(G) notation decides the product
        item.product_key = "gusset"
        item.product_note = item.product_note or "gusset inferred from W+(G) notation"


def classify_product(item: Item) -> None:
    upper = item.description.upper()
    for rx, key, note in PRODUCT_RULES:
        if rx.search(upper):
            if key is None:
                item.reasons.append(note)
                item.status = "review"
            else:
                item.product_key = key
                item.product_note = note
            return
    if TRADING_HINT.search(upper):
        item.status = "trading"
        item.reasons.append("bought-for-resale wording, no geometry to compute")


def detect_resin(item: Item) -> None:
    """Name the polymer explicitly; density follows from it, never the reverse."""
    for name, rx in RESIN_RULES:
        if rx.search(item.description):
            item.resin = name
            item.density = DENSITY.get(name, DENSITY_DEFAULT)
            break
    for tag, rx in RECYCLED_RULES:
        if rx.search(item.description):
            item.resin = (item.resin + f" ({tag})") if item.resin else tag


NAME_NOISE = re.compile(r"\(?\s*MINIMUM ORDER[^)]*\)?", re.I)
SIZE_LABEL = re.compile(r"\(?\s*SIZE\s*:", re.I)


def extract_part_code(item: Item) -> None:
    """The customer's own product code: 2P738030-1-TB, RI40021-8L, PS304,
    699-01-00-010. Codes are UPPERCASE letter/digit/dash runs - anything with
    a slash, a dot or lowercase is a dimension, a unit or prose, not a code."""
    text = NAME_NOISE.sub(" ", item.description)
    for raw in re.split(r"[\s,]+", text):
        tok = raw.strip("().:;#")
        if not (4 <= len(tok) <= 24) or not re.fullmatch(r"[A-Z0-9-]+", tok):
            continue
        if re.search(r"\dX\d", tok):  # 100X100 is a size, not a code
            continue
        if re.fullmatch(r"\d+[A-Z]{1,3}", tok):  # 105CM, 1100W, 30KG: a number wearing a unit
            continue
        letters = sum(c.isalpha() for c in tok)
        digits = sum(c.isdigit() for c in tok)
        if tok.count("-") >= 2 and letters == 0 and digits >= 6:
            item.part_code = tok  # digit-block code like 699-01-00-010
            break
        if (letters >= 2 and digits >= 2) or (letters == 1 and digits >= 4):
            item.part_code = tok
            break
    if item.part_code and item.part_code in item.product_name:
        rest = re.sub(r"\s{2,}", " ", item.product_name.replace(item.part_code, "")).strip(" -:,./")
        if rest:
            item.product_name = rest


def extract_product_name(item: Item) -> None:
    """The human name of the thing: the description up to where numbers begin."""
    text = NAME_NOISE.sub(" ", item.description)
    cut = len(text)
    for rx in (LABELED, COMPACT, GUSSET_PLUS, TRIPLE, DOUBLE):
        m = rx.search(text)
        if m:
            cut = min(cut, m.start())
    m = SIZE_LABEL.search(text)
    if m:
        cut = min(cut, m.start())
    m = re.search(r"(?:ขนาด|ยาว)\s*:?\s*\d", text)
    if m:
        cut = min(cut, m.start())
    name = re.sub(r"\s{2,}", " ", text[:cut]).strip(" -:,.(/")
    name = re.sub(r"\s+[xX×]$", "", name)  # dangling separator, not "BOX"
    name = re.sub(r"\s+(SIZE|ขนาด|ยาว)$", "", name, flags=re.I)  # label of the numbers, not the name
    name = re.sub(r"\([^)]{0,12}$", "", name).rstrip(" -:,./")  # unbalanced "(PE" left by "(PE.180 x 250 MM.)"
    name = re.sub(r"\s+(PCS?\.?|ชิ้น|ใบ)$", "", name, flags=re.I)  # sale unit is not part of the name
    item.product_name = name.strip()


def grams_for(item: Item, width_unit: str, thickness_mode: str) -> float | None:
    """Run the desktop calculator for one candidate unit reading. None = invalid."""
    try:
        w_cm = calculator.to_cm(item.width, width_unit)
        gusset_cm = calculator.to_cm(item.gusset, item.gusset_unit or width_unit) if item.gusset else 0.0
        if item.product_key == "roll":
            if item.sold_length_m:
                sold_m = item.sold_length_m
            elif item.length and (item.length_unit or width_unit) == "เมตร":
                sold_m = item.length
            elif item.length:
                sold_m = calculator.to_cm(item.length, item.length_unit or width_unit) / 100.0
            else:
                return None
            l_cm = 0.0
        else:
            sold_m = 0.0
            l_cm = calculator.to_cm(item.length, item.length_unit or width_unit)
        t_mm = calculator.thickness_to_mm(item.thickness, item.thickness_unit)
        result = calculator.calculate(
            product_key=item.product_key,
            width_cm=w_cm, length_cm=l_cm, height_cm=0.0, gusset_cm=gusset_cm,
            sold_length_m=sold_m, bottom_allowance_cm=0.0,
            thickness_input_mm=t_mm, thickness_mode=thickness_mode,
            density_g_cm3=item.density, roof_gsm=0.0, mesh_gsm=0.0,
            material_price_per_kg=0.0, markup_percent=0.0, deduction_percent=0.0,
            pack_quantity=0.0, order_quantity=0.0, control_min_g=0.0, control_max_g=0.0,
            weight_formula=calculator.DEFAULT_WEIGHT_FORMULAS[item.product_key],
            price_formula=calculator.DEFAULT_PRICE_FORMULA,
        )
        return result.grams_per_item
    except Exception:
        return None


def verify_with_price(item: Item) -> None:
    """The oracle. Try every honest reading; keep the one the paid price confirms."""
    if item.product_key is None or item.width is None:
        return
    sale = norm_sale_unit(item.unit)
    has_geometry = item.thickness is not None and (
        item.length is not None or item.product_key == "roll"
    )

    if sale == "kg" or item.price is None:
        # a kg price is the complete price record on its own; geometry is a
        # bonus for planning, computed only from an explicit unit, never guessed
        if has_geometry and item.width_unit:
            mode = item.thickness_mode_hint or "pair"
            g = grams_for(item, item.width_unit, mode)
            if g and g > 0:
                item.grams = round(g, 4)
                item.thickness_mode = mode
        item.status = "parsed"
        basis = "kg-priced" if sale == "kg" else "no price on the row"
        if item.grams is None:
            item.reasons.append(f"{basis}: price record stands alone, geometry not computable")
        else:
            item.reasons.append(f"{basis}: geometry computed, nothing to cross-check it against")
        return

    if not has_geometry:
        missing = []
        if item.thickness is None:
            missing.append("thickness")
        if item.length is None and item.product_key != "roll":
            missing.append("length")
        item.status = "partial"
        item.reasons.append(f"piece-priced but {'/'.join(missing)} missing - weight not computable")
        return

    unit_candidates = [item.width_unit] if item.width_unit else ["ซม.", "นิ้ว", "มม."]
    mode_candidates = [item.thickness_mode_hint] if item.thickness_mode_hint else ["pair", "side"]
    fits: list[tuple[str, str, float, float]] = []
    for wu in unit_candidates:
        for mode in mode_candidates:
            g = grams_for(item, wu, mode)
            if not g or g <= 0:
                continue
            thb_kg = item.price * 1000.0 / g
            if PLAUSIBLE_THB_PER_KG[0] <= thb_kg <= PLAUSIBLE_THB_PER_KG[1]:
                fits.append((wu, mode, g, thb_kg))

    if not fits:
        if item.width_unit:
            # units are printed on the paper - the geometry stands; only the
            # price refuses to reconcile (printing/special jobs cost above film)
            mode = item.thickness_mode_hint or "pair"
            g = grams_for(item, item.width_unit, mode)
            if g and g > 0:
                item.grams = round(g, 4)
                item.thickness_mode = mode
                item.status = "parsed"
                item.reasons.append(
                    "price outside the plain-film band under the stated units - "
                    "geometry kept, price not cross-checked (printed/special job?)"
                )
                return
        item.status = "review"
        item.reasons.append("no unit reading puts the paid price inside the resin band")
        return
    if len({f[0] for f in fits}) > 1:
        item.status = "review"
        item.reasons.append(
            "ambiguous units, several readings fit the price: " + ", ".join(sorted({f[0] for f in fits}))
        )
        return
    wu, mode, g, thb_kg = fits[0]
    for f in fits:
        # both modes fit: prefer pair (P9 - thickness measured on the folded bag)
        if f[1] == "pair":
            wu, mode, g, thb_kg = f
            break
    item.width_unit = item.width_unit or wu
    item.length_unit = item.length_unit or (wu if item.length is not None else None)
    item.thickness_mode = mode
    item.grams = round(g, 4)
    item.implied_thb_per_kg = round(thb_kg, 2)
    item.status = "verified"


def read_sheet(ws, file: Path, name: str) -> Sheet:
    sh = Sheet(file=file, sheet=name)
    grid: list[list] = []
    # The whole sheet, not the first 45 rows: Honda's price lists run to 120
    # items and row 165. The 45-row cap silently kept 29 of them.
    last = min(ws.max_row or 400, 400)
    for row in ws.iter_rows(min_row=1, max_row=last, max_col=12, values_only=True):
        grid.append(list(row))

    def txt(cell) -> str:
        return str(cell).strip() if cell is not None else ""

    header_row = -1
    cols: dict[str, int] = {}
    for i, row in enumerate(grid):
        joined = " ".join(txt(c).upper() for c in row)
        if "REF NO" in joined:
            for c in row:
                m = re.search(r"\b(\d{4}[/-]\d+(?:[/-]\d+)?)\b", txt(c))
                if m and not sh.ref:
                    sh.ref = m.group(1)
                    sh.ref_text = txt(c)
        if "DATE" in joined and not sh.date_iso:
            for c in row:
                # Excel stores many of these as real dates, not text: a
                # datetime cell is the answer itself, no regex needed
                if hasattr(c, "year") and hasattr(c, "month"):
                    sh.date_iso = date(c.year - 543 if c.year > 2400 else c.year, c.month, c.day).isoformat()
                    break
                iso = thai_date_to_iso(txt(c))
                if iso:
                    sh.date_iso = iso
                    break
        if txt(row[0]).upper().startswith("TO"):
            sh.customer = next((txt(c) for c in row[1:] if txt(c)), "")
        upper_cells = [txt(c).upper() for c in row]
        if any(u.startswith("ITEM") for u in upper_cells) and any(
            "QUANTITY" in u or u.startswith("QTY") for u in upper_cells
        ):
            header_row = i
            for j, u in enumerate(upper_cells):
                if u.startswith("ITEM"):
                    cols["item"] = j
                elif "QUANTITY" in u or u.startswith("QTY"):
                    cols["qty"] = j
                elif u.startswith("UNIT"):
                    cols["unit"] = j
                elif "NEW" in u and "PRICE" in u:
                    cols["price"] = j
                    sh.layout = "price-revision"
                elif "CURRENT" in u and "PRICE" in u:
                    cols["price_current"] = j
                elif "PRICE" in u and "price" not in cols:
                    cols["price"] = j
                elif "MATERIAL" in u:
                    sh.layout = "old-material-columns"
            break
        # tiered-MOQ layout: ITEM row, then a second header row holding
        # QUANTITY | UNIT | PRICE twice (one block per minimum-order size)
        if any(u.startswith("ITEM") for u in upper_cells) and i + 1 < len(grid):
            next_cells = [txt(c).upper() for c in grid[i + 1]]
            if any("QUANTITY" in u for u in next_cells):
                header_row = i + 1
                sh.layout = "tiered-moq"
                for j, u in enumerate(upper_cells):
                    if u.startswith("ITEM"):
                        cols["item"] = j
                for j, u in enumerate(next_cells):
                    if "QUANTITY" in u and "qty" not in cols:
                        cols["qty"] = j
                    elif u.startswith("UNIT") and "unit" not in cols:
                        cols["unit"] = j
                    elif "PRICE" in u:
                        if "price" not in cols:
                            cols["price"] = j
                        else:
                            cols["price_tier2"] = j
                break
    # revision sheets sometimes carry only CURRENT PRICE
    if "price" not in cols and "price_current" in cols:
        cols["price"] = cols.pop("price_current")

    if header_row < 0:
        blob = " ".join(txt(c) for row in grid for c in row)
        sh.error = "no ITEM/QUANTITY header" if blob.strip() else "empty sheet"
        return sh

    current: Item | None = None
    for row in grid[header_row + 1:]:
        cells = [txt(c) for c in row]
        joined = " ".join(cells)
        if "หมายเหตุ" in joined or "CONDITION" in joined:
            break
        qty = cells[cols["qty"]] if "qty" in cols and cols["qty"] < len(cells) else ""
        unit = cells[cols["unit"]] if "unit" in cols and cols["unit"] < len(cells) else ""
        if not unit and qty:
            # combined "QTY/UNIT" column: "1 PC." in one cell, or unit in the next
            m = re.fullmatch(rf"({NUM})\s+(\S+)", qty)
            if m:
                qty, unit = m.group(1), m.group(2)
            elif "qty" in cols and cols["qty"] + 1 < len(cells) and norm_sale_unit(cells[cols["qty"] + 1]):
                unit = cells[cols["qty"] + 1]
        price_txt = cells[cols["price"]] if "price" in cols and cols["price"] < len(cells) else ""
        prev_txt = cells[cols["price_current"]] if "price_current" in cols and cols["price_current"] < len(cells) else ""
        desc_cells = [
            c for j, c in enumerate(cells)
            if c and j not in {cols.get("qty"), cols.get("unit"), cols.get("price")}
            and not re.fullmatch(rf"({NUM})\.?", c.replace(",", ""))
        ]
        desc = " ".join(dict.fromkeys(desc_cells))
        price = None
        pm = re.fullmatch(rf"({NUM})", price_txt.replace(",", ""))
        if pm:
            price = float(pm.group(1))
        if not desc and price is None:
            continue
        # "(MINIMUM ORDER 5,000 PCS.)" is a note under the item above - and in
        # some books it is the row that carries the price
        if current is not None and re.match(r"^\(?\s*MINIMUM ORDER", desc, re.I):
            current.description = (current.description + " " + desc).strip()
            if price is not None:
                if current.price is None:
                    current.price = price
                elif price != current.price:
                    current.reasons.append(f"second price on MOQ line: {price}")
            continue
        item_cell = cells[cols["item"]] if cols.get("item", 99) < len(cells) else ""
        is_new_item = price is not None or bool(re.fullmatch(r"\d+\.?", item_cell))
        if current is None and not is_new_item:
            # header residue such as the "(THB)" line under CURRENT/NEW PRICE:
            # nothing above to attach it to, and counting it as an item shifts
            # every item number on the sheet by one
            continue
        if current is not None and not is_new_item:
            current.description = (current.description + " " + desc).strip()
            continue
        current = Item(description=desc, quantity=qty, unit=unit, price=price)
        pm2 = re.fullmatch(rf"({NUM})", prev_txt.replace(",", ""))
        if pm2:
            current.previous_price = float(pm2.group(1))
        if "price_tier2" in cols and cols["price_tier2"] < len(cells):
            t2 = re.fullmatch(rf"({NUM})", cells[cols["price_tier2"]].replace(",", ""))
            if t2:
                current.reasons.append(f"tiered MOQ quote: higher-volume price {t2.group(1)}")
        sh.items.append(current)
    return sh


def to_row(sh: Sheet, item: Item, idx: int, letter: str) -> dict:
    inputs: dict = {}
    sale = norm_sale_unit(item.unit)
    # review rows keep their parsed geometry too (even with no product_key,
    # e.g. EPE/cover): the label questions the row, and discarding what the
    # paper says would only hide it from the reviewer
    if item.status in {"verified", "parsed", "partial", "review"} and item.width is not None:
        inputs = {
            "product_key": item.product_key,
            "width": {"value": item.width, "unit": item.width_unit},
            "sale_basis": sale or "piece",
        }
        if item.length is not None:
            inputs["length"] = {"value": item.length, "unit": item.length_unit}
        if item.gusset is not None:
            inputs["gusset"] = {"value": item.gusset, "unit": item.gusset_unit}
        if item.thickness is not None:
            inputs["thickness"] = {
                "value": item.thickness, "unit": item.thickness_unit,
                "mode": item.thickness_mode or item.thickness_mode_hint or "pair",
            }
        if item.price is not None:
            key = ("selling_price_per_kg_override" if sale == "kg"
                   else "selling_price_per_piece_override")
            inputs[key] = item.price
        inputs["density_g_cm3"] = item.density
    return {
        "candidate_ref": sh.ref or sh.sheet,
        "ref_text": sh.ref_text,
        "sheet": sh.sheet,
        "item_index": idx,
        "quote_date": sh.date_iso,
        "customer": sh.customer,
        "customer_folder": sh.file.parent.name,
        "item_description": item.description,
        "product_name": item.product_name,
        "product_reference": item.part_code,
        "resin": item.resin,
        "quantity": item.quantity,
        "unit": item.unit,
        "unit_price": item.price,
        "previous_price": item.previous_price,
        "product_key": item.product_key,
        "product_note": item.product_note,
        "grams_per_item": item.grams,
        "implied_thb_per_kg": item.implied_thb_per_kg,
        "inputs": inputs,
        "extraction_status": item.status,
        "reasons": item.reasons,
        "import_source": f"Z:/{letter}/{sh.file.relative_to(sh.file.parents[1])}#{sh.sheet}",
    }


NOT_A_QUOTE_FILE = re.compile(
    r"ขอตัวอย่าง|Part List|การ Pack|PACKING STYLE|Green_Procurement|ไซต์|คอนเฟิร์ม", re.I
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("letter", help="customer letter folder, e.g. A")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    import openpyxl

    zroot = Path("Z:/")
    qroot = next(d for d in zroot.iterdir() if d.is_dir() and d.name.startswith("Quotation"))
    folder = qroot / args.letter
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    rows: list[dict] = []
    sheets_seen = 0
    errors: list[str] = []

    for f in sorted(folder.rglob("*")):
        if not f.is_file():
            continue
        rel = str(f.relative_to(qroot))
        ext = f.suffix.lower()
        if f.name.startswith("~$"):
            manifest.append({"file": rel, "status": "lock-file (someone has it open)"})
            continue
        if ext == ".xls":
            manifest.append({"file": rel, "status": "old-xls: needs conversion pass"})
            continue
        if ext in {".pdf", ".jpg", ".jpeg", ".png", ".ai", ".msg", ".docx", ".doc"}:
            manifest.append({"file": rel, "status": f"evidence ({ext[1:]}): attach, not parse"})
            continue
        if ext != ".xlsx":
            manifest.append({"file": rel, "status": f"other ({ext})"})
            continue
        if NOT_A_QUOTE_FILE.search(f.name):
            manifest.append({"file": rel, "status": "not-a-quote (sample request / part list form)"})
            continue
        try:
            wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        except Exception as exc:
            manifest.append({"file": rel, "status": f"xlsx unreadable: {exc}"})
            errors.append(f"{rel}: {exc}")
            continue
        parsed = 0
        for sheet_name in wb.sheetnames:
            try:
                sh = read_sheet(wb[sheet_name], f, sheet_name)
            except Exception as exc:
                errors.append(f"{rel}#{sheet_name}: {exc}")
                continue
            sheets_seen += 1
            if sh.error:
                # a sheet with a printed REF NO is a quote we failed to read - a
                # real error; a sheet without one is simply not a quotation
                if sh.error != "empty sheet" and sh.ref:
                    errors.append(f"{rel}#{sheet_name}: {sh.error}")
                continue
            parsed += 1
            for idx, item in enumerate(sh.items, start=1):
                classify_product(item)
                detect_resin(item)
                extract_product_name(item)
                extract_part_code(item)
                parse_dimensions(item)
                if item.product_key is None and item.status == "name_only" and item.width is not None:
                    # part-list rows like "PS294 L900xW900xT0.08" carry full
                    # geometry but no product word. With thickness present the
                    # price oracle can still confirm or refuse a flat reading;
                    # without it the row stays honestly partial.
                    if item.thickness is not None and item.length is not None:
                        item.product_key = "flat"
                        item.product_note = "no product word: flat-bag geometry assumed, subject to price check"
                    else:
                        item.status = "partial"
                        item.reasons.append("dimensions found but no product word to pick a formula")
                if item.status not in {"review", "trading", "partial"}:
                    verify_with_price(item)
                rows.append(to_row(sh, item, idx, args.letter))
        wb.close()
        manifest.append({"file": rel, "status": f"parsed {parsed} quote sheet(s)"})

    with (out / "rows.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with (out / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "status"])
        w.writeheader()
        w.writerows(manifest)
    review = [r for r in rows if r["extraction_status"] in {"review", "partial", "name_only"}]
    with (out / "review.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ref", "sheet", "customer_folder", "description", "unit", "price", "status", "reasons"])
        for r in review:
            w.writerow([r["candidate_ref"], r["sheet"], r["customer_folder"],
                        r["item_description"][:120], r["unit"], r["unit_price"],
                        r["extraction_status"], "; ".join(r["reasons"])])

    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["extraction_status"]] = by_status.get(r["extraction_status"], 0) + 1
    total = len(rows) or 1
    lines = [
        f"# Extraction pilot — folder {args.letter}",
        "",
        f"- files in manifest: {len(manifest)}",
        f"- quote sheets read: {sheets_seen}",
        f"- items extracted:   {len(rows)}",
        "",
        "| status | items | % |",
        "|---|---|---|",
    ]
    for k in ("verified", "parsed", "partial", "review", "trading", "name_only"):
        if k in by_status:
            lines.append(f"| {k} | {by_status[k]} | {by_status[k] * 100 // total}% |")
    with_resin = sum(1 for r in rows if r["resin"])
    with_name = sum(1 for r in rows if r["product_name"])
    with_code = sum(1 for r in rows if r["product_reference"])
    lines += [
        "",
        f"- rows with resin named:   {with_resin} ({with_resin * 100 // total}%)",
        f"- rows with product name:  {with_name} ({with_name * 100 // total}%)",
        f"- rows with part code:     {with_code} ({with_code * 100 // total}%)",
        f"- sheet errors: {len(errors)}",
    ]
    lines += [f"  - {e}" for e in errors[:20]]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
