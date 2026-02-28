import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))
from core.conversor_service import converter_arquivo

ORIG = Path('media/conversor/originais')
OUT = Path('media/conversor/convertidos')

# banks to try forcing in order
BANKS = ['ITAU','CAIXA','BRADESCO','SANTANDER','BANCO DO BRASIL','BNB','STONE','UNIVERSAL']

problems = []
for pdf in sorted(ORIG.glob('*.pdf')):
    stem = pdf.stem
    ofx = OUT / f"{stem}.ofx"
    # if ofx missing or zero bytes
    if not ofx.exists() or ofx.stat().st_size == 0:
        problems.append(pdf)

print('Found', len(problems), 'problem PDFs')
results = []
for pdf in problems:
    print('\nReprocessing', pdf.name)
    success = False
    last_err = None
    # try banks heuristically
    for b in BANKS:
        print(' - trying bank override:', b)
        ofx_path, err = converter_arquivo(str(pdf.resolve()), 'ofx', output_dir=str(OUT), usar_ocr=True, dpi=600, banco_override=b)
        if ofx_path and err is None:
            print('  -> success with', b, '->', ofx_path)
            results.append((pdf.name, b, ofx_path, None))
            success = True
            break
        else:
            print('  -> failed:', err)
            last_err = err
    if not success:
        # try without override as last resort
        print(' - trying without override')
        ofx_path, err = converter_arquivo(str(pdf.resolve()), 'ofx', output_dir=str(OUT), usar_ocr=True, dpi=600, banco_override=None)
        if ofx_path and err is None and Path(ofx_path).exists():
            print('  -> success without override ->', ofx_path)
            results.append((pdf.name, 'AUTO', ofx_path, None))
        else:
            print('  -> still failed:', err)
            results.append((pdf.name, None, None, last_err))

# write report
csv = OUT / 'fix_empty_ofx_report.csv'
with open(csv, 'w', encoding='utf-8') as f:
    f.write('pdf,forced_bank,ofx_path,error\n')
    for r in results:
        f.write(','.join([r[0], r[1] or '', r[2] or '', str(r[3] or '')]).replace('\n',' ') + '\n')

print('\nWrote report to', csv)
