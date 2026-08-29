"""Parity: the web API must return the desktop app's numbers, to the last decimal.

The reference side of every assertion re-walks the path app.py takes - the same
unit conversions from _collect_inputs, the same markup derivation from
_auto_update_markup, the same calculate() call from calculate_now - and calls the
SAME core module. If this file goes red, the boundary code in api/main.py drifted;
the formulas themselves cannot drift, they are one shared copy.

Run: .venv/Scripts/python.exe tests/test_parity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "api"))

from calculator import (  # noqa: E402
    DEFAULT_PRICE_FORMULA,
    DEFAULT_WEIGHT_FORMULAS,
    calculate,
    require_positive_dimensions,
    thickness_to_mm,
    to_cm,
)
from main import CalcRequest, run_calculation  # noqa: E402


def reference(case: dict) -> object:
    """What the Windows program computes, reached the way app.py reaches it."""
    dims = case["dims"]
    key = case["product_key"]
    is_bag = key in {"flat", "gusset"}

    normalized = {
        "width_cm": to_cm(*dims.get("width", (0.0, "ซม."))),
        "length_cm": to_cm(*dims.get("length", (0.0, "ซม."))),
        "height_cm": to_cm(*dims.get("height", (0.0, "ซม."))),
        "gusset_cm": to_cm(*dims.get("gusset", (0.0, "ซม."))),
        "sold_length_m": to_cm(*dims.get("sold_length", (0.0, "เมตร"))) / 100,
        "thickness_input_mm": thickness_to_mm(*case.get("thickness", (0.0, "มม."))),
        "bottom_allowance_cm": (
            to_cm(*case.get("bottom_allowance", (1.0, "ซม."))) if is_bag else 0.0
        ),
    }
    require_positive_dimensions(key, normalized)

    # app.py:1817 - markup is derived from the two price inputs, never typed.
    material = case.get("material_price_per_kg", 65.0)
    basis = case.get("selling_price_per_kg_override", 0.0)
    markup = ((basis / material) - 1) * 100 if material > 0 and basis > 0 else 0.0

    return calculate(
        product_key=key,
        width_cm=normalized["width_cm"],
        length_cm=normalized["length_cm"],
        height_cm=normalized["height_cm"],
        gusset_cm=normalized["gusset_cm"],
        sold_length_m=normalized["sold_length_m"],
        bottom_allowance_cm=normalized["bottom_allowance_cm"],
        thickness_input_mm=normalized["thickness_input_mm"],
        thickness_mode=case.get("thickness_mode", "pair"),
        density_g_cm3=case.get("density_g_cm3", 0.92),
        roof_gsm=case.get("roof_gsm", 120.0),
        mesh_gsm=case.get("mesh_gsm", 80.0),
        material_price_per_kg=material,
        markup_percent=markup,
        deduction_percent=case.get("deduction_percent", 10.0),
        pack_quantity=case.get("pack_quantity", 0.0),
        sack_quantity=case.get("sack_quantity", 0.0),
        apply_deduction=case.get("apply_deduction", True),
        sell_by_kg=case.get("sale_basis", "kg") == "kg",
        selling_price_per_piece_override=case.get("selling_price_per_piece_override", 0.0),
        selling_price_per_kg_override=basis,
        order_quantity=case.get("order_quantity", 1000.0),
        control_min_g=case.get("control_min_g", 0.0),
        control_max_g=case.get("control_max_g", 0.0),
        weight_formula=DEFAULT_WEIGHT_FORMULAS[key],
        price_formula=DEFAULT_PRICE_FORMULA,
    )


def through_api(case: dict) -> dict:
    dims = case["dims"]
    payload = {
        "product_key": case["product_key"],
        "thickness": {
            "value": case.get("thickness", (0.0, "มม."))[0],
            "unit": case.get("thickness", (0.0, "มม."))[1],
            "mode": case.get("thickness_mode", "pair"),
        },
        "density_g_cm3": case.get("density_g_cm3", 0.92),
        "material_price_per_kg": case.get("material_price_per_kg", 65.0),
        "deduction_percent": case.get("deduction_percent", 10.0),
        "apply_deduction": case.get("apply_deduction", True),
        "sale_basis": case.get("sale_basis", "kg"),
        "selling_price_per_piece_override": case.get("selling_price_per_piece_override", 0.0),
        "selling_price_per_kg_override": case.get("selling_price_per_kg_override", 0.0),
        "pack_quantity": case.get("pack_quantity", 0.0),
        "sack_quantity": case.get("sack_quantity", 0.0),
        "order_quantity": case.get("order_quantity", 1000.0),
        "control_min_g": case.get("control_min_g", 0.0),
        "control_max_g": case.get("control_max_g", 0.0),
        "roof_gsm": case.get("roof_gsm", 120.0),
        "mesh_gsm": case.get("mesh_gsm", 80.0),
    }
    for name in ("width", "length", "height", "gusset", "sold_length"):
        if name in dims:
            payload[name] = {"value": dims[name][0], "unit": dims[name][1]}
    if "bottom_allowance" in case:
        payload["bottom_allowance"] = {
            "value": case["bottom_allowance"][0],
            "unit": case["bottom_allowance"][1],
        }
    return run_calculation(CalcRequest(**payload))


CASES: list[dict] = [
    {
        "name": "flat / bag in mm, thickness per pair, sold by kg",
        "product_key": "flat",
        "dims": {"width": (400.0, "มม."), "length": (480.0, "มม.")},
        "thickness": (0.05, "มม."),
        "selling_price_per_kg_override": 78.0,
        "pack_quantity": 100.0,
        "sack_quantity": 1000.0,
    },
    {
        "name": "flat / inches in, microns thick, per side",
        "product_key": "flat",
        "dims": {"width": (12.0, "นิ้ว"), "length": (18.0, "นิ้ว")},
        "thickness": (30.0, "ไมครอน"),
        "thickness_mode": "side",
        "selling_price_per_kg_override": 82.5,
    },
    {
        "name": "flat / bottom allowance in mm, not the default cm",
        "product_key": "flat",
        "dims": {"width": (400.0, "มม."), "length": (480.0, "มม.")},
        "thickness": (0.05, "มม."),
        "bottom_allowance": (10.0, "มม."),
        "selling_price_per_kg_override": 78.0,
    },
    {
        "name": "gusset / fold on one side",
        "product_key": "gusset",
        "dims": {"width": (40.0, "ซม."), "length": (60.0, "ซม."), "gusset": (12.5, "ซม.")},
        "thickness": (0.08, "มม."),
        "selling_price_per_kg_override": 71.0,
        "order_quantity": 5000.0,
    },
    {
        "name": "opaque sheet / no bottom allowance even though length is given",
        "product_key": "opaque",
        "dims": {"width": (50.0, "ซม."), "length": (70.0, "ซม.")},
        "thickness": (0.1, "มม."),
        "selling_price_per_kg_override": 69.0,
    },
    {
        "name": "roll / metres of film",
        "product_key": "roll",
        "dims": {"width": (60.0, "ซม."), "sold_length": (300.0, "เมตร")},
        "thickness": (0.06, "มม."),
        "selling_price_per_kg_override": 74.0,
        "order_quantity": 25.0,
    },
    {
        "name": "cover / roof plus mesh, no thickness at all",
        "product_key": "cover",
        "dims": {"width": (120.0, "ซม."), "length": (100.0, "ซม."), "height": (150.0, "ซม.")},
        "roof_gsm": 120.0,
        "mesh_gsm": 80.0,
        "selling_price_per_kg_override": 95.0,
    },
    {
        "name": "sold by piece / the price the salesman types wins",
        "product_key": "flat",
        "dims": {"width": (400.0, "มม."), "length": (480.0, "มม.")},
        "thickness": (0.05, "มม."),
        "sale_basis": "piece",
        "selling_price_per_piece_override": 1.25,
        "selling_price_per_kg_override": 78.0,
    },
    {
        "name": "deduction switched off",
        "product_key": "flat",
        "dims": {"width": (400.0, "มม."), "length": (480.0, "มม.")},
        "thickness": (0.05, "มม."),
        "apply_deduction": False,
        "selling_price_per_kg_override": 78.0,
    },
    {
        "name": "no selling price / falls back to the cost formula",
        "product_key": "flat",
        "dims": {"width": (400.0, "มม."), "length": (480.0, "มม.")},
        "thickness": (0.05, "มม."),
    },
    {
        "name": "control range / weight lands inside",
        "product_key": "flat",
        "dims": {"width": (400.0, "มม."), "length": (480.0, "มม.")},
        "thickness": (0.05, "มม."),
        "control_min_g": 3.0,
        "control_max_g": 5.0,
        "selling_price_per_kg_override": 78.0,
    },
    {
        "name": "sack over 25 kg",
        "product_key": "gusset",
        "dims": {"width": (60.0, "ซม."), "length": (90.0, "ซม."), "gusset": (20.0, "ซม.")},
        "thickness": (0.15, "มม."),
        "sack_quantity": 2000.0,
        "selling_price_per_kg_override": 70.0,
    },
]

COMPARED = (
    "grams_per_item",
    "items_per_kg",
    "production_items_per_kg",
    "unit_price",
    "selling_price_per_kg",
    "calculated_price_per_piece_from_kg",
    "pack_weight_kg",
    "sack_weight_kg",
    "total_price",
    "required_kg",
    "pack_count",
    "control_status",
    "roof_area_cm2",
    "mesh_area_cm2",
    "material_length_cm",
)


def main() -> int:
    failures: list[str] = []
    for case in CASES:
        expected = reference(case)
        actual = through_api(case)["results"]
        for field in COMPARED:
            want = getattr(expected, field)
            got = actual[field]
            if isinstance(want, str):
                same = want == got
            else:
                same = abs(float(want) - float(got)) < 1e-12
            if not same:
                failures.append(case["name"] + " / " + field + ": desktop=" + repr(want) + " web=" + repr(got))
        if not failures:
            print("  ok  " + case["name"] + "  ->  " + format(expected.grams_per_item, ".4f") + " g/pc, "
                  + format(expected.unit_price, ".4f") + " THB/pc")

    print("")
    if failures:
        print("LECH " + str(len(failures)) + " cho:")
        for line in failures:
            print("  - " + line)
        return 1
    print("KHOP: " + str(len(CASES)) + " ca, " + str(len(COMPARED)) + " truong moi ca, khong lech mot so nao.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
