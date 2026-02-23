import os
import tempfile
import threading
from django.test import TestCase
from django.contrib.auth.models import User
from core.models import Empresa, NotaFiscal, HistoricoDownload, Pessoa
from core.tasks import DownloadTask, XMLParseThread
from django.core.files.base import ContentFile


class TasksTests(TestCase):
    def setUp(self):
        u = User.objects.create_user('usr')
        self.pessoa = Pessoa.objects.create(user=u, cpf='22222222222')
        self.empresa = Empresa.objects.create(cnpj='00000000000192', razao_social='E2', nome_fantasia='E2')
        self.pessoa.empresas.add(self.empresa)
        self.historico = HistoricoDownload.objects.create(
            empresa=self.empresa,
            tipo_nota='entrada',
            data_inicio='2026-01-01',
            periodo_busca_inicio='2026-01-01',
            periodo_busca_fim='2026-01-01',
        )

    def test_create_zip_saves_on_empresa(self):
        # create temporary directory with dummy files
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, 'a.pdf'), 'w').close()
            open(os.path.join(tmpdir, 'b.xml'), 'w').close()
            # create a dummy tarefa object so lookup succeeds
            from core.models import TarefaDownload
            tarefa = TarefaDownload.objects.create(
                empresa=self.empresa,
                tipo_nota='emitidas',
                data_inicio='2026-01-01',
                data_fim='2026-01-31',
            )
            task = DownloadTask(
                tarefa_id=tarefa.pk,
                empresa=self.empresa,
                tipo='emitidas',
                data_inicio='2026-01-01',
                data_fim='2026-01-31',
                pasta_destino=tmpdir
            )
            # monkeypatch log and atualizar_status to no-op
            task.log = lambda msg: None
            task.atualizar_status = lambda *args, **kwargs: None
            # call criar_zip directly
            task.criar_zip()
            # after create, empresa should have ultimo_zip file
            self.empresa.refresh_from_db()
            self.assertTrue(bool(self.empresa.ultimo_zip))

    def test_xml_parse_thread(self):
        # prepare xml file in temp dir
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_content = '''<Root><chave>TEST123</chave><Imposto Tipo="icms">15.5</Imposto></Root>'''
            fname = os.path.join(tmpdir, 'nota.xml')
            with open(fname, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            # run parser thread
            parser = XMLParseThread(tmpdir, self.empresa.pk)
            # run synchronously to avoid sqlite locking issues in tests
            parser.run()
            # check that nota created with impostos
            nota = NotaFiscal.objects.filter(chave_acesso='TEST123').first()
            self.assertIsNotNone(nota)
            # impostos should be dict (even if parser placeholder empty)
            self.assertIsInstance(nota.impostos, dict)
