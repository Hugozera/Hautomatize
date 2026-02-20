import os
import shutil
import tempfile
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from core.models import Empresa, Pessoa


class CertificadoCRUDTests(TestCase):
    def setUp(self):
        # temp media
        self.tmp_media = tempfile.mkdtemp()
        settings.MEDIA_ROOT = self.tmp_media

        # users/pessoas
        self.user_owner = User.objects.create_user('owner', password='pass')
        self.user_other = User.objects.create_user('other', password='pass')
        self.pessoa_owner = Pessoa.objects.create(user=self.user_owner, cpf='00000000000')
        self.pessoa_other = Pessoa.objects.create(user=self.user_other, cpf='11111111111')

        # empresa e associação
        self.empresa = Empresa.objects.create(cnpj='00000000000000', razao_social='ACME', nome_fantasia='ACME Ltda')
        self.empresa.usuarios.add(self.pessoa_owner)

        self.client = Client()
        self.pfx_content = b'FAKE-PFX-CONTENT'
        self.pfx_file = SimpleUploadedFile('cert.pfx', self.pfx_content, content_type='application/x-pkcs12')

    def tearDown(self):
        shutil.rmtree(self.tmp_media, ignore_errors=True)

    def test_upload_certificado_temporario_as_owner(self):
        self.client.force_login(self.user_owner)
        url = reverse('upload_certificado')
        resp = self.client.post(url, {'empresa_id': self.empresa.pk, 'senha': 'secret'}, follow=True, files={'certificado': self.pfx_file})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'OK')

        self.empresa.refresh_from_db()
        self.assertTrue(self.empresa.certificado_arquivo.name.endswith('cert.pfx'))
        self.assertEqual(self.empresa.certificado_senha, 'secret')

    def test_remover_certificado_permission_and_action(self):
        # pre-save a file
        self.empresa.certificado_arquivo.save('cert.pfx', self.pfx_file, save=True)
        self.empresa.certificado_thumbprint = 'DEADBEEF'
        self.empresa.save()

        url = reverse('remover_certificado', args=[self.empresa.pk])

        # other user cannot remove
        self.client.force_login(self.user_other)
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

        # owner can remove
        self.client.force_login(self.user_owner)
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.empresa.refresh_from_db()
        self.assertFalse(self.empresa.certificado_arquivo)
        self.assertEqual(self.empresa.certificado_thumbprint, '')

    def test_certificado_download_permissions_and_content(self):
        # pre-save
        self.empresa.certificado_arquivo.save('cert.pfx', self.pfx_file, save=True)
        self.empresa.save()

        url = reverse('certificado_download', args=[self.empresa.pk])

        self.client.force_login(self.user_other)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

        self.client.force_login(self.user_owner)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', resp.get('Content-Disposition', ''))

    def test_certificado_edit_allows_upload(self):
        self.client.force_login(self.user_owner)
        url = reverse('certificado_edit', args=[self.empresa.pk])
        file2 = SimpleUploadedFile('cert2.pfx', b'NEWFAKE', content_type='application/x-pkcs12')
        resp = self.client.post(url, {'certificado_senha': 'abc'}, follow=True, files={'certificado': file2})
        # redirect on success
        self.assertIn(resp.status_code, (200, 302))
        self.empresa.refresh_from_db()
        self.assertTrue(self.empresa.certificado_arquivo.name.endswith('cert2.pfx'))
        self.assertEqual(self.empresa.certificado_senha, 'abc')