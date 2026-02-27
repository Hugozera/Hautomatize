import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))
from core.conversor_service import processar_pasta

BASE = Path('media/conversor/originais')
OUT = BASE / 'convertidos'

# Remove existing OFX files
if OUT.exists():
    for f in OUT.glob('*.ofx'):
        try:
            f.unlink()
        except Exception:
            pass

print('Reprocessing all PDFs in', BASE)
results = processar_pasta(str(BASE), formato_destino='ofx', output_dir=str(OUT), usar_ocr=True, dpi=600)

# print summary
for arquivo, caminho, erro in results:
    print(arquivo, '->', caminho, 'err=', erro)

print('\nDone')
