# -*- coding: utf-8 -*-
"""The formula box is a hole punched through the server: a user types a string and
the server evaluates it. Until this file existed, core/formula_engine.py had ZERO
tests, so nothing proved the hole was sealed.

Three jobs here, and nothing else:

  1. SEALED. Every escape a typed string could try - attribute access, __import__,
     open(), subscripting, lambda, the four comprehension forms, collection
     literals, f-strings, walrus, boolean operators, starred args - must come back
     as a FormulaError carrying the Thai sentence the CEO actually sees. One row
     per attack, so a hole that opens later names itself.
  2. HONEST. The guards (divide by zero, exponent range, result size, formula
     length) must fire on the exact boundary the source claims, and the variable
     list shown on screen (calculator.FORMULA_VARIABLES) must be the exact list of
     names that really evaluate. A variable list that lies is a support ticket a
     month from now.
  3. LOUD ABOUT WHAT IS STILL BROKEN. visit_Constant (formula_engine.py:38-41)
     checks the TYPE of a literal and nothing else - not its magnitude, not
     whether it is finite, not whether float() can even hold it. Three kinds of
     literal walk straight through it today, and every one is recorded by
     pending_fix(), never by a passing check(). A suite that is green BECAUSE a
     bug is still there has inverted its own signal.

pending_fix() prints CHUA SUA and leaves the run green, because this file is not
allowed to edit production. The day production is fixed, that row turns BAD with
"promote to refusal()" - a ten-second red, not a phantom regression. The pending
count is printed on the last line whether the run passes or fails, so it cannot
rot quietly.

Unlike tests/test_parity.py - which is deliberately a change-detector, its
reference side calling the same calculate() - EVERY number below is a literal,
worked out by hand from the source. Nothing here re-runs production logic to
build its own expectation. If a number moves, this file says so.

NOTE on validate_formula: it has NO production caller. grep over the whole repo
finds only its definition (formula_engine.py:114) and this file. FORMULA_VARIABLES
reaches the screen at main.py:726 and :732 and is never handed to the validator,
and run_calculation (main.py:536-569) passes the user's raw string straight into
calculate(). So nothing checks a formula before it is saved or used. The rows
that call validate_formula below prove the helper itself works; they do NOT prove
anything about the running server. Every load-bearing claim goes through
calculate().

No database, no fastapi, no network: it imports core/ only.

Run (from D:\\ThaiPlasticPricing), with UTF-8 on or the Thai crashes the console:
    set PYTHONIOENCODING=utf-8
    server/.venv/Scripts/python.exe server/tests/test_formula_engine.py
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
    FORMULA_VARIABLES,
    calculate,
)
from formula_engine import FormulaError, evaluate_formula, validate_formula  # noqa: E402

failures: list[str] = []
pending: list[str] = []

VARS = {"width_cm": 45.0, "density_g_cm3": 0.92}


def check(name: str, got, want) -> None:
    if got == want:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name)
        print("       muon: " + repr(want))
        print("       nhan: " + repr(got))


def close(name: str, got, want: float, tol: float = 1e-9) -> None:
    if isinstance(got, (int, float)) and abs(float(got) - want) <= tol:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name)
        print("       muon: " + repr(want))
        print("       nhan: " + repr(got))


def refusal(name: str, fn, want: str) -> None:
    """The call must raise FormulaError carrying exactly this sentence."""
    try:
        fn()
    except ValueError as exc:
        if not isinstance(exc, FormulaError):
            failures.append(name)
            print("  BAD " + name)
            print("       muon loai: FormulaError")
            print("       nhan loai: " + type(exc).__name__ + ": " + str(exc))
            return
        check(name, str(exc), want)
        return
    failures.append(name)
    print("  BAD " + name + "  (khong tu choi gi ca)")


def refusal_opens(name: str, fn, want_prefix: str) -> None:
    """Same, but the tail of the sentence is CPython's own wording.

    Only used where formula_engine re-raises a stdlib message it did not write
    (visit_Call line 92). Pinning CPython's half would make this file red on a
    Python upgrade for no reason; the Thai half is still matched exactly.
    """
    try:
        fn()
    except ValueError as exc:
        if isinstance(exc, FormulaError) and str(exc).startswith(want_prefix) and len(str(exc)) > len(want_prefix):
            print("  ok  " + name + "  (" + str(exc) + ")")
            return
        failures.append(name)
        print("  BAD " + name)
        print("       muon mo dau bang: " + repr(want_prefix))
        print("       nhan: " + type(exc).__name__ + ": " + repr(str(exc)))
        return
    failures.append(name)
    print("  BAD " + name + "  (khong tu choi gi ca)")


def pending_fix(name: str, fn, want_message: str, broken_today: str) -> None:
    """A KNOWN PRODUCTION BUG. Recorded as a defect, NEVER as correct behaviour.

    want_message  - the Thai sentence the user SHOULD get once it is fixed.
    broken_today  - what production hands back instead, written out literally
                    (a repr for a returned value, "Type: message" for a raise).

    While the bug is alive: CHUA SUA, and the run stays green - this file may not
    edit production, so red here would never clear. The moment production raises
    a FormulaError instead, the row goes BAD telling you to promote it into a
    real refusal(); that red takes ten seconds to clear and is the tracking
    mechanism a comment beside a green check can never be.
    """
    try:
        got = fn()
    except ValueError as exc:
        if isinstance(exc, FormulaError):
            failures.append(name)
            print("  BAD " + name + "  (SAN XUAT DA SUA - doi pending_fix() nay thanh refusal())")
            print("       nhan: " + str(exc))
            print("       du dinh luc viet test: " + want_message)
            return
        failures.append(name)
        print("  BAD " + name + "  (loi da doi hinh dang, van chua dung)")
        print("       nhan: " + type(exc).__name__ + ": " + str(exc))
        return
    except Exception as exc:  # noqa: BLE001 - the wrong exception IS the bug
        current = type(exc).__name__ + ": " + str(exc)
    else:
        current = repr(got)
    if current == broken_today:
        pending.append(name)
        print("  CHUA SUA " + name)
        print("       dang tra: " + current)
        print("       phai tra: FormulaError " + want_message)
        return
    failures.append(name)
    print("  BAD " + name + "  (loi da doi hinh dang, van chua dung)")
    print("       muon (khi con hong): " + broken_today)
    print("       nhan: " + current)


def accepts(name: str, fn) -> None:
    """The call must go through. Used where the point is 'this is allowed'."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - a raise here is the failure, not a crash
        failures.append(name)
        print("  BAD " + name)
        print("       tu choi: " + type(exc).__name__ + ": " + str(exc))
    else:
        print("  ok  " + name)


def ev(expression: str, variables=None):
    """evaluate_formula that never explodes the run - a raise becomes a value."""
    try:
        return evaluate_formula(expression, VARS if variables is None else variables)
    except Exception as exc:  # noqa: BLE001 - handed to check() so the run continues
        return type(exc).__name__ + ": " + str(exc)


def bag(**over):
    """The bag on every screenshot: 45 x 60 cm, 0.08 mm per pair, density 0.92.

    Every dimension is non-zero on purpose, so a variable probe measures whether
    the name EXISTS in the engine's dict, not whether it happens to be zero.
    """
    base = dict(
        product_key="flat",
        width_cm=45.0,
        length_cm=60.0,
        height_cm=150.0,
        gusset_cm=12.5,
        sold_length_m=300.0,
        bottom_allowance_cm=1.0,
        thickness_input_mm=0.08,
        thickness_mode="pair",
        density_g_cm3=0.92,
        roof_gsm=120.0,
        mesh_gsm=80.0,
        material_price_per_kg=65.0,
        markup_percent=0.0,
        deduction_percent=10.0,
        pack_quantity=100.0,
        sack_quantity=1000.0,
        order_quantity=1000.0,
        control_min_g=0.0,
        control_max_g=0.0,
        weight_formula=DEFAULT_WEIGHT_FORMULAS["flat"],
        price_formula=DEFAULT_PRICE_FORMULA,
    )
    base.update(over)
    return calculate(**base)


# ------------------------------------------------------------ L. sandbox escape
print("Escape attempts - a typed string must never reach anything but arithmetic")

ESCAPES = [
    # label,                  what the user types,        the sentence they get back
    ("attributeAccess", "width_cm.__class__", "ไม่อนุญาตให้ใช้ Attribute ในสูตร"),
    ("attributeCall", "width_cm.__class__(1)", "ฟังก์ชันนี้ไม่ได้รับอนุญาต"),
    ("dunderImport", "__import__('os')", "ฟังก์ชันนี้ไม่ได้รับอนุญาต"),
    ("openFile", "open('secrets.env')", "ฟังก์ชันนี้ไม่ได้รับอนุญาต"),
    ("subscript", "[1, 2][0]", "ไม่อนุญาตให้ใช้ Subscript ในสูตร"),
    ("lambdaExpression", "lambda: 1", "ไม่อนุญาตให้ใช้ Lambda ในสูตร"),
    ("ternary", "1 if width_cm else 2", "ไม่อนุญาตให้ใช้ IfExp ในสูตร"),
    ("comparison", "width_cm > 1", "ไม่อนุญาตให้ใช้ Compare ในสูตร"),
    ("booleanOperator", "width_cm and 1", "ไม่อนุญาตให้ใช้ BoolOp ในสูตร"),
    ("stringConstant", "'os'", "สูตรใช้ได้เฉพาะตัวเลข"),
    ("trueConstant", "True", "สูตรใช้ได้เฉพาะตัวเลข"),
    ("falseConstant", "False", "สูตรใช้ได้เฉพาะตัวเลข"),
    ("noneConstant", "None", "สูตรใช้ได้เฉพาะตัวเลข"),
    ("fstring", 'f"{width_cm}"', "ไม่อนุญาตให้ใช้ JoinedStr ในสูตร"),
    ("walrus", "(evil := 1)", "ไม่อนุญาตให้ใช้ NamedExpr ในสูตร"),
    ("listLiteral", "[1, 2]", "ไม่อนุญาตให้ใช้ List ในสูตร"),
    ("dictLiteral", "{1: 2}", "ไม่อนุญาตให้ใช้ Dict ในสูตร"),
    ("setLiteral", "{1, 2}", "ไม่อนุญาตให้ใช้ Set ในสูตร"),
    ("tupleLiteral", "(1, 2)", "ไม่อนุญาตให้ใช้ Tuple ในสูตร"),
    ("starredArgument", "max(*[1, 2])", "ไม่อนุญาตให้ใช้ Starred ในสูตร"),
    # The four comprehension forms. Each is its own AST node with its own
    # sentence, and they are the escapes most likely to be let back in by a
    # well-meaning "let people write ranges / sums" patch.
    ("listComprehension", "[x for x in (1, 2)]", "ไม่อนุญาตให้ใช้ ListComp ในสูตร"),
    ("generatorExpression", "(x for x in (1, 2))", "ไม่อนุญาตให้ใช้ GeneratorExp ในสูตร"),
    ("setComprehension", "{x for x in (1, 2)}", "ไม่อนุญาตให้ใช้ SetComp ในสูตร"),
    ("dictComprehension", "{x: x for x in (1, 2)}", "ไม่อนุญาตให้ใช้ DictComp ในสูตร"),
]
for _label, _expr, _want in ESCAPES:
    refusal(
        "evaluate_escapeAttempt_" + _label + "_refused",
        lambda e=_expr: evaluate_formula(e, VARS),
        _want,
    )

print("Operators outside the four arithmetic ones")
OPERATORS = [
    ("floorDivide", "5 // 2"),
    # The divide-by-zero guard covers Div and Mod only. // 0 never divides at all:
    # it dies on the operator itself, so no ZeroDivisionError can escape.
    ("floorDivideByZero", "5 // 0"),
    ("matrixMultiply", "2 @ 3"),
    ("bitAnd", "6 & 3"),
    ("leftShift", "1 << 2"),
    ("bitwiseNot", "~5"),
    ("logicalNot", "not 1"),
]
for _label, _expr in OPERATORS:
    refusal(
        "evaluate_" + _label + "_refused",
        lambda e=_expr: evaluate_formula(e, VARS),
        "เครื่องหมายนี้ไม่รองรับ",
    )

print("Function and variable names the engine does not know")
refusal(
    "evaluate_unknownFunction_refusedByMessage",
    lambda: evaluate_formula("foo(1)", VARS),
    "ฟังก์ชันนี้ไม่ได้รับอนุญาต",
)
refusal(
    "evaluate_builtinNotOnTheList_sum_refused",
    lambda: evaluate_formula("sum(1)", VARS),
    "ฟังก์ชันนี้ไม่ได้รับอนุญาต",
)
refusal(
    "evaluate_namedArgument_refused",
    lambda: evaluate_formula("round(2.345, digits=1)", VARS),
    "สูตรไม่รองรับ named arguments",
)
refusal(
    "evaluate_namedArgumentOnAllowedFunction_max_refused",
    lambda: evaluate_formula("max(1, key=2)", VARS),
    "สูตรไม่รองรับ named arguments",
)
refusal(
    "evaluate_unknownVariable_namesTheVariable",
    lambda: evaluate_formula("foo", VARS),
    "ไม่รู้จักตัวแปร: foo",
)
refusal(
    "evaluate_unknownVariableAfterAKnownOne_stillNamesIt",
    lambda: evaluate_formula("width_cm + foo", VARS),
    "ไม่รู้จักตัวแปร: foo",
)

# ---------------------------------------------------------- M. numeric blow-ups
print("Numbers that would blow up - each guard on its own boundary")

refusal(
    "evaluate_divideByZero_refused",
    lambda: evaluate_formula("1 / 0", VARS),
    "สูตรหารด้วยศูนย์",
)
refusal(
    "evaluate_divideByZeroReachedByArithmetic_refused",
    lambda: evaluate_formula("width_cm / (1 - 1)", VARS),
    "สูตรหารด้วยศูนย์",
)
refusal(
    "evaluate_moduloByZero_refused",
    lambda: evaluate_formula("5 % 0", VARS),
    "สูตรหารด้วยศูนย์",
)

refusal(
    "evaluate_powExponent9_refused",
    lambda: evaluate_formula("2 ** 9", VARS),
    "เลขยกกำลังเกินขอบเขตที่อนุญาต",
)
refusal(
    "evaluate_powExponentMinus9_refused",
    lambda: evaluate_formula("2 ** -9", VARS),
    "เลขยกกำลังเกินขอบเขตที่อนุญาต",
)
# The guard is `abs(right) > 8`, so 8 itself is legal. Prove it on both signs.
check("evaluate_powExponent8_allowed", ev("2 ** 8"), 256.0)
check("evaluate_powExponentMinus8_allowed", ev("2 ** -8"), 0.00390625)

# The same line also guards the BASE: abs(left) > 1_000_000.
check("evaluate_powBase1000000_allowed", ev("1000000 ** 2"), 1000000000000.0)
refusal(
    "evaluate_powBase1000001_refused",
    lambda: evaluate_formula("1000001 ** 2", VARS),
    "เลขยกกำลังเกินขอบเขตที่อนุญาต",
)
refusal(
    "evaluate_powBaseNegative1000001_refusedBecauseGuardTakesAbs",
    lambda: evaluate_formula("(0 - 1000001) ** 2", VARS),
    "เลขยกกำลังเกินขอบเขตที่อนุญาต",
)

# abs(result) > 1e15 on every BinOp. 1e15 exactly is still in.
check("evaluate_resultExactly1e15_allowed", ev("1e14 * 10"), 1000000000000000.0)
refusal(
    "evaluate_resultAbove1e15_refused",
    lambda: evaluate_formula("1e15 * 10", VARS),
    "ผลลัพธ์อยู่นอกช่วงที่รองรับ",
)
refusal(
    "evaluate_resultOverflowsToInfinity_refused",
    lambda: evaluate_formula("1e308 * 10", VARS),
    "ผลลัพธ์อยู่นอกช่วงที่รองรับ",
)
refusal(
    "evaluate_functionResultInfinite_refused",
    lambda: evaluate_formula("abs(1e400)", VARS),
    "ผลลัพธ์ไม่ใช่ตัวเลขที่ใช้ได้",
)
# ------------------------------------------- the hole in visit_Constant
print("KNOWN PRODUCTION BUGS - one line, three ways through it")
# formula_engine.py:38-41 asks only what TYPE a literal is. Every guard above
# lives in visit_BinOp or visit_Call, so a formula that is NOTHING BUT a literal
# is never guarded at all: not for magnitude, not for finiteness, not for whether
# float() can hold it. None of these three is asserted as correct behaviour.

# 1. inf. calculate() then reads inf > 0 as a perfectly good weight in grams.
pending_fix(
    "evaluate_bareInfinityLiteral_shouldBeRefused",
    lambda: evaluate_formula("1e400", VARS),
    "ผลลัพธ์อยู่นอกช่วงที่รองรับ",
    "inf",
)
# 2. finite, but 1e293 times the result cap the very next line enforces. A fix
#    that only adds math.isfinite() to visit_Constant leaves this one open, which
#    is exactly why it gets its own row.
pending_fix(
    "evaluate_bareHugeFiniteLiteral_shouldBeRefusedByThe1e15Cap",
    lambda: evaluate_formula("9" * 308, VARS),
    "ผลลัพธ์อยู่นอกช่วงที่รองรับ",
    "1e+308",
)
# 3. The worst of the three, and the reason this section exists. One more digit
#    and it is an INTEGER literal too big for float(): line 41 raises
#    OverflowError, which is an ArithmeticError, NOT a ValueError, so it is not a
#    FormulaError. main.py catches only (ValueError, FormulaError,
#    ZeroDivisionError, KeyError) at :751, :771 and :2496 - so the CEO gets an
#    HTTP 500 and a stack trace where every other bad formula gives a Thai 400.
HUGE_INT = "9" * 309
check("evaluate_hugeIntegerLiteral_lengthIs309_wellInsideThe500Cap", len(HUGE_INT), 309)
pending_fix(
    "evaluate_hugeIntegerLiteral_shouldBeRefusedNotOverflowError",
    lambda: evaluate_formula(HUGE_INT, VARS),
    "ผลลัพธ์อยู่นอกช่วงที่รองรับ",
    "OverflowError: int too large to convert to float",
)
# It escapes from inside a normal formula just as easily - the operands are
# visited before visit_BinOp gets to guard anything.
pending_fix(
    "evaluate_hugeIntegerLiteralInsideABinOp_shouldBeRefusedNotOverflowError",
    lambda: evaluate_formula("9" * 309 + " + 1", VARS),
    "ผลลัพธ์อยู่นอกช่วงที่รองรับ",
    "OverflowError: int too large to convert to float",
)
# 308 nines is the last width that still fits a float, so the row above is the
# boundary and not an arbitrary big number.
check("evaluate_hugeIntegerLiteral_308NinesStillFitsAFloat", len("9" * 308), 308)

# --------------------------------------------------------------- N. bad input
print("Broken input - empty, too long, unparseable")

for _label, _expr in [("empty", ""), ("spacesOnly", "   "), ("newlineAndTab", "\n\t ")]:
    refusal(
        "evaluate_" + _label + "Formula_refused",
        lambda e=_expr: evaluate_formula(e, VARS),
        "กรุณากรอกสูตร",
    )
# The blank test runs BEFORE the length test, so whitespace stays "fill in a
# formula" no matter how much of it there is.
refusal(
    "evaluate_600SpacesOnly_refusedAsEmptyNotAsTooLong",
    lambda: evaluate_formula(" " * 600, VARS),
    "กรุณากรอกสูตร",
)

TOO_LONG = "1+" * 250 + "1"
check("evaluate_over500Chars_lengthIs501", len(TOO_LONG), 501)
refusal(
    "evaluate_over500Chars_refused",
    lambda: evaluate_formula(TOO_LONG, VARS),
    "สูตรยาวเกินไป",
)
# Length is measured before ast.parse, so 501 unbalanced brackets are "too long",
# never "bad syntax". That ordering is what stops a huge string being parsed.
refusal(
    "evaluate_over500CharsAndUnparseable_refusedAsTooLongNotAsSyntax",
    lambda: evaluate_formula("(" * 501, VARS),
    "สูตรยาวเกินไป",
)

EXACTLY_500 = "1+" * 249 + "11"  # 249 ones + 11 = 260
check("evaluate_exactly500Chars_lengthIs500", len(EXACTLY_500), 500)
check("evaluate_exactly500Chars_accepted", ev(EXACTLY_500), 260.0)

for _label, _expr in [("danglingPlus", "1 +"), ("openBracket", "(1"), ("twoNumbers", "1 2")]:
    refusal(
        "evaluate_syntaxError_" + _label + "_refused",
        lambda e=_expr: evaluate_formula(e, VARS),
        "รูปแบบสูตรไม่ถูกต้อง",
    )

# ------------------------------------------------------- O. the seven functions
print("The seven allowed functions still do their job")

FUNCTIONS = [
    ("abs_minus3point5", "abs(-3.5)", 3.5),
    ("min_of_3_7_2", "min(3, 7, 2)", 2.0),
    ("max_of_3_7_2", "max(3, 7, 2)", 7.0),
    # Python rounds half to EVEN. 2.5 goes down to 2, 3.5 goes up to 4.
    ("round_2point5_halfToEven", "round(2.5)", 2.0),
    ("round_3point5_halfToEven", "round(3.5)", 4.0),
    ("round_pi_to2Digits", "round(3.14159, 2)", 3.14),
    ("ceil_2point1", "ceil(2.1)", 3.0),
    ("ceil_minus2point1", "ceil(-2.1)", -2.0),
    ("floor_2point9", "floor(2.9)", 2.0),
    ("floor_minus2point1", "floor(-2.1)", -3.0),
    ("sqrt_16", "sqrt(16)", 4.0),
    ("sqrt_2", "sqrt(2)", 1.4142135623730951),
    ("nested_max_min_sqrt", "max(min(5, 3), sqrt(4))", 3.0),
    ("round_ofAVariable", "round(width_cm / 7, 3)", 6.429),
]
for _label, _expr, _want in FUNCTIONS:
    check("evaluate_allowedFunction_" + _label, ev(_expr), _want)

print("round() guards its digit argument")
ROUND_MSG = "ใช้ฟังก์ชันไม่ถูกต้อง: จำนวนตำแหน่งทศนิยมต้องเป็นจำนวนเต็มระหว่าง -10 ถึง 10"
refusal(
    "evaluate_roundWithNonIntegerDigits_refused",
    lambda: evaluate_formula("round(2.345, 1.5)", VARS),
    ROUND_MSG,
)
refusal(
    "evaluate_roundWithNonIntegerNegativeDigits_refused",
    lambda: evaluate_formula("round(2.345, -0.5)", VARS),
    ROUND_MSG,
)
refusal(
    "evaluate_roundDigits11_refused",
    lambda: evaluate_formula("round(2.345, 11)", VARS),
    ROUND_MSG,
)
refusal(
    "evaluate_roundDigitsMinus11_refused",
    lambda: evaluate_formula("round(2.345, -11)", VARS),
    ROUND_MSG,
)
# -10 and 10 are inside the range the message names, so they must work.
check("evaluate_roundDigits10_allowed", ev("round(1234.5, 10)"), 1234.5)
check("evaluate_roundDigitsMinus10_allowed", ev("round(1234.5, -10)"), 0.0)

refusal_opens(
    "evaluate_sqrtOfNegative_refusedWithThaiPrefix",
    lambda: evaluate_formula("sqrt(-1)", VARS),
    "ใช้ฟังก์ชันไม่ถูกต้อง: ",
)

print("Unary + and - are the two signs that ARE supported")
check("evaluate_unaryMinusOnLiteral_supported", ev("-5"), -5.0)
check("evaluate_unaryPlusOnLiteral_supported", ev("+5"), 5.0)
check("evaluate_doubleUnaryMinus_supported", ev("--5"), 5.0)
check("evaluate_unaryMinusOnVariable_supported", ev("-width_cm"), -45.0)

# ------------------------------------- P. custom formulas inside calculate()
print("A custom formula plugged into the real calculation")

refusal(
    "calculate_customWeightFormulaYieldingZero_refused",
    lambda: bag(weight_formula="width_cm * 0"),
    "สูตรน้ำหนักต้องให้ผลมากกว่า 0 กรัม",
)
refusal(
    "calculate_customWeightFormulaYieldingNegative_refused",
    lambda: bag(weight_formula="0 - width_cm"),
    "สูตรน้ำหนักต้องให้ผลมากกว่า 0 กรัม",
)
refusal(
    "calculate_customPriceFormulaNegative_refused",
    lambda: bag(price_formula="grams_per_item * -1"),
    "สูตรราคาต้องไม่ให้ผลติดลบ",
)

# The two guards are deliberately NOT symmetric, and zero is where the money is.
# Weight: calculator.py:203 is `grams <= 0`  -> zero is REFUSED (rows above).
# Price:  calculator.py:207 is `price < 0`   -> zero is ALLOWED, and ships.
# Pinned as literals so the day someone tightens one of them, the row that moves
# names which one. A 0 baht quote leaving the building is a business decision,
# not an accident of an off-by-one, and this file is where that decision is
# written down.
_free = bag(price_formula="grams_per_item * 0")
check("calculate_customPriceFormulaYieldingExactlyZero_allowed_unitPriceIs0", _free.unit_price, 0.0)
check("calculate_customPriceFormulaYieldingExactlyZero_allowed_totalPriceIs0", _free.total_price, 0.0)
check(
    "calculate_customPriceFormulaYieldingExactlyZero_allowed_pricePerKgIs0",
    _free.selling_price_per_kg,
    0.0,
)
# The same 0 baht quote with no custom formula at all: markup -100 collapses the
# shipped price formula's (1 + markup_percent / 100) to zero. calculator.py:145
# raises only on markup < -100, so -100 exactly is a legal input.
# (The refusal at -100.1 is pinned in tests/test_pricing_rules.py, not repeated.)
_minus100 = bag(markup_percent=-100.0)
check("calculate_markupMinus100_defaultPriceFormula_unitPriceIs0", _minus100.unit_price, 0.0)
check("calculate_markupMinus100_defaultPriceFormula_totalPriceIs0", _minus100.total_price, 0.0)
# Half that markup is not a special case - it is just half the price. Proof that
# the zero above comes from the boundary and not from a dead formula.
close("calculate_markupMinus50_defaultPriceFormula_unitPriceIs0point6566040", bag(markup_percent=-50.0).unit_price, 0.656604, 1e-9)

# The same bag three ways. Default first, so the two custom lines below are
# provably NOT the default answer.
#   default weight = 45 * 61 * 2 * (0.04/10) * 0.92 = 20.2032 g
#   custom drops the "* 2" (one layer, not a folded bag)
#            = 45 * 61 * (0.04/10) * 0.92 = 2745 * 0.004 = 10.98; * 0.92 = 10.1016 g
close("calculate_defaultWeightFormula_gives20point2032", bag().grams_per_item, 20.2032, 1e-12)
close(
    "calculate_customWeightFormula_usedInsteadOfDefault_gives10point1016",
    bag(weight_formula="width_cm * material_length_cm * (thickness_side_mm / 10) * density_g_cm3").grams_per_item,
    10.1016,
    1e-12,
)
# And the price formula is equally replaceable: 2 x 20.2032 = 40.4064 THB/piece.
close(
    "calculate_customPriceFormula_usedInsteadOfDefault_gives40point4064",
    bag(price_formula="grams_per_item * 2").unit_price,
    40.4064,
    1e-12,
)

# ------------------------------------------- the variable list must not lie
print("The variable list on screen, against the dict calculate() really builds")

# The list the CEO reads in the Formula Variables window (main.py:726 and :732),
# written out by hand. NOT `sorted(FORMULA_VARIABLES)` compared against itself:
# a name added, renamed or dropped in calculator.py must turn this row red and
# make somebody say out loud whether the screen text was updated too.
DOCUMENTED_VARIABLES = (
    "bottom_allowance_cm",
    "deduction_percent",
    "density_g_cm3",
    "grams_per_item",
    "gusset_cm",
    "height_cm",
    "length_cm",
    "markup_percent",
    "material_length_cm",
    "material_price_per_kg",
    "mesh_area_cm2",
    "mesh_area_m2",
    "mesh_gsm",
    "pack_quantity",
    "roof_area_cm2",
    "roof_area_m2",
    "roof_gsm",
    "sold_length_m",
    "thickness_input_mm",
    "thickness_pair_mm",
    "thickness_side_mm",
    "width_cm",
)
check("formulaVariables_documentedList_is22Names", len(FORMULA_VARIABLES), 22)
check(
    "formulaVariables_documentedList_matchesTheNamesWrittenHere",
    tuple(sorted(FORMULA_VARIABLES)),
    DOCUMENTED_VARIABLES,
)

print("  every documented variable really exists when a formula runs")
# Probed through the PRICE slot, which is the only point where the engine's dict
# is complete (grams_per_item is added at calculator.py:205, after the weight
# formula has already run). "<name> * 0 + 1" isolates existence from value: an
# unknown name raises, a known one gives 1 whatever it holds.
for _name in sorted(FORMULA_VARIABLES):
    accepts(
        "calculate_" + _name + "_suppliedToTheFormulaEngine",
        lambda n=_name: bag(price_formula=n + " * 0 + 1"),
    )

# Two asymmetries between the documented list and the engine's dict. Both are
# live-path facts, taken through calculate(), not through the unused validator.
# sack_quantity is handed to the engine (calculator.py:196) but is NOT on the
# list above, so it works and nobody is told it exists.
accepts(
    "calculate_sackQuantity_suppliedByEngineThoughNotOnTheDocumentedList",
    lambda: bag(price_formula="sack_quantity * 0 + 1"),
)
# grams_per_item is the mirror image: on the list, but only added at
# calculator.py:205, after the weight formula has already run. Documented, and
# unusable in the very slot a reader would first try it in.
refusal(
    "calculate_gramsPerItemInAWeightFormula_refusedBecauseItIsNotKnownYet",
    lambda: bag(weight_formula="grams_per_item"),
    "ไม่รู้จักตัวแปร: grams_per_item",
)

# ------------------------------- the shipped defaults, through the real path
print("Every shipped default weight formula, run by calculate() for its product")
# The same bag geometry through each product's own default formula, worked out by
# hand from calculator.py:38-46. This is what "the defaults are valid" has to
# mean: the numbers they produce, not that a helper nobody calls accepts them.
#   gusset: (45 + 12.5) * 61 * 2 * (0.04/10) * 0.92          = 25.8152 g
#   roll:   45 * 300 * 100 * 2 * (0.04/10) * 0.92            = 9936.0 g
#   opaque: 45 * 60 * (0.04/10) * 0.92   (one layer, no * 2) = 9.936 g
#   sleeve: 45 * 60 * 2 * (0.04/10) * 0.92 (no bottom allowance) = 19.872 g
#   cover:  roof 46*61 = 2806 cm2 -> 0.2806 m2 * 120         = 33.672 g
#           mesh ((45+60)*2+4) * 151 = 32314 cm2 -> 3.2314 m2 * 80 = 258.512 g
#                                                              = 292.184 g
# flat (20.2032 g) is pinned above, from the other direction.
for _key, _want_grams in (
    ("gusset", 25.8152),
    ("roll", 9936.0),
    ("opaque", 9.936),
    ("sleeve", 19.872),
    ("cover", 292.184),
):
    close(
        "calculate_defaultWeightFormula_" + _key + "_gives" + repr(_want_grams).replace(".", "point"),
        bag(product_key=_key, weight_formula=DEFAULT_WEIGHT_FORMULAS[_key]).grams_per_item,
        _want_grams,
        1e-9,
    )
# A product shipped without its own default formula would fall back to
# somebody else's geometry, so the set of keys is pinned by name, not counted.
check(
    "calculate_defaultWeightFormulas_oneNamedFormulaPerProduct",
    tuple(sorted(DEFAULT_WEIGHT_FORMULAS)),
    ("cover", "flat", "gusset", "opaque", "roll", "sleeve"),
)

# ---------------------------------- validate_formula: a helper nobody calls
print("validate_formula - correct, and unused by the server (see the docstring)")
# grep over the repo: defined at formula_engine.py:114, called only from here.
# These rows prove the helper behaves; they prove NOTHING about the running
# server, which validates no formula at all before saving or using it.
refusal(
    "validateFormula_variableOutsideAllowedSet_refused",
    lambda: validate_formula("width_cm * foo", set(FORMULA_VARIABLES)),
    "ไม่รู้จักตัวแปร: foo",
)
refusal(
    "validateFormula_pythonBuiltinIsNotAVariable_refused",
    lambda: validate_formula("width_cm * len", set(FORMULA_VARIABLES)),
    "ไม่รู้จักตัวแปร: len",
)
# Not asserted here: "every documented name passes the validator". validate_formula
# builds its sample dict FROM the set it is handed (formula_engine.py:115), so
# feeding it one name out of that same set is `x in x` - it passes for invented
# names too. The real claim is the loop above, through calculate().
for _key in sorted(DEFAULT_WEIGHT_FORMULAS):
    accepts(
        "validateFormula_defaultWeightFormula_" + _key + "_usesOnlyDocumentedNames",
        lambda f=DEFAULT_WEIGHT_FORMULAS[_key]: validate_formula(f, set(FORMULA_VARIABLES)),
    )
accepts(
    "validateFormula_defaultPriceFormula_usesOnlyDocumentedNames",
    lambda: validate_formula(DEFAULT_PRICE_FORMULA, set(FORMULA_VARIABLES)),
)

print()
if failures:
    print("HONG: " + str(len(failures)) + " kiem tra do - " + ", ".join(failures))
    if pending:
        print("       (con " + str(len(pending)) + " loi san xuat chua sua: " + ", ".join(pending) + ")")
    sys.exit(1)
if pending:
    print("CHU Y: " + str(len(pending)) + " LOI SAN XUAT CHUA SUA, khong phai hanh vi dung:")
    for _name in pending:
        print("   - " + _name)
    print("   Ca " + str(len(pending)) + " deu o formula_engine.py:38-41 (visit_Constant).")
    print()
print("KHOP: o nhap sutra chi lam duoc phep tinh, va danh sach bien tren man hinh khong noi doi.")
