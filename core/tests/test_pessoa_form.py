from django.contrib.auth.models import User
from django.forms import MultipleChoiceField
from django.forms.widgets import CheckboxSelectMultiple
from django.test import TestCase

from core.forms import PessoaForm
from core.models import Pessoa
from core.permissions import all_permission_codes


class PessoaFormTests(TestCase):
    def setUp(self):
        u = User.objects.create_user(username='foo', password='bar')
        self.pessoa = Pessoa.objects.create(user=u, cpf='12345678901')

    def test_fields_present(self):
        form = PessoaForm()
        self.assertNotIn('roles', form.fields)
        self.assertIn('permissions', form.fields)
        self.assertIsInstance(form.fields['permissions'], MultipleChoiceField)
        self.assertIsInstance(form.fields['permissions'].widget, CheckboxSelectMultiple)

        grouped_codes = []
        for _, choices in form.fields['permissions'].choices:
            grouped_codes.extend([code for code, _ in choices])

        for code in all_permission_codes():
            self.assertIn(code, grouped_codes)

    def test_save_permissions(self):
        data = {
            'username': 'new',
            'first_name': 'Fn',
            'last_name': 'Ln',
            'email': 'x@y.com',
            'password': 'secret',
            'password_confirm': 'secret',
            'cpf': '09876543210',
            'permissions': ['pessoa.edit', 'agendamento.manage'],
            'ativo': True,
        }
        form = PessoaForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        pessoa = form.save()
        self.assertEqual(pessoa.permissions, 'pessoa.edit,agendamento.manage')

    def test_initial_from_instance(self):
        self.pessoa.permissions = 'certificado.manage'
        self.pessoa.save()
        form = PessoaForm(instance=self.pessoa)
        self.assertEqual(form.initial['permissions'], ['certificado.manage'])

    def test_create_view_assigns_permissions(self):
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
            'permissions': ['empresa.view'],
        }
        response = client.post('/pessoas/nova/', data)
        self.assertEqual(response.status_code, 302)
        pessoa = Pessoa.objects.get(user__username='abc')
        self.assertEqual(pessoa.permissions, 'empresa.view')
