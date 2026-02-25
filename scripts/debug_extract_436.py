import traceback
from pathlib import Path

pdf = Path('PDFS') / '436-7 7.pdf'
print('PDF exists:', pdf.exists(), 'path=', pdf)

try:
    from pdfminer.high_level import extract_text
    print('pdfminer available')
    try:
        txt = extract_text(str(pdf))
        print('pdfminer extracted length:', len(txt) if txt else 0)
        if txt:
            print('preview:', repr(txt[:500]))
    except Exception as e:
        print('pdfminer error:')
        traceback.print_exc()
except Exception:
    print('pdfminer not available')

try:
    from pdf2image import convert_from_path
    print('pdf2image available')
    # try with repository poppler
    poppler_candidate = Path(__file__).resolve().parent.parent / 'poppler-25.12.0' / 'Library' / 'bin'
    poppler_path = str(poppler_candidate) if poppler_candidate.exists() else None
    print('poppler_path exists:', poppler_candidate.exists(), 'poppler_path=', poppler_path)
    try:
        images = convert_from_path(str(pdf), dpi=200, poppler_path=poppler_path) if poppler_path else convert_from_path(str(pdf), dpi=200)
        print('convert_from_path returned images:', len(images))
    except Exception as e:
        print('convert_from_path error:')
        traceback.print_exc()
except Exception:
    print('pdf2image not available')

try:
    import pytesseract
    print('pytesseract available')
except Exception:
    print('pytesseract not available')
