"""
Configuração centralizada de menu lateral
Define quais itens aparecem por permissão
Facilmente extensível para novos módulos
"""

# ==================== ESTRUTURA DO MENU ====================
# Cada item pode ter:
# - 'label': texto exibido
# - 'icon': classe Bootstrap Icons (bi-*)
# - 'url_name': nome da URL (Django)
# - 'url_pattern': padrão para detecção de página ativa (ex: '/empresas')
# - 'permission': permissão necessária (ex: 'empresa.view')
# - 'submenu': lista de subitens com mesma estrutura
# - 'requires_all_perms': se True, requer TODAS as perms (default: False = qualquer uma)

MENU_CONFIG = {
    # ===== MENU PRINCIPAL =====
    'main': [
        {
            'label': 'Principal',
            'icon': 'bi-house-door',
            'url_name': 'home',
            'url_pattern': '/$',
            'permission': None,  # Todos veem
            'order': 1,
        },
        {
            'label': 'Dashboard',
            'icon': 'bi-bar-chart',
            'url_name': 'dashboard',
            'url_pattern': '/dashboard',
            'permission': 'nfse_downloader.view',
            'order': 2,
        },
    ],
    
    # ===== MODULO: DOWNLOADS =====
    'downloader': [
        {
            'label': 'Download Rápido',
            'icon': 'bi-cloud-download',
            'url_name': 'download_manual',
            'url_pattern': '/download',
            'permission': 'nfse_downloader.view',
            'order': 10,
        },
        {
            'label': 'Histórico',
            'icon': 'bi-clock-history',
            'url_name': 'historico',
            'url_pattern': '/historico',
            'permission': 'nfse_downloader.view_historico',
            'order': 11,
        },
        {
            'label': 'Programar Downloads',
            'icon': 'bi-calendar-check',
            'url_name': 'agendamento_list',
            'url_pattern': '/agendamentos',
            'permission': 'agendamento.view',
            'order': 12,
        },
    ],
    
    # ===== MODULO: EMPRESAS =====
    'empresa': [
        {
            'label': 'Empresas',
            'icon': 'bi-building',
            'url_name': 'empresa_list',
            'url_pattern': '/empresas',
            'permission': 'empresa.view',
            'order': 20,
            'submenu': [
                {
                    'label': 'Listar',
                    'icon': 'bi-list-ul',
                    'url_name': 'empresa_list',
                    'permission': 'empresa.list',
                },
                {
                    'label': 'Criar Empresa',
                    'icon': 'bi-plus-circle',
                    'url_name': 'empresa_create',
                    'permission': 'empresa.create',
                },
            ]
        },
    ],
    
    # ===== MODULO: CERTIFICADOS =====
    'certificado': [
        {
            'label': 'Certificados',
            'icon': 'bi-shield-lock',
            'url_name': 'certificado_list',
            'url_pattern': '/certificados',
            'permission': 'certificado.view',
            'order': 30,
            'submenu': [
                {
                    'label': 'Meus Certificados',
                    'icon': 'bi-list-ul',
                    'url_name': 'certificado_list',
                    'permission': 'certificado.view',
                },
                {
                    'label': 'Upload',
                    'icon': 'bi-cloud-upload',
                    'url_name': 'certificado_create',
                    'permission': 'certificado.upload',
                },
                {
                    'label': 'Testar',
                    'icon': 'bi-check-circle',
                    'url_name': 'certificado_test',
                    'permission': 'certificado.test',
                },
            ]
        },
    ],
    
    # ===== MODULO: CONVERSOR =====
    'conversor': [
        {
            'label': 'Conversor',
            'icon': 'bi-arrow-left-right',
            'url_name': 'conversor_index',
            'url_pattern': '/conversor',
            'permission': 'conversor.view',
            'order': 40,
            'submenu': [
                {
                    'label': 'Converter Arquivo',
                    'icon': 'bi-upload',
                    'url_name': 'conversor_index',
                    'permission': 'conversor.use',
                },
                {
                    'label': 'Histórico',
                    'icon': 'bi-clock-history',
                    'url_name': 'conversor_index',
                    'permission': 'conversor.view_historico',
                },
            ]
        },
    ],
    
    # ===== MODULO: SIEG =====
    'sieg': [
        {
            'label': 'SIEG',
            'icon': 'bi-clouds',
            'url_name': 'sieg_index',
            'url_pattern': '/sieg',
            'permission': None,  # Condicional via SIEG settings
            'order': 50,
        },
    ],
    
    # ===== MODULO: PAINEL / ATENDIMENTOS =====
    'painel': [
        {
            'label': 'OS / Painel',
            'icon': 'bi-kanban',
            'url_pattern': '/painel',
            'permission': 'painel.view',
            'order': 60,
            'submenu': [
                {
                    'label': 'Meu Painel',
                    'icon': 'bi-list-check',
                    'url_name': 'painel:index',
                    'permission': 'painel.view',
                },
                {
                    'label': 'Dashboard / Relatórios',
                    'icon': 'bi-bar-chart',
                    'url_name': 'painel:relatorio_gestor',
                    'permission': 'painel.view_relatorio',
                },
                {
                    'label': 'Secretaria',
                    'icon': 'bi-file-earmark-text',
                    'url_name': 'painel:secretaria_painel',
                    'permission': 'painel.view',
                },
                {
                    'label': 'Departamentos',
                    'icon': 'bi-diagram-3',
                    'url_name': 'painel:departamento_list',
                    'permission': 'sistema.manage_users',  # Admin
                },
                {
                    'label': 'Painel TV',
                    'icon': 'bi-tv',
                    'url_name': 'painel:tv_index',
                    'permission': 'sistema.view_config',
                },
            ]
        },
    ],
    
    # ===== MODULO: ADMINISTRAÇÃO =====
    'admin': [
        {
            'label': 'Usuários',
            'icon': 'bi-people',
            'url_name': 'pessoa_list',
            'url_pattern': '/pessoas',
            'permission': 'pessoa.list',
            'order': 100,
            'submenu': [
                {
                    'label': 'Listar Usuários',
                    'icon': 'bi-list-ul',
                    'url_name': 'pessoa_list',
                    'permission': 'pessoa.list',
                },
                {
                    'label': 'Criar Usuário',
                    'icon': 'bi-person-plus',
                    'url_name': 'pessoa_create',
                    'permission': 'pessoa.create',
                },
            ]
        },
        {
            'label': 'Configurações',
            'icon': 'bi-gear',
            'url_name': 'configuracao',
            'url_pattern': '/configuracao',
            'permission': None,
            'order': 200,
            'submenu': [
                {
                    'label': 'Perfil',
                    'icon': 'bi-person-circle',
                    'url_name': 'perfil',
                    'permission': None,
                },
                {
                    'label': 'Configuração Geral',
                    'icon': 'bi-toggle-on',
                    'url_name': 'configuracao',
                    'permission': 'sistema.view_config',
                },
                {
                    'label': 'Editar Configurações',
                    'icon': 'bi-pencil-square',
                    'url_name': 'configuracao',
                    'permission': 'sistema.edit_config',
                },
            ]
        },
    ],
    
    # ===== MODULO: CHAT =====
    'chat': [
        {
            'label': 'Chat',
            'icon': 'bi-chat-left-text',
            'url_name': 'chat_index',
            'url_pattern': '/chat',
            'permission': 'painel.manage_chat',
            'order': 70,
        },
    ],
    
    # ===== ITENS FINAIS =====
    'profile': [
        {
            'label': 'Sair',
            'icon': 'bi-box-arrow-right',
            'url_name': 'logout',
            'permission': None,
            'order': 201,
            'always_visible': True,
        },
    ],
}


def get_menu_items(user, pessoa=None):
    """
    Retorna lista de itens de menu que o usuário pode ver
    baseado em suas permissões
    
    Args:
        user: usuário Django
        pessoa: objeto Pessoa do usuário (se disponível)
        
    Returns:
        Lista de dicts com itens de menu
    """
    if not user.is_authenticated:
        return []
    
    visible_items = []
    
    # Se for superuser, mostra tudo
    if user.is_superuser:
        for section_items in MENU_CONFIG.values():
            visible_items.extend(section_items)
    else:
        # Filtra por permissão
        for section_items in MENU_CONFIG.values():
            for item in section_items:
                visible_item = item.copy()
                submenu_items = item.get('submenu') or []

                if submenu_items:
                    filtered_submenu = [
                        sub for sub in submenu_items
                        if (not sub.get('permission')) or _user_has_permission(pessoa, sub.get('permission'))
                    ]
                    visible_item['submenu'] = filtered_submenu
                else:
                    filtered_submenu = []

                # Item sempre visível
                if item.get('always_visible'):
                    if submenu_items and not filtered_submenu:
                        continue
                    visible_items.append(visible_item)
                    continue

                # Sem permissão requerida
                if item.get('permission') is None:
                    if submenu_items and not filtered_submenu:
                        continue
                    visible_items.append(visible_item)
                    continue

                # Verificar permissão
                if pessoa and _user_has_permission(pessoa, item.get('permission')):
                    if submenu_items and not filtered_submenu:
                        continue
                    visible_items.append(visible_item)
    
    # Ordena por 'order'
    visible_items.sort(key=lambda x: x.get('order', 999))
    
    return visible_items


def _user_has_permission(pessoa, perm_code):
    """Verifica se usuário tem uma permissão específica"""
    if not perm_code:
        return True
    
    if not pessoa:
        return False
    
    # Usa o método do modelo Pessoa
    return pessoa.has_perm_code(perm_code)


def get_menu_grouped(user, pessoa=None):
    """
    Retorna menu agrupado por seção (main, downloader, empresa, etc.)
    
    Útil para renderizar menu com nomes de seção
    """
    visible_items = get_menu_items(user, pessoa)
    
    grouped = {}
    for section_name, section_items in MENU_CONFIG.items():
        visible_section_items = [
            item for item in visible_items
            if item in section_items
        ]
        if visible_section_items:
            grouped[section_name] = visible_section_items
    
    return grouped
