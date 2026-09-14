# -*- coding: utf-8 -*-
"""UNIT: the PacOs gate translates PacOs's answers, and never invents one.

No network and no database: `opener` is a stand-in for urllib's urlopen. Pinned:

  - the request PacOs receives: its own sign-in route, X-Client: native, the
    caller's address, the email and password as JSON
  - a yes: who came back (lower-cased email, permissions), and that the PacOs
    session is closed again with the refresh token it handed out
  - each no: 401 / 403 / 429 become PacosRefused carrying PacOs's own sentence
    and its Retry-After; anything else - a 500, a refused connection, a
    timeout, a body with no user in it - is PacosUnreachable, which the gate
    never counts as a wrong password
  - the mode switch: a misspelt AUTH_MODE, or 'pacos' with no address, is a
    boot-time error rather than a quiet fall-back to local passwords
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.error
from email.message import Message
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "api"))

import pacos_gate  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, detail="") -> None:
    if cond:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name + "  " + str(detail))


class FakeAnswer:
    def __init__(self, body) -> None:
        self._raw = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False


def http_error(code: int, body=None, headers=None) -> urllib.error.HTTPError:
    hdrs = Message()
    for key, value in (headers or {}).items():
        hdrs[key] = value
    raw = body if isinstance(body, bytes) else json.dumps(body or {}).encode("utf-8")
    return urllib.error.HTTPError("http://pacos.test/api/v1/auth/login", code, "refused", hdrs, io.BytesIO(raw))


def opener_with(script: list):
    """One scripted answer per call, in order; the last one repeats. Records
    every request so the test can read what PacOs would have received."""
    calls: list = []

    def opener(req, timeout=None):
        calls.append(req)
        step = script[min(len(calls) - 1, len(script) - 1)]
        if isinstance(step, BaseException):
            raise step
        return FakeAnswer(step)

    opener.calls = calls  # type: ignore[attr-defined]
    return opener


CEO_ID = "5b1d5c1e-8d1a-4f0e-9c3b-2a7d6e5f4a3b"
OK_BODY = {
    "user": {
        "id": CEO_ID, "email": "CEO@Pantong.test", "full_name": "Angela", "lang": "th",
        "roles": ["ceo"], "permissions": ["specs.calc", "pricing.sign_in"],
    },
    "access_token": "acc-1", "expires_in": 900, "refresh_token": "ref-1",
}

# ------------------------------------------------------------------ the switch
os.environ["PACOS_URL"] = "http://pacos.test/"
os.environ.pop("AUTH_MODE", None)
check("mode: unset means local", pacos_gate.mode() == "local")
os.environ["AUTH_MODE"] = "pacos"
check("mode: pacos with an address", pacos_gate.mode() == "pacos")
os.environ["PACOS_URL"] = "   "
try:
    pacos_gate.mode()
    check("mode: pacos without PACOS_URL refuses to boot", False, "no error raised")
except RuntimeError as exc:
    check("mode: pacos without PACOS_URL refuses to boot", "PACOS_URL" in str(exc), exc)
os.environ["PACOS_URL"] = "http://pacos.test/"
os.environ["AUTH_MODE"] = "pacoss"
try:
    pacos_gate.mode()
    check("mode: a misspelt value refuses to boot, not falls back to local", False, "no error raised")
except RuntimeError as exc:
    check("mode: a misspelt value refuses to boot, not falls back to local", "pacoss" in str(exc), exc)
os.environ["AUTH_MODE"] = "pacos"
check("describe names the address and the permission",
      "http://pacos.test" in pacos_gate.describe() and "pricing.sign_in" in pacos_gate.describe(),
      pacos_gate.describe())

# --------------------------------------------------------------------- a yes
op = opener_with([OK_BODY, {"ok": True}])
who = pacos_gate.sign_in("CEO@Pantong.test", "pw-123456", caller_ip="203.0.113.9", opener=op)
login = op.calls[0]
check("asks PacOs's own sign-in route, POST, trailing slash of PACOS_URL dropped",
      login.full_url == "http://pacos.test/api/v1/auth/login" and login.get_method() == "POST", login.full_url)
check("body is the email and password as JSON, untouched",
      json.loads(login.data) == {"email": "CEO@Pantong.test", "password": "pw-123456"}, login.data)
check("X-Client: native, so the refresh token comes back in the body", login.get_header("X-client") == "native")
check("carries the caller's address for PacOs's own per-address counter",
      login.get_header("X-forwarded-for") == "203.0.113.9")
check("who: id, lower-cased email, name, roles, permissions as PacOs said",
      who == {"id": CEO_ID, "email": "ceo@pantong.test", "full_name": "Angela",
              "roles": ["ceo"], "permissions": ["specs.calc", "pricing.sign_in"]}, who)
check("closes the PacOs session it just opened", len(op.calls) == 2 and op.calls[1].full_url == "http://pacos.test/api/v1/auth/logout",
      [c.full_url for c in op.calls])
logout = op.calls[1]
check("logout carries the access token, the refresh token, and X-Client: native",
      logout.get_header("Authorization") == "Bearer acc-1"
      and logout.get_header("X-refresh-token") == "ref-1"
      and logout.get_header("X-client") == "native")
check("allowed: pricing.sign_in opens the door", pacos_gate.allowed(who))
check("allowed: the old cost-breakdown key still opens it while PacOs D45 lands",
      pacos_gate.allowed({"permissions": ["quotations.view_cost_breakdown"]}))
check("allowed: without either the door stays shut - quotations.create is not enough",
      not pacos_gate.allowed({"permissions": ["specs.calc", "quotations.create"]}))
check("allowed: no permissions at all", not pacos_gate.allowed({}))

op = opener_with([OK_BODY, {"ok": True}])
pacos_gate.sign_in("a@b.test", "x", opener=op)
check("no caller address, no X-Forwarded-For header", op.calls[0].get_header("X-forwarded-for") is None)

op = opener_with([OK_BODY, http_error(500, {"error": "boom"})])
who = pacos_gate.sign_in("CEO@Pantong.test", "pw-123456", opener=op)
check("a failed logout does not undo a good sign-in", who["email"] == "ceo@pantong.test" and len(op.calls) == 2)

op = opener_with([{"user": {"id": CEO_ID, "email": "x@y.test"}, "expires_in": 900}])
who = pacos_gate.sign_in("x@y.test", "pw", opener=op)
check("no access token in the answer: nothing to close, no logout call", len(op.calls) == 1 and who["permissions"] == [])

# ---------------------------------------------------------------------- a no
for code, headers in ((401, {}), (403, {}), (429, {"Retry-After": "61"})):
    op = opener_with([http_error(code, {"error": "PacOs says no " + str(code)}, headers)])
    try:
        pacos_gate.sign_in("CEO@Pantong.test", "wrong", opener=op)
        check(f"{code}: refused", False, "no error raised")
    except pacos_gate.PacosRefused as exc:
        check(f"{code}: PacosRefused with PacOs's own sentence and Retry-After",
              exc.status == code and exc.message == "PacOs says no " + str(code)
              and exc.retry_after == headers.get("Retry-After"),
              (exc.status, exc.message, exc.retry_after))
    check(f"{code}: no logout attempted - there is no session to close", len(op.calls) == 1)

op = opener_with([http_error(401, b"<html>not json</html>")])
try:
    pacos_gate.sign_in("a@b.test", "wrong", opener=op)
    check("401 with a non-JSON body still refuses", False)
except pacos_gate.PacosRefused as exc:
    check("401 with a non-JSON body still refuses, with an empty sentence", exc.status == 401 and exc.message == "")

# ------------------------------------------------------------- not an answer
unreachable = {
    "500 from PacOs": http_error(500, {"error": "boom"}),
    "connection refused": urllib.error.URLError(ConnectionRefusedError(111, "Connection refused")),
    "timeout": TimeoutError("timed out"),
    "a 200 with no user in it": {"access_token": "x", "expires_in": 900},
    "a 200 that is not JSON": b"<html>proxy page</html>",
}
for name, step in unreachable.items():
    op = opener_with([step])
    try:
        pacos_gate.sign_in("CEO@Pantong.test", "pw", opener=op)
        check(name + ": PacosUnreachable", False, "no error raised")
    except pacos_gate.PacosUnreachable as exc:
        check(name + ": PacosUnreachable, never a wrong password", True)
    except pacos_gate.PacosRefused as exc:
        check(name + ": PacosUnreachable", False, "was PacosRefused " + str(exc.status))

print()
if failures:
    print(f"KHONG KHOP - {len(failures)} sai: {failures}")
    sys.exit(1)
print("KHOP - cong PacOs dich dung moi cau tra loi, khong bia them cau nao")
