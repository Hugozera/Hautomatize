import sys, os, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import conversor_service

try:
    import fitz
    from PIL import Image
    import io
    import pytesseract
    from multiprocessing import Process, Queue
except Exception as e:
    print('Missing OCR libs:', e)
    sys.exit(1)


def ocr_worker(img_bytes, q):
    try:
        img = Image.open(io.BytesIO(img_bytes))
        txt = pytesseract.image_to_string(img, lang='por+eng')
        q.put(txt)
    except Exception as e:
        q.put(None)


def ocr_with_timeout(img_bytes, timeout=15):
    q = Queue()
    p = Process(target=ocr_worker, args=(img_bytes, q))
    p.start()
    p.join(timeout)
    if p.is_alive():
        p.terminate()
        p.join()
        return None
    try:
        return q.get_nowait()
    except Exception:
        return None

pdfs = [
    r"c:\Hautomatize\media\conversor\originais\STONE_AGOSTO_TODO.pdf",
    r"c:\Hautomatize\media\conversor\originais\ExtratoContaCorrenteBNB_20251010_1138_setembro.pdf",
    r"c:\Hautomatize\media\conversor\originais\ITAU_AGOSTO_TODO.pdf",
    r"c:\Hautomatize\media\conversor\originais\Santander_Agosto_Completo.pdf",
]
out_dir = r"c:\Hautomatize\media\conversor\learning_run2"
os.makedirs(out_dir, exist_ok=True)

# set tesseract path if present
tpath = r"C:\Hautomatize\Tesseract-OCR\tesseract.exe"
if os.path.exists(tpath):
    pytesseract.pytesseract.tesseract_cmd = tpath

def main():
    for p in pdfs:
        if not os.path.exists(p):
            print('Missing:', p)
            continue
        print('\nProcessing (safe2):', p)
        nome_base = os.path.splitext(os.path.basename(p))[0]
        padrao_path = os.path.join(out_dir, f"{nome_base}_padrao.txt")
        if not os.path.exists(padrao_path):
            try:
                doc = fitz.open(p)
                texts = []
                for i, page in enumerate(doc, start=1):
                    try:
                        zoom = 2.0
                        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                        img_bytes = pix.tobytes('png')
                        txt = ocr_with_timeout(img_bytes, timeout=15)
                        if txt is None:
                            print(' page', i, 'ocr timed out')
                            texts.append('')
                        else:
                            texts.append(txt)
                            print(' page', i, 'len', len(txt))
                    except Exception as e:
                        print(' page error', i, e)
                        texts.append('')
                        continue
                all_text = '\n\n=== PAGE BREAK ===\n\n'.join(texts)
                with open(padrao_path, 'w', encoding='utf-8') as f:
                    f.write(all_text)
                print('Saved padrao:', padrao_path)
            except Exception as e:
                print('OCR failed for', p, e)
                continue
        else:
            print('Padrao exists, skipping OCR:', padrao_path)

        # Now call converter but prefer cached txt (usar_ocr=False)
        try:
            res, err = conversor_service.converter_arquivo(p, 'ofx', output_dir=out_dir, usar_ocr=False)
            print('-> result:', res, 'err:', err)
        except Exception as e:
            print('converter_arquivo failed:', e)

    print('\nSafe2 run complete')


if __name__ == '__main__':
    main()
