import sys, os, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import conversor_pipeline
p = r"c:\Hautomatize\media\conversor\originais\STONE_AGOSTO_TODO.pdf"
print('Starting extract_text_pipeline (usar_ocr=True, dpi=300)')
try:
    start = time.time()
    txt = conversor_pipeline.extract_text_pipeline(p, usar_ocr=True, dpi=300, progress_path=None)
    took = time.time() - start
    print('Took', took, 'seconds')
    if not txt:
        print('No text returned')
    else:
        print('First 1000 chars:\n')
        print(txt[:1000])
except Exception as e:
    print('Exception:', e)
