
import glob
import os
import sys
# Garante que o diretório raiz do projeto esteja no sys.path ANTES da importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.conversor_service import converter_arquivo

pdf_dir = 'PDFS'
pdfs = glob.glob(os.path.join(pdf_dir, '*.pdf'))
results = {}
print('Testando conversão de todos os PDFs para OFX...')
for pdf in pdfs:
    ofx_path, err = converter_arquivo(pdf, 'ofx', output_dir=pdf_dir)
    print(f'{os.path.basename(pdf)}: erro={err}, ofx={ofx_path}')
    results[os.path.basename(pdf)] = {'ofx': ofx_path, 'erro': err}
print('\nResumo:')
for nome, res in results.items():
    print(f'{nome}: {res}')
