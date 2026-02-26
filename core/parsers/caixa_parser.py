from typing import List, Dict, Optional
import re
from .base_parser import BaseParser


class CaixaParser(BaseParser):
    """Parser específico para extratos da CAIXA - Versão otimizada."""
    
    def __init__(self):
        super().__init__()
        self.banco_id = '104'
        self.banco_nome = 'CAIXA'
    
    def detectar_banco(self, texto: str) -> bool:
        """Detecta se o texto é da CAIXA."""
        return 'CAIXA' in texto.upper() or 'CEF' in texto.upper()
    
    def extrair_transacoes(self, texto: str) -> List[Dict]:
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

        for linha in linhas:
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
                    transacao_final = self._finalizar_transacao_caixa(transacao_em_construcao)
                    if transacao_final:
                        transacoes.append(transacao_final)
                    transacao_em_construcao = None

                dia, mes, ano, hora = data_hora_match.groups()
                data_ofx = f"{ano}{mes}{dia}"

                # Extrair documento (6 dígitos após a hora)
                partes = linha.split()
                documento = ''
                for parte in partes:
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
                    valor = self.corrigir_valor_br(valor_str)
                    
                    # Determinar tipo baseado na descrição
                    if any(palavra in descricao.upper() for palavra in ['TAR', 'PAG', 'DEB', 'D']):
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
            transacao_final = self._finalizar_transacao_caixa(transacao_em_construcao)
            if transacao_final:
                transacoes.append(transacao_final)

        # Pós-processamento
        transacoes = self._processar_transacoes_caixa(transacoes)
        
        return transacoes

    def _finalizar_transacao_caixa(self, transacao: Dict) -> Optional[Dict]:
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

        # Gerar FITID único
        fitid = f"{transacao['data']}{int(abs(transacao['valor']) * 100):08d}"
        if transacao.get('documento'):
            fitid = f"{fitid}{transacao['documento']}"
        if transacao.get('hora'):
            fitid = f"{fitid}{transacao['hora'].replace(':', '')}"
        else:
            fitid = f"{fitid}{abs(hash(descricao)) % 10000:04d}"
        
        transacao['fitid'] = fitid[:30]

        return transacao

    def _processar_transacoes_caixa(self, transacoes: List[Dict]) -> List[Dict]:
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