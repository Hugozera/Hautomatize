#!/usr/bin/env python3
"""
Lightweight conversion pipeline (PDF -> TXT) using the working script logic.

- Prefer `pdfminer.six` embedded-text extraction.
- Fallback to `pdf2image` + Poppler + Tesseract (invoked via subprocess) for OCR.
- Writes UTF-8 text and inserts clear page breaks (`=== PAGE BREAK ===`).

Public functions:
- `extract_text_pipeline(pdf_path, usar_ocr=True, dpi=300)` -> str
- `convert_pdf_to_txt(pdf_path, out_dir=None, usar_ocr=True, dpi=300)` -> (txt_path, error)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import re
import json
import time
from pathlib import Path
from typing import Optional, Tuple

POPPLER_DIR = Path("poppler-25.12.0/Library/bin")
DEFAULT_TESSERACT = Path("Tesseract-OCR/tesseract.exe")


def find_tesseract() -> Optional[str]:
    if DEFAULT_TESSERACT.exists():
        return str(DEFAULT_TESSERACT)
    which = shutil.which("tesseract")
    return which


def extract_text_pdfminer(path: Path) -> str:
    try:
        from pdfminer.high_level import extract_text

        text = extract_text(str(path))
        return text or ""
    except Exception:
        return ""


def ocr_render_and_tesseract(pdf_path: Path, tesseract_cmd: str, dpi: int = 400, progress_path: Optional[Path] = None) -> str:
    try:
        from pdf2image import convert_from_path
    except Exception as e:
        raise RuntimeError("pdf2image not installed") from e

    poppler_path = None
    if POPPLER_DIR.exists():
        poppler_path = str(POPPLER_DIR)

    out_pages: list[str] = []
    started = time.time()
    pages_converted = 0
    with tempfile.TemporaryDirectory() as tmpd:
        tmpd_p = Path(tmpd)
        images = convert_from_path(str(pdf_path), dpi=dpi, poppler_path=poppler_path)
        total_pages = len(images)
        # initialize progress file
        if progress_path:
            try:
                progress_path.parent.mkdir(parents=True, exist_ok=True)
                progress_path.write_text(json.dumps({
                    'status': 'running',
                    'total_pages': total_pages,
                    'pages_converted': 0,
                    'percent': 0.0,
                    'eta_seconds': None,
                    'started_at': started,
                    'last_update': started
                }), encoding='utf-8')
            except Exception:
                pass

        for i, img in enumerate(images, start=1):
            img_file = tmpd_p / f"page_{i:04d}.png"
            img.save(img_file, format="PNG")

            out_base = tmpd_p / f"page_{i:04d}"
            cmd = [tesseract_cmd, str(img_file), str(out_base), '-l', 'por+eng', '--oem', '1', '--psm', '6']
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if proc.returncode != 0:
                out_pages.append(f"=== TESSERACT-ERROR page {i} rc={proc.returncode} stderr={proc.stderr.decode('utf-8','replace')}\n")
                # update progress even on error
                pages_converted += 1
                if progress_path:
                    try:
                        now = time.time()
                        elapsed = now - started
                        avg = elapsed / pages_converted if pages_converted else None
                        remaining = total_pages - pages_converted
                        eta = int(avg * remaining) if avg and remaining > 0 else None
                        progress_path.write_text(json.dumps({
                            'status': 'running',
                            'total_pages': total_pages,
                            'pages_converted': pages_converted,
                            'percent': round(pages_converted / total_pages * 100, 2),
                            'eta_seconds': eta,
                            'started_at': started,
                            'last_update': now,
                            'current_page': i
                        }), encoding='utf-8')
                    except Exception:
                        pass
                continue

            txt_path = out_base.with_suffix('.txt')
            if txt_path.exists():
                out_pages.append(txt_path.read_text(encoding='utf-8', errors='replace'))
            else:
                out_pages.append("")

            # update progress
            pages_converted += 1
            if progress_path:
                try:
                    now = time.time()
                    elapsed = now - started
                    avg = elapsed / pages_converted if pages_converted else None
                    remaining = total_pages - pages_converted
                    eta = int(avg * remaining) if avg and remaining > 0 else None
                    progress_path.write_text(json.dumps({
                        'status': 'running',
                        'total_pages': total_pages,
                        'pages_converted': pages_converted,
                        'percent': round(pages_converted / total_pages * 100, 2),
                        'eta_seconds': eta,
                        'started_at': started,
                        'last_update': now,
                        'current_page': i
                    }), encoding='utf-8')
                except Exception:
                    pass

    return "\n\n=== PAGE BREAK ===\n\n".join(out_pages)


def postprocess_text(txt: str) -> str:
    txt = txt.replace('-\n', '')
    txt = '\n'.join(line.rstrip() for line in txt.splitlines())
    return txt


def extract_text_pipeline(pdf_path: str, usar_ocr: bool = True, dpi: int = 300, progress_path: Optional[str] = None) -> str:
    p = Path(pdf_path)
    if not p.exists():
        raise FileNotFoundError(pdf_path)

    # 1) try pdfminer
    text = extract_text_pdfminer(p)
    if text and len(text.strip()) >= 100:
        return text

    # 2) try pdftotext (poppler) via system if available
    if POPPLER_DIR.exists():
        pdftotext = POPPLER_DIR / 'pdftotext.exe'
        if pdftotext.exists():
            try:
                proc = subprocess.run(
                    [str(pdftotext), '-layout', '-nopgbrk', str(p), '-'],
                    capture_output=True, text=True, timeout=300
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout
            except Exception:
                pass

    # 3) fallback to OCR if allowed
    if usar_ocr:
        tcmd = find_tesseract()
        if not tcmd:
            return ""
        progress_p = Path(progress_path) if progress_path else None
        ocr_text = ocr_render_and_tesseract(p, tcmd, dpi=dpi, progress_path=progress_p)
        # normalize page markers
        ocr_text = re.sub(r"=== PAGE \d+ ===", "=== PAGE BREAK ===", ocr_text)
        # mark progress done
        if progress_p:
            try:
                now = time.time()
                progress_p.write_text(json.dumps({
                    'status': 'done',
                    'total_pages': None,
                    'pages_converted': None,
                    'percent': 100.0,
                    'eta_seconds': 0,
                    'finished_at': now
                }), encoding='utf-8')
            except Exception:
                pass
        return ocr_text

    return ""


def convert_pdf_to_txt(pdf_path: str, out_dir: Optional[str] = None, usar_ocr: bool = True, dpi: int = 300) -> Tuple[Optional[str], Optional[str]]:
    p = Path(pdf_path)
    if not p.exists():
        return None, f"Arquivo não encontrado: {pdf_path}"

    if not out_dir:
        out_dir = str(p.parent)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    nome_base = p.stem
    txt_file = out_path / f"{nome_base}.txt"
    progress_file = out_path / f"{nome_base}.progress.json"

    try:
        text = extract_text_pipeline(str(p), usar_ocr=usar_ocr, dpi=dpi, progress_path=str(progress_file))
        if not text or len(text.strip()) < 50:
            return None, "Não foi possível extrair texto significativo do PDF"

        text = postprocess_text(text)
        txt_file.write_text(text, encoding='utf-8', errors='replace')
        # write final progress
        try:
            progress_file.write_text(json.dumps({
                'status': 'finished',
                'total_pages': None,
                'pages_converted': None,
                'percent': 100.0,
                'finished_at': time.time(),
                'txt_path': str(txt_file)
            }), encoding='utf-8')
        except Exception:
            pass
        return str(txt_file), None

    except Exception as e:
        return None, str(e)


def read_progress(pdf_path: str, out_dir: Optional[str] = None) -> Optional[dict]:
    """Read the progress JSON file for a given PDF conversion, if present."""
    p = Path(pdf_path)
    if not out_dir:
        out_dir = str(p.parent)
    progress_file = Path(out_dir) / f"{p.stem}.progress.json"
    if not progress_file.exists():
        return None
    try:
        return json.loads(progress_file.read_text(encoding='utf-8'))
    except Exception:
        return None
