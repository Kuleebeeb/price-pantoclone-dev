"""Rehearse forward migrations and verify existing fields on a restored disposable DB."""
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

import psycopg
from psycopg import sql

url = os.environ.get("DATABASE_URL", "")
if os.environ.get("PANTONGONE_DISPOSABLE_TEST") != "1" or "smoke" not in urlparse(url).path:
    raise SystemExit("Explicit disposable test opt-in and a smoke database are required")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))
import db


def digest(conn, table, columns):
    projection = sql.SQL(",").join(map(sql.Identifier, columns))
    query = sql.SQL("SELECT to_jsonb(r)::text FROM (SELECT {} FROM {}) r ORDER BY to_jsonb(r)::text").format(
        projection, sql.Identifier(table))
    rows = conn.execute(query).fetchall()
    return {"rows": len(rows), "sha256": hashlib.sha256("\n".join(row[0] for row in rows).encode()).hexdigest()}


with psycopg.connect(url, autocommit=True) as conn:
    tables = [r[0] for r in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'schema_migrations' ORDER BY tablename")]
    columns = {table: [r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,))]
        for table in tables}
    before = {table: digest(conn, table, columns[table]) for table in tables}
    applied = db.run_migrations()
    after = {table: digest(conn, table, columns[table]) for table in tables}
    if before != after:
        changed = [table for table in tables if before[table] != after[table]]
        raise SystemExit("Existing data changed in: " + ", ".join(changed))
    if db.run_migrations():
        raise SystemExit("Migration replay unexpectedly changed schema history")
    print(json.dumps({"applied": applied, "preserved_tables": len(tables),
                      "preserved_rows": sum(item["rows"] for item in before.values()),
                      "existing_column_hashes_unchanged": True, "second_run_noop": True}))
db.close_pool()
