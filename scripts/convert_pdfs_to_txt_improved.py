#!/usr/bin/env python3
"""
Improved PDF -> TXT converter.
- Uses pdfminer.six to extract text when available.
- Falls back to rendering pages with pdf2image + Poppler + Tesseract OCR.
- Invokes Tesseract by filename (no shell redirection) so output files are written in UTF-8.
- Writes final output as UTF-8 and does minimal post-processing (remove hyphen-newline joins).

Usage: python scripts/convert_pdfs_to_txt_improved.py [PDF_PATH ...]
If no args provided, processes all PDFs under PDFS/.
"""
from __future__ import annotations

import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

POPPLER_DIR = Path("poppler-25.12.0/Library/bin")
DEFAULT_TESSERACT = Path(r"C:/Program Files/Tesseract-OCR/tesseract.exe")


def find_tesseract() -> Optional[str]:
    # Prefer the functional Program Files tesseract, fallback to PATH
    if DEFAULT_TESSERACT.exists():
        return str(DEFAULT_TESSERACT)
    # try plain tesseract in PATH
    which = shutil.which("tesseract")
    return which


def extract_text_pdfminer(path: Path) -> str:
    try:
        from pdfminer.high_level import extract_text

        text = extract_text(str(path))
        return text or ""
    except Exception:
        return ""


def ocr_render_and_tesseract(pdf_path: Path, tesseract_cmd: str, dpi: int = 400) -> str:
    try:
        from pdf2image import convert_from_path
    except Exception as e:
        raise RuntimeError("pdf2image not installed") from e

    poppler_path = None
    if POPPLER_DIR.exists():
        poppler_path = str(POPPLER_DIR)

    out_pages: list[str] = []
    with tempfile.TemporaryDirectory() as tmpd:
        tmpd_p = Path(tmpd)
        images = convert_from_path(str(pdf_path), dpi=dpi, poppler_path=poppler_path)
        for i, img in enumerate(images, start=1):
            img_file = tmpd_p / f"page_{i:04d}.png"
            img.save(img_file, format="PNG")

            out_base = tmpd_p / f"page_{i:04d}"
            cmd = [tesseract_cmd, str(img_file), str(out_base), '-l', 'por+eng', '--oem', '1', '--psm', '6']
            # Run without shell so tesseract writes out_base.txt in UTF-8
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            if proc.returncode != 0:
                # include stderr for diagnostics but continue
                out_pages.append(f"=== TESSERACT-ERROR page {i} rc={proc.returncode} stderr={proc.stderr.decode('utf-8', 'replace')}\n")
                continue

            txt_path = out_base.with_suffix('.txt')
            if txt_path.exists():
                # read as utf-8 (tesseract uses utf-8)
                out_pages.append(txt_path.read_text(encoding='utf-8', errors='replace'))
            else:
                out_pages.append("")

    return "\n\n=== PAGE BREAK ===\n\n".join(out_pages)


def postprocess_text(txt: str) -> str:
    # Remove hyphenated line breaks like 'exam-\nple' -> 'example'
    txt = txt.replace('-\n', '')
    # Collapse multiple consecutive spaces
    txt = '\n'.join(line.rstrip() for line in txt.splitlines())
    return txt


def process_pdf(pdf_path: Path, out_dir: Path, tesseract_cmd: Optional[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / (pdf_path.stem + '.txt')

    # 1) try pdfminer text extraction first
    text = extract_text_pdfminer(pdf_path)
    # If extracted text is short or empty, fallback to OCR
    if not text or len(text.strip()) < 50:
        if not tesseract_cmd:
            raise RuntimeError('Tesseract not found for OCR fallback')
        text = ocr_render_and_tesseract(pdf_path, tesseract_cmd)

    text = postprocess_text(text)

    # write as UTF-8
    out_file.write_text(text, encoding='utf-8', errors='replace')
    print(f"Wrote {out_file}")


def main():
    args = sys.argv[1:]
    tesseract_cmd = find_tesseract()
    if not args:
        base = Path('PDFS')
        pdfs = sorted([p for p in base.glob('*.pdf')])
    else:
        pdfs = [Path(a) for a in args]

    if not pdfs:
        print('No PDFs found')
        return

    out_dir = Path('PDFS') / 'txt'
    for p in pdfs:
        try:
            print(f'Processing {p}...')
            process_pdf(p, out_dir, tesseract_cmd)
        except Exception as e:
            print(f'ERROR processing {p}: {e}', file=sys.stderr)


if __name__ == '__main__':
    main()
