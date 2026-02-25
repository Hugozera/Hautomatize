import subprocess
from pathlib import Path
import traceback

pdf = Path('PDFS') / '436-7 7.pdf'
print('PDF exists:', pdf.exists())

from pdf2image import convert_from_path
poppler_candidate = Path(__file__).resolve().parent.parent / 'poppler-25.12.0' / 'Library' / 'bin'
poppler_path = str(poppler_candidate) if poppler_candidate.exists() else None
print('poppler_path:', poppler_path)

images = convert_from_path(str(pdf), dpi=200, poppler_path=poppler_path) if poppler_path else convert_from_path(str(pdf), dpi=200)
print('Rendered pages:', len(images))
img = images[0]
tmp = Path('tmp')
tmp.mkdir(exist_ok=True)
img_path = tmp / 'page1.png'
img.save(img_path)
print('Saved image:', img_path)

# try calling tesseract.exe directly
tesseract_candidates = [Path('C:/Hautomatize/tesseract.exe'), Path('C:/Program Files/Tesseract-OCR/tesseract.exe'), Path('C:/Program Files (x86)/Tesseract-OCR/tesseract.exe')]
found = [p for p in tesseract_candidates if p.exists()]
print('tesseract candidates found:', found)
if not found:
    try:
        out = subprocess.run(['tesseract','--version'], capture_output=True, text=True)
        print('tesseract in PATH --version exit', out.returncode)
        print('stdout:', out.stdout)
        print('stderr:', out.stderr)
    except Exception as e:
        print('tesseract not found in PATH and candidates missing')
else:
    exe = str(found[0])
    print('Using exe:', exe)
    try:
        # attempt version
        out = subprocess.run([exe,'--version'], capture_output=True, text=True)
        print('--version exit', out.returncode)
        print('stdout:', out.stdout)
        print('stderr:', out.stderr)
    except Exception as e:
        print('Failed to run --version')
        traceback.print_exc()
    try:
        # run tesseract to stdout
        out = subprocess.run([exe, str(img_path), 'stdout', '-l', 'por+eng'], capture_output=True, text=True)
        print('tesseract OCR exit', out.returncode)
        print('stdout len:', len(out.stdout))
        print('stderr len:', len(out.stderr))
        print('stderr preview:', repr(out.stderr)[:1000])
    except Exception as e:
        print('Failed calling tesseract on image')
        traceback.print_exc()
