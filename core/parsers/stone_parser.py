from typing import List, Dict, Optional
import re
from .base_parser import BaseParser


class StoneParser(BaseParser):
    """Parser específico para extratos da STONE."""
    
    def __init__(self):
        super().__init__()
        self.banco_id = '165'
        self.banco_nome = 'STONE'
    
    def detectar_banco(self, texto: str) -> bool:
        """Detecta se o texto é da Stone."""
        return 'STONE' in texto.upper()
    
    def extrair_transacoes(self, texto: str) -> List[Dict]:
        """Extrai transações do formato Stone."""
        if not texto:
            return []

        linhas = texto.split('\n')
        transacoes = []
        cabecalho_encontrado = False

        regex_data = re.compile(r'(\d{2})/(\d{2})/(\d{4})')
        regex_valor = re.compile(r'([-+]?\d{1,3}(?:\.\d{3})*,\d{2})')
        regex_tipo = re.compile(r'(Crédito|Débito)', re.IGNORECASE)

        for linha in linhas:
            linha = linha.strip()
            
            if 'DATA' in linha and 'TIPO' in linha and 'LANÇAMENTO' in linha:
                cabecalho_encontrado = True
                continue
            
            if not cabecalho_encontrado:
                continue

            if len(linha) < 5 or 'PAGE BREAK' in linha:
                continue

            data_match = regex_data.search(linha)
            
            if data_match:
                dia, mes, ano = data_match.groups()
                data_ofx = f"{ano}{mes}{dia}"

                tipo_match = regex_tipo.search(linha)
                tipo = 'CREDIT' if tipo_match and 'CRÉDITO' in tipo_match.group(0).upper() else 'DEBIT'

                valores = regex_valor.findall(linha)
                
                if len(valores) >= 1:
                    valor_str = valores[0]
                    valor = self.corrigir_valor_br(valor_str)
                    
                    if tipo == 'DEBIT':
                        valor = -abs(valor)
                    else:
                        valor = abs(valor)

                    descricao = linha
                    descricao = re.sub(r'\d{2}/\d{2}/\d{4}', '', descricao)
                    descricao = re.sub(r'Crédito|Débito', '', descricao, flags=re.IGNORECASE)
                    
                    for v in valores:
                        descricao = descricao.replace(v, '')
                    
                    descricao = re.sub(r'\s+', ' ', descricao).strip().upper()
                    
                    if not descricao or len(descricao) < 5:
                        continue

                    transacao = {
                        'data': data_ofx,
                        'valor': valor,
                        'tipo': tipo,
                        'descricao': descricao[:80],
                        'documento': ''
                    }
                    
                    transacao['fitid'] = self.gerar_fitid(
                        data_ofx, valor, '', descricao
                    )
                    
                    transacoes.append(transacao)

        transacoes.sort(key=lambda x: x['data'])
        
        return transacoes