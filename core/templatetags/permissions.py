from django import template
from .. import permissions as _perms

register = template.Library()

@register.filter
def has_perm_code(user, perm_code):
    """Template filter: returns True if user has the given permission code (direct or via role)."""
    try:
        return _perms._person_has_perm(user, perm_code)
    except Exception:
        return False
