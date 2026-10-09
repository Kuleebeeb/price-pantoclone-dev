"""Real PostgreSQL regression for trashing a quote during Sample issuance.

Requires a disposable *_smoke database migrated through 0013. With BASE set,
the race also checks the HTTP 409 contract against that same disposable API.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

DSN = os.environ.get("DATABASE_URL", "")
BASE = os.environ.get("BASE", "").rstrip("/")
target = urlparse(DSN)
if (os.environ.get("PANTONGONE_DISPOSABLE_TEST") != "1"
        or target.hostname not in {"localhost", "127.0.0.1", "postgres", "db"}
        or not target.path.endswith("_smoke")
        or BASE and urlparse(BASE).hostname not in {"localhost", "127.0.0.1", "api"}):
    raise SystemExit("Explicit disposable local *_smoke database and API required")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
import db  # noqa: E402

run = uuid4().hex
token = ""


def call(method, path, body):
    req = Request(BASE + path, method=method, data=json.dumps(body).encode(),
                  headers={"content-type": "application/json", **({"authorization": "Bearer " + token} if token else {})})
    try:
        with urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def new_quote(suffix):
    ref = "SYNTH-TRASH-RACE-" + run + "-" + suffix
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        row = conn.execute("""INSERT INTO quotations
            (quote_ref,quote_date,customer,product_key,product_label,size_text,
             inputs_json,formulas_json,results_json,unit_price,total_price,grams_per_item)
            VALUES(%s,current_date,'Synthetic race fixture','flat','Flat','10 x 20',
                   '{}'::jsonb,'{}'::jsonb,'{}'::jsonb,1,1,1) RETURNING *""", (ref,)).fetchone()
    return ref, row


def insert_sample(conn, ref, suffix):
    snapshot = {"quote_ref": ref, "quote_version": 1, "width_mm": 100, "length_mm": 200,
                "thickness_mm": .08, "synthetic_marker": run}
    row = conn.execute("""INSERT INTO sample_inspections
        (report_no,quote_ref,customer,product,inspection_date,product_key,
         width_mm,length_mm,thickness_mm,thickness_mode,source_snapshot)
        VALUES(%s,%s,'Synthetic race fixture','Synthetic flat',current_date,'flat',100,200,.08,'side',%s)
        RETURNING id,source_snapshot""", ("SYNTH-SI-" + run + "-" + suffix, ref, Jsonb(snapshot))).fetchone()
    return row["id"], snapshot


def delete(ref):
    if BASE:
        return call("DELETE", "/api/quotations/" + quote(ref, safe=""), {"reason": "Synthetic race regression"})
    try:
        removed = db.trash_quotation(ref, reason="Synthetic race regression", typed_actor="", user_id=None, user_name="Synthetic regression")
        return (200, {"deleted": ref}) if removed else (404, {})
    except db.DocumentConflict as error:
        return 409, {"detail": str(error)}


try:
    if BASE:
        status, login = call("POST", "/api/auth/login", {
            "email": os.environ.get("BOOTSTRAP_EMAIL", "smoke@test.local"),
            "password": os.environ.get("BOOTSTRAP_PASSWORD", "smoke-pass-1234")})
        assert status == 200, "Synthetic API login failed"
        token = login["token"]

    ordinary, original = new_quote("ordinary")
    assert delete(ordinary)[0] == 200
    assert db.get_quotation(ordinary) is None
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        saved = conn.execute("SELECT row_json FROM quotation_trash WHERE quote_ref=%s", (ordinary,)).fetchone()["row_json"]
        assert saved == db._jsonable(original), "Ordinary deletion must preserve the whole row"
    assert db.restore_quotation(ordinary, user_id=None, user_name="Synthetic regression")
    assert db.get_quotation(ordinary) == original, "Restore must retain the original ID and values"

    racing, racing_original = new_quote("racing")
    with psycopg.connect(DSN, row_factory=dict_row) as holder:
        holder.execute("SELECT version FROM quotations WHERE quote_ref=%s FOR SHARE", (racing,))
        holder_pid = holder.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
        sample_id, snapshot = insert_sample(holder, racing, "racing")
        # The API's preliminary check cannot see an uncommitted Sample.
        assert db.quotation_references(racing) == []
        with ThreadPoolExecutor(max_workers=1) as workers:
            future = workers.submit(delete, racing)
            try:
                blocked = False
                with psycopg.connect(DSN, autocommit=True) as observer:
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline and not future.done():
                        blocked = observer.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE %s=ANY(pg_blocking_pids(pid)))", (holder_pid,)).fetchone()[0]
                        if blocked:
                            break
                        time.sleep(.02)
                assert blocked, "Deletion must wait for the issuing Sample's quotation lock"
                holder.commit()
            finally:
                holder.rollback()
            status, result = future.result(timeout=10)
        assert status == 409 and "Cannot delete: used by" in result["detail"]
        assert db.get_quotation(racing) == racing_original
        assert db.get_sample_inspection(sample_id)["source_snapshot"] == snapshot
        with psycopg.connect(DSN) as conn:
            assert conn.execute("SELECT count(*) FROM quotation_trash WHERE quote_ref=%s", (racing,)).fetchone()[0] == 0

    hidden, hidden_original = new_quote("hidden-import")
    # The historical importer can retain a hidden quote and an issued snapshot;
    # the normal user delete guard must not reintroduce the old active-row FK.
    with psycopg.connect(DSN, row_factory=dict_row) as conn:
        conn.execute("INSERT INTO quotation_trash(quote_ref,row_json,reason,deleted_by) VALUES(%s,%s,'Synthetic historical hide','Synthetic import')", (hidden, Jsonb(db._jsonable(hidden_original))))
        conn.execute("DELETE FROM quotations WHERE quote_ref=%s", (hidden,))
        hidden_sample_id, hidden_snapshot = insert_sample(conn, hidden, "hidden")
    assert db.get_sample_inspection(hidden_sample_id)["source_snapshot"] == hidden_snapshot
    assert db.get_quotation(hidden) is None
    try:
        db.save_sample_inspection({"quote_ref": hidden, "source_snapshot": hidden_snapshot})
    except KeyError:
        pass
    else:
        raise AssertionError("New normal Sample creation still requires an active quotation")
    print("PASS: ordinary trash/restore; concurrent Sample issuance refuses delete; hidden imported snapshot FK retained" + (" (HTTP 409 verified)" if BASE else " (database mode)"))
finally:
    db.close_pool()
