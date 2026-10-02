# -*- coding: utf-8 -*-
"""UNIT: one tick per screen, checked on the server (permissions.py).

No network and no database. Pinned:

  - every /api route the app really has is covered by a rule, for every method
    it answers - walked from app.routes, so a route added without a rule turns
    this red instead of reaching production as a 403 for everybody
  - each screen's key opens that screen and nothing else; a key for one screen
    is refused on the next with a sentence naming the key to ask for
  - the drawing tab may read a quotation's form, but not its prices
  - AUTH_MODE=local holds every key (there is nobody to tick anything)
  - migration 0010 hands out exactly the keys this file defines
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "core"))
sys.path.insert(0, str(HERE / "api"))

os.environ["AUTH_MODE"] = "pacos"
os.environ.setdefault("PACOS_URL", "http://pacos.test")

import main  # noqa: E402
import permissions as P  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, detail="") -> None:
    if cond:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name + "  " + str(detail))


def who(*keys: str) -> dict:
    return {"id": 1, "email": "x@pantong.test", "permissions": [P.SIGN_IN, *keys]}


SAMPLE_VALUES = {"quote_ref": "2569/09-01", "report_id": "7", "coa_id": "7", "doc_no": "DFA-0001"}

print("every route has a rule")
seen = 0
for route in main.app.routes:
    path = getattr(route, "path", "")
    methods = getattr(route, "methods", None) or set()
    if not path.startswith("/api/") or path in main.OPEN_PATHS:
        continue
    concrete = re.sub(r"\{(\w+)(:\w+)?\}", lambda m: SAMPLE_VALUES.get(m.group(1), "x"), path)
    for method in sorted(methods - {"HEAD", "OPTIONS"}):
        seen += 1
        check(method + " " + path, P.required(method, concrete) is not None, "no rule")
check("walked a real route table", seen > 40, seen)

print("each screen opens with its own key, and only that one")
screens = {
    P.CALCULATE: ("POST", "/api/calculate"),
    P.SAVE: ("POST", "/api/quotations"),
    P.HISTORY: ("GET", "/api/history/tree/customers"),
    P.DELETE: ("DELETE", "/api/quotations/2569/09-01"),
    P.DRAWING: ("POST", "/api/drawings"),
    P.SAMPLE: ("DELETE", "/api/sample-inspections/7"),
    P.PLANNING: ("POST", "/api/work-orders/html"),
    P.COA: ("GET", "/api/coa/7/print"),
}
for key, (method, path) in screens.items():
    check(key + " opens " + path, P.refusal(method, path, who(key)) is None)
    for other in screens:
        if other == key:
            continue
        sentence = P.refusal(method, path, who(other))
        check(other + " is refused " + method + " " + path, bool(sentence) and key in sentence, sentence)

print("the door alone")
check("signed in is enough for /api/me", P.refusal("GET", "/api/me", who()) is None)
check("the door alone opens no screen", P.refusal("POST", "/api/calculate", who()) is not None)
check("HEAD is read as GET", P.refusal("HEAD", "/api/coa", who(P.COA)) is None)
check("a route with no rule is closed to everybody",
      "no permission rule" in (P.refusal("GET", "/api/new-thing", who(*P.PERMISSIONS)) or ""))
check("a paper-book reference with a slash still finds its rule",
      P.required("GET", "/api/quotations/2569/09-01/print") == frozenset({P.HISTORY}))
check("history does not open delete", P.refusal("DELETE", "/api/quotations/QT-1", who(P.HISTORY)) is not None)

print("a route that does not exist is FastAPI's 404, not a missing rule")


def asked(method: str, path: str):
    scope = {"type": "http", "method": method, "path": path, "root_path": "", "headers": [], "query_string": b""}
    return type("Q", (), {"scope": scope})()


check("GET /api/coa is a real route", main._route_answers(asked("GET", "/api/coa")))
check("a ref with a slash reaches its real route", main._route_answers(asked("GET", "/api/quotations/2569/09-01/print")))
check("DELETE /api/coa/7 is no route at all", not main._route_answers(asked("DELETE", "/api/coa/7")))
check("an unknown path is no route at all", not main._route_answers(asked("GET", "/api/new-thing")))

print("the quotation picker and the form serve the drawing tab too")
check("drawing may search quotations", P.refusal("GET", "/api/planning/sources", who(P.DRAWING)) is None)
check("drawing may read a form", P.refusal("GET", "/api/quotations/QT-1/form", who(P.DRAWING)) is None)
check("sample may not read a form", P.refusal("GET", "/api/quotations/QT-1/form", who(P.SAMPLE)) is not None)


class FakeRequest:
    def __init__(self, user):
        self.state = type("S", (), {"user": user})()


row = {
    "quote_ref": "QT-1", "quote_date": "2026-10-02", "customer": "A", "customer_code": "C1",
    "item_description": "BAG", "product_reference": "P1", "product_key": "flat", "length_reference": "",
    "inputs_json": {"material_price_per_kg": 70, "selling_price_per_kg_override": 99, "width": {"value": 10, "unit": "ซม."}},
    "formulas_json": {"price": "w * 2", "weight": "w"},
}
original_get = main.db.get_quotation
main.db.get_quotation = lambda ref: row
try:
    drawn = main.api_quotation_form("QT-1", FakeRequest(who(P.DRAWING)))["form"]
    priced = main.api_quotation_form("QT-1", FakeRequest(who(P.CALCULATE)))["form"]
finally:
    main.db.get_quotation = original_get
check("drawing gets no price field", not set(P.PRICE_FIELDS) & set(drawn), set(P.PRICE_FIELDS) & set(drawn))
check("drawing still gets the size", drawn.get("width") == "10", drawn.get("width"))
check("pricing gets every price field", set(P.PRICE_FIELDS) <= set(priced), set(P.PRICE_FIELDS) - set(priced))
check("the price that was saved comes back", priced.get("price_per_kg") == "99", priced.get("price_per_kg"))

print("local accounts")
os.environ["AUTH_MODE"] = "local"
check("local mode holds every key", P.held({"permissions": []}) == list(P.PERMISSIONS))
os.environ["AUTH_MODE"] = "pacos"
check("pacos mode holds what PacOs said", P.held(who(P.COA)) == [P.SIGN_IN, P.COA])

print("migration 0010 hands out exactly these keys")
sql = (HERE / "api" / "migrations" / "0010_one_tick_per_screen.sql").read_text(encoding="utf-8")
granted = re.findall(r'"(pricing\.\w+)"', sql)
check("0010 grants every screen key once", sorted(granted) == sorted(set(P.PERMISSIONS) - {P.SIGN_IN}), granted)

print()
if failures:
    print(f"KHONG KHOP - {len(failures)} sai: {failures}")
    sys.exit(1)
print("KHOP - moi route co luat, moi tab mo dung quyen cua no")
