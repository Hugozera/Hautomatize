from typing import List, Dict, Optional
import re
from core.parsers.base_parser import BaseParser


class BBParser(BaseParser):
    """Parser específico para extratos do BANCO DO BRASIL."""
    
    def __init__(self):
        super().__init__()
        self.banco_id = '001'
        self.banco_nome = 'BANCO DO BRASIL'
    
    def detectar_banco(self, texto: str) -> bool:
        texto_up = (texto or '').upper()
        return 'BANCO DO BRASIL' in texto_up or 'BB ' in texto_up or 'BB.' in texto_up or 'CONTA BANCÁRIA - BB' in texto_up
    
    def extrair_transacoes(self, texto: str) -> List[Dict]:
        if not texto:
            return []

        linhas = texto.split('\n')
        transacoes = []

        regex_data = re.compile(r'(\d{2})/(\d{2})/(\d{4})')
        regex_valor = re.compile(r'(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2})(?:\s*\(?(CR|DB|\+|\-)\)?)?')

        for linha in linhas:
            l = linha.strip()
            if len(l) < 6:
                continue
            # buscar data
            m = regex_data.search(l)
            if not m:
                continue
            dia, mes, ano = m.groups()
            data_ofx = f"{ano}{mes}{dia}"

            # buscar valor (último valor da linha)
            valores = regex_valor.findall(l)
            if not valores:
                continue
            valor_str = valores[-1][0]
            sinal_token = valores[-1][1]

            valor = self.corrigir_valor_br(valor_str)
            tipo = 'CREDIT'
            if sinal_token and (sinal_token in ('DB', '-',)):
                tipo = 'DEBIT'
                valor = -abs(valor)
            else:
                # heurística: se linha contém palavras de débito
                if any(w in l.upper() for w in ['DEBITO', 'DEB', 'SAQUE', 'PAGAMENTO', 'TARIFA', 'TAXA']):
                    tipo = 'DEBIT'
                    valor = -abs(valor)

            descricao = re.sub(r'\d{2}/\d{2}/\d{4}', '', l)
            descricao = re.sub(r'R?\$?\s*\d[\d\.,]*', '', descricao)
            descricao = re.sub(r'\s+', ' ', descricao).strip().upper()

            documento_search = re.search(r'\b(\d{4,})\b', l)
            documento = documento_search.group(1) if documento_search else ''

            fitid = self.gerar_fitid(data_ofx, valor, documento, descricao)

            trans = {
                'data': data_ofx,
                'valor': valor,
                'tipo': tipo,
                'descricao': descricao[:80],
                'documento': documento,
                'fitid': fitid,
                'linha_original': l,
            }
            transacoes.append(trans)

        # ordenar e deduplicar simples
        transacoes.sort(key=lambda x: x['data'])
        seen = set()
        unique = []
        for t in transacoes:
            chave = f"{t['data']}_{int(abs(t['valor'])*100)}_{t['descricao'][:20]}"
            if chave not in seen:
                seen.add(chave)
                unique.append(t)

        return unique
