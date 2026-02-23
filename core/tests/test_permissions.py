from django.test import TestCase
from django.contrib.auth.models import User
from core.models import Pessoa, Role
from core.permissions import _person_has_perm


class PermissionsLogicTests(TestCase):
    def setUp(self):
        u = User.objects.create_user(username='permuser', password='x')
        self.pessoa = Pessoa.objects.create(user=u, cpf='12345678900')
        # create a role that grants a permission
        self.role = Role.objects.create(name='PermRole', codename='permrole', permissions='empresa.edit', ativo=True)
        self.pessoa.roles.add(self.role)

    def test_person_has_perm_via_role(self):
        self.assertTrue(_person_has_perm(self.pessoa.user, 'empresa.edit'))
        self.assertFalse(_person_has_perm(self.pessoa.user, 'download.manage'))

    def test_person_has_direct_permission(self):
        # assign direct permission string
        self.pessoa.permissions = 'download.manage'
        self.pessoa.save()
        self.assertTrue(_person_has_perm(self.pessoa.user, 'download.manage'))
        # other permission still false
        self.assertFalse(_person_has_perm(self.pessoa.user, 'something.else'))

    def test_can_view_empresa(self):
        from core.models import Empresa
        from core.permissions import can_view_empresa
        empresa = Empresa.objects.create(cnpj='00000000000191', razao_social='X', nome_fantasia='X')
        # anonymous can only if ativo
        empresa.ativo = False
        empresa.save()
        self.assertFalse(can_view_empresa(None, empresa))
        empresa.ativo = True
        empresa.save()
        self.assertTrue(can_view_empresa(None, empresa))
        # superuser always
        su = User.objects.create_superuser('s','s@x','pwd')
        self.assertTrue(can_view_empresa(su, empresa))
        # regular but linked
        self.pessoa.empresas.add(empresa)
        self.assertTrue(can_view_empresa(self.pessoa.user, empresa))
        # permission via role
        self.pessoa.empresas.clear()
        self.pessoa.permissions = 'empresa.view'
        self.pessoa.save()
        self.assertTrue(can_view_empresa(self.pessoa.user, empresa))
