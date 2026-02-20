
import os
import re
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

# Tenta importar bibliotecas opcionais
try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except ImportError:
    try:
        from pypdf import PdfReader
        HAS_PYPDF2 = True
    except ImportError:
        HAS_PYPDF2 = False

# Novo: tenta importar pdfminer.six para fallback
try:
    from pdfminer.high_level import extract_text as pdfminer_extract_text
    HAS_PDFMINER = True
except ImportError:
    HAS_PDFMINER = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# project root for bundled utilities
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
POPPLER_PATH = PROJECT_ROOT  # if poppler exes reside here

# OCR: tenta importar pytesseract/pdf2image
try:
    import pytesseract
    from pdf2image import convert_from_path
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
"""
Serviço de conversão de arquivos integrado ao HDowloader
Suporte especial para PDF → OFX
"""
class ConversorService:
    # Caminho do tesseract (ajuste conforme necessário)
    # Tesseract executable (installed location)
    TESSERACT_CMD = r'C:\Users\Player\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

    """Serviço para conversão de arquivos"""

    @classmethod
    def _converter_txt_para_ofx(cls, txt_path, ofx_path):
        """Converte extrato TXT para OFX (usando o mesmo parser de texto do PDF)"""
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                texto = f.read()
            transacoes = cls._extrair_transacoes(texto)
            if not transacoes:
                return None, "Nenhuma transação encontrada no TXT"
            sucesso = cls._gerar_ofx(transacoes, ofx_path)
            if sucesso:
                return ofx_path, None
            else:
                return None, "Erro ao gerar arquivo OFX"
        except Exception as e:
            return None, f"Erro na conversão TXT→OFX: {str(e)}"
    
    # Formatos suportados por categoria
    FORMATOS = {
        'documentos': ['pdf', 'docx', 'txt', 'html', 'rtf', 'odt'],
        'planilhas': ['xlsx', 'csv', 'ods', 'xls'],
        'imagens': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp'],
        'financeiro': ['ofx', 'qif', 'csv'],
        'texto': ['txt', 'csv', 'json', 'xml'],
    }
    
    # Mapeamento de extensão para categoria
    CATEGORIA_POR_EXT = {
        'pdf': 'documentos', 'docx': 'documentos', 'txt': 'texto', 'html': 'documentos',
        'xlsx': 'planilhas', 'csv': 'planilhas', 'ods': 'planilhas',
        'jpg': 'imagens', 'jpeg': 'imagens', 'png': 'imagens', 'gif': 'imagens',
        'ofx': 'financeiro', 'qif': 'financeiro',
        'json': 'texto', 'xml': 'texto',
    }
    
    @classmethod
    def get_formatos_destino(cls, formato_origem):
        """Retorna formatos de destino compatíveis com a origem"""
        formato_origem = formato_origem.lower().replace('.', '')
        
        # PDF pode ser convertido para vários formatos
        if formato_origem == 'pdf':
            return ['ofx', 'txt', 'html', 'jpg', 'png']
        
        # Arquivo ZIP: não sabemos o conteúdo, mas assumimos conversão em lote
        if formato_origem == 'zip':
            # opções genéricas que fazem sentido para a maioria dos usos (ex.: PDFs dentro do ZIP)
            return ['ofx', 'pdf', 'txt', 'html', 'jpg', 'png', 'csv']
        
        # OFX pode ser convertido para PDF/TXT
        if formato_origem == 'ofx':
            return ['pdf', 'txt', 'csv']
        
        # Imagens
        if formato_origem in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
            return ['jpg', 'png', 'pdf']
        
        # Documentos
        if formato_origem in ['docx', 'txt', 'html', 'rtf']:
            return ['pdf', 'txt', 'html']
        
        # Planilhas
        if formato_origem in ['xlsx', 'csv', 'ods']:
            return ['csv', 'pdf', 'xlsx']
        
        # Texto
        if formato_origem in ['txt', 'csv', 'json']:
            return ['txt', 'csv', 'json', 'html']
        
        return []
    
    @classmethod
    def converter(cls, arquivo_path, formato_destino, output_dir=None):
        """
        Converte um arquivo para o formato especificado
        
        Args:
            arquivo_path: Caminho do arquivo original
            formato_destino: Formato de destino (ex: 'ofx', 'pdf')
            output_dir: Pasta de saída (opcional)
        
        Returns:
            tuple: (caminho_arquivo_convertido, mensagem_erro)
        """
        if not os.path.exists(arquivo_path):
            return None, "Arquivo não encontrado"
        
        formato_origem = os.path.splitext(arquivo_path)[1].lower().replace('.', '')
        nome_base = os.path.splitext(os.path.basename(arquivo_path))[0]
        # se o arquivo for um ZIP, descompacta e processa cada membro separadamente
        if formato_origem == 'zip':
            import zipfile, glob
            if not output_dir:
                output_dir = tempfile.gettempdir()
            with tempfile.TemporaryDirectory() as td:
                with zipfile.ZipFile(arquivo_path, 'r') as z:
                    z.extractall(td)
                resultados = []
                erros = []
                for member in glob.glob(os.path.join(td, '*')):
                    r,e = cls.converter(member, formato_destino, td)
                    if r:
                        resultados.append(r)
                    else:
                        erros.append((member,e))
                if resultados:
                    zip_out = os.path.join(output_dir, f"{nome_base}_converted.zip")
                    with zipfile.ZipFile(zip_out, 'w') as z2:
                        for res in resultados:
                            z2.write(res, os.path.basename(res))
                    return zip_out, None
                return None, 'Nenhum arquivo convertido dentro do ZIP'
        
        if not output_dir:
            output_dir = tempfile.gettempdir()
        
        output_path = os.path.join(output_dir, f"{nome_base}.{formato_destino}")
        
        # PDF → OFX (primeiro PDF → TXT, depois TXT → OFX, transparente para o usuário)
        if formato_origem == 'pdf' and formato_destino == 'ofx':
            # 1. Converte PDF para TXT temporário
            nome_base = os.path.splitext(os.path.basename(arquivo_path))[0]
            with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp_txt:
                txt_path = tmp_txt.name
            _, err_txt = cls._converter_pdf_para_txt(arquivo_path, txt_path)
            if err_txt:
                return None, f'Erro ao converter PDF para TXT: {err_txt}'
            # 2. Converte TXT para OFX
            ofx_path, err_ofx = cls._converter_txt_para_ofx(txt_path, output_path)
            # Remove TXT temporário
            try:
                os.remove(txt_path)
            except Exception:
                pass
            return ofx_path, err_ofx
            @classmethod
            def _converter_txt_para_ofx(cls, txt_path, ofx_path):
                """Converte extrato TXT para OFX (usando o mesmo parser de texto do PDF)"""
                try:
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        texto = f.read()
                    transacoes = cls._extrair_transacoes(texto)
                    if not transacoes:
                        return None, "Nenhuma transação encontrada no TXT"
                    sucesso = cls._gerar_ofx(transacoes, ofx_path)
                    if sucesso:
                        return ofx_path, None
                    else:
                        return None, "Erro ao gerar arquivo OFX"
                except Exception as e:
                    return None, f"Erro na conversão TXT→OFX: {str(e)}"
        
        # PDF → TXT
        elif formato_origem == 'pdf' and formato_destino == 'txt':
            return cls._converter_pdf_para_txt(arquivo_path, output_path)
        
        # OFX → PDF
        elif formato_origem == 'ofx' and formato_destino == 'pdf':
            return cls._converter_ofx_para_pdf(arquivo_path, output_path)
        
        # Imagens
        elif formato_origem in ['jpg', 'jpeg', 'png', 'gif', 'bmp'] and HAS_PIL:
            return cls._converter_imagem(arquivo_path, output_path, formato_destino)
        
        # Documentos com LibreOffice
        else:
            return cls._converter_com_libreoffice(arquivo_path, output_path, formato_destino)
    
    @classmethod
    def _converter_pdf_para_ofx(cls, pdf_path, ofx_path):
        """Converte extrato PDF para OFX"""
        try:
            # Extrair texto do PDF
            texto = cls._extrair_texto_pdf(pdf_path)
            if not texto:
                return None, "Não foi possível extrair texto do PDF"
            
            # Extrair transações
            transacoes = cls._extrair_transacoes(texto)
            if not transacoes:
                return None, "Nenhuma transação encontrada no PDF"
            
            # Gerar OFX
            sucesso = cls._gerar_ofx(transacoes, ofx_path)
            if sucesso:
                # DATALEARN: detectar banco e treinar layout a partir do PDF original
                try:
                    banco_detectado = cls._detectar_banco_por_texto(texto)
                    if banco_detectado:
                        cls._treinar_layout_banco(pdf_path, texto, banco_detectado, transacoes=transacoes)
                except Exception:
                    # não interromper a conversão se o treinamento falhar
                    pass

                return ofx_path, None
            else:
                return None, "Erro ao gerar arquivo OFX"
                
        except Exception as e:
            return None, f"Erro na conversão: {str(e)}"
    
    @classmethod
    def _extrair_texto_pdf(cls, pdf_path):
        """Extrai texto de PDF usando múltiplos métodos (PyPDF2, pdftotext, pdfminer, OCR)"""
        texto = ""
        # 1. PyPDF2
        if HAS_PYPDF2:
            try:
                with open(pdf_path, 'rb') as f:
                    reader = PdfReader(f)
                    for page in reader.pages:
                        t = page.extract_text()
                        if t:
                            texto += t + "\n"
                if texto.strip():
                    return texto
            except Exception:
                pass
        # 2. pdftotext (use system or bundled copy)
        try:
            pdftotext_cmd = shutil.which('pdftotext')
            if not pdftotext_cmd:
                candidate = os.path.join(PROJECT_ROOT, 'pdftotext.exe')
                if os.path.exists(candidate):
                    pdftotext_cmd = candidate
            if pdftotext_cmd:
                result = subprocess.run(
                    [pdftotext_cmd, pdf_path, '-'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout
        except Exception:
            pass
        # 3. pdfminer.six
        if HAS_PDFMINER:
            try:
                texto = pdfminer_extract_text(pdf_path)
                if texto and texto.strip():
                    return texto
            except Exception:
                pass
        # 4. OCR (pytesseract/pdf2image or pymupdf render) - aprimorado
        if HAS_OCR:
            try:
                # Força caminho do tesseract se existir
                import pytesseract
                if os.path.exists(cls.TESSERACT_CMD):
                    pytesseract.pytesseract.tesseract_cmd = cls.TESSERACT_CMD
                # primeiro tenta com pdf2image/poppler se disponível
                for dpi in [300, 400, 600]:
                    try:
                        imagens = convert_from_path(pdf_path, dpi=dpi, poppler_path=POPPLER_PATH)
                        texto_ocr = ""
                        for img in imagens:
                            img_gray = img.convert('L')
                            img_bin = img_gray.point(lambda x: 0 if x < 180 else 255, '1')
                            texto_ocr += pytesseract.image_to_string(img_gray, lang='por') + "\n"
                            texto_ocr += pytesseract.image_to_string(img_bin, lang='por') + "\n"
                        if texto_ocr.strip():
                            return texto_ocr
                    except Exception:
                        continue
                # se não conseguiu, tenta renderizando via PyMuPDF
                try:
                    import fitz
                    doc = fitz.open(pdf_path)
                    texto_ocr = ""
                    for page in doc:
                        pix = page.get_pixmap(dpi=300)
                        from PIL import Image
                        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                        img_gray = img.convert('L')
                        img_bin = img_gray.point(lambda x: 0 if x < 180 else 255, '1')
                        texto_ocr += pytesseract.image_to_string(img_gray, lang='por') + "\n"
                        texto_ocr += pytesseract.image_to_string(img_bin, lang='por') + "\n"
                    if texto_ocr.strip():
                        return texto_ocr
                except Exception:
                    pass
            except Exception:
                pass
        return texto
    
    @classmethod
    def _extrair_transacoes(cls, texto):
        """Extrai transações bancárias do texto"""
        transacoes = []
        
        # Padrões de data
        padroes_data = [
            r'(\d{2}/\d{2}/\d{4})',
            r'(\d{2}-\d{2}-\d{4})',
            r'(\d{4}-\d{2}-\d{2})'
        ]
        
        # Padrão de valor
        padrao_valor = r'([+-]?[\d.,]+(?:[.,]\d{2})?)'
        
        linhas = texto.split('\n')
        data_atual = None
        
        for linha in linhas:
            linha = linha.strip()
            if not linha:
                continue
            
            # Procurar data
            for padrao in padroes_data:
                data_match = re.search(padrao, linha)
                if data_match:
                    data_str = data_match.group(1)
                    
                    try:
                        if '/' in data_str:
                            if len(data_str.split('/')[2]) == 4:
                                data_obj = datetime.strptime(data_str, '%d/%m/%Y')
                            else:
                                data_obj = datetime.strptime(data_str, '%Y/%m/%d')
                        elif '-' in data_str:
                            data_obj = datetime.strptime(data_str, '%Y-%m-%d')
                        else:
                            continue
                        
                        data_atual = data_obj.strftime('%Y%m%d')
                        break
                    except:
                        continue
            
            # Procurar valor
            valor_match = re.search(padrao_valor, linha)
            if valor_match and data_atual:
                valor_str = valor_match.group(1)
                
                # Limpar valor
                valor_clean = valor_str.replace('.', '').replace(',', '.')
                
                try:
                    if 'R$' in valor_clean:
                        valor_clean = valor_clean.replace('R$', '').strip()
                    
                    valor = float(valor_clean)
                    
                    # Descrição
                    desc = linha
                    for padrao in padroes_data:
                        desc = re.sub(padrao, '', desc)
                    desc = re.sub(padrao_valor, '', desc)
                    desc = re.sub(r'R\$\s*', '', desc).strip()
                    
                    if desc and abs(valor) > 0.01:
                        transacoes.append({
                            'data': data_atual,
                            'valor': valor,
                            'descricao': desc[:80]
                        })
                except:
                    continue
        
        return transacoes
    
    @classmethod
    def _gerar_ofx(cls, transacoes, ofx_path):
        """Gera arquivo OFX a partir das transações"""
        try:
            linhas = []
            
            # Cabeçalho
            linhas.append('OFXHEADER:100')
            linhas.append('DATA:OFXSGML')
            linhas.append('VERSION:102')
            linhas.append('SECURITY:NONE')
            linhas.append('ENCODING:USASCII')
            linhas.append('CHARSET:1252')
            linhas.append('COMPRESSION:NONE')
            linhas.append('OLDFILEUID:NONE')
            linhas.append('NEWFILEUID:NONE')
            linhas.append('')
            
            # Início OFX
            linhas.append('<OFX>')
            linhas.append('  <SIGNONMSGSRSV1>')
            linhas.append('    <SONRS>')
            linhas.append('      <STATUS>')
            linhas.append('        <CODE>0')
            linhas.append('        <SEVERITY>INFO')
            linhas.append('      </STATUS>')
            linhas.append(f'      <DTSERVER>{datetime.now().strftime("%Y%m%d%H%M%S")}')
            linhas.append('      <LANGUAGE>POR')
            linhas.append('    </SONRS>')
            linhas.append('  </SIGNONMSGSRSV1>')
            linhas.append('  <BANKMSGSRSV1>')
            linhas.append('    <STMTTRNRS>')
            linhas.append('      <STMTRS>')
            linhas.append('        <CURDEF>BRL')
            linhas.append('        <BANKTRANLIST>')
            
            # Transações
            for t in transacoes:
                linhas.append('          <STMTTRN>')
                linhas.append('            <TRNTYPE>OTHER')
                linhas.append(f'            <DTPOSTED>{t["data"]}')
                linhas.append(f'            <TRNAMT>{t["valor"]:.2f}')
                fit_id = f'{t["data"]}{abs(int(t["valor"]*100))}'
                linhas.append(f'            <FITID>{fit_id}')
                linhas.append(f'            <NAME>{t["descricao"]}')
                linhas.append('          </STMTTRN>')
            
            linhas.append('        </BANKTRANLIST>')
            linhas.append('      </STMTRS>')
            linhas.append('    </STMTTRNRS>')
            linhas.append('  </BANKMSGSRSV1>')
            linhas.append('</OFX>')
            
            # Salvar
            with open(ofx_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(linhas))
            
            return True
            
        except Exception:
            return False

    # ------------------------------------------
    # DATALEARN: detectar/armazenar layout bancário
    # ------------------------------------------
    @classmethod
    def _detectar_banco_por_texto(cls, texto):
        """Tenta identificar o banco a partir do texto do PDF/OFX (heurística simples)."""
        if not texto:
            return None
        txt = texto.lower()
        mapeamento = {
            'banco do brasil': 'Banco do Brasil',
            'bancodobrasil': 'Banco do Brasil',
            'bb ': 'Banco do Brasil',
            'itaú': 'Itaú',
            'itau': 'Itaú',
            'bradesco': 'Bradesco',
            'santander': 'Santander',
            'caixa': 'Caixa Econômica Federal',
            'nubank': 'Nubank',
            'next': 'Next',
            'banrisul': 'Banrisul'
        }
        for k, nome in mapeamento.items():
            if k in txt:
                return nome
        return None

    @classmethod
    def _treinar_layout_banco(cls, pdf_path, texto, banco_nome, transacoes=None):
        """Armazena um template HTML simplificado baseado no PDF original.
        - salva exemplo_pdf
        - salva template_html com placeholders ({{transactions_rows}})
        Esse template será usado para gerar PDFs semelhantes a partir de OFX.
        """
        try:
            from django.core.files import File
            from .models import LayoutBancario

            # Extrair linhas de cabeçalho do PDF (texto recebido pelo extrator)
            linhas = [l.strip() for l in (texto or '').splitlines() if l.strip()]
            header_lines = linhas[:8]
            header_html = '<br>'.join(header_lines)

            # Template HTML básico que tenta espelhar o layout: cabeçalho + tabela de transações
            template_html = f"""<!doctype html>
<html>
<head>
<meta charset=\"utf-8\"> 
<style>
body {{ font-family: Arial, Helvetica, sans-serif; color:#222; margin:20px; }}
.header {{ text-align:left; margin-bottom:12px; }}
.header .bank {{ font-weight:700; font-size:18px; color:#1a73e8; }}
.table-trans {{ width:100%; border-collapse:collapse; margin-top:12px; }}
.table-trans th, .table-trans td {{ border:1px solid #ddd; padding:6px 8px; font-size:12px; }}
.table-trans th {{ background:#f7f7f7; text-align:left; }}
.footer {{ margin-top:16px; font-size:11px; color:#666; }}
</style>
</head>
<body>
  <div class=\"header\"> 
    <div class=\"bank\">{banco_nome}</div>
    <div class=\"meta\">{header_html}</div>
  </div>

  <table class=\"table-trans\">
    <thead>
      <tr><th>Data</th><th>Descrição</th><th class=\"text-end\">Valor (R$)</th></tr>
    </thead>
    <tbody>
      {{transactions_rows}}
    </tbody>
  </table>

  <div class=\"footer\">Documento gerado pelo conversor - modelo aprendido ({banco_nome})</div>
</body>
</html>"""

            # Salvar ou atualizar o registro
            layout = LayoutBancario.objects.filter(nome__iexact=banco_nome).first()
            if not layout:
                layout = LayoutBancario(nome=banco_nome)

            # atualizar identificadores (merge simples)
            ids_txt = set([s.strip() for s in (layout.identificadores or '').split(',') if s.strip()])
            # adiciona algumas palavras-chaves conhecidas a partir do nome
            ids_txt.update([p.strip() for p in (banco_nome or '').split() if p.strip()])
            layout.identificadores = ','.join(sorted(ids_txt))
            layout.template_html = template_html

            # salvar exemplo_pdf (substitui se já existir)
            try:
                with open(pdf_path, 'rb') as f:
                    django_file = File(f)
                    layout.exemplo_pdf.save(f"exemplo_{layout.nome.lower().replace(' ', '_')}.pdf", django_file, save=False)
            except Exception:
                # se falhar ao salvar arquivo, continua apenas com template
                pass

            layout.ativo = True
            layout.save()
            return True
        except Exception:
            return False

    @classmethod
    def _parse_ofx(cls, ofx_content):
        """Extrai transações simples de um conteúdo OFX/string."""
        transacoes = []
        try:
            # Encontrar blocos <STMTTRN>...</STMTTRN>
            blocos = re.findall(r'<STMTTRN>(.*?)</STMTTRN>', ofx_content, flags=re.S | re.I)
            for bloco in blocos:
                dt = re.search(r'<DTPOSTED>(\d+)', bloco, flags=re.I)
                amt = re.search(r'<TRNAMT>([-\d.,]+)', bloco, flags=re.I)
                nome = re.search(r'<NAME>([^<\n]+)', bloco, flags=re.I)

                data_str = dt.group(1)[:8] if dt else None
                data_fmt = None
                if data_str:
                    try:
                        data_fmt = datetime.strptime(data_str, '%Y%m%d').strftime('%d/%m/%Y')
                    except:
                        data_fmt = data_str

                valor = None
                if amt:
                    valor_txt = amt.group(1).replace(',', '.')
                    try:
                        valor = float(valor_txt)
                    except:
                        valor = 0.0

                descricao = nome.group(1).strip() if nome else ''

                if data_fmt and valor is not None:
                    transacoes.append({'data': data_fmt, 'valor': valor, 'descricao': descricao})
        except Exception:
            pass
        return transacoes

    @classmethod
    def _render_transactions_table(cls, transacoes):
        """Retorna HTML com linhas de transações (cadeia para injeção no template)."""
        rows = []
        for t in transacoes:
            valor_fmt = f"{t['valor']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            rows.append(f"<tr><td>{t['data']}</td><td>{t['descricao']}</td><td style=\"text-align:right\">{valor_fmt}</td></tr>")
        return '\n'.join(rows)

    @classmethod
    def _converter_pdf_para_txt(cls, pdf_path, txt_path):
        """Converte PDF para TXT"""
        texto = cls._extrair_texto_pdf(pdf_path)
        if not texto:
            return None, "Não foi possível extrair texto do PDF"
        
        try:
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(texto)
            return txt_path, None
        except Exception as e:
            return None, str(e)
    
    @classmethod
    def _converter_ofx_para_pdf(cls, ofx_path, pdf_path):
        """Converte OFX para PDF.
        Se houver um layout aprendido para o banco presente no OFX, gera o PDF usando esse template;
        caso contrário, gera uma representação genérica (fallback).
        """
        try:
            with open(ofx_path, 'r', encoding='utf-8') as f:
                conteudo = f.read()

            # Tenta parsear transações e detectar banco
            transacoes = cls._parse_ofx(conteudo)
            banco_detectado = cls._detectar_banco_por_texto(conteudo)

            layout = None
            if banco_detectado:
                try:
                    from .models import LayoutBancario
                    layout = LayoutBancario.objects.filter(nome__iexact=banco_detectado, ativo=True).first()
                except Exception:
                    layout = None

            if layout and layout.template_html:
                # Preenche o template aprendido
                html = layout.template_html
                rows = cls._render_transactions_table(transacoes or [])
                html = html.replace('{{transactions_rows}}', rows)
                html = html.replace('{{bank_name}}', layout.nome)

                html_path = pdf_path.replace('.pdf', '.html')
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html)

                return cls._converter_com_libreoffice(html_path, pdf_path, 'pdf')

            # Fallback genérico (exibe o OFX bruto)
            html = f"""<!DOCTYPE html>
<html>
<head><meta charset=\"UTF-8\"><title>OFX Convertido</title></head>
<body><pre>{conteudo}</pre></body>
</html>"""
            html_path = pdf_path.replace('.pdf', '.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)

            return cls._converter_com_libreoffice(html_path, pdf_path, 'pdf')

        except Exception as e:
            return None, str(e)
    
    @classmethod
    def _converter_imagem(cls, img_path, output_path, formato_destino):
        """Converte imagens usando PIL"""
        if not HAS_PIL:
            return None, "PIL não instalado. Instale com: pip install Pillow"
        
        try:
            img = Image.open(img_path)
            if formato_destino.upper() in ['JPG', 'JPEG'] and img.mode in ['RGBA', 'P']:
                img = img.convert('RGB')
            img.save(output_path)
            return output_path, None
        except Exception as e:
            return None, str(e)
    
    @classmethod
    def _converter_com_libreoffice(cls, input_path, output_path, formato_destino):
        """Converte usando LibreOffice"""
        try:
            # Procurar LibreOffice
            cmd = 'soffice'
            if os.name == 'nt':  # Windows
                paths = [
                    r"C:\Program Files\LibreOffice\program\soffice.exe",
                    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
                ]
                for path in paths:
                    if os.path.exists(path):
                        cmd = path
                        break
            
            # Criar pasta temporária para saída
            with tempfile.TemporaryDirectory() as temp_dir:
                result = subprocess.run(
                    [cmd, '--headless', '--convert-to', formato_destino,
                     '--outdir', temp_dir, input_path],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    # Encontrar arquivo convertido
                    nome_base = os.path.splitext(os.path.basename(input_path))[0]
                    arquivo_convertido = os.path.join(temp_dir, f"{nome_base}.{formato_destino}")
                    
                    if os.path.exists(arquivo_convertido):
                        shutil.copy2(arquivo_convertido, output_path)
                        return output_path, None
                
                return None, f"Erro na conversão: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return None, "Timeout na conversão"
        except Exception as e:
            return None, str(e)


# Interface simplificada (estas funções ficam no final do arquivo)
def converter_arquivo(arquivo_path, formato_destino, output_dir=None):
    """Função simplificada para converter arquivo"""
    return ConversorService.converter(arquivo_path, formato_destino, output_dir)


def get_formatos_destino(formato_origem):
    """Retorna formatos disponíveis para conversão"""
    return ConversorService.get_formatos_destino(formato_origem)