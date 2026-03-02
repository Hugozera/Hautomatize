"""Interactive PDF merge helper.

Usage:
  - Run: python scripts/pdf_merge_editor.py file1.pdf file2.pdf ... -o out.pdf
  - The script will generate preview images in a temp folder and show a mapping like p1:1, p2:4 etc.
  - Enter sequence as comma-separated tokens, e.g.: p1:1,p2:4,p1:2

This is a minimal CLI helper that uses pdf2image (if available) to create previews
and pypdf to merge pages according to the sequence.
"""
import os
import sys
import tempfile
import argparse
import shutil
import json
from typing import List

POPPLER_PATH = None
try:
    from core.conversor_service import ConversorService
    POPPLER_PATH = ConversorService.POPPLER_PATH
except Exception:
    POPPLER_PATH = None

try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
except Exception:
    HAS_PDF2IMAGE = False

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


def list_pages(paths: List[str]):
    """Return a mapping of source keys to page counts and file paths."""
    mapping = {}
    for i, p in enumerate(paths, start=1):
        key = f'p{i}'
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        if PdfReader:
            reader = PdfReader(p)
            pages = len(reader.pages)
        else:
            pages = None
        mapping[key] = {'path': p, 'pages': pages}
    return mapping


def generate_previews(mapping, tmpdir):
    previews = {}
    if not HAS_PDF2IMAGE:
        print('pdf2image not available — skipping previews')
        return previews

    for key, info in mapping.items():
        path = info['path']
        try:
            images = convert_from_path(path, dpi=100, poppler_path=POPPLER_PATH) if POPPLER_PATH else convert_from_path(path, dpi=100)
        except Exception as e:
            print('Failed to render', path, e)
            continue
        previews[key] = []
        for idx, img in enumerate(images, start=1):
            out = os.path.join(tmpdir, f"{key}_p{idx}.png")
            img.save(out, 'PNG')
            previews[key].append(out)
    return previews


def parse_sequence(text: str):
    """Parse sequence like p1:1,p2:4,p1:2 into list of dicts."""
    items = [t.strip() for t in text.split(',') if t.strip()]
    seq = []
    for it in items:
        if ':' not in it:
            raise ValueError('Each token must be source:page')
        src, page = it.split(':', 1)
        seq.append({'source': src, 'page': int(page)})
    return seq


def main(argv=None):
    parser = argparse.ArgumentParser(description='PDF merge editor (minimal)')
    parser.add_argument('pdfs', nargs='+', help='Input PDFs')
    parser.add_argument('-o', '--out', required=True, help='Output merged PDF')
    args = parser.parse_args(argv)

    mapping = list_pages(args.pdfs)
    print('Found sources:')
    for k, v in mapping.items():
        print(f" - {k}: {v['path']} ({v['pages']} pages)")

    tmpdir = tempfile.mkdtemp(prefix='pdf_merge_preview_')
    print('Rendering previews to', tmpdir)
    previews = generate_previews(mapping, tmpdir)

    if previews:
        print('Preview images created. Open the folder to inspect thumbnails:')
        print(tmpdir)
    else:
        print('No previews available.')

    print('\nNow enter the desired sequence, e.g.: p1:1,p2:4,p1:2')
    seq_text = input('Sequence> ').strip()
    sequence = parse_sequence(seq_text)

    from core.conversor_service import ConversorService
    sources = {k: v['path'] for k, v in mapping.items()}
    out = ConversorService.merge_pdfs_by_sequence(args.out, sources, sequence)
    print('Merged output saved to', out)

    print('Cleaning previews...')
    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass


if __name__ == '__main__':
    main()
