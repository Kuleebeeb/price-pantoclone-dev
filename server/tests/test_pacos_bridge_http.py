# -*- coding: utf-8 -*-
"""INTEGRATION: the bridge to PacOs, end to end over HTTP.

A stand-in PacOs answers the sign-in (pacos_gate) and the two bridge doors;
this API boots in AUTH_MODE=pacos with a bridge key, against the throwaway
database, and:

  - mirrors PacOs's customers at boot and writes their codes onto the old
    rows whose names match
  - offers PacOs's names and codes in the customer list, old names after
  - sends ticked rows as ONE handoff carrying the signer's e-mail, and hands
    back PacOs's address to open
  - refuses rows of two customers and a row with no PacOs customer, in Thai
    and English, and an unknown reference

Needs DATABASE_URL -> throwaway DB (with 'smoke' in it). Spawns its own API.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "core"))
sys.path.insert(0, str(HERE / "api"))

if not os.environ.get("DATABASE_URL") or "smoke" not in os.environ["DATABASE_URL"]:
    print("HONG: DATABASE_URL phai tro vao Postgres TAM (co chu 'smoke').")
    sys.exit(1)

import db  # noqa: E402
import store  # noqa: E402
from calculator import PRODUCTS  # noqa: E402

# The mirror table arrives with migration 0006; on a fresh throwaway database
# it does not exist until something runs the migrations. Run them here, the
# way the API does at boot, so the cleanup below has a table to clean.
db.run_migrations()

failures: list[str] = []


def check(name: str, cond: bool, detail="") -> None:
    if cond:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name + "  " + str(detail))


KEY = "k" * 40
CEO = "zz-bridge-ceo@test.local"
DAIKIN_OLD = "Daikin Industries (Thailand) Co.,Ltd."
DAIKIN_PACOS = "DAIKIN INDUSTRIES (THAILAND) CO., LTD."
CUSTOMERS = [
    {"id": "c-daikin", "code": "DAIKIN", "name": DAIKIN_PACOS, "name_th": ""},
    {"id": "c-honda", "code": "HONDA", "name": "Honda Automobile (Thailand) Co., Ltd.", "name_th": ""},
]


class PacosStandIn(BaseHTTPRequestHandler):
    handoffs: list[dict] = []
    keys_seen: list[str] = []

    def log_message(self, *args) -> None:
        return

    def _send(self, status, body, headers=None):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _keyed(self) -> bool:
        PacosStandIn.keys_seen.append(self.headers.get("x-bridge-key") or "")
        if self.headers.get("x-bridge-key") != KEY:
            self._send(401, {"error": "That bridge key is not right."})
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/v1/bridge/customers":
            if self._keyed():
                self._send(200, {"items": CUSTOMERS, "count": len(CUSTOMERS)})
            return
        self._send(404, {"error": "no such route"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/v1/auth/login":
            if body.get("email", "").lower() == CEO and body.get("password") == "ceo-pass-123456":
                self._send(200, {"user": {"id": "u-ceo", "email": CEO, "full_name": "CEO", "roles": ["ceo"],
                                          "permissions": ["quotations.view_cost_breakdown", "quotations.create"]},
                                 "access_token": "acc", "expires_in": 900, "refresh_token": "ref"})
            else:
                self._send(401, {"error": "That email and password do not match."})
            return
        if self.path == "/api/v1/auth/logout":
            self._send(200, {"ok": True})
            return
        if self.path == "/api/v1/bridge/handoffs":
            if self._keyed():
                PacosStandIn.handoffs.append(body)
                self._send(201, {"id": "h-%d" % len(PacosStandIn.handoffs), "expires_in_hours": 24})
            return
        self._send(404, {"error": "no such route"})


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


stand_in = ThreadingHTTPServer(("127.0.0.1", 0), PacosStandIn)
threading.Thread(target=stand_in.serve_forever, daemon=True).start()
PACOS_URL = "http://127.0.0.1:%d" % stand_in.server_address[1]

PORT = free_port()
BASE = "http://127.0.0.1:%d" % PORT
env = dict(os.environ)
env.update({
    "AUTH_MODE": "pacos", "PACOS_URL": PACOS_URL, "PACOS_BRIDGE_KEY": KEY,
    "AUTH_SECRET": os.environ.get("AUTH_SECRET", "smoke-test-secret-0123456789"),
    "TZ": os.environ.get("TZ", "Asia/Bangkok"),
})
log_path = Path(tempfile.gettempdir()) / "pantongone_pacos_bridge_api.log"
log = open(log_path, "w", encoding="utf-8")
token = ""


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("content-type", "application/json")
    if token:
        req.add_header("authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def wait_up(api) -> bool:
    for _ in range(80):
        if api.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(BASE + "/api/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.5)
    return False


def cleanup() -> None:
    with store.pool().connection() as conn:
        conn.execute("DELETE FROM quotations WHERE quote_ref LIKE 'ZZB/%%'")
        conn.execute("DELETE FROM login_attempts WHERE email LIKE 'zz-bridge-%%'")
        conn.execute("DELETE FROM users WHERE email LIKE 'zz-bridge-%%'")
        conn.execute("DELETE FROM pacos_customers WHERE pacos_id IN ('c-daikin', 'c-honda')")


def codes_of(refs):
    with store.pool().connection() as conn:
        return {r["quote_ref"]: r["customer_code"] for r in conn.execute(
            "SELECT quote_ref, customer_code FROM quotations WHERE quote_ref = ANY(%s)", (refs,)).fetchall()}


def row(ref, customer, code, inputs_extra=None):
    inputs = {
        "product_key": "flat", "width": {"value": 12, "unit": "นิ้ว"}, "length": {"value": 18, "unit": "นิ้ว"},
        "thickness": {"value": 50, "unit": "ไมครอน", "mode": "pair"}, "bottom_allowance": {"value": 1, "unit": "ซม."},
        "length_reference": "opening_to_seal", "density_g_cm3": 0.92, "sale_basis": "kg", "order_quantity": 5000,
        "product_name": "PLASTIC BAG PE",
        "normalized": {"width_cm": 30.48, "length_cm": 45.72, "thickness_input_mm": 0.05, "bottom_allowance_cm": 1.0},
    }
    inputs.update(inputs_extra or {})
    return {
        "quote_ref": ref, "quote_date": "2026-03-01", "customer": customer, "customer_code": code,
        "item_description": "PLASTIC BAG PE 12 x 18", "product_key": "flat", "product_label": PRODUCTS["flat"],
        "size_text": "12 x 18 in", "unit_price": 78.0, "inputs": inputs,
        "results": {"grams_per_item": 12.82, "selling_price_per_kg": 78}, "grams_per_item": 12.82,
        "import_source": "ZZB.xlsx • test",
    }


cleanup()
store.import_quotations([
    row("ZZB/69-01", DAIKIN_OLD, ""),
    row("ZZB/69-02", DAIKIN_OLD, ""),
    row("ZZB/69-03", "Honda Automobile (Thailand) Co., Ltd.", "HONDA"),
    row("ZZB/69-04", "Nobody Ltd", ""),
])
# The API is started AFTER the rows exist, so the boot-time mirror has old
# names to link.
api = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--app-dir", "api", "--host", "127.0.0.1", "--port", str(PORT)],
    cwd=str(HERE), env=env, stdout=log, stderr=subprocess.STDOUT,
)

try:
    if not wait_up(api):
        log.close()
        print("HONG: API khong len. Log:")
        print(log_path.read_text(encoding="utf-8")[-3000:])
        sys.exit(1)

    s, r = call("GET", "/api/meta")
    check("meta says the bridge is on", s == 200 and r.get("pacos_bridge") is True, r.get("pacos_bridge"))

    s, r = call("POST", "/api/auth/login", {"email": CEO, "password": "ceo-pass-123456"})
    check("signed in through PacOs", s == 200, str(r)[:160])
    token = r.get("token", "")

    for _ in range(40):
        s, r = call("GET", "/api/bridge/status")
        if r.get("last_sync", {}).get("ok"):
            break
        time.sleep(0.25)
    check("the boot-time mirror ran and PacOs saw the key",
          r.get("configured") is True and r["last_sync"]["ok"] and KEY in PacosStandIn.keys_seen, r)
    # At least the two seeded rows: the throwaway database may hold a copy of
    # the real book, whose own Daikin and Honda rows earn the code too.
    check("two customers mirrored, the old rows linked by name",
          r["last_sync"]["result"].get("customers") == 2 and r["last_sync"]["result"].get("rows_linked") >= 2, r["last_sync"])

    linked = codes_of(["ZZB/69-01", "ZZB/69-02", "ZZB/69-03", "ZZB/69-04"])
    check("Daikin's old rows now carry PacOs's code; Honda kept its own; Nobody stays blank",
          linked == {"ZZB/69-01": "DAIKIN", "ZZB/69-02": "DAIKIN", "ZZB/69-03": "HONDA", "ZZB/69-04": ""}, linked)

    s, r = call("GET", "/api/customers")
    rows = {c["customer"]: c for c in r["rows"]}
    check("the picker offers PacOs's name and code, counted by the linked rows",
          rows.get(DAIKIN_PACOS, {}).get("customer_code") == "DAIKIN" and rows[DAIKIN_PACOS]["times"] >= 2, rows.get(DAIKIN_PACOS))
    check("an old name nobody matched is still offered, code blank",
          rows.get("Nobody Ltd", {}).get("customer_code") == "" , rows.get("Nobody Ltd"))
    check("the old spelling of a linked name is not offered twice", DAIKIN_OLD not in rows, [k for k in rows if "aikin" in k])

    # ------------------------------------------------------------ the push
    PacosStandIn.handoffs.clear()
    s, r = call("POST", "/api/bridge/handoffs", {"refs": ["ZZB/69-01", "ZZB/69-02", "ZZB/69-01"]})
    check("two rows of one customer: sent, PacOs's address comes back",
          s == 200 and r.get("url") == PACOS_URL + "/quotations/from-pantongone/h-1" and r.get("lines") == 2, r)
    sent = PacosStandIn.handoffs[-1] if PacosStandIn.handoffs else {}
    check("the handoff carries the signer's e-mail and the shared code",
          sent.get("created_by_email") == CEO and sent.get("customer_code") == "DAIKIN" and sent.get("source") == "pantongone", sent.keys())
    first = (sent.get("lines") or [{}])[0]
    check("the line travels in millimetres with datum, basis, density and the kg price",
          (first.get("width_mm"), first.get("length_mm"), first.get("thickness_mm"), first.get("length_datum"),
           first.get("thickness_basis"), first.get("density_g_cm3"), first.get("unit_price"), first.get("sale_basis"))
          == (304.8, 457.2, 0.05, "to_seal", "per_pair", 0.92, 78.0, "kg"), first)
    check("the e-mail is the person's, the key is the server's - nothing else travels",
          "password" not in json.dumps(sent) and "token" not in json.dumps(sent))

    s, r = call("POST", "/api/bridge/handoffs", {"refs": ["ZZB/69-01", "ZZB/69-03"]})
    check("rows of two customers: 409 in Thai and English",
          s == 409 and "คนละราย" in r.get("error", "") and "different customers" in r.get("error", ""), (s, r))
    s, r = call("POST", "/api/bridge/handoffs", {"refs": ["ZZB/69-04"]})
    check("a row with no PacOs customer: 409 naming the row, in both languages",
          s == 409 and "ZZB/69-04" in r.get("error", "") and "ยังไม่ผูก" in r.get("error", "") and "not linked" in r.get("error", ""), (s, r))
    s, r = call("POST", "/api/bridge/handoffs", {"refs": ["ZZB/none"]})
    check("an unknown reference: 404", s == 404 and "ZZB/none" in r.get("error", ""), (s, r))
    s, r = call("POST", "/api/bridge/handoffs", {"refs": []})
    check("nothing ticked: 400", s == 400, (s, r))
    check("nothing but the good push reached PacOs", len(PacosStandIn.handoffs) == 1)

    s, r = call("POST", "/api/bridge/customers/sync")
    check("a sync can be pressed by hand", s == 200 and r.get("ok") is True, (s, r))

    saved = ""
    s, r = call("GET", "/api/bridge/status")
    check("status is readable", s == 200 and r.get("configured") is True)
finally:
    api.terminate()
    try:
        api.wait(timeout=10)
    except subprocess.TimeoutExpired:
        api.kill()
    log.close()
    stand_in.shutdown()
    stand_in.server_close()
    cleanup()
    import db  # noqa: E402

    if hasattr(db, "close_pool"):
        db.close_pool()

print()
if failures:
    print(f"KHONG KHOP - {len(failures)} sai: {failures}")
    sys.exit(1)
print("KHOP - khach hang soi guong dung, dong di dung, tu choi dung cua")
