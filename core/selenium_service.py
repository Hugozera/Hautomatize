"""
Serviço de automação com Selenium para o Emissor Nacional
Usa o certificado exportado da empresa (arquivo .pfx)
Download automático de NFSe em segundo plano
"""

from datetime import datetime
from urllib.parse import quote
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import sys
import tempfile
import subprocess
import pickle
import traceback

# Força saída imediata no console
try:
    sys.stdout.reconfigure(line_buffering=True)
except:
    class Unbuffered:
        def __init__(self, stream):
            self.stream = stream
        def write(self, data):
            self.stream.write(data)
            self.stream.flush()
        def __getattr__(self, attr):
            return getattr(self.stream, attr)
    sys.stdout = Unbuffered(sys.stdout)

print("\n" + "="*70)
print("🔵 SELENIUM_SERVICE.PY CARREGADO")
print("="*70)
sys.stdout.flush()

class EmissorNacionalSelenium:
    """
    Classe para automação do Emissor Nacional usando Selenium
    Usa certificado exportado da empresa
    """
    
    def __init__(self, empresa, download_path=None):
        """
        Inicializa com os dados da empresa
        Args:
            empresa: Objeto Empresa do Django (com certificado_arquivo, certificado_senha)
            download_path: Pasta onde salvar os arquivos
        """
        self.empresa = empresa
        self.thumbprint = empresa.certificado_thumbprint
        self.senha = empresa.certificado_senha
        self.certificado_arquivo = empresa.certificado_arquivo
        self.driver = None
        self.base_url = "https://www.nfse.gov.br"
        self.pem_path = None
        self.cookies_path = None
        self.headless_mode = False
        
        # Configura pasta de download
        if download_path:
            self.download_path = download_path
        else:
            self.download_path = os.path.join(tempfile.gettempdir(), 'nfse_downloads')
        
        os.makedirs(self.download_path, exist_ok=True)
        print(f"📁 Pasta de download: {self.download_path}")
        sys.stdout.flush()
        
        # Caminho para o certificado
        self.cert_path = None
        if self.certificado_arquivo and hasattr(self.certificado_arquivo, 'path'):
            self.cert_path = self.certificado_arquivo.path
            print(f"📌 Certificado da empresa: {self.cert_path}")
            sys.stdout.flush()
            
            if not os.path.exists(self.cert_path):
                print(f"⚠️ Arquivo de certificado não encontrado: {self.cert_path}")
                sys.stdout.flush()
            else:
                print(f"✅ Certificado encontrado! Tamanho: {os.path.getsize(self.cert_path)} bytes")
                sys.stdout.flush()
        
        # Caminho para cookies
        if self.thumbprint:
            self.cookies_path = os.path.join(tempfile.gettempdir(), f"cookies_{self.thumbprint[:8]}.pkl")
            print(f"📌 Arquivo de cookies: {self.cookies_path}")
            sys.stdout.flush()
    
    def exportar_certificado_para_pem(self):
        """Converte o certificado .pfx para .pem"""
        if not self.cert_path or not os.path.exists(self.cert_path):
            return None
        
        try:
            fd, pem_path = tempfile.mkstemp(suffix='.pem')
            os.close(fd)
            
            print(f"   Convertendo {self.cert_path} para PEM...")
            sys.stdout.flush()
            
            cmd = [
                'openssl', 'pkcs12',
                '-in', self.cert_path,
                '-out', pem_path,
                '-nodes',
                '-password', f'pass:{self.senha}'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.getsize(pem_path) > 0:
                print("   ✅ Certificado convertido para PEM")
                sys.stdout.flush()
                return pem_path
            else:
                print(f"   ❌ Erro na conversão: {result.stderr}")
                sys.stdout.flush()
                if os.path.exists(pem_path):
                    os.remove(pem_path)
                return None
                
        except Exception as e:
            print(f"   ❌ Erro ao converter certificado: {e}")
            sys.stdout.flush()
            return None
    
    def configurar_certificado_chrome(self, options):
        """Configura o Chrome para usar o certificado"""
        if not self.cert_path:
            return options
        
        pem_path = self.exportar_certificado_para_pem()
        if pem_path:
            options.add_argument(f'--client-certificate={pem_path}')
            options.add_argument('--auto-select-certificate')
            options.add_argument('--enable-features=PlatformCertificateVerification')
            print("   ✅ Certificado configurado no Chrome")
            sys.stdout.flush()
            self.pem_path = pem_path
        
        return options
    
    def iniciar_driver(self):
        """Inicializa o ChromeDriver com configurações apropriadas"""
        print("\n🚀 Iniciando ChromeDriver...")
        sys.stdout.flush()
        
        options = Options()
        options = self.configurar_certificado_chrome(options)
        
        # Configurações básicas
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--allow-insecure-localhost')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--auto-select-certificate')
        options.add_argument('--enable-features=PlatformCertificateVerification')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # Configura pasta de download
        prefs = {
            "download.default_directory": self.download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        options.add_experimental_option("prefs", prefs)
        
        # Decide modo headless baseado nos cookies
        if self.cookies_path and os.path.exists(self.cookies_path):
            self.headless_mode = True
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--window-size=1920,1080')
            print("   🔒 Modo automático ativado (já tem cookies salvos)")
        else:
            self.headless_mode = False
            print("   👁️ Modo visível (primeira vez - precisa selecionar certificado)")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            print("✅ ChromeDriver iniciado com sucesso!")
            sys.stdout.flush()
            return True
        except Exception as e:
            print(f"❌ Erro ao iniciar ChromeDriver: {e}")
            sys.stdout.flush()
            traceback.print_exc()
            return False
    
    def salvar_cookies(self):
        """Salva os cookies após login bem-sucedido"""
        if not self.cookies_path or not self.driver:
            return
        
        try:
            with open(self.cookies_path, 'wb') as f:
                pickle.dump(self.driver.get_cookies(), f)
            print(f"✅ Cookies salvos permanentemente em: {self.cookies_path}")
            sys.stdout.flush()
            return True
        except Exception as e:
            print(f"⚠️ Erro ao salvar cookies: {e}")
            sys.stdout.flush()
            return False
    
    def carregar_cookies(self):
        """Carrega cookies salvos para evitar novo login"""
        if not self.cookies_path or not os.path.exists(self.cookies_path):
            print("   📂 Nenhum cookie encontrado")
            return False
        
        try:
            with open(self.cookies_path, 'rb') as f:
                cookies = pickle.load(f)
            
            print(f"   📂 Carregando {len(cookies)} cookies...")
            sys.stdout.flush()
            
            self.driver.get(f"{self.base_url}/EmissorNacional")
            time.sleep(2)
            
            cookies_adicionados = 0
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                    cookies_adicionados += 1
                except:
                    pass
            
            print(f"   ✅ {cookies_adicionados} cookies adicionados")
            sys.stdout.flush()
            
            self.driver.refresh()
            time.sleep(3)
            
            if self.verificar_login_rapido():
                print(f"✅ Login via cookies! URL: {self.driver.current_url}")
                sys.stdout.flush()
                return True
            else:
                print("   ⚠️ Cookies expirados ou inválidos")
                try:
                    os.remove(self.cookies_path)
                    print("   🗑️ Arquivo de cookies removido")
                except:
                    pass
                return False
                
        except Exception as e:
            print(f"   ⚠️ Erro ao carregar cookies: {e}")
            return False
    
    def verificar_login_rapido(self):
        """Verificação rápida de login baseada na URL atual"""
        try:
            current_url = self.driver.current_url
            return 'Dashboard' in current_url or 'Notas' in current_url
        except:
            return False
    
    def verificar_login(self):
        """Verifica se está logado acessando área restrita"""
        try:
            self.driver.get(f"{self.base_url}/EmissorNacional/Dashboard")
            time.sleep(2)
            return self.verificar_login_rapido()
        except:
            return False
    
    def fazer_login(self):
        """
        Faz login no Emissor Nacional com certificado
        Aguarda a janela de seleção de certificado
        """
        print("\n🔐 Executando login com certificado...")
        sys.stdout.flush()
        
        try:
            # Acessa página inicial
            print("   Acessando página inicial...")
            self.driver.get(f"{self.base_url}/EmissorNacional")
            time.sleep(2)
            
            # Tenta acesso direto à área de certificado
            print("   Acessando página de certificado...")
            self.driver.get(f"{self.base_url}/EmissorNacional/Certificado")
            
            # AGUARDA A JANELA DE CERTIFICADO
            print("\n   ⏳ Aguardando seleção do certificado...")
            print("   🔍 O Chrome abriu uma janela para selecionar o certificado.")
            print("   👆 Selecione o certificado e clique em OK.")
            print("   ⏱️ Aguardando até 30 segundos...")
            sys.stdout.flush()
            
            for i in range(30):
                time.sleep(1)
                if self.verificar_login_rapido():
                    print(f"✅ Login bem-sucedido após {i+1} segundos!")
                    sys.stdout.flush()
                    self.salvar_cookies()
                    return True
                
                if i % 5 == 0:
                    print(f"   ⏳ Aguardando... {30-i} segundos restantes")
                    sys.stdout.flush()
            
            # Se não conseguiu, tenta o link normal
            print("\n   🔄 Tentando clicar no link de certificado...")
            self.driver.get(f"{self.base_url}/EmissorNacional")
            time.sleep(2)
            
            try:
                link_cert = self.driver.find_element(By.PARTIAL_LINK_TEXT, "Certificado")
                link_cert.click()
                print("   ✅ Link clicado")
            except:
                try:
                    link_cert = self.driver.find_element(By.XPATH, "//a[contains(@href, 'Certificado')]")
                    link_cert.click()
                    print("   ✅ Link clicado")
                except:
                    print("   ⚠️ Link não encontrado")
                    self.driver.get(f"{self.base_url}/EmissorNacional/Certificado")
            
            # Aguarda novamente
            print("\n   ⏳ Aguardando seleção do certificado...")
            for i in range(30):
                time.sleep(1)
                if self.verificar_login_rapido():
                    print(f"✅ Login bem-sucedido após {i+1} segundos!")
                    sys.stdout.flush()
                    self.salvar_cookies()
                    return True
            
            print("❌ Tempo esgotado - login não confirmado")
            screenshot_path = os.path.join(self.download_path, 'erro_login_final.png')
            self.driver.save_screenshot(screenshot_path)
            print(f"   Screenshot salvo: {screenshot_path}")
            return False
            
        except Exception as e:
            print(f"❌ Erro no login: {e}")
            traceback.print_exc()
            return False
    
    def garantir_login(self):
        """
        Garante que está logado, tentando reconectar se necessário
        """
        print("\n🔐 Verificando login...")
        sys.stdout.flush()
        
        if self.cookies_path and os.path.exists(self.cookies_path):
            print("   📂 Cookies encontrados, tentando usar...")
            if self.carregar_cookies():
                return True
            else:
                print("   ⚠️ Cookies não funcionaram, fará login normal")
        
        return self.fazer_login()
    
    def buscar_notas(self, tipo, data_inicio, data_fim):
        """Busca notas em um período específico"""
        print(f"\n🔍 Buscando notas {tipo} de {data_inicio} a {data_fim}...")
        sys.stdout.flush()
        
        try:
            data_obj_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
            data_obj_fim = datetime.strptime(data_fim, '%Y-%m-%d')
            
            data_inicio_fmt = data_obj_inicio.strftime('%d/%m/%Y')
            data_fim_fmt = data_obj_fim.strftime('%d/%m/%Y')
            
            print(f"   Datas convertidas: {data_inicio_fmt} a {data_fim_fmt}")
            sys.stdout.flush()
            
            if tipo == 'emitidas':
                url = f"{self.base_url}/EmissorNacional/Notas/Emitidas"
            else:
                url = f"{self.base_url}/EmissorNacional/Notas/Recebidas"
            
            data_inicio_encoded = quote(data_inicio_fmt)
            data_fim_encoded = quote(data_fim_fmt)
            
            url_busca = f"{url}?executar=1&busca=&datainicio={data_inicio_encoded}&datafim={data_fim_encoded}"
            
            print(f"   URL: {url_busca}")
            self.driver.get(url_busca)
            
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            return self.driver.page_source
            
        except Exception as e:
            print(f"❌ Erro ao buscar notas: {e}")
            traceback.print_exc()
            raise
    
    def extrair_links_download(self):
        """Extrai todos os links de download da página atual"""
        print("\n📎 Extraindo links de download...")
        sys.stdout.flush()
        
        links = []
        
        try:
            pdf_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/Notas/Download/DANFSe/')]")
            for link in pdf_links:
                href = link.get_attribute('href')
                numero = href.split('/')[-1]
                links.append({'numero': numero, 'url': href, 'tipo': 'PDF'})
                print(f"   📄 PDF: {numero}")
                sys.stdout.flush()
            
            xml_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/Notas/Download/NFSe/')]")
            for link in xml_links:
                href = link.get_attribute('href')
                numero = href.split('/')[-1]
                links.append({'numero': numero, 'url': href, 'tipo': 'XML'})
                print(f"   📄 XML: {numero}")
                sys.stdout.flush()
            
            print(f"✅ Total de links: {len(links)}")
            sys.stdout.flush()
            
        except Exception as e:
            print(f"❌ Erro ao extrair links: {e}")
            traceback.print_exc()
        
        return links
    
    def baixar_notas(self, links):
        """Baixa todas as notas encontradas"""
        print(f"\n⬇️ Iniciando download de {len(links)} notas...")
        sys.stdout.flush()
        
        antes = len(os.listdir(self.download_path)) if os.path.exists(self.download_path) else 0
        print(f"   Arquivos antes: {antes}")
        sys.stdout.flush()
        
        sucessos = 0
        for i, link in enumerate(links, 1):
            try:
                print(f"   {i}/{len(links)} - {link['tipo']}: {link['numero']}")
                sys.stdout.flush()
                
                self.driver.execute_script("window.open('');")
                self.driver.switch_to.window(self.driver.window_handles[1])
                self.driver.get(link['url'])
                time.sleep(2)
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
                
                sucessos += 1
                time.sleep(0.5)
                
            except Exception as e:
                print(f"   ❌ Erro: {link['numero']} - {e}")
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
        
        time.sleep(2)
        depois = len(os.listdir(self.download_path)) if os.path.exists(self.download_path) else 0
        print(f"   Arquivos depois: {depois}")
        print(f"   Novos arquivos: {depois - antes}")
        sys.stdout.flush()
        
        return sucessos
    
    def listar_arquivos_baixados(self):
        """Lista os arquivos baixados"""
        try:
            arquivos = os.listdir(self.download_path)
            print(f"\n📁 Arquivos na pasta ({len(arquivos)}):")
            sys.stdout.flush()
            
            for arquivo in sorted(arquivos)[-15:]:
                caminho = os.path.join(self.download_path, arquivo)
                if os.path.isfile(caminho):
                    tamanho = os.path.getsize(caminho)
                    data_mod = datetime.fromtimestamp(os.path.getmtime(caminho)).strftime('%d/%m/%Y %H:%M')
                    print(f"   📄 {arquivo} - {tamanho:,} bytes - {data_mod}".replace(',', '.'))
                    sys.stdout.flush()
            return arquivos
        except Exception as e:
            print(f"❌ Erro ao listar arquivos: {e}")
            return []
    
    def fechar(self):
        """Fecha o driver e limpa arquivos temporários"""
        if self.driver:
            try:
                self.driver.quit()
                print("🔒 Driver fechado.")
                sys.stdout.flush()
            except:
                pass
        
        if hasattr(self, 'pem_path') and self.pem_path and os.path.exists(self.pem_path):
            try:
                os.remove(self.pem_path)
                print("🧹 Arquivo PEM temporário removido.")
                sys.stdout.flush()
            except:
                pass


# ============================================
# FUNÇÃO PRINCIPAL
# ============================================

def baixar_com_selenium(empresa, tipo, data_inicio, data_fim, pasta_destino=None):
    """
    Função principal para baixar notas usando Selenium
    """
    print("\n" + "="*80)
    print("🚀 DOWNLOAD AUTOMÁTICO DE NFSe")
    print("="*80)
    print(f"🏢 Empresa: {empresa.nome_fantasia}")
    print(f"📋 Tipo: {tipo}")
    print(f"📅 Período: {data_inicio} a {data_fim}")
    print(f"🔐 Certificado: {empresa.certificado_arquivo.path if empresa.certificado_arquivo else 'Nenhum'}")
    sys.stdout.flush()
    
    if not pasta_destino:
        pasta_destino = os.path.join(
            'media', 'nfse', tipo,
            data_inicio[:4], data_inicio[5:7]
        )
    
    pasta_destino = os.path.abspath(pasta_destino)
    print(f"📁 Pasta destino: {pasta_destino}")
    sys.stdout.flush()
    
    try:
        os.makedirs(pasta_destino, exist_ok=True)
        teste_path = os.path.join(pasta_destino, 'teste.txt')
        with open(teste_path, 'w') as f:
            f.write('teste')
        os.remove(teste_path)
        print("✅ Pasta com permissão de escrita")
        sys.stdout.flush()
    except Exception as e:
        print(f"❌ Erro na pasta: {e}")
        raise
    
    cliente = None
    try:
        cliente = EmissorNacionalSelenium(empresa, pasta_destino)
        
        if not cliente.iniciar_driver():
            raise Exception("Não foi possível iniciar o ChromeDriver")
        
        if not cliente.garantir_login():
            raise Exception("Falha no login. Verifique certificado e senha.")
        
        cliente.buscar_notas(tipo, data_inicio, data_fim)
        links = cliente.extrair_links_download()
        
        if not links:
            print("\nℹ️ Nenhuma nota encontrada no período")
            return 0, 0, pasta_destino
        
        print(f"\n📊 Total de notas: {len(links)}")
        print(f"   PDFs: {len([l for l in links if l['tipo'] == 'PDF'])}")
        print(f"   XMLs: {len([l for l in links if l['tipo'] == 'XML'])}")
        sys.stdout.flush()
        
        sucessos = cliente.baixar_notas(links)
        cliente.listar_arquivos_baixados()
        
        print("\n" + "="*80)
        print(f"✅ DOWNLOAD CONCLUÍDO!")
        print(f"📊 Total: {len(links)}")
        print(f"✅ Baixadas: {sucessos}")
        print(f"❌ Falhas: {len(links) - sucessos}")
        print(f"📁 Pasta: {pasta_destino}")
        print("="*80)
        sys.stdout.flush()
        
        return len(links), sucessos, pasta_destino
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        traceback.print_exc()
        raise
    finally:
        if cliente:
            cliente.fechar()


if __name__ == "__main__":
    print("="*80)
    print("🚀 TESTE DIRETO DO SELENIUM SERVICE")
    print("="*80)
    print("Este arquivo deve ser usado através do Django.")
    print("Execute: python manage.py runserver")
    print("="*80)