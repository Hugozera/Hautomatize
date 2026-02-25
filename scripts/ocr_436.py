from pathlib import Path
import traceback

pdf = Path('PDFS') / '436-7 7.pdf'
txt = Path('PDFS') / 'txt' / '436-7 7.txt'

poppler_candidate = Path(__file__).resolve().parent.parent / 'poppler-25.12.0' / 'Library' / 'bin'
poppler_path = str(poppler_candidate) if poppler_candidate.exists() else None

try:
    from pdf2image import convert_from_path
    import pytesseract
except Exception as e:
    print('Dependências ausentes:', e)
    raise

print('PDF:', pdf.exists(), pdf)
print('Poppler path:', poppler_path)

try:
    images = convert_from_path(str(pdf), dpi=300, poppler_path=poppler_path) if poppler_path else convert_from_path(str(pdf), dpi=300)
    print('Páginas renderizadas:', len(images))
    page_texts = []
    for i, img in enumerate(images, start=1):
        try:
            txt_page = pytesseract.image_to_string(img, lang='por+eng', config='--psm 1')
        except Exception:
            txt_page = pytesseract.image_to_string(img)
        page_texts.append(f'--- Página {i} ---\n' + txt_page)
    full = '\n\n'.join(page_texts)
    txt.parent.mkdir(parents=True, exist_ok=True)
    with open(txt, 'w', encoding='utf-8') as f:
        f.write(full)
    print('OCR concluído. Saída em:', txt)
except Exception:
    print('Erro durante OCR:')
    traceback.print_exc()
