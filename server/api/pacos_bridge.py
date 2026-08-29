"""The bridge to PacOs: its customers come here, priced lines go there.

THE TRIP (Bee, 28-08-2026): work a price out and save it, tick several saved
rows in the history, press "create quotation", land in PacOs, put them on a
draft of that customer or on a new one. Both programs must agree on WHO the
customer is before a single price travels - so PacOs's customer list is
mirrored here, its CODE is the shared identity, and the code is written onto
every saved row: on new rows by the picker, on the 17,000 old rows by name.

WHAT LEAVES HERE is the row as this program understood it, in millimetres,
with the thickness basis, the length datum, the density and the price the CEO
settled on. PacOs prices it again its own way and keeps the CEO's figure as
the override with its provenance. Nothing here decides whether PacOs can quote
a line; PacOs says, per line, and the person reads it there before choosing.

MACHINE TO MACHINE, one shared key. PACOS_BRIDGE_KEY is compared by PacOs in
constant time; the person's own PacOs session then opens what was pushed - and
only theirs, because the handoff carries the e-mail this program signed them in
with, which is their PacOs e-mail (pacos_gate.py). Nothing here uses, stores or
forwards a PacOs password or token.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from typing import Any, Callable

from calculator import DIMENSION_FACTORS_TO_CM, THICKNESS_FACTORS_TO_MM

import db
import pacos_gate

TIMEOUT_SECONDS = 15
SYNC_EVERY_SECONDS = 15 * 60
MIN_KEY_LEN = 32
MAX_LINES = 50

Opener = Callable[..., Any]


class BridgeError(Exception):
    """PacOs refused or could not be reached. `status` is what PacOs said, or
    503 when it said nothing usable."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class SelectionError(Exception):
    """The ticked rows cannot travel together. `code` names the rule that
    refused them; the sentence lives in screen.py with the other words."""

    def __init__(self, code: str, ref: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.ref = ref


# ------------------------------------------------------------------ settings


def base_url() -> str:
    return pacos_gate.base_url()


def key() -> str:
    return os.environ.get("PACOS_BRIDGE_KEY", "").strip()


def configured() -> bool:
    return bool(base_url()) and len(key()) >= MIN_KEY_LEN


def describe() -> str:
    if configured():
        return "PacOs bridge: on, customers mirrored from " + base_url()
    if base_url() and key():
        return "PacOs bridge: OFF - PACOS_BRIDGE_KEY is shorter than " + str(MIN_KEY_LEN)
    return "PacOs bridge: OFF (PACOS_URL or PACOS_BRIDGE_KEY not set)"


def handoff_url(handoff_id: str) -> str:
    return base_url() + "/quotations/from-pantongone/" + handoff_id


# --------------------------------------------------------------- the wire


def _call(method: str, path: str, body: Any = None, opener: Opener = urllib.request.urlopen) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base_url() + path, data=data, method=method)
    req.add_header("content-type", "application/json")
    req.add_header("x-bridge-key", key())
    try:
        with opener(req, timeout=TIMEOUT_SECONDS) as answer:
            return json.loads(answer.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = ""
        try:
            parsed = json.loads(exc.read().decode("utf-8"))
            if isinstance(parsed, dict):
                message = str(parsed.get("error") or parsed.get("detail") or "")
        except (ValueError, OSError):
            pass
        raise BridgeError(exc.code, message or ("PacOs answered " + str(exc.code))) from exc
    except urllib.error.URLError as exc:
        raise BridgeError(503, "PacOs could not be reached: " + str(exc.reason)) from exc
    except (TimeoutError, OSError, ValueError) as exc:
        raise BridgeError(503, "PacOs could not be reached: " + str(exc)) from exc


def fetch_customers(opener: Opener = urllib.request.urlopen) -> list[dict[str, Any]]:
    answer = _call("GET", "/api/v1/bridge/customers", opener=opener)
    items = answer.get("items") if isinstance(answer, dict) else None
    if not isinstance(items, list):
        raise BridgeError(502, "PacOs answered without a customer list")
    return [
        {
            "pacos_id": str(c.get("id") or ""),
            "code": str(c.get("code") or "").strip(),
            "name": str(c.get("name") or "").strip(),
            "name_th": str(c.get("name_th") or "").strip(),
        }
        for c in items
        if isinstance(c, dict) and c.get("id") and c.get("code")
    ]


def push_handoff(payload: dict[str, Any], opener: Opener = urllib.request.urlopen) -> str:
    answer = _call("POST", "/api/v1/bridge/handoffs", payload, opener=opener)
    handoff_id = str(answer.get("id") or "") if isinstance(answer, dict) else ""
    if not handoff_id:
        raise BridgeError(502, "PacOs took the handoff but answered without its id")
    return handoff_id


# ----------------------------------------------------------- the customers

_NOISE = re.compile(r"[\s.,()\-]+")


def norm_name(text: str) -> str:
    """The same name written three ways in three years of paper is one name."""
    return _NOISE.sub(" ", (text or "").strip().lower()).strip()


def match_codes(names: list[str], customers: list[dict[str, Any]]) -> dict[str, str]:
    """Which PacOs code each old customer NAME earns, by its normalised form.

    English name and Thai name both count. A normalised name two PacOs
    customers share is ambiguous and earns NOTHING - a wrong code is worse than
    a blank one, because a blank still asks and a wrong one answers.
    """
    by_norm: dict[str, set[str]] = {}
    for c in customers:
        for label in (c.get("name", ""), c.get("name_th", "")):
            key_ = norm_name(label)
            if key_:
                by_norm.setdefault(key_, set()).add(c["code"])
    out: dict[str, str] = {}
    for name in names:
        codes = by_norm.get(norm_name(name))
        if codes and len(codes) == 1:
            out[name] = next(iter(codes))
    return out


def sync_customers(customers: list[dict[str, Any]]) -> dict[str, int]:
    """Mirror PacOs's list here, then write its codes onto the old rows by name."""
    with db.pool().connection() as conn:
        with conn.transaction():
            seen: list[str] = []
            for c in customers:
                conn.execute(
                    "INSERT INTO pacos_customers (pacos_id, code, name, name_th, is_active, synced_at)"
                    " VALUES (%s, %s, %s, %s, TRUE, now())"
                    " ON CONFLICT (pacos_id) DO UPDATE SET code = EXCLUDED.code, name = EXCLUDED.name,"
                    "   name_th = EXCLUDED.name_th, is_active = TRUE, synced_at = now()",
                    (c["pacos_id"], c["code"], c["name"], c.get("name_th", "")),
                )
                seen.append(c["pacos_id"])
            # Gone from PacOs is switched off here, never deleted: the code may
            # still sit on a thousand old rows.
            if seen:
                conn.execute(
                    "UPDATE pacos_customers SET is_active = FALSE WHERE NOT (pacos_id = ANY(%s)) AND is_active",
                    (seen,),
                )
            unlinked = [
                r["customer"]
                for r in conn.execute(
                    "SELECT DISTINCT customer FROM quotations WHERE customer_code = '' AND customer <> ''"
                ).fetchall()
            ]
            linked_rows = 0
            for name, code in match_codes(unlinked, customers).items():
                linked_rows += conn.execute(
                    "UPDATE quotations SET customer_code = %s WHERE customer = %s AND customer_code = ''",
                    (code, name),
                ).rowcount
    return {"customers": len(customers), "names_unlinked_before": len(unlinked), "rows_linked": linked_rows}


# The last sync, for /api/bridge/status. One place, written by whichever
# thread ran it last.
last_sync: dict[str, Any] = {"at": None, "ok": False, "error": "", "result": {}}


def run_sync(opener: Opener = urllib.request.urlopen) -> dict[str, Any]:
    try:
        result = sync_customers(fetch_customers(opener))
        last_sync.update({"at": datetime.now().isoformat(timespec="seconds"), "ok": True, "error": "", "result": result})
    except BridgeError as exc:
        last_sync.update({"at": datetime.now().isoformat(timespec="seconds"), "ok": False, "error": exc.message, "result": {}})
    return dict(last_sync)


def start_background() -> threading.Thread | None:
    """Mirror at boot and every quarter hour, off the request path."""
    if not configured():
        return None

    def loop() -> None:
        while True:
            status = run_sync()
            print("PacOs customers: " + ("synced " + json.dumps(status["result"]) if status["ok"] else "NOT synced - " + status["error"]), flush=True)
            time.sleep(SYNC_EVERY_SECONDS)

    thread = threading.Thread(target=loop, name="pacos-customer-sync", daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------- the lines

# The unit words this program's own tables know, plus the ones the paper
# books and the .exe write. Everything becomes millimetres HERE, at the edge
# (LAW P11); PacOs never sees an inch.
UNIT_TO_CM: dict[str, float] = {
    **DIMENSION_FACTORS_TO_CM,
    "inch": 2.54, "inches": 2.54, "in": 2.54, '"': 2.54, "นิ้ว": 2.54,
    "cm": 1.0, "cm.": 1.0, "ซม": 1.0,
    "mm": 0.1, "mm.": 0.1, "มม": 0.1,
    "m": 100.0, "m.": 100.0, "metre": 100.0, "meter": 100.0,
}
UNIT_TO_MM_THICK: dict[str, float] = {
    **THICKNESS_FACTORS_TO_MM,
    "mm": 1.0, "mm.": 1.0, "มม": 1.0,
    "cm": 10.0, "cm.": 10.0, "ซม": 10.0,
    "inch": 25.4, "in": 25.4, "นิ้ว": 25.4,
    "mic": 0.001, "mic.": 0.001, "micron": 0.001, "microns": 0.001, "μm": 0.001, "um": 0.001, "ไมครอน": 0.001,
}
DATUM = {"opening_to_seal": "to_seal", "opening_to_bottom": "to_bottom"}
THICKNESS_BASIS = {"pair": "per_pair", "side": "per_side"}


def _measure(inputs: dict[str, Any], name: str) -> dict[str, Any]:
    # The .exe nests dimensions under "dimensions"; the web form keeps them flat.
    dims = inputs.get("dimensions") if isinstance(inputs.get("dimensions"), dict) else inputs
    value = dims.get(name)
    return value if isinstance(value, dict) else {}


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _mm(inputs: dict[str, Any], name: str) -> float:
    m = _measure(inputs, name)
    value = _as_float(m.get("value"))
    factor = UNIT_TO_CM.get(str(m.get("unit") or "").strip())
    if value <= 0 or factor is None:
        return 0.0
    return round(value * factor * 10, 4)


def _thickness(inputs: dict[str, Any], normalized: dict[str, Any]) -> tuple[float, str]:
    m = _measure(inputs, "thickness")
    basis = THICKNESS_BASIS.get(str(m.get("mode") or "").strip().lower(), "")
    if normalized.get("thickness_input_mm"):
        return round(_as_float(normalized["thickness_input_mm"]), 4), basis
    value = _as_float(m.get("value"))
    factor = UNIT_TO_MM_THICK.get(str(m.get("unit") or "").strip())
    if value <= 0 or factor is None:
        return 0.0, basis
    return round(value * factor, 4), basis


def _roll_metres(inputs: dict[str, Any], normalized: dict[str, Any]) -> float:
    if normalized.get("sold_length_m"):
        return round(_as_float(normalized["sold_length_m"]), 4)
    m = _measure(inputs, "sold_length")
    value = _as_float(m.get("value"))
    factor = UNIT_TO_CM.get(str(m.get("unit") or "").strip())
    if value <= 0 or factor is None:
        return 0.0
    return round(value * factor / 100, 4)


def _iso(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    return str(value or "")[:10]


def line_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """One saved row, in the shape PacOs's bridge reads (internal/bridge.Line)."""
    inputs = row.get("inputs_json") or {}
    results = row.get("results_json") or {}
    normalized = inputs.get("normalized") if isinstance(inputs.get("normalized"), dict) else {}

    def dim(cm_key: str, name: str) -> float:
        if normalized.get(cm_key):
            return round(_as_float(normalized[cm_key]) * 10, 4)
        return _mm(inputs, name)

    thickness_mm, basis = _thickness(inputs, normalized)
    sale_basis = str(inputs.get("sale_basis") or "").strip().lower()
    if sale_basis not in ("kg", "piece"):
        sale_basis = "kg" if results.get("selling_price_per_kg") and not results.get("unit_price") else "piece"
    unit_price = _as_float(row.get("unit_price"))
    if sale_basis == "kg" and _as_float(results.get("selling_price_per_kg")) > 0:
        unit_price = _as_float(results.get("selling_price_per_kg"))
    datum = str(inputs.get("length_reference") or row.get("length_reference") or "").strip()

    return {
        "ref": row.get("quote_ref") or "",
        "quote_date": _iso(row.get("quote_date")),
        "product_key": row.get("product_key") or "",
        "product_name": str(inputs.get("product_name") or row.get("item_description") or "").strip(),
        "part_code": str(row.get("product_reference") or "").strip(),
        "size_text": row.get("size_text") or "",
        "width_mm": dim("width_cm", "width"),
        "length_mm": dim("length_cm", "length"),
        "height_mm": dim("height_cm", "height"),
        "gusset_mm": dim("gusset_cm", "gusset"),
        "thickness_mm": thickness_mm,
        "thickness_basis": basis,
        "length_datum": DATUM.get(datum, ""),
        "seal_allowance_mm": dim("bottom_allowance_cm", "bottom_allowance"),
        "roll_length_m": _roll_metres(inputs, normalized),
        "density_g_cm3": _as_float(inputs.get("density_g_cm3")),
        "resin": str(inputs.get("resin") or "").strip(),
        "sale_basis": sale_basis,
        "unit_price": unit_price,
        "order_quantity": _as_float(inputs.get("order_quantity")),
        "pack_quantity": _as_float(row.get("pack_quantity")),
        "grams_per_item": _as_float(row.get("grams_per_item")),
        "previous_price": _as_float(inputs.get("previous_price")),
    }


def build_handoff(rows: list[dict[str, Any]], email: str) -> dict[str, Any]:
    """The ticked rows as ONE handoff - which means ONE customer, by code.

    A row with no code is a row whose customer PacOs cannot recognise, and it
    is named rather than dropped; rows of two customers are two quotations,
    not one, and are refused as a set.
    """
    if not rows:
        raise SelectionError("none")
    if len(rows) > MAX_LINES:
        raise SelectionError("too_many")
    codes: list[str] = []
    for r in rows:
        code = str(r.get("customer_code") or "").strip().upper()
        if not code:
            raise SelectionError("no_customer_code", ref=str(r.get("quote_ref") or ""))
        codes.append(code)
    if len(set(codes)) > 1:
        raise SelectionError("mixed_customers")
    return {
        "source": "pantongone",
        "created_by_email": email.strip().lower(),
        "customer_code": codes[0],
        "customer_name": str(rows[0].get("customer") or ""),
        "lines": [line_from_row(r) for r in rows],
    }
