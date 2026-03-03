"""
Sistema centralizado de permissões - Define todas as camadas de permissão do sistema.

Estrutura:
- PERMISSION_MAP: dicionário completo de todas as permissões
- ROLE_DEFINITIONS: definição de papéis (roles) e suas permissões
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
        'edit_roles': 'Pode editar roles de pessoa',
        'view_permissions': 'Pode visualizar permissões de pessoa',
    },
    
    # ===== MÓDULO: ROLE (PAPEL) =====
    'role': {
        'view': 'Pode visualizar papéis',
        'list': 'Pode listar papéis',
        'create': 'Pode criar novo papel',
        'edit': 'Pode editar papel',
        'delete': 'Pode deletar papel',
        'manage': 'Pode gerenciar papéis (completo)',
        'assign_users': 'Pode atribuir papéis a usuários',
        'edit_permissions': 'Pode editar permissões de papel',
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
        'manage_roles': 'Pode gerenciar papéis',
        'manage_permissions': 'Pode gerenciar permissões',
        'backup': 'Pode fazer backup',
        'restore': 'Pode restaurar backup',
        'monitor': 'Pode monitorar sistema',
        'admin': 'Acesso administrativo completo',
    },
}

# ==================== DEFINIÇÃO DE PAPÉIS (ROLES) ====================

ROLE_DEFINITIONS = {
    'admin': {
        'name': 'Administrador',
        'codename': 'admin',
        'descricao': 'Acesso total ao sistema. Pode gerenciar todos os módulos, usuários e configurações.',
        'permissions': 'all',  # 'all' significa todas as permissões
        'ordem': 1,
    },
    
    'gestor': {
        'name': 'Gestor',
        'codename': 'gestor',
        'descricao': 'Gerencia empresas, usuários, downloads e relatórios. Sem acesso a configurações do sistema.',
        'permissions': [
            # NFSE Downloader
            'nfse_downloader.view', 'nfse_downloader.list_empresas', 
            'nfse_downloader.download_manual', 'nfse_downloader.view_historico',
            'nfse_downloader.export_dados',
            
            # Empresa
            'empresa.view', 'empresa.list', 'empresa.create', 'empresa.edit', 
            'empresa.manage', 'empresa.assign_users', 'empresa.view_financeiro',
            
            # Certificado
            'certificado.view', 'certificado.upload', 'certificado.edit',
            'certificado.manage', 'certificado.test',
            
            # Conversor
            'conversor.view', 'conversor.use', 'conversor.manage',
            
            # Nota Fiscal
            'nota_fiscal.view', 'nota_fiscal.list', 'nota_fiscal.download',
            'nota_fiscal.export', 'nota_fiscal.manage',
            
            # Painel
            'painel.view', 'painel.list_atendimentos', 'painel.create_atendimento',
            'painel.edit_atendimento', 'painel.view_relatorio', 'painel.manage',
            
            # Pessoa
            'pessoa.view', 'pessoa.list', 'pessoa.create', 'pessoa.edit',
            'pessoa.manage', 'pessoa.edit_permissions', 'pessoa.view_permissions',
            
            # Role
            'role.view', 'role.list', 'role.create', 'role.edit', 'role.manage',
            
            # Agendamento
            'agendamento.view', 'agendamento.list', 'agendamento.create',
            'agendamento.edit', 'agendamento.manage',
            
            # Relatório
            'relatorio.view', 'relatorio.list', 'relatorio.create', 'relatorio.export',
        ],
        'ordem': 2,
    },
    
    'analista': {
        'name': 'Analista',
        'codename': 'analista',
        'descricao': 'Gerencia atendimentos, pode visualizar empresas e dados. Sem permissão para editar configs ou deletar.',
        'permissions': [
            # NFSE Downloader
            'nfse_downloader.view', 'nfse_downloader.list_empresas',
            'nfse_downloader.view_historico',
            
            # Empresa
            'empresa.view', 'empresa.list',
            
            # Certificado
            'certificado.view',
            
            # Conversor
            'conversor.view', 'conversor.use',
            
            # Nota Fiscal
            'nota_fiscal.view', 'nota_fiscal.list', 'nota_fiscal.view_pdf',
            'nota_fiscal.view_xml', 'nota_fiscal.download',
            
            # Painel - Completo para atendimentos
            'painel.view', 'painel.list_atendimentos', 'painel.create_atendimento',
            'painel.edit_atendimento', 'painel.close_atendimento',
            'painel.view_relatorio', 'painel.manage_chat', 'painel.assign_analista',
            
            # Pessoa - Limitado
            'pessoa.view', 'pessoa.list', 'pessoa.edit_self',
            
            # Role
            'role.view', 'role.list',
            
            # Agendamento
            'agendamento.view', 'agendamento.list',
        ],
        'ordem': 3,
    },
    
    'operador': {
        'name': 'Operador',
        'codename': 'operador',
        'descricao': 'Executa downloads, conversões e tarefas operacionais. Sem permissão para editar configurações.',
        'permissions': [
            # NFSE Downloader - Executa
            'nfse_downloader.view', 'nfse_downloader.list_empresas',
            'nfse_downloader.download_manual', 'nfse_downloader.view_historico',
            'nfse_downloader.export_dados',
            
            # Empresa
            'empresa.view', 'empresa.list',
            
            # Certificado
            'certificado.view',
            
            # Conversor - Completo
            'conversor.view', 'conversor.upload', 'conversor.convert',
            'conversor.download', 'conversor.use', 'conversor.view_historico',
            
            # Nota Fiscal
            'nota_fiscal.view', 'nota_fiscal.list', 'nota_fiscal.download',
            'nota_fiscal.view_pdf',
            
            # Pessoa
            'pessoa.edit_self',
            
            # Agendamento
            'agendamento.view', 'agendamento.list',
        ],
        'ordem': 4,
    },
    
    'visualizador': {
        'name': 'Visualizador',
        'codename': 'visualizador',
        'descricao': 'Acesso apenas para visualização de dados. Sem permissão para criar, editar ou deletar.',
        'permissions': [
            # NFSE Downloader - Apenas visualizar
            'nfse_downloader.view', 'nfse_downloader.list_empresas',
            
            # Empresa
            'empresa.view', 'empresa.list',
            
            # Certificado
            'certificado.view',
            
            # Conversor - Apenas visualizar
            'conversor.view',
            
            # Nota Fiscal
            'nota_fiscal.view', 'nota_fiscal.list', 'nota_fiscal.view_pdf',
            'nota_fiscal.view_xml', 'nota_fiscal.download',
            
            # Painel
            'painel.view', 'painel.list_atendimentos', 'painel.view_relatorio',
            
            # Pessoa
            'pessoa.view', 'pessoa.list',
            
            # Role
            'role.view', 'role.list',
            
            # Agendamento
            'agendamento.view',
            
            # Relatório
            'relatorio.view', 'relatorio.list',
        ],
        'ordem': 5,
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


def get_permissions_for_role(role_codename):
    """Retorna as permissões de um papel específico."""
    if role_codename not in ROLE_DEFINITIONS:
        return []
    
    role_def = ROLE_DEFINITIONS[role_codename]
    perms = role_def['permissions']
    
    if perms == 'all':
        return get_all_permissions()
    elif isinstance(perms, list):
        return perms
    elif isinstance(perms, str):
        return [p.strip() for p in perms.split(',') if p.strip()]
    else:
        return []


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
    
    # Verifica permissões diretas
    if pessoa.has_perm_code(perm_code):
        return True
    
    # Verifica permissões via roles
    for role in pessoa.roles.filter(ativo=True):
        if perm_code in role.perm_list():
            return True
    
    return False


def get_pessoa_all_permissions(pessoa):
    """Retorna todas as permissões de uma pessoa (diretas + via roles)."""
    all_perms = set()
    
    # Permissões diretas
    for perm in pessoa.perm_list():
        all_perms.add(perm)
    
    # Permissões via roles
    for role in pessoa.roles.filter(ativo=True):
        for perm in role.perm_list():
            all_perms.add(perm)
    
    return sorted(list(all_perms))


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
    """Imprime um mapa legível de todos os papéis."""
    print("\n" + "="*80)
    print("DEFINIÇÃO DE PAPÉIS (ROLES)")
    print("="*80 + "\n")
    
    for role_code, role_def in ROLE_DEFINITIONS.items():
        perms = get_permissions_for_role(role_code)
        print(f"\n👤 PAPEL: {role_def['name']} (codename: {role_code})")
        print("-" * 80)
        print(f"   Descrição: {role_def['descricao']}")
        print(f"   Total de permissões: {len(perms)}")
        print(f"   Ordem/Hierarquia: {role_def['ordem']}")
        print(f"\n   Permissões:")
        for perm in sorted(perms):
            desc = get_permissions_description(perm)
            print(f"     ✓ {perm:<40} → {desc}")
    
    print("\n" + "="*80 + "\n")
