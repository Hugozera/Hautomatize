from typing import List, Dict, Optional
import re
from .base_parser import BaseParser


class BBParser(BaseParser):
    """Parser específico para extratos do BANCO DO BRASIL."""
    
    def __init__(self):
        super().__init__()
        self.banco_id = '001'
        self.banco_nome = 'BRASIL'
    
    def detectar_banco(self, texto: str) -> bool:
        """Detecta se o texto é do Banco do Brasil."""
        return 'BANCO DO BRASIL' in texto.upper() or 'BB RENDE FÁCIL' in texto.upper() or 'Agência: 2138-5' in texto
    
    def extrair_transacoes(self, texto: str) -> List[Dict]:
        """
        Extrai transações do formato específico do Banco do Brasil.
        Formato: Data, Lote, Documento, Histórico, Valor com (+)/(-) no final
        """
        if not texto:
            return []

        linhas = texto.split('\n')
        transacoes = []
        transacao_em_construcao = None

        # Regex para data (dd/mm/aaaa)
        regex_data = re.compile(r'(\d{2})/(\d{2})/(\d{4})')
        
        # Regex para valor com (+) ou (-) no final
        regex_valor = re.compile(r'([\d.,]+)\s*\(([+-])\)$')
        
        # Regex para valor sem sinal (mas com vírgula)
        regex_valor_simples = re.compile(r'([\d.,]+)$')
        
        # Regex para identificar linhas de transação (começam com data)
        regex_linha_transacao = re.compile(r'^\d{2}/\d{2}/\d{4}')

        for linha in linhas:
            linha_original = linha
            linha = linha.strip()
            
            # Pular linhas irrelevantes
            if (len(linha) < 5 or 
                'Lançamentos' in linha or
                'Cliente' in linha or
                'Agência:' in linha or
                'PAGE BREAK' in linha or
                'Saldo do dia' in linha or
                'Informações Adicionais' in linha or
                'Lançamentos Futuros' in linha or
                'Aplicações Financeiras' in linha):
                continue

            # Verificar se é uma linha de transação (começa com data)
            if regex_linha_transacao.match(linha):
                # Se estava construindo uma transação, finaliza
                if transacao_em_construcao:
                    transacao_final = self._finalizar_transacao_bb(transacao_em_construcao)
                    if transacao_final:
                        transacoes.append(transacao_final)
                    transacao_em_construcao = None

                # Extrair data
                data_match = regex_data.search(linha)
                if not data_match:
                    continue
                    
                dia, mes, ano = data_match.groups()
                data_ofx = f"{ano}{mes}{dia}"

                # Remover a data da linha para processar o resto
                linha_sem_data = linha.replace(data_match.group(0), '').strip()
                
                # Dividir a linha em partes
                partes = linha_sem_data.split()
                
                # Identificar o valor (geralmente é a última parte)
                valor_str = ''
                tipo_sinal = ''
                
                if partes:
                    ultima_parte = partes[-1]
                    
                    # Verificar se tem (+)/(-) no final
                    valor_match = regex_valor.search(ultima_parte)
                    if valor_match:
                        valor_str = valor_match.group(1)
                        tipo_sinal = valor_match.group(2)
                    else:
                        # Tentar encontrar qualquer valor numérico
                        for i, parte in enumerate(partes):
                            valor_simples_match = regex_valor_simples.search(parte)
                            if valor_simples_match and ',' in parte:
                                valor_str = valor_simples_match.group(1)
                                # Verificar se há (+) ou (-) em outra parte
                                for p in partes:
                                    if '(+)' in p:
                                        tipo_sinal = '+'
                                        break
                                    elif '(-)' in p:
                                        tipo_sinal = '-'
                                        break
                                break

                if valor_str:
                    # Extrair descrição (tudo entre a data e o valor)
                    descricao = linha_sem_data
                    
                    # Remover o valor encontrado da descrição
                    for parte in partes:
                        if valor_str in parte or parte == valor_str or parte == f"{valor_str}({tipo_sinal})":
                            descricao = descricao.replace(parte, '')
                    
                    # Remover códigos de lote e documento (números)
                    descricao = re.sub(r'\b\d{5,}\b', '', descricao)
                    descricao = re.sub(r'\b\d{1,3}\.\d{3}\b', '', descricao)
                    
                    # Limpar espaços extras
                    descricao = re.sub(r'\s+', ' ', descricao).strip().upper()
                    
                    # Se descrição ficou vazia, usar o histórico disponível
                    if not descricao and len(partes) > 1:
                        descricao = ' '.join(partes[:-1]).strip().upper()
                    
                    valor = self.corrigir_valor_br(valor_str)
                    
                    # Determinar tipo baseado no sinal
                    if tipo_sinal == '-' or '(-)' in linha or 'D' in linha:
                        tipo = 'DEBIT'
                        valor = -abs(valor)
                    else:
                        tipo = 'CREDIT'
                        valor = abs(valor)

                    # Extrair documento (se houver algum número de 5+ dígitos)
                    doc_match = re.search(r'\b(\d{5,})\b', linha)
                    documento = doc_match.group(1) if doc_match else ''

                    transacao_em_construcao = {
                        'data': data_ofx,
                        'valor': valor,
                        'tipo': tipo,
                        'descricao': descricao,
                        'documento': documento[:10],
                        'linha_original': linha_original,
                        'sinal': tipo_sinal
                    }

        # Finalizar última transação
        if transacao_em_construcao:
            transacao_final = self._finalizar_transacao_bb(transacao_em_construcao)
            if transacao_final:
                transacoes.append(transacao_final)

        # Ordenar por data
        transacoes.sort(key=lambda x: x['data'])
        
        # Remover duplicatas
        transacoes = self._remover_duplicatas(transacoes)
        
        return transacoes

    def _finalizar_transacao_bb(self, transacao: Dict) -> Optional[Dict]:
        """Finaliza uma transação do Banco do Brasil."""
        if not transacao or transacao['valor'] == 0.0:
            return None

        # Garantir que a descrição não está vazia
        if not transacao.get('descricao'):
            transacao['descricao'] = 'TRANSACAO'
        
        # Limitar tamanho da descrição
        transacao['descricao'] = transacao['descricao'][:80]

        # Gerar FITID único
        fitid = self.gerar_fitid(
            transacao['data'], 
            transacao['valor'], 
            transacao.get('documento', ''),
            transacao['descricao']
        )
        transacao['fitid'] = fitid

        return transacao

    def _remover_duplicatas(self, transacoes: List[Dict]) -> List[Dict]:
        """Remove transações duplicadas."""
        unicas = []
        vistos = set()
        
        for t in transacoes:
            chave = f"{t['data']}_{abs(round(t['valor'] * 100))}_{abs(hash(t.get('descricao', '')[:20]))}"
            
            if chave not in vistos:
                vistos.add(chave)
                unicas.append(t)
        
        return unicas