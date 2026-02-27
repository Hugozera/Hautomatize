from django.test import TestCase

from core.forms import PessoaForm
from core.models import Pessoa, Role
from django.contrib.auth.models import User
from core.permissions import all_permission_codes


class PessoaFormTests(TestCase):
    def setUp(self):
        # create a couple of roles for selection
        self.r1 = Role.objects.create(name='R1', codename='r1', permissions='empresa.edit', ativo=True)
        self.r2 = Role.objects.create(name='R2', codename='r2', permissions='download.manage', ativo=True)
        # create a user and pessoa for editing tests
        u = User.objects.create_user(username='foo', password='bar')
        self.pessoa = Pessoa.objects.create(user=u, cpf='12345678901')

    def test_fields_present(self):
        form = PessoaForm()
        self.assertIn('roles', form.fields)
        self.assertIn('permissions', form.fields)
        # roles field should be ModelMultipleChoice and permissions as checkbox
        from django.forms import ModelMultipleChoiceField, MultipleChoiceField
        from django.forms.widgets import CheckboxSelectMultiple
        self.assertIsInstance(form.fields['roles'], ModelMultipleChoiceField)
        from django.forms.widgets import CheckboxSelectMultiple
        self.assertIsInstance(form.fields['roles'].widget, CheckboxSelectMultiple)
        self.assertIsInstance(form.fields['permissions'], MultipleChoiceField)
        self.assertIsInstance(form.fields['permissions'].widget, CheckboxSelectMultiple)
        # choices for permissions should include all codes
        codes = [c for c, _ in form.fields['permissions'].choices]
        for code in all_permission_codes():
            self.assertIn(code, codes)

    def test_save_permissions_and_roles(self):
        data = {
            'username': 'new',
            'first_name': 'Fn',
            'last_name': 'Ln',
            'email': 'x@y.com',
            'password': 'secret',
            'password_confirm': 'secret',
            'cpf': '09876543210',
            'roles': [self.r1.pk, self.r2.pk],
            'permissions': ['pessoa.edit', 'agendamento.manage'],
            'ativo': True,
        }
        form = PessoaForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        pessoa = form.save()
        self.assertEqual(pessoa.permissions, 'pessoa.edit,agendamento.manage')
        self.assertEqual(set(pessoa.roles.all()), {self.r1, self.r2})

    def test_initial_from_instance(self):
        # assign roles and perms to existing pessoa
        self.pessoa.roles.add(self.r1)
        self.pessoa.permissions = 'certificado.manage'
        self.pessoa.save()
        form = PessoaForm(instance=self.pessoa)
        self.assertEqual(set(form.initial['roles']), {self.r1})
        self.assertEqual(form.initial['permissions'], ['certificado.manage'])

    def test_create_view_assigns_roles_and_permissions(self):
        # login as superuser to access create
        admin = User.objects.create_superuser(username='adm', email='adm@test', password='pwd')
        client = self.client
        client.login(username='adm', password='pwd')
        data = {
            'username': 'abc',
            'first_name': 'A',
            'last_name': 'B',
            'email': 'x@y.com',
            'password': 'pass1234',
            'password_confirm': 'pass1234',
            'cpf': '99999999999',
            'ativo': True,
            'roles': [self.r2.pk],
            'permissions': ['empresa.view'],
        }
        response = client.post('/pessoas/nova/', data)
        # should redirect back to list
        self.assertEqual(response.status_code, 302)
        pessoa = Pessoa.objects.get(user__username='abc')
        self.assertEqual(pessoa.permissions, 'empresa.view')
        self.assertEqual(list(pessoa.roles.all()), [self.r2])
