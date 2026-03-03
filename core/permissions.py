"""
Funções utilitárias para verificar permissões de domínio (Pessoa, Empresa, Certificado, Conversor).
Centraliza regras de autorização usadas pelas views, templates e management commands.

Este módulo integra-se com o sistema centralizado de permissões definido em permission_system.py
"""
from typing import Optional

from django.contrib.auth.models import AnonymousUser

from .models import Empresa, Pessoa, ArquivoConversao
from .permission_system import has_permission, get_pessoa_all_permissions


def _get_pessoa_from_user(user) -> Optional[Pessoa]:
    """Retorna o objeto Pessoa associado ao usuário."""
    if not user or isinstance(user, AnonymousUser):
        return None
    return getattr(user, 'pessoa', None)


# ==================== VERIFICAÇÕES DE PERMISSÃO POR MÓDULO ====================

# ===== EMPRESA =====

def check_perm(user, perm_code: str) -> bool:
    """Verifica se um usuário tem uma permissão específica.
    
    Args:
        user: Usuário Django
        perm_code: Código da permissão (ex: 'empresa.edit')
        
    Returns:
        True se o usuário tem a permissão (direta ou via role), False caso contrário
    """
    if not user or user.is_anonymous:
        return False
    
    if user.is_superuser:
        return True
    
    pessoa = _get_pessoa_from_user(user)
    if not pessoa:
        return False
    
    return has_permission(pessoa, perm_code)


def can_view_empresa(user, empresa: Empresa) -> bool:
    """Verifica se pode visualizar uma empresa."""
    if not user or user.is_anonymous:
        return bool(empresa.ativo)
    
    if user.is_superuser:
        return True
    
    return check_perm(user, 'empresa.view')


def can_list_empresa(user) -> bool:
    """Verifica se pode listar empresas."""
    return check_perm(user, 'empresa.list')


def can_create_empresa(user) -> bool:
    """Verifica se pode criar empresa."""
    return check_perm(user, 'empresa.create')


def can_edit_empresa(user, empresa: Empresa = None) -> bool:
    """Verifica se pode editar uma empresa."""
    return check_perm(user, 'empresa.edit') or check_perm(user, 'empresa.manage')


def can_delete_empresa(user) -> bool:
    """Verifica se pode deletar empresa."""
    return check_perm(user, 'empresa.delete') or check_perm(user, 'empresa.manage')


def can_manage_empresa(user) -> bool:
    """Verifica se pode gerenciar empresa (acesso completo)."""
    return check_perm(user, 'empresa.manage')


# ===== CERTIFICADO =====

def can_view_certificado(user) -> bool:
    """Verifica se pode visualizar certificados."""
    return check_perm(user, 'certificado.view')


def can_upload_certificado(user) -> bool:
    """Verifica se pode fazer upload de certificado."""
    return check_perm(user, 'certificado.upload') or check_perm(user, 'certificado.manage')


def can_edit_certificado(user) -> bool:
    """Verifica se pode editar certificado."""
    return check_perm(user, 'certificado.edit') or check_perm(user, 'certificado.manage')


def can_delete_certificado(user) -> bool:
    """Verifica se pode deletar certificado."""
    return check_perm(user, 'certificado.delete') or check_perm(user, 'certificado.manage')


def can_manage_certificado(user, empresa: Empresa = None) -> bool:
    """Verifica se pode gerenciar certificados (acesso completo)."""
    return check_perm(user, 'certificado.manage')


def can_test_certificado(user) -> bool:
    """Verifica se pode testar certificado."""
    return check_perm(user, 'certificado.test') or check_perm(user, 'certificado.manage')


# ===== NFSE DOWNLOADER =====

def can_view_downloader(user) -> bool:
    """Verifica se pode ver o dashboard do downloader."""
    return check_perm(user, 'nfse_downloader.view')


def can_download_manual(user) -> bool:
    """Verifica se pode executar downloads manuais."""
    return check_perm(user, 'nfse_downloader.download_manual')


def can_view_historico_download(user) -> bool:
    """Verifica se pode visualizar histórico de downloads."""
    return check_perm(user, 'nfse_downloader.view_historico')


def can_export_download_data(user) -> bool:
    """Verifica se pode exportar dados de downloads."""
    return check_perm(user, 'nfse_downloader.export_dados')


# ===== NOTA FISCAL =====

def can_view_nota_fiscal(user) -> bool:
    """Verifica se pode visualizar notas fiscais."""
    return check_perm(user, 'nota_fiscal.view')


def can_view_pdf_nota(user) -> bool:
    """Verifica se pode visualizar PDF de nota."""
    return check_perm(user, 'nota_fiscal.view_pdf')


def can_view_xml_nota(user) -> bool:
    """Verifica se pode visualizar XML de nota."""
    return check_perm(user, 'nota_fiscal.view_xml')


def can_download_nota(user) -> bool:
    """Verifica se pode baixar nota fiscal."""
    return check_perm(user, 'nota_fiscal.download')


def can_export_nota_fiscal(user) -> bool:
    """Verifica se pode exportar notas."""
    return check_perm(user, 'nota_fiscal.export')


# ===== CONVERSOR =====

def can_view_conversor(user) -> bool:
    """Verifica se pode visualizar conversor."""
    return check_perm(user, 'conversor.view')


def can_upload_arquivo_conversor(user) -> bool:
    """Verifica se pode fazer upload para conversor."""
    return check_perm(user, 'conversor.upload') or check_perm(user, 'conversor.use')


def can_convert(user) -> bool:
    """Verifica se pode executar conversão."""
    return check_perm(user, 'conversor.convert') or check_perm(user, 'conversor.use')


def can_download_convertido(user) -> bool:
    """Verifica se pode baixar arquivo convertido."""
    return check_perm(user, 'conversor.download')


def can_use_conversor(user, conversao: ArquivoConversao = None) -> bool:
    """Verifica se pode usar o conversor."""
    if not user or user.is_anonymous:
        return False
    
    if user.is_superuser:
        return True
    
    pessoa = _get_pessoa_from_user(user)
    if pessoa and conversao and conversao.usuario == pessoa:
        return True
    
    return check_perm(user, 'conversor.use')


# ===== PESSOA / USUÁRIO =====

def can_view_pessoa(user, pessoa_obj: Pessoa = None) -> bool:
    """Verifica se pode visualizar dados de pessoa."""
    return check_perm(user, 'pessoa.view')


def can_list_pessoa(user) -> bool:
    """Verifica se pode listar pessoas."""
    return check_perm(user, 'pessoa.list')


def can_create_pessoa(user) -> bool:
    """Verifica se pode criar novo usuário."""
    return check_perm(user, 'pessoa.create')


def can_edit_pessoa(user, pessoa_obj: Pessoa = None) -> bool:
    """Verifica se pode editar dados de pessoa."""
    if not user or user.is_anonymous:
        return False
    
    # Usuário pode editar seus próprios dados
    pessoa = _get_pessoa_from_user(user)
    if pessoa and pessoa == pessoa_obj:
        return check_perm(user, 'pessoa.edit_self')
    
    # Ou pode ter permissão geral para editar pessoas
    return check_perm(user, 'pessoa.edit') or check_perm(user, 'pessoa.manage')


def can_delete_pessoa(user) -> bool:
    """Verifica se pode deletar pessoa."""
    return check_perm(user, 'pessoa.delete') or check_perm(user, 'pessoa.manage')


def can_manage_pessoa(user) -> bool:
    """Verifica se pode gerenciar pessoas (acesso completo)."""
    return check_perm(user, 'pessoa.manage')


def can_edit_pessoa_permissions(user) -> bool:
    """Verifica se pode editar permissões de pessoa."""
    return check_perm(user, 'pessoa.edit_permissions')


# ===== PAINEL DE ATENDIMENTO =====

def can_view_painel(user) -> bool:
    """Verifica se pode visualizar painel."""
    return check_perm(user, 'painel.view')


def can_list_atendimentos(user) -> bool:
    """Verifica se pode listar atendimentos."""
    return check_perm(user, 'painel.list_atendimentos')


def can_create_atendimento(user) -> bool:
    """Verifica se pode criar atendimento."""
    return check_perm(user, 'painel.create_atendimento')


def can_edit_atendimento(user) -> bool:
    """Verifica se pode editar atendimento."""
    return check_perm(user, 'painel.edit_atendimento') or check_perm(user, 'painel.manage')


def can_close_atendimento(user) -> bool:
    """Verifica se pode fechar atendimento."""
    return check_perm(user, 'painel.close_atendimento')


# ===== ROLE (PAPEL) =====

def can_view_role(user) -> bool:
    """Verifica se pode visualizar papéis."""
    return check_perm(user, 'role.view')


def can_manage_role(user) -> bool:
    """Verifica se pode gerenciar papéis."""
    return check_perm(user, 'role.manage')


def can_assign_roles(user) -> bool:
    """Verifica se pode atribuir papéis a usuários."""
    return check_perm(user, 'role.assign_users')


# ===== SISTEMA / ADMIN =====

def is_admin(user) -> bool:
    """Verifica se é administrador."""
    if not user or user.is_anonymous:
        return False
    
    if user.is_superuser:
        return True
    
    return check_perm(user, 'sistema.admin')


# ==================== HELPERS GERAIS ====================

def get_user_permissions(user) -> list:
    """Retorna todas as permissões de um usuário."""
    if not user or user.is_anonymous:
        return []
    
    pessoa = _get_pessoa_from_user(user)
    if not pessoa:
        return []
    
    return get_pessoa_all_permissions(pessoa)


def user_has_any_permission(user, *perm_codes) -> bool:
    """Verifica se o usuário tem ALGUMA das permissões listadas."""
    for perm in perm_codes:
        if check_perm(user, perm):
            return True
    return False


def user_has_all_permissions(user, *perm_codes) -> bool:
    """Verifica se o usuário tem TODAS as permissões listadas."""
    for perm in perm_codes:
        if not check_perm(user, perm):
            return False
    return True


# ===== MATRIZ DE PERMISSÕES (PARA REFERÊNCIA) =====
# Importa do permission_system.py para manter consistência
from .permission_system import PERMISSION_MAP, ROLE_DEFINITIONS, get_all_permissions


def all_permission_codes():
    """Retorna uma lista com todos os códigos de permissão do sistema."""
    return get_all_permissions()

