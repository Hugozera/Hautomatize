"""
Sistema centralizado de permissões - Define todas as camadas de permissão do sistema.

Estrutura:
- PERMISSION_MAP: dicionário completo de todas as permissões
- Funções helper para verificação de permissões
"""

# ==================== PERMISSÕES POR MÓDULO ====================

PERMISSION_MAP = {
    # ===== MÓDULO: NFSE DOWNLOADER =====
    'nfse_downloader': {
        'view': 'Pode visualizar dashboard do downloader',
        'list_empresas': 'Pode listar empresas',
        'download_manual': 'Pode executar downloads manuais',
        'download_agendado': 'Pode acionar downloads agendados',
        'view_historico': 'Pode visualizar histórico de downloads',
        'export_dados': 'Pode exportar dados de downloads',
    },
    
    # ===== MÓDULO: EMPRESA =====
    'empresa': {
        'view': 'Pode visualizar dados da empresa',
        'list': 'Pode listar todas as empresas',
        'create': 'Pode criar nova empresa',
        'edit': 'Pode editar dados da empresa',
        'delete': 'Pode deletar empresa',
        'manage': 'Pode gerenciar empresa (completo)',
        'assign_users': 'Pode atribuir usuários à empresa',
        'view_financeiro': 'Pode visualizar dados financeiros',
    },
    
    # ===== MÓDULO: CERTIFICADO =====
    'certificado': {
        'view': 'Pode visualizar certificados',
        'upload': 'Pode fazer upload de certificado',
        'edit': 'Pode editar dados do certificado',
        'delete': 'Pode deletar certificado',
        'manage': 'Pode gerenciar certificados (completo)',
        'test': 'Pode testar certificado',
        'export': 'Pode exportar certificado',
        'renew': 'Pode renovar certificado',
    },
    
    # ===== MÓDULO: CONVERSOR =====
    'conversor': {
        'view': 'Pode visualizar conversor',
        'upload': 'Pode fazer upload de arquivo',
        'convert': 'Pode executar conversão',
        'download': 'Pode baixar arquivo convertido',
        'delete': 'Pode deletar conversão',
        'use': 'Pode usar conversor (geral)',
        'manage': 'Pode gerenciar conversões (completo)',
        'view_historico': 'Pode visualizar histórico de conversões',
    },
    
    # ===== MÓDULO: NOTA FISCAL =====
    'nota_fiscal': {
        'view': 'Pode visualizar notas fiscais',
        'list': 'Pode listar notas fiscais',
        'view_pdf': 'Pode visualizar PDF de nota',
        'view_xml': 'Pode visualizar XML de nota',
        'download': 'Pode baixar nota fiscal',
        'delete': 'Pode deletar nota fiscal',
        'manage': 'Pode gerenciar notas (completo)',
        'export': 'Pode exportar notas',
    },
    
    # ===== MÓDULO: PAINEL DE ATENDIMENTO =====
    'painel': {
        'view': 'Pode visualizar painel de atendimento',
        'list_atendimentos': 'Pode listar atendimentos',
        'create_atendimento': 'Pode criar novo atendimento',
        'edit_atendimento': 'Pode editar atendimento',
        'close_atendimento': 'Pode fechar atendimento',
        'delete_atendimento': 'Pode deletar atendimento',
        'view_relatorio': 'Pode visualizar relatórios',
        'manage_chat': 'Pode gerenciar chat de atendimento',
        'assign_analista': 'Pode atribuir analista',
        'manage': 'Pode gerenciar painel (completo)',
    },
    
    # ===== MÓDULO: PESSOA / USUÁRIO =====
    'pessoa': {
        'view': 'Pode visualizar dados da pessoa',
        'list': 'Pode listar pessoas',
        'create': 'Pode criar novo usuário',
        'edit': 'Pode editar dados da pessoa',
        'edit_self': 'Pode editar seus próprios dados',
        'delete': 'Pode deletar pessoa/usuário',
        'manage': 'Pode gerenciar pessoas (completo)',
        'edit_permissions': 'Pode editar permissões de pessoa',
        'view_permissions': 'Pode visualizar permissões de pessoa',
    },
    
    # ===== MÓDULO: AGENDAMENTO =====
    'agendamento': {
        'view': 'Pode visualizar agendamentos',
        'list': 'Pode listar agendamentos',
        'create': 'Pode criar agendamento',
        'edit': 'Pode editar agendamento',
        'delete': 'Pode deletar agendamento',
        'manage': 'Pode gerenciar agendamentos (completo)',
        'pause': 'Pode pausar agendamento',
        'resume': 'Pode retomar agendamento',
    },
    
    # ===== MÓDULO: RELATÓRIO =====
    'relatorio': {
        'view': 'Pode visualizar relatórios',
        'list': 'Pode listar relatórios',
        'create': 'Pode criar relatório',
        'export': 'Pode exportar relatório',
        'schedule': 'Pode agendar relatório',
        'manage': 'Pode gerenciar relatórios (completo)',
    },
    
    # ===== MÓDULO: SISTEMA / ADMIN =====
    'sistema': {
        'view_logs': 'Pode visualizar logs do sistema',
        'view_config': 'Pode visualizar configurações',
        'edit_config': 'Pode editar configurações',
        'manage_users': 'Pode gerenciar usuários',
        'manage_permissions': 'Pode gerenciar permissões',
        'backup': 'Pode fazer backup',
        'restore': 'Pode restaurar backup',
        'monitor': 'Pode monitorar sistema',
        'admin': 'Acesso administrativo completo',
    },
}

# ==================== FUNÇÕES HELPER ====================

def get_all_permissions():
    """Retorna uma lista com TODOS os códigos de permissão do sistema."""
    all_perms = []
    for module, perms in PERMISSION_MAP.items():
        for perm in perms.keys():
            all_perms.append(f"{module}.{perm}")
    return sorted(all_perms)


def get_permissions_description(perm_code):
    """Retorna a descrição de uma permissão específica."""
    module, perm = perm_code.split('.', 1) if '.' in perm_code else (perm_code, 'unknown')
    
    if module in PERMISSION_MAP and perm in PERMISSION_MAP[module]:
        return PERMISSION_MAP[module][perm]
    return 'Permissão desconhecida'


def get_module_permissions(module):
    """Retorna todas as permissões de um módulo."""
    if module not in PERMISSION_MAP:
        return {}
    return PERMISSION_MAP[module]


def has_permission(pessoa, perm_code):
    """Verifica se uma pessoa tem uma permissão específica."""
    if not pessoa:
        return False

    # Apenas permissões diretas
    return pessoa.has_perm_code(perm_code)


def get_pessoa_all_permissions(pessoa):
    """Retorna todas as permissões diretas de uma pessoa."""
    return sorted(list(set(pessoa.perm_list())))


def create_full_permission_string():
    """Cria string com todas as permissões separadas por vírgula."""
    return ','.join(get_all_permissions())


def print_permission_map():
    """Imprime um mapa legível de todas as permissões."""
    print("\n" + "="*80)
    print("MAPA COMPLETO DE PERMISSÕES DO SISTEMA")
    print("="*80 + "\n")
    
    for module, perms in PERMISSION_MAP.items():
        print(f"\n📦 MÓDULO: {module.upper()}")
        print("-" * 80)
        for perm, desc in perms.items():
            print(f"  ✓ {module}.{perm:<30} → {desc}")
    
    print("\n" + "="*80)
    print(f"TOTAL DE PERMISSÕES: {len(get_all_permissions())}")
    print("="*80 + "\n")


def print_role_map():
    """Compatibilidade legada: papéis foram descontinuados."""
    print("Papéis foram descontinuados. O sistema utiliza permissões diretas por usuário.")
