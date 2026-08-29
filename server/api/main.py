"""HTTP API around the desktop app's calculation core.

The two files in core/ are byte-identical copies of the Windows program
(Z:\\1\\calculator.py and formula_engine.py). Nothing here re-derives a formula:
this module only converts units at the boundary, calls calculate(), and formats
the result into the same strings the desktop screen shows. Any arithmetic drift
between this and the .exe would be a bug in THIS file, never in the formulas.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

import db  # noqa: E402
from calculator import (  # noqa: E402
    DEFAULT_PRICE_FORMULA,
    DEFAULT_WEIGHT_FORMULAS,
    DIMENSION_FACTORS_TO_CM,
    FORMULA_VARIABLES,
    LENGTH_REFERENCES,
    PRODUCTS,
    THICKNESS_FACTORS_TO_MM,
    calculate,
    require_positive_dimensions,
    size_description,
    thickness_to_mm,
    to_cm,
)
from formula_engine import FormulaError  # noqa: E402
from drawing import (  # noqa: E402
    PRODUCT_TO_SHAPE,
    DrawingError,
    DrawingSpec,
    render_html,
    render_svg,
)
import screen  # noqa: E402
from screen import screen_labels  # noqa: E402

import auth  # noqa: E402
import releases  # noqa: E402
import routes_auth  # noqa: E402
import pacos_gate  # noqa: E402
import pacos_bridge  # noqa: E402
import routes_bridge  # noqa: E402
import store  # noqa: E402

# Clone cua MA NGUON tai Z:\1, khong phai cua mot ban .exe. Toi 27-08 nguon da
# len "1.7.1 (Phase 1) - Planning screen" (app.py:51, mtime 18:12) - MOI HON ban
# .exe v1.5.1 (17:31). CEO sua nguon nhieu lan mot ngay: truoc khi tin ban clone,
# so mtime va APP_VERSION cua Z:\1\app.py voi chuoi duoi day.
APP_VERSION = "src-2026-08-27T18:12 (ui == app.py v1.7.1)"
app = FastAPI(title="Plastic Pricing", version=APP_VERSION, docs_url="/api/docs")


# --------------------------------------------------------------------------- #
# Request shapes
# --------------------------------------------------------------------------- #


class Measure(BaseModel):
    value: float = 0.0
    unit: str = "ซม."


class Thickness(BaseModel):
    value: float = 0.0
    unit: str = "มม."
    mode: Literal["side", "pair"] = "pair"


class CalcRequest(BaseModel):
    product_key: Literal["flat", "opaque", "gusset", "roll", "cover"] = "flat"

    width: Measure = Field(default_factory=Measure)
    length: Measure = Field(default_factory=Measure)
    height: Measure = Field(default_factory=Measure)
    gusset: Measure = Field(default_factory=Measure)
    sold_length: Measure = Field(default_factory=lambda: Measure(unit="เมตร"))
    bottom_allowance: Measure = Field(default_factory=lambda: Measure(value=1.0))
    thickness: Thickness = Field(default_factory=Thickness)

    length_reference: str = LENGTH_REFERENCES["opening_to_seal"]

    density_g_cm3: float = 0.92
    material_price_per_kg: float = 65.0
    deduction_percent: float = 10.0
    apply_deduction: bool = True

    sale_basis: Literal["kg", "piece"] = "kg"
    selling_price_per_piece_override: float = 0.0
    selling_price_per_kg_override: float = 0.0

    pack_quantity: float = 0.0
    sack_quantity: float = 0.0
    order_quantity: float = 1000.0
    control_min_g: float = 0.0
    control_max_g: float = 0.0
    roof_gsm: float = 120.0
    mesh_gsm: float = 80.0

    weight_formula: str = ""
    price_formula: str = DEFAULT_PRICE_FORMULA

    # Carried through to the saved record, not used by the arithmetic.
    tolerance_width: Measure = Field(default_factory=lambda: Measure(value=0.0, unit="มม."))
    tolerance_length: Measure = Field(default_factory=lambda: Measure(value=0.0, unit="มม."))
    tolerance_thickness: Measure = Field(default_factory=lambda: Measure(value=0.0, unit="มม."))


class DrawingRequest(BaseModel):
    """The approval drawing, asked for in the units somebody is working in.

    Converted to millimetres HERE, at the boundary, and nowhere else - the
    drawing module stores mm and only mm, and a figure that arrives already
    converted is a figure nobody can check (LAW P11).
    """

    product_key: Literal["flat", "opaque", "gusset", "roll", "cover"] = "flat"
    doc_no: str = ""
    customer: str = ""
    customer_code: str = ""
    title: str = ""
    part_no: str = "-"
    revision: str = "A"
    date: str = ""
    material: str = "POLYETHYLENE"
    color: str = "-"
    printing: str = "-"

    width: Measure = Field(default_factory=Measure)
    length: Measure = Field(default_factory=Measure)
    height: Measure = Field(default_factory=Measure)
    gusset: Measure = Field(default_factory=Measure)
    thickness: Thickness = Field(default_factory=Thickness)

    tol_dim_lo: float = -10.0
    tol_dim_hi: float = 10.0
    tol_thickness: float = 0.005
    length_datum: str = "opening_to_seal"
    display_unit: Literal["mm", "inch"] = "mm"
    holes_count: int = 0
    holes_dia: str = ""
    label_w: float = 0.0
    label_h: float = 0.0
    extra_notes: list[str] = Field(default_factory=list)


def _to_mm(measure: Measure) -> float:
    if measure.unit not in DIMENSION_FACTORS_TO_CM:
        raise ValueError("หน่วยระยะไม่รองรับ: " + measure.unit)
    return measure.value * DIMENSION_FACTORS_TO_CM[measure.unit] * 10.0


@app.post("/api/drawing")
def api_drawing(req: DrawingRequest) -> dict[str, Any]:
    """The approval drawing, as SVG.

    Drawn by the desktop program's OWN drawing.py - the same file, copied whole
    into core/ beside calculator.py. The browser is handed a finished picture
    rather than a list of lines to draw itself, for the same reason it is handed
    a finished figure rather than a formula: two programs drawing the same bag
    are two drawings, and the customer signs one of them.
    """
    try:
        spec = DrawingSpec(
            doc_no=req.doc_no.strip() or "-",
            customer=req.customer.strip(),
            title=req.title.strip(),
            shape=PRODUCT_TO_SHAPE[req.product_key],
            revision=req.revision.strip() or "A",
            date=req.date.strip(),
            part_no=req.part_no.strip() or "-",
            customer_code=req.customer_code.strip(),
            material=req.material.strip() or "POLYETHYLENE",
            color=req.color.strip() or "-",
            printing=req.printing.strip() or "-",
            width_mm=_to_mm(req.width),
            length_mm=_to_mm(req.length),
            height_mm=_to_mm(req.height),
            gusset_mm=_to_mm(req.gusset),
            thickness_mm=thickness_to_mm(req.thickness.value, req.thickness.unit),
            tol_dim_lo=req.tol_dim_lo,
            tol_dim_hi=req.tol_dim_hi,
            tol_thickness=req.tol_thickness,
            length_datum=req.length_datum,
            display_unit=req.display_unit,
            holes_count=req.holes_count,
            holes_dia=req.holes_dia.strip(),
            label_w=req.label_w,
            label_h=req.label_h,
            extra_notes=[line for line in req.extra_notes if line.strip()],
        )
        return {"svg": render_svg(spec)}
    except (DrawingError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/customers")
def api_customers(limit: int = Query(default=2000, ge=1, le=5000)) -> dict[str, Any]:
    """Who has been quoted before, the most-quoted first.

    ORDERED BY HOW OFTEN, NOT ALPHABETICALLY. The point of the list is to save
    typing for the company somebody quotes every week, and alphabetical order
    buries those behind whoever starts with "A".

    The code that comes back is the one MOST used with that name: 17,391 rows
    read out of the paper books carry no customer code at all, so for most names
    it is blank - and blank is what must be returned, not a guess.
    """
    return {"rows": db.known_customers(limit)}


class SaveRequest(BaseModel):
    calc: CalcRequest
    quote_date: date
    customer: str
    customer_code: str = ""
    item_description: str = ""
    product_reference: str = ""
    product_image_path: str = ""
    revised_from_ref: str = ""


# --------------------------------------------------------------------------- #
# Boundary: units in, numbers out. Mirrors app.py _collect_inputs.
# --------------------------------------------------------------------------- #


def _check_units(req: CalcRequest) -> None:
    for name, measure in (
        ("width", req.width),
        ("length", req.length),
        ("height", req.height),
        ("gusset", req.gusset),
        ("sold_length", req.sold_length),
        ("bottom_allowance", req.bottom_allowance),
    ):
        if measure.unit not in DIMENSION_FACTORS_TO_CM:
            raise ValueError("หน่วยระยะไม่รองรับ (" + name + "): " + measure.unit)
    if req.thickness.unit not in THICKNESS_FACTORS_TO_MM:
        raise ValueError("หน่วยความหนาไม่รองรับ: " + req.thickness.unit)


def normalize(req: CalcRequest) -> dict[str, Any]:
    _check_units(req)
    is_bag = req.product_key in {"flat", "gusset"}
    normalized = {
        "width_cm": to_cm(req.width.value, req.width.unit),
        "length_cm": to_cm(req.length.value, req.length.unit),
        "height_cm": to_cm(req.height.value, req.height.unit),
        "gusset_cm": to_cm(req.gusset.value, req.gusset.unit),
        "sold_length_m": to_cm(req.sold_length.value, req.sold_length.unit) / 100,
        "thickness_input_mm": thickness_to_mm(req.thickness.value, req.thickness.unit),
        "bottom_allowance_cm": (
            to_cm(req.bottom_allowance.value, req.bottom_allowance.unit) if is_bag else 0.0
        ),
    }
    require_positive_dimensions(req.product_key, normalized)
    if req.control_max_g > 0 and req.control_min_g > req.control_max_g:
        raise ValueError("น้ำหนักควบคุมต่ำสุดต้องไม่มากกว่าค่าสูงสุด")
    return normalized


def auto_markup(material_price_per_kg: float, basis_per_kg: float) -> float:
    """markup% = ((basis/material) - 1) x 100. Derived, never typed (app.py:1817)."""
    if material_price_per_kg <= 0 or basis_per_kg <= 0:
        return 0.0
    return ((basis_per_kg / material_price_per_kg) - 1) * 100


def dimensions_raw(req: CalcRequest) -> dict[str, dict[str, Any]]:
    return {
        "width": {"value": req.width.value, "unit": req.width.unit},
        "length": {"value": req.length.value, "unit": req.length.unit},
        "height": {"value": req.height.value, "unit": req.height.unit},
        "gusset": {"value": req.gusset.value, "unit": req.gusset.unit},
        "sold_length": {"value": req.sold_length.value, "unit": req.sold_length.unit},
    }


# --------------------------------------------------------------------------- #
# Formatting: the exact strings the desktop screen prints.
# --------------------------------------------------------------------------- #


def n(value: float, digits: int = 3) -> str:
    return format(value, "," + "." + str(digits) + "f")


def g(value: float) -> str:
    return format(value, "g")


def build_display(req: CalcRequest, res: Any, normalized: dict[str, Any], markup: float) -> dict[str, str]:
    length_unit = req.length.unit
    shown_length = res.material_length_cm / DIMENSION_FACTORS_TO_CM[length_unit]
    material_length = n(shown_length) + " " + length_unit
    if length_unit != "ซม.":
        material_length += " (" + n(res.material_length_cm) + " ซม.)"

    packaging_weights = [
        weight
        for quantity, weight in (
            (req.pack_quantity, res.pack_weight_kg),
            (req.sack_quantity, res.sack_weight_kg),
        )
        if quantity > 0
    ]
    # "!" and "√", not "⚠" and "✓": the desktop's own characters (app.py:3045-3050).
    # Leelawadee UI has no warning triangle, so the program never used one.
    if not packaging_weights:
        pack_warning = "ยังไม่ได้กำหนดจำนวนบรรจุ / Packaging Not Set"
    elif max(packaging_weights) > 25:
        pack_warning = "! น้ำหนักบรรจุเกิน 25 กก. / Packaging over 25 kg"
    else:
        pack_warning = "√ น้ำหนักบรรจุไม่เกิน 25 กก. / Packaging ≤ 25 kg"

    not_set = "ยังไม่ได้กำหนด / Not Set"
    control_range = (
        g(req.control_min_g) + "–" + g(req.control_max_g) + " กรัม • " + res.control_status
        if req.control_min_g > 0 or req.control_max_g > 0
        else "ไม่กำหนดช่วง / No range • " + res.control_status
    )
    return {
        "grams": n(res.grams_per_item) + " กรัม",
        "material_length": material_length,
        "items_per_kg": n(res.items_per_kg, 2) + " ชิ้น",
        "adjusted_items": n(res.production_items_per_kg, 2) + " ชิ้น",
        "deduction_effect": (
            "เปิด / ON −" + g(req.deduction_percent) + "%"
            if req.apply_deduction
            else "ปิด / OFF (ใช้จำนวนปกติ / normal)"
        ),
        "unit_price": n(res.unit_price) + " บาท",
        "calculated_piece": n(res.calculated_price_per_piece_from_kg) + " บาท/ชิ้น",
        "selling_price_per_kg": n(res.selling_price_per_kg) + " บาท",
        "pack_weight": n(res.pack_weight_kg, 4) + " กก." if req.pack_quantity > 0 else not_set,
        "sack_weight": n(res.sack_weight_kg, 4) + " กก." if req.sack_quantity > 0 else not_set,
        "small_pack_qty": n(req.pack_quantity, 0) + " ชิ้น" if req.pack_quantity > 0 else not_set,
        "sack_qty": n(req.sack_quantity, 0) + " ชิ้น" if req.sack_quantity > 0 else not_set,
        "pack_warning": pack_warning,
        "required_kg": n(res.required_kg) + " กก.",
        "pack_count": n(res.pack_count) + " แพ็ก",
        "total_price": n(res.total_price) + " บาท",
        "control_status": res.control_status,
        "control_range": control_range,
        "roof_area": n(res.roof_area_cm2) + " ตร.ซม. (" + n(res.roof_area_cm2 / 10000) + " ตร.ม.)",
        "mesh_area": n(res.mesh_area_cm2) + " ตร.ซม. (" + n(res.mesh_area_cm2 / 10000) + " ตร.ม.)",
        "markup_percent": format(markup, ".2f") if markup else "",
        "size_text": size_description(req.product_key, dimensions_raw(req)),
        "primary_line": primary_line(req, res),
        "derivation": derivation_lines(req, res),
        "deduction_caption": deduction_caption(req),
    }


def deduction_caption(req: CalcRequest) -> str:
    """The live label over the adjusted-items tile (app.py:589-609)."""
    if not req.apply_deduction:
        return "จำนวนชิ้นต่อกก. (ไม่หักเผื่อ) / Items per kg (no deduction)"
    shown = g(req.deduction_percent)
    return "จำนวนชิ้นต่อกก.หลังหัก " + shown + "% / Items per kg after " + shown + "% deduction"


def primary_line(req: CalcRequest, res: Any) -> str:
    """The green line beside the sale-basis box, after a calculation
    (app.py:2811-2827)."""
    deduction = g(req.deduction_percent if req.apply_deduction else 0)
    if req.sale_basis == "kg":
        return (
            "ขายเป็นกก. / Sell by kg • จำนวนมาตรฐาน " + n(res.items_per_kg, 2)
            + " ชิ้น/กก. • จำนวนหลังหัก " + deduction + "% = "
            + n(res.production_items_per_kg, 2) + " ชิ้น/กก."
        )
    return (
        "ขายเป็นชิ้น / Sell by piece\n"
        + "น้ำหนักต่อชิ้น / Weight per item: " + n(res.grams_per_item) + " กรัม / g\n"
        + "จำนวนมาตรฐานต่อกก. / Standard items per kg: " + n(res.items_per_kg, 2)
        + " (จำนวนหลังหัก " + deduction + "% / Adjusted: " + n(res.production_items_per_kg, 2) + ")\n"
        + "ราคาคำนวณต่อชิ้น / Calculated price per piece: "
        + n(res.calculated_price_per_piece_from_kg) + " บาท / THB"
    )


def derivation_lines(req: CalcRequest, res: Any) -> str:
    """The three-line derivation under the price boxes when selling by piece
    (app.py:3017-3023). The desktop hides the label entirely when selling by
    kg; the screen does the same, so an empty string is the honest value there.
    """
    if req.sale_basis == "kg":
        return ""
    basis = req.selling_price_per_kg_override
    deduction = g(req.deduction_percent if req.apply_deduction else 0)
    return (
        "สูตรคำนวณ / Derivation\n"
        + n(basis) + " บาท/กก. ÷ จำนวนหลังหัก " + deduction + "% ("
        + n(res.production_items_per_kg, 2) + " ชิ้น/กก.) = "
        + n(res.calculated_price_per_piece_from_kg) + " บาท/ชิ้น\n"
        + "ไม่ใช้จำนวนแพ็กในการคำนวณ / pack quantity not used"
    )


def human_summary(req: CalcRequest, res: Any, normalized: dict[str, Any]) -> str:
    """Same verification line as app.py _human_calculation_summary."""
    thickness_mm = normalized["thickness_input_mm"]
    density = req.density_g_cm3
    key = req.product_key
    if key == "gusset":
        area_text = (
            "(" + g(normalized["width_cm"]) + " + " + g(normalized["gusset_cm"]) + ") × "
            + g(res.material_length_cm)
        )
    elif key in {"flat", "opaque"}:
        area_text = g(normalized["width_cm"]) + " × " + g(res.material_length_cm)
    elif key == "roll":
        area_text = g(normalized["width_cm"]) + " × " + g(normalized["sold_length_m"]) + " m"
    else:
        # "»", not "→": the desktop's own separator (app.py:2928-2933).
        return (
            "น้ำหนัก / Weight = " + n(res.grams_per_item) + " g  »  "
            "จำนวน / Items = " + n(res.items_per_kg, 2) + "/kg  »  "
            "ราคา / Price = " + n(res.calculated_price_per_piece_from_kg) + " THB/item"
        )
    if req.thickness.mode == "pair":
        thickness_text = (
            "(" + g(thickness_mm) + "/10) × " + g(density)
            + " [Per Pair: ใช้ความหนารวมโดยตรง, ไม่คูณ 2 / no extra ×2]"
        )
    else:
        thickness_text = (
            "2 × (" + g(thickness_mm) + "/10) × " + g(density)
            + " [Per Side: คูณสองด้าน / ×2 sides]"
        )
    deduction = req.deduction_percent if req.apply_deduction else 0
    basis = req.selling_price_per_kg_override
    price_step = (
        g(basis) + " ÷ " + n(res.production_items_per_kg, 2) + " = "
        if basis > 0
        else "ผลสูตรต้นทุน / cost formula = "
    )
    return (
        "ตรวจสูตรน้ำหนัก / Weight: " + area_text + " × " + thickness_text
        + " = " + n(res.grams_per_item) + " g\n"
        + "จำนวน / Items: 1,000 ÷ " + n(res.grams_per_item) + " = " + n(res.items_per_kg, 2)
        + "/kg; หลังหัก " + g(deduction) + "% / adjusted = " + n(res.production_items_per_kg, 2) + "/kg\n"
        + "ราคาต่อชิ้น / Price per item: " + price_step
        + n(res.calculated_price_per_piece_from_kg) + " THB"
    )


def price_basis_summary(req: CalcRequest, res: Any, price_formula: str) -> str:
    basis = req.selling_price_per_kg_override
    adjusted = res.production_items_per_kg
    if req.sale_basis == "kg" and basis > 0:
        return "ราคาขายที่กรอก " + n(basis) + " บาท/กก. / Entered final price per kg"
    if basis > 0 and adjusted > 0:
        return n(basis) + " บาท/กก. ÷ " + n(adjusted, 2) + " ชิ้น/กก."
    return "สูตรราคา / Price formula: " + price_formula


# --------------------------------------------------------------------------- #
# The one place a calculation happens
# --------------------------------------------------------------------------- #


def run_calculation(req: CalcRequest) -> dict[str, Any]:
    normalized = normalize(req)
    weight_formula = (req.weight_formula or "").strip() or DEFAULT_WEIGHT_FORMULAS[req.product_key]
    price_formula = (req.price_formula or "").strip() or DEFAULT_PRICE_FORMULA
    markup = auto_markup(req.material_price_per_kg, req.selling_price_per_kg_override)

    res = calculate(
        product_key=req.product_key,
        width_cm=normalized["width_cm"],
        length_cm=normalized["length_cm"],
        height_cm=normalized["height_cm"],
        gusset_cm=normalized["gusset_cm"],
        sold_length_m=normalized["sold_length_m"],
        bottom_allowance_cm=normalized["bottom_allowance_cm"],
        thickness_input_mm=normalized["thickness_input_mm"],
        thickness_mode=req.thickness.mode,
        density_g_cm3=req.density_g_cm3,
        roof_gsm=req.roof_gsm,
        mesh_gsm=req.mesh_gsm,
        material_price_per_kg=req.material_price_per_kg,
        markup_percent=markup,
        deduction_percent=req.deduction_percent,
        pack_quantity=req.pack_quantity,
        sack_quantity=req.sack_quantity,
        apply_deduction=req.apply_deduction,
        sell_by_kg=req.sale_basis == "kg",
        selling_price_per_piece_override=req.selling_price_per_piece_override,
        selling_price_per_kg_override=req.selling_price_per_kg_override,
        order_quantity=req.order_quantity,
        control_min_g=req.control_min_g,
        control_max_g=req.control_max_g,
        weight_formula=weight_formula,
        price_formula=price_formula,
    )

    results = {
        "grams_per_item": res.grams_per_item,
        "items_per_kg": res.items_per_kg,
        "production_items_per_kg": res.production_items_per_kg,
        "unit_price": res.unit_price,
        "selling_price_per_kg": res.selling_price_per_kg,
        "calculated_price_per_piece_from_kg": res.calculated_price_per_piece_from_kg,
        "pack_weight_kg": res.pack_weight_kg,
        "sack_weight_kg": res.sack_weight_kg,
        "total_price": res.total_price,
        "required_kg": res.required_kg,
        "pack_count": res.pack_count,
        "control_status": res.control_status,
        "roof_area_cm2": res.roof_area_cm2,
        "mesh_area_cm2": res.mesh_area_cm2,
        "material_length_cm": res.material_length_cm,
        "markup_percent": markup,
    }
    return {
        "raw": res,
        "results": results,
        "normalized": normalized,
        "display": build_display(req, res, normalized, markup),
        "human_summary": human_summary(req, res, normalized),
        "price_basis": price_basis_summary(req, res, price_formula),
        "formulas": {"weight": weight_formula, "price": price_formula},
    }


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


OPEN_PATHS = {
    "/api/health",
    "/api/meta",
    "/api/auth/login",
    "/api/docs",
    "/api/openapi.json",
    # The download page must work for somebody who has no account yet - that is
    # what they come to it to get. It gives away a version number and an
    # installer that does nothing without one.
    "/api/version",
}


@app.middleware("http")
async def require_signed_in(request: Request, call_next):
    """Everything under /api needs a token except the five paths above.

    A gate, not a decorator on each route: a route added next month is closed by
    default rather than closed if somebody remembered. /api/meta stays open
    because the sign-in screen draws itself from the labels it returns, and
    /api/health because a monitor cannot hold a password.
    """
    path = request.url.path
    if path.startswith("/api/") and path not in OPEN_PATHS:
        header = request.headers.get("authorization")
        try:
            routes_auth.current_user(header)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": str(exc.detail), "detail": str(exc.detail)},
            )
    return await call_next(request)


app.include_router(routes_auth.router)
app.include_router(routes_bridge.router)
app.include_router(releases.router)




@app.exception_handler(HTTPException)
def _house_error_shape(request: Request, exc: HTTPException) -> JSONResponse:
    """PacOs reads `error`, FastAPI writes `detail`.

    Its client does `body.error ?? "The server refused the request (400)."`
    (pacos-fontend/src/lib/api.ts:55). Left alone, every check this service
    makes - "หน่วยความหนาไม่รองรับ", "สูตรหารด้วยศูนย์" - would reach the
    screen as that one useless English sentence. The message is the whole
    point of validating, so this service speaks the house shape.
    """
    detail = exc.detail
    message = detail if isinstance(detail, str) else str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": message, "detail": message},
        headers=getattr(exc, "headers", None) or {},
    )


@app.exception_handler(RequestValidationError)
def _validation_error_shape(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", ()) if p not in ("body",))
    message = (where + ": " if where else "") + str(first.get("msg", "invalid request"))
    return JSONResponse(status_code=400, content={"error": message, "detail": message})


@app.on_event("startup")
def _startup() -> None:
    applied = db.run_migrations()
    if applied:
        print("migrations applied: " + ", ".join(applied), flush=True)
    # Raises when AUTH_MODE is misspelt or names PacOs without an address,
    # so the container fails its health check instead of quietly opening
    # the door with local passwords.
    print(pacos_gate.describe(), flush=True)
    print(pacos_bridge.describe(), flush=True)
    # Mirrors PacOs's customers at boot and every quarter hour, off the
    # request path. Does nothing when the bridge is not set up.
    pacos_bridge.start_background()
    created = routes_auth.bootstrap_admin()
    if created:
        print("bootstrap account created: " + created, flush=True)


@app.on_event("shutdown")
def _shutdown() -> None:
    db.close_pool()


@app.get("/api/health")
def health() -> dict[str, Any]:
    try:
        db.ping()
    except Exception as exc:  # noqa: BLE001 - the caller needs the reason, not a type
        raise HTTPException(status_code=503, detail={"ok": False, "postgres": str(exc)}) from exc
    return {"ok": True, "version": APP_VERSION, "checks": {"postgres": {"ok": True}}}


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    return {
        "version": APP_VERSION,
        # WHAT A PERSON SEES, as against what a diagnosis needs. APP_VERSION is
        # a build string and belongs in a log. The desktop gate prints
        # "v" + the version's first word (gate.py:150) - "v1.7.1" - and the
        # sign-in screen here says the same thing, from screen.py's one copy.
        "version_label": screen.VERSION_LABEL,
        # Whose password the box on the gate is asking for. Open on purpose:
        # a sign-in screen that will not say which account it wants is one
        # more thing for a person to guess at.
        "sign_in_with": pacos_gate.mode(),
        # Whether the history tab may send ticked prices to PacOs. Drawn from
        # the server so the button never promises a bridge that is not there.
        "pacos_bridge": pacos_bridge.configured(),
        "products": PRODUCTS,
        "length_references": LENGTH_REFERENCES,
        "dimension_units": list(DIMENSION_FACTORS_TO_CM),
        "thickness_units": list(THICKNESS_FACTORS_TO_MM),
        "default_weight_formulas": DEFAULT_WEIGHT_FORMULAS,
        "default_price_formula": DEFAULT_PRICE_FORMULA,
        "formula_variables": FORMULA_VARIABLES,
        # The Formula Variables window's whole text, composed the way
        # show_formula_help composes it (app.py:3796-3804): name, two spaces,
        # "=", two spaces, description.
        "formula_help_text": "\n".join(
            ["ตัวแปรที่ใช้ได้ในสูตร / Formula Variables", ""]
            + [name + "  =  " + desc for name, desc in FORMULA_VARIABLES.items()]
            + [
                "",
                "เครื่องหมาย / Operators: +  -  *  /  %  **  ( )",
                "ฟังก์ชัน / Functions: abs, min, max, round, ceil, floor, sqrt",
                "",
                "หมายเหตุ / Note: สูตรไม่สามารถเรียกไฟล์ อินเทอร์เน็ต หรือคำสั่งระบบ / formulas cannot access files, internet, or system commands",
            ]
        ),
        # The screen's own words, so the panel that draws it holds none of its
        # own and PacOs's translator never rewrites the CEO's labels.
        "labels": screen_labels(),
    }


@app.post("/api/calculate")
def api_calculate(req: CalcRequest) -> dict[str, Any]:
    try:
        out = run_calculation(req)
    except (ValueError, FormulaError, ZeroDivisionError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "results": out["results"],
        "normalized": out["normalized"],
        "display": out["display"],
        "human_summary": out["human_summary"],
        "price_basis": out["price_basis"],
        "formulas": out["formulas"],
    }


@app.post("/api/quotations")
def api_save(req: SaveRequest) -> dict[str, Any]:
    if not req.customer.strip():
        raise HTTPException(status_code=400, detail="กรุณากรอกชื่อลูกค้า / Customer is required")
    if not req.customer_code.strip():
        raise HTTPException(status_code=400, detail="กรุณากรอกรหัสลูกค้า / Customer code is required")
    try:
        out = run_calculation(req.calc)
    except (ValueError, FormulaError, ZeroDivisionError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    calc = req.calc
    res = out["raw"]
    inputs = calc.model_dump(mode="json")
    inputs["normalized"] = out["normalized"]
    inputs["price_basis"] = out["price_basis"]
    inputs["human_summary"] = out["human_summary"]

    row = db.save_quotation(
        {
            "quote_date": req.quote_date,
            "customer": req.customer.strip(),
            "customer_code": req.customer_code.strip(),
            "item_description": req.item_description.strip(),
            "product_reference": req.product_reference.strip(),
            "product_image_path": req.product_image_path.strip(),
            "revised_from_ref": req.revised_from_ref.strip(),
            "product_key": calc.product_key,
            "product_label": PRODUCTS[calc.product_key],
            "size_text": out["display"]["size_text"],
            "length_reference": (
                calc.length_reference if calc.product_key in {"flat", "gusset"} else ""
            ),
            "inputs": inputs,
            "formulas": out["formulas"],
            "results": out["results"],
            "unit_price": res.unit_price,
            "total_price": res.total_price,
            "grams_per_item": res.grams_per_item,
            "pack_quantity": calc.pack_quantity,
            "pack_weight_kg": res.pack_weight_kg,
            "sack_quantity": calc.sack_quantity,
            "sack_weight_kg": res.sack_weight_kg,
        }
    )
    return {"quote_ref": row["quote_ref"], "id": row["id"], "created_at": row["created_at"]}


@app.get("/api/quotations")
def api_search(
    customer: str = "",
    item: str = "",
    product_key: str = "",
    size: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "newest",
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict[str, Any]:
    rows = db.search_quotations(
        customer=customer.strip(),
        item=item.strip(),
        product_key=product_key.strip(),
        size=size.strip(),
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        limit=limit,
    )
    return {"rows": rows, "count": len(rows)}


@app.get("/api/quotations/related")
def api_related(product_reference: str = "", item_description: str = "", size_text: str = "") -> dict[str, Any]:
    rows = db.related_quotations(
        product_reference=product_reference.strip(),
        item_description=item_description.strip(),
        size_text=size_text.strip(),
    )
    companies = sorted({r["customer"] for r in rows})
    return {"rows": rows, "companies": companies, "count": len(rows)}


# NOTE: the one-row GET and DELETE are registered at the BOTTOM of this file,
# after every /api/quotations/{ref}/<suffix> route. Their {quote_ref:path}
# converter is what lets a paper-book reference like "2569/09-01" - a slash
# the customer has been holding for years - reach its row at all; being
# greedy, it must be matched LAST or it would swallow /details and /print.


# --------------------------------------------------------------------------- #
# The history tab's own table, dialogs and edit-as-revision prefill.
# Formatted HERE, so the browser prints the desktop's exact cells
# (app.py:3979-4034, 4101-4169, 4185-4296) and holds no Thai of its own.
# --------------------------------------------------------------------------- #


def _sale_is_kg(sale_basis: Any) -> bool:
    s = str(sale_basis or "")
    # Desktop-synced rows hold the Thai label; web rows hold "kg"/"piece".
    return s.startswith("ขายเป็นกิโลกรัม") or s == "kg" or s == ""


def _sale_label(sale_basis: Any) -> str:
    s = str(sale_basis or "")
    if s in ("kg", "piece", ""):
        return "ขายเป็นกิโลกรัม / Sell by kg" if s != "piece" else "ขายเป็นชิ้น / Sell by piece"
    return s


def _thickness_cell(thickness: Any) -> str:
    th = thickness or {}
    value = th.get("value", 0) if isinstance(th, dict) else 0
    if not value:
        return "ไม่ใช้ / N/A"
    unit = th.get("unit", "มม.")
    mode = "ต่อคู่ / Per Pair" if th.get("mode", "pair") == "pair" else "ต่อด้าน / Per Side"
    return g(float(value)) + " " + unit + " • " + mode


def _f(value: Any, digits: int = 3) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def _calc_price_cells(row: dict[str, Any]) -> tuple[str, str, str]:
    """(calc_price, price_kg, price_piece) exactly as the table prints them."""
    by_kg = _sale_is_kg(row.get("sale_basis"))
    calc_kg = _f(row.get("calc_price_kg"))
    calc_piece = _f(row.get("calc_price_piece"))
    if calc_kg is None and calc_piece is not None:
        # Rows saved before calculated_price_per_kg existed: the desktop's own
        # derivation, piece x adjusted (app.py:3276-3279).
        adjusted = _f(row.get("production_items_per_kg")) or 0
        calc_kg = calc_piece * adjusted
    if by_kg:
        calc_price = n(calc_kg) if calc_kg is not None else "—"
        # A row read out of the books has no results block: its unit_price IS
        # the price per kg the customer was quoted. Printing 0.000 there hid
        # every kg price in the old books.
        price_kg = n(_f(row.get("selling_price_per_kg")) or float(row.get("unit_price") or 0))
        price_piece = "—"
    else:
        calc_price = n(calc_piece) if calc_piece is not None else "—"
        price_kg = "—"
        price_piece = n(float(row.get("unit_price") or 0))
    return calc_price, price_kg, price_piece


def _item_cell(row: dict[str, Any]) -> str:
    return " / ".join(
        part for part in (row.get("item_description"), row.get("product_reference")) if part
    )


def _history_cells(row: dict[str, Any]) -> dict[str, str]:
    calc_price, price_kg, price_piece = _calc_price_cells(row)
    pack_qty = float(row.get("pack_quantity") or 0)
    return {
        "ref": str(row["quote_ref"]),
        "date": str(row["quote_date"]),
        "customer_code": str(row.get("customer_code") or ""),
        "customer": str(row.get("customer") or ""),
        "sale_unit": _sale_label(row.get("sale_basis")),
        "item": _item_cell(row),
        "product": str(row.get("product_label") or ""),
        "size": str(row.get("size_text") or ""),
        "thickness": _thickness_cell(row.get("thickness_json")),
        "grams": n(float(row.get("grams_per_item") or 0)),
        "price_basis": str(row.get("price_basis") or ""),
        "calc_price": calc_price,
        "price_kg": price_kg,
        "price": price_piece,
        "pack": n(float(row.get("pack_weight_kg") or 0), 4) if pack_qty > 0 else "—",
        # Not columns: what the Related Companies button needs from the
        # selected row (app.py:4171-4183). Underscored so no column drifts in.
        "_product_reference": str(row.get("product_reference") or ""),
        "_item_description": str(row.get("item_description") or ""),
    }


@app.get("/api/history")
def api_history(
    customer: str = "",
    item: str = "",
    product_key: str = "",
    size: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "newest",
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict[str, Any]:
    rows = db.search_quotations(
        customer=customer.strip(),
        item=item.strip(),
        product_key=product_key.strip(),
        size=size.strip(),
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        limit=limit,
    )
    shown = len(rows)
    if shown >= limit:
        total = db.count_quotations()
        count_text = (
            "แสดง " + format(shown, ",") + " จากทั้งหมด " + format(total, ",")
            + " รายการ — ใช้ตัวกรองเพื่อค้นหา / showing " + format(shown, ",")
            + " of " + format(total, ",") + " — narrow with the filters above"
        )
    else:
        count_text = format(shown, ",") + " รายการ / records"
    return {"rows": [_history_cells(r) for r in rows], "count_text": count_text}


def _tree_filters(customer: str, item: str, product_key: str, size: str,
                  date_from: date | None, date_to: date | None) -> dict[str, Any]:
    return {
        "customer": customer.strip(), "item": item.strip(), "product_key": product_key.strip(),
        "size": size.strip(), "date_from": date_from, "date_to": date_to,
    }


def _period(first: Any, last: Any) -> str:
    a, b = str(first or ""), str(last or "")
    return a if a == b else a + " → " + b


@app.get("/api/history/tree/customers")
def api_history_tree_customers(
    customer: str = "", item: str = "", product_key: str = "", size: str = "",
    date_from: date | None = None, date_to: date | None = None,
) -> dict[str, Any]:
    """The book folded like a folder tree: customers first (the request came
    with a screenshot - "group by customer, then click to see their old
    prices"). Each folder says how many products and quotes it holds."""
    groups = db.history_customers(**_tree_filters(customer, item, product_key, size, date_from, date_to))
    total_quotes = sum(int(g["quotes"]) for g in groups)
    count_text = (
        format(len(groups), ",") + " ลูกค้า / customers · "
        + format(total_quotes, ",") + " รายการ / records"
    )
    return {
        "groups": [
            {
                "customer": g["customer"],
                "customer_code": g["customer_code"] or "",
                "quotes": int(g["quotes"]),
                "products": int(g["products"]),
                "period": _period(g["first_date"], g["last_date"]),
            }
            for g in groups
        ],
        "count_text": count_text,
    }


@app.get("/api/history/tree/products")
def api_history_tree_products(
    exact_customer: str, item: str = "", product_key: str = "", size: str = "",
    date_from: date | None = None, date_to: date | None = None,
) -> dict[str, Any]:
    groups = db.history_products(exact_customer, **_tree_filters("", item, product_key, size, date_from, date_to))
    out = []
    for g in groups:
        lo, hi = float(g["min_price"] or 0), float(g["max_price"] or 0)
        out.append({
            "product_name": g["product_name"] or "",
            "size": g["size_text"] or "",
            "quotes": int(g["quotes"]),
            "period": _period(g["first_date"], g["last_date"]),
            "latest_price": n(float(g["latest_price"] or 0)),
            "price_range": n(lo) if abs(hi - lo) < 0.0005 else n(lo) + " – " + n(hi),
            "sale_unit": _sale_label(g["sale_basis"]),
        })
    return {"groups": out}


@app.get("/api/history/tree/rows")
def api_history_tree_rows(
    exact_customer: str, product_name: str, size_text: str = "",
    item: str = "", product_key: str = "", size: str = "",
    date_from: date | None = None, date_to: date | None = None,
) -> dict[str, Any]:
    rows = db.history_rows(exact_customer, product_name, size_text,
                           **_tree_filters("", item, product_key, size, date_from, date_to))
    return {"rows": [_history_cells(r) for r in rows]}


@app.get("/api/related/table")
def api_related_table(
    product_reference: str = "", item_description: str = "", size_text: str = ""
) -> dict[str, Any]:
    rows = db.related_quotations(
        product_reference=product_reference.strip(),
        item_description=item_description.strip(),
        size_text=size_text.strip(),
    )
    title = "บริษัทที่เคยได้รับใบเสนอราคา / Related Companies"
    tag = product_reference.strip() or item_description.strip() or size_text.strip()
    if tag:
        title += " — " + tag
    cells = []
    for row in rows:
        calc_price, price_kg, price_piece = _calc_price_cells(row)
        pack_qty = float(row.get("pack_quantity") or 0)
        cells.append(
            {
                "ref": str(row["quote_ref"]),
                "date": str(row["quote_date"]),
                "customer_code": str(row.get("customer_code") or ""),
                "customer": str(row.get("customer") or ""),
                "sale_unit": _sale_label(row.get("sale_basis")),
                "item": _item_cell(row),
                "size": str(row.get("size_text") or ""),
                "grams": n(float(row.get("grams_per_item") or 0)),
                "price_basis": str(row.get("price_basis") or ""),
                "calc_price": calc_price,
                "price_piece": price_piece,
                "price_kg": price_kg,
                # The one cell the Related window words differently from the
                # history table (app.py:3226-3228).
                "pack_kg": (
                    n(float(row.get("pack_weight_kg") or 0), 4)
                    if pack_qty > 0
                    else "ยังไม่ได้กำหนด / Not Set"
                ),
            }
        )
    return {"title": title, "rows": cells, "count": len(cells)}


def _inputs_measure(inputs: dict[str, Any], name: str) -> dict[str, Any]:
    if "dimensions" in inputs:
        return inputs["dimensions"].get(name, {}) or {}
    return inputs.get(name, {}) or {}


@app.get("/api/quotations/{quote_ref:path}/details")
def api_details(quote_ref: str) -> dict[str, Any]:
    """The read-only Details window, line for line (app.py:4113-4162)."""
    row = db.get_quotation(quote_ref)
    if row is None:
        raise HTTPException(status_code=404, detail="ไม่พบใบเสนอราคา / Quotation not found")
    inputs = row["inputs_json"]
    results = row["results_json"]
    formulas = row["formulas_json"]

    def dash(value: Any) -> str:
        text = "" if value is None else str(value)
        return text if text.strip() else "-"

    def rf(key: str, digits: int = 3) -> str:
        return n(float(results.get(key) or 0), digits)

    thickness = inputs.get("thickness", {}) or {}
    allowance = _inputs_measure(inputs, "bottom_allowance")
    deduction = g(float(inputs.get("deduction_percent") or 0))
    apply_deduction = bool(inputs.get("apply_deduction", True))
    by_kg = _sale_is_kg(inputs.get("sale_basis"))
    pack_qty = float(inputs.get("pack_quantity") or 0)
    sack_qty = float(inputs.get("sack_quantity") or 0)

    lines = [
        "เลขอ้างอิง / Quote Ref: " + str(row["quote_ref"]),
        "วันที่ / Date: " + str(row["quote_date"]),
        "ชื่อลูกค้า/บริษัท / Customer/Company: " + dash(row["customer"]),
        "รหัสลูกค้า / Customer Code: " + dash(row["customer_code"]),
        "รายการ / Item: " + dash(row["item_description"]),
        "รหัสสินค้า / Part Number: " + dash(row["product_reference"]),
        "แก้ไขจาก / Revised from: " + dash(row["revised_from_ref"]),
        "รูป/ไฟล์ / Image/File: " + dash(row["product_image_path"]),
        "ประเภท / Product Type: " + str(row["product_label"]),
        "ขนาด / Size: " + str(row["size_text"]),
        "ความหนา / Thickness: " + _thickness_cell(thickness),
        "จุดอ้างอิง / Length Reference: " + dash(row["length_reference"]),
        "ค่าบวกก้นถุง / Bottom Allowance: "
        + g(float(allowance.get("value") or 0)) + " " + str(allowance.get("unit") or "ซม."),
        "",
        "ผลคำนวณ / Results",
        "  หน่วยขาย / Selling Unit: " + _sale_label(inputs.get("sale_basis")),
        "  ความยาววัสดุ / Material Length: " + rf("material_length_cm") + " ซม.",
        "  จำนวนมาตรฐานต่อกก. / Standard Items per kg: " + rf("items_per_kg", 2),
        "  การหักเผื่อ / Deduction: "
        + ("เปิด / ON (" + deduction + "%)" if apply_deduction else "ปิด / OFF"),
        "  จำนวนชิ้นต่อกก.หลังหัก " + deduction + "% / Items per kg after deduction: "
        + rf("production_items_per_kg", 2),
        "  ฐาน/สูตรที่ใช้คำนวณ / Price Basis/Formula: "
        + str(inputs.get("price_basis") or results.get("price_basis_summary") or ""),
    ]
    if by_kg:
        lines.append(
            "  ราคาขายจริงต่อกิโลกรัม / Final Selling Price per kg: "
            + rf("selling_price_per_kg") + " บาท"
        )
    else:
        lines += [
            "  ราคาต่อชิ้นที่คำนวณได้ / Calculated Price per Piece: "
            + rf("calculated_price_per_piece_from_kg") + " บาท",
            "  ราคาขายจริงต่อชิ้น / Final Selling Price per Piece: "
            + rf("unit_price") + " บาท",
        ]
    lines += [
        "  ราคารวม / Total Price: " + rf("total_price") + " บาท",
        (
            "  แพ็ก / Pack: " + n(pack_qty, 0) + " ชิ้น / pieces • "
            + rf("pack_weight_kg", 4) + " กก. / kg"
            if pack_qty > 0
            else "  แพ็ก / Pack: ยังไม่ได้กำหนด / Not Set"
        ),
        (
            "  กระสอบ / Sack: " + n(sack_qty, 0) + " ชิ้น / pieces • "
            + rf("sack_weight_kg", 4) + " กก. / kg"
            if sack_qty > 0
            else "  กระสอบ / Sack: ยังไม่ได้กำหนด / Not Set"
        ),
        "  วัตถุดิบ / Required Material: " + rf("required_kg") + " กก. / kg",
        "  สถานะควบคุม / Control Status: " + str(results.get("control_status") or ""),
        "",
        "สูตรที่บันทึก / Saved Formulas",
        "  น้ำหนัก / Weight = " + str(formulas.get("weight") or ""),
        "  ราคา / Price = " + str(formulas.get("price") or ""),
    ]
    if row["product_key"] == "cover":
        lines += [
            "",
            "พื้นที่หลังคา / Roof Area: " + rf("roof_area_cm2") + " ตร.ซม.",
            "พื้นที่ตาข่าย / Mesh Area: " + rf("mesh_area_cm2") + " ตร.ซม.",
        ]
    return {
        "title": "รายละเอียด / Details — " + str(row["quote_ref"]),
        "text": "\n".join(lines),
    }


@app.get("/api/quotations/{quote_ref:path}/form")
def api_quotation_form(quote_ref: str) -> dict[str, Any]:
    """Everything the Edit button pours back into the form (app.py:4185-4296),
    as the strings the boxes should hold - one mapper for both the web's flat
    inputs and the desktop's nested `dimensions` shape."""
    row = db.get_quotation(quote_ref)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="ไม่พบเลขอ้างอิง / Quote reference not found: " + quote_ref,
        )
    inputs = row["inputs_json"]
    formulas = row["formulas_json"]
    thickness = inputs.get("thickness", {}) or {}

    def measure(name: str, default_unit: str) -> dict[str, str]:
        m = _inputs_measure(inputs, name)
        value = float(m.get("value") or 0)
        return {"value": g(value) if value else "", "unit": str(m.get("unit") or default_unit)}

    def number(key: str, keep_zero: bool = False) -> str:
        value = float(inputs.get(key) or 0)
        return g(value) if (value or keep_zero) else ""

    width = measure("width", "ซม.")
    length = measure("length", "ซม.")
    height = measure("height", "ซม.")
    gusset = measure("gusset", "ซม.")
    sold_length = measure("sold_length", "เมตร")
    allowance = measure("bottom_allowance", "ซม.")
    thickness_value = float(thickness.get("value") or 0)
    return {
        "quote_ref": row["quote_ref"],
        "form": {
            "customer": row["customer"],
            "customer_code": row["customer_code"],
            "quote_date": str(row["quote_date"]),
            "item_description": row["item_description"],
            "product_reference": row["product_reference"],
            "product_key": row["product_key"],
            "width": width["value"],
            "width_unit": width["unit"],
            "length": length["value"],
            "length_unit": length["unit"],
            "height": height["value"],
            "gusset": gusset["value"],
            "sold_length": sold_length["value"],
            "sold_length_unit": sold_length["unit"],
            "thickness": g(thickness_value) if thickness_value else "",
            "thickness_unit": str(thickness.get("unit") or "มม."),
            "thickness_mode": "side" if thickness.get("mode") == "side" else "pair",
            "bottom_allowance": allowance["value"] or "0",
            "length_reference": str(row["length_reference"] or ""),
            "density": number("density_g_cm3") or "0.92",
            "material_price": number("material_price_per_kg") or "65",
            "deduction": number("deduction_percent") or "10",
            "apply_deduction": bool(inputs.get("apply_deduction", True)),
            "sale_basis": "kg" if _sale_is_kg(inputs.get("sale_basis")) else "piece",
            "price_per_kg": number("selling_price_per_kg_override"),
            "price_per_piece": number("selling_price_per_piece_override"),
            "order_quantity": number("order_quantity") or "1000",
            "pack_quantity": number("pack_quantity"),
            "sack_quantity": number("sack_quantity"),
            "control_min": number("control_min_g"),
            "control_max": number("control_max_g"),
            "roof_gsm": number("roof_gsm") or "120",
            "mesh_gsm": number("mesh_gsm") or "80",
            "weight_formula": str(formulas.get("weight") or ""),
            "price_formula": str(formulas.get("price") or ""),
        },
        "ref_text": (
            "กำลังแก้ไข / Editing: " + str(row["quote_ref"])
            + " (เก็บเป็นฉบับใหม่ / Save as revision)"
        ),
        "status": (
            "แก้ไขแล้วคำนวณใหม่ จากนั้นกดเก็บบันทึก / Edit, recalculate, then save — "
            + str(row["quote_ref"])
        ),
    }


# --------------------------------------------------------------------------- #
# The drawing tab beyond the picture itself: the printable page, the saved
# register with its DFA- numbers, and reopening a saved sheet
# (app.py:2269-2423). Numbers are issued ONLY on save, by one SQL statement.
# --------------------------------------------------------------------------- #


def _drawing_spec(req: DrawingRequest) -> DrawingSpec:
    return DrawingSpec(
        doc_no=req.doc_no.strip() or "— DRAFT —",
        customer=req.customer.strip(),
        title=req.title.strip(),
        shape=PRODUCT_TO_SHAPE[req.product_key],
        revision=req.revision.strip() or "A",
        date=req.date.strip(),
        part_no=req.part_no.strip() or "-",
        customer_code=req.customer_code.strip(),
        material=req.material.strip() or "POLYETHYLENE",
        color=req.color.strip() or "-",
        printing=req.printing.strip() or "-",
        width_mm=_to_mm(req.width),
        length_mm=_to_mm(req.length),
        height_mm=_to_mm(req.height),
        gusset_mm=_to_mm(req.gusset),
        thickness_mm=thickness_to_mm(req.thickness.value, req.thickness.unit),
        tol_dim_lo=req.tol_dim_lo,
        tol_dim_hi=req.tol_dim_hi,
        tol_thickness=req.tol_thickness,
        length_datum=req.length_datum,
        display_unit=req.display_unit,
        holes_count=req.holes_count,
        holes_dia=req.holes_dia.strip(),
        label_w=req.label_w,
        label_h=req.label_h,
        extra_notes=[line for line in req.extra_notes if line.strip()],
    )


@app.post("/api/drawing/html")
def api_drawing_html(req: DrawingRequest) -> dict[str, Any]:
    """The printable page the desktop's Preview & Print opens - drawing.py's
    own render_html, A4 landscape."""
    if not req.customer.strip():
        raise HTTPException(status_code=400, detail="ต้องระบุชื่อลูกค้า / Customer is required")
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="ต้องระบุชื่อแบบ / Drawing title is required")
    try:
        return {"html": render_html(_drawing_spec(req))}
    except (DrawingError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class DrawingSaveRequest(BaseModel):
    doc_no: str = ""
    drawing_date: str
    revision: str = "A"
    customer: str = ""
    customer_code: str = ""
    title: str = ""
    part_no: str = "-"
    product_key: Literal["flat", "opaque", "gusset", "roll", "cover"] = "flat"
    length_datum: str = ""
    display_unit: Literal["mm", "inch"] = "mm"
    width: Measure = Field(default_factory=Measure)
    length: Measure = Field(default_factory=Measure)
    height: Measure = Field(default_factory=Measure)
    gusset: Measure = Field(default_factory=Measure)
    # Per SIDE, as the drawing card asks for it.
    thickness: Thickness = Field(default_factory=lambda: Thickness(mode="side"))
    material: str = "POLYETHYLENE"
    color: str = "-"
    printing: str = "-"
    tol_dim_lo: float = -10.0
    tol_dim_hi: float = 10.0
    tol_thickness: float = 0.005
    holes_count: int = 0
    holes_dia: str = ""
    label_w: float = 0.0
    label_h: float = 0.0
    extra_notes: list[str] = Field(default_factory=list)


@app.post("/api/drawings")
def api_drawing_save(req: DrawingSaveRequest, request: Request) -> dict[str, Any]:
    if not req.customer.strip():
        raise HTTPException(status_code=400, detail="ต้องระบุชื่อลูกค้า / Customer is required")
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="ต้องระบุชื่อแบบ / Drawing title is required")
    try:
        record = {
            "doc_no": req.doc_no,
            "drawing_date": req.drawing_date,
            "revision": req.revision.strip() or "A",
            "customer": req.customer.strip(),
            "customer_code": req.customer_code.strip(),
            "title": req.title.strip(),
            "part_no": req.part_no.strip() or "-",
            "product_key": req.product_key,
            "length_datum": req.length_datum,
            "display_unit": req.display_unit,
            "width_mm": _to_mm(req.width),
            "length_mm": _to_mm(req.length),
            "height_mm": _to_mm(req.height),
            "gusset_mm": _to_mm(req.gusset),
            "thickness_mm": thickness_to_mm(req.thickness.value, req.thickness.unit),
            "spec": {
                "material": req.material.strip() or "POLYETHYLENE",
                "color": req.color.strip() or "-",
                "printing": req.printing.strip() or "-",
                "tol_dim_lo": req.tol_dim_lo,
                "tol_dim_hi": req.tol_dim_hi,
                "tol_thickness": req.tol_thickness,
                "holes_count": req.holes_count,
                "holes_dia": req.holes_dia.strip(),
                "label_w": req.label_w,
                "label_h": req.label_h,
                "extra_notes": [line for line in req.extra_notes if line.strip()],
            },
        }
        user = routes_auth.current_user(request.headers.get("authorization"))
        doc_no = store.save_drawing_web(record, user_id=user.get("id"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "doc_no": doc_no,
        "status": "บันทึกแล้ว เลขเอกสาร " + doc_no + " / Saved as " + doc_no,
    }


def _drawing_size_cell(row: dict[str, Any]) -> str:
    size = g(float(row["width_mm"])) + " x " + g(float(row["length_mm"]))
    if float(row["thickness_mm"] or 0) > 0:
        size += " x " + g(float(row["thickness_mm"]))
    return size


@app.get("/api/drawings")
def api_drawing_register(q: str = "", limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    rows = store.search_drawings(q.strip(), limit)
    return {
        "rows": [
            {
                "doc_no": row["doc_no"],
                "date": str(row["drawing_date"]),
                "rev": row["revision"],
                "customer": row["customer"],
                "title": row["title"],
                "size": _drawing_size_cell(row),
            }
            for row in rows
        ]
    }


@app.get("/api/drawings/{doc_no}")
def api_drawing_get(doc_no: str) -> dict[str, Any]:
    row = store.get_drawing(doc_no)
    if row is None:
        raise HTTPException(status_code=404, detail="ไม่พบแบบ / Drawing not found: " + doc_no)
    spec = row["spec_json"] or {}

    def mm(value: Any) -> str:
        number = float(value or 0)
        return g(number) if number else ""

    return {
        "doc_no": row["doc_no"],
        "form": {
            "doc_no": row["doc_no"],
            "date": str(row["drawing_date"]),
            "revision": row["revision"] or "A",
            "customer": row["customer"],
            "customer_code": row["customer_code"],
            "title": row["title"],
            "part_no": row["part_no"] or "-",
            "product_key": row["product_key"],
            "length_datum": row["length_datum"] or "opening_to_seal",
            "display_unit": row["display_unit"] or "mm",
            # Reopened in mm, as the desktop reloads them (app.py:2395-2404).
            "width": mm(row["width_mm"]),
            "length": mm(row["length_mm"]),
            "height": mm(row["height_mm"]),
            "gusset": mm(row["gusset_mm"]),
            "thickness": mm(row["thickness_mm"]),
            "material": str(spec.get("material") or "POLYETHYLENE"),
            "color": str(spec.get("color") or "-"),
            "printing": str(spec.get("printing") or "-"),
            "tol_lo": g(float(spec.get("tol_dim_lo", -10.0))),
            "tol_hi": g(float(spec.get("tol_dim_hi", 10.0))),
            "tol_thickness": g(float(spec.get("tol_thickness", 0.005))),
            "holes_count": g(float(spec.get("holes_count", 0))),
            "holes_dia": str(spec.get("holes_dia") or ""),
            "label_w": g(float(spec.get("label_w", 0))),
            "label_h": g(float(spec.get("label_h", 0))),
            "extra_notes": "\n".join(spec.get("extra_notes") or []),
        },
    }


# --------------------------------------------------------------------------- #
# The planning tab: source picker, weight comparison, shop-floor work orders.
# Mirrors app.py load_planning_source / compare_planning_weight /
# print_work_order (1237-1415). The browser holds none of these words or sums.
# --------------------------------------------------------------------------- #


def as_float_thai(text: str, label: str, *, allow_zero: bool = True) -> float:
    """app.py as_float (96-117): the same three refusals, word for word."""
    raw = str(text).replace(",", "").strip()
    if not raw:
        value = 0.0
    else:
        try:
            value = float(raw)
        except ValueError:
            raise ValueError(label + "ต้องเป็นตัวเลข") from None
    if value < 0:
        raise ValueError(label + "ต้องไม่ติดลบ")
    if not allow_zero and value <= 0:
        raise ValueError(label + "ต้องมากกว่า 0")
    return value


def _source_line(row: dict[str, Any]) -> str:
    """app.py _planning_source_line (1214-1218)."""
    return " | ".join(
        [
            str(row["quote_ref"]),
            str(row.get("customer_code") or ""),
            str(row.get("customer") or ""),
            str(row.get("item_description") or row.get("product_label") or ""),
        ]
    )


@app.get("/api/planning/sources")
def api_planning_sources(q: str = "", limit: int = Query(default=12, ge=1, le=50)) -> dict[str, Any]:
    rows = db.find_quotations(q.strip(), limit)
    return {"rows": [{**row, "line": _source_line(row)} for row in rows]}


@app.get("/api/planning/source")
def api_planning_source(selected: str = "") -> dict[str, Any]:
    """Resolve one picked/typed/pasted line into the planning prefill.

    Three ways in, because all three happen (app.py:1246-1254): picked from the
    list, typed as a bare REF, or pasted whole - and when the direct reference
    misses, a single search match is taken as the answer.
    """
    chosen = selected.strip()
    if not chosen:
        raise HTTPException(
            status_code=400,
            detail="กรุณาเลือกใบคำนวณราคาที่บันทึกแล้ว / Please select a saved pricing record",
        )
    quote_ref = chosen.split(" | ", 1)[0].strip()
    quote = db.get_quotation(quote_ref)
    if not quote:
        matches = db.find_quotations(chosen, limit=2)
        if len(matches) == 1:
            quote_ref = matches[0]["quote_ref"]
            quote = db.get_quotation(quote_ref)
    if not quote:
        raise HTTPException(
            status_code=404,
            detail="ไม่พบใบคำนวณราคาที่ตรงกับ / No saved pricing record matches:\n" + chosen,
        )
    inputs = quote["inputs_json"]
    results = quote["results_json"]
    normalized = inputs.get("normalized", {})
    pack_quantity = inputs.get("pack_quantity", 0)
    return {
        "quote_ref": quote["quote_ref"],
        "line": _source_line(quote),
        # The prefill strings, formatted the desktop's way (1266-1279): {:g}
        # for the sizes, the thickness raw as typed, the package with its unit.
        "width": format(float(normalized.get("width_cm", 0)), "g"),
        "length": format(
            float(results.get("material_length_cm", normalized.get("length_cm", 0))), "g"
        ),
        "thickness": str(inputs.get("thickness", {}).get("value", "")),
        "gusset": format(float(normalized.get("gusset_cm", 0)), "g"),
        "package": (format(float(pack_quantity), "g") + " ชิ้น/แพ็ก") if pack_quantity else "",
        "quantity": format(float(inputs.get("order_quantity", 0)), "g"),
        "summary": (
            str(quote["quote_ref"]) + " • " + str(quote["customer_code"]) + " • "
            + str(quote["customer"]) + " • "
            + str(quote["item_description"] or quote["product_label"]) + " • "
            + str(quote["size_text"])
        ),
        "status": (
            "รับข้อมูลใบราคา " + str(quote["quote_ref"])
            + " เข้าหน้าวางแผนแล้ว / Pricing data loaded into Planning"
        ),
    }


class PlanningCompareRequest(BaseModel):
    quote_ref: str
    quantity: str = ""
    width: str = ""
    length: str = ""
    thickness: str = ""
    gusset: str = ""


@app.post("/api/planning/compare")
def api_planning_compare(req: PlanningCompareRequest) -> dict[str, Any]:
    quote = db.get_quotation(req.quote_ref.strip())
    if not quote:
        raise HTTPException(
            status_code=400,
            detail="กรุณารับข้อมูลจากใบราคาก่อน / Load a pricing record first",
        )
    try:
        quantity = as_float_thai(req.quantity, "จำนวนใบ", allow_zero=False)
        new_width = as_float_thai(req.width, "ความกว้าง", allow_zero=False)
        new_length = as_float_thai(req.length, "ความยาว", allow_zero=False)
        new_thickness = as_float_thai(req.thickness, "ความหนา", allow_zero=False)
        new_gusset = as_float_thai(req.gusset, "พับข้าง")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    inputs = quote["inputs_json"]
    results = quote["results_json"]
    normalized = inputs.get("normalized", {})
    ref_width = float(normalized.get("width_cm", 0) or 0)
    ref_length = float(results.get("material_length_cm", normalized.get("length_cm", 0)) or 0)
    ref_thickness = float(inputs.get("thickness", {}).get("value", 0) or 0)
    ref_gusset = float(normalized.get("gusset_cm", 0) or 0)
    if min(ref_width, ref_length, ref_thickness) <= 0:
        raise HTTPException(
            status_code=400,
            detail="ใบราคาไม่มีข้อมูลอ้างอิงครบ / Pricing record lacks reference dimensions",
        )
    ratio = (
        ((new_width + new_gusset) / (ref_width + ref_gusset))
        * (new_length / ref_length)
        * (new_thickness / ref_thickness)
    )
    ref_grams = float(quote["grams_per_item"])
    new_grams = ref_grams * ratio
    ref_kg = ref_grams * quantity / 1000
    new_kg = new_grams * quantity / 1000
    return {
        "line": (
            format(quantity, ",.0f") + " ใบ / pcs • อ้างอิง " + format(ref_kg, ",.3f")
            + " กก. (" + format(ref_grams, ",.3f") + " g/ใบ) » ใหม่ "
            + format(new_kg, ",.3f") + " กก. (" + format(new_grams, ",.3f")
            + " g/ใบ) • ต่าง " + format(new_kg - ref_kg, "+,.3f") + " กก."
        )
    }


class WorkOrderRequest(BaseModel):
    department: Literal["blown", "cutting"] = "blown"
    source: str = ""
    width: str = ""
    length: str = ""
    thickness: str = ""
    gusset: str = ""
    package: str = ""
    notes: str = ""


@app.post("/api/work-orders/html")
def api_work_order_html(req: WorkOrderRequest) -> dict[str, Any]:
    """The shop-floor sheet, exactly as print_work_order writes it
    (app.py:1384-1415) - same table, same colours, same print button."""
    import html as html_mod

    label = (
        "แผนกเป่า / Blown-film Department"
        if req.department == "blown"
        else "แผนกตัดถุง / Bag-cutting Department"
    )
    rows = "".join(
        "<tr><th>" + html_mod.escape(name) + "</th><td>"
        + html_mod.escape(value or "—") + "</td></tr>"
        for name, value in (
            ("ต้นทางใบราคา / Pricing Source", req.source.strip()),
            ("ความกว้างผลิต / Production Width", req.width.strip()),
            ("ความยาวผลิต / Production Length", req.length.strip()),
            ("ความหนาผลิต / Production Thickness", req.thickness.strip()),
            ("พับข้าง / Gusset", req.gusset.strip()),
            ("แพ็กเกจ / Packaging", req.package.strip()),
            ("รายละเอียด / Notes", req.notes.strip()),
        )
    )
    page = (
        "<!doctype html><meta charset='utf-8'><title>Work Order</title>"
        "<style>body{font-family:Arial,sans-serif;margin:28px}table{width:100%;border-collapse:collapse}"
        "th,td{border:1px solid #999;padding:9px;text-align:left}th{width:34%;background:#eef4f8}"
        "@media print{button{display:none}}</style>"
        "<h1>" + html_mod.escape(label) + "</h1><table>" + rows + "</table>"
        "<p><button onclick='window.print()'>พิมพ์ / Print</button></p>"
    )
    return {"html": page}


# --------------------------------------------------------------------------- #
# The print summary: the A4 sheet _build_print_html writes (app.py:3371-3517),
# byte for byte - same CSS values, same row labels, same auto window.print().
# Built HERE so the browser holds none of its Thai and none of its arithmetic.
# --------------------------------------------------------------------------- #


class PrintRequest(BaseModel):
    calc: CalcRequest
    quote_date: str = ""
    customer: str = ""
    customer_code: str = ""
    item_description: str = ""
    product_reference: str = ""
    # What the header's top-right says: a saved reference, or nothing - the
    # sheet then prints the desktop's own "ยังไม่บันทึก / Unsaved".
    quote_ref: str = ""
    # Set when the form was loaded from a saved record: the sheet then carries
    # the desktop's own "แก้ไขจาก / Revised From" identity row (app.py:3412-3414).
    revised_from_ref: str = ""


def _print_rows(rows: list[tuple[str, Any]]) -> str:
    import html as html_mod

    def e(value: Any) -> str:
        text = "" if value is None else str(value)
        return html_mod.escape(text) if text.strip() else "—"

    return "".join(
        "<tr><th>" + html_mod.escape(name) + "</th><td>" + e(value) + "</td></tr>"
        for name, value in rows
    )


def build_print_html(req: PrintRequest, out: dict[str, Any]) -> str:
    import html as html_mod
    from datetime import datetime
    from zoneinfo import ZoneInfo

    calc = req.calc
    res = out["raw"]
    sale_by_kg = calc.sale_basis == "kg"
    sale_label = "ขายเป็นกิโลกรัม / Sell by kg" if sale_by_kg else "ขายเป็นชิ้น / Sell by piece"
    not_set = "ยังไม่ได้กำหนด / Not Set"

    if calc.product_key == "cover":
        thickness_text = "ไม่ใช้ / Not applicable"
    else:
        mode_text = "ต่อคู่ / Per Pair" if calc.thickness.mode == "pair" else "ต่อด้าน / Per Side"
        thickness_text = g(calc.thickness.value) + " " + calc.thickness.unit + " • " + mode_text

    identity = [
        ("เลขอ้างอิง / Quote Ref", req.quote_ref.strip() or "ยังไม่บันทึก / Unsaved"),
        ("วันที่ / Date", req.quote_date),
        ("รหัสลูกค้า / Customer Code", req.customer_code),
        ("ชื่อลูกค้า/บริษัท / Customer/Company", req.customer.strip() or "—"),
        ("รายการสินค้า / Item", req.item_description),
        ("รหัสสินค้า / Part Number", req.product_reference),
        ("ประเภทสินค้า / Product Type", PRODUCTS[calc.product_key]),
        ("ขนาด / Size", out["display"]["size_text"]),
        ("ความหนา / Thickness", thickness_text),
        ("หน่วยขาย / Selling Unit", sale_label),
    ]
    if req.revised_from_ref.strip():
        identity.append(("แก้ไขจาก / Revised From", req.revised_from_ref.strip()))

    deduction = g(calc.deduction_percent)
    adjusted_suffix = " (เปิด / ON)" if calc.apply_deduction else " (ปิด / OFF)"
    results: list[tuple[str, Any]] = [
        ("น้ำหนักต่อชิ้น / Grams per item", n(res.grams_per_item) + " กรัม / g"),
        ("จำนวนมาตรฐานต่อกก. / Standard items per kg", n(res.items_per_kg, 2)),
        (
            "จำนวนหลังหัก " + deduction + "% / Adjusted items per kg",
            n(res.production_items_per_kg, 2) + adjusted_suffix,
        ),
        ("ฐาน/สูตรคำนวณราคา / Price Basis or Formula", out["price_basis"]),
    ]
    # Only when there is one - the desktop adds this row conditionally
    # (app.py:3427-3430), and a paper-book row has no derivation to show.
    if str(out["human_summary"] or "").strip():
        results.append(("ลำดับตรวจสอบสูตร / Human-readable Verification", out["human_summary"]))
    if sale_by_kg:
        results.append(
            ("ราคาขายจริงต่อกิโลกรัม / Final selling price per kg", n(res.selling_price_per_kg) + " บาท")
        )
    else:
        results += [
            ("ราคาฐานต่อกิโลกรัม / Price basis per kg", n(calc.selling_price_per_kg_override) + " บาท"),
            ("ราคาต่อชิ้นที่คำนวณได้ / Calculated price per piece", n(res.calculated_price_per_piece_from_kg) + " บาท"),
            ("ราคาขายจริงต่อชิ้น / Final selling price per piece", n(res.unit_price) + " บาท"),
        ]
    results += [
        (
            "บรรจุต่อแพ็ก / Pieces per pack",
            (n(calc.pack_quantity, 0) + " ชิ้น • " + n(res.pack_weight_kg, 4) + " กก.")
            if calc.pack_quantity > 0
            else not_set,
        ),
        (
            "บรรจุต่อกระสอบ / Pieces per sack",
            (n(calc.sack_quantity, 0) + " ชิ้น • " + n(res.sack_weight_kg, 4) + " กก.")
            if calc.sack_quantity > 0
            else not_set,
        ),
    ]

    formulas = [
        ("สูตรน้ำหนัก / Weight Formula", out["formulas"]["weight"]),
        ("สูตรราคา / Price Formula", out["formulas"]["price"]),
    ]

    # Bangkok on purpose: the container runs UTC, and a bare now() would stamp
    # the sheet seven hours behind the person printing it (tech-stack.md 3).
    stamp = datetime.now(ZoneInfo("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M")
    title = req.quote_ref.strip() or "ยังไม่บันทึก / Unsaved"

    return (
        "<!doctype html><html lang=\"th\"><head><meta charset=\"utf-8\">"
        "<title>" + html_mod.escape(title) + "</title><style>"
        "@page { size: A4; margin: 14mm; }"
        "body{color:#172b3a;font:14px/1.45 \"Leelawadee UI\", \"Tahoma\", sans-serif;background:#eef3f7;margin:0}"
        ".sheet{width:210mm;min-height:276mm;margin:12px auto;padding:14mm;background:#fff;box-shadow:0 2px 14px #8aa0b333}"
        "h1{color:#16324f;font-size:24px;margin:0}"
        ".subtitle{color:#516273;margin:4px 0 18px}"
        "h2{color:#fff;background:#1f6aa5;font-size:16px;padding:7px 10px;margin:18px 0 7px}"
        "table{width:100%;border-collapse:collapse}"
        "th,td{border:1px solid #9fb1c1;padding:7px 9px;text-align:left;vertical-align:top}"
        "th{width:44%;background:#f1f6fa;font-weight:700}"
        ".price th,.price td{border-color:#6f91ac}"
        ".note{margin-top:12px;padding:9px;border:1px solid #c7d3dd;background:#f8fafc;color:#445667}"
        ".actions{position:sticky;top:0;padding:10px;text-align:center;background:#16324f}"
        "button{padding:9px 22px;border:0;border-radius:5px;background:#167d5a;color:#fff;font-weight:700;cursor:pointer}"
        "@media print{body{background:#fff}.sheet{margin:0;box-shadow:none}.no-print{display:none !important}}"
        "</style></head>"
        "<body onload=\"setTimeout(function(){ window.print(); }, 350)\">"
        "<div class=\"actions no-print\"><button onclick=\"window.print()\">พิมพ์ / Print</button></div>"
        "<div class=\"sheet\">"
        "<h1>สรุปการคำนวณและใบเสนอราคา / Calculation &amp; Quotation Summary</h1>"
        "<p class=\"subtitle\">จัดทำเมื่อ / Generated: " + stamp + "</p>"
        "<h2>ข้อมูลลูกค้าและสินค้า / Customer &amp; Product</h2>"
        "<table>" + _print_rows(identity) + "</table>"
        "<h2>ผลคำนวณและราคา / Calculation &amp; Pricing</h2>"
        "<table class=\"price\">" + _print_rows(results) + "</table>"
        "<p class=\"note\">น้ำหนักต่อแพ็ก (กก.) = กรัมต่อชิ้น × ชิ้นในแพ็ก ÷ 1,000 / Pack Weight (kg) = grams per item × pieces per pack ÷ 1,000</p>"
        "<h2>สูตรที่บันทึก / Saved Formulas</h2>"
        "<table>" + _print_rows(formulas) + "</table>"
        "</div></body></html>"
    )


@app.post("/api/print/html")
def api_print_html(req: PrintRequest) -> dict[str, Any]:
    try:
        out = run_calculation(req.calc)
    except (ValueError, FormulaError, ZeroDivisionError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"html": build_print_html(req, out)}


@app.get("/api/quotations/{quote_ref:path}/print")
def api_print_saved(quote_ref: str) -> dict[str, Any]:
    """Reprint a saved record from its STORED figures - never a recompute.

    LAW P5: a saved sheet is a snapshot, and reprinting it must show the
    numbers that were agreed, not the numbers today's parameters would give.
    It is also the only way a paper-book row can print at all: those rows
    carry no inputs to replay, only the figures the book recorded.
    """
    from types import SimpleNamespace

    row = db.get_quotation(quote_ref)
    if row is None:
        raise HTTPException(status_code=404, detail="ไม่พบใบเสนอราคา / Quotation not found")
    inputs = row["inputs_json"] or {}
    results = row["results_json"] or {}
    formulas = row["formulas_json"] or {}

    def rn(key: str, fallback: Any = 0) -> float:
        try:
            return float(results.get(key) or fallback or 0)
        except (TypeError, ValueError):
            return 0.0

    thickness = inputs.get("thickness", {}) or {}
    req = PrintRequest(
        calc=CalcRequest(
            product_key=row["product_key"],
            thickness=Thickness(
                value=float(thickness.get("value") or 0),
                unit=str(thickness.get("unit") or "มม."),
                mode="side" if thickness.get("mode") == "side" else "pair",
            ),
            sale_basis="kg" if _sale_is_kg(inputs.get("sale_basis")) else "piece",
            deduction_percent=float(inputs.get("deduction_percent") or 0),
            apply_deduction=bool(inputs.get("apply_deduction", True)),
            pack_quantity=float(row["pack_quantity"] or 0),
            sack_quantity=float(row["sack_quantity"] or 0),
            selling_price_per_kg_override=float(
                inputs.get("selling_price_per_kg_override") or results.get("selling_price_per_kg") or 0
            ),
        ),
        quote_date=str(row["quote_date"]),
        customer=row["customer"],
        customer_code=row["customer_code"],
        item_description=row["item_description"],
        product_reference=row["product_reference"],
        quote_ref=row["quote_ref"],
        revised_from_ref=str(row["revised_from_ref"] or ""),
    )
    out = {
        "raw": SimpleNamespace(
            grams_per_item=float(row["grams_per_item"] or 0) or rn("grams_per_item"),
            items_per_kg=rn("items_per_kg"),
            production_items_per_kg=rn("production_items_per_kg"),
            selling_price_per_kg=rn("selling_price_per_kg"),
            calculated_price_per_piece_from_kg=rn("calculated_price_per_piece_from_kg"),
            unit_price=float(row["unit_price"] or 0) or rn("unit_price"),
            pack_weight_kg=float(row["pack_weight_kg"] or 0) or rn("pack_weight_kg"),
            sack_weight_kg=float(row["sack_weight_kg"] or 0) or rn("sack_weight_kg"),
        ),
        "display": {"size_text": row["size_text"]},
        "price_basis": str(
            inputs.get("price_basis") or results.get("price_basis_summary") or ""
        ),
        "human_summary": str(
            inputs.get("human_summary") or results.get("verification_summary") or ""
        ),
        "formulas": {
            "weight": str(formulas.get("weight") or ""),
            "price": str(formulas.get("price") or ""),
        },
    }
    return {"html": build_print_html(req, out)}


# The greedy pair, LAST on purpose (see the note beside /api/quotations above):
# {quote_ref:path} is what lets "2569/09-01" - a reference with a slash, held
# by a customer since before this system existed - reach its own row.
@app.get("/api/quotations/{quote_ref:path}")
def api_get(quote_ref: str) -> dict[str, Any]:
    row = db.get_quotation(quote_ref)
    if row is None:
        raise HTTPException(status_code=404, detail="ไม่พบใบเสนอราคา / Quotation not found")
    return row


@app.delete("/api/quotations/{quote_ref:path}")
def api_delete(quote_ref: str) -> dict[str, Any]:
    if not db.delete_quotation(quote_ref):
        raise HTTPException(status_code=404, detail="ไม่พบใบเสนอราคา / Quotation not found")
    return {"deleted": quote_ref}


# --------------------------------------------------------------------------- #
# The screen
# --------------------------------------------------------------------------- #

# MOUNTED LAST, AT THE ROOT - AND "LAST" MEANS THE LAST LINE OF THIS FILE.
#
# Put after include_router but ABOVE the route definitions, which is where
# it first went, this swallowed every one of them: /api/health, /api/meta,
# /api/calculate and the whole quotations set answered 404 while /api/version
# kept working, because that one lives on a router registered earlier. A mount
# on "/" matches every path there is, and Starlette takes the first match.
#
# Last, because a mount swallows every path below it and the routers above must
# get their say first: /api, /auth, /sync, /download and /api/version are all
# registered before this line and all still answer.
#
# At the root because the program IS the site now - the .exe is retired and the
# installer page has moved to /download, the address that describes it. The
# machines still running a copy keep syncing through the same /sync routes, so
# nothing anybody has typed is stranded by the move.
#
# html=True serves index.html for "/" and for anything under it, which is what
# a single-page app needs when somebody reloads.
#
# Absent in a checkout that has not built the screen (running the API straight
# from the source tree), and that is not an error: the API is complete without
# it, and a missing folder must not stop the .exe's own server from starting.
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
if WEB_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
