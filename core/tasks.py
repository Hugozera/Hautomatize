"""
Tarefas em background para download de NFSe
"""
import os
import time
import zipfile
import threading
from datetime import datetime
from django.utils import timezone

from .playwright_service import baixar_com_playwright
from .models import TarefaDownload

class DownloadTask(threading.Thread):
    """Thread para executar download em background"""
    
    def __init__(self, tarefa_id, empresa, tipo, data_inicio, data_fim, pasta_destino):
        self.tarefa_id = tarefa_id
        self.empresa = empresa
        self.tipo = tipo
        self.data_inicio = data_inicio
        self.data_fim = data_fim
        self.pasta_destino = pasta_destino
        super().__init__()
    
    def log(self, mensagem):
        """Adiciona log à tarefa"""
        from .models import TarefaDownload
        try:
            tarefa = TarefaDownload.objects.get(pk=self.tarefa_id)
            tarefa.logs += f"\n[{datetime.now().strftime('%H:%M:%S')}] {mensagem}"
            tarefa.save()
        except:
            pass
        print(f"[Tarefa {self.tarefa_id}] {mensagem}")
    
    def atualizar_status(self, status, progresso=None, mensagem=None):
        """Atualiza status da tarefa"""
        from .models import TarefaDownload
        try:
            tarefa = TarefaDownload.objects.get(pk=self.tarefa_id)
            tarefa.status = status
            if progresso is not None:
                tarefa.progresso = progresso
            if mensagem:
                tarefa.mensagem = mensagem
            if status == 'processando' and not tarefa.data_inicio_execucao:
                tarefa.data_inicio_execucao = timezone.now()
            if status in ['concluido', 'erro']:
                tarefa.data_fim_execucao = timezone.now()
            tarefa.save()
        except:
            pass
    
    def atualizar_contadores(self, total, baixadas):
        """Atualiza contadores da tarefa"""
        from .models import TarefaDownload
        try:
            tarefa = TarefaDownload.objects.get(pk=self.tarefa_id)
            tarefa.total_notas = total
            tarefa.notas_baixadas = baixadas
            tarefa.notas_erro = total - baixadas
            if total > 0:
                tarefa.progresso = int((baixadas / total) * 100)
            tarefa.save()
        except:
            pass
    
    def criar_zip(self):
        """Cria arquivo ZIP com as notas baixadas"""
        self.log("📦 Criando arquivo ZIP...")
        self.atualizar_status('zipando', 95, "Compactando arquivos...")
        
        try:
            from .models import TarefaDownload
            tarefa = TarefaDownload.objects.get(pk=self.tarefa_id)
            
            # Nome do arquivo ZIP
            nome_zip = f"nfse_{self.empresa.pk}_{self.tipo}_{self.data_inicio}_a_{self.data_fim}.zip"
            # primeiro caminho dentro da pasta geral de zips (para compatibilidade histórica)
            caminho_zip = os.path.join('media', 'zips', nome_zip)
            os.makedirs(os.path.dirname(caminho_zip), exist_ok=True)
            
            # Cria o ZIP
            with zipfile.ZipFile(caminho_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                arquivos = os.listdir(self.pasta_destino)
                for arquivo in arquivos:
                    if arquivo.endswith(('.pdf', '.xml')):
                        caminho_completo = os.path.join(self.pasta_destino, arquivo)
                        zipf.write(caminho_completo, arquivo)
                        self.log(f"   Adicionado: {arquivo}")
            
            # Salva referência no modelo da tarefa
            from django.core.files import File
            with open(caminho_zip, 'rb') as f:
                tarefa.arquivo_zip.save(nome_zip, File(f), save=True)

            # Também guarda cópia no registro da empresa para acesso direto
            try:
                with open(caminho_zip, 'rb') as f:
                    self.empresa.ultimo_zip.save(nome_zip, File(f), save=True)
            except Exception as e:
                self.log(f"⚠️ Falha ao salvar ZIP na empresa: {e}")

            self.log(f"✅ ZIP criado: {caminho_zip}")
            
        except Exception as e:
            self.log(f"❌ Erro ao criar ZIP: {e}")
    
    def run(self):
        """Executa o download"""
        self.log("🚀 Iniciando tarefa de download...")
        self.atualizar_status('processando', 10, "Iniciando download...")
        
        try:
            # Executa o download
            self.atualizar_status('extraindo_links', 30, "Buscando notas...")
            
            total, baixadas, pasta = baixar_com_playwright(
                empresa=self.empresa,
                tipo=self.tipo,
                data_inicio=self.data_inicio,
                data_fim=self.data_fim,
                pasta_destino=self.pasta_destino,
                headless=True
            )
            
            # Atualiza contadores
            self.atualizar_contadores(total, baixadas)
            
            if total == 0:
                self.atualizar_status('concluido', 100, "Nenhuma nota encontrada")
                self.log("ℹ️ Nenhuma nota encontrada")
                return
            
            # Cria ZIP
            self.criar_zip()
            
            # Dispara parsing assíncrono dos XMLs baixados (sem bloquear esta thread)
            parser = XMLParseThread(self.pasta_destino, self.empresa.pk)
            parser.start()
            
            # Finaliza
            self.atualizar_status('concluido', 100, f"Download concluído! {baixadas}/{total} notas")
            self.log(f"✅ Tarefa concluída! {baixadas}/{total} notas baixadas")
            
        except Exception as e:
            self.log(f"❌ Erro: {e}")
            self.atualizar_status('erro', 0, str(e))
            import traceback
            traceback.print_exc()




class XMLParseThread(threading.Thread):
    """Thread que percorre a pasta de XMLs e extrai dados para o banco."""
    def __init__(self, pasta, empresa_pk):
        super().__init__()
        self.pasta = pasta
        self.empresa_pk = empresa_pk

    def run(self):
        # está rodando em background; qualquer exceção não deve interromper o processo
        try:
            from .models import NotaFiscal, Empresa
            from xml.etree import ElementTree as ET
            empresa = Empresa.objects.get(pk=self.empresa_pk)
            # cria um historico mínimo para ligar as notas se não existir
            from .models import HistoricoDownload
            hist, _ = HistoricoDownload.objects.get_or_create(
                empresa=empresa,
                defaults={
                    'tipo_nota': 'entrada',
                    'data_inicio': timezone.now(),
                    'data_fim': timezone.now(),
                    'periodo_busca_inicio': timezone.now().date(),
                    'periodo_busca_fim': timezone.now().date(),
                }
            )
            for nome in os.listdir(self.pasta):
                if nome.lower().endswith('.xml'):
                    path = os.path.join(self.pasta, nome)
                    try:
                        tree = ET.parse(path)
                        root = tree.getroot()
                        # placeholder: extrair impostos e demais informações
                        impostos = {}
                        # TODO: implementar parser real conforme schema XML
                        # Exemplo:
                        # for imp in root.findall('.//Imposto'):
                        #     impostos[imp.attrib.get('Tipo')] = float(imp.text or 0)
                        # atualiza ou cria nota fiscal correspondente
                        chave = root.findtext('.//chave') or ''
                        # when creating note use safe defaults for required fields
                        nota, created = NotaFiscal.objects.get_or_create(
                            chave_acesso=chave,
                            empresa=empresa,
                            defaults={
                                'arquivo_xml': f'xmls/{nome}',
                                'numero': chave or nome,
                                'data_emissao': timezone.now().date(),
                                'valor': 0,
                                'tipo': 'entrada',
                                'historico': hist,
                            }
                        )
                        nota.impostos = impostos
                        nota.save()
                    except Exception as e:
                        print(f"Erro ao parsear XML {nome}: {e}")
        except Exception as e:
            print(f"Falha na thread de parsing de XML: {e}")


def iniciar_download_tarefa(empresa, tipo, data_inicio, data_fim, pasta_destino, usuario=None):
    """
    Inicia uma nova tarefa de download em background
    """
    from .models import TarefaDownload
    
    # Cria a tarefa no banco
    tarefa = TarefaDownload.objects.create(
        usuario=usuario,
        empresa=empresa,
        tipo_nota=tipo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        pasta_destino=pasta_destino,
        status='aguardando',
        progresso=0,
        logs=f"Tarefa criada em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )
    
    # Inicia a thread
    thread = DownloadTask(
        tarefa_id=tarefa.pk,
        empresa=empresa,
        tipo=tipo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        pasta_destino=pasta_destino
    )
    thread.start()
    
    return tarefa.pk