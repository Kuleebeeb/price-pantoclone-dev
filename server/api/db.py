"""Postgres access for the pricing app. SQL written by hand, no ORM."""

from __future__ import annotations

import json
import hashlib
import os
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from psycopg import Connection, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

MIGRATIONS_DIR = Path(__file__).with_name("migrations")

_pool: ConnectionPool | None = None


def dsn() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL chua duoc dat")
    return url


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(dsn(), min_size=1, max_size=8, kwargs={"row_factory": dict_row})
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def run_migrations() -> list[str]:
    """Forward-only, numbered files, applied once. No down files: the way back is a backup."""
    applied: list[str] = []
    with pool().connection() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        done = {r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in done:
                continue
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
            applied.append(path.name)
    return applied


def ping() -> None:
    with pool().connection() as conn:
        conn.execute("SELECT 1")


def next_reference(conn: Connection, quote_date: date) -> str:
    """Hand out QT-YYYYMMDD-NNNN in one statement so two savers cannot collide.

    The desktop original used SELECT MAX()+1 (database.py:147). Two people pressing
    Save in the same second read the same maximum and write the same number; the
    UNIQUE index then rejects one of them with an error nobody can explain.
    """
    row = conn.execute(
        """
        INSERT INTO quotation_counters (counter_date, last_number)
        VALUES (%s, 1)
        ON CONFLICT (counter_date)
        DO UPDATE SET last_number = quotation_counters.last_number + 1
        RETURNING last_number
        """,
        (quote_date,),
    ).fetchone()
    stamp = quote_date.strftime("%Y%m%d")
    return "QT-" + stamp + "-" + str(row["last_number"]).zfill(4)


class DocumentConflict(ValueError):
    """A stale form or a request id reused for different contents."""


def _jsonable(value: Any) -> Any:
    def encode(item):
        if isinstance(item, (datetime, date)):
            return item.isoformat()
        if isinstance(item, Decimal):
            return int(item) if item.as_tuple().exponent >= 0 else float(item)
        return str(item)
    return json.loads(json.dumps(value, default=encode, ensure_ascii=False))


def audit_document(conn, kind, identity, action, before, after, actor_id=None, actor_name=""):
    conn.execute(
        "INSERT INTO document_audit(entity_type,entity_id,action,before_json,after_json,actor_id,actor_name)"
        " VALUES(%s,%s,%s,%s,%s,%s,%s)",
        (kind, str(identity), action, Jsonb(_jsonable(before)) if before is not None else None,
         Jsonb(_jsonable(after)) if after is not None else None, actor_id, actor_name),
    )


def _saved_request(conn, scope, actor_id, request_id, fingerprint):
    if not request_id:
        return None
    actor_key = str(actor_id or "local")
    # Locks both a first request and its concurrent retries before a row exists.
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                 (scope + ":" + actor_key + ":" + request_id,))
    old = conn.execute(
        "SELECT fingerprint,response_json FROM document_save_requests"
        " WHERE scope=%s AND actor_key=%s AND request_id=%s", (scope, actor_key, request_id),
    ).fetchone()
    if old and old["fingerprint"] != fingerprint:
        raise DocumentConflict("คำขอบันทึกนี้ถูกใช้กับข้อมูลอื่นแล้ว / This save request was used with different contents")
    return old["response_json"] if old else None


def _remember_request(conn, scope, actor_id, request_id, fingerprint, response):
    if request_id:
        conn.execute(
            "INSERT INTO document_save_requests(scope,actor_key,request_id,fingerprint,response_json) VALUES(%s,%s,%s,%s,%s)",
            (scope, str(actor_id or "local"), request_id, fingerprint, Jsonb(_jsonable(response))),
        )


def request_fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def save_quotation(record: dict[str, Any], *, update_ref="", expected_version=None,
                   request_id="", fingerprint="", actor_id=None, actor_name="",
                   preserve_image_path=False) -> dict[str, Any]:
    columns = ["quote_date", "customer", "customer_code", "item_description", "product_reference",
               "product_image_path", "revised_from_ref", "product_key", "product_label", "size_text",
               "length_reference", "inputs_json", "formulas_json", "results_json", "unit_price", "total_price",
               "grams_per_item", "pack_quantity", "pack_weight_kg", "sack_quantity", "sack_weight_kg"]
    data = {**record, "inputs_json": record["inputs"], "formulas_json": record["formulas"], "results_json": record["results"]}
    for name in ("customer_code", "item_description", "product_reference", "product_image_path", "revised_from_ref", "length_reference"):
        data.setdefault(name, "")
    for name in ("pack_quantity", "pack_weight_kg", "sack_quantity", "sack_weight_kg"):
        data.setdefault(name, 0)
    with pool().connection() as conn:
        with conn.transaction():
            replay = _saved_request(conn, "quotation", actor_id, request_id, fingerprint)
            if replay is not None:
                return replay
            old = None
            if update_ref:
                old = conn.execute("SELECT * FROM quotations WHERE quote_ref=%s FOR UPDATE", (update_ref,)).fetchone()
                if old is None:
                    raise KeyError("Quotation not found")
                if expected_version is None or int(old["version"]) != expected_version:
                    raise DocumentConflict("รายการถูกแก้ไขแล้ว กรุณาเปิดใหม่ / Quotation changed; reopen it before saving")
                # Preserve identity, revision lineage and imported provenance.
                data["revised_from_ref"] = old["revised_from_ref"]
                data["inputs_json"] = {**old["inputs_json"], **data["inputs_json"]}
                if preserve_image_path:
                    data["product_image_path"] = old["product_image_path"]
            values = [Jsonb(data[c]) if c.endswith("_json") else data[c] for c in columns]
            if old:
                assignments = ",".join(c + "=%s" for c in columns)
                row = conn.execute(
                    f"UPDATE quotations SET {assignments},version=version+1,updated_at=now() WHERE quote_ref=%s RETURNING *",
                    values + [update_ref],
                ).fetchone()
            else:
                ref = record.get("quote_ref") or next_reference(conn, record["quote_date"])
                names, marks = ",".join(columns), ",".join(["%s"] * len(columns))
                row = conn.execute(f"INSERT INTO quotations(quote_ref,{names}) VALUES(%s,{marks}) RETURNING *",
                                   [ref] + values).fetchone()
            audit_document(conn, "quotation", row["quote_ref"], "update" if old else "create", old, row, actor_id, actor_name)
            response = _jsonable({key: row[key] for key in ("id", "quote_ref", "created_at", "version")})
            _remember_request(conn, "quotation", actor_id, request_id, fingerprint, response)
    return response


# What a "product" is when the book is folded into folders: the clean name the
# extractor read (inputs_json.product_name), or the raw description for rows
# that never got one. Same name + same size = one folder.
PRODUCT_NAME_SQL = "COALESCE(NULLIF(inputs_json->>'product_name', ''), item_description)"

# The fifteen-column table needs a handful of figures that live inside the
# JSON blocks. Picked out here rather than shipping 500 whole documents.
HISTORY_SELECT = (
    "SELECT id, quote_ref, quote_date, customer, customer_code, item_description,"
    " product_reference, product_key, product_label, size_text, inputs_json,"
    " unit_price, total_price, grams_per_item, created_at,"
    " pack_quantity, pack_weight_kg,"
    " inputs_json->>'sale_basis' AS sale_basis,"
    " COALESCE(inputs_json->'thickness', inputs_json->'dimensions'->'thickness') AS thickness_json,"
    # Web rows keep it in inputs; rows synced from the .exe keep it in
    # results as price_basis_summary. One column, both homes.
    " COALESCE(inputs_json->>'price_basis', results_json->>'price_basis_summary') AS price_basis,"
    " results_json->>'calculated_price_per_kg' AS calc_price_kg,"
    " results_json->>'calculated_price_per_piece_from_kg' AS calc_price_piece,"
    " results_json->>'production_items_per_kg' AS production_items_per_kg,"
    " results_json->>'selling_price_per_kg' AS selling_price_per_kg,"
    # MOQ and selling by the roll (CEO 02-10-2026). Absent on older rows,
    # which the cells then leave blank.
    " inputs_json->>'moq_quantity' AS moq_quantity,"
    " inputs_json->>'moq_unit' AS moq_unit,"
    " inputs_json->>'selling_price_per_kg_override' AS price_kg_basis,"
    " inputs_json->>'selling_price_per_roll_override' AS price_per_roll,"
    " results_json->>'roll_kg' AS roll_kg,"
    " results_json->>'roll_price' AS roll_price,"
    " results_json->>'roll_sale_price' AS roll_sale_price,"
    " results_json->>'roll_quantity' AS roll_quantity,"
    " results_json->>'roll_total_kg' AS roll_total_kg,"
    " results_json->>'roll_total_price' AS roll_total_price"
    " FROM quotations "
)


def _history_where(
    *, customer: str = "", item: str = "", product_key: str = "", size: str = "",
    date_from: date | None = None, date_to: date | None = None,
    exact_customer: str = "", product_name: str | None = None, size_exact: str | None = None,
) -> tuple[str, list[Any]]:
    """The one place the history filters become SQL - the flat table and the
    customer tree must agree on what 'filtered' means, so they share it."""
    where: list[str] = []
    args: list[Any] = []
    if customer:
        where.append("(customer ILIKE %s OR customer_code ILIKE %s)")
        args += ["%" + customer + "%", "%" + customer + "%"]
    if exact_customer:
        where.append("customer = %s")
        args.append(exact_customer)
    if product_name is not None:
        where.append(PRODUCT_NAME_SQL + " = %s")
        args.append(product_name)
    if size_exact is not None:
        where.append("size_text = %s")
        args.append(size_exact)
    if item:
        where.append("(item_description ILIKE %s OR product_reference ILIKE %s)")
        args += ["%" + item + "%", "%" + item + "%"]
    if product_key:
        where.append("product_key = %s")
        args.append(product_key)
    if size:
        where.append("size_text ILIKE %s")
        args.append("%" + size + "%")
    if date_from:
        where.append("quote_date >= %s")
        args.append(date_from)
    if date_to:
        where.append("quote_date <= %s")
        args.append(date_to)
    return ("WHERE " + " AND ".join(where) if where else ""), args


def search_quotations(
    *,
    customer: str = "",
    item: str = "",
    product_key: str = "",
    size: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "newest",
    limit: int = 200,
) -> list[dict[str, Any]]:
    clause, args = _history_where(
        customer=customer, item=item, product_key=product_key, size=size,
        date_from=date_from, date_to=date_to,
    )
    # The desktop's five orders (app.py:3962-3968) - no price sort exists there.
    order = {
        "newest": "quote_date DESC, id DESC",
        "oldest": "quote_date ASC, id ASC",
        "customer": "customer ASC, quote_date DESC",
        "product": "product_label ASC, quote_date DESC",
        "size": "size_text ASC, quote_date DESC",
    }.get(sort, "quote_date DESC, id DESC")
    args.append(limit)
    sql = HISTORY_SELECT + clause + " ORDER BY " + order + " LIMIT %s"
    with pool().connection() as conn:
        return conn.execute(sql, args).fetchall()


def history_customers(**filters: Any) -> list[dict[str, Any]]:
    """Top of the tree: one folder per customer, most recently quoted first."""
    clause, args = _history_where(**filters)
    sql = (
        "SELECT customer,"
        " COALESCE(max(NULLIF(customer_code, '')), '') AS customer_code,"
        " count(*) AS quotes,"
        " count(DISTINCT (" + PRODUCT_NAME_SQL + ", size_text)) AS products,"
        " min(quote_date) AS first_date, max(quote_date) AS last_date"
        " FROM quotations " + clause +
        " GROUP BY customer ORDER BY max(quote_date) DESC, customer ASC LIMIT 2000"
    )
    with pool().connection() as conn:
        return conn.execute(sql, args).fetchall()


def history_products(exact_customer: str, **filters: Any) -> list[dict[str, Any]]:
    """Second level: the customer's products, same name + same size folded
    into one folder, with the price span the folder holds."""
    clause, args = _history_where(exact_customer=exact_customer, **filters)
    sql = (
        "SELECT " + PRODUCT_NAME_SQL + " AS product_name, size_text,"
        " count(*) AS quotes, min(quote_date) AS first_date, max(quote_date) AS last_date,"
        " min(unit_price) AS min_price, max(unit_price) AS max_price,"
        " (array_agg(unit_price ORDER BY quote_date DESC, id DESC))[1] AS latest_price,"
        " (array_agg(inputs_json->>'sale_basis' ORDER BY quote_date DESC, id DESC))[1] AS sale_basis"
        " FROM quotations " + clause +
        " GROUP BY 1, 2 ORDER BY max(quote_date) DESC, count(*) DESC LIMIT 1000"
    )
    with pool().connection() as conn:
        return conn.execute(sql, args).fetchall()


def history_rows(exact_customer: str, product_name: str, size_exact: str, **filters: Any) -> list[dict[str, Any]]:
    """Leaves: every quotation in one product folder, newest first - the price
    of that bag at every point in time it was ever offered."""
    clause, args = _history_where(
        exact_customer=exact_customer, product_name=product_name, size_exact=size_exact, **filters
    )
    sql = HISTORY_SELECT + clause + " ORDER BY quote_date DESC, id DESC LIMIT 500"
    with pool().connection() as conn:
        return conn.execute(sql, args).fetchall()


def count_quotations() -> int:
    with pool().connection() as conn:
        return conn.execute("SELECT count(*) AS n FROM quotations").fetchone()["n"]


def known_customers(limit: int = 2000) -> list[dict[str, Any]]:
    """Every customer in the book, the most-quoted first.

    Ordered by how often they appear rather than alphabetically: the list
    exists to save typing for the company somebody quotes weekly, and A-to-Z
    buries those behind whoever starts with "A".

    The code is the one MOST used with that name, and it is genuinely empty for
    most of them - none of the 17,391 quotations read out of the paper books
    carries a customer code, because the forms never had that column. Returning
    a blank is the honest answer; guessing one would be worse than useless,
    because a wrong code looks like an answered field.
    """
    # SINCE 28-08-2026 PACOS'S LIST COMES FIRST. Every active PacOs customer is
    # offered under PacOs's own name and CODE, counted by the rows already
    # carrying that code; the old names that no PacOs customer matched follow,
    # code blank, so three years of history stay searchable. Picking a PacOs
    # row is what writes the shared code onto the next saved price.
    with pool().connection() as conn:
        rows = conn.execute(
            """
            SELECT customer, customer_code, times FROM (
                SELECT c.name AS customer, c.code AS customer_code,
                       COALESCE(t.times, 0) AS times
                FROM pacos_customers c
                LEFT JOIN (
                    SELECT upper(customer_code) AS code, count(*) AS times
                    FROM quotations WHERE customer_code <> ''
                    GROUP BY 1
                ) t ON t.code = upper(c.code)
                WHERE c.is_active
                UNION ALL
                SELECT customer, '' AS customer_code, count(*) AS times
                FROM quotations
                WHERE customer <> '' AND customer_code = ''
                GROUP BY customer
            ) u
            ORDER BY times DESC, customer
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def quotations_by_refs(refs: list[str]) -> list[dict[str, Any]]:
    """The whole rows for these references, in the order they were asked for."""
    if not refs:
        return []
    with pool().connection() as conn:
        rows = conn.execute("SELECT * FROM quotations WHERE quote_ref = ANY(%s)", (refs,)).fetchall()
    order = {ref: i for i, ref in enumerate(refs)}
    return sorted((dict(r) for r in rows), key=lambda r: order.get(r["quote_ref"], len(refs)))


def find_quotations(q: str, limit: int = 12) -> list[dict[str, Any]]:
    """One box, many columns - the planning tab's source picker.

    Mirrors the desktop's db.find_quotations: a single typed string matched
    against the reference, the customer (name or code) and the item (name or
    part number), newest first. An empty string returns the newest records,
    which is what the ▼ button shows before anybody has typed.
    """
    args: list[Any] = []
    clause = ""
    if q:
        like = "%" + q + "%"
        clause = (
            "WHERE quote_ref ILIKE %s OR customer_code ILIKE %s OR customer ILIKE %s"
            " OR item_description ILIKE %s OR product_reference ILIKE %s"
        )
        args = [like, like, like, like, like]
    args.append(limit)
    with pool().connection() as conn:
        return conn.execute(
            "SELECT quote_ref, quote_date, customer, customer_code, item_description,"
            " product_reference, product_label, size_text"
            " FROM quotations " + clause +
            " ORDER BY quote_date DESC, id DESC LIMIT %s",
            args,
        ).fetchall()


def get_quotation(quote_ref: str) -> dict[str, Any] | None:
    with pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM quotations WHERE quote_ref = %s", (quote_ref,)
        ).fetchone()


def trash_quotation(
    quote_ref: str, *, reason: str, typed_actor: str, user_id: int | None, user_name: str
) -> bool:
    """Move one quotation into quotation_trash, whole, in one transaction.
    False when there is no such reference."""
    with pool().connection() as conn:
        with conn.transaction():
            row = conn.execute(
                "DELETE FROM quotations q WHERE q.quote_ref = %s RETURNING to_jsonb(q) AS row_json",
                (quote_ref,),
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                """
                INSERT INTO quotation_trash (quote_ref, row_json, reason, typed_actor,
                                             deleted_by_user_id, deleted_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (quote_ref, Jsonb(row["row_json"]), reason, typed_actor, user_id, user_name),
            )
    return True


def list_trash(limit: int = 500) -> list[dict[str, Any]]:
    with pool().connection() as conn:
        return conn.execute(
            """
            SELECT quote_ref, reason, typed_actor, deleted_by, deleted_at
              FROM quotation_trash
             WHERE restored_at IS NULL
             ORDER BY deleted_at DESC, id DESC
             LIMIT %s
            """,
            (limit,),
        ).fetchall()


def restore_quotation(quote_ref: str, *, user_id: int | None, user_name: str) -> bool:
    """Put a trashed quotation back exactly as it was - same id, same figures.

    Only the columns the saved document has AND the table still has are
    written, so a column added after the delete takes its default instead of
    being forced to NULL. False when nothing is in the trash under that
    reference; UniqueViolation when the reference is in use again."""
    with pool().connection() as conn:
        with conn.transaction():
            entry = conn.execute(
                "SELECT id, row_json FROM quotation_trash"
                " WHERE quote_ref = %s AND restored_at IS NULL"
                " ORDER BY deleted_at DESC, id DESC LIMIT 1 FOR UPDATE",
                (quote_ref,),
            ).fetchone()
            if entry is None:
                return False
            existing = {
                r["column_name"]
                for r in conn.execute(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_schema = current_schema() AND table_name = 'quotations'"
                )
            }
            # "id" is GENERATED ALWAYS (0001): OVERRIDING SYSTEM VALUE keeps the old one.
            columns = [c for c in entry["row_json"] if c in existing]
            names = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
            conn.execute(
                sql.SQL(
                    "INSERT INTO quotations ({names}) OVERRIDING SYSTEM VALUE"
                    " SELECT {names} FROM jsonb_populate_record(NULL::quotations, %s)"
                ).format(names=names),
                (Jsonb(entry["row_json"]),),
            )
            conn.execute(
                "UPDATE quotation_trash SET restored_at = now(), restored_by_user_id = %s,"
                " restored_by = %s WHERE id = %s",
                (user_id, user_name, entry["id"]),
            )
    return True


def quotation_references(quote_ref: str) -> list[str]:
    """The COA and sample reports still pointing at a quotation (the FKs of 0007/0008)."""
    with pool().connection() as conn:
        rows = conn.execute(
            """
            SELECT COALESCE(certificate_no, 'COA DRAFT #' || id) AS doc
              FROM coa_certificates WHERE quote_ref = %s
            UNION ALL
            SELECT report_no FROM sample_inspections WHERE quote_ref = %s
            """,
            (quote_ref, quote_ref),
        ).fetchall()
    return [row["doc"] for row in rows]


def related_quotations(
    *, product_reference: str, item_description: str, size_text: str
) -> list[dict[str, Any]]:
    """Which other companies were quoted the same part, or the same item at the same size."""
    if not product_reference and not (item_description and size_text):
        return []
    with pool().connection() as conn:
        return conn.execute(
            """
            SELECT quote_ref, quote_date, customer, customer_code, item_description,
                   product_reference, size_text, unit_price, grams_per_item,
                   pack_quantity, pack_weight_kg,
                   inputs_json->>'sale_basis' AS sale_basis,
                   COALESCE(inputs_json->>'price_basis',
                            results_json->>'price_basis_summary') AS price_basis,
                   results_json->>'calculated_price_per_kg' AS calc_price_kg,
                   results_json->>'calculated_price_per_piece_from_kg' AS calc_price_piece,
                   results_json->>'production_items_per_kg' AS production_items_per_kg,
                   results_json->>'selling_price_per_kg' AS selling_price_per_kg,
                   inputs_json->>'selling_price_per_kg_override' AS price_kg_basis
            FROM quotations
            WHERE (%s <> '' AND product_reference = %s)
               OR (%s <> '' AND %s <> '' AND item_description = %s AND size_text = %s)
            ORDER BY quote_date DESC, id DESC
            LIMIT 100
            """,
            (
                product_reference,
                product_reference,
                item_description,
                size_text,
                item_description,
                size_text,
            ),
        ).fetchall()


def get_setting(key: str, default: str = "") -> str:
    with pool().connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = %s", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with pool().connection() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (%s, %s)"
            " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (key, value),
        )


def save_coa(record: dict[str, Any]) -> dict[str, Any]:
    """Create or revise a COA. A certificate number is assigned only at FINAL."""
    with pool().connection() as conn:
        with conn.transaction():
            coa_id = record.pop("id", None)
            if coa_id:
                old = conn.execute("SELECT * FROM coa_certificates WHERE id = %s FOR UPDATE", (coa_id,)).fetchone()
                if not old:
                    raise KeyError("COA not found")
                certificate_no = old["certificate_no"]
                revision = int(old["revision"]) + 1
            else:
                certificate_no = None
                revision = 1
            if record["status"] == "FINAL" and not certificate_no:
                issue = record.get("issue_date") or date.today()
                month = issue.replace(day=1)
                counter = conn.execute(
                    """INSERT INTO coa_counters (counter_month, last_number) VALUES (%s, 1)
                       ON CONFLICT (counter_month) DO UPDATE
                       SET last_number = coa_counters.last_number + 1 RETURNING last_number""",
                    (month,),
                ).fetchone()["last_number"]
                certificate_no = f"COA-{issue:%Y%m}-{counter:04d}"
            columns = [
                "status", "quote_ref", "customer", "customer_code", "po_no", "part_no", "product",
                "lot_no", "production_date", "inspection_date", "issue_date", "quantity", "material",
                "color", "printing", "width_mm", "length_mm", "thickness_mm", "thickness_mode",
                "width_tolerance_mm", "length_tolerance_mm", "thickness_tolerance_mm", "actual_width_mm",
                "actual_length_mm", "actual_thickness_mm", "result", "remarks", "checked_by", "approved_by",
                "created_by",
            ]
            values = [record.get(c) for c in columns]
            if coa_id:
                assignments = ", ".join(f"{c} = %s" for c in columns)
                row = conn.execute(
                    f"UPDATE coa_certificates SET {assignments}, certificate_no = %s, revision = %s, updated_at = now() WHERE id = %s RETURNING *",
                    values + [certificate_no, revision, coa_id],
                ).fetchone()
            else:
                names = ", ".join(columns)
                marks = ", ".join(["%s"] * len(columns))
                row = conn.execute(
                    f"INSERT INTO coa_certificates ({names}, certificate_no, revision) VALUES ({marks}, %s, %s) RETURNING *",
                    values + [certificate_no, revision],
                ).fetchone()
    return dict(row)


def list_coas(limit: int = 200) -> list[dict[str, Any]]:
    with pool().connection() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM coa_certificates ORDER BY updated_at DESC LIMIT %s", (limit,)
        ).fetchall()]


def get_coa(coa_id: int) -> dict[str, Any] | None:
    with pool().connection() as conn:
        row = conn.execute("SELECT * FROM coa_certificates WHERE id = %s", (coa_id,)).fetchone()
    return dict(row) if row else None


def delete_coa(coa_id: int, *, actor_id=None, actor_name="") -> bool:
    """Only an unissued draft may be removed; its previous contents remain audited."""
    with pool().connection() as conn:
        with conn.transaction():
            old = conn.execute("SELECT * FROM coa_certificates WHERE id=%s FOR UPDATE", (coa_id,)).fetchone()
            if not old:
                return False
            if old["status"] == "FINAL" or old["certificate_no"]:
                raise DocumentConflict("ใบรับรองที่ออกแล้วลบไม่ได้ / An issued COA cannot be deleted")
            conn.execute("DELETE FROM coa_certificates WHERE id=%s", (coa_id,))
            audit_document(conn, "coa", coa_id, "delete", old, None, actor_id, actor_name)
    return True


def sample_number_day(now: datetime | None = None) -> date:
    return (now or datetime.now(ZoneInfo("Asia/Bangkok"))).astimezone(ZoneInfo("Asia/Bangkok")).date()


def save_sample_inspection(record: dict[str, Any], *, expected_revision=None,
                           expected_quote_version=None, request_id="", fingerprint="",
                           actor_id=None, actor_name="") -> dict[str, Any]:
    record = dict(record)
    with pool().connection() as conn:
        with conn.transaction():
            replay = _saved_request(conn, "sample", actor_id, request_id, fingerprint)
            if replay is not None:
                return replay
            report_id = record.pop("id", None)
            old = None
            if report_id:
                old = conn.execute("SELECT * FROM sample_inspections WHERE id=%s AND deleted_at IS NULL FOR UPDATE", (report_id,)).fetchone()
                if not old:
                    raise KeyError("Sample inspection not found")
                if expected_revision is None or old["revision"] != expected_revision:
                    raise DocumentConflict("รายงานถูกแก้ไขแล้ว กรุณาเปิดใหม่ / Report changed; reopen it before saving")
                if old["quote_ref"] != record["quote_ref"]:
                    raise DocumentConflict("รายงานเดิมเปลี่ยนใบอ้างอิงไม่ได้ / Create a new report to change its source")
                report_no, revision = old["report_no"], int(old["revision"]) + 1
                record["source_snapshot"] = old["source_snapshot"]
            else:
                # Keep the standards selected in the picker coherent with this
                # issuance. Quotation edits need FOR UPDATE, so they cannot
                # cross this check and the report INSERT in this transaction.
                quote = conn.execute("SELECT version FROM quotations WHERE quote_ref=%s FOR SHARE",
                                     (record["quote_ref"],)).fetchone()
                if not quote:
                    raise KeyError("Quotation not found")
                selected_version = expected_quote_version if expected_quote_version is not None else 1
                snapshot_version = record["source_snapshot"].get("quote_version")
                if selected_version != quote["version"] or snapshot_version != quote["version"]:
                    raise DocumentConflict("ใบเสนอราคาถูกแก้ไขแล้ว กรุณาเลือกต้นฉบับใหม่ / Source quotation changed; select it again before saving")
                day = sample_number_day()
                seq = conn.execute("""INSERT INTO sample_daily_counters(counter_date,last_number) VALUES(%s,1)
                    ON CONFLICT(counter_date) DO UPDATE SET last_number=sample_daily_counters.last_number+1
                    RETURNING last_number""", (day,)).fetchone()["last_number"]
                report_no, revision = f"SI-{day:%Y%m%d}-{seq:04d}", 1
            columns = ["quote_ref","customer","customer_code","part_no","product","inspection_date","product_key",
                "width_mm","length_mm","thickness_mm","thickness_mode","gusset_mm","tolerance_width_mm",
                "tolerance_length_mm","tolerance_thickness_mm","tolerance_gusset_left_mm","tolerance_gusset_right_mm",
                "results_json","display_json","source_snapshot","length_datum","overall_result","remarks","checked_by","approved_by"]
            json_fields = {"results_json", "display_json", "source_snapshot"}
            values = [Jsonb(record[c]) if c in json_fields else record.get(c) for c in columns]
            if report_id:
                assigns = ",".join(f"{c}=%s" for c in columns)
                row = conn.execute(f"UPDATE sample_inspections SET {assigns},revision=%s,updated_at=now() WHERE id=%s RETURNING *",
                    values + [revision, report_id]).fetchone()
            else:
                names, marks = ",".join(columns), ",".join(["%s"]*len(columns))
                row = conn.execute(f"INSERT INTO sample_inspections({names},report_no,revision) VALUES({marks},%s,%s) RETURNING *",
                    values + [report_no, revision]).fetchone()
            audit_document(conn, "sample", row["id"], "update" if old else "create", old, row, actor_id, actor_name)
            response = _jsonable(dict(row))
            _remember_request(conn, "sample", actor_id, request_id, fingerprint, response)
    return response


def list_sample_inspections(limit: int = 200) -> list[dict[str, Any]]:
    with pool().connection() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM sample_inspections WHERE deleted_at IS NULL ORDER BY updated_at DESC LIMIT %s", (limit,)).fetchall()]


def get_sample_inspection(report_id: int) -> dict[str, Any] | None:
    with pool().connection() as conn:
        row = conn.execute("SELECT * FROM sample_inspections WHERE id=%s AND deleted_at IS NULL", (report_id,)).fetchone()
    return dict(row) if row else None


def delete_sample_inspection(report_id: int, *, actor_id=None, actor_name="") -> bool:
    with pool().connection() as conn:
        with conn.transaction():
            old = conn.execute("SELECT * FROM sample_inspections WHERE id=%s AND deleted_at IS NULL FOR UPDATE", (report_id,)).fetchone()
            if not old:
                return False
            row = conn.execute("UPDATE sample_inspections SET deleted_at=now(),deleted_by=%s,updated_at=now() WHERE id=%s RETURNING *",
                               (actor_name, report_id)).fetchone()
            audit_document(conn, "sample", report_id, "delete", old, row, actor_id, actor_name)
    return True
