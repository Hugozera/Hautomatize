# -*- coding: utf-8 -*-
"""
Converte PDF escaneado para TXT usando OCR (Tesseract + pdf2image)
Salva o resultado na mesma pasta com o mesmo nome + .txt
"""

import os
import sys
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

# Configurações (mude aqui se precisar)
IDIOMAS = 'por'          # 'por' ou 'por+eng' se tiver inglês misturado
DPI = 300                # 300 é bom equilíbrio. 200 = mais rápido, 400 = mais preciso
PSM = 6                  # 6 = bloco uniforme de texto. Tente 3 ou 4 se o resultado sair ruim


def extrair_texto_pdf(caminho_pdf):
    caminho_pdf = Path(caminho_pdf).resolve()
    
    if not caminho_pdf.is_file():
        print(f"Arquivo não encontrado: {caminho_pdf}")
        return None
    
    pasta = caminho_pdf.parent
    nome_base = caminho_pdf.stem
    caminho_txt = pasta / f"{nome_base}.txt"
    
    print(f"Processando: {caminho_pdf.name}")
    print(f" → Idioma: {IDIOMAS} | DPI: {DPI} | PSM: {PSM}")
    
    try:
        # Converte PDF → imagens
        imagens = convert_from_path(
            str(caminho_pdf),
            dpi=DPI,
            thread_count=os.cpu_count() or 4
        )
    except Exception as e:
        print(f"Erro ao converter PDF para imagens: {e}")
        print("Verifique se poppler-utils está instalado (necessário para pdf2image)")
        return None
    
    textos = []
    
    for i, img in enumerate(imagens, 1):
        print(f"  OCR página {i}/{len(imagens)}...", end=" ", flush=True)
        try:
            texto = pytesseract.image_to_string(
                img,
                lang=IDIOMAS,
                config=f'--psm {PSM}'
            )
            textos.append(f"\n\n--- Página {i} ---\n{texto.strip()}")
            print("OK")
        except Exception as e:
            print(f"Erro na página {i}: {e}")
    
    if not textos:
        print("Nenhum texto foi extraído.")
        return None
    
    texto_final = "\n".join(textos)
    
    # Salva
    try:
        with open(caminho_txt, "w", encoding="utf-8") as f:
            f.write(texto_final)
        print(f"\nConcluído! Arquivo salvo em:")
        print(f"  → {caminho_txt}")
        print(f"Tamanho: {len(texto_final):,} caracteres")
    except Exception as e:
        print(f"Erro ao salvar TXT: {e}")
        return None
    
    return caminho_txt


if __name__ == "__main__":
    # Você pode passar o caminho por argumento ou deixar fixo
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = r"C:\Hautomatize\PDFS\436-7 7.pdf"   # ← seu caminho
    
    extrair_texto_pdf(pdf_path)