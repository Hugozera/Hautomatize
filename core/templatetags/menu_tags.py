"""
Template tags para renderizar menu dinâmico baseado em permissões
Uso: {% load menu_tags %} e depois {% render_menu user %}
"""

from django import template
from django.urls import reverse
from core.menu_config import get_menu_items
from django.utils.safestring import mark_safe

register = template.Library()


@register.inclusion_tag('core/tags/menu_items.html', takes_context=True)
def render_menu(context):
    """
    Template tag que renderiza o menu dinâmico
    Recebe o contexto e extrai usuário e pessoa
    """
    request = context.get('request')
    user = request.user if request else None
    
    # Tenta pegar a pessoa associada ao usuário
    pessoa = getattr(user, 'pessoa', None) if user else None
    
    # Obtém items do menu
    menu_items = get_menu_items(user, pessoa)
    
    # Agrupa por seção
    grouped = {}
    for item in menu_items:
        # Resolve a URL
        try:
            if item.get('url_name'):
                item['url'] = reverse(item['url_name'])
            else:
                item['url'] = '#'
        except:
            item['url'] = '#'
        
        # Determina se está ativo
        if request:
            if item.get('url_pattern'):
                import re
                item['is_active'] = bool(re.search(item['url_pattern'], request.path))
            else:
                item['is_active'] = request.path == item.get('url', '')
        
        # Processa subitens também
        if item.get('submenu'):
            for sub in item['submenu']:
                try:
                    if sub.get('url_name'):
                        sub['url'] = reverse(sub['url_name'])
                    else:
                        sub['url'] = '#'
                except:
                    sub['url'] = '#'
                
                if request:
                    sub['is_active'] = request.path == sub.get('url', '')
    
    return {
        'menu_items': menu_items,
        'request': request,
    }


@register.simple_tag(takes_context=True)
def user_can_see(context, permission_code):
    """
    Verifica se usuário pode ver algo baseado em permissão
    Uso: {% if request.user|user_can_see:'empresa.edit' %}
    """
    request = context.get('request')
    user = request.user if request else None
    
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    pessoa = getattr(user, 'pessoa', None)
    if pessoa:
        return pessoa.has_perm_code(permission_code)
    
    return False


@register.filter
def has_perm(user, perm_code):
    """
    Filtro para verificar permissão em templates
    Uso: {% if user|has_perm:'empresa.edit' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    pessoa = getattr(user, 'pessoa', None)
    if pessoa:
        return pessoa.has_perm_code(perm_code)
    
    return False


@register.simple_tag
def can_perform_action(user, action, obj=None):
    """
    Verifica se usuário pode realizar uma ação específica
    Mais semântico que has_perm
    
    Uso: {% can_perform_action user 'edit' empresa %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    # Mapear ações comuns para permissões
    action_perm_map = {
        'view': 'view',
        'create': 'create',
        'edit': 'edit',
        'delete': 'delete',
        'manage': 'manage',
        'upload': 'upload',
        'download': 'download',
        'export': 'export',
        'list': 'list',
    }
    
    # Tentar determinar o módulo do objeto
    if obj:
        obj_type = type(obj).__name__.lower()
    else:
        obj_type = 'sistema'
    
    # Construir código de permissão
    perm_code = f"{obj_type}.{action_perm_map.get(action, action)}"
    
    pessoa = getattr(user, 'pessoa', None)
    if pessoa:
        return pessoa.has_perm_code(perm_code)
    
    return False
