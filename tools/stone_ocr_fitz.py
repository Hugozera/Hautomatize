import sys, os, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    import fitz
    from PIL import Image
    import pytesseract
except Exception as e:
    print('Missing lib:', e)
    sys.exit(1)

p = r"c:\Hautomatize\media\conversor\originais\STONE_AGOSTO_TODO.pdf"
print('Opening', p)
doc = fitz.open(p)
texts = []
start = time.time()
for i, page in enumerate(doc, start=1):
    try:
        # render at 2x (approx 144 dpi); adjust matrix for desired DPI
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_data = pix.tobytes('png')
        img = Image.open(sys.modules['io'].BytesIO(img_data))
        # set tesseract cmd if available in project
        try:
            tpath = r"C:\Hautomatize\Tesseract-OCR\tesseract.exe"
            if os.path.exists(tpath):
                pytesseract.pytesseract.tesseract_cmd = tpath
        except Exception:
            pass
        txt = pytesseract.image_to_string(img, lang='por+eng')
        texts.append(txt)
        print(f'Page {i} length {len(txt)}')
        if i >= 5:
            break
    except Exception as e:
        print('page error', i, e)
        continue

print('Total pages processed:', len(texts))
all_text = '\n\n=== PAGE BREAK ===\n\n'.join(texts)
print('\nFirst 2000 chars:\n')
print(all_text[:2000])
print('Elapsed', time.time()-start)
