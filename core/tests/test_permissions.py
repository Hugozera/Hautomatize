from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Empresa, Pessoa
from core.permissions import can_view_empresa, check_perm


class PermissionsLogicTests(TestCase):
    def setUp(self):
        u = User.objects.create_user(username='permuser', password='x')
        self.pessoa = Pessoa.objects.create(user=u, cpf='12345678900')

    def test_check_perm_with_direct_permission(self):
        self.pessoa.permissions = 'empresa.edit,download.manage'
        self.pessoa.save()
        self.assertTrue(check_perm(self.pessoa.user, 'empresa.edit'))
        self.assertTrue(check_perm(self.pessoa.user, 'download.manage'))
        self.assertFalse(check_perm(self.pessoa.user, 'something.else'))

    def test_can_view_empresa(self):
        empresa = Empresa.objects.create(cnpj='00000000000191', razao_social='X', nome_fantasia='X')

        empresa.ativo = False
        empresa.save()
        self.assertFalse(can_view_empresa(None, empresa))

        empresa.ativo = True
        empresa.save()
        self.assertTrue(can_view_empresa(None, empresa))

        su = User.objects.create_superuser('s', 's@x', 'pwd')
        self.assertTrue(can_view_empresa(su, empresa))

        self.pessoa.permissions = 'empresa.view'
        self.pessoa.save()
        self.assertTrue(can_view_empresa(self.pessoa.user, empresa))
