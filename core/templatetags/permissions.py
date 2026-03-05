from django import template

from ..permissions import check_perm

register = template.Library()


@register.filter
def has_perm_code(user, perm_code):
    """Template filter: retorna True se o usuário possui a permissão informada."""
    try:
        return check_perm(user, perm_code)
    except Exception:
        return False
