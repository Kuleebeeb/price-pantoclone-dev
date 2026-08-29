"""Product geometry, unit conversion, and pricing calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from formula_engine import FormulaError, evaluate_formula


PRODUCTS = {
    "flat": "ถุงพลาสติกเปิดปากตรง (Plastic Bag)",
    "opaque": "แผ่นพลาสติก (Plastic Sheet)",
    "gusset": "ถุงพับข้าง (Gusset Bag)",
    "roll": "ม้วนพลาสติก (Plastic Roll)",
    "cover": "ถุงคลุมสินค้า (Product Cover)",
}

LENGTH_REFERENCES = {
    "opening_to_seal": "ปากถึงแนวซีล / Opening to Seal",
    "opening_to_bottom": "ปากถึงก้นถุง / Opening to Bottom",
}

DIMENSION_FACTORS_TO_CM = {
    "นิ้ว": 2.54,
    "ซม.": 1.0,
    "มม.": 0.1,
    "เมตร": 100.0,
}

THICKNESS_FACTORS_TO_MM = {
    "มม.": 1.0,
    "ซม.": 10.0,
    "นิ้ว": 25.4,
    "ไมครอน": 0.001,
}

DEFAULT_WEIGHT_FORMULAS = {
    "flat": "width_cm * material_length_cm * 2 * (thickness_side_mm / 10) * density_g_cm3",
    "gusset": "(width_cm + gusset_cm) * material_length_cm * 2 * (thickness_side_mm / 10) * density_g_cm3",
    "roll": "width_cm * sold_length_m * 100 * 2 * (thickness_side_mm / 10) * density_g_cm3",
    "opaque": "width_cm * length_cm * 2 * (thickness_side_mm / 10) * density_g_cm3",
    "cover": "roof_area_m2 * roof_gsm + mesh_area_m2 * mesh_gsm",
}

DEFAULT_PRICE_FORMULA = "(grams_per_item / 1000) * material_price_per_kg * (1 + markup_percent / 100)"

FORMULA_VARIABLES = {
    "width_cm": "ความกว้าง / Width (cm)",
    "length_cm": "ความยาวตามสเปก / Specification Length (cm)",
    "material_length_cm": "ความยาววัสดุคำนวณ / Material Length (cm)",
    "bottom_allowance_cm": "ค่าบวกก้นถุง / Bottom Allowance (cm)",
    "height_cm": "ความสูง / Height (cm)",
    "gusset_cm": "ขนาดพับข้าง / Gusset (cm)",
    "sold_length_m": "ความยาวโรล / Roll Length (m)",
    "thickness_input_mm": "ความหนาที่กรอก / Input Thickness (mm)",
    "thickness_side_mm": "ความหนาต่อด้าน / Per-side Thickness (mm)",
    "thickness_pair_mm": "ความหนาต่อคู่ / Pair Thickness (mm)",
    "density_g_cm3": "ความหนาแน่น / Density (g/cm³)",
    "roof_area_cm2": "พื้นที่หลังคา / Roof Area (cm²)",
    "mesh_area_cm2": "พื้นที่ตาข่าย / Mesh Area (cm²)",
    "roof_area_m2": "พื้นที่หลังคา / Roof Area (m²)",
    "mesh_area_m2": "พื้นที่ตาข่าย / Mesh Area (m²)",
    "roof_gsm": "น้ำหนักวัสดุหลังคา / Roof GSM",
    "mesh_gsm": "น้ำหนักตาข่าย / Mesh GSM",
    "grams_per_item": "น้ำหนักต่อชิ้น / Weight per Item (g)",
    "material_price_per_kg": "ราคาวัตถุดิบ / Material Price per kg",
    "markup_percent": "เปอร์เซ็นต์บวกเพิ่ม / Markup (%)",
    "pack_quantity": "จำนวนต่อแพ็ก / Pieces per Pack",
    "deduction_percent": "เปอร์เซ็นต์หักเผื่อผลิต / Production Deduction (%)",
}


def to_cm(value: float, unit: str) -> float:
    try:
        return value * DIMENSION_FACTORS_TO_CM[unit]
    except KeyError as exc:
        raise ValueError(f"หน่วยระยะไม่รองรับ: {unit}") from exc


def thickness_to_mm(value: float, unit: str) -> float:
    try:
        return value * THICKNESS_FACTORS_TO_MM[unit]
    except KeyError as exc:
        raise ValueError(f"หน่วยความหนาไม่รองรับ: {unit}") from exc


@dataclass
class CalculationResult:
    variables: dict[str, float]
    grams_per_item: float
    items_per_kg: float
    production_items_per_kg: float
    unit_price: float
    selling_price_per_kg: float
    calculated_price_per_piece_from_kg: float
    pack_weight_kg: float
    sack_weight_kg: float
    total_price: float
    required_kg: float
    pack_count: float
    control_status: str
    roof_area_cm2: float
    mesh_area_cm2: float
    material_length_cm: float


def calculate(
    *,
    product_key: str,
    width_cm: float,
    length_cm: float,
    height_cm: float,
    gusset_cm: float,
    sold_length_m: float,
    bottom_allowance_cm: float,
    thickness_input_mm: float,
    thickness_mode: str,
    density_g_cm3: float,
    roof_gsm: float,
    mesh_gsm: float,
    material_price_per_kg: float,
    markup_percent: float,
    deduction_percent: float,
    pack_quantity: float,
    order_quantity: float,
    control_min_g: float,
    control_max_g: float,
    weight_formula: str,
    price_formula: str,
    sack_quantity: float = 0,
    apply_deduction: bool = True,
    sell_by_kg: bool = True,
    selling_price_per_piece_override: float = 0,
    selling_price_per_kg_override: float = 0,
) -> CalculationResult:
    if product_key not in PRODUCTS:
        raise ValueError("ประเภทสินค้าไม่ถูกต้อง")
    if thickness_mode not in {"side", "pair"}:
        raise ValueError("รูปแบบความหนาไม่ถูกต้อง")
    if density_g_cm3 <= 0:
        raise ValueError("ความหนาแน่นต้องมากกว่า 0")
    if material_price_per_kg < 0 or markup_percent < -100:
        raise ValueError("ราคา/เปอร์เซ็นต์บวกเพิ่มไม่ถูกต้อง")
    if not 0 <= deduction_percent < 100:
        raise ValueError("เปอร์เซ็นต์หักต้องอยู่ระหว่าง 0 ถึงน้อยกว่า 100")
    if pack_quantity < 0:
        raise ValueError("จำนวนต่อแพ็กต้องไม่ติดลบ")
    if sack_quantity < 0:
        raise ValueError("จำนวนต่อกระสอบต้องไม่ติดลบ")
    if order_quantity < 0:
        raise ValueError("จำนวนสั่งผลิตต้องไม่ติดลบ")
    if selling_price_per_piece_override < 0 or selling_price_per_kg_override < 0:
        raise ValueError("ราคาขายต้องไม่ติดลบ")
    if bottom_allowance_cm < 0:
        raise ValueError("ค่าบวกก้นถุงต้องไม่ติดลบ")

    thickness_side_mm = thickness_input_mm if thickness_mode == "side" else thickness_input_mm / 2
    thickness_pair_mm = thickness_side_mm * 2

    # Quoted/spec length remains untouched. Only these two bag forms add the editable
    # bottom allowance to the material length used by the default weight formula.
    material_length_cm = (
        length_cm + bottom_allowance_cm if product_key in {"flat", "gusset"} else length_cm
    )

    # These allowances belong exclusively to the hand-sewn bag cover.
    roof_area_cm2 = (width_cm + 1) * (length_cm + 1) if product_key == "cover" else 0.0
    mesh_area_cm2 = (
        (((width_cm + length_cm) * 2) + 4) * (height_cm + 1)
        if product_key == "cover"
        else 0.0
    )

    variables = {
        "width_cm": width_cm,
        "length_cm": length_cm,
        "material_length_cm": material_length_cm,
        "bottom_allowance_cm": bottom_allowance_cm,
        "height_cm": height_cm,
        "gusset_cm": gusset_cm,
        "sold_length_m": sold_length_m,
        "thickness_input_mm": thickness_input_mm,
        "thickness_side_mm": thickness_side_mm,
        "thickness_pair_mm": thickness_pair_mm,
        "density_g_cm3": density_g_cm3,
        "roof_area_cm2": roof_area_cm2,
        "mesh_area_cm2": mesh_area_cm2,
        "roof_area_m2": roof_area_cm2 / 10_000,
        "mesh_area_m2": mesh_area_cm2 / 10_000,
        "roof_gsm": roof_gsm,
        "mesh_gsm": mesh_gsm,
        "material_price_per_kg": material_price_per_kg,
        "markup_percent": markup_percent,
        "pack_quantity": pack_quantity,
        "sack_quantity": sack_quantity,
        "deduction_percent": deduction_percent,
    }

    grams = evaluate_formula(weight_formula, variables)
    if grams <= 0:
        raise FormulaError("สูตรน้ำหนักต้องให้ผลมากกว่า 0 กรัม")
    variables["grams_per_item"] = grams
    suggested_unit_price = evaluate_formula(price_formula, variables)
    if suggested_unit_price < 0:
        raise FormulaError("สูตรราคาต้องไม่ให้ผลติดลบ")

    items_per_kg = 1000 / grams
    production_items_per_kg = (
        items_per_kg * (1 - deduction_percent / 100) if apply_deduction else items_per_kg
    )
    calculated_price_per_piece_from_kg = (
        selling_price_per_kg_override / production_items_per_kg
        if selling_price_per_kg_override > 0
        else suggested_unit_price
    )
    if not sell_by_kg and selling_price_per_piece_override > 0:
        unit_price = selling_price_per_piece_override
        selling_price_per_kg = unit_price * production_items_per_kg
    elif selling_price_per_kg_override > 0:
        selling_price_per_kg = selling_price_per_kg_override
        unit_price = selling_price_per_kg / production_items_per_kg
    else:
        unit_price = suggested_unit_price
        selling_price_per_kg = unit_price * production_items_per_kg
    pack_weight_kg = grams * pack_quantity / 1000
    sack_weight_kg = grams * sack_quantity / 1000
    total_price = unit_price * order_quantity
    required_kg = order_quantity / production_items_per_kg if production_items_per_kg else 0
    pack_count = order_quantity / pack_quantity if pack_quantity else 0

    if control_min_g > 0 or control_max_g > 0:
        if control_min_g > 0 and grams < control_min_g:
            control_status = "ต่ำกว่าช่วง / Below Range"
        elif control_max_g > 0 and grams > control_max_g:
            control_status = "สูงกว่าช่วง / Above Range"
        else:
            control_status = "อยู่ในช่วง / Within Range"
    else:
        control_status = "ยังไม่กำหนด / Not Set"

    return CalculationResult(
        variables=variables,
        grams_per_item=grams,
        items_per_kg=items_per_kg,
        production_items_per_kg=production_items_per_kg,
        unit_price=unit_price,
        selling_price_per_kg=selling_price_per_kg,
        calculated_price_per_piece_from_kg=calculated_price_per_piece_from_kg,
        pack_weight_kg=pack_weight_kg,
        sack_weight_kg=sack_weight_kg,
        total_price=total_price,
        required_kg=required_kg,
        pack_count=pack_count,
        control_status=control_status,
        roof_area_cm2=roof_area_cm2,
        mesh_area_cm2=mesh_area_cm2,
        material_length_cm=material_length_cm,
    )


def require_positive_dimensions(product_key: str, values: dict[str, float]) -> None:
    required = {
        "flat": ("width_cm", "length_cm", "thickness_input_mm"),
        "gusset": ("width_cm", "length_cm", "gusset_cm", "thickness_input_mm"),
        "roll": ("width_cm", "sold_length_m", "thickness_input_mm"),
        "opaque": ("width_cm", "length_cm", "thickness_input_mm"),
        "cover": ("width_cm", "length_cm", "height_cm"),
    }[product_key]
    labels = {
        "width_cm": "ความกว้าง",
        "length_cm": "ความยาว",
        "height_cm": "ความสูง",
        "gusset_cm": "ขนาดพับข้าง",
        "sold_length_m": "ความยาวม้วน",
        "thickness_input_mm": "ความหนา",
    }
    for name in required:
        if values.get(name, 0) <= 0:
            raise ValueError(f"{labels[name]}ต้องมากกว่า 0")


def size_description(product_key: str, dimensions: dict[str, dict[str, Any]]) -> str:
    def show(name: str) -> str:
        item = dimensions[name]
        value = f"{item['value']:g}"
        return f"{value} {item['unit']}"

    if product_key in {"flat", "opaque"}:
        return f"กว้าง/Width {show('width')} × ยาว/Length {show('length')}"
    if product_key == "gusset":
        return f"กว้าง/Width {show('width')} × ยาว/Length {show('length')} × พับข้าง/Gusset {show('gusset')}"
    if product_key == "roll":
        return f"กว้าง/Width {show('width')} × ความยาวโรล/Roll Length {show('sold_length')}"
    return f"กว้าง/Width {show('width')} × ยาว/Length {show('length')} × สูง/Height {show('height')}"
