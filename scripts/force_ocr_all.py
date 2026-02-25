import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
PDFS = ROOT / 'PDFS'
TXT_DIR = PDFS / 'txt'

# detect tesseract
tesseract_candidates = [
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    Path("C:/Hautomatize/tesseract.exe")
]
TESS = None
for p in tesseract_candidates:
    if p.exists():
        TESS = str(p)
        break

if not TESS:
    print('Nenhum tesseract encontrado. Saindo.')
    raise SystemExit(1)

print('Usando tesseract:', TESS)

try:
    from pdf2image import convert_from_path
except Exception:
    print('pdf2image não disponível. Instale pdf2image e poppler.')
    raise

poppler_candidate = ROOT / 'poppler-25.12.0' / 'Library' / 'bin'
poppler_path = str(poppler_candidate) if poppler_candidate.exists() else None

for pdf_file in PDFS.glob('*.pdf'):
    txt_file = TXT_DIR / (pdf_file.stem + '.txt')
    needs = True
    if txt_file.exists():
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()
            if '=== Sem texto extraído' not in content:
                needs = False
        except Exception:
            needs = True
    if not needs:
        print('Pulando (já tem texto):', pdf_file.name)
        continue

    print('OCR forçando em:', pdf_file.name)
    images = convert_from_path(str(pdf_file), dpi=300, poppler_path=poppler_path) if poppler_path else convert_from_path(str(pdf_file), dpi=300)
    page_texts = []
    tmp_dir = TXT_DIR / 'tmp_force'
    tmp_dir.mkdir(parents=True, exist_ok=True)
    for i, img in enumerate(images, start=1):
        img_path = tmp_dir / f"{pdf_file.stem}_p{i}.png"
        try:
            img.save(img_path)
        except Exception:
            img.convert('RGB').save(img_path)
        try:
            # use shell redirection to avoid subprocess text decoding threads
            tmp_out = tmp_dir / f"{pdf_file.stem}_p{i}.txt"
            cmd = f'"{TESS}" "{img_path}" stdout -l por+eng > "{tmp_out}" 2>&1'
            rc = os.system(cmd)
            if rc == 0:
                try:
                    with open(tmp_out, 'r', encoding='utf-8', errors='replace') as tf:
                        out = tf.read()
                except Exception:
                    out = ''
                page_texts.append(f"--- Página {i} ---\n" + (out or ''))
            else:
                print(f"tesseract retornou {rc} para {img_path}")
                page_texts.append('')
        except Exception as e:
            print('erro tesseract em', img_path, e)
            page_texts.append('')
    # write output
    out_text = '\n\n'.join(page_texts)
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(out_text or f"=== Sem texto extraído de {pdf_file.name} ===\n")
    # cleanup
    for p in tmp_dir.glob(f"{pdf_file.stem}_p*.png"):
        try:
            p.unlink()
        except Exception:
            pass
    print('OCR concluído para', pdf_file.name)

print('Finalizado')
