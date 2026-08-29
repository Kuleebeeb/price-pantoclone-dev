# -*- coding: utf-8 -*-
"""Match freshly extracted rows to the rows already on prod, by workbook+sheet+item."""
import csv, json, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from pathlib import Path
from collections import defaultdict, Counter

root = Path(r"D:\ThaiPlasticPricing\etl-output")

# --- prod rows -------------------------------------------------------------
paper = {}
paper_sheets = defaultdict(list)
bad_src = 0
with (root / "paper_rows.csv").open(encoding="utf-8", newline="") as fh:
    for r in csv.DictReader(fh):
        m = re.match(r"^(.*?)\s+•\s+(.*)$", r["import_source"])
        if not m:
            bad_src += 1
            continue
        file_stem, sheet = m.group(1).strip().lower(), m.group(2).strip()
        mi = re.search(r"-(\d+)(?:\s+·|$)", r["quote_ref"])
        idx = int(mi.group(1)) if mi else 1
        key = (file_stem, sheet, idx)
        paper[key] = r
        paper_sheets[(file_stem, sheet)].append(r)

# --- new extraction --------------------------------------------------------
mine = {}
mine_sheets = defaultdict(list)
for f in root.glob("*/rows.jsonl"):
    for line in f.open(encoding="utf-8"):
        r = json.loads(line)
        src = r["import_source"]                 # Z:/H/.../Honda Lock.xlsx#64-01
        path, sheet = src.rsplit("#", 1)
        file_stem = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
        key = (file_stem, sheet, r["item_index"])
        mine[key] = r
        mine_sheets[(file_stem, sheet)].append(r)

both = set(paper) & set(mine)
only_paper = set(paper) - set(mine)
only_mine = set(mine) - set(paper)

def price_close(a, b):
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return None
    return abs(a - b) < 0.005

agree = disagree = unknown = 0
for k in both:
    pc = price_close(paper[k]["unit_price"], mine[k]["unit_price"])
    if pc is None: unknown += 1
    elif pc: agree += 1
    else: disagree += 1

sheet_both = set(paper_sheets) & set(mine_sheets)
count_mismatch = [(k, len(paper_sheets[k]), len(mine_sheets[k])) for k in sheet_both
                  if len(paper_sheets[k]) != len(mine_sheets[k])]

print(f"prod rows           : {len(paper)}  (unparseable import_source: {bad_src})")
print(f"extracted rows      : {len(mine)}")
print(f"matched (file+sheet+item): {len(both)}")
print(f"  price agrees      : {agree}   disagrees: {disagree}   no price on one side: {unknown}")
print(f"prod-only rows      : {len(only_paper)}")
print(f"extracted-only rows : {len(only_mine)}")
print(f"sheets on both sides: {len(sheet_both)}, of which item-count differs: {len(count_mismatch)}")
print()
enrich_ready = Counter(mine[k]["extraction_status"] for k in both)
print("status of matched rows:", dict(enrich_ready))
print()
# why prod-only: which files
po_files = Counter(k[0] for k in only_paper)
print("prod-only rows by workbook (top 12):")
for f, n in po_files.most_common(12): print(f"  {n:5}  {f}")
print()
mo_files = Counter(k[0] for k in only_mine)
print("extracted-only rows by workbook (top 12):")
for f, n in mo_files.most_common(12): print(f"  {n:5}  {f}")
print()
print("item-count mismatches (first 10):")
for k, a, b in count_mismatch[:10]: print(f"  {k[0]} # {k[1]}: prod {a} vs mine {b}")
print()
print("price disagreements (first 8):")
shown = 0
for k in both:
    if price_close(paper[k]["unit_price"], mine[k]["unit_price"]) is False:
        print(f"  {k}: prod {paper[k]['unit_price']} vs mine {mine[k]['unit_price']} | {mine[k]['item_description'][:60]}")
        shown += 1
        if shown >= 8: break
