"""Funções utilitárias para verificar permissões de domínio (Pessoa, Empresa, Certificado, Conversor).
Centraliza regras de autorização usadas pelas views e templates.
"""
from typing import Optional

from django.contrib.auth.models import AnonymousUser

from .models import Empresa, Pessoa, ArquivoConversao


def _get_pessoa_from_user(user) -> Optional[Pessoa]:
    if not user or isinstance(user, AnonymousUser):
        return None
    return getattr(user, 'pessoa', None)


# ===== Empresa =====
def _person_has_role_perm(user, perm_code: str) -> bool:
    """Retorna True se o usuário (via Pessoa) tiver um Role que contenha perm_code."""
    pessoa = _get_pessoa_from_user(user)
    if not pessoa:
        return False
    for role in getattr(pessoa, 'roles').all():
        if perm_code in role.perm_list():
            return True
    return False


def can_edit_empresa(user, empresa: Empresa) -> bool:
    """Usuário pode editar a empresa?"""
    if not user or user.is_anonymous:
        return False
    if user.is_superuser:
        return True
    pessoa = _get_pessoa_from_user(user)
    if pessoa and pessoa in empresa.usuarios.all():
        return True
    # roles-based permission (ex.: 'empresa.edit')
    if _person_has_role_perm(user, 'empresa.edit'):
        return True
    return False


def can_edit_empresa(user, empresa: Empresa) -> bool:
    """Usuário pode editar a empresa (incluir certificado, alterar dados)?"""
    if not user or user.is_anonymous:
        return False
    if user.is_superuser:
        return True
    pessoa = _get_pessoa_from_user(user)
    return bool(pessoa and pessoa in empresa.usuarios.all())


# ===== Certificado (ligado à empresa) =====
def can_manage_certificado(user, empresa: Empresa) -> bool:
    """Permissão para salvar/remover/baixar certificado associado a `empresa`."""
    if can_edit_empresa(user, empresa):
        return True
    # roles-based permission (ex.: 'certificado.manage')
    return _person_has_role_perm(user, 'certificado.manage')


# ===== Pessoa =====
def can_view_pessoa(user, pessoa_obj: Pessoa) -> bool:
    if not user or user.is_anonymous:
        return False
    if user.is_superuser:
        return True
    return user == pessoa_obj.user


def can_edit_pessoa(user, pessoa_obj: Pessoa) -> bool:
    if not user or user.is_anonymous:
        return False
    if user.is_superuser:
        return True
    return user == pessoa_obj.user


# ===== Conversor (ArquivoConversao) =====
def can_use_conversor(user, conversao: ArquivoConversao) -> bool:
    """Permissão para visualizar/processar/download de uma conversão específica."""
    if not user or user.is_anonymous:
        return False
    if user.is_superuser:
        return True
    pessoa = _get_pessoa_from_user(user)
    if pessoa and conversao.usuario == pessoa:
        return True
    # roles-based permission (ex.: 'conversor.use')
    return _person_has_role_perm(user, 'conversor.use')


# Matriz de permissões (para documentação/consulta rápida)
PERMISSIONS_MATRIX = {
    'Pessoa': {
        'view': 'self or superuser',
        'edit': 'self or superuser'
    },
    'Empresa': {
        'view': 'superuser or linked user or public if ativo',
        'edit': 'superuser or linked user'
    },
    'Certificado': {
        'manage': 'same as Empresa.edit (superuser or linked user)'
    },
    'Conversor': {
        'use': 'owner (u.pessoa) or superuser'
    }
}
