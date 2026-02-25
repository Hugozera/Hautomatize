import os
import sys

# Ensure Django settings are loaded
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')

from core.conversor_service import converter_arquivo

INPUT = r'PDFS/txt/436-7 7.txt'
OUTPUT_DIR = r'PDFS/service_out'

if __name__ == '__main__':
    print('Input:', INPUT)
    result = converter_arquivo(INPUT, 'ofx', output_dir=OUTPUT_DIR, usar_ocr=False)
    print('Result:', result)
