import sqlite3
import time
import os
from typing import Optional, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'learning_store.sqlite')


class LearningStore:
    @classmethod
    def _conn(cls):
        path = os.path.abspath(DB_PATH)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = sqlite3.connect(path, timeout=5)
        return conn

    @classmethod
    def init_db(cls):
        conn = cls._conn()
        cur = conn.cursor()
        cur.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT,
            file_size INTEGER,
            page_count INTEGER,
            method TEXT,
            dpi INTEGER,
            usar_ocr INTEGER,
            txt_path TEXT,
            text_len INTEGER,
            trans_count INTEGER,
            banco TEXT,
            parser TEXT,
            success INTEGER,
            created_at INTEGER
        )
        ''')
        conn.commit()
        conn.close()

    @classmethod
    def record(cls, rec: Dict[str, Any]) -> None:
        conn = cls._conn()
        cur = conn.cursor()
        cur.execute('''
        INSERT INTO records (file_hash, file_size, page_count, method, dpi, usar_ocr, txt_path, text_len, trans_count, banco, parser, success, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            rec.get('file_hash'),
            rec.get('file_size'),
            rec.get('page_count'),
            rec.get('method'),
            rec.get('dpi'),
            1 if rec.get('usar_ocr') else 0,
            rec.get('txt_path'),
            rec.get('text_len'),
            rec.get('trans_count'),
            rec.get('banco'),
            rec.get('parser'),
            1 if rec.get('success') else 0,
            int(time.time())
        ))
        conn.commit()
        conn.close()

    @classmethod
    def find_by_file_hash(cls, file_hash: str) -> Optional[Dict[str, Any]]:
        if not file_hash:
            return None
        conn = cls._conn()
        cur = conn.cursor()
        cur.execute('SELECT file_hash, file_size, page_count, method, dpi, usar_ocr, txt_path, text_len, trans_count, banco, parser, success, created_at FROM records WHERE file_hash = ? ORDER BY created_at DESC LIMIT 1', (file_hash,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            'file_hash': row[0], 'file_size': row[1], 'page_count': row[2], 'method': row[3], 'dpi': row[4],
            'usar_ocr': bool(row[5]), 'txt_path': row[6], 'text_len': row[7], 'trans_count': row[8], 'banco': row[9], 'parser': row[10], 'success': bool(row[11]), 'created_at': row[12]
        }

    @classmethod
    def delete_by_file_hash(cls, file_hash: str) -> None:
        if not file_hash:
            return
        conn = cls._conn()
        cur = conn.cursor()
        try:
            cur.execute('DELETE FROM records WHERE file_hash = ?', (file_hash,))
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def recommend_for(cls, file_size: int, page_count: Optional[int]) -> Optional[Dict[str, Any]]:
        """Return the most frequent successful strategy for similar file_size/page_count.
        Similarity heuristic: same page_count and file_size within 2%.
        """
        conn = cls._conn()
        cur = conn.cursor()
        if page_count is not None:
            low = int(file_size * 0.98)
            high = int(file_size * 1.02)
            cur.execute('''
            SELECT method, dpi, usar_ocr, txt_path, COUNT(*) as cnt
            FROM records
            WHERE page_count = ? AND file_size BETWEEN ? AND ? AND success = 1
            GROUP BY method, dpi, usar_ocr, txt_path
            ORDER BY cnt DESC
            LIMIT 1
            ''', (page_count, low, high))
            row = cur.fetchone()
        else:
            low = int(file_size * 0.98)
            high = int(file_size * 1.02)
            cur.execute('''
            SELECT method, dpi, usar_ocr, txt_path, COUNT(*) as cnt
            FROM records
            WHERE file_size BETWEEN ? AND ? AND success = 1
            GROUP BY method, dpi, usar_ocr, txt_path
            ORDER BY cnt DESC
            LIMIT 1
            ''', (low, high))
            row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {'method': row[0], 'dpi': row[1], 'usar_ocr': bool(row[2]), 'txt_path': row[3], 'count': row[4]}


LearningStore.init_db()
