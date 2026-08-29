"""Signing in, and taking in a day's work from a station that was offline.

These four routes are the whole difference between the .exe the CEO built and a
program a factory can run: an account, and a way for what a laptop wrote with no
signal to reach the same book everyone else reads.

SINCE 28-08-2026 THE PASSWORD MAY BE PACOS'S. With AUTH_MODE=pacos the gate
sends what was typed to PacOs and lets PacOs answer - one account for both
programs, switched off in one place. pacos_gate.py says why and how. The
token this service hands back is still its own; PacOs's secret never comes
here.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

import auth
import pacos_gate
import store

router = APIRouter(prefix="/api")


class LoginRequest(BaseModel):
    email: str
    password: str


class SyncQuotation(BaseModel):
    """One row a station saved locally. The numbers are already worked out by
    the station's own copy of calculator.py, and the server keeps them as they
    are - it is the same code, so re-running it would only add a chance to
    differ."""

    client_uid: str
    quote_date: str
    customer: str
    customer_code: str = ""
    item_description: str = ""
    product_reference: str = ""
    product_image_path: str = ""
    revised_from_ref: str = ""
    product_key: str
    product_label: str
    size_text: str
    length_reference: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    formulas: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, Any] = Field(default_factory=dict)
    unit_price: float
    total_price: float
    grams_per_item: float
    pack_quantity: float = 0
    pack_weight_kg: float = 0
    sack_quantity: float = 0
    sack_weight_kg: float = 0
    saved_at: str | None = None


class SyncDrawing(BaseModel):
    client_uid: str
    drawing_date: str
    revision: str = "A"
    amended_from: str = ""
    customer: str
    customer_code: str = ""
    title: str = ""
    part_no: str = ""
    product_key: str
    length_datum: str = ""
    display_unit: str = "mm"
    width_mm: float
    length_mm: float
    height_mm: float = 0
    gusset_mm: float = 0
    thickness_mm: float = 0
    quote_ref: str = ""
    spec: dict[str, Any] = Field(default_factory=dict)


class PushQuotations(BaseModel):
    device_name: str = ""
    rows: list[SyncQuotation]


class PushDrawings(BaseModel):
    device_name: str = ""
    rows: list[SyncDrawing]


def current_user(authorization: str | None) -> dict[str, Any]:
    """Every data route goes through here. No header, no data.

    401 and not 403: the caller is not known, rather than known and refused -
    and the station reads that difference to decide whether to ask for the
    password again or just say the server said no.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="กรุณาเข้าสู่ระบบ / please sign in")
    try:
        claims = auth.read_token(authorization.split(" ", 1)[1].strip())
    except auth.AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user = store.get_user_by_email(str(claims.get("email", "")))
    # Checked on every request, not just at sign-in: a token issued this morning
    # must stop working the moment somebody's account is switched off.
    if user is None or not user["is_active"]:
        raise HTTPException(status_code=401, detail="บัญชีถูกปิด / account is closed")
    return user


def caller_ip(request: Request) -> str:
    """Who is knocking, as far as nginx will say.

    X-Real-IP is set by our own nginx site and is the only header trusted here.
    X-Forwarded-For is deliberately not read: a client can send that header
    itself, and a throttle that counts a number the attacker chooses is a
    throttle that resets whenever they like.
    """
    header = request.headers.get("x-real-ip", "").strip()
    if header:
        return header[:60]
    return (request.client.host if request.client else "")[:60]


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "permissions": list(user.get("permissions") or []),
    }


def _session_of(user: dict[str, Any]) -> dict[str, Any]:
    issued = auth.issue_token(user["id"], user["email"])
    return {"token": issued["token"], "expires_at": issued["expires_at"], "user": public_user(user)}


@router.post("/auth/login")
def login(body: LoginRequest, request: Request) -> dict[str, Any]:
    source_ip = caller_ip(request)

    # Checked BEFORE the password is verified. Verifying first would keep the
    # expensive scrypt sum running for every guess, so the lockout would protect
    # the account while leaving the server itself as the thing being attacked.
    # In PacOs mode the same check spares PacOs from a grinder that found us.
    if store.login_is_blocked(body.email, source_ip):
        raise HTTPException(
            status_code=429,
            detail=(
                "ลองผิดหลายครั้งเกินไป กรุณารอ "
                + str(store.WINDOW_MINUTES)
                + " นาทีแล้วลองใหม่ / too many failed attempts - wait "
                + str(store.WINDOW_MINUTES)
                + " minutes and try again"
            ),
        )

    if pacos_gate.mode() == "pacos":
        return _login_via_pacos(body, source_ip)

    user = store.get_user_by_email(body.email)
    # One message for "no such account" and for "wrong password", on purpose:
    # two different messages tell whoever is guessing which half they got right.
    bad = HTTPException(status_code=401, detail="อีเมลหรือรหัสผ่านไม่ถูกต้อง / that email and password do not match")
    if user is None or not user["is_active"]:
        store.record_login_attempt(body.email, source_ip, False)
        raise bad
    if not auth.verify_password(body.password, user["password_hash"]):
        store.record_login_attempt(body.email, source_ip, False)
        raise bad

    store.record_login_attempt(body.email, source_ip, True)
    return _session_of(user)


def _login_via_pacos(body: LoginRequest, source_ip: str) -> dict[str, Any]:
    """PacOs decides. This function only translates its answer for the gate.

    Only a wrong password is counted against the local throttle. A switched-off
    account already knew the password; PacOs being down is not the caller's
    doing; and "no permission" is a right password on the wrong account -
    counting any of those would lock somebody out for a thing they did not do.
    """
    try:
        who = pacos_gate.sign_in(body.email, body.password, caller_ip=source_ip)
    except pacos_gate.PacosRefused as exc:
        if exc.status == 401:
            store.record_login_attempt(body.email, source_ip, False)
            raise HTTPException(
                status_code=401,
                detail="อีเมลหรือรหัสผ่านไม่ถูกต้อง / that email and password do not match",
            ) from exc
        if exc.status == 429:
            raise HTTPException(
                status_code=429,
                detail="ลองผิดหลายครั้งเกินไป / " + (exc.message or "too many failed sign-in attempts - wait and try again"),
                headers={"Retry-After": exc.retry_after} if exc.retry_after else None,
            ) from exc
        raise HTTPException(
            status_code=403,
            detail="บัญชี PacOs นี้ถูกปิด / this PacOs account has been switched off - ask IT",
        ) from exc
    except pacos_gate.PacosUnreachable as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "ต่อ PacOs ไม่ได้ จึงยังเข้าสู่ระบบไม่ได้ / PacOs could not be reached, "
                "so nobody can sign in right now (" + str(exc) + ")"
            ),
        ) from exc

    if not pacos_gate.allowed(who):
        # Right password, wrong account: the person exists in PacOs and may not
        # see the cost structure there either. Naming the permission sends them
        # to the right colleague, as PacOs's own refusal does.
        raise HTTPException(
            status_code=403,
            detail=(
                "บัญชี PacOs นี้ไม่มีสิทธิ์ดูโครงสร้างต้นทุน จึงใช้โปรแกรมคำนวณราคาไม่ได้ / "
                "this PacOs account may not see the cost structure, so it cannot use the "
                "pricing program (needs " + pacos_gate.REQUIRED_PERMISSION + ")"
            ),
        )

    user = store.upsert_pacos_user(who["email"], who["full_name"], who["id"], who["permissions"])
    store.record_login_attempt(body.email, source_ip, True)
    return _session_of(user)


@router.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    return public_user(current_user(authorization))


@router.post("/sync/quotations")
def push_quotations(
    body: PushQuotations, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    user = current_user(authorization)
    try:
        mapped = store.sync_quotations(
            [row.model_dump() for row in body.rows],
            user_id=user["id"],
            device_name=body.device_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"mapped": mapped, "count": len(mapped)}


@router.post("/sync/drawings")
def push_drawings(
    body: PushDrawings, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    user = current_user(authorization)
    try:
        mapped = store.sync_drawings(
            [row.model_dump() for row in body.rows],
            user_id=user["id"],
            device_name=body.device_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"mapped": mapped, "count": len(mapped)}


@router.get("/sync/quotations")
def pull_quotations(
    since: str | None = None,
    after_id: int = 0,
    limit: int = 500,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """A page of the book, so a machine that was away can catch up.

    Paged by row id. A station coming to a server that already holds the
    factory's whole paper history has tens of thousands of rows to fetch, and
    they were all written in one transaction - so they share a created_at, and a
    timestamp cursor walks straight past every row that ties with the last one.

    `since` is kept for the older shape of this call and is only consulted when
    no id cursor is given.
    """
    current_user(authorization)
    limit = max(1, min(limit, 2000))
    if after_id or not since:
        rows = store.quotations_after(after_id, limit)
    else:
        rows = store.quotations_changed_since(since, limit)
    next_id = rows[-1]["id"] if rows else after_id
    return {
        "rows": rows,
        "count": len(rows),
        "next_id": next_id,
        "total": store.quotation_count(),
    }


@router.get("/sync/drawings")
def pull_drawings(
    since: str | None = None, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    current_user(authorization)
    rows = store.drawings_changed_since(since)
    return {"rows": rows, "count": len(rows)}


def bootstrap_admin() -> str | None:
    """The one account that exists before anybody can sign in.

    Read once, at boot, and only when the table is empty - so leaving the
    variables in the environment does not reset a password somebody changed.
    There is no self-registration route: accounts are made by whoever runs the
    server. With AUTH_MODE=pacos there is nothing to make: the accounts are
    PacOs's, and a local admin row would be a password that opens nothing.
    """
    if pacos_gate.mode() == "pacos":
        return None
    email = os.environ.get("BOOTSTRAP_EMAIL", "").strip()
    password = os.environ.get("BOOTSTRAP_PASSWORD", "").strip()
    if not email or not password:
        return None
    if store.count_users() > 0:
        return None
    store.create_user(email, os.environ.get("BOOTSTRAP_NAME", "Administrator"), auth.hash_password(password))
    return email
