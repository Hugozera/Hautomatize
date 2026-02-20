import glob
import os
import tempfile

from django.test import TestCase

from core.conversor_service import converter_arquivo


class ConversorServiceTests(TestCase):
    def test_convert_all_pdfs_to_ofx(self):
        """Garantir que todos os exemplos em PDFS podem ser convertidos para OFX sem erros"""
        pdf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'PDFS'))
        pdfs = glob.glob(os.path.join(pdf_dir, '*.pdf'))
        self.assertTrue(pdfs, "senão houver pdfs de teste na pasta PDFS")

        for pdf in pdfs:
            with self.subTest(pdf=os.path.basename(pdf)):
                with tempfile.TemporaryDirectory() as tempdir:
                    ofx_path, err = converter_arquivo(pdf, 'ofx', output_dir=tempdir)
                    self.assertIsNone(err, f'erro de conversão para {os.path.basename(pdf)}: {err}')
                    self.assertIsNotNone(ofx_path)
                    self.assertTrue(os.path.exists(ofx_path))
                    size = os.path.getsize(ofx_path)
                    self.assertGreater(size, 100, 'ofx produzido parece vazio')
                    # verificar se há pelo menos uma transação no arquivo
                    with open(ofx_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self.assertIn('<STMTTRN>', content)

    def test_zip_input_converts_and_returns_zip(self):
        """Enviar um ZIP com alguns PDFs e verificar que um ZIP é retornado contendo os OFX"""
        pdf_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'PDFS'))
        pdfs = glob.glob(os.path.join(pdf_dir, '*.pdf'))
        self.assertTrue(pdfs, "sem pdfs de teste para zip")

        # criar zip temporário com dois primeiros pdfs (ou apenas um se houver só um)
        with tempfile.TemporaryDirectory() as tempdir:
            zip_path = os.path.join(tempdir, 'arquivos.zip')
            import zipfile
            with zipfile.ZipFile(zip_path, 'w') as zf:
                for pdf in pdfs[:2]:
                    zf.write(pdf, arcname=os.path.basename(pdf))

            out_path, err = converter_arquivo(zip_path, 'ofx', output_dir=tempdir)
            self.assertIsNone(err, f'erro ao converter zip: {err}')
            self.assertTrue(out_path.endswith('.zip'))
            self.assertTrue(os.path.exists(out_path))

            # extrair o zip de saída e verificar conteúdo OFX
            extract_dir = os.path.join(tempdir, 'outdir')
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(out_path, 'r') as zf:
                zf.extractall(extract_dir)
            ofx_files = glob.glob(os.path.join(extract_dir, '*.ofx'))
            self.assertTrue(ofx_files, 'nenhum ofx no zip de saída')
            for ofx in ofx_files:
                with open(ofx, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.assertIn('<STMTTRN>', content)

