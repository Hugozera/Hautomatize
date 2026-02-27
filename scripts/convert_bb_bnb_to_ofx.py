from pathlib import Path
import sys
from pathlib import Path as P
# ensure project root on sys.path
sys.path.insert(0, str(P('.').resolve()))
from core.conversor_service import converter_arquivo

BASE = Path('media/conversor/originais')
OUT = Path('media/conversor/convertidos')
OUT.mkdir(parents=True, exist_ok=True)

files = [
    'BB.pdf',
    'ExtratoContaCorrenteBNB_20250811_1643_julho.pdf',
    'ExtratoContaCorrenteBNB_20250910_1257_agosto.pdf',
    'ExtratoContaCorrenteBNB_20251010_1138_setembro.pdf',
    'ExtratoContaCorrenteBNB_20251010_1138_setembro_9CmrGR9.pdf',
    'ExtratoContaCorrenteBNB_novembro.pdf'
]

results = []
for f in files:
    p = str((BASE / f).resolve())
    print('\nProcessing', f)
    ofx_path, err = converter_arquivo(p, 'ofx', output_dir=str(OUT), usar_ocr=True, dpi=300)
    results.append((f, ofx_path, err))
    print(' ->', ofx_path, err)

print('\nSummary:')
for r in results:
    print(r)
