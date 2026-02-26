from typing import List, Dict, Optional
import re
from datetime import datetime
from .base_parser import BaseParser


class UniversalParser(BaseParser):
    """
    Parser universal que funciona para qualquer banco.
    Identifica padrões comuns em extratos bancários:
    - Datas (dd/mm/aaaa, dd/mm/aa, dd.mm.aaaa)
    - Valores no formato brasileiro (1.234,56)
    - Débitos/Créditos (C, D, +, -, CRED, DEB)
    - Documentos (números com 5+ dígitos)
    """
    
    def __init__(self):
        super().__init__()
        self.banco_id = '000'
        self.banco_nome = 'UNIVERSAL'
    
    def detectar_banco(self, texto: str) -> bool:
        """Sempre retorna True pois é universal."""
        return True
    
    def extrair_transacoes(self, texto: str) -> List[Dict]:
        """
        Extrai transações de qualquer extrato bancário usando padrões universais.
        """
        if not texto:
            return []

        linhas = texto.split('\n')
        transacoes = []
        transacao_em_construcao = None

        # Padrões universais
        regex_data = re.compile(r'(\d{2})[./](\d{2})[./](\d{2,4})')  # dd/mm/aaaa, dd.mm.aa
        regex_data_hora = re.compile(r'(\d{2})[./](\d{2})[./](\d{2,4})\s+(\d{2}:\d{2}:\d{2})')
        regex_data_hora_simples = re.compile(r'(\d{2})[./](\d{2})[./](\d{2,4})\s+(\d{2}:\d{2})')
        
        # Valor brasileiro: 1.234,56 ou 1234,56
        regex_valor = re.compile(r'([-+]?\s*\d{1,3}(?:\.\d{3})*,\d{2})')
        
        # Documentos (números com 5+ dígitos)
        regex_documento = re.compile(r'\b(\d{5,})\b')
        
        # Indicadores de débito/crédito
        regex_tipo = re.compile(r'\b([CD])\b|\b(DEBITO|CREDITO|DÉBITO|CRÉDITO|DEB|CRED)\b', re.IGNORECASE)
        regex_sinal = re.compile(r'([+-])')

        for linha in linhas:
            linha_original = linha
            linha = linha.strip()
            
            # Pular linhas muito curtas ou irrelevantes
            if len(linha) < 5:
                continue
                
            # Ignorar cabeçalhos comuns
            if any(palavra in linha.upper() for palavra in [
                'EXTRATO', 'PERÍODO', 'PERIODO', 'LANÇAMENTOS', 'LANCAMENTOS',
                'SALDO', 'PAGE BREAK', 'DATA', 'HISTÓRICO', 'HISTORICO',
                'AGÊNCIA', 'AGENCIA', 'CONTA', 'CLIENTE', 'CPF', 'CNPJ'
            ]):
                continue

            # Procurar data na linha (com ou sem hora)
            data_match = regex_data_hora.search(linha) or regex_data_hora_simples.search(linha) or regex_data.search(linha)
            
            if data_match:
                # Finalizar transação anterior
                if transacao_em_construcao:
                    transacao_final = self._finalizar_transacao_universal(transacao_em_construcao)
                    if transacao_final:
                        transacoes.append(transacao_final)
                    transacao_em_construcao = None

                # Extrair data
                grupos = data_match.groups()
                dia = grupos[0]
                mes = grupos[1]
                ano = grupos[2]
                
                # Ajustar ano com 2 dígitos
                if len(ano) == 2:
                    ano = f"20{ano}" if int(ano) <= 50 else f"19{ano}"
                
                # Extrair hora se disponível
                hora = grupos[3] if len(grupos) >= 4 else ''
                
                data_ofx = f"{ano}{mes}{dia}"

                # Remover a data da linha
                linha_sem_data = linha.replace(data_match.group(0), '').strip()

                # Procurar valores na linha
                valores = regex_valor.findall(linha_sem_data)
                
                # Procurar documento
                doc_match = regex_documento.search(linha_sem_data)
                documento = doc_match.group(1) if doc_match else ''

                # Se encontrou pelo menos um valor
                if valores:
                    # O primeiro valor geralmente é o da transação
                    valor_str = valores[0]
                    
                    # Determinar o tipo (débito/crédito)
                    tipo = 'UNKNOWN'
                    
                    # 1. Verificar sinal no valor
                    if valor_str.strip().startswith('-'):
                        tipo = 'DEBIT'
                        valor = -abs(self.corrigir_valor_br(valor_str))
                    else:
                        # 2. Verificar indicadores na linha
                        linha_upper = linha_sem_data.upper()
                        if any(p in linha_upper for p in ['D ', ' D ', 'DEB', 'PAG', '(-)', 'DÉBITO', 'DEBITO']):
                            tipo = 'DEBIT'
                            valor = -abs(self.corrigir_valor_br(valor_str))
                        elif any(p in linha_upper for p in ['C ', ' C ', 'CRED', '(+)', 'CRÉDITO', 'CREDITO']):
                            tipo = 'CREDIT'
                            valor = abs(self.corrigir_valor_br(valor_str))
                        else:
                            # 3. Verificar se tem C/D no final da linha
                            if re.search(r'[CD]\s*$', linha_upper):
                                if 'C' in linha_upper[-3:]:
                                    tipo = 'CREDIT'
                                    valor = abs(self.corrigir_valor_br(valor_str))
                                else:
                                    tipo = 'DEBIT'
                                    valor = -abs(self.corrigir_valor_br(valor_str))
                            else:
                                # Padrão: assumir crédito
                                tipo = 'CREDIT'
                                valor = abs(self.corrigir_valor_br(valor_str))

                    # Extrair descrição (tudo entre a data e o valor)
                    descricao = linha_sem_data
                    for v in valores:
                        descricao = descricao.replace(v, '')
                    
                    # Remover documento da descrição
                    if documento:
                        descricao = descricao.replace(documento, '')
                    
                    # Limpar descrição
                    descricao = re.sub(r'[^\w\s\-/]', ' ', descricao)
                    descricao = re.sub(r'\s+', ' ', descricao).strip().upper()
                    
                    # Se descrição ficou vazia, usar um texto padrão
                    if not descricao or len(descricao) < 3:
                        # Tentar extrair das partes da linha
                        partes = [p for p in linha_sem_data.split() if not re.match(r'^[\d.,]+$', p)]
                        if partes:
                            descricao = ' '.join(partes).upper()
                        else:
                            descricao = 'TRANSACAO'

                    transacao_em_construcao = {
                        'data': data_ofx,
                        'valor': valor,
                        'tipo': tipo,
                        'descricao': descricao,
                        'documento': documento,
                        'hora': hora,
                        'linha_original': linha_original,
                        'valores_encontrados': len(valores),
                        'valor_bruto': valor_str
                    }

        # Finalizar última transação
        if transacao_em_construcao:
            transacao_final = self._finalizar_transacao_universal(transacao_em_construcao)
            if transacao_final:
                transacoes.append(transacao_final)

        # Pós-processamento
        transacoes = self._processar_transacoes_universal(transacoes)
        
        return transacoes

    def _finalizar_transacao_universal(self, transacao: Dict) -> Optional[Dict]:
        """Finaliza uma transação universal."""
        if not transacao:
            return None

        # Se valor for zero, tentar extrair da linha original
        if transacao['valor'] == 0.0 and transacao.get('linha_original'):
            valores = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', transacao['linha_original'])
            if valores:
                valor = self.corrigir_valor_br(valores[0])
                if 'D' in transacao['linha_original'].upper() or 'PAG' in transacao['descricao'].upper():
                    transacao['valor'] = -abs(valor)
                    transacao['tipo'] = 'DEBIT'
                else:
                    transacao['valor'] = abs(valor)
                    transacao['tipo'] = 'CREDIT'

        # Garantir descrição não vazia
        if not transacao.get('descricao'):
            transacao['descricao'] = 'TRANSACAO'
        
        # Limitar tamanho
        transacao['descricao'] = transacao['descricao'][:80]

        # Gerar FITID
        fitid = self.gerar_fitid(
            transacao['data'], 
            transacao['valor'], 
            transacao.get('documento', ''),
            transacao['descricao']
        )
        transacao['fitid'] = fitid

        return transacao

    def _processar_transacoes_universal(self, transacoes: List[Dict]) -> List[Dict]:
        """Processa e valida transações universais."""
        if not transacoes:
            return []

        # Remover duplicatas
        transacoes_unicas = []
        vistos = set()
        
        for t in transacoes:
            chave = f"{t['data']}_{abs(round(t['valor'] * 100))}_{abs(hash(t['descricao'][:20]))}"
            
            if chave not in vistos:
                vistos.add(chave)
                transacoes_unicas.append(t)

        # Ordenar por data
        transacoes_unicas.sort(key=lambda x: x['data'])

        return transacoes_unicas