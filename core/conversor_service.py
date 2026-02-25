import os
import re
import subprocess
import zipfile
import tempfile
from datetime import datetime
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Optional
import traceback

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
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    POPPLER_PATH = os.path.join(PROJECT_ROOT, 'poppler-25.12.0', 'Library', 'bin')
    TESSERACT_CMD = os.path.join(PROJECT_ROOT, 'Tesseract-OCR', 'tesseract.exe')
    TESSDATA_PREFIX = os.path.join(PROJECT_ROOT, 'tessdata')

    # Configura caminhos
    if os.path.exists(POPPLER_PATH):
        os.environ['PATH'] = POPPLER_PATH + os.pathsep + os.environ.get('PATH', '')
    
    if os.path.exists(TESSDATA_PREFIX):
        os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX
    
    if os.path.exists(TESSERACT_CMD) and HAS_OCR:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

    # Configurações de OCR
    OCR_CONFIGS = [
        {
            'nome': 'Rápido (150 DPI)',
            'dpi': 150,
            'grayscale': True,
            'preprocess': 'basic',
            'tesseract_config': r'--oem 3 --psm 6',
            'peso': 1
        },
        {
            'nome': 'Médio (200 DPI)',
            'dpi': 200,
            'grayscale': False,
            'preprocess': 'contrast',
            'tesseract_config': r'--oem 3 --psm 3',
            'peso': 2
        },
        {
            'nome': 'Completo (300 DPI)',
            'dpi': 300,
            'grayscale': False,
            'preprocess': 'full',
            'tesseract_config': r'--oem 3 --psm 3 --dpi 300',
            'peso': 3
        }
    ]
    
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
    def _preprocessar_imagem(cls, imagem, nivel='basic'):
        """Pré-processa imagem em diferentes níveis."""
        try:
            if nivel == 'basic':
                return imagem.convert('L')
            
            elif nivel == 'contrast':
                img = imagem.convert('L')
                enhancer = ImageEnhance.Contrast(img)
                return enhancer.enhance(1.5)
            
            elif nivel == 'full':
                img = imagem.convert('L')
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.0)
                img = img.filter(ImageFilter.MedianFilter(size=3))
                img = ImageOps.autocontrast(img, cutoff=2)
                return img
            
            return imagem
            
        except Exception as e:
            print(f"    Erro no pré-processamento: {e}")
            return imagem

    @classmethod
    def _extrair_texto_com_ocr(cls, pdf_path: str, config: dict) -> str:
        """Extrai texto com OCR processando TODAS as páginas."""
        if not HAS_OCR:
            return ""
        
        print(f"\n  📸 Tentando OCR: {config['nome']}")
        
        try:
            # Prepara parâmetros
            kwargs = {
                'pdf_path': pdf_path,
                'dpi': config['dpi'],
                'poppler_path': cls.POPPLER_PATH,
                'fmt': 'jpeg',
                'thread_count': cls.MAX_WORKERS
            }
            
            if config.get('grayscale'):
                kwargs['grayscale'] = True
            
            print(f"    🔄 Convertendo PDF ({config['dpi']} DPI)...")
            
            # Converte TODAS as páginas
            imagens = convert_from_path(**kwargs)
            total_paginas = len(imagens)
            print(f"    📄 {total_paginas} páginas convertidas")

            def processar_pagina(args):
                idx, img = args
                try:
                    img_proc = cls._preprocessar_imagem(img, config.get('preprocess', 'basic'))
                    texto = pytesseract.image_to_string(
                        img_proc, 
                        lang='por', 
                        config=config['tesseract_config']
                    )
                    
                    if (idx + 1) % 10 == 0 or (idx + 1) == total_paginas:
                        print(f"      Página {idx+1}/{total_paginas}: {len(texto)} chars")
                    
                    return texto
                except Exception as e:
                    print(f"      Erro na página {idx+1}: {e}")
                    return ""

            # Processa em paralelo
            with ThreadPoolExecutor(max_workers=cls.MAX_WORKERS) as executor:
                args_list = [(i, img) for i, img in enumerate(imagens)]
                resultados = list(executor.map(processar_pagina, args_list))

            texto_final = '\n'.join(resultados)
            print(f"    ✅ Extraídos {len(texto_final)} caracteres de {total_paginas} páginas")
            
            return texto_final

        except Exception as e:
            print(f"    ❌ Erro no OCR: {e}")
            traceback.print_exc()
            return ""

    @classmethod
    def extrair_texto_pdf(cls, pdf_path: str, modo_rapido: bool = True) -> str:
        """
        Extrai texto de PDF com múltiplas tentativas - processa TODAS as páginas.
        """
        if not os.path.exists(pdf_path):
            print(f"  Arquivo não encontrado: {pdf_path}")
            return ""

        print(f"\n📄 Extraindo texto de: {os.path.basename(pdf_path)}")
        print(f"  Tamanho: {os.path.getsize(pdf_path) / 1024 / 1024:.1f} MB")
        print(f"  Modo: {'RÁPIDO' if modo_rapido else 'COMPLETO'}")

        textos_encontrados = []

        # Estratégia 1: PyMuPDF
        if HAS_FITZ:
            try:
                print("\n  📄 Tentando PyMuPDF...")
                doc = fitz.open(pdf_path)
                total_paginas = len(doc)
                texto = ""
                paginas_com_texto = 0
                
                for i, pagina in enumerate(doc):
                    page_text = pagina.get_text()
                    if page_text.strip():
                        texto += page_text + "\n"
                        paginas_com_texto += 1
                    
                    if (i + 1) % 10 == 0 or (i + 1) == total_paginas:
                        print(f"    Página {i+1}/{total_paginas}: {len(page_text)} chars")
                
                doc.close()
                
                if texto.strip():
                    print(f"  ✅ PyMuPDF extraiu {len(texto)} caracteres de {paginas_com_texto} páginas")
                    textos_encontrados.append(('PyMuPDF', texto))
                else:
                    print("  ⚠ PyMuPDF não encontrou texto")
                    
            except Exception as e:
                print(f"  Erro no PyMuPDF: {e}")

        # Estratégia 2: pdftotext
        try:
            print("\n  📄 Tentando pdftotext...")
            pdftotext_cmd = os.path.join(cls.POPPLER_PATH, 'pdftotext.exe')
            if os.path.exists(pdftotext_cmd):
                resultado = subprocess.run(
                    [pdftotext_cmd, '-layout', '-nopgbrk', pdf_path, '-'],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if resultado.returncode == 0 and resultado.stdout.strip():
                    texto = resultado.stdout
                    print(f"  ✅ pdftotext extraiu {len(texto)} caracteres")
                    textos_encontrados.append(('pdftotext', texto))
                else:
                    print("  ⚠ pdftotext não encontrou texto")
        except subprocess.TimeoutExpired:
            print("  ⚠ pdftotext timeout (muito lento)")
        except Exception as e:
            print(f"  Erro no pdftotext: {e}")

        # Estratégia 3: OCR
        if HAS_OCR:
            if modo_rapido:
                configs_tentar = cls.OCR_CONFIGS[:2]
            else:
                configs_tentar = cls.OCR_CONFIGS
            
            for config in configs_tentar:
                texto = cls._extrair_texto_com_ocr(pdf_path, config)
                if texto.strip():
                    textos_encontrados.append((config['nome'], texto))
                    if len(texto) > 100000 and modo_rapido:
                        print(f"\n  ✅ Texto suficiente encontrado, parando...")
                        break

        # Escolhe o melhor texto
        if textos_encontrados:
            melhor_texto = max(textos_encontrados, key=lambda x: len(x[1]))
            print(f"\n  ✅ Melhor resultado: {melhor_texto[0]} - {len(melhor_texto[1])} caracteres")
            return melhor_texto[1]

        print("\n  ❌ Nenhum texto extraído")
        return ""

    @classmethod
    def extrair_transacoes(cls, texto: str) -> List[Dict]:
        """
        Extrai transações bancárias do texto - VERSÃO OTIMIZADA.
        """
        if not texto:
            return []

        print(f"\n📊 Extraindo transações de {len(texto)} caracteres")
        
        todas_transacoes = []
        linhas = texto.split('\n')
        print(f"  {len(linhas)} linhas para processar")

        # Padrões simples e rápidos
        padrao_data = re.compile(r'(\d{2}[/]\d{2}[/]\d{2,4})')
        padrao_valor = re.compile(r'(\d{1,3}(?:[.]\d{3})*[,]\d{2})')
        padrao_doc = re.compile(r'\b(\d{6})\b')
        
        # Palavras-chave para tipo
        palavras_debito = ['PAG', 'DEB', 'TAR', 'ENVIADO', 'BOLETO', 'D ']
        palavras_credito = ['CRED', 'RECEBIDO', 'PIX RECEBIDO', 'C ']

        print("\n  🔍 Processando transações linha a linha...")
        
        for i, linha in enumerate(linhas):
            linha = linha.strip()
            if len(linha) < 10:  # Linhas muito curtas ignorar
                continue
            
            # Procura data e valor na mesma linha
            data_match = padrao_data.search(linha)
            valor_match = padrao_valor.search(linha)
            
            if data_match and valor_match:
                try:
                    # Data
                    data_str = data_match.group(1)
                    partes = data_str.split('/')
                    if len(partes) == 3:
                        dia, mes, ano = partes
                        if len(ano) == 2:
                            ano = f"20{ano}" if int(ano) <= 30 else f"19{ano}"
                        data = f"{ano}{mes}{dia}"
                        
                        # Valor
                        valor_str = valor_match.group(1)
                        valor = float(valor_str.replace('.', '').replace(',', '.'))
                        
                        # Documento (opcional)
                        doc_match = padrao_doc.search(linha)
                        documento = doc_match.group(1) if doc_match else ""
                        
                        # Determina tipo baseado em palavras-chave
                        linha_upper = linha.upper()
                        if any(p in linha_upper for p in palavras_debito):
                            tipo = 'DEBIT'
                        elif any(p in linha_upper for p in palavras_credito):
                            tipo = 'CREDIT'
                        else:
                            # Tenta inferir pelo sinal
                            tipo = 'DEBIT' if ('-' in linha) else 'CREDIT'
                        
                        # Descrição (remove datas, valores e documentos)
                        desc = linha
                        desc = padrao_data.sub('', desc)
                        desc = padrao_valor.sub('', desc)
                        if documento:
                            desc = desc.replace(documento, '')
                        desc = re.sub(r'\s+', ' ', desc).strip()
                        
                        if not desc:
                            desc = f"Transacao {documento}" if documento else "Transacao"
                        
                        todas_transacoes.append({
                            'data': data,
                            'valor': valor,
                            'descricao': desc[:60].upper(),
                            'tipo': tipo,
                            'documento': documento
                        })
                        
                        if len(todas_transacoes) % 100 == 0:
                            print(f"    {len(todas_transacoes)} transações encontradas...")
                            
                except Exception as e:
                    # Silencia erros individuais para não travar
                    pass

        print(f"\n  ✅ Encontradas {len(todas_transacoes)} transações brutas")

        # Remove duplicatas de forma eficiente
        print("  🔄 Removendo duplicatas...")
        transacoes_unicas = []
        vistos = set()
        
        for t in todas_transacoes:
            # Chave única: data + valor + primeiros 10 chars da descrição
            chave = f"{t['data']}_{t['valor']:.2f}_{t['descricao'][:10]}"
            if chave not in vistos:
                vistos.add(chave)
                
                # Gera FITID
                fitid = f"{t['data']}{int(t['valor'] * 100):08d}"
                if t.get('documento'):
                    fitid = f"{fitid}{t['documento']}"
                else:
                    # Usa hash simples da descrição
                    fitid = f"{fitid}{abs(hash(t['descricao'])) % 10000:04d}"
                
                t['fitid'] = fitid[:30]
                transacoes_unicas.append(t)

        # Ordena por data
        transacoes_unicas.sort(key=lambda x: x['data'])
        
        print(f"\n  ✅ Total final: {len(transacoes_unicas)} transações únicas")
        
        # Mostra estatísticas
        if transacoes_unicas:
            datas = [t['data'] for t in transacoes_unicas]
            print(f"    Período: {min(datas)} a {max(datas)}")
            
            # Conta por tipo
            debitos = sum(1 for t in transacoes_unicas if t['tipo'] == 'DEBIT')
            creditos = sum(1 for t in transacoes_unicas if t['tipo'] == 'CREDIT')
            print(f"    Débitos: {debitos}, Créditos: {creditos}")
            
            print("\n  📝 Primeiras 10 transações:")
            for t in transacoes_unicas[:10]:
                print(f"    {t['data']} | {t['tipo']:6} | R$ {t['valor']:8.2f} | {t['descricao'][:40]}")
        
        return transacoes_unicas

    @classmethod
    def gerar_ofx(cls, transacoes: List[Dict], ofx_path: str, banco_id: str = "104", 
                  agencia: str = "0000", conta: str = "99999999") -> bool:
        """Gera arquivo OFX."""
        try:
            if not transacoes:
                return False

            print(f"\n📝 Gerando OFX com {len(transacoes)} transações...")
            
            transacoes.sort(key=lambda x: x['data'])
            data_inicio = min(t['data'] for t in transacoes)
            data_fim = max(t['data'] for t in transacoes)
            
            agora = datetime.now()
            data_server = agora.strftime("%Y%m%d%H%M%S")

            with open(ofx_path, 'w', encoding='utf-8') as f:
                # HEADER
                f.write("OFXHEADER:100\n")
                f.write("DATA:OFXSGML\n")
                f.write("VERSION:102\n")
                f.write("SECURITY:NONE\n")
                f.write("ENCODING:UTF-8\n")
                f.write("CHARSET:1252\n")
                f.write("COMPRESSION:NONE\n")
                f.write("OLDFILEUID:NONE\n")
                f.write("NEWFILEUID:NONE\n")
                f.write("\n")

                # OFX
                f.write("<OFX>\n")
                
                # SIGNON
                f.write("  <SIGNONMSGSRSV1>\n")
                f.write("    <SONRS>\n")
                f.write("      <STATUS>\n")
                f.write("        <CODE>0</CODE>\n")
                f.write("        <SEVERITY>INFO</SEVERITY>\n")
                f.write("      </STATUS>\n")
                f.write(f"      <DTSERVER>{data_server}</DTSERVER>\n")
                f.write("      <LANGUAGE>POR</LANGUAGE>\n")
                f.write("    </SONRS>\n")
                f.write("  </SIGNONMSGSRSV1>\n")
                
                # BANK
                f.write("  <BANKMSGSRSV1>\n")
                f.write("    <STMTTRNRS>\n")
                f.write("      <TRNUID>0</TRNUID>\n")
                f.write("      <STATUS>\n")
                f.write("        <CODE>0</CODE>\n")
                f.write("        <SEVERITY>INFO</SEVERITY>\n")
                f.write("      </STATUS>\n")
                f.write("      <STMTRS>\n")
                f.write(f"        <CURDEF>BRL</CURDEF>\n")
                
                # Conta
                f.write("        <BANKACCTFROM>\n")
                f.write(f"          <BANKID>{banco_id}</BANKID>\n")
                f.write(f"          <ACCTID>{conta}</ACCTID>\n")
                f.write("          <ACCTTYPE>CHECKING</ACCTTYPE>\n")
                f.write("        </BANKACCTFROM>\n")
                
                # Transações
                f.write("        <BANKTRANLIST>\n")
                f.write(f"          <DTSTART>{data_inicio}</DTSTART>\n")
                f.write(f"          <DTEND>{data_fim}</DTEND>\n")
                
                for i, t in enumerate(transacoes):
                    f.write("          <STMTTRN>\n")
                    f.write(f"            <TRNTYPE>{t['tipo']}</TRNTYPE>\n")
                    f.write(f"            <DTPOSTED>{t['data']}</DTPOSTED>\n")
                    
                    valor = t['valor'] if t['tipo'] == 'CREDIT' else -t['valor']
                    valor_str = f"{valor:.2f}".replace('.', ',')
                    f.write(f"            <TRNAMT>{valor_str}</TRNAMT>\n")
                    
                    f.write(f"            <FITID>{t['fitid']}</FITID>\n")
                    
                    checknum = t.get('documento', f"{i+1:06d}")
                    f.write(f"            <CHECKNUM>{checknum}</CHECKNUM>\n")
                    
                    f.write(f"            <MEMO>{t['descricao']}</MEMO>\n")
                    f.write("          </STMTTRN>\n")
                
                f.write("        </BANKTRANLIST>\n")
                
                # Saldo
                saldo_final = sum(t['valor'] if t['tipo'] == 'CREDIT' else -t['valor'] 
                                 for t in transacoes)
                saldo_str = f"{saldo_final:.2f}".replace('.', ',')
                
                f.write("        <LEDGERBAL>\n")
                f.write(f"          <BALAMT>{saldo_str}</BALAMT>\n")
                f.write(f"          <DTASOF>{data_fim}</DTASOF>\n")
                f.write("        </LEDGERBAL>\n")
                
                f.write("      </STMTRS>\n")
                f.write("    </STMTTRNRS>\n")
                f.write("  </BANKMSGSRSV1>\n")
                f.write("</OFX>\n")

            print(f"  ✅ OFX gerado: {os.path.basename(ofx_path)}")
            return True

        except Exception as e:
            print(f"  ❌ Erro ao gerar OFX: {e}")
            traceback.print_exc()
            return False

    @classmethod
    def _salvar_como_csv(cls, transacoes: List[Dict], csv_path: str) -> bool:
        """Salva transações em CSV."""
        try:
            import csv
            with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(['Data', 'Tipo', 'Valor', 'Descrição', 'Documento', 'FITID'])
                for t in transacoes:
                    writer.writerow([
                        t['data'],
                        t['tipo'],
                        f"{t['valor']:.2f}".replace('.', ','),
                        t['descricao'],
                        t.get('documento', ''),
                        t.get('fitid', '')
                    ])
            return True
        except Exception as e:
            print(f"Erro ao salvar CSV: {e}")
            return False

    @classmethod
    def converter(cls, arquivo_path: str, formato_destino: str, 
                  output_dir: Optional[str] = None, modo_rapido: bool = True) -> Tuple[Optional[str], Optional[str]]:
        """
        Converte arquivo para formato destino.
        """
        print(f"\n🔄 Iniciando conversão:")
        print(f"  Arquivo: {os.path.basename(arquivo_path)}")
        print(f"  Formato destino: {formato_destino}")
        print(f"  Modo: {'RÁPIDO' if modo_rapido else 'COMPLETO'}")

        if not os.path.exists(arquivo_path):
            return None, f"Arquivo não encontrado: {arquivo_path}"

        if not output_dir:
            output_dir = os.path.dirname(arquivo_path)
        
        os.makedirs(output_dir, exist_ok=True)

        formato_origem = os.path.splitext(arquivo_path)[1].lower().replace('.', '')
        nome_base = os.path.splitext(os.path.basename(arquivo_path))[0]
        output_path = os.path.join(output_dir, f"{nome_base}.{formato_destino}")

        # Processa PDF
        if formato_origem == 'pdf':
            print("\n📄 Processando PDF...")
            
            # Extrai texto
            texto = cls.extrair_texto_pdf(arquivo_path, modo_rapido)
            
            if not texto.strip():
                return None, "Não foi possível extrair texto do PDF"
            
            print(f"\n✅ Texto extraído: {len(texto)} caracteres")
            
            # Extrai transações
            transacoes = cls.extrair_transacoes(texto)
            
            # Salva texto para debug
            txt_debug = os.path.join(output_dir, f"{nome_base}_texto_extraido.txt")
            with open(txt_debug, 'w', encoding='utf-8') as f:
                f.write(texto)
            print(f"  📝 Texto salvo: {txt_debug}")
            
            # Salva CSV se tiver transações
            if transacoes:
                csv_path = os.path.join(output_dir, f"{nome_base}.csv")
                cls._salvar_como_csv(transacoes, csv_path)
                print(f"  📊 CSV salvo: {csv_path}")
            
            # Gera formato solicitado
            if formato_destino == 'ofx':
                if transacoes:
                    if cls.gerar_ofx(transacoes, output_path):
                        return output_path, None
                    else:
                        return csv_path, "Falha ao gerar OFX, mas CSV foi criado"
                else:
                    return None, "Nenhuma transação encontrada no PDF"
            
            elif formato_destino == 'csv' and transacoes:
                return csv_path, None
            
            elif formato_destino == 'txt':
                return txt_debug, None
            
            else:
                return None, f"Conversão de PDF para {formato_destino} não implementada"

        return None, f"Conversão de {formato_origem} para {formato_destino} não suportada"


# Funções de interface pública
def converter_arquivo(arquivo_path: str, formato_destino: str, 
                      output_dir: Optional[str] = None, modo_rapido: bool = True) -> Tuple[Optional[str], Optional[str]]:
    """
    Converte um arquivo para o formato desejado.
    """
    return ConversorService.converter(arquivo_path, formato_destino, output_dir, modo_rapido)


def get_formatos_destino(formato_origem: str) -> List[str]:
    return ConversorService.get_formatos_destino(formato_origem)