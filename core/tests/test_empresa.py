from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from core.models import Empresa, Pessoa


class EmpresaApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('u1', 'u1@example.com', 'pw')
        self.user2 = User.objects.create_user('u2', 'u2@example.com', 'pw')
        self.p1 = Pessoa.objects.create(user=self.user, cpf='00000000000')
        self.p2 = Pessoa.objects.create(user=self.user2, cpf='11111111111')
        self.client.login(username='u1', password='pw')

    def test_buscar_cnpj_invalid(self):
        resp = self.client.post(reverse('buscar_cnpj'), data='{"cnpj":"123"}', content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('status'), 'ERRO')

    def test_api_cep_invalid(self):
        resp = self.client.get(reverse('api_cep') + '?cep=123')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('status'), 'ERRO')

    def test_empresa_edit_permission_denied(self):
        # Criar empresa sem vincular ao usuário 1
        emp = Empresa.objects.create(cnpj='00000000000191', razao_social='X', nome_fantasia='X')
        url = reverse('empresa_edit', args=[emp.pk])
        resp = self.client.get(url)
        # usuário não deve ter acesso (redirecionado)
        self.assertIn(resp.status_code, (302, 301))

    def test_remover_certificado_requires_permission(self):
        emp = Empresa.objects.create(cnpj='00000000000191', razao_social='X', nome_fantasia='X', certificado_thumbprint='ABC')
        url = reverse('remover_certificado', args=[emp.pk])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)
