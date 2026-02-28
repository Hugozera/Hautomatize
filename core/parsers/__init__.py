"""core.parsers

Keep this module lightweight: avoid eager imports of all parser
modules so importing the package doesn't fail when a single parser
module has a typo or missing dependency. Parsers are discovered
and imported dynamically by the conversion scripts when needed.
"""

from .base_parser import BaseParser

__all__ = [
    'BaseParser',
]