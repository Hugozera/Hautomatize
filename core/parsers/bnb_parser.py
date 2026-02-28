from typing import List, Dict, Optional
import re
from core.parsers.base_parser import BaseParser


class BNBParser(BaseParser):
    """Parser simples para extratos do Banco do Nordeste (BNB)."""

    def __init__(self):
        super().__init__()
        self.banco_id = '004'
        self.banco_nome = 'BANCO DO NORDESTE'

    def detectar_banco(self, texto: str) -> bool:
        t = (texto or '').upper()
        # muitos extratos do BNB seguem formato com TITULAR / AGÊNCIA / CONTA e coluna 'Valor R$'
        if 'BANCO DO NORDESTE' in t or 'BNB' in t:
            return True
        if 'TITULAR:' in t and 'AGÊNCIA' in t and 'CONTA' in t and 'VALOR R$' in t:
            return True
        if 'PERÍODO:' in t and 'TITULAR' in t and 'AGÊNCIA' in t:
            return True
        return False

    def extrair_transacoes(self, texto: str) -> List[Dict]:
        if not texto:
            return []

        linhas = [l.rstrip() for l in texto.split('\n')]
        transacoes: List[Dict] = []

        regex_data = re.compile(r'^(\d{2})/(\d{2})/(\d{4})')
        regex_valor = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})')

        current_date = None
        buffer_desc: List[str] = []

        for linha in linhas:
            l = linha.strip()
            if not l:
                continue

            m_date = regex_data.match(l)
            if m_date:
                # new row starts
                current_date = m_date.groups()
                buffer_desc = [l[m_date.end():].strip()]
                continue

            # look for a value line (often the value is in its own column/line)
            m_val = regex_valor.search(l)
            if m_val and current_date:
                # assemble description from buffer + previous lines
                valor_str = m_val.group(1)
                valor = self.corrigir_valor_br(valor_str)

                desc = ' '.join(buffer_desc + [l[:m_val.start()].strip()])
                desc = re.sub(r'\s+', ' ', desc).strip().upper()

                dia, mes, ano = current_date
                data_ofx = f"{ano}{mes}{dia}"

                # determine type
                # Determine type with more robust checks: keywords, trailing D/C and PIX handling
                upper = desc.upper()
                resto = l[m_val.end():].upper() if m_val.end() < len(l) else ''

                is_debito = False

                # PIX-specific rules
                if 'PIX' in upper:
                    if re.search(r'RECEB|RECEBIDO|RECEBEU|DEPOSI', upper):
                        is_debito = False
                    elif re.search(r'ENVI|ENVIADO|ENVIAR|PAG|PAGAMENTO|TRANSFER|SAQUE', upper):
                        is_debito = True

                # trailing D/C indicator after the value (common in some layouts)
                if not is_debito:
                    m_tipo_final = re.search(r'\bD\b', resto)
                    if m_tipo_final:
                        is_debito = True

                # keyword-based fallback
                if not is_debito and any(k in upper for k in ['SAQUE', 'DEBITO', 'DEB', 'PAGAMENTO', 'TARIFA', 'TAXA']):
                    is_debito = True

                if is_debito:
                    tipo = 'DEBIT'
                    valor = -abs(valor)
                else:
                    tipo = 'CREDIT'

                documento_search = re.search(r'\b(\d{4,})\b', desc)
                documento = documento_search.group(1) if documento_search else ''

                fitid = self.gerar_fitid(data_ofx, valor, documento, desc)

                trans = {
                    'data': data_ofx,
                    'valor': valor,
                    'tipo': tipo,
                    'descricao': desc[:80] if desc else 'TRANSACAO',
                    'documento': documento,
                    'fitid': fitid,
                    'linha_original': '\n'.join(buffer_desc + [l])
                }
                transacoes.append(trans)

                # reset buffer, keep current_date for next
                buffer_desc = []
                continue

            # otherwise accumulate description lines
            if current_date:
                buffer_desc.append(l)

        # ordenar e remover duplicatas simples
        transacoes.sort(key=lambda x: x['data'])
        seen = set()
        unique = []
        for t in transacoes:
            chave = f"{t['data']}_{int(abs(t['valor'])*100)}_{t['descricao'][:20]}"
            if chave not in seen:
                seen.add(chave)
                unique.append(t)

        return unique
