from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import Pessoa


class AuthProfileTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.username = 'testuser'
        self.password = 'p@ssw0rd123'
        self.user = User.objects.create_user(username=self.username, password=self.password, first_name='Teste', last_name='User', email='t@example.com')

    def test_logout_view_logs_out(self):
        self.client.login(username=self.username, password=self.password)
        resp = self.client.get('/logout/')
        # logout deve redirecionar para a página de login
        self.assertIn(resp.status_code, (302, 303))
        # após logout, acessar perfil deve redirecionar para login
        r2 = self.client.get(reverse('perfil'))
        self.assertIn(r2.status_code, (302, 303))

    def test_profile_without_pessoa_redirects_to_create(self):
        self.client.login(username=self.username, password=self.password)
        resp = self.client.get(reverse('perfil'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('pessoa_create'), resp['Location'])

    def test_profile_shows_pessoa_data(self):
        pessoa = Pessoa.objects.create(user=self.user, cpf='12345678901', telefone='(11)99999-9999')
        self.client.login(username=self.username, password=self.password)
        resp = self.client.get(reverse('perfil'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '12345678901')
        self.assertContains(resp, 'Teste')

    def test_certificado_info_returns_empresa(self):
        from core.models import Empresa
        Empresa.objects.create(cnpj='00000000000191', nome_fantasia='ACME', razao_social='ACME Ltda', certificado_thumbprint='DEADBEEF')
        self.client.login(username=self.username, password=self.password)
        resp = self.client.get(reverse('certificado_info') + '?thumbprint=DEADBEEF')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('empresas', resp.json())
        self.assertTrue(len(resp.json()['empresas']) >= 1)

