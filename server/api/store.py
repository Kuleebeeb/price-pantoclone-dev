"""Accounts, and taking in what a station made while it was offline.

Kept apart from db.py because it answers a different question. db.py is "what is
in the book"; this is "who is writing, and how does a page written on a machine
with no signal get into the book exactly once".
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from psycopg import Connection

from db import next_reference, pool


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with pool().connection() as conn:
        return conn.execute(
            "SELECT id, email, full_name, password_hash, is_active, pacos_user_id, permissions"
            " FROM users WHERE email = %s",
            (email.strip().lower(),),
        ).fetchone()


def upsert_pacos_user(email: str, full_name: str, pacos_user_id: str, permissions: list[str]) -> dict[str, Any]:
    """One local row per PacOs account, keyed on the email they sign in with.

    Written on EVERY sign-in, not only the first: the name and the permissions
    are PacOs's to change, and a row switched off here is switched back on
    when PacOs says yes - in this mode PacOs is the one source of truth about
    who may enter. The local password_hash is left as it is; it is not read
    while AUTH_MODE=pacos.
    """
    with pool().connection() as conn:
        return conn.execute(
            "INSERT INTO users (email, full_name, password_hash, pacos_user_id, permissions, is_active, last_login_at)"
            " VALUES (%s, %s, NULL, %s, %s::jsonb, TRUE, now())"
            " ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name,"
            "   pacos_user_id = EXCLUDED.pacos_user_id, permissions = EXCLUDED.permissions,"
            "   is_active = TRUE, last_login_at = now()"
            " RETURNING id, email, full_name, password_hash, is_active, pacos_user_id, permissions",
            (email.strip().lower(), full_name.strip(), pacos_user_id, json.dumps(permissions)),
        ).fetchone()


def create_user(email: str, full_name: str, password_hash: str) -> dict[str, Any]:
    with pool().connection() as conn:
        return conn.execute(
            "INSERT INTO users (email, full_name, password_hash) VALUES (%s, %s, %s)"
            " RETURNING id, email, full_name",
            (email.strip().lower(), full_name.strip(), password_hash),
        ).fetchone()


def count_users() -> int:
    with pool().connection() as conn:
        return conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"]


# --------------------------------------------------------------------------- #
# Login throttle
#
# The server address is inside every copy of the .exe and inside every packet it
# sends. It is not a secret and must never be defended as one. What actually
# stops somebody who knows the address is this: guess wrong often enough and the
# door stops answering for a while.
#
# Counted per EMAIL and per SOURCE IP, because the two attacks look nothing
# alike. Grinding one account's password shows up as many failures on one email;
# trying one common password against every account shows up as many failures
# from one address and never more than one per email.
# --------------------------------------------------------------------------- #

WINDOW_MINUTES = 15
MAX_FAILURES_PER_EMAIL = 8
MAX_FAILURES_PER_IP = 30


def record_login_attempt(email: str, source_ip: str, succeeded: bool) -> None:
    with pool().connection() as conn:
        conn.execute(
            "INSERT INTO login_attempts (email, source_ip, succeeded) VALUES (%s, %s, %s)",
            (email.strip().lower()[:200], source_ip[:60], succeeded),
        )
        # Swept here rather than by a cron job. A cron that stops running leaves
        # a table growing quietly for a year; this cannot fall out of step with
        # the thing it is cleaning up because it IS the thing.
        conn.execute("DELETE FROM login_attempts WHERE attempted_at < now() - interval '2 days'")


def login_is_blocked(email: str, source_ip: str) -> bool:
    """Too many recent failures for this account, or from this address.

    Only failures SINCE the last success count. Otherwise somebody who mistyped
    their password all morning would still be locked out after getting it right,
    which teaches people that signing in correctly does not help.
    """
    with pool().connection() as conn:
        by_email = conn.execute(
            """
            SELECT count(*) AS n FROM login_attempts
             WHERE lower(email) = %s
               AND attempted_at > now() - make_interval(mins => %s)
               AND NOT succeeded
               AND attempted_at > coalesce((
                     SELECT max(attempted_at) FROM login_attempts
                      WHERE lower(email) = %s AND succeeded
                   ), 'epoch'::timestamptz)
            """,
            (email.strip().lower(), WINDOW_MINUTES, email.strip().lower()),
        ).fetchone()["n"]
        if by_email >= MAX_FAILURES_PER_EMAIL:
            return True

        if not source_ip:
            return False
        by_ip = conn.execute(
            """
            SELECT count(*) AS n FROM login_attempts
             WHERE source_ip = %s
               AND attempted_at > now() - make_interval(mins => %s)
               AND NOT succeeded
            """,
            (source_ip, WINDOW_MINUTES),
        ).fetchone()["n"]
        return by_ip >= MAX_FAILURES_PER_IP


# --------------------------------------------------------------------------- #
# Sync
# --------------------------------------------------------------------------- #


def sync_quotations(
    rows: list[dict[str, Any]], *, user_id: int, device_name: str
) -> list[dict[str, Any]]:
    """Take rows a station made offline and give each one its real number.

    IDEMPOTENT BY client_uid. A batch sent twice - the answer lost on the way
    back, the station retrying in the morning - returns the numbers already
    issued instead of issuing a second set. Without that, one dropped reply is
    one duplicated quotation under two references, and nobody finds out until
    the customer asks which one is real.

    The number is issued HERE and not on the station, and that is the whole
    reason this endpoint exists: two laptops that both counted MAX()+1 in their
    own SQLite would both call it QT-20260827-0001.
    """
    out: list[dict[str, Any]] = []
    with pool().connection() as conn:
        with conn.transaction():
            for row in rows:
                uid = str(row.get("client_uid", "")).strip()
                if not uid:
                    raise ValueError("thieu client_uid")

                seen = conn.execute(
                    "SELECT quote_ref FROM quotations WHERE client_uid = %s", (uid,)
                ).fetchone()
                if seen:
                    out.append({"client_uid": uid, "quote_ref": seen["quote_ref"], "created": False})
                    continue

                quote_date = row["quote_date"]
                if isinstance(quote_date, str):
                    quote_date = date.fromisoformat(quote_date)
                ref = next_reference(conn, quote_date)

                conn.execute(
                    """
                    INSERT INTO quotations (
                        quote_ref, client_uid, device_name, created_by, saved_at,
                        quote_date, customer, customer_code, item_description,
                        product_reference, product_image_path, revised_from_ref, product_key,
                        product_label, size_text, length_reference, inputs_json, formulas_json,
                        results_json, unit_price, total_price, grams_per_item, pack_quantity,
                        pack_weight_kg, sack_quantity, sack_weight_kg
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        ref,
                        uid,
                        device_name,
                        user_id,
                        row.get("saved_at"),
                        quote_date,
                        row["customer"],
                        row.get("customer_code", ""),
                        row.get("item_description", ""),
                        row.get("product_reference", ""),
                        row.get("product_image_path", ""),
                        row.get("revised_from_ref", ""),
                        row["product_key"],
                        row["product_label"],
                        row["size_text"],
                        row.get("length_reference", ""),
                        json.dumps(row.get("inputs", {}), ensure_ascii=False),
                        json.dumps(row.get("formulas", {}), ensure_ascii=False),
                        json.dumps(row.get("results", {}), ensure_ascii=False),
                        row["unit_price"],
                        row["total_price"],
                        row["grams_per_item"],
                        row.get("pack_quantity", 0),
                        row.get("pack_weight_kg", 0),
                        row.get("sack_quantity", 0),
                        row.get("sack_weight_kg", 0),
                    ),
                )
                out.append({"client_uid": uid, "quote_ref": ref, "created": True})
    return out


def next_drawing_reference(conn: Connection, year: str) -> str:
    row = conn.execute(
        """
        INSERT INTO drawing_counters (counter_year, last_number)
        VALUES (%s, 1)
        ON CONFLICT (counter_year)
        DO UPDATE SET last_number = drawing_counters.last_number + 1
        RETURNING last_number
        """,
        (year,),
    ).fetchone()
    return "DFA-" + year + "-" + str(row["last_number"]).zfill(4)


def sync_drawings(
    rows: list[dict[str, Any]], *, user_id: int, device_name: str
) -> list[dict[str, Any]]:
    """Same contract as quotations, and one rule of its own.

    A REVISION IS NOT A NEW DOCUMENT. Revision B keeps the number Revision A was
    given; only the letter moves. So a row that names an amended_from writes
    over that document instead of taking a fresh number - otherwise the customer
    receives a second document number for the same conversation and the trail of
    what was agreed breaks in half.
    """
    out: list[dict[str, Any]] = []
    with pool().connection() as conn:
        with conn.transaction():
            for row in rows:
                uid = str(row.get("client_uid", "")).strip()
                if not uid:
                    raise ValueError("thieu client_uid")

                seen = conn.execute(
                    "SELECT doc_no FROM drawings WHERE client_uid = %s", (uid,)
                ).fetchone()
                if seen:
                    out.append({"client_uid": uid, "doc_no": seen["doc_no"], "created": False})
                    continue

                drawing_date = row["drawing_date"]
                if isinstance(drawing_date, str):
                    drawing_date = date.fromisoformat(drawing_date)

                amended_from = str(row.get("amended_from", "")).strip()
                doc_no = amended_from or next_drawing_reference(conn, drawing_date.strftime("%Y"))

                conn.execute(
                    """
                    INSERT INTO drawings (
                        doc_no, client_uid, drawing_date, revision, amended_from, customer,
                        customer_code, title, part_no, product_key, length_datum, display_unit,
                        width_mm, length_mm, height_mm, gusset_mm, thickness_mm, quote_ref,
                        spec_json, device_name, created_by
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (doc_no) DO UPDATE SET
                        revision = EXCLUDED.revision,
                        spec_json = EXCLUDED.spec_json,
                        title = EXCLUDED.title,
                        quote_ref = EXCLUDED.quote_ref,
                        client_uid = EXCLUDED.client_uid
                    """,
                    (
                        doc_no,
                        uid,
                        drawing_date,
                        row.get("revision", "A"),
                        amended_from,
                        row["customer"],
                        row.get("customer_code", ""),
                        row.get("title", ""),
                        row.get("part_no", ""),
                        row["product_key"],
                        row.get("length_datum", ""),
                        row.get("display_unit", "mm"),
                        row["width_mm"],
                        row["length_mm"],
                        row.get("height_mm", 0),
                        row.get("gusset_mm", 0),
                        row.get("thickness_mm", 0),
                        row.get("quote_ref", ""),
                        json.dumps(row.get("spec", {}), ensure_ascii=False),
                        device_name,
                        user_id,
                    ),
                )
                out.append({"client_uid": uid, "doc_no": doc_no, "created": True})
    return out


def import_quotations(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Load quotations that ALREADY have their numbers, from the old paper books.

    The opposite of sync_quotations in the one way that matters: nothing here
    issues a reference. 2569/09-01 is the number the customer was given years
    ago and is still holding, and a server that renamed it would sever the row
    from the document it describes.

    Idempotent by quote_ref rather than by client_uid, because the reference IS
    the identity of a document that already existed. Running the load twice adds
    nothing - and it will be run twice, because the first pass always turns up a
    workbook somebody forgot to mention.
    """
    added = 0
    seen = 0
    with pool().connection() as conn:
        with conn.transaction():
            for row in rows:
                seen += 1
                quote_date = row["quote_date"]
                if isinstance(quote_date, str):
                    quote_date = date.fromisoformat(quote_date)
                cursor = conn.execute(
                    """
                    INSERT INTO quotations (
                        quote_ref, quote_date, customer, customer_code, item_description,
                        product_reference, product_image_path, revised_from_ref, product_key,
                        product_label, size_text, length_reference, inputs_json, formulas_json,
                        results_json, unit_price, total_price, grams_per_item, pack_quantity,
                        pack_weight_kg, sack_quantity, sack_weight_kg, import_source
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (quote_ref) DO NOTHING
                    """,
                    (
                        row["quote_ref"],
                        quote_date,
                        row["customer"],
                        row.get("customer_code", ""),
                        row.get("item_description", ""),
                        row.get("product_reference", ""),
                        row.get("product_image_path", ""),
                        row.get("revised_from_ref", ""),
                        row["product_key"],
                        row["product_label"],
                        row.get("size_text", ""),
                        row.get("length_reference", ""),
                        json.dumps(row.get("inputs", {}), ensure_ascii=False),
                        json.dumps(row.get("formulas", {}), ensure_ascii=False),
                        json.dumps(row.get("results", {}), ensure_ascii=False),
                        row.get("unit_price", 0),
                        row.get("total_price", 0),
                        row.get("grams_per_item", 0),
                        row.get("pack_quantity", 0),
                        row.get("pack_weight_kg", 0),
                        row.get("sack_quantity", 0),
                        row.get("sack_weight_kg", 0),
                        row.get("import_source", ""),
                    ),
                )
                added += cursor.rowcount
    return {"seen": seen, "added": added}


def quotations_after(after_id: int, limit: int = 500) -> list[dict[str, Any]]:
    """A page of history, walked by row id rather than by timestamp.

    created_at is the obvious cursor and the wrong one here. A bulk load writes
    tens of thousands of rows inside one transaction, so they all carry the same
    instant, and `created_at > stamp` steps straight over every row that shares
    the last one's timestamp. The id never ties.
    """
    with pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM quotations WHERE id > %s ORDER BY id ASC LIMIT %s",
            (after_id, limit),
        ).fetchall()


def quotation_count() -> int:
    with pool().connection() as conn:
        return conn.execute("SELECT count(*) AS n FROM quotations").fetchone()["n"]


def quotations_changed_since(stamp: str | None, limit: int = 500) -> list[dict[str, Any]]:
    """What other stations have added, so a machine that was away can catch up."""
    where = "WHERE created_at > %s" if stamp else ""
    args: list[Any] = [stamp] if stamp else []
    args.append(limit)
    with pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM quotations " + where + " ORDER BY created_at ASC LIMIT %s", args
        ).fetchall()


def drawings_changed_since(stamp: str | None, limit: int = 500) -> list[dict[str, Any]]:
    where = "WHERE created_at > %s" if stamp else ""
    args: list[Any] = [stamp] if stamp else []
    args.append(limit)
    with pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM drawings " + where + " ORDER BY created_at ASC LIMIT %s", args
        ).fetchall()


# --------------------------------------------------------------------------- #
# The web screen's own drawing register (app.py drawing_save / search /
# load_selected, 2295-2423). Same table, same counter as the sync above.
# --------------------------------------------------------------------------- #


def save_drawing_web(record: dict[str, Any], *, user_id: int | None) -> str:
    """Save from the web tab. An empty doc_no is issued a DFA- number; a row
    that already carries one keeps it - a revision is not a new document."""
    with pool().connection() as conn:
        with conn.transaction():
            drawing_date = record["drawing_date"]
            if isinstance(drawing_date, str):
                drawing_date = date.fromisoformat(drawing_date)
            doc_no = str(record.get("doc_no") or "").strip()
            if not doc_no.startswith("DFA-"):
                doc_no = next_drawing_reference(conn, drawing_date.strftime("%Y"))
            conn.execute(
                """
                INSERT INTO drawings (
                    doc_no, drawing_date, revision, customer, customer_code, title,
                    part_no, product_key, length_datum, display_unit,
                    width_mm, length_mm, height_mm, gusset_mm, thickness_mm,
                    quote_ref, spec_json, device_name, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                          %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (doc_no) DO UPDATE SET
                    drawing_date = EXCLUDED.drawing_date,
                    revision = EXCLUDED.revision,
                    customer = EXCLUDED.customer,
                    customer_code = EXCLUDED.customer_code,
                    title = EXCLUDED.title,
                    part_no = EXCLUDED.part_no,
                    product_key = EXCLUDED.product_key,
                    length_datum = EXCLUDED.length_datum,
                    display_unit = EXCLUDED.display_unit,
                    width_mm = EXCLUDED.width_mm,
                    length_mm = EXCLUDED.length_mm,
                    height_mm = EXCLUDED.height_mm,
                    gusset_mm = EXCLUDED.gusset_mm,
                    thickness_mm = EXCLUDED.thickness_mm,
                    spec_json = EXCLUDED.spec_json
                """,
                (
                    doc_no,
                    drawing_date,
                    record.get("revision", "A"),
                    record["customer"],
                    record.get("customer_code", ""),
                    record["title"],
                    record.get("part_no", "-"),
                    record["product_key"],
                    record.get("length_datum", ""),
                    record.get("display_unit", "mm"),
                    record["width_mm"],
                    record["length_mm"],
                    record.get("height_mm", 0),
                    record.get("gusset_mm", 0),
                    record.get("thickness_mm", 0),
                    record.get("quote_ref", ""),
                    json.dumps(record.get("spec", {}), ensure_ascii=False),
                    "web",
                    user_id,
                ),
            )
    return doc_no


def search_drawings(query: str, limit: int = 100) -> list[dict[str, Any]]:
    args: list[Any] = []
    where = ""
    if query:
        like = "%" + query + "%"
        where = (
            "WHERE doc_no ILIKE %s OR customer ILIKE %s OR customer_code ILIKE %s"
            " OR title ILIKE %s OR part_no ILIKE %s"
        )
        args = [like, like, like, like, like]
    args.append(limit)
    with pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM drawings " + where + " ORDER BY doc_no DESC LIMIT %s", args
        ).fetchall()


def get_drawing(doc_no: str) -> dict[str, Any] | None:
    with pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM drawings WHERE doc_no = %s", (doc_no,)
        ).fetchone()
