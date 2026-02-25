from pathlib import Path
import subprocess

pdf = Path('PDFS') / '436-7 7.pdf'
txt = Path('PDFS') / 'txt' / '436-7 7.txt'

poppler_candidate = Path(__file__).resolve().parent.parent / 'poppler-25.12.0' / 'Library' / 'bin'
poppler_path = str(poppler_candidate) if poppler_candidate.exists() else None

# prefer Program Files tesseract
candidates = [Path('C:/Program Files/Tesseract-OCR/tesseract.exe'), Path('C:/Program Files (x86)/Tesseract-OCR/tesseract.exe'), Path('C:/Hautomatize/tesseract.exe')]
TESS = None
for p in candidates:
    if p.exists():
        TESS = str(p)
        break

print('PDF exists:', pdf.exists())
print('Using tesseract:', TESS)

from pdf2image import convert_from_path
images = convert_from_path(str(pdf), dpi=300, poppler_path=poppler_path) if poppler_path else convert_from_path(str(pdf), dpi=300)
print('Pages:', len(images))

tmp = txt.parent / 'tmp_ocr_direct'
tmp.mkdir(parents=True, exist_ok=True)
page_texts = []
for i, img in enumerate(images, start=1):
    img_path = tmp / f'p{i}.png'
    img.save(img_path)
    print('Saved', img_path)
    try:
        proc = subprocess.run([TESS, str(img_path), 'stdout', '-l', 'por+eng'], capture_output=True, text=True, timeout=60)
        print('tess rc', proc.returncode, 'stdout_len', len(proc.stdout))
        page_texts.append(f'--- Página {i} ---\n' + (proc.stdout or ''))
    except Exception as e:
        print('error', e)
        page_texts.append('')

with open(txt, 'w', encoding='utf-8') as f:
    f.write('\n\n'.join(page_texts) or f"=== Sem texto extraído de {pdf.name} ===\n")
print('Wrote', txt)
