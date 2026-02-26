from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import re


class BaseParser(ABC):
    """Classe base abstrata para todos os parsers de banco."""
    
    def __init__(self):
        self.banco_id = '000'
        self.banco_nome = 'DESCONHECIDO'
    
    @abstractmethod
    def extrair_transacoes(self, texto: str) -> List[Dict]:
        """
        Método abstrato que deve ser implementado por cada parser específico.
        """
        pass
    
    def detectar_banco(self, texto: str) -> bool:
        """
        Detecta se o texto pertence a este banco.
        Deve ser sobrescrito por cada parser.
        """
        return False
    
    @staticmethod
    def corrigir_valor_br(valor_str: str) -> float:
        """Converte string de valor brasileiro para float."""
        if not valor_str:
            return 0.0
        
        valor_str = re.sub(r'[R\$\s]', '', valor_str)
        
        if ',' in valor_str and len(valor_str.split(',')[1]) > 2:
            parte_int, parte_dec = valor_str.split(',')
            valor_str = f"{parte_int},{parte_dec[:2]}"
        
        if '.' in valor_str and ',' in valor_str:
            try:
                valor_limpo = valor_str.replace('.', '').replace(',', '.')
                return float(valor_limpo)
            except:
                pass
        
        elif ',' in valor_str and '.' not in valor_str:
            try:
                valor_limpo = valor_str.replace(',', '.')
                return float(valor_limpo)
            except:
                pass
        
        try:
            valor_limpo = re.sub(r'[^\d,]', '', valor_str)
            valor_limpo = valor_limpo.replace(',', '.')
            return float(valor_limpo)
        except:
            return 0.0
    
    @staticmethod
    def gerar_fitid(data: str, valor: float, documento: str = '', descricao: str = '') -> str:
        """Gera um FITID único para a transação."""
        valor_int = int(abs(valor) * 100)
        fitid = f"{data}{valor_int:08d}"
        
        if documento:
            fitid = f"{fitid}{documento[:6]}"
        else:
            fitid = f"{fitid}{abs(hash(descricao)) % 10000:04d}"
        
        return fitid[:30]