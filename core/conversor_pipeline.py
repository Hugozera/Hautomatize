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
import concurrent.futures
from concurrent.futures import FIRST_COMPLETED
from typing import Optional, Tuple

POPPLER_DIR = Path("poppler-25.12.0/Library/bin")
DEFAULT_TESSERACT = Path(r"Tesseract-OCR/tesseract.exe")


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
    # Prefer rendering via PyMuPDF (fitz) when available to avoid poppler hangs.
    try:
        import fitz
        from PIL import Image
        import io
        has_fitz = True
    except Exception:
        has_fitz = False

    poppler_path = None
    if POPPLER_DIR.exists():
        poppler_path = str(POPPLER_DIR)

    out_pages: list[str] = []
    started = time.time()
    pages_converted = 0

    if has_fitz:
        try:
            import fitz
            import pytesseract
            # ensure pytesseract uses configured tesseract binary if provided
            if tesseract_cmd:
                try:
                    pytesseract.pytesseract.tesseract_cmd = str(tesseract_cmd)
                except Exception:
                    pass
            doc = fitz.open(str(pdf_path))
            zoom = dpi / 72.0
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                img_bytes = pix.tobytes('png')
                img = Image.open(io.BytesIO(img_bytes))
                # protect against tesseract hanging by using subprocess via pytesseract
                txt = pytesseract.image_to_string(img, lang='por+eng')
                out_pages.append(txt)
                pages_converted += 1
            total_pages = len(out_pages)
        except Exception as e:
            # on any fitz-based error, fall back to pdf2image below
            out_pages = []
            total_pages = 0
    else:
        try:
            from pdf2image import convert_from_path
        except Exception as e:
            return f"=== OCR-ERROR pdf2image not installed: {str(e)}\n"

        with tempfile.TemporaryDirectory() as tmpd:
            tmpd_p = Path(tmpd)
            try:
                # allow longer timeout for poppler image conversion (some PDFs take long)
                images = convert_from_path(str(pdf_path), dpi=dpi, poppler_path=poppler_path, timeout=600)
            except Exception as e:
                # return a clear OCR error marker so upstream can continue and log
                return f"=== OCR-ERROR convert_from_path: {str(e)}\n"
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
            try:
                # protect against Tesseract hanging: timeout per page
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=300,
                )
            except subprocess.TimeoutExpired as te:
                out_pages.append(f"=== TESSERACT-TIMEOUT page {i} after 300s\n")
                # update progress and continue to next page
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
                            'current_page': i,
                            'error': 'tesseract_timeout'
                        }), encoding='utf-8')
                    except Exception:
                        pass
                continue

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


def extract_text_pipeline(pdf_path: str, usar_ocr: bool = True, dpi: int = 300, progress_path: Optional[str] = None, timeout_seconds: int = 180) -> str:
    p = Path(pdf_path)
    if not p.exists():
        raise FileNotFoundError(pdf_path)

    # 1) try pdfminer
    text = extract_text_pdfminer(p)
    if text and len(text.strip()) >= 100:
        return text

    # Quick pre-check: try to extract from first pages fast (fitz text or low-res OCR)
    def quick_page_check(max_pages: int = 2, per_page_timeout: int = 5) -> str:
        try:
            import fitz
        except Exception:
            return ""
        try:
            doc = fitz.open(str(p))
            out = []
            import pytesseract
            from PIL import Image
            import io
            for i, page in enumerate(doc, start=0):
                if i >= max_pages:
                    break
                try:
                    # prefer embedded text via fitz
                    t = page.get_text('text')
                    if t and len(t.strip()) >= 80:
                        out.append(t)
                        continue
                    # otherwise render a small image and OCR with timeout
                    zoom = 150 / 72.0
                    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                    img_bytes = pix.tobytes('png')
                    img = Image.open(io.BytesIO(img_bytes))

                    def do_ocr():
                        return pytesseract.image_to_string(img, lang='por+eng')

                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as exe:
                        fut = exe.submit(do_ocr)
                        try:
                            txt = fut.result(timeout=per_page_timeout)
                        except Exception:
                            txt = ''
                    if txt and len(txt.strip()) >= 80:
                        out.append(txt)
                except Exception:
                    continue
            doc.close()
            return "\n\n=== PAGE BREAK ===\n\n".join(out)
        except Exception:
            return ""

    quick = ""
    try:
        quick = quick_page_check()
    except Exception:
        quick = ""
    if quick and len(quick.strip()) >= 100:
        return quick

    # 2) try pdftotext (poppler) via system if available or parallel strategies
    def try_pdftotext() -> str:
        if not POPPLER_DIR.exists():
            return ""
        pdftotext = POPPLER_DIR / 'pdftotext.exe'
        if not pdftotext.exists():
            return ""
        try:
            proc = subprocess.run(
                [str(pdftotext), '-layout', '-nopgbrk', str(p), '-'],
                capture_output=True, text=True, timeout=300
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout
        except Exception:
            return ""
        return ""

    def try_pdfminer() -> str:
        try:
            return extract_text_pdfminer(p)
        except Exception:
            return ""

    def try_ocr_pdf2image(dpi_try: int) -> str:
        tcmd = find_tesseract()
        if not tcmd:
            return ""
        progress_p = Path(progress_path) if progress_path else None
        return ocr_render_and_tesseract(p, tcmd, dpi=dpi_try, progress_path=progress_p)

    def try_ocr_fitz(dpi_try: int) -> str:
        try:
            import fitz
            from PIL import Image
            import io
            import pytesseract
        except Exception:
            return ""
        out_pages = []
        try:
            doc = fitz.open(str(p))
            zoom = dpi_try / 72.0
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                img_bytes = pix.tobytes('png')
                img = Image.open(io.BytesIO(img_bytes))
                txt = pytesseract.image_to_string(img, lang='por+eng')
                out_pages.append(txt)
            return "\n\n=== PAGE BREAK ===\n\n".join(out_pages)
        except Exception:
            return ""

    # If we have sufficient results from pdftotext quickly, return it; otherwise run parallel attempts
    fast_pdftotext = try_pdftotext()
    if fast_pdftotext and len(fast_pdftotext.strip()) >= 100:
        return fast_pdftotext

    # If OCR is not allowed, return whatever we have (pdfminer or pdftotext), otherwise try parallel strategies
    if not usar_ocr:
        # prefer pdfminer text then pdftotext
        if text and len(text.strip()) >= 50:
            return text
        if fast_pdftotext and len(fast_pdftotext.strip()) >= 50:
            return fast_pdftotext
        return ""

    # Run multiple extractors in parallel and take first acceptable result
    candidates = []
    # include pdfminer and pdftotext as quick candidates
    candidates.append((try_pdfminer, ()))
    candidates.append((try_pdftotext, ()))
    # include OCR strategies with a few DPI values
    dpi_values = [300, 400]
    # prefer fitz-based rendering (PyMuPDF) to avoid blocking poppler/pdf2image
    for dv in dpi_values:
        candidates.append((try_ocr_fitz, (dv,)))

    # Run extractors in parallel but avoid blocking shutdown by not using context manager
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(candidates)))
    futures = {ex.submit(func, *args): (func, args) for func, args in candidates}
    try:
        try:
            for fut in concurrent.futures.as_completed(futures, timeout=timeout_seconds):
                try:
                    result = fut.result()
                except Exception:
                    result = ""
                if result and len(result.strip()) >= 100:
                    # cancel remaining
                    for of in list(futures.keys()):
                        if not of.done():
                            of.cancel()
                    # normalize page markers
                    result = re.sub(r"=== PAGE \d+ ===", "=== PAGE BREAK ===", result)
                    return result
            # No candidate returned large text within timeout; try to return any moderately sized text
            for fut in list(futures.keys()):
                try:
                    r = fut.result(timeout=0)
                    if r and len(r.strip()) >= 50:
                        r = re.sub(r"=== PAGE \d+ ===", "=== PAGE BREAK ===", r)
                        return r
                except Exception:
                    continue
        except concurrent.futures.TimeoutError:
            # timed out waiting for long OCR; attempt to cancel remaining futures and return what we have
            for of in list(futures.keys()):
                try:
                    if not of.done():
                        of.cancel()
                except Exception:
                    pass
            # fall through to return empty
    finally:
        try:
            ex.shutdown(wait=False)
        except Exception:
            pass

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
        # tentativa inicial (use a shorter timeout to fail fast in web requests)
        start_time = time.time()
        MAX_TOTAL_SECONDS = 180
        # Increase initial timeout to allow longer extraction for complex PDFs
        text = extract_text_pipeline(str(p), usar_ocr=usar_ocr, dpi=dpi, progress_path=str(progress_file), timeout_seconds=60)

        # se pouco texto, tentar passes de OCR mais agressivos (maior DPI)
        if usar_ocr and (not text or len(text.strip()) < 50):
            for extra_dpi in (400, 600, 800):
                # check overall elapsed time to avoid long blocking
                if time.time() - start_time > MAX_TOTAL_SECONDS:
                    return None, 'Tempo máximo de extração excedido'
                try:
                    # allow longer timeout for aggressive OCR passes
                    extra_text = extract_text_pipeline(str(p), usar_ocr=usar_ocr, dpi=extra_dpi, progress_path=str(progress_file), timeout_seconds=90)
                    if extra_text and len(extra_text.strip()) >= 50:
                        text = extra_text
                        break
                except Exception:
                    continue

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
