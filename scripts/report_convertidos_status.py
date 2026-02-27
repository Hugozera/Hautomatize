#!/usr/bin/env python3
import os
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / 'media' / 'conversor' / 'originais'
OUT_DIR = ROOT / 'media' / 'conversor' / 'convertidos'
REPORT = OUT_DIR / 'status_report.csv'

rows = []
for fn in sorted(os.listdir(INPUT_DIR)):
    if not fn.lower().endswith('.pdf'):
        continue
    base = os.path.splitext(fn)[0]
    padrao = OUT_DIR / f"{base}_padrao.txt"
    txt = OUT_DIR / f"{base}.txt"
    ofx = OUT_DIR / f"{base}.ofx"
    progress = OUT_DIR / f"{base}.progress.json"

    rows.append({
        'file': fn,
        'padrao_exists': padrao.exists(),
        'padrao_bytes': padrao.stat().st_size if padrao.exists() else '',
        'txt_exists': txt.exists(),
        'txt_bytes': txt.stat().st_size if txt.exists() else '',
        'ofx_exists': ofx.exists(),
        'ofx_bytes': ofx.stat().st_size if ofx.exists() else '',
        'progress_exists': progress.exists()
    })

OUT_DIR.mkdir(parents=True, exist_ok=True)
with open(REPORT, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['file','padrao_exists','padrao_bytes','txt_exists','txt_bytes','ofx_exists','ofx_bytes','progress_exists'])
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

print('Report written to', REPORT)
