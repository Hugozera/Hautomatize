#!/usr/bin/env python3
from pathlib import Path
import re
import sys

TXT = Path('PDFS/txt/436-7 7.txt')
PDF = Path('PDFS/436-7 7.pdf')
POPPLER = Path('poppler-25.12.0/Library/bin')

def pdf_page_count(pdf_path):
    try:
        from PyPDF2 import PdfReader
        return len(PdfReader(str(pdf_path)).pages)
    except Exception:
        try:
            from pdf2image import convert_from_path
            poppler_path = str(POPPLER) if POPPLER.exists() else None
            imgs = convert_from_path(str(pdf_path), poppler_path=poppler_path, first_page=1, last_page=1)
            # convert_from_path with single page still needs to know total; fallback: convert all
            imgs_all = convert_from_path(str(pdf_path), poppler_path=poppler_path)
            return len(imgs_all)
        except Exception:
            return None

def main():
    if not TXT.exists():
        print('MISSING_TXT')
        sys.exit(2)
    txt = TXT.read_text(encoding='utf-8', errors='replace')

    # page-breaks
    page_breaks = txt.count('=== PAGE BREAK ===')

    # PDF page count
    pdf_pages = pdf_page_count(PDF)

    # header checks
    headers = {
        'cliente': 'Cliente' in txt,
        'conta': 'Conta' in txt,
        'data_header': 'Data' in txt or 'Data ' in txt,
        'periodo': 'Período dos lançamentos' in txt or 'Período' in txt,
    }

    # date occurrences
    dates = re.findall(r'\b\d{2}/\d{2}/\d{4}\b', txt)

    # amount-like occurrences (e.g., 1.234,56)
    amounts = re.findall(r'\d{1,3}(?:[\.\d]{0,})(?:,\d{2})', txt)

    # suspicious replacement chars
    replacement_chars = '�' in txt

    # basic numeric sanity: at least one amount per page on average
    avg_amounts = len(amounts) / (pdf_pages or max(1, page_breaks+1))

    print('PDF_PAGES:', pdf_pages)
    print('PAGE_BREAKS_in_txt:', page_breaks)
    print('TXT_CHARS:', len(txt))
    print('HEADERS:', headers)
    print('DATE_COUNT:', len(dates))
    print('AMOUNT_COUNT:', len(amounts))
    print('AMOUNTS_PER_PAGE(avg):', f"{avg_amounts:.2f}")
    print('HAS_REPLACEMENT_CHAR:', replacement_chars)

    # quick content completeness heuristics
    issues = []
    if pdf_pages is None:
        issues.append('Could not determine PDF page count (missing libs)')
    else:
        if pdf_pages != page_breaks + 1:
            issues.append(f'Page count mismatch: PDF={pdf_pages} vs TXT pages={page_breaks+1}')

    if not headers['cliente'] or not headers['conta']:
        issues.append('Missing expected header fields (Cliente/Conta)')

    if len(dates) < 10:
        issues.append('Unusually few dates extracted (<10)')

    if len(amounts) < 50:
        issues.append('Unusually few amounts extracted (<50)')

    if replacement_chars:
        issues.append('Replacement character(s) found in text')

    if issues:
        print('ISSUES_FOUND:')
        for it in issues:
            print('-', it)
        sys.exit(3)
    else:
        print('OK: basic validation passed')
        sys.exit(0)

if __name__ == '__main__':
    main()
