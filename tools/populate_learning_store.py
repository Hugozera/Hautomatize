import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import conversor_service

pdfs = [
    r"c:\Hautomatize\media\conversor\originais\STONE_AGOSTO_TODO.pdf",
    r"c:\Hautomatize\media\conversor\originais\ExtratoContaCorrenteBNB_20251010_1138_setembro.pdf",
    r"c:\Hautomatize\media\conversor\originais\ITAU_AGOSTO_TODO.pdf",
    r"c:\Hautomatize\media\conversor\originais\Santander_Agosto_Completo.pdf",
]
out_dir = r"c:\Hautomatize\media\conversor\learning_run"
os.makedirs(out_dir, exist_ok=True)

for p in pdfs:
    if not os.path.exists(p):
        print('Missing:', p)
        continue
    print('\nProcessing:', p)
    try:
        res, err = conversor_service.converter_arquivo(p, 'ofx', output_dir=out_dir, usar_ocr=True)
        print('-> result:', res, 'err:', err)
    except Exception as e:
        print('-> exception:', e)

print('\nDone')
