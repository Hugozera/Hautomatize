from django import template

from .. import permissions as _perms

register = template.Library()


@register.simple_tag
def can_edit_empresa(user, empresa):
    return _perms.can_edit_empresa(user, empresa)


@register.simple_tag
def can_view_empresa(user, empresa):
    return _perms.can_view_empresa(user, empresa)


@register.simple_tag
def can_manage_certificado(user, empresa):
    return _perms.can_manage_certificado(user, empresa)


@register.simple_tag
def can_use_conversor(user, conversao):
    return _perms.can_use_conversor(user, conversao)


@register.simple_tag
def can_edit_pessoa(user, pessoa):
    return _perms.can_edit_pessoa(user, pessoa)
