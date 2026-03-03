"""
Serviço de automação com Playwright para o Emissor Nacional
VERSÃO OTIMIZADA - Download e classificação de notas fiscais
"""

import os
import sys
import time
import tempfile
import pickle
import asyncio
import threading
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from urllib.parse import quote
from typing import List, Dict, Tuple
import shutil
from pathlib import Path
from enum import Enum

import requests

from .certificado_service import converter_pfx_para_cert_e_key

# Namespace do XML da NFSe
NAMESPACES = {
    'nfse': 'http://www.sped.fazenda.gov.br/nfse',
    'dsig': 'http://www.w3.org/2000/09/xmldsig#'
}

# Configuração do event loop para Windows
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except:
        pass


class ClassificacaoNota(Enum):
    """Classificações possíveis para uma nota fiscal"""
    SEM_IRRF_SEM_RETENCAO = "SEM IRRF - SEM RETENÇÃO"
    SEM_IRRF_COM_RETENCAO = "SEM IRRF - COM RETENÇÃO"
    COM_IRRF_SEM_RETENCAO = "COM IRRF - SEM RETENÇÃO"
    COM_IRRF_COM_RETENCAO = "COM IRRF - COM RETENÇÃO"
    
    @classmethod
    def get_pasta(cls, classificacao):
        pastas = {
            cls.SEM_IRRF_SEM_RETENCAO: "01 - SEM IRRF - SEM RETENCAO",
            cls.SEM_IRRF_COM_RETENCAO: "02 - SEM IRRF - COM RETENCAO",
            cls.COM_IRRF_SEM_RETENCAO: "03 - COM IRRF - SEM RETENCAO",
            cls.COM_IRRF_COM_RETENCAO: "04 - COM IRRF - COM RETENCAO",
        }
        return pastas.get(classificacao, "05 - OUTROS")


class AnalisadorImpostos:
    """Analisa XMLs de NFSe para identificar impostos"""
    
    @staticmethod
    def analisar_xml(caminho_xml: str) -> Dict:
        resultado = {
            'tem_irrf': False,
            'retencao_issqn': 'NAO_INFORMADO',
            'numero_nfse': Path(caminho_xml).stem,
            'classificacao': None
        }
        
        try:
            tree = ET.parse(caminho_xml)
            root = tree.getroot()
            
            # Extrair número da NFSe
            nfse_elem = root.find('.//nfse:nNFSe', NAMESPACES)
            if nfse_elem is not None and nfse_elem.text:
                resultado['numero_nfse'] = nfse_elem.text.strip()
            
            # Verificar IRRF
            locais_irrf = ['.//nfse:vIRRF', './/nfse:irrf', './/nfse:valorIRRF']
            for local in locais_irrf:
                elem = root.find(local, NAMESPACES)
                if elem is not None and elem.text:
                    try:
                        if float(elem.text.replace(',', '.')) > 0:
                            resultado['tem_irrf'] = True
                            break
                    except:
                        pass
            
            # Verificar retenção de ISSQN
            locais_retencao = ['.//nfse:tribMun//nfse:tpRetISSQN', './/nfse:trib//nfse:tribMun//nfse:tpRetISSQN']
            for local in locais_retencao:
                elem = root.find(local, NAMESPACES)
                if elem is not None and elem.text:
                    resultado['retencao_issqn'] = 'RETIDO' if elem.text == '1' else 'NAO RETIDO'
                    break
            
            # Classificar
            if not resultado['tem_irrf'] and resultado['retencao_issqn'] == 'NAO RETIDO':
                resultado['classificacao'] = ClassificacaoNota.SEM_IRRF_SEM_RETENCAO
            elif not resultado['tem_irrf'] and resultado['retencao_issqn'] == 'RETIDO':
                resultado['classificacao'] = ClassificacaoNota.SEM_IRRF_COM_RETENCAO
            elif resultado['tem_irrf'] and resultado['retencao_issqn'] == 'NAO RETIDO':
                resultado['classificacao'] = ClassificacaoNota.COM_IRRF_SEM_RETENCAO
            elif resultado['tem_irrf'] and resultado['retencao_issqn'] == 'RETIDO':
                resultado['classificacao'] = ClassificacaoNota.COM_IRRF_COM_RETENCAO
            else:
                resultado['classificacao'] = ClassificacaoNota.SEM_IRRF_SEM_RETENCAO if not resultado['tem_irrf'] else ClassificacaoNota.COM_IRRF_SEM_RETENCAO
            
        except:
            resultado['classificacao'] = ClassificacaoNota.SEM_IRRF_SEM_RETENCAO
        
        return resultado


class EmissorNacionalPlaywright:
    """Automação com Playwright para download de notas"""
    
    def __init__(self, empresa, download_path=None, headless=True):
        self.empresa = empresa
        self.cert_path = empresa.certificado_arquivo.path
        self.senha = empresa.certificado_senha
        self.base_url = "https://www.nfse.gov.br"
        self.headless = headless
        self._thread_id = threading.get_ident()
        
        self.download_path = download_path or os.path.join(tempfile.gettempdir(), "nfse_downloads")
        os.makedirs(self.download_path, exist_ok=True)
        
        self.cert_pem = None
        self.key_pem = None
        self.context = None
        self.page = None
        self._session = None

    def _verificar_thread(self):
        if threading.get_ident() != self._thread_id:
            raise RuntimeError("Playwright não pode ser usado em threads diferentes")

    def extrair_certificado(self):
        self._verificar_thread()
        if not os.path.exists(self.cert_path):
            raise Exception("Certificado não encontrado")
        
        self.cert_pem, self.key_pem = converter_pfx_para_cert_e_key(self.cert_path, self.senha)
        if not self.cert_pem or not self.key_pem:
            raise Exception("Falha ao extrair certificado")

    def iniciar(self):
        self._verificar_thread()
        self.extrair_certificado()
        
        from playwright.sync_api import sync_playwright
        
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        
        context_options = {
            "accept_downloads": True,
            "ignore_https_errors": True,
            "client_certificates": [{
                "origin": self.base_url,
                "certPath": self.cert_pem,
                "keyPath": self.key_pem
            }]
        }
        
        self.context = self.browser.new_context(**context_options)
        self.page = self.context.new_page()
        return True

    def fazer_login(self) -> bool:
        self._verificar_thread()
        
        try:
            self.page.goto(f"{self.base_url}/EmissorNacional/Dashboard", timeout=5000)
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            if self.page.locator("a[href*='/Notas/']").count() > 0:
                return True
        except:
            pass

        try:
            self.page.goto(f"{self.base_url}/EmissorNacional/Login", timeout=10000)
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            self.page.locator("a[href*='Certificado']").first.click(timeout=5000)
            self.page.wait_for_url("**/Dashboard**", timeout=10000)
            return True
        except:
            return False

    def aplicar_filtro(self, tipo: str, data_inicio: str, data_fim: str):
        self._verificar_thread()
        url = f"{self.base_url}/EmissorNacional/Notas/{'Emitidas' if tipo == 'emitidas' else 'Recebidas'}"
        self.page.goto(url, timeout=10000)
        self.page.wait_for_load_state("domcontentloaded", timeout=5000)
        
        data_inicio_fmt = datetime.strptime(data_inicio, "%Y-%m-%d").strftime("%d/%m/%Y")
        data_fim_fmt = datetime.strptime(data_fim, "%Y-%m-%d").strftime("%d/%m/%Y")
        
        url_busca = f"{url}?executar=1&busca=&datainicio={quote(data_inicio_fmt)}&datafim={quote(data_fim_fmt)}"
        self.page.goto(url_busca, timeout=10000)
        self.page.wait_for_load_state("domcontentloaded", timeout=5000)

    def extrair_links(self) -> Tuple[List[Dict], int]:
        """Extrai links de todas as páginas"""
        self._verificar_thread()
        todos_links = []
        pagina = 1
        
        while True:
            # Extrair PDFs
            pdf_links = self.page.locator("a[href*='/Notas/Download/DANFSe/']").all()
            for link in pdf_links:
                href = link.get_attribute("href")
                if href:
                    if not href.startswith('http'):
                        href = f"https://www.nfse.gov.br{href}"
                    numero = href.split('/')[-1]
                    todos_links.append({"numero": numero, "url": href, "tipo": "PDF"})
            
            # Extrair XMLs
            xml_links = self.page.locator("a[href*='/Notas/Download/NFSe/']").all()
            for link in xml_links:
                href = link.get_attribute("href")
                if href:
                    if not href.startswith('http'):
                        href = f"https://www.nfse.gov.br{href}"
                    numero = href.split('/')[-1]
                    todos_links.append({"numero": numero, "url": href, "tipo": "XML"})
            
            # Próxima página
            proximo = self.page.locator("ul.pagination li a i.fa-angle-right").first
            if proximo.count() == 0:
                break
                
            link_pai = proximo.locator("xpath=..")
            href = link_pai.get_attribute("href")
            if not href or href == "javascript:":
                break
                
            self.page.goto(f"https://www.nfse.gov.br{href}", timeout=10000)
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            pagina += 1
            time.sleep(0.5)
        
        total_notas = len([l for l in todos_links if l['tipo'] == 'XML'])
        return todos_links, total_notas

    def baixar_arquivos(self, links: List[Dict]) -> int:
        """Download sequencial dos arquivos"""
        self._verificar_thread()
        if not links:
            return 0
        
        session = requests.Session()
        session.cert = (self.cert_pem, self.key_pem)
        session.verify = False
        
        cookies = {c['name']: c['value'] for c in self.context.cookies()}
        session.cookies.update(cookies)
        
        sucessos = 0
        total = len(links)
        
        for link in links:
            try:
                resp = session.get(link["url"], timeout=30)
                if resp.status_code == 200:
                    ext = 'pdf' if link['tipo'] == 'PDF' else 'xml'
                    filename = f"{link['numero']}.{ext}"
                    caminho = os.path.join(self.download_path, filename)
                    
                    with open(caminho, 'wb') as f:
                        f.write(resp.content)
                    sucessos += 1
            except:
                pass
        
        return sucessos

    def fechar(self):
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except:
            pass


def organizar_notas(pasta_download: str) -> str:
    """Organiza as notas em pastas por classificação"""
    
    # Criar estrutura de pastas
    pasta_org = os.path.join(pasta_download, "organizado")
    pastas = {
        ClassificacaoNota.SEM_IRRF_SEM_RETENCAO: os.path.join(pasta_org, "01 - SEM IRRF - SEM RETENCAO"),
        ClassificacaoNota.SEM_IRRF_COM_RETENCAO: os.path.join(pasta_org, "02 - SEM IRRF - COM RETENCAO"),
        ClassificacaoNota.COM_IRRF_SEM_RETENCAO: os.path.join(pasta_org, "03 - COM IRRF - SEM RETENCAO"),
        ClassificacaoNota.COM_IRRF_COM_RETENCAO: os.path.join(pasta_org, "04 - COM IRRF - COM RETENCAO"),
    }
    
    for pasta in pastas.values():
        os.makedirs(pasta, exist_ok=True)
    
    # Listar arquivos
    arquivos_xml = list(Path(pasta_download).glob("*.xml"))
    arquivos_pdf = {f.stem: f for f in Path(pasta_download).glob("*.pdf")}
    
    # Analisar e organizar
    contagem = {p: 0 for p in pastas.values()}
    
    for xml_path in arquivos_xml:
        resultado = AnalisadorImpostos.analisar_xml(str(xml_path))
        pasta_dest = pastas[resultado['classificacao']]
        
        # Copiar XML
        shutil.copy2(xml_path, os.path.join(pasta_dest, xml_path.name))
        contagem[pasta_dest] += 1
        
        # Copiar PDF correspondente (mesmo nome)
        if xml_path.stem in arquivos_pdf:
            pdf_path = arquivos_pdf[xml_path.stem]
            shutil.copy2(pdf_path, os.path.join(pasta_dest, pdf_path.name))
    
    # Criar ZIP
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(pasta_download, f"notas_{timestamp}.zip")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(pasta_org):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, pasta_org)
                zipf.write(file_path, arcname)
    
    # Limpar
    shutil.rmtree(pasta_org)
    
    return zip_path


def baixar_com_playwright(empresa, tipo, data_inicio, data_fim, pasta_destino=None, headless=True):
    """Função principal - Download e organização das notas"""
    
    if not pasta_destino:
        pasta_destino = os.path.join('media', 'nfse', tipo, data_inicio[:4], data_inicio[5:7])
    pasta_destino = os.path.abspath(pasta_destino)
    os.makedirs(pasta_destino, exist_ok=True)
    
    cliente = None
    
    try:
        print(f"\n📥 Iniciando download de {tipo} - {data_inicio} a {data_fim}")
        
        cliente = EmissorNacionalPlaywright(empresa, pasta_destino, headless=headless)
        cliente.iniciar()
        
        if not cliente.fazer_login():
            raise Exception("Falha no login")
        
        cliente.aplicar_filtro(tipo, data_inicio, data_fim)
        links, total_notas = cliente.extrair_links()
        
        if total_notas == 0:
            print("ℹ️ Nenhuma nota encontrada")
            return 0, 0, pasta_destino, None
        
        print(f"📊 Encontradas {total_notas} notas")
        print(f"📥 Baixando arquivos...")
        
        sucessos = cliente.baixar_arquivos(links)
        
        if sucessos < len(links):
            print(f"⚠️ Baixados {sucessos} de {len(links)} arquivos")
        
        print(f"📦 Organizando e compactando...")
        zip_path = organizar_notas(pasta_destino)
        
        print(f"✅ Concluído! ZIP: {zip_path}")
        
        return total_notas, total_notas, pasta_destino, zip_path
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        raise
    finally:
        if cliente:
            cliente.fechar()