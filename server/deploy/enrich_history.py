"""Enrich the quotation history with the specs read out of the Excel books.

RUN INSIDE THE API CONTAINER, like load_history.py:

    docker compose cp deploy/enrich_history.py api:/tmp/enrich_history.py
    docker compose cp enrich.jsonl              api:/tmp/enrich.jsonl
    docker compose exec -T api python /tmp/enrich_history.py /tmp/enrich.jsonl [--prices]

WHAT IT TOUCHES AND WHAT IT NEVER TOUCHES. Only rows that came out of the books
(import_source <> ''). A row saved from the web or synced from the .exe is a
snapshot somebody made on purpose (law P5) and is never rewritten here, even if
the same reference turns up in the file.

Two kinds of line in the JSONL, told apart by "action":
    update  the row already exists (matched by quote_ref AND import_source);
            fills product_key, size_text, inputs_json, results_json,
            grams_per_item and product_reference (only when it was blank)
    insert  a quoted item the earlier load never saw; goes through
            store.import_quotations, so a second run adds nothing (ON CONFLICT)

PRICES ARE NOT REWRITTEN unless --prices is given. On price-revision sheets
the earlier load took the CURRENT PRICE column; the extractor takes NEW PRICE
(the figure actually being quoted on that date) and keeps CURRENT as
previous_price. Which one the history should show is a decision for the
CEO, so it stays behind a flag and is counted either way.

SAFE TO RUN AGAIN: every update writes the same values, every insert is
idempotent by quote_ref.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/srv/app/api")

import store  # noqa: E402
from store import pool  # noqa: E402

BATCH = 500


def apply_updates(lines: list[dict], rewrite_prices: bool) -> dict[str, int]:
    done = missed = price_diff = 0
    with pool().connection() as conn:
        with conn.transaction():
            for row in lines:
                sets = [
                    "product_key = %s", "size_text = %s", "inputs_json = %s",
                    "results_json = %s", "grams_per_item = %s",
                    # never blank a code somebody typed; fill only an empty one
                    "product_reference = CASE WHEN product_reference = '' THEN %s ELSE product_reference END",
                ]
                params = [
                    row["product_key"], row.get("size_text", ""),
                    json.dumps(row.get("inputs", {}), ensure_ascii=False),
                    json.dumps(row.get("results", {}), ensure_ascii=False),
                    row.get("grams_per_item") or 0,
                    row.get("product_reference", ""),
                ]
                if row.get("price_differs"):
                    price_diff += 1
                    if rewrite_prices and row.get("unit_price") is not None:
                        sets.append("unit_price = %s")
                        params.append(row["unit_price"])
                params += [row["quote_ref"], row["import_source"]]
                cur = conn.execute(
                    "UPDATE quotations SET " + ", ".join(sets)
                    + " WHERE quote_ref = %s AND import_source = %s AND import_source <> ''",
                    params,
                )
                if cur.rowcount == 1:
                    done += 1
                else:
                    missed += 1
    return {"updated": done, "missed": missed, "price_differs": price_diff}


def main(path: Path, rewrite_prices: bool) -> None:
    updates: list[dict] = []
    inserts: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            (updates if row.get("action") == "update" else inserts).append(row)

    before = store.quotation_count()
    up = apply_updates(updates, rewrite_prices)
    added = seen = 0
    for i in range(0, len(inserts), BATCH):
        result = store.import_quotations(inserts[i:i + BATCH])
        seen += result["seen"]
        added += result["added"]
    after = store.quotation_count()

    print(f"updates applied     : {up['updated']}  (no matching book row: {up['missed']})")
    print(f"price differs       : {up['price_differs']}  ({'REWRITTEN' if rewrite_prices else 'left as is'})")
    print(f"inserts seen/added  : {seen}/{added}")
    print(f"quotations before   : {before}")
    print(f"quotations after    : {after}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: enrich_history.py <enrich.jsonl> [--prices]")
    main(Path(sys.argv[1]), "--prices" in sys.argv[2:])
