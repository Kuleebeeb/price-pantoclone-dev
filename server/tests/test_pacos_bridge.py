# -*- coding: utf-8 -*-
"""UNIT: what leaves for PacOs is the row in millimetres, and never a guess.

No network, no database. Pinned:

  - a web-saved row travels from its `normalized` block: mm, thickness basis
    from the mode, the datum, the seal allowance, kg price from the results
  - a row synced from the .exe (dimensions nested, inches) converts at this
    edge (LAW P11) and PacOs never sees an inch
  - a row read off the paper books carries its resin word and whatever it
    had; what it lacked stays 0 and blank - PacOs names the gap, we do not
    invent one
  - a roll carries metres, not a bag length
  - ticked rows travel only as ONE customer, by code; a row with no code is
    named; two codes are refused
  - old names earn a PacOs code only when exactly one PacOs customer matches
  - PacOs's refusals and absence become BridgeError with its status
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
from datetime import date
from email.message import Message
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "core"))
sys.path.insert(0, str(HERE / "api"))

# Forced, not defaulted: inside the production image these are the real
# address and the real key, and a test that read them would compare its
# stand-in against the live server's settings.
os.environ["PACOS_URL"] = "http://pacos.test"
os.environ["PACOS_BRIDGE_KEY"] = "k" * 40

import pacos_bridge as pb  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, detail="") -> None:
    if cond:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name + "  " + str(detail))


def web_row(**over):
    row = {
        "quote_ref": "QT-20260828-0012", "quote_date": date(2026, 8, 28), "customer": "DAIKIN INDUSTRIES (THAILAND) CO., LTD.",
        "customer_code": "DAIKIN", "item_description": "PLASTIC BAG PE 12 x 18", "product_reference": "HN-4471",
        "product_key": "flat", "size_text": "กว้าง/Width 12 นิ้ว × ยาว/Length 18 นิ้ว", "length_reference": "",
        "unit_price": 1.0, "grams_per_item": 12.82, "pack_quantity": 100,
        "inputs_json": {
            "product_key": "flat",
            "width": {"value": 12, "unit": "นิ้ว"}, "length": {"value": 18, "unit": "นิ้ว"},
            "thickness": {"value": 50, "unit": "ไมครอน", "mode": "pair"},
            "bottom_allowance": {"value": 1, "unit": "ซม."},
            "length_reference": "opening_to_seal", "density_g_cm3": 0.92, "sale_basis": "kg",
            "order_quantity": 5000, "previous_price": 71,
            "normalized": {"width_cm": 30.48, "length_cm": 45.72, "thickness_input_mm": 0.05, "bottom_allowance_cm": 1.0},
        },
        "results_json": {"grams_per_item": 12.82, "unit_price": 1.0, "selling_price_per_kg": 78},
    }
    row.update(over)
    return row


# ------------------------------------------------------------- web row
line = pb.line_from_row(web_row())
check("web row: reference, date, kind, name, part code, size", (line["ref"], line["quote_date"], line["product_key"], line["product_name"], line["part_code"]) == ("QT-20260828-0012", "2026-08-28", "flat", "PLASTIC BAG PE 12 x 18", "HN-4471"), line)
check("web row: millimetres from the normalized block", (line["width_mm"], line["length_mm"], line["thickness_mm"]) == (304.8, 457.2, 0.05), line)
check("web row: thickness basis from the mode", line["thickness_basis"] == "per_pair", line["thickness_basis"])
check("web row: datum and seal allowance", (line["length_datum"], line["seal_allowance_mm"]) == ("to_seal", 10.0), line)
check("web row: sold by kg, the kg price travels", (line["sale_basis"], line["unit_price"]) == ("kg", 78.0), line)
check("web row: density, quantity, pack, grams, previous price", (line["density_g_cm3"], line["order_quantity"], line["pack_quantity"], line["grams_per_item"], line["previous_price"]) == (0.92, 5000.0, 100.0, 12.82, 71.0), line)
check("web row: no resin word on a web row", line["resin"] == "")

piece = pb.line_from_row(web_row(inputs_json={**web_row()["inputs_json"], "sale_basis": "piece"}, unit_price=1.2))
check("sold by piece, the piece price travels", (piece["sale_basis"], piece["unit_price"]) == ("piece", 1.2), piece)

# --------------------------------------------------------- .exe row
exe = web_row(inputs_json={
    "dimensions": {
        "width": {"value": 12, "unit": "นิ้ว"}, "length": {"value": 18, "unit": "นิ้ว"},
        "thickness": {"value": 0.05, "unit": "มม.", "mode": "side"},
    },
    "length_reference": "opening_to_bottom", "density_g_cm3": 0.95, "sale_basis": "piece", "order_quantity": 100,
})
line = pb.line_from_row(exe)
check(".exe row: inches nested under dimensions become millimetres", (line["width_mm"], line["length_mm"]) == (304.8, 457.2), line)
check(".exe row: thickness in mm per side", (line["thickness_mm"], line["thickness_basis"]) == (0.05, "per_side"), line)
check(".exe row: to the bottom", line["length_datum"] == "to_bottom")
check(".exe row: no allowance block, 0 - not invented", line["seal_allowance_mm"] == 0.0)

# --------------------------------------------------------- paper row
paper = web_row(quote_ref="2564/01-01 · Book", product_reference="", unit_price=66.0, results_json={"grams_per_item": 0}, grams_per_item=0, inputs_json={
    "width": {"value": 12, "unit": "นิ้ว"}, "length": {"value": 18, "unit": "นิ้ว"},
    "thickness": {"value": 40, "unit": "ไมครอน"}, "density_g_cm3": 0.0,
    "product_name": "PLASTIC BAG PE", "resin": "HDPE", "extraction_status": "parsed",
})
line = pb.line_from_row(paper)
check("paper row: the resin word travels", line["resin"] == "HDPE")
check("paper row: product name from the extraction", line["product_name"] == "PLASTIC BAG PE")
check("paper row: microns to millimetres, basis blank (nobody said)", (line["thickness_mm"], line["thickness_basis"]) == (0.04, ""), line)
check("paper row: no datum on the paper stays blank (LAW P13)", line["length_datum"] == "")
check("paper row: no sale basis and no kg figure - by the piece, the row's price", (line["sale_basis"], line["unit_price"]) == ("piece", 66.0), line)

# --------------------------------------------------------------- roll
roll = web_row(product_key="roll", inputs_json={
    "width": {"value": 60, "unit": "ซม."}, "sold_length": {"value": 300, "unit": "เมตร"},
    "thickness": {"value": 0.03, "unit": "มม.", "mode": "side"}, "density_g_cm3": 0.92, "sale_basis": "kg",
    "normalized": {"width_cm": 60, "sold_length_m": 300, "thickness_input_mm": 0.03},
})
line = pb.line_from_row(roll)
check("roll: metres travel as metres, no bag length", (line["roll_length_m"], line["length_mm"], line["width_mm"]) == (300.0, 0.0, 600.0), line)

# ----------------------------------------------------- the selection
rows = [web_row(quote_ref="A-1"), web_row(quote_ref="A-2")]
payload = pb.build_handoff(rows, "CEO@Pantong.test ")
check("one customer, two lines, the e-mail lower-cased", (payload["customer_code"], payload["created_by_email"], len(payload["lines"]), payload["source"]) == ("DAIKIN", "ceo@pantong.test", 2, "pantongone"), payload)
check("the customer's name as written on the row", payload["customer_name"] == "DAIKIN INDUSTRIES (THAILAND) CO., LTD.")

try:
    pb.build_handoff([web_row(quote_ref="A-1"), web_row(quote_ref="H-1", customer_code="honda")], "x@y")
    check("two customers are refused", False)
except pb.SelectionError as exc:
    check("two customers are refused, as a set", exc.code == "mixed_customers", exc.code)
try:
    pb.build_handoff([web_row(quote_ref="A-1"), web_row(quote_ref="N-4", customer_code="  ")], "x@y")
    check("a row with no code is refused", False)
except pb.SelectionError as exc:
    check("a row with no code is refused and named", (exc.code, exc.ref) == ("no_customer_code", "N-4"), (exc.code, exc.ref))
try:
    pb.build_handoff([], "x@y")
    check("nothing ticked", False)
except pb.SelectionError as exc:
    check("nothing ticked is refused", exc.code == "none")
try:
    pb.build_handoff([web_row(quote_ref="A-%d" % i) for i in range(51)], "x@y")
    check("51 rows", False)
except pb.SelectionError as exc:
    check("more than 50 rows is refused", exc.code == "too_many")
check("codes are matched case-blind: DAIKIN and daikin are one customer",
      pb.build_handoff([web_row(quote_ref="A-1"), web_row(quote_ref="A-2", customer_code="daikin")], "x@y")["customer_code"] == "DAIKIN")

# ----------------------------------------------------- old names to codes
customers = [
    {"pacos_id": "c1", "code": "DAIKIN", "name": "DAIKIN INDUSTRIES (THAILAND) CO., LTD.", "name_th": ""},
    {"pacos_id": "c2", "code": "HONDA", "name": "Honda Automobile (Thailand) Co., Ltd.", "name_th": "บริษัท ฮอนด้า ออโตโมบิล (ประเทศไทย) จำกัด"},
    {"pacos_id": "c3", "code": "TWIN1", "name": "Twin Co., Ltd.", "name_th": ""},
    {"pacos_id": "c4", "code": "TWIN2", "name": "TWIN CO.,LTD.", "name_th": ""},
]
got = pb.match_codes([
    "Daikin Industries (Thailand) Co.,Ltd.", "daikin industries thailand co ltd", "บริษัท ฮอนด้า ออโตโมบิล (ประเทศไทย) จำกัด",
    "Twin Co Ltd", "Nobody Ltd",
], customers)
check("punctuation, case and spacing do not make two names", got.get("Daikin Industries (Thailand) Co.,Ltd.") == "DAIKIN" and got.get("daikin industries thailand co ltd") == "DAIKIN", got)
check("the Thai name counts too", got.get("บริษัท ฮอนด้า ออโตโมบิล (ประเทศไทย) จำกัด") == "HONDA", got)
check("a name two PacOs customers share earns nothing", "Twin Co Ltd" not in got, got)
check("a name nobody has earns nothing", "Nobody Ltd" not in got, got)

# -------------------------------------------------------------- the wire
class FakeAnswer:
    def __init__(self, body): self._raw = json.dumps(body).encode()
    def read(self): return self._raw
    def __enter__(self): return self
    def __exit__(self, *a): return False


def http_error(code, body):
    return urllib.error.HTTPError("http://pacos.test/x", code, "no", Message(), io.BytesIO(json.dumps(body).encode()))


def opener_with(step, calls):
    def opener(req, timeout=None):
        calls.append(req)
        if isinstance(step, BaseException):
            raise step
        return FakeAnswer(step)
    return opener


calls: list = []
items = pb.fetch_customers(opener_with({"items": [{"id": "c1", "code": "DAIKIN", "name": "Daikin", "name_th": ""}, {"id": "", "code": "X", "name": "no id"}]}, calls))
check("customers: the key travels, the route is PacOs's, rows without an id are dropped",
      calls[0].get_header("X-bridge-key") == "k" * 40 and calls[0].full_url == "http://pacos.test/api/v1/bridge/customers" and items == [{"pacos_id": "c1", "code": "DAIKIN", "name": "Daikin", "name_th": ""}], (calls[0].full_url, items))

calls = []
hid = pb.push_handoff(payload, opener_with({"id": "h-1", "expires_in_hours": 24}, calls))
check("handoff: POSTed as JSON with the key, the id comes back", hid == "h-1" and calls[0].get_method() == "POST" and json.loads(calls[0].data)["customer_code"] == "DAIKIN")
check("handoff url is PacOs's screen for it", pb.handoff_url("h-1") == "http://pacos.test/quotations/from-pantongone/h-1")

for name, step, status in (
    ("401 wrong key", http_error(401, {"error": "That bridge key is not right."}), 401),
    ("503 bridge off", http_error(503, {"error": "not set up"}), 503),
    ("connection refused", urllib.error.URLError(ConnectionRefusedError(111, "refused")), 503),
    ("timeout", TimeoutError("timed out"), 503),
):
    try:
        pb.fetch_customers(opener_with(step, []))
        check(name + ": BridgeError", False)
    except pb.BridgeError as exc:
        check(name + f": BridgeError {status} with PacOs's sentence", exc.status == status and exc.message, (exc.status, exc.message))

# ------------------------------------------------------------- configured
os.environ["PACOS_BRIDGE_KEY"] = "short"
check("a short key means the bridge is off", not pb.configured() and "shorter" in pb.describe())
os.environ["PACOS_BRIDGE_KEY"] = "k" * 40
check("url + long key means on", pb.configured())

print()
if failures:
    print(f"KHONG KHOP - {len(failures)} sai: {failures}")
    sys.exit(1)
print("KHOP - dong di sang PacOs la dong that, tinh bang mm, khong bia them gi")
