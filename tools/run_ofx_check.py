import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import conversor_service
p = r"c:\Hautomatize\media\conversor\originais\ExtratoContaCorrenteBNB_20251010_1138_setembro.pdf"
out_dir = r"c:\Hautomatize\media\conversor\originais\processing_test"
res, err = conversor_service.converter_arquivo(p, 'ofx', output_dir=out_dir, usar_ocr=False)
print('result:', res, 'err:', err)
if res and os.path.exists(res):
    print('\n--- OFX sample ---')
    with open(res, 'r', encoding='utf-8', errors='replace') as f:
        for i, line in enumerate(f):
            print(line.rstrip())
            if i > 60:
                break
