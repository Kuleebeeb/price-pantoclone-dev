"""Who may open which screen, and which button on it.

WHY. Bee, 02-10-2026. Until today the only question asked was the one at the
door (pacos_gate.REQUIRED_PERMISSION): an account that could sign in could do
everything - work out a price, delete a quotation the company sent three
years ago, issue a COA. The program is now the quality office as well as the
price calculator, and the person who measures a sample is not the person who
should see what a bag costs (SRS 3).

WHERE THE TICKS LIVE. In PacOs, People > "Who is allowed to do what", under
`pricing` (PacOs migration 0138). The accounts are PacOs's, so the rights are
too: one place to switch a person on, off, or down. The sign-in answer carries
them and store.upsert_pacos_user keeps them on the users row, so a tick moved
in PacOs reaches this program at that person's next sign-in.

HOW IT IS CHECKED. On the server, per request, by RULES below - never by the
screen (LAW K1). The screen hides what a person may not use so they are not
sent into a refusal, and that is all it does.

CLOSED BY DEFAULT. A route under /api with no rule here is refused for
everybody, with a sentence that says so. A route added next month without a
rule is a loud 403 on the first click, not a door left open; and
tests/test_permissions.py walks every route the app has and fails while any
is missing.
"""

from __future__ import annotations

import re
from typing import Any

import pacos_gate

SIGN_IN = pacos_gate.REQUIRED_PERMISSION
CALCULATE = "pricing.calculate"
SAVE = "pricing.save"
HISTORY = "pricing.history"
DELETE = "pricing.delete"
DRAWING = "pricing.drawing"
SAMPLE = "pricing.sample_inspection"
PLANNING = "pricing.planning"
COA = "pricing.coa"

# Must match PacOs migration 0138 key for key: a key PacOs never hands out is a
# screen nobody can open, and nothing else would say so.
PERMISSIONS = (SIGN_IN, CALCULATE, SAVE, HISTORY, DELETE, DRAWING, SAMPLE, PLANNING, COA)

# Signed in is enough: who am I, is the bridge on.
ANYONE: frozenset[str] = frozenset()

# (methods, path, keys): the person needs ANY ONE of the keys. First match wins,
# so a longer path sits above the shorter one it starts with. HEAD is a GET.
_REF = r"[^?#]+"
RULES: list[tuple[frozenset[str], re.Pattern[str], frozenset[str]]] = [
    (frozenset(m.split()), re.compile(p), frozenset(k))
    for m, p, k in [
        ("GET", r"/api/me", ANYONE),
        ("GET", r"/api/bridge/status", ANYONE),
        # Customer names fill the box on the pricing form, the drawing and the
        # history filter. Names and codes only, never a price.
        ("GET", r"/api/customers", {CALCULATE, DRAWING, HISTORY}),
        # Pricing tab.
        ("POST", r"/api/calculate", {CALCULATE}),
        ("POST", r"/api/print/html", {CALCULATE}),
        ("POST", r"/api/quotations", {SAVE}),
        ("POST", r"/api/sync/quotations", {SAVE}),
        ("POST", r"/api/bridge/customers/sync", {SAVE}),
        # History tab: every price quoted before.
        ("GET", r"/api/history", {HISTORY}),
        ("GET", r"/api/history/tree/(customers|products|rows)", {HISTORY}),
        ("GET", r"/api/related/table", {HISTORY}),
        ("GET", r"/api/quotations", {HISTORY}),
        ("GET", r"/api/quotations/related", {HISTORY}),
        ("GET", r"/api/sync/quotations", {HISTORY}),
        ("POST", r"/api/bridge/handoffs", {HISTORY}),
        # The Edit button pours a record back into the pricing form; the drawing
        # tab pours the same record into a drawing. api_quotation_form takes the
        # price fields out for somebody without CALCULATE (PRICE_FIELDS).
        ("GET", r"/api/quotations/" + _REF + r"/form", {CALCULATE, DRAWING}),
        ("GET", r"/api/quotations/" + _REF + r"/(details|print)", {HISTORY}),
        ("GET", r"/api/quotations/" + _REF, {HISTORY}),
        ("DELETE", r"/api/quotations/" + _REF, {DELETE}),
        # The trash Delete moves a quotation into, and Restore out of it.
        ("GET", r"/api/history/trash", {DELETE}),
        ("POST", r"/api/quotations/" + _REF + r"/restore", {DELETE}),
        # Drawing tab.
        ("POST", r"/api/drawing(/html)?", {DRAWING}),
        ("GET POST", r"/api/drawings", {DRAWING}),
        ("GET", r"/api/drawings/" + _REF, {DRAWING}),
        ("GET POST", r"/api/sync/drawings", {DRAWING}),
        # The quotation picker: reference, customer, item and size - no price.
        # Planning and the drawing tab both search with it.
        ("GET", r"/api/planning/sources", {PLANNING, DRAWING}),
        ("GET", r"/api/planning/source", {PLANNING}),
        ("POST", r"/api/planning/compare", {PLANNING}),
        ("POST", r"/api/work-orders/html", {PLANNING}),
        # Sample Inspection.
        ("GET POST", r"/api/sample-inspections", {SAMPLE}),
        ("GET", r"/api/sample-inspections/sources", {SAMPLE}),
        ("DELETE", r"/api/sample-inspections/\d+", {SAMPLE}),
        ("GET", r"/api/sample-inspections/\d+/print", {SAMPLE}),
        # COA / Quality.
        ("GET POST", r"/api/coa", {COA}),
        ("DELETE", r"/api/coa/\d+", {COA}),
        ("GET", r"/api/coa/sources", {COA}),
        ("GET", r"/api/coa/\d+/print", {COA}),
    ]
]

# What the pricing form holds that is a price or the makings of one. Taken out
# of /form for somebody who may draw but may not price.
PRICE_FIELDS = (
    "material_price",
    "deduction",
    "apply_deduction",
    "sale_basis",
    "price_per_kg",
    "price_per_piece",
    "price_per_roll",
    "price_formula",
)


def held(user: dict[str, Any]) -> list[str]:
    """What this person may do here.

    With AUTH_MODE=local there is nobody to ask: the accounts are this
    service's own, made by whoever runs it, and there is no screen to tick
    anything on. They get every key, which is what every account had before
    permissions existed.
    """
    if pacos_gate.mode() == "local":
        return list(PERMISSIONS)
    return [str(key) for key in (user.get("permissions") or [])]


def required(method: str, path: str) -> frozenset[str] | None:
    """The keys that open this request, any one of them. None: no rule at all."""
    method = "GET" if method == "HEAD" else method
    for methods, pattern, keys in RULES:
        if method in methods and pattern.fullmatch(path):
            return keys
    return None


def refusal(method: str, path: str, user: dict[str, Any]) -> str | None:
    """The sentence to refuse with, or None to let the request through."""
    keys = required(method, path)
    if keys is None:
        return (
            "หน้านี้ยังไม่ได้กำหนดสิทธิ์ จึงปิดไว้ก่อน / this action has no permission rule yet, "
            "so it is closed to everybody (" + method + " " + path + ") - tell IT"
        )
    if not keys or set(keys) & set(held(user)):
        return None
    names = " or ".join(sorted(keys))
    return (
        "บัญชีนี้ไม่มีสิทธิ์ใช้ส่วนนี้ ขอสิทธิ์ " + names + " จากผู้ดูแลใน PacOs / "
        "this account may not do this - ask whoever manages accounts in PacOs for " + names
    )
