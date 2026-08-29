"""Load the factory's old quotation books into the server, from a JSONL file.

RUN INSIDE THE API CONTAINER. It borrows that container's DATABASE_URL and its
psycopg, so there is nothing to install and no second place holding a password:

    docker compose cp deploy/load_history.py api:/tmp/load_history.py
    docker compose cp quotes-final.jsonl     api:/tmp/quotes.jsonl
    docker compose exec -T api python /tmp/load_history.py /tmp/quotes.jsonl

WHY A SCRIPT AND NOT AN ENDPOINT. This is a one-off of 17,412 rows read off a
network drive nobody else can reach. An HTTP route for it would need an upload
path, a batching protocol and an admin role, all built for a job that runs twice
- and would sit there afterwards as a way to write straight into the price book.

IT IS SAFE TO RUN AGAIN. Every row is keyed by its own reference and inserted
with ON CONFLICT DO NOTHING, so a second pass over the same file changes
nothing, and a pass over a longer file adds only what is new. The first run
always turns out to have missed a workbook.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/srv/app/api")

import store  # noqa: E402

BATCH = 500


def main(path: Path) -> None:
    before = store.quotation_count()
    seen = added = 0
    batch: list[dict] = []

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            batch.append(json.loads(line))
            if len(batch) >= BATCH:
                result = store.import_quotations(batch)
                seen += result["seen"]
                added += result["added"]
                batch = []
                print(f"  {seen:>6} read, {added:>6} added", flush=True)

    if batch:
        result = store.import_quotations(batch)
        seen += result["seen"]
        added += result["added"]

    after = store.quotation_count()
    print()
    print(f"rows in file        : {seen}")
    print(f"rows added          : {added}")
    print(f"already there       : {seen - added}")
    print(f"quotations before   : {before}")
    print(f"quotations after    : {after}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: load_history.py <file.jsonl>")
    main(Path(sys.argv[1]))
