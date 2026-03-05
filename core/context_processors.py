"""
Context Processors para adicionar dados globais ao contexto de templates
"""

from core.menu_config import get_menu_items


def menu_context(request):
    """
    Adiciona items do menu ao contexto global de templates
    Configuração em settings.py:
        TEMPLATES = [{
            'OPTIONS': {
                'context_processors': [
                    ...
                    'core.context_processors.menu_context',
                ]
            }
        }]
    """
    if not request.user.is_authenticated:
        return {'menu_items': []}
    
    pessoa = getattr(request.user, 'pessoa', None)
    menu_items = get_menu_items(request.user, pessoa)
    
    # Calcular URLs e status ativo
    for item in menu_items:
        _process_menu_item(item, request)
    
    return {
        'menu_items': menu_items,
        'has_menu': bool(menu_items),
    }


def permissions_context(request):
    """
    Adiciona funções de verificação de permissão ao contexto
    Permite usar {% if request.user|has_perm:'modulo.acao' %} em templates
    """
    if not request.user.is_authenticated:
        return {}
    
    pessoa = getattr(request.user, 'pessoa', None)
    
    return {
        'user_pessoa': pessoa,
        'user_can_manage': pessoa.has_perm_code('sistema.admin') if pessoa else False,
    }


def _process_menu_item(item, request):
    """Processa um item de menu para resolver URL e status ativo"""
    from django.urls import reverse
    import re
    
    try:
        if item.get('url_name'):
            item['url'] = reverse(item['url_name'])
        else:
            item['url'] = '#'
    except:
        item['url'] = '#'
    
    # Determina se está ativo
    if item.get('url_pattern'):
        item['is_active'] = bool(re.search(item['url_pattern'], request.path))
    else:
        item['is_active'] = request.path == item.get('url', '')
    
    # Processa subitens também
    if item.get('submenu'):
        for sub in item['submenu']:
            _process_menu_item(sub, request)
