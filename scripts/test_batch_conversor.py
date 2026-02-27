#!/usr/bin/env python3
import os
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.conversor_service import converter_arquivo
INPUT_DIR = ROOT / 'media' / 'conversor' / 'originais'
OUTPUT_DIR = ROOT / 'media' / 'conversor' / 'convertidos_ofx_test'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

results = []

for fn in sorted(os.listdir(INPUT_DIR)):
    if not fn.lower().endswith('.pdf'):
        continue
    path = str(INPUT_DIR / fn)
    print('Processing', fn)
    try:
        out, err = converter_arquivo(path, 'ofx', output_dir=str(OUTPUT_DIR), usar_ocr=True, dpi=300)
        results.append({'file': fn, 'out': out or '', 'err': err or ''})
    except Exception as e:
        results.append({'file': fn, 'out': '', 'err': str(e)})

report_path = OUTPUT_DIR / 'report.csv'
with open(report_path, 'w', newline='', encoding='utf-8') as csvf:
    writer = csv.DictWriter(csvf, fieldnames=['file', 'out', 'err'])
    writer.writeheader()
    for r in results:
        writer.writerow(r)

print('Done. Report:', report_path)
