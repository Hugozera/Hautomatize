from typing import List, Dict, Optional
import re
from .base_parser import BaseParser


class BradescoParser(BaseParser):
    """Parser específico para extratos do BRADESCO."""
    
    def __init__(self):
        super().__init__()
        self.banco_id = '237'
        self.banco_nome = 'BRADESCO'
    
    def detectar_banco(self, texto: str) -> bool:
        """Detecta se o texto é do Bradesco."""
        return 'BRADESCO' in texto.upper()
    
    def extrair_transacoes(self, texto: str) -> List[Dict]:
        """Extrai transações do formato Bradesco."""
        if not texto:
            return []

        linhas = texto.split('\n')
        transacoes = []
        transacao_em_construcao = None

        regex_data = re.compile(r'(\d{2})/(\d{2})/(\d{4})')
        regex_documento = re.compile(r'(\d{5,})')
        regex_valor = re.compile(r'([-+]?\d{1,3}(?:\.\d{3})*,\d{2})')

        for linha in linhas:
            linha = linha.strip()
            
            if len(linha) < 5 or 'Folha' in linha or 'PAGE BREAK' in linha:
                continue

            data_match = regex_data.search(linha)
            
            if data_match:
                if transacao_em_construcao:
                    transacoes.append(self._finalizar_transacao(transacao_em_construcao))
                    transacao_em_construcao = None

                dia, mes, ano = data_match.groups()
                data_ofx = f"{ano}{mes}{dia}"

                linha_sem_data = linha.replace(data_match.group(0), '').strip()
                
                doc_match = regex_documento.search(linha_sem_data)
                documento = doc_match.group(1) if doc_match else ''

                if doc_match:
                    linha_sem_doc = linha_sem_data.replace(doc_match.group(1), '').strip()
                else:
                    linha_sem_doc = linha_sem_data

                valores = regex_valor.findall(linha_sem_doc)
                
                if len(valores) >= 2:
                    valor_str = valores[0]  # Primeiro valor é o da transação
                    
                    descricao = linha_sem_doc
                    for v in valores:
                        descricao = descricao.replace(v, '')
                    
                    descricao = re.sub(r'\s+', ' ', descricao).strip().upper()
                    
                    if 'DEBITO' in descricao.upper() or 'PAG' in descricao.upper() or valor_str.startswith('-'):
                        tipo = 'DEBIT'
                        valor = -abs(self.corrigir_valor_br(valor_str))
                    else:
                        tipo = 'CREDIT'
                        valor = abs(self.corrigir_valor_br(valor_str))

                    transacao_em_construcao = {
                        'data': data_ofx,
                        'valor': valor,
                        'tipo': tipo,
                        'descricao': descricao,
                        'documento': documento[:10],
                        'linha_original': linha
                    }

        if transacao_em_construcao:
            transacoes.append(self._finalizar_transacao(transacao_em_construcao))

        transacoes.sort(key=lambda x: x['data'])
        
        return transacoes
    
    def _finalizar_transacao(self, transacao: Dict) -> Dict:
        """Finaliza uma transação do Bradesco."""
        transacao['descricao'] = transacao.get('descricao', 'TRANSACAO')[:80]
        
        transacao['fitid'] = self.gerar_fitid(
            transacao['data'],
            transacao['valor'],
            transacao.get('documento', ''),
            transacao['descricao']
        )
        
        return transacao