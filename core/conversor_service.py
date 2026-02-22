import os
import re
import subprocess
import tempfile
import zipfile
import shutil
import glob
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

# Bibliotecas para OCR
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image, ImageEnhance, ImageFilter
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

# PyMuPDF para extração rápida
try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

class ConversorService:
    # Configuração dos paths
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    POPPLER_PATH = os.path.join(PROJECT_ROOT, 'poppler-25.12.0', 'Library', 'bin')
    TESSERACT_CMD = os.path.join(PROJECT_ROOT, 'tesseract.exe')
    TESSDATA_PREFIX = os.path.join(PROJECT_ROOT, 'tessdata')
    
    # Configurar environment
    os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX
    if os.path.exists(POPPLER_PATH):
        os.environ['PATH'] = POPPLER_PATH + os.pathsep + os.environ.get('PATH', '')
    
    # Cache para performance
    _cache = {}
    
    # Configurações de performance
    MAX_WORKERS = multiprocessing.cpu_count()
    OCR_DPI = 200
    
    # Formatos suportados
    FORMATOS_SUPORTADOS = {
        'pdf': ['ofx', 'txt', 'html', 'xml', 'csv', 'jpg', 'png', 'zip'],
        'ofx': ['pdf', 'txt', 'csv', 'xml', 'html', 'zip'],
        'txt': ['pdf', 'ofx', 'html', 'xml', 'csv', 'zip'],
        'csv': ['ofx', 'pdf', 'txt', 'xml', 'html', 'zip'],
        'xml': ['ofx', 'pdf', 'txt', 'html', 'csv', 'zip'],
        'jpg': ['pdf', 'png', 'ofx', 'txt', 'zip'],
        'jpeg': ['pdf', 'png', 'ofx', 'txt', 'zip'],
        'png': ['pdf', 'jpg', 'ofx', 'txt', 'zip'],
        'zip': ['*'],  # * significa extrair todos os formatos internos
    }
    
    @classmethod
    def get_formatos_destino(cls, formato_origem):
        """Retorna formatos disponíveis para conversão"""
        formato_origem = formato_origem.lower().replace('.', '')
        
        # Mapeamento de formatos
        formatos = {
            'pdf': ['ofx', 'txt', 'html', 'xml', 'csv', 'jpg', 'png', 'zip'],
            'ofx': ['pdf', 'txt', 'csv', 'xml', 'html', 'zip'],
            'txt': ['pdf', 'ofx', 'html', 'xml', 'csv', 'zip'],
            'csv': ['ofx', 'pdf', 'txt', 'xml', 'html', 'zip'],
            'xml': ['ofx', 'pdf', 'txt', 'html', 'csv', 'zip'],
            'jpg': ['pdf', 'png', 'ofx', 'txt', 'zip'],
            'jpeg': ['pdf', 'png', 'ofx', 'txt', 'zip'],
            'png': ['pdf', 'jpg', 'ofx', 'txt', 'zip'],
            'zip': ['pdf', 'ofx', 'txt', 'html', 'xml', 'csv', 'jpg', 'png'],  # ← CORRIGIDO
        }
        
        return formatos.get(formato_origem, ['ofx', 'pdf', 'txt', 'zip'])

    @classmethod
    def _extrair_texto_pdf_rapido(cls, pdf_path):
        """Versão ULTRA RÁPIDA de extração de texto"""
        if pdf_path in cls._cache:
            return cls._cache[pdf_path]
        
        texto = ""
        
        # ESTRATÉGIA 1: PyMuPDF (mais rápido para PDFs com texto)
        if HAS_FITZ:
            try:
                doc = fitz.open(pdf_path)
                for page in doc:
                    texto += page.get_text() + "\n"
                doc.close()
                if texto.strip() and len(texto) > 100:
                    print(f"⚡ PyMuPDF extraiu {len(texto)} caracteres")
                    cls._cache[pdf_path] = texto
                    return texto
            except:
                pass
        
        # ESTRATÉGIA 2: pdftotext
        try:
            pdftotext_cmd = os.path.join(cls.POPPLER_PATH, 'pdftotext.exe')
            if os.path.exists(pdftotext_cmd):
                result = subprocess.run(
                    [pdftotext_cmd, '-layout', '-nopgbrk', pdf_path, '-'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    texto = result.stdout
                    if len(texto) > 100:
                        print(f"⚡ pdftotext extraiu {len(texto)} caracteres")
                        cls._cache[pdf_path] = texto
                        return texto
        except:
            pass
        
        # ESTRATÉGIA 3: OCR PARALELO
        if HAS_OCR:
            try:
                print(f"🚀 OCR paralelo com {cls.MAX_WORKERS} threads...")
                
                if os.path.exists(cls.TESSERACT_CMD):
                    pytesseract.pytesseract.tesseract_cmd = cls.TESSERACT_CMD
                
                imagens = convert_from_path(
                    pdf_path,
                    dpi=cls.OCR_DPI,
                    poppler_path=cls.POPPLER_PATH,
                    fmt='jpeg',
                    thread_count=cls.MAX_WORKERS
                )
                
                print(f"📸 {len(imagens)} imagens (DPI {cls.OCR_DPI})")
                
                textos_por_pagina = [None] * len(imagens)
                
                with ThreadPoolExecutor(max_workers=cls.MAX_WORKERS) as executor:
                    futures = {}
                    for i, img in enumerate(imagens):
                        future = executor.submit(cls._processar_imagem_rapido, img, i)
                        futures[future] = i
                    
                    for future in as_completed(futures):
                        i, texto_pagina = future.result()
                        textos_por_pagina[i] = texto_pagina
                
                for texto_pagina in textos_por_pagina:
                    if texto_pagina:
                        texto += texto_pagina + "\n"
                
                if texto.strip():
                    print(f"✅ OCR: {len(texto)} caracteres")
                    cls._cache[pdf_path] = texto
                    return texto
                    
            except Exception as e:
                print(f"⚠️ OCR erro: {e}")
        
        cls._cache[pdf_path] = texto
        return texto
    
    @classmethod
    def _processar_imagem_rapido(cls, img, index):
        """Processa imagem para OCR"""
        try:
            img_gray = img.convert('L')
            enhancer = ImageEnhance.Contrast(img_gray)
            img_enhanced = enhancer.enhance(1.5)
            
            texto = pytesseract.image_to_string(
                img_enhanced,
                lang='por',
                config='--psm 6 --oem 3'
            )
            
            return index, texto
        except:
            return index, ""
    
    @classmethod
    def _extrair_transacoes_rapido(cls, texto):
        """Extrai transações de qualquer extrato"""
        transacoes = []
        
        # Padrões universais
        padrao_data = re.compile(r'(\d{2}/\d{2}(?:/\d{4})?)')
        padrao_valor = re.compile(r'([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})')
        
        linhas = texto.split('\n')
        ano_atual = datetime.now().year
        
        for linha in linhas:
            linha = linha.strip()
            if not linha or len(linha) < 10:
                continue
            
            data_match = padrao_data.search(linha)
            if not data_match:
                continue
            
            valor_match = padrao_valor.search(linha)
            if not valor_match:
                continue
            
            try:
                data_str = data_match.group(1)
                valor_str = valor_match.group(1)
                
                # Data
                if len(data_str) == 10:
                    data_obj = datetime.strptime(data_str, '%d/%m/%Y')
                else:
                    data_obj = datetime.strptime(f"{data_str}/{ano_atual}", '%d/%m/%Y')
                
                data_ofx = data_obj.strftime('%Y%m%d')
                
                # Valor
                valor = float(valor_str.replace('.', '').replace(',', '.'))
                
                # Descrição
                descricao = linha
                descricao = descricao.replace(data_str, '')
                descricao = descricao.replace(valor_str, '')
                descricao = re.sub(r'[R$\s]', ' ', descricao)
                descricao = re.sub(r'[+-]', '', descricao)
                descricao = re.sub(r'\s+', ' ', descricao).strip()
                
                if descricao and abs(valor) > 0.01:
                    transacoes.append({
                        'data': data_ofx,
                        'valor': valor,
                        'descricao': descricao[:80]
                    })
            except:
                continue
        
        return transacoes
    
    @classmethod
    def _gerar_ofx(cls, transacoes, ofx_path):
        """Gera arquivo OFX"""
        try:
            with open(ofx_path, 'w', encoding='utf-8') as f:
                f.write('OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\n')
                f.write('SECURITY:NONE\nENCODING:USASCII\nCHARSET:1252\n')
                f.write('COMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n')
                
                f.write('<OFX>\n<SIGNONMSGSRSV1>\n<SONRS>\n<STATUS>\n')
                f.write('<CODE>0\n<SEVERITY>INFO\n</STATUS>\n')
                f.write(f'<DTSERVER>{datetime.now().strftime("%Y%m%d%H%M%S")}\n')
                f.write('<LANGUAGE>POR\n</SONRS>\n</SIGNONMSGSRSV1>\n')
                f.write('<BANKMSGSRSV1>\n<STMTTRNRS>\n<STMTRS>\n')
                f.write('<CURDEF>BRL\n<BANKTRANLIST>\n')
                
                for t in transacoes:
                    f.write('<STMTTRN>\n<TRNTYPE>OTHER\n')
                    f.write(f'<DTPOSTED>{t["data"]}\n')
                    f.write(f'<TRNAMT>{t["valor"]:.2f}\n')
                    f.write(f'<FITID>{t["data"]}{abs(int(t["valor"]*100))}\n')
                    f.write(f'<NAME>{t["descricao"]}\n</STMTTRN>\n')
                
                f.write('</BANKTRANLIST>\n</STMTRS>\n</STMTTRNRS>\n')
                f.write('</BANKMSGSRSV1>\n</OFX>\n')
            
            return True
        except:
            return False
    
    @classmethod
    def _gerar_txt(cls, texto, txt_path):
        """Gera arquivo TXT"""
        try:
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(texto)
            return True
        except:
            return False
    
    @classmethod
    def _gerar_html(cls, texto, html_path, titulo="Documento Convertido"):
        """Gera arquivo HTML"""
        try:
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{titulo}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        pre {{ background: #f5f5f5; padding: 10px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h2>{titulo}</h2>
    <pre>{texto}</pre>
</body>
</html>"""
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)
            return True
        except:
            return False
    
    @classmethod
    def _gerar_xml(cls, transacoes, xml_path):
        """Gera arquivo XML"""
        try:
            import xml.etree.ElementTree as ET
            
            root = ET.Element("extrato")
            root.set("data", datetime.now().strftime("%Y-%m-%d"))
            
            transacoes_elem = ET.SubElement(root, "transacoes")
            
            for t in transacoes:
                t_elem = ET.SubElement(transacoes_elem, "transacao")
                ET.SubElement(t_elem, "data").text = t['data']
                ET.SubElement(t_elem, "valor").text = f"{t['valor']:.2f}"
                ET.SubElement(t_elem, "descricao").text = t['descricao']
            
            xml_str = ET.tostring(root, encoding='unicode')
            
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(xml_str)
            
            return True
        except:
            return False
    
    @classmethod
    def _gerar_csv(cls, transacoes, csv_path):
        """Gera arquivo CSV"""
        try:
            with open(csv_path, 'w', encoding='utf-8') as f:
                f.write("Data,Valor,Descricao\n")
                for t in transacoes:
                    f.write(f"{t['data']},{t['valor']:.2f},\"{t['descricao']}\"\n")
            return True
        except:
            return False
    
    @classmethod
    def _gerar_imagem(cls, pdf_path, img_path, formato='jpeg'):
        """Converte PDF para imagem"""
        try:
            imagens = convert_from_path(
                pdf_path,
                dpi=150,
                poppler_path=cls.POPPLER_PATH,
                fmt=formato,
                first_page=1,
                last_page=1
            )
            if imagens:
                imagens[0].save(img_path, formato.upper())
                return True
            return False
        except:
            return False
    
    @classmethod
    def _processar_zip(cls, zip_path, output_dir):
        """Processa arquivo ZIP"""
        try:
            resultados = []
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(zip_path, 'r') as z:
                    z.extractall(temp_dir)
                
                for arquivo in glob.glob(os.path.join(temp_dir, '*')):
                    if os.path.isfile(arquivo):
                        ext = os.path.splitext(arquivo)[1].lower().replace('.', '')
                        if ext in cls.FORMATOS_SUPORTADOS:
                            resultado, erro = cls.converter(arquivo, 'ofx', temp_dir)
                            if resultado:
                                resultados.append(resultado)
                
                if resultados:
                    zip_out = os.path.join(output_dir, f"convertidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
                    with zipfile.ZipFile(zip_out, 'w') as z2:
                        for res in resultados:
                            z2.write(res, os.path.basename(res))
                    return zip_out, None
                return None, "Nenhum arquivo convertido no ZIP"
        except Exception as e:
            return None, str(e)
    
    @classmethod
    def converter(cls, arquivo_path, formato_destino, output_dir=None):
        """Converte qualquer arquivo para qualquer formato"""
        if not os.path.exists(arquivo_path):
            return None, "Arquivo não encontrado"
        
        if not output_dir:
            output_dir = os.path.dirname(arquivo_path)
        
        os.makedirs(output_dir, exist_ok=True)
        
        formato_origem = os.path.splitext(arquivo_path)[1].lower().replace('.', '')
        nome_base = os.path.splitext(os.path.basename(arquivo_path))[0]
        output_path = os.path.join(output_dir, f"{nome_base}.{formato_destino}")
        
        # Processar ZIP
        if formato_origem == 'zip':
            return cls._processar_zip(arquivo_path, output_dir)
        
        # PDF para outros formatos
        if formato_origem == 'pdf':
            texto = cls._extrair_texto_pdf_rapido(arquivo_path)
            transacoes = cls._extrair_transacoes_rapido(texto) if texto else []
            
            if formato_destino == 'ofx':
                if not transacoes:
                    return None, "Nenhuma transação encontrada"
                if cls._gerar_ofx(transacoes, output_path):
                    return output_path, None
                
            elif formato_destino == 'txt':
                if cls._gerar_txt(texto, output_path):
                    return output_path, None
                
            elif formato_destino == 'html':
                if cls._gerar_html(texto, output_path, f"Extrato {nome_base}"):
                    return output_path, None
                
            elif formato_destino == 'xml':
                if transacoes and cls._gerar_xml(transacoes, output_path):
                    return output_path, None
                
            elif formato_destino == 'csv':
                if transacoes and cls._gerar_csv(transacoes, output_path):
                    return output_path, None
                
            elif formato_destino in ['jpg', 'jpeg', 'png']:
                if cls._gerar_imagem(arquivo_path, output_path, formato_destino):
                    return output_path, None
                
            elif formato_destino == 'zip':
                # Criar ZIP com múltiplos formatos
                zip_path = os.path.join(output_dir, f"{nome_base}_completo.zip")
                with zipfile.ZipFile(zip_path, 'w') as zf:
                    # TXT
                    txt_path = os.path.join(output_dir, f"{nome_base}.txt")
                    if cls._gerar_txt(texto, txt_path):
                        zf.write(txt_path, os.path.basename(txt_path))
                        os.remove(txt_path)
                    
                    # OFX
                    if transacoes:
                        ofx_path = os.path.join(output_dir, f"{nome_base}.ofx")
                        if cls._gerar_ofx(transacoes, ofx_path):
                            zf.write(ofx_path, os.path.basename(ofx_path))
                            os.remove(ofx_path)
                        
                        # XML
                        xml_path = os.path.join(output_dir, f"{nome_base}.xml")
                        if cls._gerar_xml(transacoes, xml_path):
                            zf.write(xml_path, os.path.basename(xml_path))
                            os.remove(xml_path)
                        
                        # CSV
                        csv_path = os.path.join(output_dir, f"{nome_base}.csv")
                        if cls._gerar_csv(transacoes, csv_path):
                            zf.write(csv_path, os.path.basename(csv_path))
                            os.remove(csv_path)
                    
                    # HTML
                    html_path = os.path.join(output_dir, f"{nome_base}.html")
                    if cls._gerar_html(texto, html_path, f"Extrato {nome_base}"):
                        zf.write(html_path, os.path.basename(html_path))
                        os.remove(html_path)
                    
                    # JPG
                    jpg_path = os.path.join(output_dir, f"{nome_base}.jpg")
                    if cls._gerar_imagem(arquivo_path, jpg_path):
                        zf.write(jpg_path, os.path.basename(jpg_path))
                        os.remove(jpg_path)
                
                return zip_path, None
            
            return None, f"Falha ao converter para {formato_destino}"
        
        # OFX para outros formatos
        elif formato_origem == 'ofx':
            try:
                with open(arquivo_path, 'r', encoding='utf-8') as f:
                    conteudo = f.read()
                
                transacoes = cls._extrair_transacoes_rapido(conteudo)
                
                if formato_destino == 'txt':
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(conteudo)
                    return output_path, None
                    
                elif formato_destino == 'csv' and transacoes:
                    if cls._gerar_csv(transacoes, output_path):
                        return output_path, None
                        
                elif formato_destino == 'xml' and transacoes:
                    if cls._gerar_xml(transacoes, output_path):
                        return output_path, None
                        
                elif formato_destino == 'html':
                    if cls._gerar_html(conteudo, output_path, "OFX Convertido"):
                        return output_path, None
                        
            except Exception as e:
                return None, str(e)
        
        # TXT para outros formatos
        elif formato_origem == 'txt':
            try:
                with open(arquivo_path, 'r', encoding='utf-8') as f:
                    texto = f.read()
                
                transacoes = cls._extrair_transacoes_rapido(texto)
                
                if formato_destino == 'ofx' and transacoes:
                    if cls._gerar_ofx(transacoes, output_path):
                        return output_path, None
                        
                elif formato_destino == 'html':
                    if cls._gerar_html(texto, output_path):
                        return output_path, None
                        
                elif formato_destino == 'xml' and transacoes:
                    if cls._gerar_xml(transacoes, output_path):
                        return output_path, None
                        
                elif formato_destino == 'csv' and transacoes:
                    if cls._gerar_csv(transacoes, output_path):
                        return output_path, None
                        
            except Exception as e:
                return None, str(e)
        
        # Imagens para outros formatos
        elif formato_origem in ['jpg', 'jpeg', 'png']:
            try:
                if formato_destino == 'pdf':
                    img = Image.open(arquivo_path)
                    img.save(output_path, 'PDF')
                    return output_path, None
                    
                elif formato_destino in ['jpg', 'jpeg', 'png']:
                    img = Image.open(arquivo_path)
                    img.save(output_path)
                    return output_path, None
                    
                elif formato_destino == 'ofx' and HAS_OCR:
                    if os.path.exists(cls.TESSERACT_CMD):
                        pytesseract.pytesseract.tesseract_cmd = cls.TESSERACT_CMD
                    
                    img = Image.open(arquivo_path)
                    texto = pytesseract.image_to_string(img, lang='por')
                    transacoes = cls._extrair_transacoes_rapido(texto)
                    
                    if transacoes and cls._gerar_ofx(transacoes, output_path):
                        return output_path, None
                        
            except Exception as e:
                return None, str(e)
        
        return None, f"Conversão de {formato_origem} para {formato_destino} não suportada"

# Funções de interface
def converter_arquivo(arquivo_path, formato_destino, output_dir=None):
    return ConversorService.converter(arquivo_path, formato_destino, output_dir)

def get_formatos_destino(formato_origem):
    return ConversorService.get_formatos_destino(formato_origem)