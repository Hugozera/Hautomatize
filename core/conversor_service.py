# C:\Hautomatize\core\conversor_service.py

import os
import re
import subprocess
import zipfile
import tempfile
from datetime import datetime
import multiprocessing

# Tentativa de importar bibliotecas opcionais
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    import pytesseract
    from pdf2image import convert_from_path, pdfinfo_from_path
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


class ConversorService:
    # CORREÇÃO: Root do projeto é C:\Hautomatize
    PROJECT_ROOT = r"C:\Hautomatize"  # Caminho absoluto fixo
    POPPLER_PATH = os.path.join(PROJECT_ROOT, 'poppler-25.12.0', 'Library', 'bin')
    TESSERACT_CMD = os.path.join(PROJECT_ROOT, 'Tesseract-OCR', 'tesseract.exe')
    TESSDATA_PREFIX = os.path.join(PROJECT_ROOT, 'tessdata')

    if os.path.exists(POPPLER_PATH):
        # Adiciona ao PATH de várias formas para garantir
        os.environ['PATH'] = POPPLER_PATH + os.pathsep + os.environ.get('PATH', '')
    try:
        os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX
    except Exception:
        pass

    OCR_DPI = 200
    MAX_WORKERS = multiprocessing.cpu_count()

    FORMATOS_SUPORTADOS = {
        'pdf': ['ofx', 'txt', 'html', 'xml', 'csv', 'jpg', 'png', 'zip'],
        'ofx': ['pdf', 'txt', 'csv', 'xml', 'html', 'zip'],
        'txt': ['pdf', 'ofx', 'html', 'xml', 'csv', 'zip'],
        'csv': ['ofx', 'pdf', 'txt', 'xml', 'html', 'zip'],
        'xml': ['ofx', 'pdf', 'txt', 'html', 'csv', 'zip'],
        'jpg': ['pdf', 'png', 'ofx', 'txt', 'zip'],
        'jpeg': ['pdf', 'png', 'ofx', 'txt', 'zip'],
        'png': ['pdf', 'jpg', 'ofx', 'txt', 'zip'],
        'zip': ['*'],
    }

    @classmethod
    def get_formatos_destino(cls, formato_origem):
        return cls.FORMATOS_SUPORTADOS.get(
            (formato_origem or '').lower().replace('.', ''), 
            ['ofx', 'pdf', 'txt', 'zip']
        )

    @classmethod
    def _extrair_texto_pdf_rapido(cls, pdf_path):
        """Extrai texto do PDF tentando PyMuPDF, depois pdftotext e por fim OCR.
        Mantemos os parâmetros de OCR/geração de imagens sem alterações de performance."""
        texto = ''

        # 1) PyMuPDF
        if HAS_FITZ:
            try:
                doc = fitz.open(pdf_path)
                partes = []
                for p in doc:
                    partes.append(p.get_text())
                doc.close()
                texto = '\n'.join(partes)
                if texto.strip():
                    return texto
            except Exception:
                pass

        # 2) pdftotext (poppler)
        try:
            pdftotext_cmd = os.path.join(cls.POPPLER_PATH, 'pdftotext.exe')
            if os.path.exists(pdftotext_cmd):
                r = subprocess.run([pdftotext_cmd, '-layout', '-nopgbrk', pdf_path, '-'], capture_output=True, text=True, timeout=20)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout
        except Exception:
            pass

        # 3) OCR (só se as bibliotecas existirem)
        if HAS_OCR:
            try:
                if os.path.exists(cls.TESSERACT_CMD):
                    pytesseract.pytesseract.tesseract_cmd = cls.TESSERACT_CMD

                imagens = convert_from_path(pdf_path, dpi=cls.OCR_DPI, poppler_path=cls.POPPLER_PATH, fmt='jpeg', thread_count=cls.MAX_WORKERS)
                partes = []
                for img in imagens:
                    try:
                        partes.append(pytesseract.image_to_string(img, lang='por'))
                    except Exception:
                        partes.append('')
                texto = '\n'.join(partes)
                return texto
            except Exception:
                pass

        return texto

    @classmethod
    def _extrair_transacoes_rapido(cls, texto):
        """Heurística simples para extrair data, valor e descrição de extratos.
        Não é perfeita mas serve para decidir se houve transações."""
        if not texto:
            return []

        padrao_data = re.compile(r"(\d{2}/\d{2}(?:/\d{4})?)")
        padrao_valor = re.compile(r"([+-]?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))")

        linhas = [l.strip() for l in texto.splitlines() if l.strip()]
        transacoes = []
        ano_atual = datetime.now().year
        last_date = None
        last_desc = ''

        for i, linha in enumerate(linhas):
            if not linha:
                continue
            dm = padrao_data.search(linha)
            vm = padrao_valor.search(linha)

            if dm:
                last_date = dm.group(1)
                rest = padrao_data.sub('', linha).strip()
                rest = padrao_valor.sub('', rest).strip()
                if rest:
                    last_desc = rest
                continue

            if vm:
                valor = vm.group(1)
                data_str = last_date
                if not data_str:
                    # procurar para trás algumas linhas
                    for j in range(1, 6):
                        if i - j < 0:
                            break
                        pm = padrao_data.search(linhas[i - j])
                        if pm:
                            data_str = pm.group(1)
                            break
                if not data_str:
                    continue

                descricao = last_desc or ''
                if not descricao:
                    for j in range(1, 6):
                        if i - j < 0:
                            break
                        if not padrao_valor.search(linhas[i - j]) and not linhas[i - j].isdigit():
                            descricao = linhas[i - j]
                            break

                try:
                    if '/' in data_str and len(data_str) == 10:
                        dobj = datetime.strptime(data_str, '%d/%m/%Y')
                    else:
                        dobj = datetime.strptime(f"{data_str}/{ano_atual}", '%d/%m/%Y')
                except Exception:
                    continue

                try:
                    v = float(valor.replace('.', '').replace(',', '.'))
                except Exception:
                    continue

                desc = re.sub(r'[R$\s]', ' ', descricao or '')
                desc = re.sub(r'[+-]', '', desc)
                desc = re.sub(r'\s+', ' ', desc).strip()

                if desc and abs(v) > 0.01:
                    transacoes.append({'data': dobj.strftime('%Y%m%d'), 'valor': v, 'descricao': desc[:120]})

                last_desc = ''
                continue

            if len(linha) > 3 and not padrao_valor.search(linha) and not linha.isdigit():
                last_desc = linha

        return transacoes

    @classmethod
    def _gerar_ofx(cls, transacoes, ofx_path):
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
        except Exception:
            return False

    @classmethod
    def _gerar_txt(cls, texto, txt_path):
        try:
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(texto)
            return True
        except Exception:
            return False

    @classmethod
    def converter(cls, arquivo_path, formato_destino, output_dir=None):
        """Conversor mínimo com fallback PDF->TXT->OFX somente quando não houver transacoes."""
        if not os.path.exists(arquivo_path):
            return None, 'Arquivo não encontrado'

        if not output_dir:
            output_dir = os.path.dirname(arquivo_path)
        os.makedirs(output_dir, exist_ok=True)

        formato_origem = os.path.splitext(arquivo_path)[1].lower().replace('.', '')
        nome_base = os.path.splitext(os.path.basename(arquivo_path))[0]
        output_path = os.path.join(output_dir, f"{nome_base}.{formato_destino}")

        # ZIP de origem: extrai e processa cada arquivo internamente
        if formato_origem == 'zip':
            try:
                resultados = []
                with tempfile.TemporaryDirectory() as temp_dir:
                    with zipfile.ZipFile(arquivo_path, 'r') as z:
                        z.extractall(temp_dir)

                    # procurar arquivos extraídos
                    for root, _, files in os.walk(temp_dir):
                        for f in files:
                            arquivo_interno = os.path.join(root, f)
                            ext = os.path.splitext(f)[1].lower().replace('.', '')
                            if ext in cls.FORMATOS_SUPORTADOS:
                                res, err = cls.converter(arquivo_interno, formato_destino, temp_dir)
                                if res:
                                    resultados.append(res)

                    if not resultados:
                        return None, 'Nenhum arquivo convertido no ZIP'

                    # Se apenas um resultado e o usuário pediu um formato simples, retorne-o
                    if len(resultados) == 1 and formato_destino != 'zip':
                        return resultados[0], None

                    # Caso contrário, empacotar resultados em um ZIP para download
                    zip_out = os.path.join(output_dir, f"{nome_base}_convertidos.zip")
                    with zipfile.ZipFile(zip_out, 'w') as zf:
                        for r in resultados:
                            if os.path.exists(r):
                                zf.write(r, os.path.basename(r))
                    return zip_out, None
            except Exception as e:
                return None, str(e)

        # Tratamento PDF
        if formato_origem == 'pdf':
            texto = cls._extrair_texto_pdf_rapido(arquivo_path)
            transacoes = cls._extrair_transacoes_rapido(texto) if texto else []

            if formato_destino == 'ofx':
                # Se conseguimos extrair transacoes já geramos OFX
                if transacoes and cls._gerar_ofx(transacoes, output_path):
                    return output_path, None

                # Fallback mínimo: gerar TXT intermediário e tentar extrair novamente
                try:
                    txt_tmp = os.path.join(output_dir, f"{nome_base}_intermediario.txt")
                    if texto and cls._gerar_txt(texto, txt_tmp):
                        with open(txt_tmp, 'r', encoding='utf-8', errors='ignore') as f:
                            txt_conteudo = f.read()
                        trans_txt = cls._extrair_transacoes_rapido(txt_conteudo)
                        if trans_txt and cls._gerar_ofx(trans_txt, output_path):
                            try:
                                os.remove(txt_tmp)
                            except Exception:
                                pass
                            return output_path, None
                        try:
                            os.remove(txt_tmp)
                        except Exception:
                            pass
                except Exception as e:
                    # Não interromper o fluxo principal
                    print(f'Fallback PDF->TXT falhou: {e}')

                return None, 'Nenhuma transação encontrada'

            if formato_destino == 'txt':
                if cls._gerar_txt(texto, output_path):
                    return output_path, None

            if formato_destino == 'zip':
                try:
                    zip_path = os.path.join(output_dir, f"{nome_base}_completo.zip")
                    with zipfile.ZipFile(zip_path, 'w') as zf:
                        # TXT
                        txt_path = os.path.join(output_dir, f"{nome_base}.txt")
                        if cls._gerar_txt(texto, txt_path):
                            zf.write(txt_path, os.path.basename(txt_path))
                            try:
                                os.remove(txt_path)
                            except Exception:
                                pass

                        # OFX
                        if transacoes:
                            ofx_path = os.path.join(output_dir, f"{nome_base}.ofx")
                            if cls._gerar_ofx(transacoes, ofx_path):
                                zf.write(ofx_path, os.path.basename(ofx_path))
                                try:
                                    os.remove(ofx_path)
                                except Exception:
                                    pass

                    return zip_path, None
                except Exception as e:
                    return None, str(e)

            # outros formatos básicos: se transacoes existem, gerar xml/csv/ofx conforme pedido
            if formato_destino == 'xml' and transacoes:
                if cls._gerar_xml(transacoes, output_path):
                    return output_path, None

            if formato_destino == 'csv' and transacoes:
                if cls._gerar_csv(transacoes, output_path):
                    return output_path, None

            return None, f'Falha ao converter para {formato_destino}'

        # TXT
        if formato_origem == 'txt':
            try:
                with open(arquivo_path, 'r', encoding='utf-8') as f:
                    texto = f.read()
                transacoes = cls._extrair_transacoes_rapido(texto)
                if formato_destino == 'ofx' and transacoes:
                    if cls._gerar_ofx(transacoes, output_path):
                        return output_path, None
                if formato_destino == 'html':
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(texto)
                    return output_path, None
            except Exception as e:
                return None, str(e)

        # Para outros formatos (ofx, imagens, zip etc) manter comportamento padrão mínimo
        if formato_origem == 'ofx':
            # apenas salvar como txt/html se solicitado
            try:
                with open(arquivo_path, 'r', encoding='utf-8') as f:
                    conteudo = f.read()
                if formato_destino == 'txt':
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(conteudo)
                    return output_path, None
            except Exception as e:
                return None, str(e)

        return None, f'Conversão de {formato_origem} para {formato_destino} não suportada'


# Funções de interface

def converter_arquivo(arquivo_path, formato_destino, output_dir=None):
    return ConversorService.converter(arquivo_path, formato_destino, output_dir)


def get_formatos_destino(formato_origem):
    return ConversorService.get_formatos_destino(formato_origem)
