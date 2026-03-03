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
from datetime import datetime, date
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
    COM_IPF_COM_RET = "COM IPF - COM RETENÇÃO"
    COM_IPF_SEM_RET = "COM IPF - SEM RETENÇÃO"
    SEM_IPF_COM_RET = "SEM IPF - COM RETENÇÃO"
    SEM_IPF_SEM_RET = "SEM IPF - SEM RETENÇÃO"
    
    @classmethod
    def get_pasta(cls, classificacao):
        pastas = {
            cls.COM_IPF_COM_RET: "01 - COM IPF - COM RETENCAO",
            cls.COM_IPF_SEM_RET: "02 - COM IPF - SEM RETENCAO",
            cls.SEM_IPF_COM_RET: "03 - SEM IPF - COM RETENCAO",
            cls.SEM_IPF_SEM_RET: "04 - SEM IPF - SEM RETENCAO",
        }
        return pastas.get(classificacao, "05 - OUTROS")


class AnalisadorImpostos:
    """Analisa XMLs de NFSe para identificar impostos"""
    
    @staticmethod
    def analisar_xml(caminho_xml: str) -> Dict:
        resultado = {
            'tem_ipf': False,  # IPF = Impostos Federais (IRRF, PIS, COFINS, CSLL)
            'retencao_issqn': False,  # True se tpRetISSQN = 2
            'numero_nfse': Path(caminho_xml).stem,
            'classificacao': None,
            'valores': {
                'irrf': 0,
                'pis': 0,
                'cofins': 0,
                'csll': 0
            }
        }
        
        try:
            tree = ET.parse(caminho_xml)
            root = tree.getroot()
            
            # Extrair número da NFSe
            nfse_elem = root.find('.//nfse:nNFSe', NAMESPACES)
            if nfse_elem is not None and nfse_elem.text:
                resultado['numero_nfse'] = nfse_elem.text.strip()
            
            # ===== VERIFICAR IMPOSTOS FEDERAIS (IPF) =====
            # Procurar em tribFed (estrutura mais comum)
            trib_fed = root.find('.//nfse:tribFed', NAMESPACES)
            if trib_fed is not None:
                # PIS/COFINS
                piscofins = trib_fed.find('.//nfse:piscofins', NAMESPACES)
                if piscofins is not None:
                    vpis = piscofins.find('.//nfse:vPis', NAMESPACES)
                    if vpis is not None and vpis.text:
                        try:
                            valor = float(vpis.text.replace(',', '.'))
                            if valor > 0:
                                resultado['tem_ipf'] = True
                                resultado['valores']['pis'] = valor
                        except:
                            pass
                    
                    vcofins = piscofins.find('.//nfse:vCofins', NAMESPACES)
                    if vcofins is not None and vcofins.text:
                        try:
                            valor = float(vcofins.text.replace(',', '.'))
                            if valor > 0:
                                resultado['tem_ipf'] = True
                                resultado['valores']['cofins'] = valor
                        except:
                            pass
                
                # CSLL
                vcsll = trib_fed.find('.//nfse:vRetCSLL', NAMESPACES)
                if vcsll is not None and vcsll.text:
                    try:
                        valor = float(vcsll.text.replace(',', '.'))
                        if valor > 0:
                            resultado['tem_ipf'] = True
                            resultado['valores']['csll'] = valor
                    except:
                        pass
            
            # IRRF (pode estar em locais diferentes)
            locais_irrf = [
                './/nfse:vIRRF',
                './/nfse:irrf',
                './/nfse:valorIRRF',
                './/nfse:tribFed//nfse:vRetIRRF'
            ]
            for local in locais_irrf:
                elem = root.find(local, NAMESPACES)
                if elem is not None and elem.text:
                    try:
                        valor = float(elem.text.replace(',', '.'))
                        if valor > 0:
                            resultado['tem_ipf'] = True
                            resultado['valores']['irrf'] = valor
                            break
                    except:
                        pass
            
            # ===== VERIFICAR RETENÇÃO ISSQN =====
            # tpRetISSQN: 1 = SEM RETENÇÃO, 2 = COM RETENÇÃO
            locais_retencao = [
                './/nfse:tribMun//nfse:tpRetISSQN',
                './/nfse:trib//nfse:tribMun//nfse:tpRetISSQN',
                './/nfse:tpRetISSQN',
                './/tpRetISSQN'
            ]
            
            for local in locais_retencao:
                elem = root.find(local, NAMESPACES)
                if elem is not None and elem.text:
                    valor = elem.text.strip()
                    if valor == '2':  # RETIDO PELO TOMADOR
                        resultado['retencao_issqn'] = True
                        break
                    elif valor == '1':  # NÃO RETIDO
                        resultado['retencao_issqn'] = False
                        break
            
            # ===== CLASSIFICAR =====
            if resultado['tem_ipf'] and resultado['retencao_issqn']:
                resultado['classificacao'] = ClassificacaoNota.COM_IPF_COM_RET
            elif resultado['tem_ipf'] and not resultado['retencao_issqn']:
                resultado['classificacao'] = ClassificacaoNota.COM_IPF_SEM_RET
            elif not resultado['tem_ipf'] and resultado['retencao_issqn']:
                resultado['classificacao'] = ClassificacaoNota.SEM_IPF_COM_RET
            else:  # SEM IPF e SEM RETENÇÃO
                resultado['classificacao'] = ClassificacaoNota.SEM_IPF_SEM_RET
            
        except Exception as e:
            print(f"⚠️ Erro ao analisar XML {Path(caminho_xml).name}: {e}")
            resultado['classificacao'] = ClassificacaoNota.SEM_IPF_SEM_RET
        
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
        # Limpar pasta de download ANTES de começar
        if os.path.exists(self.download_path):
            try:
                shutil.rmtree(self.download_path)
            except:
                pass
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

    def _normalizar_data_iso(self, valor):
        if isinstance(valor, datetime):
            return valor.date().strftime("%Y-%m-%d")
        if isinstance(valor, date):
            return valor.strftime("%Y-%m-%d")
        return str(valor)

    def aplicar_filtro(self, tipo: str, data_inicio: str, data_fim: str):
        self._verificar_thread()
        url = f"{self.base_url}/EmissorNacional/Notas/{'Emitidas' if tipo == 'emitidas' else 'Recebidas'}"
        self.page.goto(url, timeout=10000)
        self.page.wait_for_load_state("domcontentloaded", timeout=5000)

        data_inicio = self._normalizar_data_iso(data_inicio)
        data_fim = self._normalizar_data_iso(data_fim)

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
        ClassificacaoNota.COM_IPF_COM_RET: os.path.join(pasta_org, "01 - COM IPF - COM RETENCAO"),
        ClassificacaoNota.COM_IPF_SEM_RET: os.path.join(pasta_org, "02 - COM IPF - SEM RETENCAO"),
        ClassificacaoNota.SEM_IPF_COM_RET: os.path.join(pasta_org, "03 - SEM IPF - COM RETENCAO"),
        ClassificacaoNota.SEM_IPF_SEM_RET: os.path.join(pasta_org, "04 - SEM IPF - SEM RETENCAO"),
    }
    
    for pasta in pastas.values():
        os.makedirs(pasta, exist_ok=True)
    
    # Listar arquivos
    arquivos_xml = list(Path(pasta_download).glob("*.xml"))
    arquivos_pdf = {f.stem: f for f in Path(pasta_download).glob("*.pdf")}
    
    # Estatísticas
    estatisticas = {
        'COM_IPF_COM_RET': 0,
        'COM_IPF_SEM_RET': 0,
        'SEM_IPF_COM_RET': 0,
        'SEM_IPF_SEM_RET': 0,
        'pdfs_encontrados': 0
    }
    
    print("\n📊 Classificando notas:")
    print("-" * 60)
    
    for xml_path in arquivos_xml:
        resultado = AnalisadorImpostos.analisar_xml(str(xml_path))
        pasta_dest = pastas[resultado['classificacao']]
        
        # Atualizar estatísticas
        if resultado['classificacao'] == ClassificacaoNota.COM_IPF_COM_RET:
            estatisticas['COM_IPF_COM_RET'] += 1
        elif resultado['classificacao'] == ClassificacaoNota.COM_IPF_SEM_RET:
            estatisticas['COM_IPF_SEM_RET'] += 1
        elif resultado['classificacao'] == ClassificacaoNota.SEM_IPF_COM_RET:
            estatisticas['SEM_IPF_COM_RET'] += 1
        else:
            estatisticas['SEM_IPF_SEM_RET'] += 1
        
        # Log da classificação
        ipf = "COM IPF" if resultado['tem_ipf'] else "SEM IPF"
        ret = "COM RET" if resultado['retencao_issqn'] else "SEM RET"
        valores = []
        if resultado['valores']['irrf'] > 0:
            valores.append(f"IRRF={resultado['valores']['irrf']:.2f}")
        if resultado['valores']['pis'] > 0:
            valores.append(f"PIS={resultado['valores']['pis']:.2f}")
        if resultado['valores']['cofins'] > 0:
            valores.append(f"COFINS={resultado['valores']['cofins']:.2f}")
        if resultado['valores']['csll'] > 0:
            valores.append(f"CSLL={resultado['valores']['csll']:.2f}")
        
        print(f"  📄 {xml_path.stem[:35]:35} : {ipf:8} - {ret:8} -> {os.path.basename(pasta_dest)}")
        if valores:
            print(f"      └─ Impostos: {', '.join(valores)}")
        
        # Copiar XML
        shutil.copy2(xml_path, os.path.join(pasta_dest, xml_path.name))
        
        # Copiar PDF correspondente (mesmo nome)
        if xml_path.stem in arquivos_pdf:
            pdf_path = arquivos_pdf[xml_path.stem]
            shutil.copy2(pdf_path, os.path.join(pasta_dest, pdf_path.name))
            estatisticas['pdfs_encontrados'] += 1
    
    print("-" * 60)
    print(f"\n📊 Resumo da classificação:")
    print(f"   📁 01 - COM IPF - COM RETENCAO: {estatisticas['COM_IPF_COM_RET']} notas")
    print(f"   📁 02 - COM IPF - SEM RETENCAO: {estatisticas['COM_IPF_SEM_RET']} notas")
    print(f"   📁 03 - SEM IPF - COM RETENCAO: {estatisticas['SEM_IPF_COM_RET']} notas")
    print(f"   📁 04 - SEM IPF - SEM RETENCAO: {estatisticas['SEM_IPF_SEM_RET']} notas")
    print(f"   📄 PDFs encontrados: {estatisticas['pdfs_encontrados']} de {len(arquivos_xml)} notas")
    
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

    def _normalizar_data_iso(valor):
        if isinstance(valor, datetime):
            return valor.date().strftime("%Y-%m-%d")
        if isinstance(valor, date):
            return valor.strftime("%Y-%m-%d")
        return str(valor)

    data_inicio = _normalizar_data_iso(data_inicio)
    data_fim = _normalizar_data_iso(data_fim)
    
    if not pasta_destino:
        pasta_destino = os.path.join('media', 'nfse', tipo, data_inicio[:4], data_inicio[5:7])
    
    # Adicionar identificador da empresa na pasta para evitar conflitos
    empresa_id = getattr(empresa, 'id', 'temp')
    pasta_destino = os.path.join(pasta_destino, f"empresa_{empresa_id}")
    pasta_destino = os.path.abspath(pasta_destino)
    
    # Limpar pasta específica da empresa
    if os.path.exists(pasta_destino):
        try:
            shutil.rmtree(pasta_destino)
        except:
            pass
    os.makedirs(pasta_destino, exist_ok=True)
    
    cliente = None
    
    try:
        print(f"\n{'='*60}")
        print(f"📥 INICIANDO DOWNLOAD")
        print(f"📅 Período: {data_inicio} a {data_fim}")
        print(f"📁 Empresa: {empresa_id}")
        print(f"{'='*60}")
        
        cliente = EmissorNacionalPlaywright(empresa, pasta_destino, headless=headless)
        cliente.iniciar()
        
        if not cliente.fazer_login():
            raise Exception("Falha no login")
        
        cliente.aplicar_filtro(tipo, data_inicio, data_fim)
        links, total_notas = cliente.extrair_links()
        
        if total_notas == 0:
            print("\nℹ️ Nenhuma nota encontrada no período")
            return 0, 0, pasta_destino, None
        
        print(f"\n📊 Encontradas {total_notas} notas")
        print(f"📥 Baixando {len(links)} arquivos...")
        
        sucessos = cliente.baixar_arquivos(links)
        
        if sucessos < len(links):
            print(f"⚠️ Baixados {sucessos} de {len(links)} arquivos")
        
        print(f"\n📦 Organizando e classificando...")
        zip_path = organizar_notas(pasta_destino)
        
        print(f"\n{'='*60}")
        print(f"✅ PROCESSO CONCLUÍDO!")
        print(f"📊 Total de notas: {total_notas}")
        print(f"📦 ZIP: {zip_path}")
        print(f"{'='*60}\n")
        
        return total_notas, total_notas, pasta_destino, zip_path
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        raise
    finally:
        if cliente:
            cliente.fechar()