import sqlite3
import json
import os
from collections import defaultdict
from .learning_store import DB_PATH

OUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'learning_heuristics.json')


def aggregate(limit=1000):
    db = os.path.abspath(DB_PATH)
    if not os.path.exists(db):
        print('No learning DB found at', db)
        return {}

    conn = sqlite3.connect(db)
    cur = conn.cursor()

    # Gather successful records
    cur.execute('''
    SELECT page_count, file_size, method, dpi, usar_ocr, txt_path, COUNT(*) as cnt, SUM(success) as successes
    FROM records
    GROUP BY page_count, file_size, method, dpi, usar_ocr, txt_path
    ORDER BY cnt DESC
    LIMIT ?
    ''', (limit,))

    rows = cur.fetchall()
    conn.close()

    # Bucket by (page_count) and by file_size percentage bands
    buckets = defaultdict(list)
    for r in rows:
        page_count, file_size, method, dpi, usar_ocr, txt_path, cnt, successes = r
        try:
            size = int(file_size) if file_size else 0
        except Exception:
            size = 0
        size_bucket = None
        if size > 0:
            # bucket by order of magnitude and 10% bands
            magnitude = 10 ** (len(str(size)) - 1)
            band = (size // max(magnitude // 10, 1)) * (magnitude // 10)
            size_bucket = f"{band}"
        key = f"p{page_count}_s{size_bucket}"
        buckets[key].append({
            'page_count': page_count,
            'file_size': size,
            'method': method,
            'dpi': dpi,
            'usar_ocr': bool(usar_ocr),
            'txt_path': txt_path,
            'count': cnt,
            'successes': successes
        })

    # For each bucket pick best strategy by success rate then by count
    heuristics = {}
    for k, items in buckets.items():
        best = None
        best_score = -1
        for it in items:
            # score = success rate * log(count+1)
            succ = it.get('successes') or 0
            cnt = it.get('count') or 1
            score = (succ / cnt) * (1 + (cnt ** 0.5))
            if score > best_score:
                best_score = score
                best = it
        heuristics[k] = best

    # Write JSON
    outp = os.path.abspath(OUT_PATH)
    try:
        with open(outp, 'w', encoding='utf-8') as f:
            json.dump(heuristics, f, indent=2, ensure_ascii=False)
        print('Wrote heuristics to', outp)
    except Exception as e:
        print('Failed to write heuristics:', e)

    return heuristics


if __name__ == '__main__':
    h = aggregate()
    print('Buckets:', len(h))
