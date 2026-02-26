"""
Módulo de parsers para diferentes bancos.
"""

from .base_parser import BaseParser
from .caixa_parser import CaixaParser
from .itau_parser import ItauParser
from .bradesco_parser import BradescoParser
from .santander_parser import SantanderParser
from .stone_parser import StoneParser
from .bb_parser import BBParser
from .universal_parser import UniversalParser

__all__ = [
    'BaseParser',
    'CaixaParser',
    'ItauParser',
    'BradescoParser',
    'SantanderParser',
    'StoneParser',
    'BBParser',
    'UniversalParser'
]