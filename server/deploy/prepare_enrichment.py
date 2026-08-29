# -*- coding: utf-8 -*-
"""Join the extractor's rows with the rows already on the server -> enrich.jsonl.

RUNS LOCALLY (needs the Z: extraction output and a CSV export of the server's
book rows). Emits one line per extracted item:

    action=update   the server already has this item (same workbook, sheet and
                    item number) - carries the server's own quote_ref and
                    import_source so the loader can address the row exactly
    action=insert   the earlier load never saw it - numbered the way the
                    earlier load numbered everything, so the book stays one
                    scheme: "<REF cell>-<item> · <workbook>[ @<sheet>]"

WHY MATCH BY WORKBOOK+SHEET+ITEM AND NOT BY REF. The earlier load derived refs
from the same cells this extractor reads, so a ref match would prove nothing
a source match does not - while a source match survives every ref-spelling
quirk. The price is then compared as an independent witness: 11,000+ agree to
the satang, which is what makes the alignment trustworthy.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import calculator  # noqa: E402

SHEET_NUMBERED = re.compile(r"^\d{2}-\d{2,3}")


def book_and_sheet(import_source: str) -> tuple[str, str]:
    path, sheet = import_source.rsplit("#", 1)
    return path.replace("\\", "/").rsplit("/", 1)[-1], sheet


def size_text_for(row: dict) -> str:
    inp = row.get("inputs") or {}
    key = inp.get("product_key") or row.get("product_key")
    if not key or key not in calculator.PRODUCTS:
        return ""
    dims = {}
    for name in ("width", "length", "gusset", "sold_length", "height"):
        m = inp.get(name) or {}
        # no unit written on the sheet -> no size text; "ซม." as a default would
        # print a confident wrong size, the one thing worse than a blank
        dims[name] = {"value": float(m.get("value") or 0), "unit": m.get("unit")}
    if key == "roll" and not dims["sold_length"]["value"] and dims["length"]["value"]:
        dims["sold_length"] = dims["length"]
    needed = {"flat": ("width", "length"), "opaque": ("width", "length"),
              "gusset": ("width", "length", "gusset"), "roll": ("width", "sold_length"),
              "cover": ("width", "length", "height")}[key]
    if any(not dims[n]["value"] or not dims[n]["unit"] for n in needed):
        return ""
    return calculator.size_description(key, dims)


def aligned(mine: dict, theirs: dict) -> bool:
    """Same item on both sides? The paid price says so - directly, or via the
    CURRENT-PRICE column the earlier load happened to take."""
    try:
        p_theirs = float(theirs.get("unit_price"))
    except (TypeError, ValueError):
        return True  # nothing to compare against - keep the positional match
    for candidate in (mine.get("unit_price"), mine.get("previous_price")):
        try:
            if candidate is not None and abs(float(candidate) - p_theirs) < 0.005:
                return True
        except (TypeError, ValueError):
            pass
    return mine.get("unit_price") is None


def derive_ref(row: dict, sheet: str) -> str:
    base = (row.get("ref_text") or row.get("candidate_ref") or "").strip()
    m = re.match(r"^(\d{2})-(\d{2,3})", sheet)
    if not re.match(r"^\d{4}[/-]", base) and m:
        base = f"25{m.group(1)}/{m.group(2)}"
    return base


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows-dir", required=True)
    ap.add_argument("--paper", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    prod: dict[tuple, dict] = {}
    with open(args.paper, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            m = re.match(r"^(.*?)\s+•\s+(.*)$", r["import_source"])
            if not m:
                continue
            mi = re.search(r"-(\d+)(?:\s+·|$)", r["quote_ref"])
            key = (m.group(1).strip().lower(), m.group(2).strip(), int(mi.group(1)) if mi else 1)
            prod[key] = r

    stats = Counter()
    seen_refs: set[str] = set(r["quote_ref"] for r in prod.values())
    out = open(args.out, "w", encoding="utf-8")
    review = open(str(Path(args.out).with_name("misaligned.jsonl")), "w", encoding="utf-8")
    for f in sorted(Path(args.rows_dir).glob("*/rows.jsonl")):
        for line in f.open(encoding="utf-8"):
            r = json.loads(line)
            book, sheet = book_and_sheet(r["import_source"])
            key = (book.lower(), sheet, r["item_index"])
            inputs = dict(r.get("inputs") or {})
            inputs.update({
                "product_name": r.get("product_name", ""),
                "resin": r.get("resin", ""),
                "extraction_status": r["extraction_status"],
                "extraction_reasons": r.get("reasons", []),
            })
            if r.get("previous_price") is not None:
                inputs["previous_price"] = r["previous_price"]
            grams = r.get("grams_per_item") or 0
            results = {"grams_per_item": grams, "items_per_kg": round(1000.0 / grams, 4)} if grams else {}
            common = {
                "product_key": r.get("product_key"),
                "size_text": size_text_for(r),
                "inputs": inputs,
                "results": results,
                "grams_per_item": grams,
                "product_reference": r.get("product_reference", ""),
                # NOT NULL on the table; the earlier load wrote 0 for a missing price too
                "unit_price": r["unit_price"] if r.get("unit_price") is not None else 0.0,
            }
            hit = prod.get(key)
            if hit:
                mine, theirs = r.get("unit_price"), hit.get("unit_price")  # raw, None = no price
                differs = False
                try:
                    differs = mine is not None and abs(float(mine) - float(theirs)) >= 0.005
                except (TypeError, ValueError):
                    pass
                if not aligned(r, hit):
                    # the price is the one independent witness that "item 7"
                    # here is "item 7" there. When it disagrees and the old
                    # CURRENT-PRICE column does not explain it, the two loads
                    # counted rows differently on this sheet - writing specs
                    # into that row would put one bag's size on another's line
                    stats["skipped_misaligned"] += 1
                    review.write(json.dumps({"quote_ref": hit["quote_ref"], "import_source": hit["import_source"],
                                             "prod_price": theirs, "mine": mine,
                                             "previous_price": r.get("previous_price"),
                                             "description": r["item_description"][:120]},
                                            ensure_ascii=False) + "\n")
                    continue
                rec = dict(common, action="update", quote_ref=hit["quote_ref"],
                           import_source=hit["import_source"], price_differs=differs,
                           product_key=r.get("product_key") or hit.get("product_key") or "flat")
                stats["update"] += 1
                stats["price_differs"] += int(differs)
            else:
                if not r.get("quote_date"):
                    stats["insert_skipped_no_date"] += 1
                    continue
                if not (r.get("item_description") or "").strip():
                    # a price with no words beside it is not a record anyone
                    # could ever find again
                    stats["insert_skipped_no_description"] += 1
                    continue
                base = derive_ref(r, sheet)
                if not base:
                    stats["insert_skipped_no_ref"] += 1
                    continue
                stem = book[:-5] if book.lower().endswith(".xlsx") else book
                tag = stem if SHEET_NUMBERED.match(sheet) else f"{stem} @{sheet}"
                ref = f"{base}-{r['item_index']:02d} · {tag}"
                if ref in seen_refs and not tag.endswith(f"@{sheet}"):
                    # same printed REF on two sheets (an original and its
                    # REV.1): the earlier load told them apart with "@sheet"
                    ref = f"{base}-{r['item_index']:02d} · {stem} @{sheet}"
                if ref in seen_refs:
                    stats["insert_skipped_ref_taken"] += 1
                    continue
                seen_refs.add(ref)
                key_ = r.get("product_key") or "flat"
                if not r.get("product_key"):
                    inputs["product_key_assumed"] = True
                rec = dict(common, action="insert", quote_ref=ref, quote_date=r["quote_date"],
                           customer=r.get("customer") or r.get("customer_folder", ""),
                           customer_code="", item_description=r["item_description"],
                           product_key=key_, product_label=calculator.PRODUCTS[key_],
                           import_source=f"{book} • {sheet}")
                stats["insert"] += 1
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out.close()
    review.close()
    for k, v in sorted(stats.items()):
        print(f"{k:28} {v}")


if __name__ == "__main__":
    main()
