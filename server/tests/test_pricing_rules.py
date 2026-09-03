# -*- coding: utf-8 -*-
"""The business numbers themselves, pinned to literals nobody computed with this code.

Why this file exists, and why the two files beside it are not enough:

  test_parity.py  builds its "expected" side by calling the SAME calculate() the
                  web API calls. It can prove the boundary in api/main.py did not
                  drift - it can NEVER prove a single number is right. Change the
                  weight formula and both sides move together, silently, green.
  test_screen_logic.py  pins the SENTENCES one product prints. Wording, not maths.

Every expectation below is a literal, worked out by hand away from the source and
cross-checked, then written down. Nothing here re-derives production logic on the
expectation side: no test-side formula, no calculate() on the "want" half. If a
line goes red, either the business rule moved or the hand arithmetic is wrong -
and both of those are worth a human reading them.

DB-free on purpose: only calculate(), normalize(), auto_markup(), run_calculation(),
require_positive_dimensions(), size_description(), to_cm(), thickness_to_mm() and
evaluate_formula() are touched. No endpoint that reads storage is called, so this
file runs with no DATABASE_URL, unlike test_screen_logic.py.

Run (Windows console needs the encoding or Thai output crashes it):
    set PYTHONIOENCODING=utf-8
    .venv/Scripts/python.exe tests/test_pricing_rules.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "core"))
sys.path.insert(0, str(HERE / "api"))

from calculator import (  # noqa: E402
    DEFAULT_PRICE_FORMULA,
    DEFAULT_WEIGHT_FORMULAS,
    calculate,
    require_positive_dimensions,
    size_description,
    thickness_to_mm,
    to_cm,
)
from formula_engine import evaluate_formula  # noqa: E402
from main import (  # noqa: E402
    CalcRequest,
    Measure,
    Thickness,
    auto_markup,
    normalize,
    run_calculation,
)

failures: list[str] = []


def check(name: str, got, want) -> None:
    if got == want:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name)
        print("       muon: " + repr(want))
        print("       nhan: " + repr(got))


def close(name: str, got, want, tol: float = 1e-9) -> None:
    """Same as check(), but for floats: IEEE-754 noise is not a business error."""
    try:
        same = abs(float(got) - float(want)) <= tol
    except (TypeError, ValueError):
        same = False
    if same:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name)
        print("       muon: " + repr(want) + "  (sai so cho phep " + repr(tol) + ")")
        print("       nhan: " + repr(got))


def refusal(name: str, fn, want: str) -> None:
    """The refusal must arrive, and it must say exactly this sentence in Thai."""
    try:
        fn()
    except ValueError as exc:
        check(name, str(exc), want)
        return
    failures.append(name)
    print("  BAD " + name + "  (khong tu choi gi ca)")


def allows(name: str, fn) -> None:
    """The other half of a boundary: this input must NOT be refused."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - any refusal at all is the failure
        failures.append(name)
        print("  BAD " + name + "  (tu choi nham: " + repr(exc) + ")")
        return
    print("  ok  " + name)


# --------------------------------------------------------------------------- #
# The bag on every screenshot: 45 x 60 cm, 0.08 mm per pair, 1 cm bottom, LDPE.
# --------------------------------------------------------------------------- #


def bag(**over) -> CalcRequest:
    base = dict(
        product_key="flat",
        width=Measure(value=45, unit="ซม."),
        length=Measure(value=60, unit="ซม."),
        thickness=Thickness(value=0.08, unit="มม.", mode="pair"),
        bottom_allowance=Measure(value=1, unit="ซม."),
        density_g_cm3=0.92,
        material_price_per_kg=65,
        deduction_percent=10,
        apply_deduction=True,
        sale_basis="kg",
        order_quantity=1000,
    )
    base.update(over)
    return CalcRequest(**base)


def out(**over) -> dict:
    return run_calculation(bag(**over))


def res(**over) -> dict:
    return out(**over)["results"]


def core(**over):
    """calculate() reached directly - the only way to hand it values CalcRequest
    would reject at the door (a product key that is not one of the five, a
    thickness mode that is neither side nor pair)."""
    base = dict(
        product_key="flat",
        width_cm=45.0,
        length_cm=60.0,
        height_cm=0.0,
        gusset_cm=0.0,
        sold_length_m=0.0,
        bottom_allowance_cm=1.0,
        thickness_input_mm=0.08,
        thickness_mode="pair",
        density_g_cm3=0.92,
        roof_gsm=120.0,
        mesh_gsm=80.0,
        material_price_per_kg=65.0,
        markup_percent=0.0,
        deduction_percent=10.0,
        pack_quantity=0.0,
        sack_quantity=0.0,
        order_quantity=1000.0,
        control_min_g=0.0,
        control_max_g=0.0,
        weight_formula=DEFAULT_WEIGHT_FORMULAS["flat"],
        price_formula=DEFAULT_PRICE_FORMULA,
    )
    base.update(over)
    return calculate(**base)


# =========================================================================== #
print("A. Nam nhanh cong thuc can nang - moi nhanh mot con so viet tay")
# =========================================================================== #

# 1  flat: 45 * 61 * 2 * (0.04/10) * 0.92 = 20.2032 g
close(
    "weight_flat_45x60x0p08pair_matchesLiteralGrams",
    res()["grams_per_item"],
    20.2032,
)

# 2  gusset: the fold joins the WIDTH, not the length. (40+12.5) * 61 * 2 * 0.004 * 0.92
close(
    "weight_gusset_addsGussetToWidth",
    res(
        product_key="gusset",
        width=Measure(value=40, unit="ซม."),
        gusset=Measure(value=12.5, unit="ซม."),
    )["grams_per_item"],
    23.5704,
)

# 3  roll: metres of film become centimetres by x100. 60 * 300 * 100 * 2 * 0.003 * 0.92
close(
    "weight_roll_metresTimes100",
    res(
        product_key="roll",
        width=Measure(value=60, unit="ซม."),
        sold_length=Measure(value=300, unit="เมตร"),
        thickness=Thickness(value=0.06, unit="มม.", mode="pair"),
    )["grams_per_item"],
    9936.0,
)

# 4  opaque sheet: ONE layer (no x2) and NO bottom allowance. Both readings of the
#    SAME sheet are written down here, next to each other, because "pair" is the
#    default mode (main.py:79, screen.py:189) and calculator.py:160 halves the typed
#    thickness for pair mode with no regard for the product: a 0.1 mm sheet entered
#    on the default screen is weighed at 0.05 mm.
#      pair: 50 * 70 * 0.005 * 0.92 = 16.1 g
#      side: 50 * 70 * 0.010 * 0.92 = 32.2 g   <- exactly twice the material
#    16.1 is what production returns TODAY. It is recorded, not endorsed - see the
#    human_summary pin below, where the screen's own verification line prints the
#    32.2 arithmetic underneath the 16.100 answer.
sheet_pair = out(
    product_key="opaque",
    width=Measure(value=50, unit="ซม."),
    length=Measure(value=70, unit="ซม."),
    thickness=Thickness(value=0.1, unit="มม.", mode="pair"),
)
close(
    "weight_opaque_0p1mmPairMode_16p1g_thicknessHalvedLikeABag",
    sheet_pair["results"]["grams_per_item"],
    16.1,
)
close(
    "weight_opaque_0p1mmSideMode_32p2g_twiceThePairReading",
    res(
        product_key="opaque",
        width=Measure(value=50, unit="ซม."),
        length=Measure(value=70, unit="ซม."),
        thickness=Thickness(value=0.1, unit="มม.", mode="side"),
    )["grams_per_item"],
    32.2,
)
# KNOWN CONTRADICTION IN PRODUCTION, pinned so it cannot be lost: the line the
# salesman is meant to check the number WITH shows the full 0.1 mm and no halving.
# 50 x 70 x (0.1/10) x 0.92 is 32.2, not the 16.100 the same line then prints.
# human_summary (main.py:487-493) is handed normalized["thickness_input_mm"], never
# thickness_side_mm. One of the two figures is wrong by a factor of two - a 50%
# material swing on every sheet quote - and this file will not guess which.
check(
    "humanSummary_opaquePairMode_printsThe32p2ArithmeticUnderThe16p1Answer",
    sheet_pair["human_summary"].split("\n")[0],
    "ตรวจสูตรน้ำหนัก / Weight: 50 × 70 × (0.1/10) × 0.92 "
    "[Plastic Sheet: หนึ่งแผ่น/ด้านเดียว, ไม่คูณ 2 / single layer, no ×2] = 16.100 g",
)

# 5  cover: no thickness anywhere - roof gsm on the roof, mesh gsm on the skirt.
#    (20301/10000)*120 + (91204/10000)*80 = 243.612 + 729.632
close(
    "weight_cover_roofPlusMesh",
    res(
        product_key="cover",
        width=Measure(value=100, unit="ซม."),
        length=Measure(value=200, unit="ซม."),
        height=Measure(value=150, unit="ซม."),
        thickness=Thickness(value=0, unit="มม.", mode="pair"),
        roof_gsm=120,
        mesh_gsm=80,
    )["grams_per_item"],
    973.244,
)


# =========================================================================== #
print("")
print("B. Hinh hoc chet lang le - phan bu ay chi thuoc ve hai loai tui")
# =========================================================================== #

# 6  flat/gusset: the material is longer than the quoted length by the allowance.
close(
    "materialLength_flat_addsBottomAllowance",
    res()["material_length_cm"],
    61.0,
)
close(
    "materialLength_flat_allowanceZero_staysAtQuotedLength",
    res(bottom_allowance=Measure(value=0, unit="ซม."))["material_length_cm"],
    60.0,
)
close(
    "weight_flat_allowanceZero_19p872g",  # 45 * 60 * 2 * 0.004 * 0.92
    res(bottom_allowance=Measure(value=0, unit="ซม."))["grams_per_item"],
    19.872,
)

# 7  a sheet has no bottom to seal. TWO independent guards say so, and each one is
#    pinned on its own here - a check that runs through both at once stays green
#    while either one of them rots, which is no guard at all.
#      guard 1  normalize() zeroes the allowance for anything that is not a bag
#               (main.py:308, 316-318)
#      guard 2  calculate() adds the allowance only for flat/gusset
#               (calculator.py:165-167)
sheet = out(
    product_key="opaque",
    width=Measure(value=50, unit="ซม."),
    length=Measure(value=70, unit="ซม."),
    thickness=Thickness(value=0.1, unit="มม.", mode="pair"),
    bottom_allowance=Measure(value=5, unit="ซม."),
)
close(
    "normalize_opaque_bottomAllowance5cm_zeroedAtTheBoundary",
    sheet["normalized"]["bottom_allowance_cm"],
    0.0,
)
close(
    "materialLength_opaque_throughTheApi_ignoresBottomAllowance",
    sheet["results"]["material_length_cm"],
    70.0,
)
# guard 2 alone: 5 cm reaches calculate() unlaundered, because core() skips
# normalize() entirely. Nothing upstream can hide a broken product test here.
close(
    "materialLength_opaque_5cmAllowanceStraightIntoCalculate_stays70cm",
    core(
        product_key="opaque",
        width_cm=50.0,
        length_cm=70.0,
        thickness_input_mm=0.1,
        bottom_allowance_cm=5.0,
        weight_formula=DEFAULT_WEIGHT_FORMULAS["opaque"],
    ).material_length_cm,
    70.0,
)
# and the reason a broken guard would not even show up in the grams: the sheet
# formula reads the QUOTED length, never the material length. Fed a variables dict
# where the two deliberately differ, only one of them can produce 16.1 g.
close(
    "weightFormula_opaque_readsQuotedLength70_notMaterialLength75",
    evaluate_formula(
        DEFAULT_WEIGHT_FORMULAS["opaque"],
        {
            "width_cm": 50.0,
            "length_cm": 70.0,
            "material_length_cm": 75.0,
            "thickness_side_mm": 0.05,
            "density_g_cm3": 0.92,
        },
    ),
    16.1,
)

# 8  seam allowances belong to the hand-sewn cover and to nothing else.
cover_out = res(
    product_key="cover",
    width=Measure(value=100, unit="ซม."),
    length=Measure(value=200, unit="ซม."),
    height=Measure(value=150, unit="ซม."),
    thickness=Thickness(value=0, unit="มม.", mode="pair"),
)
close("coverAreas_roof_101x201_20301cm2", cover_out["roof_area_cm2"], 20301.0)
close("coverAreas_mesh_604x151_91204cm2", cover_out["mesh_area_cm2"], 91204.0)
close("coverAreas_flatBag_roofIsZero", res()["roof_area_cm2"], 0.0)
close("coverAreas_flatBag_meshIsZero", res()["mesh_area_cm2"], 0.0)


# =========================================================================== #
print("")
print("C. Do mot mat hay ca cap - sai cho nay la sai gap doi tien")
# =========================================================================== #

# 9  0.08 mm PER SIDE is twice the material of 0.08 mm per pair. Exactly twice.
close(
    "thickness_pairMode_0p08_20p2032g",
    res()["grams_per_item"],
    20.2032,
)
close(
    "thickness_sideMode_0p08_40p4064g",
    res(thickness=Thickness(value=0.08, unit="มม.", mode="side"))["grams_per_item"],
    40.4064,
)


# =========================================================================== #
print("")
print("D. Quy doi don vi o BIEN, khong bao gio o giua")
# =========================================================================== #

# 10  to_cm: one unit in, its factor out.
for name, unit, want in (
    ("toCm_1nyu_2p54cm", "นิ้ว", 2.54),
    ("toCm_1sm_1cm", "ซม.", 1.0),
    ("toCm_1mm_0p1cm", "มม.", 0.1),
    ("toCm_1met_100cm", "เมตร", 100.0),
):
    close(name, to_cm(1.0, unit), want)

# 11  thickness_to_mm: a different table, deliberately - micron is 0.001 mm.
for name, unit, want in (
    ("thicknessToMm_1mm_1mm", "มม.", 1.0),
    ("thicknessToMm_1sm_10mm", "ซม.", 10.0),
    ("thicknessToMm_1nyu_25p4mm", "นิ้ว", 25.4),
    ("thicknessToMm_1maikron_0p001mm", "ไมครอน", 0.001),
):
    close(name, thickness_to_mm(1.0, unit), want)

# The conversion must survive the whole trip, not just the helper: a bag typed
# in millimetres, and a bag typed in inches with a thickness in microns.
mm_bag = out(
    width=Measure(value=400, unit="มม."),
    length=Measure(value=480, unit="มม."),
    thickness=Thickness(value=0.05, unit="มม.", mode="pair"),
)
close("toCm_bagIn_400mm_width_becomes40cm", mm_bag["normalized"]["width_cm"], 40.0)
close("toCm_bagIn_480mm_length_becomes48cm", mm_bag["normalized"]["length_cm"], 48.0)
close("materialLength_bagIn_48cmPlus1_49cm", mm_bag["results"]["material_length_cm"], 49.0)
close("weight_bagIn_mm_40x49x0p025side_9p016g", mm_bag["results"]["grams_per_item"], 9.016)

inch_bag = out(
    width=Measure(value=12, unit="นิ้ว"),
    length=Measure(value=18, unit="นิ้ว"),
    thickness=Thickness(value=30, unit="ไมครอน", mode="side"),
)
close("toCm_bagIn_12inch_width_becomes30p48cm", inch_bag["normalized"]["width_cm"], 30.48)
close("toCm_bagIn_18inch_length_becomes45p72cm", inch_bag["normalized"]["length_cm"], 45.72)
close(
    "weight_bagIn_inches_30micronSide_7p860621312g",
    inch_bag["results"]["grams_per_item"],
    7.860621312,
)

# 12  an unknown unit is refused, and the refusal repeats the unit back.
refusal("toCm_unknownUnit_refusesByName", lambda: to_cm(1.0, "ฟุต"), "หน่วยระยะไม่รองรับ: ฟุต")
refusal(
    "thicknessToMm_unknownUnit_refusesByName",
    lambda: thickness_to_mm(1.0, "ฟุต"),
    "หน่วยความหนาไม่รองรับ: ฟุต",
)

# 13  at the boundary the message must also say WHICH box is wrong - "unsupported
#     unit" alone sends the salesman hunting through six fields.
refusal(
    "normalize_unknownWidthUnit_namesWidth",
    lambda: normalize(bag(width=Measure(value=45, unit="ฟุต"))),
    "หน่วยระยะไม่รองรับ (width): ฟุต",
)
refusal(
    "normalize_unknownGussetUnit_namesGusset",
    lambda: normalize(bag(gusset=Measure(value=0, unit="ฟุต"))),
    "หน่วยระยะไม่รองรับ (gusset): ฟุต",
)
refusal(
    "normalize_unknownBottomAllowanceUnit_namesBottomAllowance",
    lambda: normalize(bag(bottom_allowance=Measure(value=1, unit="ฟุต"))),
    "หน่วยระยะไม่รองรับ (bottom_allowance): ฟุต",
)
# KNOWN GAP, recorded rather than dressed up as a pass: the three rows above name
# the box ("(width)", "(gusset)", "(bottom_allowance)"), the thickness row cannot.
# The boundary guard (main.py:302-303) raises a message byte-identical to the one
# thickness_to_mm raises (calculator.py:87), so this check cannot tell the two
# apart - delete the boundary guard and it stays green. The asymmetry is
# production's: for thickness, "say WHICH box is wrong" is simply not done.
refusal(
    "thicknessUnit_refusalDoesNotNameTheField_knownGap",
    lambda: normalize(bag(thickness=Thickness(value=0.08, unit="ฟุต", mode="pair"))),
    "หน่วยความหนาไม่รองรับ: ฟุต",
)
# What CAN be pinned: which complaint arrives first. A bad unit and a blank box at
# once must report the unit, not send the salesman to fix a width that was never
# the problem.
refusal(
    "normalize_badThicknessUnitAndBlankWidth_reportsTheUnitNotTheBlank",
    lambda: normalize(
        bag(
            width=Measure(value=0, unit="ซม."),
            thickness=Thickness(value=0.08, unit="ฟุต", mode="pair"),
        )
    ),
    "หน่วยความหนาไม่รองรับ: ฟุต",
)


# =========================================================================== #
print("")
print("E. Ai quyet dinh gia ban - ba nhanh va hai cai bay")
# =========================================================================== #

# 14  branch A: sold by piece and a piece price typed -> that price wins outright,
#     and the price per kg is worked backwards from it.
by_piece = res(
    sale_basis="piece",
    selling_price_per_piece_override=1.25,
    selling_price_per_kg_override=53,
)
close("price_pieceOverride_winsOverEverything", by_piece["unit_price"], 1.25)
close(
    "sellingPricePerKg_pieceOverride_1p25x44p54739843193158_55p68424803991447",
    by_piece["selling_price_per_kg"],
    55.68424803991447,
)

# 15  branch B: a price per kg typed -> divided by the count AFTER the deduction,
#     never by the raw count.
by_kg = res(selling_price_per_kg_override=53)
close("price_kgOverride_dividesByAdjustedItems", by_kg["unit_price"], 1.189744)
close("sellingPricePerKg_kgOverride_passesThrough_53", by_kg["selling_price_per_kg"], 53.0)
close("totalPrice_1p189744x1000pcs_1189p744", by_kg["total_price"], 1189.744)
close("requiredKg_1000pcsOver44p54739843193158_22p448", by_kg["required_kg"], 22.448)
close("markupPercent_53basisOn65material_minus18p46153846153846", by_kg["markup_percent"], -18.46153846153846)

# 16  branch C: nothing typed -> the cost formula, at whatever markup was derived
#     (here nothing was derived, so markup is 0 and the price is bare cost).
bare = res()
close("price_noOverride_fallsBackToCostFormula", bare["unit_price"], 1.313208)
close("sellingPricePerKg_noOverride_1p313208x44p54739843193158_58p5", bare["selling_price_per_kg"], 58.5)

# 17  TRAP: a piece price left over from an earlier quote must NOT leak into a
#     kg sale. Branch A is gated on sale_basis, not on the field being filled.
close(
    "price_saleBasisKg_ignoresPieceOverride",
    res(
        sale_basis="kg",
        selling_price_per_piece_override=1.25,
        selling_price_per_kg_override=53,
    )["unit_price"],
    1.189744,
)

# 18  TRAP the other way: sold by piece but the piece box is blank. Zero is not a
#     price, so it must fall through to the kg basis - not quote the bag at 0.
close(
    "price_saleBasisPiece_butPieceBlank_fallsToKgOverride",
    res(
        sale_basis="piece",
        selling_price_per_piece_override=0,
        selling_price_per_kg_override=53,
    )["unit_price"],
    1.189744,
)

# 19  the "calculated price per piece" column is always the KG basis divided out.
#     It is the figure the salesman compares his typed piece price against, so it
#     must not quietly become that same typed number.
close(
    "calculatedPricePerPiece_alwaysFromKgBasis_notTypedPiece",
    by_piece["calculated_price_per_piece_from_kg"],
    1.189744,
)
close(
    "calculatedPricePerPiece_noKgBasis_fallsBackToCostPrice",
    res(sale_basis="piece")["calculated_price_per_piece_from_kg"],
    1.313208,
)


# =========================================================================== #
print("")
print("F. Phan tram bu lai la SUY RA tu hai o gia, khong ai go vao")
# =========================================================================== #

# 20  78 over 65 is a fifth more.
close("autoMarkup_78over65_returns20Percent", auto_markup(65.0, 78.0), 20.0)

# 21  no material price -> nothing to mark up FROM. The guard is what stops a
#     division by zero, so it must come before the formula, not after.
check("autoMarkup_zeroMaterialPrice_returnsZero", auto_markup(0.0, 78.0), 0.0)
check("autoMarkup_negativeMaterialPrice_returnsZero", auto_markup(-5.0, 78.0), 0.0)

# 22  no kg basis typed -> markup 0. NOT -100: the unguarded formula would give
#     ((0/65)-1)*100 = -100, which makes (1 + markup/100) zero and quotes every
#     bag at 0 baht.
check("autoMarkup_noKgBasis_returnsZero", auto_markup(65.0, 0.0), 0.0)

# 23  selling under the material price must SHOW as a negative markup, not be
#     clamped to zero - a loss the screen hides is a loss nobody catches.
close("autoMarkup_52basisOn65material_returnsMinus20", auto_markup(65.0, 52.0), -20.0)
close(
    "autoMarkup_53basisOn65material_returnsMinus18p46153846153846",
    auto_markup(65.0, 53.0),
    -18.46153846153846,
)

# 24  markup 0 -> the quote is the bare material cost, nothing added.
piece_no_basis = res(sale_basis="piece")
close("price_pieceSaleWithNoKgBasis_quotesAtCost", piece_no_basis["unit_price"], 1.313208)
close("markupPercent_pieceSaleWithNoKgBasis_isZero", piece_no_basis["markup_percent"], 0.0)

# The price formula itself, fed by hand. Two readings of the same bag: at markup 0
# it is the raw cost; at the markup auto_markup derives for a 53 THB/kg basis it
# collapses back to grams x that basis - which is the whole point of deriving the
# markup instead of typing one.
close(
    "priceFormula_20p2032gAt65thbMarkup0_1p313208",
    evaluate_formula(
        DEFAULT_PRICE_FORMULA,
        {"grams_per_item": 20.2032, "material_price_per_kg": 65.0, "markup_percent": 0.0},
    ),
    1.313208,
)
# NOT A REACHABLE QUOTE - the arithmetic of the markup term, nothing more. Through
# CalcRequest, markup_percent is non-zero only when selling_price_per_kg_override
# is (main.py:326-329, 540) - and whenever that override is set, calculate() takes
# the kg branch for both unit_price and the calculated piece price
# (calculator.py:207-217), so suggested_unit_price, the only consumer of
# markup_percent, is computed and thrown away. The derived markup is a display
# figure on that path. The term is still live inside calculate() when a caller
# passes a markup directly - section J pins that at exactly -100.
close(
    "priceFormula_markupTermArithmetic_notAReachableQuote",
    evaluate_formula(
        DEFAULT_PRICE_FORMULA,
        {
            "grams_per_item": 20.2032,
            "material_price_per_kg": 65.0,
            "markup_percent": -18.46153846153846,
        },
    ),
    1.0707696,
)
close(
    "priceFormula_13p4688gAt79p5thbMarkup0_1p0707696",
    evaluate_formula(
        DEFAULT_PRICE_FORMULA,
        {"grams_per_item": 13.4688, "material_price_per_kg": 79.5, "markup_percent": 0.0},
    ),
    1.0707696,
)


# =========================================================================== #
print("")
print("G. Hut hao san xuat - cai cong tac va hai bien")
# =========================================================================== #

# 25  10% off the count means fewer bags per kilo, so a dearer bag.
on = res(selling_price_per_kg_override=53)
close("deduction_on_itemsPerKg_49p49710936881286", on["items_per_kg"], 49.49710936881286)
close(
    "deduction_on_reducesItemsPerKg",
    on["production_items_per_kg"],
    44.54739843193158,
)

# 26  the switch, not the number, decides. 10 stays typed in the box and is ignored.
off = res(apply_deduction=False, selling_price_per_kg_override=53)
close(
    "deduction_off_keepsNormalItemsPerKg",
    off["production_items_per_kg"],
    49.49710936881286,
)
close("deduction_off_unitPrice_53over49p49710936881286_1p0707696", off["unit_price"], 1.0707696)

# 27 + 28  the bound is exclusive: 99.9 is a legal (if absurd) deduction, 100 is not,
#          because 100 would leave zero bags per kilo and divide by zero downstream.
close(
    "deduction_99p9_accepted",
    res(deduction_percent=99.9)["production_items_per_kg"],
    0.04949710936881286,
)
refusal(
    "deduction_100_refused",
    lambda: core(deduction_percent=100),
    "เปอร์เซ็นต์หักต้องอยู่ระหว่าง 0 ถึงน้อยกว่า 100",
)


# =========================================================================== #
print("")
print("H. Bon phan quyet cua khoang kiem soat can nang")
# =========================================================================== #

# 29  the bag weighs 20.2032 g. Four windows, four verdicts.
for name, lo, hi, want in (
    ("controlStatus_noRangeSet_notSet", 0, 0, "ยังไม่กำหนด / Not Set"),
    ("controlStatus_20p2032gUnder25to30_belowRange", 25, 30, "ต่ำกว่าช่วง / Below Range"),
    ("controlStatus_20p2032gOver10to15_aboveRange", 10, 15, "สูงกว่าช่วง / Above Range"),
    ("controlStatus_20p2032gInside20to21_withinRange", 20, 21, "อยู่ในช่วง / Within Range"),
):
    check(name, res(control_min_g=lo, control_max_g=hi)["control_status"], want)

# 30  a floor with no ceiling can only ever say "below" or "within". Reporting
#     "above" with no maximum typed would be a verdict on a rule nobody set.
check(
    "controlStatus_onlyMinSet_heavyBag_neverReportsAbove",
    res(control_min_g=10, control_max_g=0)["control_status"],
    "อยู่ในช่วง / Within Range",
)
check(
    "controlStatus_onlyMinSet_lightBag_stillReportsBelow",
    res(control_min_g=25, control_max_g=0)["control_status"],
    "ต่ำกว่าช่วง / Below Range",
)

# 31  an impossible window is refused at the boundary, before any weight is judged
#     against it - but only when a ceiling was actually typed.
refusal(
    "normalize_minAboveMax_refused",
    lambda: normalize(bag(control_min_g=30, control_max_g=20)),
    "น้ำหนักควบคุมต่ำสุดต้องไม่มากกว่าค่าสูงสุด",
)
allows(
    "normalize_minSetWithNoMax_accepted",
    lambda: normalize(bag(control_min_g=30, control_max_g=0)),
)


# =========================================================================== #
print("")
print("I. Moi loai san pham doi nhung o khac nhau, va goi ten o con thieu")
# =========================================================================== #

# 32  the missing box must be named in Thai. "Invalid input" would send somebody
#     back through five fields to find which one.
refusal(
    "requiredDimensions_flatMissingLength_namesLength",
    lambda: require_positive_dimensions(
        "flat", {"width_cm": 45.0, "length_cm": 0.0, "thickness_input_mm": 0.08}
    ),
    "ความยาวต้องมากกว่า 0",
)
refusal(
    "requiredDimensions_gussetMissingGusset_namesGusset",
    lambda: require_positive_dimensions(
        "gusset",
        {"width_cm": 40.0, "length_cm": 60.0, "gusset_cm": 0.0, "thickness_input_mm": 0.08},
    ),
    "ขนาดพับข้างต้องมากกว่า 0",
)
refusal(
    "requiredDimensions_rollMissingSoldLength_namesRollLength",
    lambda: require_positive_dimensions(
        "roll", {"width_cm": 60.0, "sold_length_m": 0.0, "thickness_input_mm": 0.06}
    ),
    "ความยาวม้วนต้องมากกว่า 0",
)
refusal(
    "requiredDimensions_opaqueMissingThickness_namesThickness",
    lambda: require_positive_dimensions(
        "opaque", {"width_cm": 50.0, "length_cm": 70.0, "thickness_input_mm": 0.0}
    ),
    "ความหนาต้องมากกว่า 0",
)
# A hand-sewn cover is cut from bought fabric sold by gsm - it HAS no thickness to
# type. Demanding one here would make the whole product unquotable.
allows(
    "requiredDimensions_coverWithNoThickness_accepted",
    lambda: require_positive_dimensions(
        "cover",
        {"width_cm": 100.0, "length_cm": 200.0, "height_cm": 150.0, "thickness_input_mm": 0.0},
    ),
)
refusal(
    "requiredDimensions_coverMissingHeight_namesHeight",
    lambda: require_positive_dimensions(
        "cover", {"width_cm": 100.0, "length_cm": 200.0, "height_cm": 0.0}
    ),
    "ความสูงต้องมากกว่า 0",
)


# =========================================================================== #
print("")
print("J. Moi cau lenh tu choi trong calculate(), nguyen van")
# =========================================================================== #

# 33  one row per raise in calculate(), in the order the function checks them - all
#     twelve, including the two FormulaError sites at the end, which are reachable
#     from the API surface: weight_formula and price_formula are free strings on
#     CalcRequest (main.py:112-113). refusal() catches ValueError and FormulaError
#     subclasses it (formula_engine.py:10), so no helper change is needed.
for name, over, want in (
    ("calculate_unknownProductKey_refused", {"product_key": "bottle"}, "ประเภทสินค้าไม่ถูกต้อง"),
    ("calculate_unknownThicknessMode_refused", {"thickness_mode": "double"}, "รูปแบบความหนาไม่ถูกต้อง"),
    ("calculate_zeroDensity_refused", {"density_g_cm3": 0}, "ความหนาแน่นต้องมากกว่า 0"),
    ("calculate_negativeDensity_refused", {"density_g_cm3": -0.92}, "ความหนาแน่นต้องมากกว่า 0"),
    (
        "calculate_negativeMaterialPrice_refused",
        {"material_price_per_kg": -1},
        "ราคา/เปอร์เซ็นต์บวกเพิ่มไม่ถูกต้อง",
    ),
    (
        "calculate_markupBelowMinus100_refused",
        {"markup_percent": -100.1},
        "ราคา/เปอร์เซ็นต์บวกเพิ่มไม่ถูกต้อง",
    ),
    (
        "calculate_negativeDeduction_refused",
        {"deduction_percent": -1},
        "เปอร์เซ็นต์หักต้องอยู่ระหว่าง 0 ถึงน้อยกว่า 100",
    ),
    (
        "calculate_deduction100_refused",
        {"deduction_percent": 100},
        "เปอร์เซ็นต์หักต้องอยู่ระหว่าง 0 ถึงน้อยกว่า 100",
    ),
    ("calculate_negativePackQuantity_refused", {"pack_quantity": -1}, "จำนวนต่อแพ็กต้องไม่ติดลบ"),
    ("calculate_negativeSackQuantity_refused", {"sack_quantity": -1}, "จำนวนต่อกระสอบต้องไม่ติดลบ"),
    ("calculate_negativeOrderQuantity_refused", {"order_quantity": -1}, "จำนวนสั่งผลิตต้องไม่ติดลบ"),
    (
        "calculate_negativePiecePrice_refused",
        {"selling_price_per_piece_override": -1},
        "ราคาขายต้องไม่ติดลบ",
    ),
    (
        "calculate_negativeKgPrice_refused",
        {"selling_price_per_kg_override": -1},
        "ราคาขายต้องไม่ติดลบ",
    ),
    (
        "calculate_negativeBottomAllowance_refused",
        {"bottom_allowance_cm": -1},
        "ค่าบวกก้นถุงต้องไม่ติดลบ",
    ),
    # a cover with no fabric weighs nothing: 0 g must be refused, not priced.
    (
        "calculate_zeroWeightFormulaResult_refused",
        {
            "product_key": "cover",
            "roof_gsm": 0,
            "mesh_gsm": 0,
            "weight_formula": DEFAULT_WEIGHT_FORMULAS["cover"],
        },
        "สูตรน้ำหนักต้องให้ผลมากกว่า 0 กรัม",
    ),
    # a custom price formula that goes below zero must not become a quote.
    (
        "calculate_negativePriceFormulaResult_refused",
        {"price_formula": "grams_per_item - 1000"},
        "สูตรราคาต้องไม่ให้ผลติดลบ",
    ),
):
    refusal(name, lambda over=over: core(**over), want)

# The other side of the markup bound: exactly -100 is legal, and it prices the bag
# at nothing. That is a business decision the rule allows, not an accident.
allows("calculate_markupExactlyMinus100_accepted", lambda: core(markup_percent=-100))
close("calculate_markupExactlyMinus100_unitPriceIsZero", core(markup_percent=-100).unit_price, 0.0)


# =========================================================================== #
print("")
print("K. Dong kich thuoc in ra, va can nang cua mot pack")
# =========================================================================== #

DIMS = {
    "width": {"value": 45, "unit": "ซม."},
    "length": {"value": 60, "unit": "ซม."},
    "height": {"value": 150, "unit": "ซม."},
    "gusset": {"value": 12.5, "unit": "ซม."},
    "sold_length": {"value": 300, "unit": "เมตร"},
}

# 34  the size line on the quote, character for character.
check(
    "sizeDescription_flat_widthTimesLength",
    size_description("flat", DIMS),
    "กว้าง/Width 45 ซม. × ยาว/Length 60 ซม.",
)
check(
    "sizeDescription_opaque_sameShapeAsFlat",
    size_description("opaque", DIMS),
    "กว้าง/Width 45 ซม. × ยาว/Length 60 ซม.",
)
check(
    "sizeDescription_gusset_addsTheFold",
    size_description("gusset", DIMS),
    "กว้าง/Width 45 ซม. × ยาว/Length 60 ซม. × พับข้าง/Gusset 12.5 ซม.",
)
check(
    "sizeDescription_roll_widthTimesRollLength",
    size_description("roll", DIMS),
    "กว้าง/Width 45 ซม. × ความยาวโรล/Roll Length 300 เมตร",
)
check(
    "sizeDescription_cover_addsHeight",
    size_description("cover", DIMS),
    "กว้าง/Width 45 ซม. × ยาว/Length 60 ซม. × สูง/Height 150 ซม.",
)

# packing weights: grams x count / 1000, and the pack count off the order.
packed = res(pack_quantity=100, sack_quantity=1000, order_quantity=1000)
close("packWeight_20p2032gTimes100Over1000_2p02032kg", packed["pack_weight_kg"], 2.02032)
close("sackWeight_20p2032gTimes1000Over1000_20p2032kg", packed["sack_weight_kg"], 20.2032)
close("packCount_1000pcsOver100PerPack_10packs", packed["pack_count"], 10.0)

# nobody typed a pack size: answer 0, do not divide by zero and take the screen down.
unpacked = res(pack_quantity=0, order_quantity=1000)
close("packCount_zeroPackQuantity_returnsZeroNotCrash", unpacked["pack_count"], 0.0)
close("packWeight_zeroPackQuantity_returnsZero", unpacked["pack_weight_kg"], 0.0)


print("")
if failures:
    print("HONG: " + str(len(failures)) + " kiem tra do - " + ", ".join(failures))
    sys.exit(1)
print("KHOP: moi con so nghiep vu deu khop voi so viet tay, khong phai voi chinh no.")
