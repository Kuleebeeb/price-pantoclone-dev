"""Signing in with a PacOs account, so one password opens both programs.

WHY. Bee, 28-08-2026: the pricing program and PacOs are used by the same few
people, and the bridge between them (a price worked out here, put on a
quotation there) is only honest if the person is the same person on both
sides. Two account tables drift: somebody switched off in PacOs keeps a
working password here, and nobody notices until they use it.

HOW. In this mode the service holds NO password of its own. The email and
password typed at the gate go to PacOs's own sign-in route, and PacOs's
answer decides. What comes back is who they are and what they may do; that
is mirrored into the users table here (so created_by keeps pointing at a
row) and this service signs its own 12-hour token exactly as before.

WHAT IS DELIBERATELY NOT DONE.
  - JWT_SECRET is not shared (source-code.md:139): a shared secret means a
    token minted for one system opens the other. PacOs checks the password;
    this service signs its own token with its own AUTH_SECRET.
  - The PacOs session the sign-in opens is closed again at once (auth/logout).
    Keeping it would leave a 30-day refresh token lying in this service for
    nothing, and put a phantom "device" on the person's PacOs sessions screen
    at every sign-in.
  - The gate is a PacOs PERMISSION, not a role name. Roles get renamed;
    pricing.sign_in says exactly what it grants - the right to use this
    program, which prints the cost structure behind a price, a thing SRS 3
    keeps away from the sales role. Until 14-09-2026 the key was
    quotations.view_cost_breakdown; PacOs D45 drops every cost permission
    along with its formula, so the gate got a key of its own. The old key
    still opens the door while the two deploys cross, and goes after.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any, Callable

# The PacOs permission that opens this program: granted to ceo, sale_manager
# and admin, not to sale - the same three the cost-breakdown key went to
# (0001_init.sql: "no cost breakdown. SRS 3 and K2"), because the pricing
# screen prints the cost behind every price.
REQUIRED_PERMISSION = "pricing.sign_in"

# Still accepted while PacOs D45 lands: PacOs seeds pricing.sign_in in the same
# migration that drops quotations.view_cost_breakdown, and this service is
# deployed FIRST - so for a while the only key an account carries is the old
# one. Drop the second entry once PacOs has deployed migration 0131.
ACCEPTED_PERMISSIONS = (REQUIRED_PERMISSION, "quotations.view_cost_breakdown")

# Long enough for a cold PacOs container, short enough that a person at the
# gate is told "PacOs is not answering" instead of watching a spinner.
TIMEOUT_SECONDS = 8

Opener = Callable[..., Any]


class PacosRefused(Exception):
    """PacOs answered, and the answer was no: 401 wrong password, 403 account
    switched off, 429 too many failures. `message` is PacOs's own sentence."""

    def __init__(self, status: int, message: str, retry_after: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.retry_after = retry_after


class PacosUnreachable(Exception):
    """PacOs gave no usable answer: down, timed out, or a shape this code does
    not know. Never counted as a wrong password."""


def base_url() -> str:
    return os.environ.get("PACOS_URL", "").strip().rstrip("/")


def mode() -> str:
    """'local' (this service's own users table) or 'pacos'.

    Read every time rather than cached, so a test can flip it. A misspelt value,
    or 'pacos' with no address, is a boot-time error - NOT a quiet fall-back to
    local passwords, which is the kind of failure that looks like it works.
    """
    value = os.environ.get("AUTH_MODE", "local").strip().lower() or "local"
    if value not in ("local", "pacos"):
        raise RuntimeError("AUTH_MODE phai la 'local' hoac 'pacos', dang la " + repr(value))
    if value == "pacos" and not base_url():
        raise RuntimeError("AUTH_MODE=pacos nhung PACOS_URL chua dat")
    return value


def describe() -> str:
    if mode() == "pacos":
        return "sign-in: PacOs accounts at " + base_url() + " (needs " + REQUIRED_PERMISSION + ")"
    return "sign-in: LOCAL accounts (this service's own users table)"


def _read_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode("utf-8"))
    except (ValueError, OSError):
        return ""
    if isinstance(body, dict):
        return str(body.get("error") or body.get("detail") or "")
    return ""


def sign_in(
    email: str,
    password: str,
    caller_ip: str = "",
    opener: Opener = urllib.request.urlopen,
) -> dict[str, Any]:
    """Ask PacOs whether this email and password are right, and who that is.

    Returns {"id", "email", "full_name", "roles", "permissions"} as PacOs
    describes them. Raises PacosRefused or PacosUnreachable.
    """
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(base_url() + "/api/v1/auth/login", data=payload, method="POST")
    req.add_header("content-type", "application/json")
    # auth-flow.md step 7: with this header PacOs puts the refresh token in the
    # body instead of a cookie. There is no cookie jar here to hold one, and a
    # token in the body can be handed straight back to /auth/logout below.
    req.add_header("x-client", "native")
    if caller_ip:
        # PacOs counts wrong passwords per address as well as per email. Every
        # sign-in relayed by this service would otherwise arrive from ONE
        # address - this container's - and one person's mistakes would fill
        # everybody's bucket. PacOs only honours a public address here, so a
        # private one is harmlessly ignored.
        req.add_header("x-forwarded-for", caller_ip)

    try:
        with opener(req, timeout=TIMEOUT_SECONDS) as answer:
            body = json.loads(answer.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 429):
            raise PacosRefused(exc.code, _read_error(exc), exc.headers.get("Retry-After")) from exc
        raise PacosUnreachable("PacOs answered " + str(exc.code)) from exc
    except urllib.error.URLError as exc:
        raise PacosUnreachable(str(exc.reason)) from exc
    except (socket.timeout, TimeoutError, OSError, ValueError) as exc:
        raise PacosUnreachable(str(exc)) from exc

    user = body.get("user") if isinstance(body, dict) else None
    if not isinstance(user, dict) or not user.get("id") or not user.get("email"):
        raise PacosUnreachable("PacOs answered without a user")

    _close_session(str(body.get("access_token") or ""), str(body.get("refresh_token") or ""), opener)
    return {
        "id": str(user["id"]),
        "email": str(user["email"]).strip().lower(),
        "full_name": str(user.get("full_name") or ""),
        "roles": [str(r) for r in user.get("roles") or []],
        "permissions": [str(p) for p in user.get("permissions") or []],
    }


def _close_session(access_token: str, refresh_token: str, opener: Opener) -> None:
    """End the PacOs session the sign-in just opened. Best effort: a failure
    here leaves an idle session in PacOs, not a person outside the door."""
    if not access_token:
        return
    req = urllib.request.Request(base_url() + "/api/v1/auth/logout", data=b"{}", method="POST")
    req.add_header("content-type", "application/json")
    req.add_header("authorization", "Bearer " + access_token)
    req.add_header("x-client", "native")
    if refresh_token:
        req.add_header("x-refresh-token", refresh_token)
    try:
        with opener(req, timeout=TIMEOUT_SECONDS):
            pass
    except Exception:  # noqa: BLE001 - deliberately swallowed, see docstring
        return


def allowed(user: dict[str, Any]) -> bool:
    held = user.get("permissions") or []
    return any(key in held for key in ACCEPTED_PERMISSIONS)
