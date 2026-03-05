"""
Testes do sistema de menu dinâmico e permissões diretas.
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from core.menu_config import MENU_CONFIG, get_menu_grouped, get_menu_items
from core.models import Pessoa
from core.permissions import check_perm


class MenuSystemTestCase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin_teste',
            email='admin@test.com',
            password='admin123',
        )
        self.admin_pessoa = Pessoa.objects.create(user=self.admin_user, cpf='11111111111')

        self.operador_user = User.objects.create_user(
            username='operador_teste',
            email='operador@test.com',
            password='operador123',
        )
        self.operador_pessoa = Pessoa.objects.create(
            user=self.operador_user,
            cpf='22222222222',
            permissions='empresa.view',
        )

        self.user_sem_permissoes = User.objects.create_user(
            username='sem_perm',
            email='sem@test.com',
            password='senha123',
        )
        self.pessoa_sem_permissoes = Pessoa.objects.create(
            user=self.user_sem_permissoes,
            cpf='33333333333',
        )

        self.client = Client()

    def test_admin_ve_mais_itens(self):
        items_admin = get_menu_items(self.admin_user, self.admin_pessoa)
        items_operador = get_menu_items(self.operador_user, self.operador_pessoa)
        self.assertGreater(len(items_admin), len(items_operador))

    def test_usuario_sem_permissoes_nao_ve_atalhos_restritos(self):
        items = get_menu_items(self.user_sem_permissoes, self.pessoa_sem_permissoes)
        labels = {item.get('label') for item in items}
        self.assertNotIn('Usuários', labels)

    def test_menu_agrupado(self):
        grouped = get_menu_grouped(self.admin_user, self.admin_pessoa)
        self.assertIn('main', grouped)
        self.assertIn('profile', grouped)

    def test_check_perm_direta(self):
        self.assertTrue(check_perm(self.operador_user, 'empresa.view'))
        self.assertFalse(check_perm(self.operador_user, 'sistema.admin'))

    def test_menu_sem_autenticacao(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(get_menu_items(AnonymousUser(), None), [])


class MenuIntegrationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='test',
            email='test@test.com',
            password='test123',
        )
        self.pessoa = Pessoa.objects.create(user=self.user, cpf='12345678901')
        self.client = Client()

    def test_home_page_renderiza_menu(self):
        self.client.login(username='test', password='test123')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'nav-item')


class MenuConfigTestCase(TestCase):
    def test_menu_config_estrutura(self):
        self.assertIn('main', MENU_CONFIG)
        self.assertIn('profile', MENU_CONFIG)

    def test_menu_items_tem_label_icon(self):
        for section_name, section_items in MENU_CONFIG.items():
            for item in section_items:
                self.assertIn('label', item, f'Item em {section_name} sem label')
                self.assertIn('icon', item, f'Item em {section_name} sem icon')

    def test_menu_items_ordem(self):
        user = User.objects.create_superuser(
            username='ordem_test',
            email='ordem@test.com',
            password='test123',
        )
        pessoa = Pessoa.objects.create(user=user, cpf='12345678901')
        items = get_menu_items(user, pessoa)
        ordens = [item.get('order', 999) for item in items]
        self.assertEqual(ordens, sorted(ordens))
