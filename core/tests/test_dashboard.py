from django.test import TestCase
from django.contrib.auth.models import User
from core.models import Empresa, Pessoa, NotaFiscal
from django.urls import reverse
from datetime import date


class EmpresaDashboardTests(TestCase):
    def setUp(self):
        # superuser
        self.su = User.objects.create_superuser('admin', 'a@b.c', 'pwd')
        # empresa and pessoa
        u = User.objects.create_user('user1')
        self.pessoa = Pessoa.objects.create(user=u, cpf='11111111111')
        self.empresa = Empresa.objects.create(cnpj='00000000000191', razao_social='E', nome_fantasia='E')
        self.pessoa.empresas.add(self.empresa)
        # create some notas
        from core.models import HistoricoDownload
        hist = HistoricoDownload.objects.create(
            empresa=self.empresa,
            tipo_nota='entrada',
            data_inicio=date(2026,1,1),
            data_fim=date(2026,1,1),
            periodo_busca_inicio=date(2026,1,1),
            periodo_busca_fim=date(2026,1,1)
        )
        NotaFiscal.objects.create(
            empresa=self.empresa,
            historico=hist,
            numero='1',
            chave_acesso='k1',
            data_emissao=date(2026,1,1),
            valor=100,
            tipo='entrada'
        )
        NotaFiscal.objects.create(
            empresa=self.empresa,
            historico=hist,
            numero='2',
            chave_acesso='k2',
            data_emissao=date(2026,2,1),
            valor=200,
            tipo='saida'
        )

    def test_dashboard_view_basic(self):
        client = self.client
        client.login(username='admin', password='pwd')
        url = reverse('empresa_dashboard', args=[self.empresa.pk])
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Total de Notas')
        self.assertContains(resp, '100')
        self.assertContains(resp, '200')

    def test_filter_by_date(self):
        client = self.client
        client.login(username='admin', password='pwd')
        url = reverse('empresa_dashboard', args=[self.empresa.pk])
        resp = client.get(url, {'start': '2026-02-01'})
        # page should still load and context should reflect filtered notes
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_notas'], 1)
        self.assertEqual(resp.context['total_valor'], 200.0)

    def test_home_contains_module_cards(self):
        client = self.client
        client.login(username='admin', password='pwd')
        url = reverse('home')
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        # ensure module card section exists by checking link to conversor
        self.assertContains(resp, reverse('conversor_index'))
        # dark mode fixed toggle should be rendered
        self.assertContains(resp, 'id="dark-toggle-fixed"')
        # ensure external widgets removed
        self.assertNotContains(resp, 'Clima em Palmas')
        self.assertNotContains(resp, 'Notícias de Contabilidade')

    def test_dashboard_includes_dark_toggle(self):
        client = self.client
        client.login(username='admin', password='pwd')
        url = reverse('dashboard')
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="dark-toggle-fixed"')
        # widgets removed here as well
        self.assertNotContains(resp, 'Clima em Palmas')
        self.assertNotContains(resp, 'Notícias de Contabilidade')
