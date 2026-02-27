import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import conversor_service
p = r"c:\Hautomatize\media\conversor\originais\STONE_AGOSTO_TODO.pdf"
out_dir = r"c:\Hautomatize\media\conversor\originais\processing_test"
res, err = conversor_service.converter_arquivo(p, 'ofx', output_dir=out_dir, usar_ocr=False)
print('result:', res, 'err:', err)
if res and os.path.exists(res):
    print('\nOFX generated at', res)
else:
    txt_candidate = os.path.join(out_dir, os.path.splitext(os.path.basename(p))[0] + '.txt')
    if os.path.exists(txt_candidate):
        print('Fast-path txt at', txt_candidate)
    else:
        print('No fast-path txt')
