"""
Serviço de conversão de arquivos integrado ao HDowloader
Suporte especial para PDF → OFX
"""
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

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class ConversorService:
    """Serviço para conversão de arquivos"""
    
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
        
        if not output_dir:
            output_dir = tempfile.gettempdir()
        
        output_path = os.path.join(output_dir, f"{nome_base}.{formato_destino}")
        
        # PDF → OFX (nosso foco principal)
        if formato_origem == 'pdf' and formato_destino == 'ofx':
            return cls._converter_pdf_para_ofx(arquivo_path, output_path)
        
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
                return ofx_path, None
            else:
                return None, "Erro ao gerar arquivo OFX"
                
        except Exception as e:
            return None, f"Erro na conversão: {str(e)}"
    
    @classmethod
    def _extrair_texto_pdf(cls, pdf_path):
        """Extrai texto de PDF"""
        texto = ""
        
        if HAS_PYPDF2:
            try:
                with open(pdf_path, 'rb') as f:
                    reader = PdfReader(f)
                    for page in reader.pages:
                        texto += page.extract_text() + "\n"
                if texto.strip():
                    return texto
            except:
                pass
        
        # Fallback para pdftotext
        try:
            result = subprocess.run(
                ['pdftotext', pdf_path, '-'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout
        except:
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
        """Converte OFX para PDF (representação simples)"""
        try:
            # Ler OFX
            with open(ofx_path, 'r', encoding='utf-8') as f:
                conteudo = f.read()
            
            # HTML simples
            html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>OFX Convertido</title></head>
<body><pre>{conteudo}</pre></body>
</html>"""
            
            html_path = pdf_path.replace('.pdf', '.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)
            
            # Converter HTML para PDF (via LibreOffice)
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