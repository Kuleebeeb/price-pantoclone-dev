# -*- coding: utf-8 -*-
"""INTEGRATION: signing in through PacOs, end to end over HTTP.

Starts a stand-in PacOs (a few lines of http.server answering the way
pacos-backend/internal/auth/http.go does) and THIS API in AUTH_MODE=pacos
against the throwaway database, then walks the gate:

  - /api/meta says the password is PacOs's
  - a right password on an account with the cost-breakdown permission: a
    token, the name PacOs holds, a mirrored users row with NO local password,
    /api/me with permissions, and the PacOs session closed again
  - that row switched off locally is switched back on by PacOs's next yes
  - a right password WITHOUT the permission: 403 naming it, and no row
  - wrong password 401 (counted), switched-off 403, PacOs's 429 with Retry-After
  - a password from the old local table opens nothing any more
  - PacOs down: 503, and NOT counted as a failed attempt

Needs DATABASE_URL -> throwaway DB (with 'smoke' in it). Spawns its own API on
a free port, so the :8145 server other tests use is left alone.
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

import auth  # noqa: E402
import store  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, detail="") -> None:
    if cond:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name + "  " + str(detail))


# ------------------------------------------------------------ a stand-in PacOs
CEO_ID = "5b1d5c1e-8d1a-4f0e-9c3b-2a7d6e5f4a3b"
CEO = "zz-pacos-ceo@test.local"
SALE = "zz-pacos-sale@test.local"
OFF = "zz-pacos-off@test.local"
BUSY = "zz-pacos-busy@test.local"
LOCAL = "zz-pacos-local@test.local"

ACCOUNTS = {
    (CEO, "ceo-pass-123456"): {
        "id": CEO_ID, "email": "ZZ-PacOs-CEO@test.local", "full_name": "Angela (PacOs)", "lang": "th",
        "roles": ["ceo"], "permissions": ["specs.calc", "quotations.create", "quotations.view_cost_breakdown"],
    },
    (SALE, "sale-pass-123456"): {
        "id": "7c2e6d2f-9e2b-4a1f-8d4c-3b8e7f6a5b4c", "email": SALE, "full_name": "Somchai (Sale)", "lang": "th",
        "roles": ["sale"], "permissions": ["specs.calc", "quotations.create"],
    },
}


class PacosStandIn(BaseHTTPRequestHandler):
    seen: list[dict] = []

    def log_message(self, *args) -> None:  # quiet
        return

    def _send(self, status: int, body: dict, headers: dict | None = None) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:  # noqa: N802 - http.server's name
        length = int(self.headers.get("content-length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        PacosStandIn.seen.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
        if self.path == "/api/v1/auth/logout":
            self._send(200, {"ok": True})
            return
        if self.path != "/api/v1/auth/login":
            self._send(404, {"error": "no such route"})
            return
        email = str(body.get("email", "")).strip().lower()
        if email == OFF:
            self._send(403, {"error": "This account has been switched off. Ask IT to turn it back on."})
            return
        if email == BUSY:
            self._send(429, {"error": "Too many failed sign-in attempts. Wait a minute and try again."}, {"Retry-After": "60"})
            return
        user = ACCOUNTS.get((email, str(body.get("password", ""))))
        if user is None:
            self._send(401, {"error": "That email and password do not match."})
            return
        self._send(200, {"user": user, "access_token": "acc-" + email, "expires_in": 900, "refresh_token": "ref-" + email})


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


stand_in = ThreadingHTTPServer(("127.0.0.1", 0), PacosStandIn)
threading.Thread(target=stand_in.serve_forever, daemon=True).start()
PACOS_URL = "http://127.0.0.1:%d" % stand_in.server_address[1]

# ------------------------------------------------------------------ this API
PORT = free_port()
BASE = "http://127.0.0.1:%d" % PORT
env = dict(os.environ)
env.update({
    "AUTH_MODE": "pacos",
    "PACOS_URL": PACOS_URL + "/",
    "AUTH_SECRET": os.environ.get("AUTH_SECRET", "smoke-test-secret-0123456789"),
    "TZ": os.environ.get("TZ", "Asia/Bangkok"),
    # Would be ignored in pacos mode anyway; set so the test proves that.
    "BOOTSTRAP_EMAIL": LOCAL,
    "BOOTSTRAP_PASSWORD": "local-pass-1234",
})
log_path = Path(tempfile.gettempdir()) / "pantongone_pacos_login_api.log"
log = open(log_path, "w", encoding="utf-8")
api = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "main:app", "--app-dir", "api", "--host", "127.0.0.1", "--port", str(PORT)],
    cwd=str(HERE), env=env, stdout=log, stderr=subprocess.STDOUT,
)

token = ""


def call(method: str, path: str, body=None, bearer: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("content-type", "application/json")
    if bearer:
        req.add_header("authorization", "Bearer " + bearer)
    # The headers stay an HTTPMessage: uvicorn writes them lower-case, and a
    # dict() of that would make "Retry-After" a key nobody finds.
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode()), r.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode()), e.headers


def wait_up() -> bool:
    for _ in range(60):
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
        conn.execute("DELETE FROM login_attempts WHERE email LIKE 'zz-pacos-%%'")
        conn.execute("DELETE FROM users WHERE email LIKE 'zz-pacos-%%'")


def user_row(email: str):
    with store.pool().connection() as conn:
        return conn.execute(
            "SELECT email, full_name, password_hash, is_active, pacos_user_id, permissions FROM users WHERE email = %s",
            (email,),
        ).fetchone()


def failed_attempts(email: str) -> int:
    with store.pool().connection() as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM login_attempts WHERE email = %s AND NOT succeeded", (email,)
        ).fetchone()["n"]


try:
    cleanup()
    # A leftover from the days of local passwords: the row exists, the hash is
    # right, and in this mode it must open nothing.
    store.create_user(LOCAL, "Local Leftover", auth.hash_password("local-pass-1234"))

    if not wait_up():
        log.close()
        print("HONG: API khong len. Log:")
        print(log_path.read_text(encoding="utf-8")[-3000:])
        sys.exit(1)

    s, r, _ = call("GET", "/api/meta")
    check("meta says the password is PacOs's", s == 200 and r.get("sign_in_with") == "pacos", r.get("sign_in_with"))

    check("bootstrap admin not created in pacos mode",
          user_row(LOCAL)["full_name"] == "Local Leftover", user_row(LOCAL))

    # ---------------------------------------------------------------- a yes
    PacosStandIn.seen.clear()
    s, r, _ = call("POST", "/api/auth/login", {"email": "ZZ-PacOs-CEO@test.local", "password": "ceo-pass-123456"})
    check("right PacOs password: 200 with a token", s == 200 and bool(r.get("token")), str(r)[:200])
    token = r.get("token", "")
    check("the name is the one PacOs holds", r.get("user", {}).get("full_name") == "Angela (PacOs)", r.get("user"))
    check("the email is lower-cased", r.get("user", {}).get("email") == CEO, r.get("user"))
    check("permissions travel with the session",
          "quotations.view_cost_breakdown" in r.get("user", {}).get("permissions", []), r.get("user"))
    check("PacOs received X-Client: native",
          PacosStandIn.seen and PacosStandIn.seen[0]["path"] == "/api/v1/auth/login"
          and PacosStandIn.seen[0]["headers"].get("x-client") == "native", PacosStandIn.seen[:1])
    check("the PacOs session was closed again, with its refresh token",
          len(PacosStandIn.seen) == 2 and PacosStandIn.seen[1]["path"] == "/api/v1/auth/logout"
          and PacosStandIn.seen[1]["headers"].get("x-refresh-token") == "ref-" + CEO
          and PacosStandIn.seen[1]["headers"].get("authorization") == "Bearer acc-" + CEO,
          PacosStandIn.seen[1:])

    row = user_row(CEO)
    check("a users row mirrors the account: PacOs id, name, active, NO local password",
          row is not None and row["pacos_user_id"] == CEO_ID and row["full_name"] == "Angela (PacOs)"
          and row["is_active"] is True and row["password_hash"] is None, row)
    check("the row keeps the permissions PacOs granted",
          row is not None and "quotations.view_cost_breakdown" in row["permissions"], row and row["permissions"])

    s, r, _ = call("GET", "/api/me", bearer=token)
    check("/api/me answers with the same permissions", s == 200 and "quotations.view_cost_breakdown" in r.get("permissions", []), r)

    # switched off locally -> the token dies at once; PacOs's next yes revives the row
    with store.pool().connection() as conn:
        conn.execute("UPDATE users SET is_active = FALSE WHERE email = %s", (CEO,))
    s, r, _ = call("GET", "/api/me", bearer=token)
    check("a row switched off locally stops the token on the next request", s == 401, (s, r))
    s, r, _ = call("POST", "/api/auth/login", {"email": CEO, "password": "ceo-pass-123456"})
    check("PacOs says yes again: signed in, and the row is switched back on",
          s == 200 and user_row(CEO)["is_active"] is True, (s, user_row(CEO)))

    # ------------------------------------------------------------ the gate
    s, r, _ = call("POST", "/api/auth/login", {"email": SALE, "password": "sale-pass-123456"})
    check("right password without the cost-breakdown permission: 403 naming it",
          s == 403 and "quotations.view_cost_breakdown" in r.get("error", ""), (s, r))
    check("no row is mirrored for an account that may not enter", user_row(SALE) is None)
    check("that refusal is not counted as a wrong password", failed_attempts(SALE) == 0)

    # ------------------------------------------------------------- the noes
    before = failed_attempts(CEO)
    s, r, _ = call("POST", "/api/auth/login", {"email": CEO, "password": "wrong-pass-123"})
    check("wrong password: 401 in both languages", s == 401 and "do not match" in r.get("error", ""), (s, r))
    check("a wrong password IS counted against the local throttle", failed_attempts(CEO) == before + 1)

    s, r, _ = call("POST", "/api/auth/login", {"email": OFF, "password": "whatever-1234"})
    check("switched off in PacOs: 403 saying so", s == 403 and "switched off" in r.get("error", ""), (s, r))

    s, r, headers = call("POST", "/api/auth/login", {"email": BUSY, "password": "whatever-1234"})
    check("PacOs's own 429 comes through with its sentence and Retry-After",
          s == 429 and "Wait a minute" in r.get("error", "") and headers.get("Retry-After") == "60", (s, r, headers.get("Retry-After")))

    s, r, _ = call("POST", "/api/auth/login", {"email": LOCAL, "password": "local-pass-1234"})
    check("a password from the old local table opens nothing", s == 401, (s, r))

    # ----------------------------------------------------------- PacOs down
    stand_in.shutdown()
    stand_in.server_close()
    before = failed_attempts(CEO)
    s, r, _ = call("POST", "/api/auth/login", {"email": CEO, "password": "ceo-pass-123456"})
    check("PacOs down: 503 saying it could not be reached",
          s == 503 and "could not be reached" in r.get("error", ""), (s, r))
    check("PacOs down is not counted as a failed attempt", failed_attempts(CEO) == before)

finally:
    api.terminate()
    try:
        api.wait(timeout=10)
    except subprocess.TimeoutExpired:
        api.kill()
    log.close()
    cleanup()
    check("cleanup", user_row(CEO) is None and user_row(LOCAL) is None)
    import db  # noqa: E402

    if hasattr(db, "close_pool"):
        db.close_pool()

print()
if failures:
    print(f"KHONG KHOP - {len(failures)} sai: {failures}")
    sys.exit(1)
print("KHOP - dang nhap qua PacOs dung tung cua: mo, dong, khong quyen, PacOs sap")
