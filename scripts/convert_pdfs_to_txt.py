import os
import sys
from pathlib import Path

try:
    from pdfminer.high_level import extract_text
except Exception:
    extract_text = None

try:
    from pdf2image import convert_from_path
    from PIL import Image
    import pytesseract
except Exception:
    convert_from_path = None


# Procedural script: percorre PDFS e gera arquivos .txt correspondentes
ROOT = Path(__file__).resolve().parent.parent
PDFS_DIR = ROOT / "PDFS"
OUT_DIR = PDFS_DIR / "txt"

if not PDFS_DIR.exists():
    print(f"Pasta não encontrada: {PDFS_DIR}")
    sys.exit(1)

OUT_DIR.mkdir(parents=True, exist_ok=True)

# Tenta detectar poppler bin automaticamente (opcional)
poppler_candidate = ROOT / "poppler-25.12.0" / "Library" / "bin"
poppler_path = str(poppler_candidate) if poppler_candidate.exists() else None

# Preferir tesseract instalado em Program Files se disponível
tesseract_candidates = [
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    Path("C:/Hautomatize/tesseract.exe")
]
tesseract_path = None
for p in tesseract_candidates:
    if p.exists():
        tesseract_path = str(p)
        break

if 'pytesseract' in globals() and tesseract_path:
    try:
        import pytesseract as _pyt
        _pyt.pytesseract.tesseract_cmd = tesseract_path
        pytesseract = _pyt
    except Exception:
        pass

count = 0
for root, dirs, files in os.walk(PDFS_DIR):
    for f in files:
        if not f.lower().endswith('.pdf'):
            continue
        pdf_path = Path(root) / f
        # cria caminho de saída preservando subpastas
        rel = pdf_path.relative_to(PDFS_DIR).with_suffix('.txt')
        txt_path = OUT_DIR / rel
        txt_path.parent.mkdir(parents=True, exist_ok=True)

        text = ''
        # tentativa com pdfminer
        if extract_text is not None:
            try:
                text = extract_text(str(pdf_path)) or ''
            except Exception as e:
                print(f"pdfminer falhou para {pdf_path}: {e}")

        # se vazio, tenta OCR página a página
        if (not text or not text.strip()) and convert_from_path is not None:
            try:
                images = convert_from_path(str(pdf_path), dpi=300, poppler_path=poppler_path) if poppler_path else convert_from_path(str(pdf_path), dpi=300)
                page_texts = []
                tmp_dir = OUT_DIR / 'tmp_images'
                tmp_dir.mkdir(parents=True, exist_ok=True)
                import subprocess
                for img_i, img in enumerate(images, start=1):
                    img_file = tmp_dir / f"{pdf_path.stem}_p{img_i}.png"
                    try:
                        img.save(img_file)
                    except Exception:
                        # fallback: convert to RGB and save
                        try:
                            img.convert('RGB').save(img_file)
                        except Exception as e:
                            print(f"Falha ao salvar imagem temporária {img_file}: {e}")
                            page_texts.append('')
                            continue

                    # determine tesseract executable
                    texe = None
                    if 'pytesseract' in globals():
                        try:
                            texe = pytesseract.pytesseract.tesseract_cmd
                        except Exception:
                            texe = None
                    if not texe and tesseract_path:
                        texe = tesseract_path

                    if not texe:
                        print('Nenhum tesseract disponível para OCR')
                        page_texts.append('')
                        continue

                    try:
                        proc = subprocess.run([texe, str(img_file), 'stdout', '-l', 'por+eng'], capture_output=True, text=True, timeout=60)
                        if proc.returncode == 0:
                            page_texts.append(f"--- Página {img_i} ---\n" + proc.stdout)
                        else:
                            print(f"tesseract retornou código {proc.returncode} para {img_file}")
                            page_texts.append('')
                    except subprocess.TimeoutExpired:
                        print(f"tesseract timeout em {img_file}")
                        page_texts.append('')
                    except Exception as e:
                        print(f"Erro ao rodar tesseract em {img_file}: {e}")
                        page_texts.append('')

                # opcional: remover imagens temporárias
                try:
                    for p in tmp_dir.iterdir():
                        try:
                            p.unlink()
                        except Exception:
                            pass
                except Exception:
                    pass

                text = '\n\n'.join(page_texts)
            except Exception as e:
                print(f"OCR falhou para {pdf_path}: {e}")

        # Se ainda vazio, escrevemos nota para o arquivo para evitar perda de referência
        if not text:
            note = f"=== Sem texto extraído de {pdf_path.name} ===\n"
            text = note

        # salvar com codificação utf-8
        try:
            with open(txt_path, 'w', encoding='utf-8') as out:
                out.write(text)
            count += 1
            print(f"Convertido: {pdf_path} -> {txt_path}")
        except Exception as e:
            print(f"Falha ao salvar {txt_path}: {e}")

print(f"Concluído. Arquivos convertidos: {count}. Saída em: {OUT_DIR}")
