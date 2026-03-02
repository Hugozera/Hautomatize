"""Delegate painel models to core.models to preserve migrations while moving implementation to core.

This module intentionally imports the implementations from `core.models` so the
app label `painel` remains available for Django's migration history.
"""

from core.models import Departamento, Analista, Atendimento, ChatMessage

__all__ = [
	'Departamento', 'Analista', 'Atendimento', 'ChatMessage'
]
