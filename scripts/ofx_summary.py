from pathlib import Path
import csv

OUT = Path('media/conversor/convertidos')
OUT.mkdir(parents=True, exist_ok=True)

def count_transactions(ofx_text: str) -> int:
    # crude but effective: count <STMTTRN> tags
    return ofx_text.upper().count('<STMTTRN>')

def main():
    rows = []
    for ofx in sorted(OUT.glob('*.ofx')):
        try:
            txt = ofx.read_text(encoding='utf-8', errors='replace')
        except Exception:
            txt = ''
        tx_count = count_transactions(txt)
        size = ofx.stat().st_size
        rows.append((ofx.name, str(ofx), tx_count, size))

    csv_path = OUT / 'ofx_summary.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['file','path','tx_count','bytes'])
        for r in rows:
            w.writerow(r)

    print('Wrote', csv_path)

if __name__ == '__main__':
    main()
