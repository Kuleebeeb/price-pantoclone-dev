"""The button that sends ticked prices to PacOs, and the customer mirror's
switches. Words come from screen.py like every other sentence on the screen."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

import db
import pacos_bridge
import pacos_gate
import routes_auth
import screen

router = APIRouter(prefix="/api/bridge")


class HandoffRequest(BaseModel):
    refs: list[str]


def _off() -> HTTPException:
    return HTTPException(status_code=503, detail=screen.BRIDGE["off"])


@router.post("/handoffs")
def create_handoff(body: HandoffRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = routes_auth.current_user(authorization)
    if not pacos_bridge.configured():
        raise _off()
    # The handoff is opened in PacOs by the person's OWN session, matched on
    # e-mail. Signed in locally, their e-mail is whatever the local table says
    # and PacOs would show them nothing - so the door is only open when the
    # sign-in itself went through PacOs.
    if pacos_gate.mode() != "pacos":
        raise HTTPException(status_code=409, detail=screen.BRIDGE["needs_pacos_login"])

    refs: list[str] = []
    for ref in body.refs:
        ref = ref.strip()
        if ref and ref not in refs:
            refs.append(ref)
    if not refs:
        raise HTTPException(status_code=400, detail=screen.BRIDGE["select_first"])

    rows = db.quotations_by_refs(refs)
    missing = [ref for ref in refs if ref not in {r["quote_ref"] for r in rows}]
    if missing:
        raise HTTPException(status_code=404, detail=screen.BRIDGE["missing"].replace("{ref}", ", ".join(missing)))

    try:
        payload = pacos_bridge.build_handoff(rows, user["email"])
    except pacos_bridge.SelectionError as exc:
        sentence = screen.BRIDGE.get(exc.code, screen.BRIDGE["select_first"]).replace("{ref}", exc.ref)
        raise HTTPException(status_code=409 if exc.code in ("mixed_customers", "no_customer_code") else 400, detail=sentence) from exc

    try:
        handoff_id = pacos_bridge.push_handoff(payload)
    except pacos_bridge.BridgeError as exc:
        status = exc.status if exc.status in (400, 401, 503) else 502
        raise HTTPException(status_code=status, detail="PacOs: " + exc.message) from exc

    return {
        "handoff_id": handoff_id,
        "url": pacos_bridge.handoff_url(handoff_id),
        "lines": len(payload["lines"]),
        "customer": payload["customer_name"],
        "customer_code": payload["customer_code"],
    }


@router.post("/customers/sync")
def sync_customers(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    routes_auth.current_user(authorization)
    if not pacos_bridge.configured():
        raise _off()
    status = pacos_bridge.run_sync()
    if not status["ok"]:
        raise HTTPException(status_code=502, detail="PacOs: " + status["error"])
    return status


@router.get("/status")
def status(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    routes_auth.current_user(authorization)
    return {"configured": pacos_bridge.configured(), "last_sync": dict(pacos_bridge.last_sync)}
