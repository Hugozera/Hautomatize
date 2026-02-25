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
    TESSDATA_PREFIX = os.path.join(PROJECT_ROOT, 'tessdata')

    print(f"🔍 Debug - PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"🔍 Debug - POPPLER_PATH: {POPPLER_PATH}")
    print(f"🔍 Debug - POPPLER existe: {os.path.exists(POPPLER_PATH)}")

    # Configura caminhos - FORÇA o PATH correto
    if os.path.exists(POPPLER_PATH):
        # Adiciona ao PATH de várias formas para garantir
        os.environ['PATH'] = POPPLER_PATH + os.pathsep + os.environ.get('PATH', '')
        os.environ['PATH'] = os.environ['PATH'] + os.pathsep + POPPLER_PATH
        print(f"✅ Poppler configurado em: {POPPLER_PATH}")
        
        # Lista arquivos para debug
        try:
            arquivos = os.listdir(POPPLER_PATH)
            dlls = [f for f in arquivos if f.endswith('.dll')]
            exes = [f for f in arquivos if f.endswith('.exe')]
            print(f"   DLLs encontradas: {len(dlls)}")
            print(f"   EXEs encontrados: {len(exes)}")
        except:
            pass
    else:
        print(f"❌ Poppler NÃO encontrado em: {POPPLER_PATH}")
    
    if os.path.exists(TESSDATA_PREFIX):
        os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX
        print(f"✅ Tessdata configurado em: {TESSDATA_PREFIX}")
    
    if os.path.exists(TESSERACT_CMD) and HAS_OCR:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        print(f"✅ Tesseract configurado em: {TESSERACT_CMD}")

    # NOTE: Legacy ULTRA OCR configuration removed.
    # Use `conversor_pipeline` for PDF->TXT extraction and OCR fallbacks.
    
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
        """Legacy image preprocessing stub retained for compatibility.
        Actual preprocessing is performed in `core.conversor_pipeline` when OCR is used.
        Returns the input image unchanged."""
        return imagem

    @classmethod
    def _corrigir_encoding_santander(cls, texto: str) -> str:
        """
        Corrige problemas de encoding específicos do Santander.
        """
        if not texto:
            return texto
        
        # Se for bytes, tenta decodificar como latin1
        if isinstance(texto, bytes):
            try:
                return texto.decode('latin1')
            except:
                try:
                    return texto.decode('utf-8', errors='ignore')
                except:
                    pass
        
        # Mapeamento de caracteres especiais comuns em PDFs do Santander
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
        
        # Remove caracteres não imprimíveis
        texto = ''.join(char for char in texto if ord(char) >= 32 or char in '\n\r\t')
        
        return texto

    @classmethod
    def _limpar_texto_corrompido_hibrido(cls, texto: str, banco: str = "CAIXA") -> str:
        """
        Limpa texto corrompido de forma HÍBRIDA:
        - Usa regras específicas para bancos conhecidos
        - Usa lógica dinâmica para casos genéricos
        
        Args:
            texto: Texto extraído
            banco: "CAIXA", "BRADESCO", "ITAU", "SANTANDER", "BRASIL", "STONE"
        """
        if not texto:
            return texto
        
        print(f"\n  🔧 Aplicando limpeza híbrida para banco: {banco}")
        
        # ========== CORREÇÕES ESPECÍFICAS POR BANCO ==========
        if banco.upper() == "CAIXA":
            # Regras específicas da CAIXA (aprendidas com milhares de extratos)
            print(f"    Aplicando regras específicas da CAIXA...")
            
            # CORREÇÃO 1: "351" no início de datas deve ser "31"
            # Ex: 351/07/2025 → 31/07/2025
            texto = re.sub(r'35(\d{2}/\d{2}/\d{2,4})', r'3\1', texto)
            
            # CORREÇÃO 2: "351" no início de documentos (6 dígitos) deve ser "31"
            # Ex: 3510826 → 310826
            texto = re.sub(r'\b35(\d{5})\b', r'31\1', texto)
            
            # CORREÇÃO 3: "350" no início deve ser "30"
            texto = re.sub(r'\b350(\d{4})\b', r'30\1', texto)
            
            # CORREÇÃO 4: Valores com dígitos extras (359,80 → 39,80)
            def corrigir_valor_caixa(match):
                prefixo = match.group(1)  # "35"
                digito = match.group(2)   # dígito após 35
                resto = match.group(3)    # ",XX"
                return f"3{digito}{resto}"
            
            texto = re.sub(r'(\d{2})(\d)(,\d{2})', corrigir_valor_caixa, texto)
            
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
            # Aplica correção de encoding específica do Santander
            texto = cls._corrigir_encoding_santander(texto)
            
            # Regras específicas do Santander
            texto = re.sub(r'Per[ií]odos?:?\s*(\d{2}/\d{2}/\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})', 
                          r'Período: \1 a \2', texto, flags=re.IGNORECASE)
            texto = re.sub(r'Saldo dispon[ií]vel', r'Saldo disponível', texto, flags=re.IGNORECASE)
        
        elif banco.upper() == "STONE":
            # Regras específicas da Stone
            texto = re.sub(r'D[eé]bito', r'Débito', texto, flags=re.IGNORECASE)
            texto = re.sub(r'Cr[eé]dito', r'Crédito', texto, flags=re.IGNORECASE)
            texto = re.sub(r'Transfer[êe]ncia', r'Transferência', texto, flags=re.IGNORECASE)
        
        elif banco.upper() == "ITAU":
            # Regras específicas do Itaú
            texto = re.sub(r'dispon#vel', r'disponível', texto, flags=re.IGNORECASE)
        
        # ========== REGRAS GENÉRICAS (FUNCIONAM PARA QUALQUER TEXTO) ==========
        
        # 1. Remove espaços múltiplos
        texto = re.sub(r'\s+', ' ', texto)
        
        # 2. Corrige datas com dígitos extras
        def corrigir_data_generico(match):
            data = match.group(0)
            partes = data.split('/')
            if len(partes) == 3:
                dia, mes, ano = partes
                # Se dia tem 3 dígitos, pega só os 2 primeiros
                if len(dia) == 3:
                    dia = dia[:2]
                # Se ano tem mais de 4 dígitos, trunca
                if len(ano) > 4:
                    ano = ano[:4]
                # Se ano tem 2 dígitos, adiciona 20
                if len(ano) == 2:
                    ano = f"20{ano}"
                return f"{dia}/{mes}/{ano}"
            return data
        
        texto = re.sub(r'\d{2,3}/\d{2}/\d{2,5}', corrigir_data_generico, texto)
        
        # 3. Corrige documentos (números de 5-7 dígitos)
        def corrigir_documento_generico(match):
            doc = match.group(0)
            # Remove caracteres não numéricos
            doc = re.sub(r'[^0-9]', '', doc)
            # Se tem 7 dígitos, tenta reduzir para 6 removendo o dígito extra
            if len(doc) == 7:
                # Verifica se os primeiros 2 dígitos são suspeitos (35, 34, 36)
                if doc[:2] in ['35', '34', '36']:
                    return doc[1:]  # 351234 -> 31234 (5 dígitos? cuidado)
                elif doc[:2] in ['31', '30', '32']:
                    return doc  # mantém
            return doc
        
        texto = re.sub(r'\b\d{5,7}\b', corrigir_documento_generico, texto)
        
        # 4. Corrige valores monetários
        def corrigir_valor_generico(match):
            valor = match.group(0)
            # Remove pontos extras (R$ 1.2.34,56 -> R$ 1.234,56)
            if valor.count('.') > 1 and ',' in valor:
                partes = valor.split(',')
                inteiro = partes[0].replace('.', '')
                if len(inteiro) > 3:
                    inteiro = inteiro[:-3] + '.' + inteiro[-3:]
                return f"{inteiro},{partes[1]}"
            return valor
        
        texto = re.sub(r'\d{1,3}(?:\.\d{3})*,\d{2,3}', corrigir_valor_generico, texto)
        
        return texto

    @classmethod
    def _corrigir_espacos_e_caracteres(cls, texto: str) -> str:
        """
        Corrige espaços ausentes e caracteres especiais após o OCR.
        """
        if not texto:
            return texto
        
        # 1. Corrige palavras que deveriam ter espaço
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
        
        # 2. Corrige barras em valores (2.8//41D → 2.877,41 D)
        texto = re.sub(r'(\d+)\.(\d+)//(\d+)D', r'\1.\2\3 D', texto)
        texto = re.sub(r'//', '/', texto)
        
        # 3. Remove pontos extras em números
        texto = re.sub(r'(\d+)\.(\d+)\.(\d+)', r'\1.\2\3', texto)
        
        # 4. Garante que 'C' e 'D' tenham espaço antes
        texto = re.sub(r'(\d+,\d{2})C', r'\1 C', texto)
        texto = re.sub(r'(\d+,\d{2})D', r'\1 D', texto)
        
        # 5. Corrige espaços em datas
        texto = re.sub(r'(\d{2}/\d{2}/\d{4})-', r'\1 - ', texto)
        
        return texto

    @classmethod
    def _detectar_banco(cls, texto: str) -> str:
        """Deprecated: bank detection disabled — always returns DESCONHECIDO."""
        return "DESCONHECIDO"

    @classmethod
    def _extrair_texto_com_ocr(cls, pdf_path: str, config: dict) -> str:
        """Legacy ULTRA OCR function removed.
        Use `core.conversor_pipeline.extract_text_pipeline` for robust PDF->TXT extraction
        (pdfminer -> pdftotext -> OCR fallback). This stub remains for compatibility.
        """
        return ""

    @classmethod
    def extrair_texto_pdf(cls, pdf_path: str) -> str:
        """Legacy method removed. Use `conversor_pipeline.extract_text_pipeline` instead."""
        return ""

    @classmethod
    def corrigir_valor_br(cls, valor_str: str) -> float:
        """
        Converte string de valor brasileiro para float.
        CORRIGE problemas comuns de OCR.
        """
        if not valor_str:
            return 0.0
        
        # Remove R$ e espaços
        valor_str = re.sub(r'[R\$\s]', '', valor_str)
        
        # CORREÇÃO: "359,80" -> "39,80"
        if re.match(r'35\d,\d{2}', valor_str):
            valor_str = '3' + valor_str[2:]
        
        # CORREÇÃO: "1,329,07" (vírgula como separador de milhar)
        if valor_str.count(',') == 2:
            # Substitui a primeira vírgula por ponto (milhar) e mantém a segunda (decimal)
            partes = valor_str.split(',')
            if len(partes) == 3:
                valor_str = f"{partes[0]}.{partes[1]},{partes[2]}"
        
        # Corrige padrões problemáticos
        # Ex: "15.2355,56" -> "15.235,56" (remove dígito extra)
        valor_str = re.sub(r'(\d+)\.(\d{3})(\d)(\d{3})', r'\1.\2\4', valor_str)
        
        # Corrige "8.9350,63" -> "8.935,63" (remove zero extra)
        valor_str = re.sub(r'(\d+)\.(\d{3})0,(\d{2})', r'\1.\2,\3', valor_str)
        
        # Corrige "15.275,356" -> "15.275,36" (centavos com 3 dígitos)
        if ',' in valor_str and len(valor_str.split(',')[1]) > 2:
            parte_int, parte_dec = valor_str.split(',')
            valor_str = f"{parte_int},{parte_dec[:2]}"
        
        # Corrige barras no lugar de vírgulas
        valor_str = valor_str.replace('/', ',')
        
        # Caso 1: Formato correto "1.329,07"
        if '.' in valor_str and ',' in valor_str:
            # Ponto é milhar, vírgula é decimal
            try:
                valor_limpo = valor_str.replace('.', '').replace(',', '.')
                return float(valor_limpo)
            except:
                pass
        
        # Caso 2: Só vírgula "11,24894"
        elif ',' in valor_str and '.' not in valor_str:
            try:
                valor_limpo = valor_str.replace(',', '.')
                return float(valor_limpo)
            except:
                pass
        
        # Caso 3: Só ponto "1.32907"
        elif '.' in valor_str and ',' not in valor_str:
            # Tenta identificar se é milhar + decimal sem vírgula
            partes = valor_str.split('.')
            if len(partes) == 2 and len(partes[1]) in [2, 3, 5]:
                # Se a parte decimal tem 2 dígitos, é provavelmente correto
                if len(partes[1]) == 2:
                    valor_limpo = valor_str.replace('.', '')
                    valor_limpo = valor_limpo[:-2] + '.' + valor_limpo[-2:]
                    try:
                        return float(valor_limpo)
                    except:
                        pass
                else:
                    # Remove todos os pontos
                    valor_limpo = valor_str.replace('.', '')
                    try:
                        return float(valor_limpo)
                    except:
                        pass
        
        # Último recurso: remove tudo que não é dígito ou vírgula
        try:
            valor_limpo = re.sub(r'[^\d,]', '', valor_str)
            valor_limpo = valor_limpo.replace(',', '.')
            return float(valor_limpo)
        except:
            return 0.0

    @classmethod
    def _extrair_data(cls, texto: str) -> str:
        """Extrai data no formato YYYYMMDD de qualquer formato."""
        # Procura por padrões de data
        padroes = [
            r'(\d{2})[/-](\d{2})[/-](\d{4})',  # DD/MM/YYYY
            r'(\d{2})[/-](\d{2})[/-](\d{2})',  # DD/MM/YY
            r'(\d{4})[/-](\d{2})[/-](\d{2})',  # YYYY/MM/DD
        ]
        
        for padrao in padroes:
            match = re.search(padrao, texto)
            if match:
                grupos = match.groups()
                if len(grupos) == 3:
                    if len(grupos[0]) == 4:  # YYYY/MM/DD
                        return f"{grupos[0]}{grupos[1]}{grupos[2]}"
                    elif len(grupos[2]) == 4:  # DD/MM/YYYY
                        return f"{grupos[2]}{grupos[1]}{grupos[0]}"
                    else:  # DD/MM/YY
                        return f"20{grupos[2]}{grupos[1]}{grupos[0]}"
        
        return ""

    @classmethod
    def _extrair_valor(cls, texto: str) -> float:
        """Extrai valor monetário do texto."""
        match = re.search(r'(\d{1,3}(?:[.,]\d{3})*[.,]\d{2,3})', texto)
        if match:
            return cls.corrigir_valor_br(match.group(1))
        return 0.0

    @classmethod
    def _extrair_transacoes_caixa(cls, texto: str) -> List[Dict]:
        """Removed: bank-specific parser(s) for CAIXA. Use generic extractor instead."""
        return cls.extrair_transacoes_avancado(texto)

    @classmethod
    def _extrair_transacoes_stone(cls, texto: str) -> List[Dict]:
        """Removed: bank-specific parser for STONE. Use generic extractor instead."""
        return cls.extrair_transacoes_avancado(texto)

    @classmethod
    def _extrair_transacoes_santander(cls, texto: str) -> List[Dict]:
        """Removed: bank-specific parser for SANTANDER. Use generic extractor instead."""
        return cls.extrair_transacoes_avancado(texto)

    @classmethod
    def _extrair_transacoes_itau(cls, texto: str) -> List[Dict]:
        """Removed: bank-specific parser for ITAU. Use generic extractor instead."""
        return cls.extrair_transacoes_avancado(texto)

    @classmethod
    def _extrair_transacoes_bb(cls, texto: str) -> List[Dict]:
        """Removed: bank-specific parser for BANCO DO BRASIL. Use generic extractor instead."""
        return cls.extrair_transacoes_avancado(texto)

    @classmethod
    def _extrair_transacoes_bradesco(cls, texto: str) -> List[Dict]:
        """Removed: bank-specific parser for BRADESCO. Use generic extractor instead."""
        return cls.extrair_transacoes_avancado(texto)

    @classmethod
    def _extrair_transacoes_por_banco(cls, texto: str, banco: str) -> List[Dict]:
        """Deprecated wrapper — uses generic advanced extraction (no bank-specific parsing)."""
        texto_limpo = cls._limpar_texto_corrompido_hibrido(texto, banco)
        texto_limpo = cls._corrigir_espacos_e_caracteres(texto_limpo)
        return cls.extrair_transacoes_avancado(texto_limpo)

    @classmethod
    def _pos_processar_transacoes(cls, transacoes: List[Dict]) -> List[Dict]:
        """Aplica correções específicas pós-extração."""
        transacoes_corrigidas = []
        
        for t in transacoes:
            # Corrige documentos com prefixo errado
            doc = t.get('documento', '')
            if doc:
                if len(doc) >= 7 and doc.startswith('35'):
                    t['documento'] = '31' + doc[2:]
                elif len(doc) >= 7 and doc.startswith('350'):
                    t['documento'] = '30' + doc[3:]
                elif len(doc) == 7 and doc.startswith('34'):
                    t['documento'] = '31' + doc[2:]
                elif len(doc) == 7 and doc.startswith('33'):
                    t['documento'] = '30' + doc[2:]
            
            # Corrige valores absurdos
            if abs(t['valor']) > 100000 and 'PIX' in t['descricao']:
                # PIX geralmente são valores menores
                # Provavelmente erro de OCR
                print(f"    ⚠ Valor suspeito: R$ {t['valor']:.2f} - {t['descricao']}")
            
            # Garante que FITID existe
            if 'fitid' not in t:
                fitid = f"{t['data']}{int(abs(t['valor']) * 100):08d}"
                if t.get('documento'):
                    fitid = f"{fitid}{t['documento']}"
                else:
                    fitid = f"{fitid}{abs(hash(t['descricao'])) % 10000:04d}"
                t['fitid'] = fitid[:30]
            else:
                # Remove caracteres estranhos do FITID
                t['fitid'] = re.sub(r'[^0-9]', '', t['fitid'])[:30]
            
            transacoes_corrigidas.append(t)
        
        return transacoes_corrigidas

    @classmethod
    def extrair_transacoes(cls, texto: str) -> List[Dict]:
        """
        Extrai transações bancárias do texto - VERSÃO MELHORADA E UNIVERSAL.
        """
        if not texto:
            return []

        print(f"\n📊 Extraindo transações de {len(texto)} caracteres")
        
        todas_transacoes = []
        linhas = texto.split('\n')
        print(f"  {len(linhas)} linhas para processar")

        # Padrões principais
        padrao_data = re.compile(r'(\d{2}[/]\d{2}[/](\d{4}|\d{2}))')
        padrao_valor = re.compile(r'(\d{1,3}(?:[.]\d{3})*[,]\d{2,3})')
        padrao_doc = re.compile(r'\b(\d{5,7})\b')
        
        # ========== PASSO 1: Extração principal ==========
        print("\n  🔍 PASSO 1: Extração principal...")
        
        transacoes_temp = []
        
        for i, linha in enumerate(linhas):
            linha = linha.strip()
            if len(linha) < 10:
                continue
            
            # Encontra data e valor
            data_match = padrao_data.search(linha)
            valor_match = padrao_valor.search(linha)
            
            if not (data_match and valor_match):
                continue
            
            try:
                # Processa data
                data_str = data_match.group(1)
                partes = data_str.split('/')
                dia, mes, ano = partes
                if len(ano) == 2:
                    ano = f"20{ano}"
                data = f"{ano}{mes}{dia}"
                
                # Processa valor
                valor_str = valor_match.group(1)
                # Converte formato brasileiro para float
                valor = cls.corrigir_valor_br(valor_str)
                
                # Documento
                doc_match = padrao_doc.search(linha)
                documento = doc_match.group(1) if doc_match else f"{i+1:06d}"
                
                # Determina tipo baseado no contexto
                linha_upper = linha.upper()
                if ' D ' in f" {linha_upper} " or linha_upper.endswith(' D') or 'DEB' in linha_upper or 'PAG' in linha_upper or 'TAR' in linha_upper or 'DÉBITO' in linha_upper:
                    tipo = 'DEBIT'
                    valor = -abs(valor)
                elif ' C ' in f" {linha_upper} " or linha_upper.endswith(' C') or 'CRED' in linha_upper or 'RECEBIDO' in linha_upper or 'CRÉDITO' in linha_upper:
                    tipo = 'CREDIT'
                    valor = abs(valor)
                else:
                    # Tenta determinar pelo sinal no valor
                    if '-' in linha and valor_str not in linha.replace('-', ''):
                        tipo = 'DEBIT'
                        valor = -abs(valor)
                    else:
                        tipo = 'CREDIT'  # default
                        valor = abs(valor)
                
                # Extrai descrição (remove data, valor e documento)
                desc = linha
                desc = desc.replace(data_str, '')
                desc = desc.replace(valor_str, '')
                if documento and documento in desc:
                    desc = desc.replace(documento, '')
                
                # Remove hora se houver
                desc = re.sub(r'\d{2}:\d{2}:\d{2}', '', desc)
                
                # Remove caracteres especiais
                desc = re.sub(r'[^\w\s\-/]', ' ', desc)
                desc = re.sub(r'\s+', ' ', desc).strip()
                
                # Se descrição vazia, usa palavras-chave
                if not desc or len(desc) < 5:
                    if 'PIX' in linha_upper:
                        desc = 'PIX'
                    elif 'CIEL' in linha_upper:
                        desc = 'CIELO'
                    elif 'BOLETO' in linha_upper:
                        desc = 'BOLETO'
                    elif 'TAR' in linha_upper:
                        desc = 'TARIFA'
                    elif 'PAG' in linha_upper:
                        desc = 'PAGAMENTO'
                    elif 'REC' in linha_upper:
                        desc = 'RECEBIMENTO'
                    else:
                        desc = 'TRANSACAO'
                
                # Limita tamanho
                desc = desc[:80].upper()
                
                transacoes_temp.append({
                    'data': data,
                    'valor': valor,
                    'descricao': desc,
                    'tipo': tipo,
                    'documento': documento,
                    'linha': linha[:100]  # guarda para referência
                })
                
            except Exception as e:
                continue
        
        print(f"    Encontradas: {len(transacoes_temp)} transações")

        # ========== PASSO 2: Agrupamento por data/valor (elimina duplicatas) ==========
        print("\n  🔍 PASSO 2: Agrupando transações...")
        
        grupos = {}
        
        for t in transacoes_temp:
            chave = f"{t['data']}_{t['valor']:.2f}"
            
            if chave not in grupos:
                grupos[chave] = []
            grupos[chave].append(t)
        
        # Para cada grupo, escolhe a melhor descrição
        for chave, transacoes_grupo in grupos.items():
            if len(transacoes_grupo) == 1:
                todas_transacoes.append(transacoes_grupo[0])
            else:
                # Escolhe a melhor descrição
                melhor_desc = ""
                melhor_doc = ""
                
                for t in transacoes_grupo:
                    if len(t['descricao']) > len(melhor_desc) and t['descricao'] != 'TRANSACAO':
                        melhor_desc = t['descricao']
                        melhor_doc = t['documento']
                
                if not melhor_desc:
                    melhor_desc = transacoes_grupo[0]['descricao']
                
                todas_transacoes.append({
                    'data': transacoes_grupo[0]['data'],
                    'valor': transacoes_grupo[0]['valor'],
                    'descricao': melhor_desc,
                    'tipo': transacoes_grupo[0]['tipo'],
                    'documento': melhor_doc
                })
        
        print(f"    Após agrupamento: {len(todas_transacoes)} transações")

        # ========== PASSO 3: Pós-processamento ==========
        print("\n  🔄 Pós-processando transações...")
        transacoes_finais = cls._pos_processar_transacoes(todas_transacoes)

        # ========== PASSO 4: Limpeza final e ordenação ==========
        print("\n  🔄 Limpeza final...")
        
        # Remove duplicatas definitivas
        transacoes_unicas = []
        vistos = set()
        
        for t in transacoes_finais:
            # Chave única: data + valor (com tolerância)
            chave = f"{t['data']}_{round(t['valor'] * 100)}"
            
            if chave not in vistos:
                vistos.add(chave)
                transacoes_unicas.append(t)

        # Ordena por data
        transacoes_unicas.sort(key=lambda x: x['data'])
        
        print(f"\n  ✅ Total final: {len(transacoes_unicas)} transações únicas")
        
        # Estatísticas
        if transacoes_unicas:
            datas = [t['data'] for t in transacoes_unicas]
            print(f"    Período: {min(datas)} a {max(datas)}")
            
            debitos = sum(1 for t in transacoes_unicas if t['tipo'] == 'DEBIT')
            creditos = sum(1 for t in transacoes_unicas if t['tipo'] == 'CREDIT')
            print(f"    Débitos: {debitos}, Créditos: {creditos}")
            
            # Mostra primeiras 10
            print("\n  📝 Primeiras 10 transações:")
            for t in transacoes_unicas[:10]:
                print(f"    {t['data']} | {t['tipo']:6} | R$ {t['valor']:8.2f} | {t['descricao'][:50]}")
        
        return transacoes_unicas

    @classmethod
    def extrair_transacoes_avancado(cls, texto: str) -> List[Dict]:
        """
        Versão ULTRA ROBUSTA que captura transações de extratos complexos
        usando uma máquina de estados para lidar com transações multi-linha.
        """
        if not texto:
            return []

        print(f"\n📊 Extração AVANÇADA (Robusta) de transações...")
        linhas = texto.split('\n')
        transacoes = []
        transacao_em_construcao = None

        # Compila as regex uma única vez para performance
        regex_data = re.compile(r'(\d{2})/(\d{2})/(\d{4})')
        regex_valor = re.compile(r'(\d{1,3}(?:[.]\d{3})*[,]\d{2})')  # Captura valores como 1.329,07 ou 85,30
        regex_doc = re.compile(r'\b(\d{5,7})\b')
        regex_tipo = re.compile(r'\b([CD])\b')  # Captura 'C' ou 'D' isolados

        for i, linha in enumerate(linhas):
            linha_original = linha
            linha = linha.strip()
            
            # Pula linhas muito curtas ou de cabeçalho/rodapé
            if len(linha) < 5 or 'CAIXA' in linha or 'PAGE BREAK' in linha or 'Alô CAIXA' in linha:
                continue

            # ========== DETECÇÃO DE INÍCIO DE TRANSAÇÃO ==========
            # Procura por data no formato DD/MM/AAAA
            data_match = regex_data.search(linha)
            
            if data_match:
                # Se já tinha uma transação em construção, finaliza ela
                if transacao_em_construcao:
                    transacoes.append(cls._finalizar_transacao(transacao_em_construcao))
                    transacao_em_construcao = None

                # Processa a data
                dia, mes, ano = data_match.groups()
                data_ofx = f"{ano}{mes}{dia}"

                # Procura por documento (número de 5-7 dígitos)
                doc_match = regex_doc.search(linha)
                documento = doc_match.group(1) if doc_match else ''

                # Procura por valor
                valor_match = regex_valor.search(linha)
                valor_str = valor_match.group(1) if valor_match else ''

                # Procura por tipo (C/D)
                tipo_match = regex_tipo.search(linha)
                tipo_char = tipo_match.group(1) if tipo_match else ''

                # Extrai a descrição (tudo entre a data e o valor)
                descricao = cls._extrair_descricao(linha, data_match, valor_match, doc_match, tipo_match)

                # Se encontrou valor, já pode criar a transação
                if valor_str:
                    valor = cls.corrigir_valor_br(valor_str)
                    
                    # Determina o tipo
                    if tipo_char == 'D' or 'D ' in linha or 'DEB' in linha.upper() or 'PAG' in linha.upper():
                        tipo = 'DEBIT'
                        valor = -abs(valor)
                    elif tipo_char == 'C' or 'C ' in linha or 'CRED' in linha.upper() or 'RECEBIDO' in linha.upper():
                        tipo = 'CREDIT'
                        valor = abs(valor)
                    else:
                        # Tenta inferir pelo contexto
                        if 'PAG' in linha.upper() or 'DEB' in linha.upper() or 'TAR' in linha.upper():
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
                        'linhas': [linha_original]
                    }
                else:
                    # Inicia uma transação sem valor (continuará nas próximas linhas)
                    transacao_em_construcao = {
                        'data': data_ofx,
                        'valor': 0.0,
                        'tipo': 'UNKNOWN',
                        'descricao': descricao,
                        'documento': documento,
                        'linhas': [linha_original]
                    }

            # ========== CONTINUAÇÃO DE TRANSAÇÃO ==========
            elif transacao_em_construcao:
                # Adiciona a linha à transação atual
                transacao_em_construcao['linhas'].append(linha_original)

                # Tenta encontrar valor nesta linha
                if transacao_em_construcao['valor'] == 0.0:
                    valor_match = regex_valor.search(linha)
                    if valor_match:
                        valor_str = valor_match.group(1)
                        valor = cls.corrigir_valor_br(valor_str)
                        
                        # Determina o tipo
                        linha_upper = linha.upper()
                        if 'D' in linha_upper or 'DEB' in linha_upper or 'PAG' in linha_upper:
                            transacao_em_construcao['tipo'] = 'DEBIT'
                            transacao_em_construcao['valor'] = -abs(valor)
                        else:
                            transacao_em_construcao['tipo'] = 'CREDIT'
                            transacao_em_construcao['valor'] = abs(valor)

                # Tenta encontrar documento
                if not transacao_em_construcao['documento']:
                    doc_match = regex_doc.search(linha)
                    if doc_match:
                        transacao_em_construcao['documento'] = doc_match.group(1)

                # Concatena a descrição
                # Remove partes que já são conhecidas (data, doc, valor)
                linha_para_desc = linha
                if transacao_em_construcao['data']:
                    # Remove a data se estiver no formato errado
                    data_br = f"{transacao_em_construcao['data'][6:8]}/{transacao_em_construcao['data'][4:6]}/{transacao_em_construcao['data'][0:4]}"
                    linha_para_desc = linha_para_desc.replace(data_br, '')
                
                if transacao_em_construcao['documento']:
                    linha_para_desc = linha_para_desc.replace(transacao_em_construcao['documento'], '')
                
                # Limpa a linha para descrição
                linha_para_desc = re.sub(r'\d{2}:\d{2}:\d{2}', '', linha_para_desc)  # Remove hora
                linha_para_desc = re.sub(r'[^\w\s\-/]', ' ', linha_para_desc)
                linha_para_desc = re.sub(r'\s+', ' ', linha_para_desc).strip()
                
                if linha_para_desc and len(linha_para_desc) > 3:
                    if transacao_em_construcao['descricao']:
                        transacao_em_construcao['descricao'] += ' ' + linha_para_desc
                    else:
                        transacao_em_construcao['descricao'] = linha_para_desc

        # ========== FINALIZA A ÚLTIMA TRANSAÇÃO ==========
        if transacao_em_construcao:
            transacoes.append(cls._finalizar_transacao(transacao_em_construcao))

        # ========== PÓS-PROCESSAMENTO ==========
        print(f"  📝 Transações brutas encontradas: {len(transacoes)}")
        
        # Remove duplicatas
        transacoes_unicas = cls._remover_duplicatas_transacoes(transacoes)
        
        # Pós-processa cada transação
        for t in transacoes_unicas:
            # Limpa a descrição
            t['descricao'] = re.sub(r'\s+', ' ', t['descricao']).strip().upper()
            t['descricao'] = t['descricao'][:80]  # Limita tamanho
            
            # Gera FITID se não existir
            if 'fitid' not in t:
                fitid = f"{t['data']}{int(abs(t['valor']) * 100):08d}"
                if t.get('documento'):
                    fitid = f"{fitid}{t['documento']}"
                else:
                    fitid = f"{fitid}{abs(hash(t['descricao'])) % 10000:04d}"
                t['fitid'] = fitid[:30]

        # Ordena por data
        transacoes_unicas.sort(key=lambda x: x['data'])

        # Estatísticas
        if transacoes_unicas:
            datas = [t['data'] for t in transacoes_unicas]
            print(f"  ✅ Transações únicas: {len(transacoes_unicas)}")
            print(f"  📅 Período: {min(datas)} a {max(datas)}")
            
            debitos = sum(1 for t in transacoes_unicas if t['tipo'] == 'DEBIT')
            creditos = sum(1 for t in transacoes_unicas if t['tipo'] == 'CREDIT')
            print(f"  💰 Débitos: {debitos}, Créditos: {creditos}")
            
            # Mostra as primeiras 5 como exemplo
            print("\n  📝 Primeiras 5 transações:")
            for t in transacoes_unicas[:5]:
                print(f"    {t['data']} | {t['tipo']:6} | R$ {t['valor']:10.2f} | {t['descricao'][:50]}")

        return transacoes_unicas

    @classmethod
    def _extrair_descricao(cls, linha: str, data_match, valor_match=None, doc_match=None, tipo_match=None) -> str:
        """Extrai a descrição removendo data, documento, valor e tipo."""
        desc = linha
        
        # Remove a data
        if data_match:
            desc = desc.replace(data_match.group(0), '')
        
        # Remove o valor
        if valor_match:
            desc = desc.replace(valor_match.group(1), '')
        
        # Remove o documento
        if doc_match:
            desc = desc.replace(doc_match.group(1), '')
        
        # Remove o tipo (C/D)
        if tipo_match:
            desc = desc.replace(tipo_match.group(1), '')
        
        # Remove hora
        desc = re.sub(r'\d{2}:\d{2}:\d{2}', '', desc)
        
        # Remove caracteres especiais
        desc = re.sub(r'[^\w\s\-/]', ' ', desc)
        desc = re.sub(r'\s+', ' ', desc).strip()
        
        return desc

    @classmethod
    def _finalizar_transacao(cls, transacao: Dict) -> Dict:
        """Finaliza uma transação, garantindo que todos os campos necessários existam."""
        if not transacao:
            return transacao
        
        # Se ainda não tem valor definido, tenta extrair de todas as linhas
        if transacao['valor'] == 0.0:
            for linha in transacao['linhas']:
                valor_match = re.search(r'(\d{1,3}(?:[.]\d{3})*[,]\d{2})', linha)
                if valor_match:
                    valor = cls.corrigir_valor_br(valor_match.group(1))
                    
                    # Tenta determinar o tipo
                    if 'D' in linha or 'DEB' in linha.upper() or 'PAG' in linha.upper():
                        transacao['tipo'] = 'DEBIT'
                        transacao['valor'] = -abs(valor)
                    else:
                        transacao['tipo'] = 'CREDIT'
                        transacao['valor'] = abs(valor)
                    break
        
        # Se a descrição estiver vazia, usa a primeira linha
        if not transacao['descricao'] and transacao['linhas']:
            primeira_linha = transacao['linhas'][0]
            # Remove data e hora
            desc = re.sub(r'\d{2}/\d{2}/\d{4}', '', primeira_linha)
            desc = re.sub(r'\d{2}:\d{2}:\d{2}', '', desc)
            desc = re.sub(r'[^\w\s\-/]', ' ', desc)
            transacao['descricao'] = re.sub(r'\s+', ' ', desc).strip()
        
        # Remove campos temporários
        if 'linhas' in transacao:
            del transacao['linhas']
        
        # Garante valores padrão
        if not transacao.get('documento'):
            transacao['documento'] = ''
        
        if transacao['descricao']:
            transacao['descricao'] = transacao['descricao'].upper()
        
        return transacao

    @classmethod
    def _remover_duplicatas_transacoes(cls, transacoes: List[Dict]) -> List[Dict]:
        """Remove transações duplicadas baseado em data e valor."""
        transacoes_unicas = []
        vistos = set()
        
        for t in transacoes:
            # Chave única: data + valor (com 2 casas decimais)
            chave = f"{t['data']}_{abs(round(t['valor'] * 100))}"
            
            if chave not in vistos:
                vistos.add(chave)
                transacoes_unicas.append(t)
            else:
                # Se já existe, mantém a que tem descrição mais longa
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
                    # Formata valor com vírgula (formato brasileiro)
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
                
                # Saldo
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
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Data', 'Tipo', 'Valor', 'Descrição', 'Documento', 'FITID'])
                for t in transacoes:
                    writer.writerow([
                        t.get('data', ''),
                        t.get('tipo', ''),
                        f"{t.get('valor', 0):.2f}",
                        t.get('descricao', ''),
                        t.get('documento', t.get('checknum', '')),
                        t.get('fitid', '')
                    ])
            print(f"  📊 CSV salvo: {csv_path}")
            return True
        except Exception as e:
            print(f"Erro ao salvar CSV: {e}")
            return False

    @classmethod
    def _salvar_txt_universal(cls, texto: str, txt_path: str, banco: str = "DESCONHECIDO") -> bool:
        """Salva o texto extraído em TXT com correções específicas do banco."""
        try:
            # Aplica limpeza híbrida antes de salvar
            print(f"\n  📄 Aplicando limpeza para TXT (banco: {banco})...")
            texto_limpo = cls._limpar_texto_corrompido_hibrido(texto, banco)
            texto_limpo = cls._corrigir_espacos_e_caracteres(texto_limpo)
            
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(texto_limpo)
            print(f"  📄 TXT universal salvo: {txt_path}")
            print(f"    Tamanho original: {len(texto)} caracteres")
            print(f"    Tamanho limpo:    {len(texto_limpo)} caracteres")
            return True
        except Exception as e:
            print(f"Erro ao salvar TXT: {e}")
            return False

    @classmethod
    def converter(cls, arquivo_path: str, formato_destino: str, 
                  output_dir: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """Legacy converter removed. Use the top-level `converter_arquivo` function
        or `core.conversor_pipeline.convert_pdf_to_txt` for PDF->TXT extraction and
        downstream conversion (OFX/CSV) based on the extracted text."""
        return None, "Use converter_arquivo or conversor_pipeline for conversions"


# ========== FUNÇÕES DE INTERFACE PÚBLICA ==========

def converter_arquivo(arquivo_path: str, formato_destino: str,
                      output_dir: Optional[str] = None, usar_ocr: bool = True,
                      dpi: int = 300) -> Tuple[Optional[str], Optional[str]]:
    """
    Converte um arquivo para o formato desejado.
    - Para `txt` usa o pipeline leve (pdfminer -> OCR fallback) implementado em `conversor_pipeline`.
    - Para outros formatos delega para a implementação existente em `ConversorService`.
    """
    # Prepare output dir
    if not output_dir:
        output_dir = os.path.join(os.path.dirname(arquivo_path), 'convertidos')
    os.makedirs(output_dir, exist_ok=True)

    origem_ext = os.path.splitext(arquivo_path)[1].lower()
    texto = ''

    # If original is TXT, read it directly; if PDF, run the extraction pipeline
    if origem_ext == '.txt':
        try:
            with open(arquivo_path, 'r', encoding='utf-8', errors='replace') as f:
                texto = f.read()
            txt_path = arquivo_path
        except Exception as e:
            return None, f"Erro ao ler TXT original: {e}"
    else:
        # PDF (or other) -> convert to TXT via pipeline
        txt_path, erro = conversor_pipeline.convert_pdf_to_txt(arquivo_path, out_dir=output_dir, usar_ocr=usar_ocr, dpi=dpi)
        if not txt_path:
            return None, erro

        # Lê o texto extraído
        try:
            with open(txt_path, 'r', encoding='utf-8', errors='replace') as f:
                texto = f.read()
        except Exception as e:
            return None, f"Erro ao ler TXT gerado: {e}"

    # Não fazemos detecção de banco: aplica limpeza genérica e extrai transações
    banco_detectado = 'DESCONHECIDO'
    texto_limpo = ConversorService._limpar_texto_corrompido_hibrido(texto, banco_detectado)
    texto_limpo = ConversorService._corrigir_espacos_e_caracteres(texto_limpo)

    # Salva versão universal do TXT (limpo)
    nome_base = os.path.splitext(os.path.basename(arquivo_path))[0]
    txt_universal_path = os.path.join(output_dir, f"{nome_base}_texto_universal.txt")
    try:
        ConversorService._salvar_txt_universal(texto, txt_universal_path, banco_detectado)
    except Exception:
        pass

    # Se o usuário só quer TXT, retorna a versão universal (se criada) ou o TXT original
    if formato_destino == 'txt':
        return txt_universal_path if os.path.exists(txt_universal_path) else txt_path, None

    # Extrai transações usando o método avançado genérico (sem parser por banco)
    transacoes = ConversorService.extrair_transacoes_avancado(texto_limpo)
    if not transacoes:
        transacoes = ConversorService.extrair_transacoes(texto_limpo)

    # Salva CSV auxiliar
    csv_path = os.path.join(output_dir, f"{nome_base}.csv")
    if transacoes:
        ConversorService._salvar_como_csv(transacoes, csv_path)

    # Gera OFX quando solicitado
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
            return (csv_path if os.path.exists(csv_path) else (txt_universal_path if os.path.exists(txt_universal_path) else txt_path)), "Falha ao gerar OFX"

    # Outros formatos: retornamos CSV se disponível
    if formato_destino == 'csv':
        if os.path.exists(csv_path):
            return csv_path, None
        else:
            return None, "CSV não gerado"

    return None, f"Formato {formato_destino} não suportado"


def get_formatos_destino(formato_origem: str) -> List[str]:
    """
    Retorna lista de formatos disponíveis para conversão.
    """
    return ConversorService.get_formatos_destino(formato_origem)


# ========== FUNÇÕES ADICIONAIS PARA PROCESSAMENTO EM LOTE ==========

def processar_pasta(pasta_path: str, formato_destino: str = 'ofx', 
                    output_dir: Optional[str] = None, usar_ocr: bool = True,
                    dpi: int = 300) -> List[Tuple[str, Optional[str], Optional[str]]]:
    """
    Processa todos os PDFs de uma pasta usando OCR ULTRA.
    Retorna lista de tuplas (arquivo, caminho_resultado, erro).
    """
    if not os.path.exists(pasta_path):
        return [(pasta_path, None, f"Pasta não encontrada: {pasta_path}")]
    
    if not output_dir:
        output_dir = os.path.join(pasta_path, 'convertidos')
    
    os.makedirs(output_dir, exist_ok=True)
    
    resultados = []
    arquivos = [f for f in os.listdir(pasta_path) if f.lower().endswith('.pdf')]
    
    print(f"\n📁 Encontrados {len(arquivos)} PDFs para processar em: {pasta_path}")
    print(f"⚠ ATENÇÃO: Cada arquivo pode levar vários minutos para processar (DPI={dpi})!")
    
    for i, arquivo in enumerate(arquivos, 1):
        print(f"\n{'='*60}")
        print(f"Processando {i}/{len(arquivos)}: {arquivo}")
        print(f"{'='*60}")
        
        arquivo_path = os.path.join(pasta_path, arquivo)
        resultado, erro = converter_arquivo(arquivo_path, formato_destino, output_dir, usar_ocr=usar_ocr, dpi=dpi)
        resultados.append((arquivo, resultado, erro))
    
    # Relatório final
    print(f"\n{'='*60}")
    print(f"✅ PROCESSAMENTO CONCLUÍDO")
    print(f"{'='*60}")
    sucessos = sum(1 for _, r, _ in resultados if r is not None)
    falhas = len(resultados) - sucessos
    print(f"Total: {len(resultados)} | Sucessos: {sucessos} | Falhas: {falhas}")
    
    if falhas > 0:
        print("\n❌ Falhas:")
        for arquivo, _, erro in resultados:
            if erro:
                print(f"  - {arquivo}: {erro}")
    
    return resultados


# ========== FUNÇÃO PRINCIPAL PARA EXECUÇÃO DIRETA ==========

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

⚠ ATENÇÃO: Este conversor usa OCR ULTRA (900 DPI) e pode levar vários minutos por arquivo!
        """)
    
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        print_ajuda()
        sys.exit(0)
    
    caminho = sys.argv[1]
    formato = 'ofx'
    output_dir = None
    
    # Processa argumentos
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
    
    # Executa
    if os.path.isdir(caminho):
        resultados = processar_pasta(caminho, formato, output_dir)
    else:
        resultado, erro = converter_arquivo(caminho, formato, output_dir)
        if resultado:
            print(f"\n✅ Sucesso! Arquivo gerado: {resultado}")
        else:
            print(f"\n❌ Erro: {erro}")