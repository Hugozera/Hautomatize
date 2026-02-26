from typing import List, Dict, Optional
import re
from .base_parser import BaseParser


class ItauParser(BaseParser):
    """Parser específico para extratos do ITAÚ."""
    
    def __init__(self):
        super().__init__()
        self.banco_id = '341'
        self.banco_nome = 'ITAU'
    
    def detectar_banco(self, texto: str) -> bool:
        """Detecta se o texto é do Itaú."""
        return 'ITAU' in texto.upper() or 'ITAÚ' in texto.upper()
    
    def extrair_transacoes(self, texto: str) -> List[Dict]:
        """Extrai transações do formato Itaú."""
        if not texto:
            return []

        linhas = texto.split('\n')
        transacoes = []
        
        regex_data = re.compile(r'(\d{2})\s*/\s*([a-z]{3})', re.IGNORECASE)
        regex_valor = re.compile(r'([-+]?\d{1,3}(?:\.\d{3})*,\d{2})')
        
        meses = {
            'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04', 'mai': '05', 'jun': '06',
            'jul': '07', 'ago': '08', 'set': '09', 'out': '10', 'nov': '11', 'dez': '12'
        }

        ano = '2025'  # Ajustar conforme necessário

        for linha in linhas:
            linha = linha.strip()
            
            if (len(linha) < 5 or 
                'SALDO ANTERIOR' in linha or
                'saldo disponível' in linha or
                'lançamentos período' in linha or
                'PAGE BREAK' in linha):
                continue

            data_match = regex_data.search(linha)
            
            if data_match:
                dia, mes_abrev = data_match.groups()
                mes_abrev = mes_abrev.lower()[:3]
                
                if mes_abrev in meses:
                    mes = meses[mes_abrev]
                    data_ofx = f"{ano}{mes}{int(dia):02d}"

                    linha_sem_data = linha.replace(data_match.group(0), '').strip()
                    
                    valores = regex_valor.findall(linha_sem_data)
                    
                    if valores:
                        valor_str = valores[0]
                        
                        if valor_str.startswith('-'):
                            tipo = 'DEBIT'
                            valor = self.corrigir_valor_br(valor_str)
                        else:
                            if any(palavra in linha_sem_data.upper() for palavra in 
                                   ['SISPAG', 'PAG', 'TAR', 'IOF', 'JUROS', 'PARCELA']):
                                tipo = 'DEBIT'
                                valor = -abs(self.corrigir_valor_br(valor_str))
                            else:
                                tipo = 'CREDIT'
                                valor = abs(self.corrigir_valor_br(valor_str))

                        descricao = linha_sem_data
                        for v in valores:
                            descricao = descricao.replace(v, '')
                        
                        descricao = re.sub(r'7731[.\-]?\d+', '', descricao)
                        descricao = re.sub(r'\d{5,}', '', descricao)
                        descricao = re.sub(r'\s+', ' ', descricao).strip().upper()
                        
                        if not descricao:
                            descricao = 'TRANSACAO'

                        doc_match = re.search(r'(\d{5,})', linha)
                        documento = doc_match.group(1) if doc_match else ''

                        transacao = {
                            'data': data_ofx,
                            'valor': valor,
                            'tipo': tipo,
                            'descricao': descricao,
                            'documento': documento[:10]
                        }
                        
                        transacao['fitid'] = self.gerar_fitid(
                            data_ofx, valor, documento, descricao
                        )
                        
                        transacoes.append(transacao)

        transacoes.sort(key=lambda x: x['data'])
        
        return transacoes