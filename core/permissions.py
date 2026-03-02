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
    """Simplified: consider any authenticated user as having the permission.

    The original system distinguished between roles, permissions, and
    superusers.  The requester wanted to remove that bureaucracy so every
    logged-in user effectively acts like a superuser.  This helper therefore
    simply returns True for any non-anonymous user. """
    if not user or user.is_anonymous:
        return False
    return True


def can_view_empresa(user, empresa: Empresa) -> bool:
    """Any authenticated user may view any empresa (simplified rules)."""
    if not user or user.is_anonymous:
        return bool(empresa.ativo)
    # authenticated users see everything
    return True


def can_edit_empresa(user, empresa: Empresa) -> bool:
    """Any authenticated user may edit any empresa (simplified rules)."""
    if not user or user.is_anonymous:
        return False
    return True




# ===== Certificado (ligado à empresa) =====
def can_manage_certificado(user, empresa: Empresa) -> bool:
    """Manage certificado only if user is superuser or linked to the empresa.

    Tests expect that only the company owner (Pessoa linked via `empresa.usuarios`)
    or a superuser may download/remove certificates. Restore that behavior.
    """
    if not user or user.is_anonymous:
        return False
    if user.is_superuser:
        return True
    pessoa = _get_pessoa_from_user(user)
    if pessoa and pessoa in empresa.usuarios.all():
        return True
    return False


# ===== Pessoa =====
def can_view_pessoa(user, pessoa_obj: Pessoa) -> bool:
    if not user or user.is_anonymous:
        return False
    return True


def can_edit_pessoa(user, pessoa_obj: Pessoa) -> bool:
    if not user or user.is_anonymous:
        return False
    return True


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
    # módulos principais
    'nfse_downloader': {
        'view': 'pode ver tela do módulo',
        'edit': 'pode editar configurações/itens',
        'delete': 'pode remover registros',
        'use': 'pode executar ações',
    },
    'conversor': {
        'view': 'pode ver tela do módulo',
        'edit': 'pode editar conversões',
        'delete': 'pode excluir conversões',
        'use': 'pode usar conversor',
    },
    'painel': {
        'view': 'pode ver painel/OS',
        'edit': 'pode atualizar atendimentos',
        'delete': 'pode excluir atendimentos',
        'use': 'pode utilizar funcionalidades de painel',
    },
    'rh': {
        'view': 'pode visualizar pessoas',
        'add': 'pode cadastrar pessoas',
        'edit': 'pode editar pessoas',
        'delete': 'pode excluir pessoas',
    },
}


# permissões adicionais usadas em outros lugares (management commands, etc.)
EXTRA_PERMISSIONS = [
    'empresa.view',
    'pessoa.edit',
    'pessoa.add',
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

