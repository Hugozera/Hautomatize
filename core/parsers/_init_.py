"""
Módulo de parsers para diferentes bancos.
"""

from .caixa_parser import CaixaParser
from .itau_parser import ItauParser
from .bradesco_parser import BradescoParser
from .santander_parser import SantanderParser
from .stone_parser import StoneParser

__all__ = [
    'CaixaParser',
    'ItauParser',
    'BradescoParser',
    'SantanderParser',
    'StoneParser'
]