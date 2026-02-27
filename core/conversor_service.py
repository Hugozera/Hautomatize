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
from .learning_store import LearningStore
import pkgutil
import importlib
import inspect
import hashlib
import json
from collections import OrderedDict

# Cache for parser instances to avoid repeated heavy imports during conversion
_PARSER_INSTANCES = None

# Cache for bank detection based on text hash to avoid re-running detection on identical texts
_DETECTION_CACHE = OrderedDict()
_DETECTION_CACHE_MAX = 1024

def _load_parser_instances():
    """Load and cache parser instances from core.parsers package."""
    global _PARSER_INSTANCES
    if _PARSER_INSTANCES is not None:
        return _PARSER_INSTANCES
    instances = []
    try:
        from . import parsers as parsers_pkg
        from .parsers.base_parser import BaseParser
        for finder, name, ispkg in pkgutil.iter_modules(parsers_pkg.__path__):
            try:
                mod = importlib.import_module(f"{parsers_pkg.__name__}.{name}")
            except Exception:
                continue
            for attr in dir(mod):
                try:
                    obj = getattr(mod, attr)
                    if inspect.isclass(obj) and issubclass(obj, BaseParser) and obj is not BaseParser:
                        try:
                            instances.append(obj())
                        except Exception:
                            continue
                except Exception:
                    continue
    except Exception:
        pass
    _PARSER_INSTANCES = instances
    return _PARSER_INSTANCES

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
        
                def get_formatos_destino(formato_origem: str) -> List[str]:
                    """Module-level wrapper for backward compatibility with views importing this symbol."""
                    return ConversorService.get_formatos_destino(formato_origem)

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
    def _normalizar_para_txt_padrao(cls, texto_bruto: str, banco_detectado: str = None) -> str:
        """
        Converte o texto bruto de qualquer extrato para um formato TXT padrão e universal.
        Formato de saída: DATA;VALOR;TIPO;DESCRICAO;DOCUMENTO;SALDO
        """
        linhas_padrao = []
        
        # --- ETAPA 1: Limpeza pesada e correções específicas de encoding ---
        texto_limpo = cls._limpar_texto_corrompido_hibrido(texto_bruto, banco_detectado if banco_detectado else "CAIXA")
        texto_limpo = cls._corrigir_espacos_e_caracteres(texto_limpo)
        
        # Remove cabeçalhos e rodapés
        linhas = texto_limpo.split('\n')
        linhas_filtradas = []
        for linha in linhas:
            linha_lower = linha.lower()
            # Lista expandida de termos a ignorar
            if any(ignorar in linha_lower for ignorar in [
                'página', 'pagina', 'page break', 'lançamentos', 'lançamento',
                'data', 'histórico', 'documento', 'agência', 'conta', 'cpf', 'cnpj',
                'autenticação', 'autenticacao', 'código', 'codigo', 'sac', 'ouvidoria',
                '0800', 'telefone', 'whatsapp', 'e-mail', 'email', 'www', 'http',
                'gerado em', 'emitido em', 'posicao', 'posição', 'consolidado',
                'folha', 'total disponível', 'limite da conta', 'aplicações',
                'saldo anterior', 'saldo do dia', 'saldo dia'
            ]):
                continue
            if len(linha.strip()) < 8:
                continue
            linhas_filtradas.append(linha)
        
        texto_sem_cabecalho = '\n'.join(linhas_filtradas)

        # --- NOVO: Reconstruir páginas com extração em colunas (DATA / TIPO / LANÇAMENTO / VALOR / SALDO)
        def _reconstruct_columnar_page(page_text: str) -> str:
            # Detect common headers (variants)
            headers = ['DATA', 'TIPO', 'LANÇAMENTO', 'LANCAMENTO', 'LANÇAMENTO', 'VALOR', 'SALDO']
            up = page_text.upper()
            # find indices of headers
            hdr_positions = {}
            for h in ['DATA', 'TIPO', 'LAN', 'VALOR', 'SALDO']:
                idx = up.find(h)
                if idx >= 0:
                    hdr_positions[h] = idx

            # Simple heuristic: if we have at least DATA and VALOR present, attempt reconstruction
            if 'DATA' not in hdr_positions or 'VALOR' not in hdr_positions:
                return page_text

            # try to slice blocks by locating the header keywords in order
            # fallback: split by known header words
            parts = {}
            try:
                # find header tokens in the original case-insensitive text
                tokens = ['DATA', 'TIPO', 'LANÇAMENTO', 'LANCAMENTO', 'VALOR', 'SALDO']
                locs = []
                for t in tokens:
                    m = re.search(rf"\b{t}\b", page_text, flags=re.IGNORECASE)
                    if m:
                        locs.append((m.start(), t.upper()))
                locs.sort()
                # build slices between headers
                for i, (pos, t) in enumerate(locs):
                    start = pos + len(t)
                    end = locs[i+1][0] if i+1 < len(locs) else len(page_text)
                    block = page_text[start:end].strip()
                    parts[t] = [ln.strip() for ln in block.split('\n') if ln.strip()]
            except Exception:
                return page_text

            # gather columns
            date_lines = parts.get('DATA', [])
            tipo_lines = parts.get('TIPO', [])
            lanc_lines = parts.get('LANÇAMENTO', []) or parts.get('LANCAMENTO', [])
            valor_lines = parts.get('VALOR', [])
            saldo_lines = parts.get('SALDO', [])

            # normalize valor lines to lines that look like numbers
            regex_val = re.compile(r'-?\d+[\.\d]*,\d{2}')
            valor_filtered = [v for v in valor_lines if regex_val.search(v)]
            if not valor_filtered:
                # try extracting numbers inside lines
                valor_filtered = [v for v in valor_lines]

            N = max(len(date_lines), len(valor_filtered), len(tipo_lines))
            if N == 0:
                return page_text

            # Normalize lanc_lines to have approximately N items by merging if necessary
            try:
                if lanc_lines and len(lanc_lines) > N:
                    # merge from the end until counts match
                    while len(lanc_lines) > N:
                        # merge last two
                        lanc_lines[-2] = lanc_lines[-2] + ' ' + lanc_lines[-1]
                        lanc_lines.pop()
                elif lanc_lines and len(lanc_lines) < N:
                    # pad with empty strings
                    while len(lanc_lines) < N:
                        lanc_lines.append('')
            except Exception:
                pass

            reconstructed = []
            for i in range(N):
                d = date_lines[i] if i < len(date_lines) else ''
                t = tipo_lines[i] if i < len(tipo_lines) else ''
                v = valor_filtered[i] if i < len(valor_filtered) else ''
                s = saldo_lines[i] if i < len(saldo_lines) else ''
                desc = lanc_lines[i] if i < len(lanc_lines) else ''
                # collapse multiple spaces and remove header tokens
                row = f"{d} {v} {t} {desc} {s}".strip()
                row = re.sub(r'\s+', ' ', row)
                reconstructed.append(row)

            return '\n'.join(reconstructed)

        # Apply reconstruction per page
        pages = texto_sem_cabecalho.split('\n=== PAGE BREAK ===\n')
        new_pages = []
        for ptext in pages:
            new_pages.append(_reconstruct_columnar_page(ptext))
        texto_sem_cabecalho = '\n=== PAGE BREAK ===\n'.join(new_pages)

        # --- ETAPA 2: Detectar transações ---
        # Regex para encontrar datas no formato brasileiro DD/MM/AAAA ou DD/MM/AA
        regex_data_hora = re.compile(
            r'(\d{2})[/-](\d{2})[/-](\d{2,4})'  # Data: DD/MM/AAAA ou DD/MM/AA
            r'(?:[\s-]+(\d{2}:\d{2}(?::\d{2})?))?'  # Hora opcional
        )
        
        # Regex APENAS para números com separador de milhar e vírgula decimal: 1.234,56 ou 1234,56
        regex_valor_br = re.compile(r'\b(\d{1,3}(?:\.\d{3})*,\d{2})\b')
        
        # Regex para identificar se é débito (palavras-chave mais completas)
        regex_debito = re.compile(r'\b(DEB|DEBIT|DEBITO|DÉBITO|PAG|PAGAMENTO|TAR|TARIFA|SAQUE|RETIRADA|PAG\.?)\b', re.IGNORECASE)

        # Regex para capturar 'D' ou 'C' no final da linha (isolado)
        # Require a boundary before the letter to avoid matching 'D' inside words
        regex_tipo_final = re.compile(r'\b([DC])\s*$', re.IGNORECASE)
        
        # Regex para número de documento (6 dígitos)
        regex_documento = re.compile(r'\b(\d{6})\b')

        # Processar linha por linha
        for raw_linha in texto_sem_cabecalho.split('\n'):
            linha = raw_linha.strip()
            if not linha:
                continue

            # Se a linha contém múltiplas transações (várias datas), quebramos em segmentos
            # Ex.: quando o PDF extraiu duas linhas visuais numa única linha de texto.
            segmentos = []
            try:
                date_iter = list(regex_data_hora.finditer(linha))
                if len(date_iter) > 1:
                    for idx, m in enumerate(date_iter):
                        start = m.start()
                        end = date_iter[idx + 1].start() if idx + 1 < len(date_iter) else len(linha)
                        seg = linha[start:end].strip()
                        if seg:
                            segmentos.append(seg)
                else:
                    segmentos = [linha]
            except Exception:
                segmentos = [linha]

            for linha in segmentos:
                linha = linha.strip()
                if not linha:
                    continue

            # --- Encontrar data na linha ---
            data_match = regex_data_hora.search(linha)
            if not data_match:
                continue
            
            dia, mes, ano, hora = data_match.groups()
            
            # Normalizar ano para 4 dígitos
            if len(ano) == 2:
                if int(ano) < 70:
                    ano = '20' + ano
                else:
                    ano = '19' + ano
            # Normalizar hora para HHMMSS (padronizar quando hora for opcional)
            hora_str = '000000'
            if hora:
                parts = hora.split(':')
                if len(parts) == 2:
                    parts.append('00')
                # garantir dois dígitos
                hora_str = ''.join(p.zfill(2) for p in parts[:3])

            data_ofx = f"{ano}{mes}{dia}{hora_str}"

            # --- Extrair TODOS os valores da linha ---
            todos_valores = regex_valor_br.findall(linha)
            
            # Se não tem valor, não é uma transação
            if not todos_valores:
                continue
            
            # Para a CAIXA, o padrão é: [valor da transação, saldo]
            if len(todos_valores) >= 2:
                valor_transacao_str = todos_valores[0]  # PRIMEIRO valor é a transação
                saldo_str = todos_valores[-1]           # ÚLTIMO valor é o saldo
            else:
                valor_transacao_str = todos_valores[0]
                saldo_str = ''
            
            # Converter valor para float
            valor_float = cls.corrigir_valor_br(valor_transacao_str)
            
            # --- Determinar o tipo (Débito/Crédito) de forma mais robusta ---
            # Verificar 3 coisas:
            # 1. Se há 'D' no final da linha
            # 2. Se a descrição contém palavras de débito (DEB, PAG, TAR)
            # 3. Se o caractere após o valor é 'D'
            
            linha_upper = linha.upper()
            tipo = 'CREDITO'  # Padrão é crédito
            valor_final = abs(valor_float)  # Começa com valor positivo
            
            # Verificar se é débito
            is_debito = False
            
            # Verificar 'D' no final da linha
            tipo_match = regex_tipo_final.search(linha)
            if tipo_match and tipo_match.group(1) == 'D':
                is_debito = True
            
            # Verificar palavras-chave de débito (busca por tokens completos)
            if regex_debito.search(linha):
                # Special-case PIX: if line contains PIX, check whether it's recebido (credit) or enviado/pagamento (debit)
                if re.search(r'\bPIX\b', linha, flags=re.IGNORECASE):
                    if re.search(r'\b(RECEB|RECEBIDO|RECEBEU|RECEBER)\b', linha, flags=re.IGNORECASE):
                        is_debito = False
                    elif re.search(r'\b(ENVI|ENVIADO|ENVIAR|PAG|PAGAMENTO|TRANSFER)\b', linha, flags=re.IGNORECASE):
                        is_debito = True
                    else:
                        # fallback to debit when ambiguous
                        is_debito = True
                else:
                    is_debito = True
            
            # Verificar se o valor está próximo de 'D' na linha
            # (útil para casos onde o D está colado no valor)
            for valor in todos_valores:
                pos = linha.find(valor)
                if pos >= 0 and pos + len(valor) < len(linha):
                    resto = linha[pos + len(valor):]
                    # look for a trailing token like 'D' or 'C' or a token starting with D (isolated)
                    m2 = re.match(r'^\s*([DC])\b', resto)
                    if m2 and m2.group(1).upper() == 'D':
                        is_debito = True
                        break
                    # also check if there's a nearby word indicating debit
                    if regex_debito.search(resto):
                        is_debito = True
                        break
            
            if is_debito:
                tipo = 'DEBITO'
                valor_final = -abs(valor_float)  # Negativo para débito

            # --- Extrair Documento ---
            doc_match = regex_documento.search(linha)
            documento = doc_match.group(1) if doc_match else ''
            
            # --- Extrair Descrição (removendo data, valores, documento) ---
            descricao = linha
            # Remove a data
            descricao = regex_data_hora.sub('', descricao)
            # Remove todos os valores encontrados
            for val in todos_valores:
                descricao = descricao.replace(val, '')
            # Remove o documento
            if documento:
                descricao = descricao.replace(documento, '')
            # Remove 'C' e 'D' no final da linha
            descricao = re.sub(r'\s+[CD]\s*$', '', descricao)
            # Remove códigos de transação como 'CRED PIX CHAVE', 'DEB PIX CHAVE', etc.
            descricao = re.sub(r'\b(CRED\s+PIX\s+CHAVE|DEB\s+PIX\s+CHAVE|PIX\s+RECEBIDO|PAG\s+BOLETO\s+IBC)\b', '', descricao, flags=re.IGNORECASE)
            # Limpeza final
            descricao = re.sub(r'[^\w\s\-/]', ' ', descricao)
            descricao = re.sub(r'\s+', ' ', descricao).strip().upper()
            
            # Se a descrição ficou vazia, usa um placeholder
            if not descricao:
                descricao = 'TRANSACAO'
            
            # --- Processar saldo (se existir) ---
            saldo_normalizado = ''
            if saldo_str:
                try:
                    saldo_float = cls.corrigir_valor_br(saldo_str)
                    saldo_normalizado = f"{saldo_float:.2f}"
                except:
                    pass
            
            # --- Montar a linha no formato padrão ---
            linha_padrao = (
                f"{data_ofx};"
                f"{valor_final:.2f};"
                f"{tipo};"
                f"{descricao};"
                f"{documento};"
                f"{saldo_normalizado}"
            )
            
            # Adiciona à lista
            linhas_padrao.append(linha_padrao)

        return '\n'.join(linhas_padrao)

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
                # data padrão com hora incluída (YYYYMMDDHHMMSS)
                hora_norm = hora.replace(':', '') if hora else '000000'
                data_ofx = f"{ano}{mes}{dia}{hora_norm}"

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
                    
                    # Determinar tipo baseado na descrição usando tokens completos
                    # PIX-specific: recebido -> credit, enviado/pagamento -> debit
                    if re.search(r'\bPIX\b', descricao, flags=re.IGNORECASE):
                        if re.search(r'\b(RECEB|RECEBIDO|RECEBEU|RECEBER)\b', descricao, flags=re.IGNORECASE):
                            tipo = 'CREDIT'
                            valor = abs(valor)
                        elif re.search(r'\b(ENVI|ENVIADO|ENVIAR|PAG|PAGAMENTO|TRANSFER|SAQUE)\b', descricao, flags=re.IGNORECASE):
                            tipo = 'DEBIT'
                            valor = -abs(valor)
                        else:
                            # ambiguous PIX -> fall back to credit? choose debit as safer default
                            tipo = 'DEBIT'
                            valor = -abs(valor)
                    elif re.search(r'\b(DEB|DEBIT|DEBITO|DÉBITO|PAG|PAGAMENTO|TAR|TARIFA|SAQUE|RETIRADA)\b', descricao, flags=re.IGNORECASE):
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

        # Gerar FITID único: data já pode conter hora (YYYYMMDDHHMMSS)
        fitid = f"{transacao['data']}{int(abs(transacao['valor']) * 100):08d}"
        if transacao.get('documento'):
            fitid = f"{fitid}{transacao['documento']}"
        # Só acrescenta hora separada quando a data NÃO contém hora (data length == 8)
        if len(str(transacao['data'])) == 8 and transacao.get('hora'):
            fitid = f"{fitid}{transacao['hora'].replace(':', '')}"
        elif len(str(transacao['data'])) == 8:
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
                    # Ensure TRNTYPE is one of 'DEBIT' or 'CREDIT'
                    trntype_raw = str(t.get('tipo', 'CREDIT')).upper()
                    # Accept multiple representations: full words and single-letter codes
                    if trntype_raw in ('DEBITO', 'DEBIT', 'D', 'B'):
                        trntype = 'DEBIT'
                    else:
                        trntype = 'CREDIT'

                    # Use absolute value for TRNAMT; sign is represented by TRNTYPE
                    amt = abs(t.get('valor', 0.0))
                    valor_str = f"{amt:.2f}".replace('.', ',')

                    f.write("          <STMTTRN>\n")
                    f.write(f"            <TRNTYPE>{trntype}</TRNTYPE>\n")
                    f.write(f"            <DTPOSTED>{t['data']}</DTPOSTED>\n")
                    f.write(f"            <TRNAMT>{valor_str}</TRNAMT>\n")

                    fitid = t.get('fitid', f"{t['data']}{i:06d}")
                    f.write(f"            <FITID>{fitid}</FITID>\n")

                    documento = t.get('documento', t.get('checknum', f"{i+1:06d}"))
                    f.write(f"            <CHECKNUM>{documento}</CHECKNUM>\n")

                    # Include 'destino' if provided by the front-end as part of the MEMO
                    memo = t.get('descricao', 'TRANSACAO') or 'TRANSACAO'
                    destino_val = t.get('destino') or t.get('destination') or ''
                    if destino_val:
                        memo = f"{memo} / Dest:{destino_val}"
                    f.write(f"            <MEMO>{memo}</MEMO>\n")
                    f.write("          </STMTTRN>\n")
                
                f.write("        </BANKTRANLIST>\n")
                
                # Calcular saldo final corretamente
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

        except Exception as e:
            print(f"Erro ao gerar OFX: {e}")
            return False

    @classmethod
    def _normalize_transacoes_heuristic(cls, transacoes: List[Dict]) -> List[Dict]:
        """Apply heuristic rules to ensure tipo (DEBIT/CREDIT) and valor signs are correct.

        Rules:
        - If descricao contains PIX and RECEB* -> CREDIT
        - If descricao contains PIX and ENVI*/PAG*/TRANSFER* -> DEBIT
        - If descricao contains debit words (PAGAMENTO, TARIFA, SAQUE, RETIRADA) -> DEBIT
        - If descricao contains credit words (RECEBIDO, DEPOSITO) -> CREDIT
        - If tipo present as single letter 'B' -> DEBIT, 'C' -> CREDIT
        - Fallback: use sign of valor (negative -> DEBIT)
        """
        if not transacoes:
            return transacoes

        for t in transacoes:
            desc = (t.get('descricao') or '')
            val = float(t.get('valor') or 0.0)
            tipo_present = (t.get('tipo') or '').strip().upper()

            decided = None
            # Provided single-letter hints
            if tipo_present in ('B', 'D'):
                decided = 'DEBIT'
            elif tipo_present == 'C':
                decided = 'CREDIT'

            # PIX rules
            if decided is None and re.search(r'\bPIX\b', desc, flags=re.IGNORECASE):
                if re.search(r'\b(RECEB|RECEBIDO|RECEBEU|RECEBER|DEPOSI)\b', desc, flags=re.IGNORECASE):
                    decided = 'CREDIT'
                elif re.search(r'\b(ENVI|ENVIADO|ENVIAR|PAG|PAGAMENTO|TRANSFER|SAQUE)\b', desc, flags=re.IGNORECASE):
                    decided = 'DEBIT'

            # Generic keywords
            if decided is None:
                if re.search(r'\b(PAGAMENTO|PAG|TARIFA|TAR|SAQUE|RETIRADA|DEBITO|DEB|DESPESA)\b', desc, flags=re.IGNORECASE):
                    decided = 'DEBIT'
                elif re.search(r'\b(RECEBIDO|RECEB|DEPOSITO|CREDITO|CRED)\b', desc, flags=re.IGNORECASE):
                    decided = 'CREDIT'

            # Fallback to numeric sign
            if decided is None:
                if val < 0:
                    decided = 'DEBIT'
                else:
                    decided = 'CREDIT'

            # Apply decision
            t['tipo'] = decided
            # Ensure valor sign is consistent: OFX expects absolute TRNAMT and TRNTYPE indicates sign
            if decided == 'DEBIT' and val > 0:
                t['valor'] = -abs(val)
            elif decided == 'CREDIT' and val < 0:
                t['valor'] = abs(val)

        return transacoes

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
                      dpi: int = 300, banco_override: Optional[str] = None,
                      force_quality: bool = False, overwrite_learning: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """
    Converte um arquivo para o formato desejado.
    - Gera TXT usando o pipeline do conversor_pipeline
    - NORMALIZA para o formato TXT PADRÃO UNIVERSAL
    - Extrai transações do TXT PADRÃO e gera OFX/CSV quando solicitado
    """
    if not output_dir:
        output_dir = os.path.join(os.path.dirname(arquivo_path), 'convertidos')
    os.makedirs(output_dir, exist_ok=True)

    origem_ext = os.path.splitext(arquivo_path)[1].lower()
    texto = ''
    txt_path = None
    nome_base = os.path.splitext(os.path.basename(arquivo_path))[0]

    # compute lightweight file properties for learning store
    file_hash = None
    file_size = None
    page_count = None
    try:
        import hashlib
        file_size = os.path.getsize(arquivo_path)
        with open(arquivo_path, 'rb') as fh:
            file_bytes = fh.read()
            file_hash = hashlib.sha256(file_bytes).hexdigest()
    except Exception:
        file_hash = None
        file_size = None

    # page count quick probe (uses fitz if available)
    try:
        if HAS_FITZ:
            import fitz
            doc = fitz.open(arquivo_path)
            page_count = doc.page_count
            doc.close()
    except Exception:
        page_count = None

    # If caller requested forced high-quality or to overwrite learning, skip cached TXT reuse
    skip_cached_text = bool(force_quality or overwrite_learning)
    try:
        if overwrite_learning and file_hash:
            try:
                LearningStore.delete_by_file_hash(file_hash)
            except Exception:
                pass
    except Exception:
        pass
    # If forcing quality, clear detection cache so bank detection runs anew
    try:
        if force_quality:
            try:
                _DETECTION_CACHE.clear()
            except Exception:
                pass
    except Exception:
        pass

    # Try to reuse cached extracted text in the output_dir to avoid re-running OCR
    try:
        possível_txt_universal = os.path.join(output_dir, f"{nome_base}_texto_universal.txt")
        possível_txt_fast = os.path.join(output_dir, f"{nome_base}.txt")
        possível_txt_padrao = os.path.join(output_dir, f"{nome_base}_padrao.txt")
        if not skip_cached_text:
            if os.path.exists(possível_txt_universal):
                with open(possível_txt_universal, 'r', encoding='utf-8', errors='replace') as tf:
                    texto = tf.read()
                txt_path = possível_txt_universal
            elif os.path.exists(possível_txt_fast):
                with open(possível_txt_fast, 'r', encoding='utf-8', errors='replace') as tf:
                    texto = tf.read()
                txt_path = possível_txt_fast
            elif os.path.exists(possível_txt_padrao):
                # padrao file contains normalized TXT; use it as source
                with open(possível_txt_padrao, 'r', encoding='utf-8', errors='replace') as tf:
                    texto = tf.read()
                txt_path = possível_txt_padrao
        else:
            # remove/ignore any existing cached TXT/meta/ofx to force fresh extraction
            try:
                meta_path = os.path.join(output_dir, f"{nome_base}.meta.json")
                ofx_path = os.path.join(output_dir, f"{nome_base}.ofx")
                csv_path = os.path.join(output_dir, f"{nome_base}.csv")
                for p in (possível_txt_universal, possível_txt_fast, possível_txt_padrao, meta_path, ofx_path, csv_path):
                    if os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
            except Exception:
                pass
            texto = ''
            txt_path = None
    except Exception:
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
        # Fast-path: if PyMuPDF (fitz) is available, try extracting embedded text first
        # Only run extraction pipeline if we don't already have cached text
        if not txt_path and HAS_FITZ:
            try:
                import fitz
                doc = fitz.open(arquivo_path)
                pages_text = []
                for p in doc:
                    try:
                        t = p.get_text('text')
                        if t:
                            pages_text.append(t)
                    except Exception:
                        continue
                doc.close()
                combined = "\n\n=== PAGE BREAK ===\n\n".join(pages_text).strip()
                if combined and len(combined.strip()) >= 50:
                    # save extracted text to output dir and use it
                    txt_file_path = os.path.join(output_dir, f"{nome_base}.txt")
                    try:
                        with open(txt_file_path, 'w', encoding='utf-8', errors='replace') as tf:
                            tf.write(combined)
                        txt_path = txt_file_path
                        texto = combined
                    except Exception:
                        txt_path = None
                        texto = ''
            except Exception:
                # If fitz exists but extraction fails, fallback to pipeline
                txt_path = None
                texto = ''
        # If no fast-path text and no cached text, try learning store recommendation then pipeline
        if not txt_path:
            try:
                rec = None
                if not skip_cached_text:
                    # Prefer exact match by file_hash when available to avoid reusing unrelated cached TXT
                    if file_hash:
                        try:
                            rec = LearningStore.find_by_file_hash(file_hash)
                        except Exception:
                            rec = None
                    # Fallback to size/page_count recommendation only if no exact hash match
                    if not rec:
                        try:
                            rec = LearningStore.recommend_for(file_size or 0, page_count)
                        except Exception:
                            rec = None
                else:
                    rec = None
            except Exception:
                rec = None

            if rec and rec.get('txt_path') and os.path.exists(rec.get('txt_path')):
                try:
                    with open(rec.get('txt_path'), 'r', encoding='utf-8', errors='replace') as tf:
                        texto = tf.read()
                        txt_path = rec.get('txt_path')
                except Exception:
                    txt_path = None

            # apply recommended params if available
            if not txt_path and rec:
                try:
                    usar_ocr = rec.get('usar_ocr', usar_ocr)
                    dpi = rec.get('dpi', dpi) or dpi
                except Exception:
                    pass

            if not txt_path:
                # quick initial conversion attempt: fail fast to avoid long waits in web requests
                # if user requested forced high-quality, prefer larger initial dpi and longer passes
                if force_quality:
                    txt_path, erro = conversor_pipeline.convert_pdf_to_txt(arquivo_path, out_dir=output_dir, usar_ocr=True, dpi=max(dpi, 600))
                else:
                    txt_path, erro = conversor_pipeline.convert_pdf_to_txt(arquivo_path, out_dir=output_dir, usar_ocr=usar_ocr, dpi=dpi)
                if not txt_path:
                    return None, erro

            try:
                with open(txt_path, 'r', encoding='utf-8', errors='replace') as f:
                    texto = f.read()
            except Exception as e:
                return None, f"Erro ao ler TXT gerado: {e}"

            # If extracted text looks insufficient, retry with increasing DPI and OCR toggles
            MIN_TEXT_CHARS = 80
            if not texto or len(texto.strip()) < MIN_TEXT_CHARS:
                tried = set()
                # choose dpi candidates depending on force_quality
                if force_quality:
                    dpi_candidates = [600, 800, 1000, 1200]
                else:
                    dpi_candidates = list(range(100, 1201, 100))
                ocr_modes = [usar_ocr]
                if not usar_ocr:
                    ocr_modes.append(True)
                else:
                    ocr_modes.append(False)

                for use_ocr_try in ocr_modes:
                    for dpi_try in dpi_candidates:
                        key = (use_ocr_try, dpi_try)
                        if key in tried:
                            continue
                        tried.add(key)
                        try:
                            txt_path_try, erro_try = conversor_pipeline.convert_pdf_to_txt(
                                arquivo_path, out_dir=output_dir, usar_ocr=use_ocr_try, dpi=dpi_try)
                        except Exception:
                            txt_path_try, erro_try = None, 'erro na tentativa de conversão'

                        if not txt_path_try:
                            continue

                        try:
                            with open(txt_path_try, 'r', encoding='utf-8', errors='replace') as ftry:
                                texto_try = ftry.read()
                        except Exception:
                            texto_try = ''

                        # Accept if extracted text is reasonably large
                        if texto_try and len(texto_try.strip()) >= MIN_TEXT_CHARS:
                            txt_path = txt_path_try
                            texto = texto_try
                            # update chosen dpi and usar_ocr for downstream logic
                            dpi = dpi_try
                            usar_ocr = use_ocr_try
                            break
                    if texto and len(texto.strip()) >= MIN_TEXT_CHARS:
                        break

    # Detectar banco automaticamente usando os parsers disponíveis
    def detect_bank_from_text(texto: str) -> str:
        try:
            # Use a stable hash of the text to memoize detection results
            try:
                key = hashlib.sha256((texto or '').encode('utf-8')).hexdigest()
            except Exception:
                key = None

            if key is not None and key in _DETECTION_CACHE:
                return _DETECTION_CACHE[key]

            for inst in _load_parser_instances():
                try:
                    if inst.detectar_banco(texto):
                        banco_nome = inst.banco_nome
                        if key is not None:
                            _DETECTION_CACHE[key] = banco_nome
                            # keep cache size bounded
                            if len(_DETECTION_CACHE) > _DETECTION_CACHE_MAX:
                                _DETECTION_CACHE.popitem(last=False)
                        return banco_nome
                except Exception:
                    continue
        except Exception:
            pass
        return 'UNIVERSAL'

    def extract_with_parser(texto: str, banco_nome: str) -> List[Dict]:
        """Tenta extrair transações usando o parser específico do banco detectado."""
        try:
            # Prefer the parser matching banco_nome first
            best = []
            for inst in _load_parser_instances():
                try:
                    if getattr(inst, 'banco_nome', '').upper() == (banco_nome or '').upper():
                        try:
                            res = inst.extrair_transacoes(texto) or []
                            if res:
                                return res
                            else:
                                best = res
                        except Exception:
                            continue
                except Exception:
                    continue

            # Fallback: try all parsers and choose the one with most transactions
            best_count = len(best)
            best_res = best
            for inst in _load_parser_instances():
                try:
                    res = inst.extrair_transacoes(texto) or []
                    if len(res) > best_count:
                        best_count = len(res)
                        best_res = res
                except Exception:
                    continue
            return best_res
        except Exception:
            pass
        return []

        def heuristic_extract_transactions(texto: str) -> List[Dict]:
            """Heuristic extraction: scan lines for date + amount patterns and build transactions.
            This augments parser results when parsers miss descriptions or transactions.
            """
            res = []
            try:
                lines = (texto or '').splitlines()
                for i, line in enumerate(lines):
                    if not line or len(line.strip()) < 6:
                        continue
                    # find date formats dd/mm/YYYY or YYYYMMDD
                    mdate = re.search(r'(\d{2}/\d{2}/\d{4})', line) or re.search(r'(\d{4}\d{2}\d{2})', line)
                    mamt = re.search(r'(-?\d{1,3}(?:[\.\d]{0,}\d)?(?:,\d{2}))', line)
                    if mdate and mamt:
                        date_raw = mdate.group(1)
                        amt_raw = mamt.group(1)
                        # build description from surrounding lines
                        desc_parts = []
                        if i > 0:
                            prev = lines[i-1].strip()
                            if prev and not re.search(r'\d{2}/\d{2}/\d{4}', prev):
                                desc_parts.append(prev)
                        # remove date and amount from current line
                        cur = line.replace(date_raw, '').replace(amt_raw, '').strip()
                        if cur:
                            desc_parts.append(cur)
                        if i + 1 < len(lines):
                            nxt = lines[i+1].strip()
                            if nxt and not re.search(r'\d{2}/\d{2}/\d{4}', nxt):
                                desc_parts.append(nxt)
                        descricao = ' '.join(desc_parts).strip()
                        # normalize amount to float
                        try:
                            valor = float(amt_raw.replace('.', '').replace(',', '.'))
                        except Exception:
                            try:
                                valor = float(re.sub(r'[^0-9\-,]', '', amt_raw).replace(',', '.'))
                            except Exception:
                                valor = None
                        if valor is None:
                            continue
                        # normalize date to YYYYMMDDHHMMSS
                        parsed_date = None
                        try:
                            if re.match(r'^\d{8}$', date_raw):
                                parsed_date = date_raw + '000000'
                            else:
                                m = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', date_raw)
                                if m:
                                    d, mo, y = m.groups()
                                    parsed_date = f"{y}{mo}{d}000000"
                        except Exception:
                            parsed_date = None
                        if not parsed_date:
                            continue
                        tipo = 'DEBIT' if valor < 0 else 'CREDIT'
                        trans = {
                            'data': parsed_date,
                            'valor': abs(float(valor)),
                            'tipo': tipo,
                            'descricao': descricao or '',
                            'documento': '',
                            'fitid': ''
                        }
                        res.append(trans)
            except Exception:
                pass
            return res

    banco_detectado = banco_override or detect_bank_from_text(texto)

    # --- NOVO: Gerar o TXT Padrão Universal ---
    txt_padrao_content = ConversorService._normalizar_para_txt_padrao(texto, banco_detectado)

    nome_base = os.path.splitext(os.path.basename(arquivo_path))[0]
    txt_padrao_path = os.path.join(output_dir, f"{nome_base}_padrao.txt")
    try:
        with open(txt_padrao_path, 'w', encoding='utf-8') as f:
            f.write(txt_padrao_content)
    except Exception as e:
        print(f"Aviso: Não foi possível salvar TXT padrão: {e}")

    # Se o formato solicitado for 'txt', retornamos o TXT Padrão
    if formato_destino == 'txt':
        return txt_padrao_path, None

    # --- Tentar extrair transações com parser específico ---
    transacoes = extract_with_parser(texto, banco_detectado)

    # Record learning data (best-effort)
    try:
        trans_count = len(transacoes) if transacoes else 0
    except Exception:
        trans_count = 0

        try:
            # If requested, remove existing learning entries for this file_hash so we overwrite with new data
            if overwrite_learning and file_hash:
                try:
                    LearningStore.delete_by_file_hash(file_hash)
                except Exception:
                    pass

            LearningStore.record({
                'file_hash': file_hash,
                'file_size': file_size,
                'page_count': page_count,
                'method': 'auto',
                'dpi': dpi,
                'usar_ocr': usar_ocr,
                'txt_path': txt_path or txt_padrao_path,
                'text_len': len(texto) if texto else 0,
                'trans_count': trans_count,
                'banco': banco_detectado,
                'parser': banco_detectado,
                'success': True if texto and len(texto.strip()) > 0 else False
            })
        except Exception:
            pass

    # Helper: check if any parser exists for a banco name
    def parser_exists(banco_nome: str) -> bool:
        try:
            for inst in _load_parser_instances():
                try:
                    if getattr(inst, 'banco_nome', '').upper() == (banco_nome or '').upper():
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    # --- If parser produced none, try to build transacoes from TXT padrão ---
    if not transacoes:
        for linha in txt_padrao_content.split('\n'):
            if not linha.strip() or linha.count(';') != 5:
                continue
            partes = linha.split(';')
            try:
                valor_float = float(partes[1])
                # O tipo já vem correto do TXT padrão
                if partes[2].upper() == 'DEBITO':
                    tipo_ofx = 'DEBIT'
                else:
                    tipo_ofx = 'CREDIT'
                transacao = {
                    'data': partes[0],
                    'valor': valor_float,  # Já vem com sinal correto
                    'tipo': tipo_ofx,
                    'descricao': partes[3],
                    'documento': partes[4],
                    'saldo': partes[5]
                }
                # Gerar FITID único baseado nos dados
                fitid = f"{transacao['data']}{abs(int(transacao['valor']*100)):08d}"
                if transacao['documento']:
                    fitid += transacao['documento']
                transacao['fitid'] = fitid[:30]
                transacoes.append(transacao)
            except (ValueError, IndexError) as e:
                print(f"Aviso: Ignorando linha mal formatada no TXT padrão: {linha} - Erro: {e}")
                continue

    # Heuristic augmentation: if transactions are missing or lack descriptions, try heuristics
    try:
        need_aug = False
        heur_added = 0
        heur_filled_desc = 0
        if not transacoes:
            need_aug = True
        else:
            # if many transactions have empty descrição, consider augmentation
            empty_desc = sum(1 for t in transacoes if not (t.get('descricao')))
            if empty_desc / max(1, len(transacoes)) > 0.3:
                need_aug = True
        if need_aug:
            heur = heuristic_extract_transactions(texto)
            # merge heuristics without duplicating existing by date+valor
            for h in heur:
                dup = False
                for exi in transacoes:
                    try:
                        if str(exi.get('data')) == str(h.get('data')) and abs(float(exi.get('valor') or 0) - float(h.get('valor') or 0)) < 0.01:
                            # if existing lacks descricao but heuristic provides, fill it
                            if (not exi.get('descricao')) and h.get('descricao'):
                                exi['descricao'] = h.get('descricao')
                                heur_filled_desc += 1
                            dup = True
                            break
                    except Exception:
                        continue
                if not dup:
                    transacoes.append(h)
                    heur_added += 1
    except Exception:
        pass

    # --- Gerar CSV e OFX (código existente adaptado) ---
    csv_path = os.path.join(output_dir, f"{nome_base}.csv")
    if transacoes:
        ConversorService._salvar_como_csv(transacoes, csv_path)

    # If CSV requested, return CSV path
    if formato_destino == 'csv':
        if os.path.exists(csv_path):
            return csv_path, None
        else:
            return None, 'Erro ao gerar CSV'

    # Apply heuristic normalization to fix wrong credit/debit classification from parsers
    try:
        transacoes = ConversorService._normalize_transacoes_heuristic(transacoes)
    except Exception:
        pass

    if formato_destino == 'ofx':
        banco_id_map = {
            'CAIXA': '104', 'BRADESCO': '237', 'ITAU': '341', 'SANTANDER': '033', 'BRASIL': '001', 'STONE': '165',
            # full names / aliases
            'BANCO DO BRASIL': '001',
            'BANCO DO NORDESTE': '004',
            'BNB': '004'
        }

        # If no transactions were detected, decide next step:
        if not transacoes:
            # check if TXT padrão produced any transactions
            has_txt_transactions = any(1 for l in txt_padrao_content.split('\n') if l.strip() and l.count(';') == 5)
            parser_available = parser_exists(banco_detectado)

            # If there's no parser implemented for this banco and TXT has no transactions,
            # send the original PDF to support for parser development.
            if (not parser_available) and (not has_txt_transactions):
                try:
                    import shutil
                    support_dir = os.path.join(output_dir, 'support_queue')
                    os.makedirs(support_dir, exist_ok=True)
                    support_path = os.path.join(support_dir, os.path.basename(arquivo_path))
                    shutil.copy(arquivo_path, support_path)
                except Exception:
                    support_path = os.path.join(output_dir, os.path.basename(arquivo_path))
                return None, f"SUPPORT:{support_path}"

            # If TXT padrão has transactions, use them (already collected into transacoes list)
            # If parser exists but returned empty, fall back to generating OFX from TXT padrão if available
            if not transacoes and has_txt_transactions:
                # transacoes was filled above from TXT padrão parsing
                pass

        banco_id = banco_id_map.get(banco_detectado, '104')
        ofx_path = os.path.join(output_dir, f"{nome_base}.ofx")
        ok = ConversorService.gerar_ofx(transacoes, ofx_path, banco_id=banco_id)
        try:
            LearningStore.record({
                'file_hash': file_hash,
                'file_size': file_size,
                'page_count': page_count,
                'method': 'auto',
                'dpi': dpi,
                'usar_ocr': usar_ocr,
                'txt_path': txt_path or txt_padrao_path,
                'text_len': len(texto) if texto else 0,
                'trans_count': trans_count,
                'banco': banco_detectado,
                'parser': banco_detectado,
                'success': True if texto and len(texto.strip()) > 0 else False,
                'heuristic_used': True if (('heur_added' in locals() and heur_added > 0) or ('heur_filled_desc' in locals() and heur_filled_desc > 0)) else False
            })
        except Exception:
            pass

        # Write metadata about heuristic augmentation to output_dir for frontend visibility
        try:
            meta = {
                'heuristic_used': True if (('heur_added' in locals() and heur_added > 0) or ('heur_filled_desc' in locals() and heur_filled_desc > 0)) else False,
                'heuristic_added': int(heur_added) if 'heur_added' in locals() else 0,
                'heuristic_filled_desc': int(heur_filled_desc) if 'heur_filled_desc' in locals() else 0,
                'trans_count': trans_count,
                'banco_detectado': banco_detectado,
                'txt_path': txt_path or txt_padrao_path
            }
            try:
                meta_path = os.path.join(output_dir, f"{nome_base}.meta.json")
                with open(meta_path, 'w', encoding='utf-8') as mf:
                    json.dump(meta, mf)
            except Exception:
                pass
        except Exception:
            pass
        # Return result for OFX
        if ok and os.path.exists(ofx_path):
            return ofx_path, None
        else:
            return None, 'Erro ao gerar OFX'


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


# Module-level wrapper for backward compatibility with views importing this symbol
def get_formatos_destino(formato_origem: str) -> List[str]:
    """Return destination formats for a given origin format."""
    return ConversorService.get_formatos_destino(formato_origem)