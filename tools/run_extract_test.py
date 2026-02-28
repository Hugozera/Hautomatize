import os, sys
sys.path.insert(0, r'c:\Hautomatize')
from core.conversor_service import converter_arquivo, ConversorService

paths = [
    r'c:\Hautomatize\media\conversor\originais\ExtratoContaCorrenteBNB_20251010_1138_setembro.pdf',
    r'c:\Hautomatize\media\conversor\originais\STONE_AGOSTO_TODO.pdf'
]
for p in paths:
    print('\n---', p)
    out, err = converter_arquivo(p, 'txt', output_dir=os.path.join(os.path.dirname(p),'processing_test'), usar_ocr=False)
    print('result:', out, 'err:', err)
    if out and os.path.exists(out):
        try:
            with open(out, 'r', encoding='utf-8', errors='replace') as f:
                lines = [ln.strip() for ln in f.readlines() if ln.strip()]
            print('total lines in txt padrao:', len(lines))
            sample = lines[:100]
            deb=0; cred=0
            for ln in sample:
                parts = ln.split(';')
                if len(parts)>=3:
                    tipo = parts[2].upper()
                    if 'DEBIT' in tipo or 'DEBITO' in tipo:
                        deb+=1
                    else:
                        cred+=1
            print('sample lines (first 10):')
            for ln in sample[:10]:
                print(ln)
            print('counts in first', len(sample), 'lines -> debit:', deb, 'credit:', cred)
        except Exception as e:
            print('failed reading out:', e)
    else:
        print('no output file')
