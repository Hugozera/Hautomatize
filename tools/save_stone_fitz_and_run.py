import os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import conversor_service

p = r"c:\Hautomatize\media\conversor\originais\STONE_AGOSTO_TODO.pdf"
out_dir = r"c:\Hautomatize\media\conversor\originais\processing_test"

try:
    import fitz
    from PIL import Image
    import io
    import pytesseract
except Exception as e:
    print('Missing modules for fitz OCR:', e)
    sys.exit(1)

# set tesseract binary if present
tpath = r"C:\Hautomatize\Tesseract-OCR\tesseract.exe"
if os.path.exists(tpath):
    pytesseract.pytesseract.tesseract_cmd = tpath

print('Opening', p)
doc = fitz.open(p)
texts = []
start = time.time()
for i, page in enumerate(doc, start=1):
    try:
        # render at 300 dpi
        zoom = 300.0 / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img_bytes = pix.tobytes('png')
        img = Image.open(io.BytesIO(img_bytes))
        txt = pytesseract.image_to_string(img, lang='por+eng')
        texts.append(txt)
        print(f'Page {i} length {len(txt)}')
    except Exception as e:
        print('page error', i, e)

all_text = '\n\n=== PAGE BREAK ===\n\n'.join(texts)
if not os.path.exists(out_dir):
    os.makedirs(out_dir, exist_ok=True)

nome_base = os.path.splitext(os.path.basename(p))[0]
padrao_path = os.path.join(out_dir, f"{nome_base}_padrao.txt")
fast_path = os.path.join(out_dir, f"{nome_base}.txt")
try:
    with open(padrao_path, 'w', encoding='utf-8') as f:
        f.write(all_text)
    with open(fast_path, 'w', encoding='utf-8') as f:
        f.write(all_text)
    print('Saved padrao txt to', padrao_path)
except Exception as e:
    print('Failed to save txt:', e)

# Now call converter using existing txt (usar_ocr=False)
res, err = conversor_service.converter_arquivo(p, 'ofx', output_dir=out_dir, usar_ocr=False)
print('result:', res, 'err:', err)
if res and os.path.exists(res):
    print('\n--- OFX sample ---')
    with open(res, 'r', encoding='utf-8', errors='replace') as f:
        for i, line in enumerate(f):
            print(line.rstrip())
            if i > 120:
                break
else:
    print('No OFX; checking padrao file sample')
    if os.path.exists(padrao_path):
        with open(padrao_path, 'r', encoding='utf-8', errors='replace') as f:
            for i, line in enumerate(f):
                print(line.rstrip())
                if i > 120:
                    break

print('Elapsed', time.time()-start)
