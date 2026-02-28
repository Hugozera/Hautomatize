import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import conversor_service
p = r"c:\Hautomatize\media\conversor\originais\STONE_AGOSTO_TODO.pdf"
out_dir = r"c:\Hautomatize\media\conversor\originais\processing_test"
res, err = conversor_service.converter_arquivo(p, 'ofx', output_dir=out_dir, usar_ocr=True)
print('result:', res, 'err:', err)
if res and os.path.exists(res):
    print('\n--- OFX sample ---')
    with open(res, 'r', encoding='utf-8', errors='replace') as f:
        for i, line in enumerate(f):
            print(line.rstrip())
            if i > 80:
                break
else:
    # try to show any intermediate txt produced
    txt_candidate = os.path.join(out_dir, os.path.splitext(os.path.basename(p))[0] + '_padrao.txt')
    if os.path.exists(txt_candidate):
        print('\n--- TXT padrão sample ---')
        with open(txt_candidate, 'r', encoding='utf-8', errors='replace') as f:
            for i, line in enumerate(f):
                print(line.rstrip())
                if i > 80:
                    break
