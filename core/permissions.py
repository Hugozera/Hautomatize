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

def _person_has_perm(user, perm_code: str) -> bool:
    """Retorna True se a pessoa possuir `perm_code` diretamente ou via roles."""
    pessoa = _get_pessoa_from_user(user)
    if not pessoa:
        return False
    # permissões diretas
    if perm_code in (getattr(pessoa, 'permissions', '') or '').split(','):
        return True
    # permissões herdadas de roles
    for role in getattr(pessoa, 'roles').all():
        if perm_code in role.perm_list():
            return True
    return False


def can_view_empresa(user, empresa: Empresa) -> bool:
    """Usuário pode visualizar a empresa?

    Segue regra da matriz: superuser, usuário ligado, ou público se empresa.ativo.
    Também considera permissão explícita ``empresa.view`` quando presente em
    roles/permissions da pessoa.
    """
    if not user or user.is_anonymous:
        return bool(empresa.ativo)
    if user.is_superuser:
        return True
    pessoa = _get_pessoa_from_user(user)
    if pessoa and pessoa in empresa.usuarios.all():
        return True
    if _person_has_perm(user, 'empresa.view'):
        return True
    return bool(empresa.ativo)


def can_edit_empresa(user, empresa: Empresa) -> bool:
    """Usuário pode editar a empresa?"""
    if not user or user.is_anonymous:
        return False
    if user.is_superuser:
        return True
    pessoa = _get_pessoa_from_user(user)
    if pessoa and pessoa in empresa.usuarios.all():
        return True
    # check custom permissions/roles
    if _person_has_perm(user, 'empresa.edit'):
        return True
    return False




# ===== Certificado (ligado à empresa) =====
def can_manage_certificado(user, empresa: Empresa) -> bool:
    """Permissão para salvar/remover/baixar certificado associado a `empresa`."""
    if can_edit_empresa(user, empresa):
        return True
    # permissions/roles
    return _person_has_perm(user, 'certificado.manage')


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
    # permissions/roles
    return _person_has_perm(user, 'conversor.use')


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

# permissões adicionais usadas em outros lugares (management commands, etc.)
EXTRA_PERMISSIONS = [
    'empresa.view',
    'pessoa.edit',
    'agendamento.manage',
    'download.manage',
    'historico.view',
    'role.manage',
]


def all_permission_codes():
    """Retorna uma lista com todos os códigos de permissão conhecidos.

    Combina os valores definidos em PERMISSIONS_MATRIX com qualquer código extra
    que não faça parte das regras de autorização englobadas pelo matrix.
    """
    codes = []
    for model, perms in PERMISSIONS_MATRIX.items():
        for k in perms.keys():
            codes.append(f"{model.lower()}.{k}")
    codes.extend(EXTRA_PERMISSIONS)
    # remover duplicatas e ordenar para consistência
    return sorted(set(codes))

