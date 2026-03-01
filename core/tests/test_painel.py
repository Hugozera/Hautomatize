from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import Departamento, Analista, Atendimento, Empresa
from django.utils import timezone


class PainelMVPTests(TestCase):
    def setUp(self):
        self.client = Client()
        # create users
        self.coord = User.objects.create_user('coord', 'coord@example.com', 'pass')
        self.coord.is_staff = True
        self.coord.save()
        self.analista_user = User.objects.create_user('anal', 'anal@example.com', 'pass')
        # create departamento
        self.dept = Departamento.objects.create(nome='Suporte')
        # create analista linked to user
        self.analista = Analista.objects.create(user=self.analista_user, departamento=self.dept, disponivel=True)

    def test_painel_department_api_returns_data(self):
        # create an atendimento
        at = Atendimento.objects.create(empresa='ACME', departamento=self.dept, motivo='Teste', status='pendente')
        # login required for API
        self.client.login(username='coord', password='pass')
        url = reverse('painel:painel_api_department', args=[self.dept.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('analistas', data)
        self.assertIn('atendimentos', data)
        # Empresa may be omitted for pure pendentes (hidden until claimed), assert the atendimento exists
        self.assertTrue(any(a['id'] == at.pk for a in data['atendimentos']))

    def test_secretaria_ajax_create_os(self):
        # login
        self.client.login(username='coord', password='pass')
        url = reverse('painel:secretaria_painel')
        post = {'empresa': 'EmpresaX', 'empresa_id': '', 'departamento': str(self.dept.pk), 'motivo': 'Help'}
        resp = self.client.post(url, post, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(len(data.get('ultimas', [])) >= 1)

    def test_puxar_proximo_claims_and_redirects(self):
        # create pending atendimento
        at = Atendimento.objects.create(empresa='ClienteZ', departamento=self.dept, motivo='Urgente', status='pendente')
        # login as analista
        self.client.login(username='anal', password='pass')
        url = reverse('painel:puxar_proximo')
        resp = self.client.post(url)
        # after claim, should redirect to atendimento page
        self.assertEqual(resp.status_code, 302)
        at.refresh_from_db()
        self.assertEqual(at.status, 'atendendo')
        self.assertIsNotNone(at.iniciado_em)

    def test_anexo_upload_endpoint_allows_and_rejects(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        # create atendimento
        at = Atendimento.objects.create(empresa='ClienteY', departamento=self.dept, motivo='Logs', status='pendente')
        self.client.login(username='anal', password='pass')
        url = reverse('painel:atendimento_anexo_upload')
        # allowed small text file
        f = SimpleUploadedFile('log.txt', b'log content', content_type='text/plain')
        resp = self.client.post(url, {'atendimento_id': at.pk, 'anexo': f})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('status'), 'ok')
        # too large file
        big = SimpleUploadedFile('big.bin', b'a' * (11 * 1024 * 1024), content_type='application/octet-stream')
        resp2 = self.client.post(url, {'atendimento_id': at.pk, 'anexo': big})
        self.assertEqual(resp2.status_code, 400)
        # disallowed type
        bad = SimpleUploadedFile('exe.bin', b'1234', content_type='application/x-msdownload')
        resp3 = self.client.post(url, {'atendimento_id': at.pk, 'anexo': bad})
        self.assertEqual(resp3.status_code, 400)

    def test_departamento_create_assigns_analista(self):
        # make a new user to assign
        u = User.objects.create_user('newanal', 'new@example.com', 'pass')
        self.client.login(username='coord', password='pass')
        url = reverse('painel:departamento_create')
        resp = self.client.post(url, {'nome': 'NovoDept', 'analistas': [str(u.pk)]})
        self.assertEqual(resp.status_code, 302)
        d = Departamento.objects.filter(nome='NovoDept').first()
        self.assertIsNotNone(d)
        self.assertTrue(Analista.objects.filter(user=u, departamento=d).exists())

    def test_departamento_edit_updates_analistas(self):
        # existing departamento and analistas
        d = Departamento.objects.create(nome='ToEdit')
        u1 = User.objects.create_user('u1', 'u1@example.com', 'pass')
        u2 = User.objects.create_user('u2', 'u2@example.com', 'pass')
        a1 = Analista.objects.create(user=u1, departamento=d)
        # login as coord and edit to assign u2 instead
        self.client.login(username='coord', password='pass')
        url = reverse('painel:departamento_edit', args=[d.pk])
        resp = self.client.post(url, {'nome': 'ToEditUpdated', 'analistas': [str(u2.pk)]})
        self.assertEqual(resp.status_code, 302)
        d.refresh_from_db()
        self.assertEqual(d.nome, 'ToEditUpdated')
        self.assertTrue(Analista.objects.filter(user=u2, departamento=d).exists())
        self.assertFalse(Analista.objects.filter(user=u1, departamento=d).exists())
