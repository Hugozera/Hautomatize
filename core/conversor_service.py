# C:\Hautomatize\core\conversor_service.py

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
import csv
from . import conversor_pipeline

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
    TESSDATA_PREFIX = os.path.join(PROJECT_ROOT, 'Tesseract-OCR','tessdata')

    # Configura caminhos - FORÇA o PATH correto
    if os.path.exists(POPPLER_PATH):
        os.environ['PATH'] = POPPLER_PATH + os.pathsep + os.environ.get('PATH', '')
        os.environ['PATH'] = os.environ['PATH'] + os.pathsep + POPPLER_PATH
    
    if os.path.exists(TESSDATA_PREFIX):
        os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX
    
    if os.path.exists(TESSERACT_CMD) and HAS_OCR:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    
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
    def _corrigir_encoding_santander(cls, texto: str) -> str:
        """Corrige problemas de encoding específicos do Santander."""
        if not texto:
            return texto
        
        if isinstance(texto, bytes):
            try:
                return texto.decode('latin1')
            except:
                try:
                    return texto.decode('utf-8', errors='ignore')
                except:
                    pass
        
        replacements = {
            '': '', '': '', '': '', '': '', '': '', '': '',
            '': '', '': '', '': '', '': '', '': '', '': '',
            '': '', '': '', '': '', '': '', '': '', '': '',
            '': '', '': '', '': '', '': '', '': '', '': '',
            '': '', '': '', '': '', '': '', '': '', '': '',
            '': '', '': '', ' ': ' ', '¡': '', '¢': '', '£': '',
            '¤': '', '¥': '', '¦': '', '§': '', '¨': '', '©': '',
            'ª': '', '«': '', '¬': '', '­': '', '®': '', '¯': '',
            '°': '', '±': '', '²': '', '³': '', '´': '', 'µ': '',
            '¶': '', '·': '', '¸': '', '¹': '', 'º': '', '»': '',
            '¼': '', '½': '', '¾': '', '¿': '',
        }
        
        for old, new in replacements.items():
            texto = texto.replace(old, new)
        
        texto = ''.join(char for char in texto if ord(char) >= 32 or char in '\n\r\t')
        
        return texto

    @classmethod
    def _limpar_texto_corrompido_hibrido(cls, texto: str, banco: str = "CAIXA") -> str:
        """Limpa texto corrompido de forma HÍBRIDA."""
        if not texto:
            return texto
        
        if banco.upper() == "CAIXA":
            # CORREÇÃO 1: "351" no início de datas deve ser "31"
            texto = re.sub(r'35(\d{2}/\d{2}/\d{2,4})', r'3\1', texto)
            
            # CORREÇÃO 2: "351" no início de documentos (6 dígitos) deve ser "31"
            texto = re.sub(r'\b35(\d{5})\b', r'31\1', texto)
            
            # CORREÇÃO 3: "350" no início deve ser "30"
            texto = re.sub(r'\b350(\d{4})\b', r'30\1', texto)
            
            # CORREÇÃO 4: Valores com dígitos extras (359,80 → 39,80)
            def corrigir_valor_caixa(match):
                digito = match.group(2)
                resto = match.group(3)
                return f"3{digito}{resto}"
            
            texto = re.sub(r'(\b35)(\d)(,\d{2}\b)', corrigir_valor_caixa, texto)
            
            # CORREÇÃO 5: Valores com centavos extras (15.275,356 → 15.275,36)
            texto = re.sub(r',(\d{3})', r',\1', texto)
            
            # CORREÇÃO 6: Caracteres especiais nos nomes
            texto = texto.replace('*+**', '***')
            texto = texto.replace('*1**', '***')
            texto = texto.replace('t*', '')
            texto = texto.replace('1**', '***')
            
            # CORREÇÃO 7: Símbolos de moeda errados
            texto = texto.replace('€', 'C')
            texto = texto.replace('¢', 'C')
            
        elif banco.upper() == "SANTANDER":
            texto = cls._corrigir_encoding_santander(texto)
            
            texto = re.sub(r'Per[ií]odos?:?\s*(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})', 
                          r'Período: \1 a \2', texto, flags=re.IGNORECASE)
            texto = re.sub(r'Saldo dispon[ií]vel', r'Saldo disponível', texto, flags=re.IGNORECASE)
        
        elif banco.upper() == "STONE":
            texto = re.sub(r'D[eé]bito', r'Débito', texto, flags=re.IGNORECASE)
            texto = re.sub(r'Cr[eé]dito', r'Crédito', texto, flags=re.IGNORECASE)
            texto = re.sub(r'Transfer[êe]ncia', r'Transferência', texto, flags=re.IGNORECASE)
        
        elif banco.upper() == "ITAU":
            texto = re.sub(r'dispon#vel', r'disponível', texto, flags=re.IGNORECASE)
        
        # REGRAS GENÉRICAS
        # Remove espaços múltiplos mas preserva quebras de linha
        linhas = texto.split('\n')
        linhas_limpas = []
        for linha in linhas:
            linha = re.sub(r' +', ' ', linha)
            if linha.strip():
                linhas_limpas.append(linha)
        
        texto = '\n'.join(linhas_limpas)
        
        return texto

    @classmethod
    def _corrigir_espacos_e_caracteres(cls, texto: str) -> str:
        """Corrige espaços ausentes e caracteres especiais após o OCR."""
        if not texto:
            return texto
        
        replacements = [
            (r'CIELMC\.CD', 'CIEL MC CD'),
            (r'CIELVSCD', 'CIEL VS CD'),
            (r'CIELELCD', 'CIEL EL CD'),
            (r'PIXRECEBIDO', 'PIX RECEBIDO'),
            (r'CREDPIXCHAVE', 'CRED PIX CHAVE'),
            (r'TARPIX', 'TAR PIX'),
            (r'PAGBOLETOIBC', 'PAG BOLETO IBC'),
            (r'PAGORGAOSGOVIBC', 'PAG ORGAOS GOV IBC'),
            (r'SLZC', 'SANTA LUZIA COMERC'),
            (r'SNLZC', 'SANTA LUZIA COMERC'),
            (r'SLCM', 'SANTA LUZIA COMERC'),
        ]
        
        for pattern, replacement in replacements:
            texto = re.sub(pattern, replacement, texto, flags=re.IGNORECASE)
        
        texto = re.sub(r'//', '/', texto)
        texto = re.sub(r'(\d+,\d{2})C', r'\1 C', texto)
        texto = re.sub(r'(\d+,\d{2})D', r'\1 D', texto)
        
        return texto

    @classmethod
    def corrigir_valor_br(cls, valor_str: str) -> float:
        """Converte string de valor brasileiro para float."""
        if not valor_str:
            return 0.0
        
        valor_str = re.sub(r'[R\$\s]', '', valor_str)
        
        if re.match(r'35\d,\d{2}', valor_str):
            valor_str = '3' + valor_str[2:]
        
        if valor_str.count(',') == 2:
            partes = valor_str.split(',')
            if len(partes) == 3:
                valor_str = f"{partes[0]}.{partes[1]},{partes[2]}"
        
        valor_str = re.sub(r'(\d+)\.(\d{3})(\d)(\d{3})', r'\1.\2\4', valor_str)
        valor_str = re.sub(r'(\d+)\.(\d{3})0,(\d{2})', r'\1.\2,\3', valor_str)
        
        if ',' in valor_str and len(valor_str.split(',')[1]) > 2:
            parte_int, parte_dec = valor_str.split(',')
            valor_str = f"{parte_int},{parte_dec[:2]}"
        
        valor_str = valor_str.replace('/', ',')
        
        if '.' in valor_str and ',' in valor_str:
            try:
                valor_limpo = valor_str.replace('.', '').replace(',', '.')
                return float(valor_limpo)
            except:
                pass
        
        elif ',' in valor_str and '.' not in valor_str:
            try:
                valor_limpo = valor_str.replace(',', '.')
                return float(valor_limpo)
            except:
                pass
        
        elif '.' in valor_str and ',' not in valor_str:
            partes = valor_str.split('.')
            if len(partes) == 2 and len(partes[1]) in [2, 3, 5]:
                if len(partes[1]) == 2:
                    valor_limpo = valor_str.replace('.', '')
                    valor_limpo = valor_limpo[:-2] + '.' + valor_limpo[-2:]
                    try:
                        return float(valor_limpo)
                    except:
                        pass
                else:
                    valor_limpo = valor_str.replace('.', '')
                    try:
                        return float(valor_limpo)
                    except:
                        pass
        
        try:
            valor_limpo = re.sub(r'[^\d,]', '', valor_str)
            valor_limpo = valor_limpo.replace(',', '.')
            return float(valor_limpo)
        except:
            return 0.0

    @classmethod
    def extrair_transacoes_avancado(cls, texto: str) -> List[Dict]:
        """
        Extrai transações de extratos bancários de forma robusta.
        Versão otimizada para CAIXA.
        """
        if not texto:
            return []

        linhas = texto.split('\n')
        transacoes = []
        transacao_em_construcao = None

        # Regex mais específicos
        regex_data_hora = re.compile(r'(\d{2})/(\d{2})/(\d{4})\s*-\s*(\d{2}:\d{2}:\d{2})')
        regex_doc = re.compile(r'\b(\d{6})\b')  # Documentos têm 6 dígitos
        regex_valor_br = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})')  # Formato brasileiro: 1.234,56
        regex_saldo = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s+([CD])$')  # Valor com C/D no final da linha
        regex_tipo_transacao = re.compile(r'(CIEL|PIX|TAR|CRED|DEB|PAG)')

        for i, linha in enumerate(linhas):
            linha_original = linha
            linha = linha.strip()
            
            # Pular linhas irrelevantes
            if (len(linha) < 10 or 
                'CAIXA' in linha or 
                'PAGE BREAK' in linha or 
                'Alô CAIXA' in linha or
                'Extrato por periodo' in linha or
                'Cliente' in linha or
                'Conta' in linha):
                continue

            # Buscar data e hora
            data_hora_match = regex_data_hora.search(linha)
            
            if data_hora_match:
                # Se estava construindo uma transação, finaliza
                if transacao_em_construcao:
                    transacao_final = cls._finalizar_transacao_caixa(transacao_em_construcao)
                    if transacao_final:
                        transacoes.append(transacao_final)
                    transacao_em_construcao = None

                dia, mes, ano, hora = data_hora_match.groups()
                data_ofx = f"{ano}{mes}{dia}"

                # Extrair documento (6 dígitos após a hora)
                partes = linha.split()
                documento = ''
                for j, parte in enumerate(partes):
                    if regex_doc.match(parte):
                        documento = parte
                        break

                # Extrair descrição (tudo entre documento e valor)
                descricao = ''
                valor_str = ''
                saldo_str = ''
                tipo_saldo = ''

                # Encontrar posição do documento e dos valores
                if documento:
                    pos_doc = linha.find(documento) + len(documento)
                    resto = linha[pos_doc:].strip()
                    
                    # Procurar valores no resto da linha
                    valores = regex_valor_br.findall(resto)
                    if len(valores) >= 1:
                        valor_str = valores[0]
                        
                        # Verificar se tem saldo no final
                        saldo_match = regex_saldo.search(resto)
                        if saldo_match:
                            saldo_str = saldo_match.group(1)
                            tipo_saldo = saldo_match.group(2)
                        
                        # Descrição é o que está entre documento e primeiro valor
                        pos_primeiro_valor = resto.find(valor_str)
                        if pos_primeiro_valor > 0:
                            descricao = resto[:pos_primeiro_valor].strip()
                            
                            # Remover códigos do CIEL se presentes
                            descricao = re.sub(r'\b00\d{4}\b', '', descricao)
                            descricao = re.sub(r'\s+', ' ', descricao).strip()

                # Se não conseguiu extrair com o método acima, tenta abordagem mais simples
                if not valor_str:
                    # Pega os últimos 2 valores numéricos (valor e saldo)
                    todos_valores = regex_valor_br.findall(linha)
                    if len(todos_valores) >= 2:
                        valor_str = todos_valores[-2]  # Penúltimo é o valor da transação
                        
                        # Descrição é tudo entre documento e este valor
                        if documento:
                            pos_doc = linha.find(documento) + len(documento)
                            resto = linha[pos_doc:].strip()
                            pos_valor = resto.find(valor_str)
                            if pos_valor > 0:
                                descricao = resto[:pos_valor].strip()
                            else:
                                descricao = resto
                        else:
                            descricao = linha

                if valor_str:
                    valor = cls.corrigir_valor_br(valor_str)
                    
                    # Determinar tipo baseado na descrição
                    if any(palavra in descricao.upper() for palavra in ['TAR', 'PAG', 'DEB', 'D']):
                        tipo = 'DEBIT'
                        valor = -abs(valor)
                    else:
                        tipo = 'CREDIT'
                        valor = abs(valor)

                    transacao_em_construcao = {
                        'data': data_ofx,
                        'valor': valor,
                        'tipo': tipo,
                        'descricao': descricao,
                        'documento': documento,
                        'hora': hora,
                        'linha_original': linha_original,
                        'saldo': saldo_str if saldo_str else None,
                        'tipo_saldo': tipo_saldo if tipo_saldo else None
                    }

        # Finalizar última transação
        if transacao_em_construcao:
            transacao_final = cls._finalizar_transacao_caixa(transacao_em_construcao)
            if transacao_final:
                transacoes.append(transacao_final)

        # Pós-processamento
        transacoes = cls._processar_transacoes_caixa(transacoes)
        
        return transacoes

    @classmethod
    def _finalizar_transacao_caixa(cls, transacao: Dict) -> Optional[Dict]:
        """Finaliza uma transação específica da CAIXA."""
        if not transacao or transacao['valor'] == 0.0:
            return None

        # Limpar descrição
        descricao = transacao.get('descricao', '')
        
        # Remover códigos de documento que possam estar na descrição
        if transacao.get('documento'):
            descricao = descricao.replace(transacao['documento'], '')
        
        # Remover valores que possam estar na descrição
        descricao = re.sub(r'\d{1,3}(?:\.\d{3})*,\d{2}', '', descricao)
        
        # Remover espaços extras e padronizar
        descricao = re.sub(r'\s+', ' ', descricao).strip().upper()
        
        # Limitar tamanho
        descricao = descricao[:80]
        
        transacao['descricao'] = descricao if descricao else 'TRANSACAO'

        # Gerar FITID único
        fitid = f"{transacao['data']}{int(abs(transacao['valor']) * 100):08d}"
        if transacao.get('documento'):
            fitid = f"{fitid}{transacao['documento']}"
        if transacao.get('hora'):
            fitid = f"{fitid}{transacao['hora'].replace(':', '')}"
        else:
            fitid = f"{fitid}{abs(hash(descricao)) % 10000:04d}"
        
        transacao['fitid'] = fitid[:30]

        return transacao

    @classmethod
    def _processar_transacoes_caixa(cls, transacoes: List[Dict]) -> List[Dict]:
        """Processa e valida transações da CAIXA."""
        if not transacoes:
            return []

        # Remover duplicatas
        transacoes_unicas = []
        vistos = set()
        
        for t in transacoes:
            # Chave única: data + valor absoluto + hash da descrição
            chave = f"{t['data']}_{abs(round(t['valor'] * 100))}_{abs(hash(t['descricao'][:20]))}"
            
            if chave not in vistos:
                vistos.add(chave)
                
                # Garantir que campos obrigatórios existam
                t['tipo'] = t.get('tipo', 'UNKNOWN')
                t['documento'] = t.get('documento', '')
                
                transacoes_unicas.append(t)

        # Ordenar por data
        transacoes_unicas.sort(key=lambda x: x['data'])

        # Validar consistência dos saldos (opcional)
        saldo_acumulado = 0
        for t in transacoes_unicas:
            saldo_acumulado += t['valor']
            t['saldo_acumulado'] = round(saldo_acumulado, 2)

        return transacoes_unicas

    @classmethod
    def _extrair_descricao(cls, linha: str, data_match, valor_match=None, doc_match=None) -> str:
        """Extrai a descrição removendo data, documento e valor."""
        desc = linha
        
        if data_match:
            desc = desc.replace(data_match.group(0), '')
        
        if valor_match:
            desc = desc.replace(valor_match.group(1), '')
        
        if doc_match:
            desc = desc.replace(doc_match.group(1), '')
        
        desc = re.sub(r'\d{2}:\d{2}:\d{2}', '', desc)
        desc = re.sub(r'[^\w\s\-/]', ' ', desc)
        desc = re.sub(r'\s+', ' ', desc).strip()
        
        return desc

    @classmethod
    def _finalizar_transacao(cls, transacao: Dict) -> Dict:
        """Finaliza uma transação, garantindo todos os campos necessários."""
        if not transacao:
            return transacao
        
        if transacao['valor'] == 0.0:
            for linha in transacao['linhas']:
                valor_match = re.search(r'(\d{1,3}(?:[.]\d{3})*[,]\d{2})', linha)
                if valor_match:
                    valor = cls.corrigir_valor_br(valor_match.group(1))
                    
                    if 'D' in linha or 'DEB' in linha.upper() or 'PAG' in linha.upper():
                        transacao['tipo'] = 'DEBIT'
                        transacao['valor'] = -abs(valor)
                    else:
                        transacao['tipo'] = 'CREDIT'
                        transacao['valor'] = abs(valor)
                    break
        
        if not transacao.get('descricao') and transacao.get('linhas'):
            primeira_linha = transacao['linhas'][0]
            desc = re.sub(r'\d{2}/\d{2}/\d{4}', '', primeira_linha)
            desc = re.sub(r'\d{2}:\d{2}:\d{2}', '', desc)
            desc = re.sub(r'[^\w\s\-/]', ' ', desc)
            transacao['descricao'] = re.sub(r'\s+', ' ', desc).strip()
        
        if 'linhas' in transacao:
            del transacao['linhas']
        
        if not transacao.get('documento'):
            transacao['documento'] = ''
        
        if transacao.get('descricao'):
            transacao['descricao'] = transacao['descricao'].upper()
        
        return transacao

    @classmethod
    def _remover_duplicatas_transacoes(cls, transacoes: List[Dict]) -> List[Dict]:
        """Remove transações duplicadas baseado em data e valor."""
        transacoes_unicas = []
        vistos = set()
        
        for t in transacoes:
            chave = f"{t['data']}_{abs(round(t['valor'] * 100))}"
            
            if chave not in vistos:
                vistos.add(chave)
                transacoes_unicas.append(t)
            else:
                for i, existente in enumerate(transacoes_unicas):
                    chave_existente = f"{existente['data']}_{abs(round(existente['valor'] * 100))}"
                    if chave_existente == chave:
                        if len(t.get('descricao', '')) > len(existente.get('descricao', '')):
                            transacoes_unicas[i] = t
                        break
        
        return transacoes_unicas

    @classmethod
    def gerar_ofx(cls, transacoes: List[Dict], ofx_path: str, banco_id: str = "104", 
                  agencia: str = "0000", conta: str = "99999999") -> bool:
        """Gera arquivo OFX no formato padrão ouro."""
        try:
            if not transacoes:
                return False

            transacoes.sort(key=lambda x: x['data'])
            data_inicio = min(t['data'] for t in transacoes)
            data_fim = max(t['data'] for t in transacoes)
            
            agora = datetime.now()
            data_server = agora.strftime("%Y%m%d%H%M%S")

            with open(ofx_path, 'w', encoding='utf-8') as f:
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

                f.write("<OFX>\n")
                
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
                
                f.write("  <BANKMSGSRSV1>\n")
                f.write("    <STMTTRNRS>\n")
                f.write("      <TRNUID>0</TRNUID>\n")
                f.write("      <STATUS>\n")
                f.write("        <CODE>0</CODE>\n")
                f.write("        <SEVERITY>INFO</SEVERITY>\n")
                f.write("      </STATUS>\n")
                f.write("      <STMTRS>\n")
                f.write(f"        <CURDEF>BRL</CURDEF>\n")
                
                f.write("        <BANKACCTFROM>\n")
                f.write(f"          <BANKID>{banco_id}</BANKID>\n")
                f.write(f"          <ACCTID>{conta}</ACCTID>\n")
                f.write("          <ACCTTYPE>CHECKING</ACCTTYPE>\n")
                f.write("        </BANKACCTFROM>\n")
                
                f.write("        <BANKTRANLIST>\n")
                f.write(f"          <DTSTART>{data_inicio}</DTSTART>\n")
                f.write(f"          <DTEND>{data_fim}</DTEND>\n")
                
                for i, t in enumerate(transacoes):
                    valor_str = f"{t['valor']:.2f}".replace('.', ',')
                    
                    f.write("          <STMTTRN>\n")
                    f.write(f"            <TRNTYPE>{t['tipo']}</TRNTYPE>\n")
                    f.write(f"            <DTPOSTED>{t['data']}</DTPOSTED>\n")
                    f.write(f"            <TRNAMT>{valor_str}</TRNAMT>\n")
                    
                    fitid = t.get('fitid', f"{t['data']}{i:06d}")
                    f.write(f"            <FITID>{fitid}</FITID>\n")
                    
                    documento = t.get('documento', t.get('checknum', f"{i+1:06d}"))
                    f.write(f"            <CHECKNUM>{documento}</CHECKNUM>\n")
                    
                    f.write(f"            <MEMO>{t.get('descricao', 'TRANSACAO')}</MEMO>\n")
                    f.write("          </STMTTRN>\n")
                
                f.write("        </BANKTRANLIST>\n")
                
                saldo_final = sum(t['valor'] for t in transacoes)
                saldo_str = f"{saldo_final:.2f}".replace('.', ',')
                
                f.write("        <LEDGERBAL>\n")
                f.write(f"          <BALAMT>{saldo_str}</BALAMT>\n")
                f.write(f"          <DTASOF>{data_fim}</DTASOF>\n")
                f.write("        </LEDGERBAL>\n")
                
                f.write("      </STMTRS>\n")
                f.write("    </STMTTRNRS>\n")
                f.write("  </BANKMSGSRSV1>\n")
                f.write("</OFX>\n")

            return True

        except Exception:
            return False

    @classmethod
    def _salvar_como_csv(cls, transacoes: List[Dict], csv_path: str) -> bool:
        """Salva transações em CSV."""
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Data', 'Tipo', 'Valor', 'Descrição', 'Documento', 'FITID'])
                for t in transacoes:
                    writer.writerow([
                        t.get('data', ''),
                        t.get('tipo', ''),
                        f"{t.get('valor', 0):.2f}",
                        t.get('descricao', ''),
                        t.get('documento', ''),
                        t.get('fitid', '')
                    ])
            return True
        except Exception:
            return False

    @classmethod
    def _salvar_txt_universal(cls, texto: str, txt_path: str, banco: str = "DESCONHECIDO") -> bool:
        """Salva o texto extraído em TXT com correções específicas do banco."""
        try:
            texto_limpo = cls._limpar_texto_corrompido_hibrido(texto, banco)
            texto_limpo = cls._corrigir_espacos_e_caracteres(texto_limpo)
            
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(texto_limpo)
            return True
        except Exception:
            return False


# ========== FUNÇÕES DE INTERFACE PÚBLICA ==========

def converter_arquivo(arquivo_path: str, formato_destino: str,
                      output_dir: Optional[str] = None, usar_ocr: bool = True,
                      dpi: int = 300) -> Tuple[Optional[str], Optional[str]]:
    """
    Converte um arquivo para o formato desejado.
    - Gera TXT usando o pipeline do conversor_pipeline
    - Extrai transações e gera OFX/CSV quando solicitado
    """
    if not output_dir:
        output_dir = os.path.join(os.path.dirname(arquivo_path), 'convertidos')
    os.makedirs(output_dir, exist_ok=True)

    origem_ext = os.path.splitext(arquivo_path)[1].lower()
    texto = ''
    txt_path = None

    if origem_ext == '.txt':
        try:
            with open(arquivo_path, 'r', encoding='utf-8', errors='replace') as f:
                texto = f.read()
            txt_path = arquivo_path
        except Exception as e:
            return None, f"Erro ao ler TXT original: {e}"
    else:
        txt_path, erro = conversor_pipeline.convert_pdf_to_txt(arquivo_path, out_dir=output_dir, usar_ocr=usar_ocr, dpi=dpi)
        if not txt_path:
            return None, erro

        try:
            with open(txt_path, 'r', encoding='utf-8', errors='replace') as f:
                texto = f.read()
        except Exception as e:
            return None, f"Erro ao ler TXT gerado: {e}"

    banco_detectado = 'CAIXA'
    texto_limpo = ConversorService._limpar_texto_corrompido_hibrido(texto, banco_detectado)
    texto_limpo = ConversorService._corrigir_espacos_e_caracteres(texto_limpo)

    nome_base = os.path.splitext(os.path.basename(arquivo_path))[0]
    txt_universal_path = os.path.join(output_dir, f"{nome_base}_texto_universal.txt")
    try:
        ConversorService._salvar_txt_universal(texto, txt_universal_path, banco_detectado)
    except Exception:
        pass

    if formato_destino == 'txt':
        return txt_universal_path if os.path.exists(txt_universal_path) else txt_path, None

    transacoes = ConversorService.extrair_transacoes_avancado(texto_limpo)

    csv_path = os.path.join(output_dir, f"{nome_base}.csv")
    if transacoes:
        ConversorService._salvar_como_csv(transacoes, csv_path)

    if formato_destino == 'ofx':
        if not transacoes:
            return (txt_universal_path if os.path.exists(txt_universal_path) else txt_path), "Nenhuma transação encontrada para gerar OFX"

        banco_id_map = {
            'CAIXA': '104', 'BRADESCO': '237', 'ITAU': '341', 'SANTANDER': '033', 'BRASIL': '001', 'STONE': '165'
        }
        banco_id = banco_id_map.get(banco_detectado, '104')
        ofx_path = os.path.join(output_dir, f"{nome_base}.ofx")
        ok = ConversorService.gerar_ofx(transacoes, ofx_path, banco_id=banco_id)
        if ok:
            return ofx_path, None
        else:
            return (csv_path if os.path.exists(csv_path) else txt_universal_path), "Falha ao gerar OFX"

    if formato_destino == 'csv':
        if os.path.exists(csv_path):
            return csv_path, None
        else:
            return None, "CSV não gerado"

    return None, f"Formato {formato_destino} não suportado"


def get_formatos_destino(formato_origem: str) -> List[str]:
    """Retorna lista de formatos disponíveis para conversão."""
    return ConversorService.get_formatos_destino(formato_origem)


def processar_pasta(pasta_path: str, formato_destino: str = 'ofx', 
                    output_dir: Optional[str] = None, usar_ocr: bool = True,
                    dpi: int = 300) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """
    Processa todos os PDFs de uma pasta.
    Retorna lista de tuplas (arquivo, caminho_resultado, erro).
    """
    if not os.path.exists(pasta_path):
        return [(pasta_path, None, f"Pasta não encontrada: {pasta_path}")]
    
    if not output_dir:
        output_dir = os.path.join(pasta_path, 'convertidos')
    
    os.makedirs(output_dir, exist_ok=True)
    
    resultados = []
    arquivos = [f for f in os.listdir(pasta_path) if f.lower().endswith('.pdf')]
    
    for arquivo in arquivos:
        arquivo_path = os.path.join(pasta_path, arquivo)
        resultado, erro = converter_arquivo(arquivo_path, formato_destino, output_dir, usar_ocr=usar_ocr, dpi=dpi)
        resultados.append((arquivo, resultado, erro))
    
    return resultados


if __name__ == "__main__":
    import sys
    
    def print_ajuda():
        print("""
Uso: python conversor_service.py <caminho> [formato] [--output DIR]

Argumentos:
  caminho               Caminho do arquivo PDF ou pasta com PDFs
  formato               Formato de saída (ofx, csv, txt) [padrão: ofx]
  --output DIR          Pasta de saída [padrão: mesma do arquivo / subpasta 'convertidos']

EXEMPLOS:
  python conversor_service.py extrato.pdf
  python conversor_service.py extrato.pdf csv
  python conversor_service.py C:\\PDFs\\ --output C:\\Saida
        """)
    
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        print_ajuda()
        sys.exit(0)
    
    caminho = sys.argv[1]
    formato = 'ofx'
    output_dir = None
    
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ['--output', '-o'] and i + 1 < len(sys.argv):
            output_dir = sys.argv[i + 1]
            i += 2
        elif arg in ['csv', 'ofx', 'txt']:
            formato = arg
            i += 1
        else:
            i += 1
    
    if os.path.isdir(caminho):
        processar_pasta(caminho, formato, output_dir)
    else:
        resultado, erro = converter_arquivo(caminho, formato, output_dir)
        if resultado:
            print(f"\n✅ Sucesso! Arquivo gerado: {resultado}")
        else:
            print(f"\n❌ Erro: {erro}")