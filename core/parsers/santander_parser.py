from typing import List, Dict, Optional
import re
from .base_parser import BaseParser


class SantanderParser(BaseParser):
    """Parser específico para extratos do SANTANDER."""
    
    def __init__(self):
        super().__init__()
        self.banco_id = '033'
        self.banco_nome = 'SANTANDER'
    
    def detectar_banco(self, texto: str) -> bool:
        """Detecta se o texto é do Santander."""
        return 'SANTANDER' in texto.upper()
    
    def extrair_transacoes(self, texto: str) -> List[Dict]:
        """Extrai transações do formato Santander."""
        if not texto:
            return []

        linhas = texto.split('\n')
        transacoes = []

        regex_data = re.compile(r'(\d{2})/(\d{2})/(\d{4})')
        regex_valor = re.compile(r'([-+]?\d{1,3}(?:\.\d{3})*,\d{2})')
        regex_historico = re.compile(r'(Pix|Debito|Credito|Resgate|Aplicacao|Tarifa|Transferencia)', re.IGNORECASE)

        for linha in linhas:
            linha = linha.strip()
            
            if len(linha) < 5 or 'Periodos:' in linha:
                continue

            data_match = regex_data.search(linha)
            
            if data_match:
                dia, mes, ano = data_match.groups()
                data_ofx = f"{ano}{mes}{dia}"

                linha_sem_data = linha.replace(data_match.group(0), '').strip()
                
                valores = regex_valor.findall(linha_sem_data)
                
                if len(valores) >= 2:  # Valor da transação e saldo
                    valor_str = valores[0]
                    
                    descricao = linha_sem_data
                    for v in valores:
                        descricao = descricao.replace(v, '')
                    
                    descricao = re.sub(r'\s+', ' ', descricao).strip().upper()
                    
                    hist_match = regex_historico.search(descricao)
                    if hist_match:
                        descricao = hist_match.group(1).upper()
                    
                    if 'DEBITO' in descricao or 'TARIFA' in descricao or 'PAG' in descricao or valor_str.startswith('-'):
                        tipo = 'DEBIT'
                        valor = -abs(self.corrigir_valor_br(valor_str))
                    else:
                        tipo = 'CREDIT'
                        valor = abs(self.corrigir_valor_br(valor_str))

                    doc_match = re.search(r'\b(\d{6})\b', linha)
                    documento = doc_match.group(1) if doc_match else ''

                    transacao = {
                        'data': data_ofx,
                        'valor': valor,
                        'tipo': tipo,
                        'descricao': descricao[:80],
                        'documento': documento
                    }
                    
                    transacao['fitid'] = self.gerar_fitid(
                        data_ofx, valor, documento, descricao
                    )
                    
                    transacoes.append(transacao)

        transacoes.sort(key=lambda x: x['data'])
        
        return transacoes