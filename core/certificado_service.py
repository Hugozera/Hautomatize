"""
Serviço de certificados digitais para Windows
HDowloader - Download Automático de NFSe
"""

import requests
import subprocess
import tempfile
import os
import hashlib
import random
import string
import time
import ssl
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# ============================================
# CONFIGURAÇÃO DE DIRETÓRIOS
# ============================================

# Obtém o diretório raiz do projeto (pai do diretório core)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Caminhos do OpenSSL no projeto
OPENSSL_BIN_PATH = os.path.join(PROJECT_ROOT, 'OpenSSL-Win64', 'bin')
OPENSSL_LIB_PATH = os.path.join(PROJECT_ROOT, 'OpenSSL-Win64', 'lib')
OPENSSL_MODULES_PATH = os.path.join(OPENSSL_LIB_PATH, 'ossl-modules')
OPENSSL_EXE = os.path.join(OPENSSL_BIN_PATH, 'openssl.exe')

def configurar_ambiente_openssl():
    r"""
    Configura as variáveis de ambiente para usar OpenSSL com suporte a certificados legados.
    
    Isso permite que certificados antigos (com algoritmos SHA1, MD5, etc) sejam processados
    pelo OpenSSL 3.x através das DLLs legacy em OpenSSL-Win64\lib\ossl-modules\
    """
    try:
        # Adiciona o diretório bin ao PATH
        if os.path.exists(OPENSSL_BIN_PATH):
            path_atual = os.environ.get('PATH', '')
            if OPENSSL_BIN_PATH not in path_atual:
                os.environ['PATH'] = f"{OPENSSL_BIN_PATH};{path_atual}"
                print(f"✅ OpenSSL bin adicionado ao PATH: {OPENSSL_BIN_PATH}")
        
        # Configura o diretório de módulos para DLL legacy
        if os.path.exists(OPENSSL_MODULES_PATH):
            os.environ['OPENSSL_MODULES'] = OPENSSL_MODULES_PATH
            print(f"✅ OPENSSL_MODULES configurado para suporte a certificados legados: {OPENSSL_MODULES_PATH}")
        
        # Define a biblioteca do OpenSSL explicitamente
        if os.path.exists(OPENSSL_LIB_PATH):
            os.environ['LD_LIBRARY_PATH'] = OPENSSL_LIB_PATH
            print(f"✅ LD_LIBRARY_PATH configurado: {OPENSSL_LIB_PATH}")
            
    except Exception as e:
        print(f"⚠️ Erro ao configurar ambiente OpenSSL: {e}")

# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def gerar_senha_temporaria(tamanho=8):
    """Gera uma senha aleatória para exportação temporária"""
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for _ in range(tamanho))

def limpar_arquivo_temporario(caminho):
    """Remove arquivo temporário com segurança"""
    try:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)
            print(f"Arquivo temporário removido: {caminho}")
    except Exception as e:
        print(f"Erro ao remover arquivo temporário: {e}")

def verificar_openssl_instalado():
    """Verifica se o OpenSSL está instalado no sistema"""
    try:
        # Configura variáveis de ambiente primeiro
        configurar_ambiente_openssl()
        
        # Prioridade: tenta o OpenSSL do projeto primeiro
        openssl_paths = [
            OPENSSL_EXE,  # OpenSSL-Win64\bin\openssl.exe (LOCAL DO PROJETO)
            os.path.join(PROJECT_ROOT, 'lib', 'OpenSSL-Win64', 'bin', 'openssl.exe'),
            os.path.join(PROJECT_ROOT, 'lib', 'openssl.exe'),
            os.path.join(PROJECT_ROOT, 'tools', 'openssl.exe'),
            'openssl',
            'C:\\Program Files\\OpenSSL-Win64\\bin\\openssl.exe',
            'C:\\Program Files (x86)\\OpenSSL-Win32\\bin\\openssl.exe',
            'C:\\OpenSSL-Win64\\bin\\openssl.exe',
            'C:\\OpenSSL-Win32\\bin\\openssl.exe',
        ]
        
        for path in openssl_paths:
            try:
                result = subprocess.run([path, 'version'], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=5)
                if result.returncode == 0:
                    print(f"✅ OpenSSL encontrado: {path}")
                    print(f"Versão: {result.stdout.strip()}")
                    return path
            except:
                continue
        
        print("⚠️ OpenSSL não encontrado")
        return None
        
    except Exception as e:
        print(f"Erro ao verificar OpenSSL: {e}")
        return None

# ============================================
# EXPORTAÇÃO VIA POWERSHELL (CORRIGIDA)
# ============================================

def exportar_certificado_powershell(thumbprint, senha):
    """
    Exporta certificado da loja do Windows usando PowerShell
    
    Args:
        thumbprint (str): Thumbprint do certificado
        senha (str): Senha para proteger o PFX
    
    Returns:
        str: Caminho do arquivo PFX temporário
    """
    # Se a senha estiver vazia, usa 123456 como fallback
    if not senha:
        print("⚠️ Senha vazia, usando 123456 como fallback")
        senha = "123456"
    
    # Criar arquivo temporário
    fd, temp_path = tempfile.mkstemp(suffix='.pfx')
    os.close(fd)
    
    print(f"\n{'='*50}")
    print(f"EXPORTANDO CERTIFICADO VIA POWERSHELL")
    print(f"Thumbprint: {thumbprint}")
    print(f"Arquivo temporário: {temp_path}")
    
    # Escapa a senha para o PowerShell
    senha_escaped = senha.replace("'", "''")
    
    # Script PowerShell para exportar o certificado
    ps_script = f'''
    $ErrorActionPreference = "Stop"
    
    try {{
        $cert = Get-ChildItem -Path Cert:\\CurrentUser\\My | Where-Object {{ $_.Thumbprint -eq '{thumbprint}' }}
        
        if (-not $cert) {{
            Write-Error "Certificado não encontrado"
            exit 1
        }}
        
        Write-Host "Certificado encontrado: $($cert.Subject)"
        
        $securePassword = ConvertTo-SecureString -String '{senha_escaped}' -Force -AsPlainText
        Export-PfxCertificate -Cert $cert -FilePath '{temp_path}' -Password $securePassword
        
        if (Test-Path '{temp_path}') {{
            Write-Host "Certificado exportado com sucesso"
            exit 0
        }} else {{
            Write-Error "Arquivo não foi criado"
            exit 1
        }}
    }}
    catch {{
        Write-Error $_.Exception.Message
        exit 1
    }}
    '''
    
    try:
        # Executar PowerShell
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_script],
            capture_output=True,
            text=True,
            shell=False,
            timeout=30
        )
        
        print(f"Saída PowerShell: {result.stdout}")
        
        if result.stderr:
            print(f"Erros PowerShell: {result.stderr}")
        
        if result.returncode == 0 and os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            print("✅ Certificado exportado com sucesso via PowerShell")
            return temp_path
        else:
            print(f"❌ PowerShell retornou código {result.returncode}")
            print(f"STDERR: {result.stderr}")
            limpar_arquivo_temporario(temp_path)
            raise Exception("Falha na exportação via PowerShell")
            
    except subprocess.TimeoutExpired:
        print("❌ Timeout na execução do PowerShell")
        limpar_arquivo_temporario(temp_path)
        raise
    except Exception as e:
        print(f"❌ Erro no PowerShell: {e}")
        limpar_arquivo_temporario(temp_path)
        raise


def exportar_certificado_pfx(thumbprint):
    """
    Wrapper que exporta um certificado PFX gerando uma senha temporária.
    Retorna tupla (pfx_path, senha)
    """
    senha = gerar_senha_temporaria(12)
    pfx_path = exportar_certificado_powershell(thumbprint, senha)
    return pfx_path, senha

# ============================================
# CONVERSÃO PFX PARA PEM (COM OPENSSL)
# ============================================

openssl_path = None  # Variável global para cache do caminho do OpenSSL

def converter_pfx_para_pem_python(pfx_path, senha, pem_path):
    """
    Converte arquivo PFX para formato PEM usando Python puro (cryptography)
    
    Este método nativo do Python é mais robusto para certificados legados com
    SHA1, MD5, e algoritmos deprecated que OpenSSL 3.x bloqueia por padrão.
    
    Returns:
        str: Caminho do arquivo PEM ou None se falhar
    """
    try:
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        
        print(f"Convertendo PFX para PEM usando Python (cryptography)...")
        
        # Lê o arquivo PFX
        with open(pfx_path, 'rb') as f:
            pfx_data = f.read()
        
        print(f"Arquivo PFX lido: {len(pfx_data)} bytes")
        
        # Carrega o PKCS12
        try:
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                pfx_data,
                senha.encode() if isinstance(senha, str) else senha,
                backend=default_backend()
            )
        except TypeError:
            # Versões antigas podem ter assinatura diferente
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                pfx_data,
                senha.encode() if isinstance(senha, str) else senha
            )
        
        print(f"PKCS12 carregado com sucesso")
        print(f"  Certificado: {certificate is not None}")
        print(f"  Chave privada: {private_key is not None}")
        print(f"  Certificados adicionais: {len(additional_certs) if additional_certs else 0}")
        
        # Escreve o PEM
        pem_data = b''
        
        # Adiciona certificado
        if certificate:
            pem_data += certificate.public_bytes(serialization.Encoding.PEM)
        
        # Adiciona chave privada
        if private_key:
            pem_data += private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
        
        # Adiciona certificados adicionais
        if additional_certs:
            for cert in additional_certs:
                pem_data += cert.public_bytes(serialization.Encoding.PEM)
        
        # Escreve o arquivo PEM
        with open(pem_path, 'wb') as f:
            f.write(pem_data)
        
        print(f"✅ PEM escrito com sucesso: {len(pem_data)} bytes")
        print(f"Arquivo: {pem_path}")
        
        return pem_path
        
    except Exception as e:
        print(f"Erro na conversão Python: {e}")
        import traceback
        traceback.print_exc()
        return None


def converter_pfx_para_pem(pfx_path, senha, pem_path):
    """
    Converte arquivo PFX para formato PEM usando OpenSSL com suporte a certificados legados.
    
    Tenta primeiro com Python puro (mais robusto), depois com OpenSSL.
    
    Returns:
        str: Caminho do arquivo PEM ou None se falhar
    """
    global openssl_path
    
    # ESTRATÉGIA 0: Tenta com Python puro primeiro (mais robusto para legados)
    print(f"\nTentativa 0: usando Python puro (cryptography)...")
    resultado = converter_pfx_para_pem_python(pfx_path, senha, pem_path)
    if resultado:
        return resultado
    
    if openssl_path is None:
        openssl_path = verificar_openssl_instalado()
    
    if not openssl_path:
        print("⚠️ OpenSSL não disponível para conversão")
        return None
    
    try:
        print(f"Convertendo PFX para PEM com OpenSSL...")
        print(f"Usando OpenSSL: {openssl_path}")
        print(f"Arquivo PFX: {pfx_path}")
        print(f"Arquivo PEM (saída): {pem_path}")
        
        # Prepara o ambiente com as variáveis para suporte legado
        env = os.environ.copy()
        
        # Converte PFX para PEM (estratégia 1: com -provider-path legacy + -nomacver)
        cmd = [
            openssl_path, 'pkcs12',
            '-in', pfx_path,
            '-out', pem_path,
            '-nodes',
            '-passin', 'stdin',
            '-nomacver',
            '-provider-path', OPENSSL_MODULES_PATH,
            '-provider', 'legacy',
            '-legacy'
        ]
        
        print(f"\nTentativa 1: usando -nomacver -provider-path -provider legacy...")
        result = subprocess.run(
            cmd, 
            input=senha, 
            capture_output=True, 
            text=True, 
            timeout=30,
            env=env,
            shell=False
        )
        
        if result.returncode == 0 and os.path.exists(pem_path) and os.path.getsize(pem_path) > 0:
            print("✅ Conversão para PEM bem-sucedida (estratégia 1)")
            print(f"Arquivo criado: {pem_path}")
            return pem_path
        
        # Se falhar, tenta estratégia 2: com arquivo temporário para senha
        if result.returncode != 0:
            print(f"⚠️ Estratégia 1 falhou: {result.stderr[:200]}")
            print(f"\nTentativa 2: usando arquivo temporário para senha com -nomacver...")
            
            # Cria arquivo temporário com a senha
            fd_senha, temp_senha = tempfile.mkstemp(suffix='.txt')
            try:
                with os.fdopen(fd_senha, 'w') as f:
                    f.write(senha)
                
                # Tenta com arquivo de senha
                cmd2 = [
                    openssl_path, 'pkcs12',
                    '-in', pfx_path,
                    '-out', pem_path,
                    '-nodes',
                    '-passin', f'file:{temp_senha}',
                    '-nomacver',
                    '-provider-path', OPENSSL_MODULES_PATH,
                    '-provider', 'legacy',
                    '-legacy'
                ]
                
                result = subprocess.run(
                    cmd2,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env,
                    shell=False
                )
                
                if result.returncode == 0 and os.path.exists(pem_path) and os.path.getsize(pem_path) > 0:
                    print("✅ Conversão para PEM bem-sucedida (estratégia 2)")
                    print(f"Arquivo criado: {pem_path}")
                    return pem_path
                else:
                    print(f"⚠️ Estratégia 2 também falhou: {result.stderr[:200]}")
            finally:
                if os.path.exists(temp_senha):
                    os.remove(temp_senha)
        
        # Se ambas falharem, tenta estratégia 3: com -provider default + stdin + nomacver
        if result.returncode != 0:
            print(f"\nTentativa 3: usando -nomacver -provider-path + default...")
            
            cmd3 = [
                openssl_path, 'pkcs12',
                '-in', pfx_path,
                '-out', pem_path,
                '-nodes',
                '-passin', 'stdin',
                '-nomacver',
                '-provider-path', OPENSSL_MODULES_PATH,
                '-provider', 'default'
            ]
            
            result = subprocess.run(
                cmd3,
                input=senha,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
                shell=False
            )
            
            if result.returncode == 0 and os.path.exists(pem_path) and os.path.getsize(pem_path) > 0:
                print("✅ Conversão para PEM bem-sucedida (estratégia 3)")
                print(f"Arquivo criado: {pem_path}")
                return pem_path
        
        # Estratégia 4: tenta apenas com stdin + nomacver + provider-path, sem legacy
        if result.returncode != 0:
            print(f"\nTentativa 4: usando -nomacver -provider-path stdin (sem legacy)...")
            
            cmd4 = [
                openssl_path, 'pkcs12',
                '-in', pfx_path,
                '-out', pem_path,
                '-nodes',
                '-passin', 'stdin',
                '-nomacver',
                '-provider-path', OPENSSL_MODULES_PATH
            ]
            
            result = subprocess.run(
                cmd4,
                input=senha,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
                shell=False
            )
            
            if result.returncode == 0 and os.path.exists(pem_path) and os.path.getsize(pem_path) > 0:
                print("✅ Conversão para PEM bem-sucedida (estratégia 4)")
                print(f"Arquivo criado: {pem_path}")
                return pem_path
        
        # Estratégia 5: tenta apenas com stdin + nomacver, sem providers (fallback)
        if result.returncode != 0:
            print(f"\nTentativa 5: usando stdin + nomacver (sem providers)...")
            
            cmd5 = [
                openssl_path, 'pkcs12',
                '-in', pfx_path,
                '-out', pem_path,
                '-nodes',
                '-passin', 'stdin',
                '-nomacver'
            ]
            
            result = subprocess.run(
                cmd5,
                input=senha,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
                shell=False
            )
            
            if result.returncode == 0 and os.path.exists(pem_path) and os.path.getsize(pem_path) > 0:
                print("✅ Conversão para PEM bem-sucedida (estratégia 5)")
                print(f"Arquivo criado: {pem_path}")
                return pem_path
        
        # Se nada funcionou, imprime debug detalhado
        print(f"\n❌ Todas as estratégias falharam!")
        print(f"Código de retorno: {result.returncode}")
        print(f"\nSTDERR completo (últimos 500 chars):")
        print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
        print(f"\nSTDOUT completo (últimos 500 chars):")
        print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
        print(f"\nDicas de debug:")
        print(f"- Verificar se o arquivo PFX existe: {os.path.exists(pfx_path)}")
        print(f"- Verificar se o OpenSSL funciona: {openssl_path}")
        print(f"- OPENSSL_MODULES_PATH: {OPENSSL_MODULES_PATH}")
        print(f"- Módulos legacy.dll existe: {os.path.exists(os.path.join(OPENSSL_MODULES_PATH, 'legacy.dll'))}")
        print(f"- Variável OPENSSL_MODULES: {env.get('OPENSSL_MODULES', 'NÃO DEFINIDA')}")
        print(f"- Variável PATH contem bin dir: {OPENSSL_BIN_PATH in env.get('PATH', '')}")
        
        return None
            
    except subprocess.TimeoutExpired:
        print("❌ Timeout na conversão (30s excedido)")
        return None
    except Exception as e:
        print(f"❌ Erro na conversão OpenSSL: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================
# CRIAÇÃO DE SESSÃO COM PEM (MÉTODO PRINCIPAL)
# ============================================

def criar_sessao_certificado(thumbprint, senha):
    """
    Cria uma sessão usando o certificado convertido para PEM
    """
    pfx_path = None
    pem_path = None
    
    try:
        print(f"\n{'='*50}")
        print("CRIANDO SESSÃO COM CERTIFICADO (MÉTODO PEM)")
        print(f"Thumbprint: {thumbprint}")
        print(f"Senha: {'*' * len(senha)}")
        
        # Exporta o certificado via PowerShell
        pfx_path = exportar_certificado_powershell(thumbprint, senha)
        
        # Verifica se OpenSSL está disponível
        if not verificar_openssl_instalado():
            raise Exception("OpenSSL não está instalado. Necessário para conversão para PEM.")
        
        # Cria arquivo PEM temporário
        fd, pem_path = tempfile.mkstemp(suffix='.pem')
        os.close(fd)
        
        # Converte para PEM
        pem_result = converter_pfx_para_pem(pfx_path, senha, pem_path)
        
        if not pem_result:
            raise Exception("Falha na conversão para PEM")
        
        print("✅ PEM gerado com sucesso")
        
        # Cria sessão com o PEM
        session = requests.Session()
        session.cert = pem_result
        session.verify = False
        
        # Headers para simular navegador
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        session.timeout = 30
        
        # Armazena caminhos para limpeza
        session._pfx_path = pfx_path
        session._pem_path = pem_path
        original_close = session.close
        
        def close_with_cleanup():
            if hasattr(session, '_pfx_path'):
                limpar_arquivo_temporario(session._pfx_path)
            if hasattr(session, '_pem_path'):
                limpar_arquivo_temporario(session._pem_path)
            original_close()
        
        session.close = close_with_cleanup
        
        print("✅ Sessão criada com sucesso")
        return session
        
    except Exception as e:
        if pfx_path:
            limpar_arquivo_temporario(pfx_path)
        if pem_path:
            limpar_arquivo_temporario(pem_path)
        print(f"❌ Erro ao criar sessão: {e}")
        raise

# ============================================
# FUNÇÃO PARA USAR ARQUIVO SALVO
# ============================================

def criar_sessao_com_arquivo(cert_path, senha):
    """
    Cria sessão usando arquivo .pfx salvo no sistema
    """
    print(f"\n{'='*50}")
    print("CRIANDO SESSÃO COM ARQUIVO PFX")
    print(f"Arquivo: {cert_path}")
    
    pem_path = None
    
    try:
        # Verifica se OpenSSL está disponível
        if not verificar_openssl_instalado():
            raise Exception("OpenSSL não está instalado. Necessário para conversão para PEM.")
        
        # Cria arquivo PEM temporário
        fd, pem_path = tempfile.mkstemp(suffix='.pem')
        os.close(fd)
        
        # Converte para PEM
        pem_result = converter_pfx_para_pem(cert_path, senha, pem_path)
        
        if not pem_result:
            raise Exception("Falha na conversão para PEM")
        
        print("✅ PEM gerado com sucesso")
        
        # Cria sessão com o PEM
        session = requests.Session()
        session.cert = pem_result
        session.verify = False
        
        # Headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        
        session.timeout = 30
        
        # Armazena caminho para limpeza
        session._pem_path = pem_path
        original_close = session.close
        
        def close_with_cleanup():
            if hasattr(session, '_pem_path'):
                limpar_arquivo_temporario(session._pem_path)
            original_close()
        
        session.close = close_with_cleanup
        
        print("✅ Sessão com arquivo criada com sucesso")
        return session
        
    except Exception as e:
        if pem_path:
            limpar_arquivo_temporario(pem_path)
        print(f"❌ Erro ao criar sessão com arquivo: {e}")
        raise

# ============================================
# LISTAR CERTIFICADOS (fallback seguro)
# ============================================

def listar_certificados_windows():
    """Retorna lista de certificados disponíveis no repositório do usuário.
    Implementação resiliente: tenta usar PowerShell/Win32, mas em ambiente sem Windows
    retorna lista vazia em vez de lançar exceção.

    Returns: list of dict { 'thumbprint': str, 'subject': str }
    """
    try:
        # Tenta usar PowerShell para listar em JSON (Windows)
        ps = r"Get-ChildItem Cert:\CurrentUser\My | Select-Object Thumbprint, Subject | ConvertTo-Json"
        result = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            import json as _json
            try:
                data = _json.loads(result.stdout)
            except Exception:
                # Se vier um único objeto, normaliza para lista
                try:
                    obj = result.stdout.strip()
                    # tentar extrair Thumbprint/Subject via regex
                    matches = re.findall(r"Thumbprint\s*:\s*([A-F0-9]+)\s*Subject\s*:\s*(.+)", result.stdout, flags=re.I)
                    certs = []
                    for m in matches:
                        certs.append({'thumbprint': m[0].strip(), 'subject': m[1].strip()})
                    return certs
                except Exception:
                    return []

            # Normalize to list
            if isinstance(data, dict):
                data = [data]
            certs = []
            for item in data:
                thumb = item.get('Thumbprint') or item.get('thumbprint')
                subj = item.get('Subject') or item.get('subject')
                if thumb:
                    certs.append({'thumbprint': thumb.strip(), 'subject': subj or ''})
            return certs
    except Exception:
        pass

    # Fallback genérico: retorna lista vazia
    return []


# ============================================
# TESTE DE CERTIFICADO
# ============================================

def testar_certificado(thumbprint, senha):
    """
    Testa se o certificado funciona fazendo uma requisição simples
    """
    session = None
    try:
        print(f"\n{'='*50}")
        print("TESTANDO CERTIFICADO")
        print(f"Thumbprint: {thumbprint}")
        
        session = criar_sessao_certificado(thumbprint, senha)
        
        # Tenta acessar o site
        print("Acessando https://www.nfse.gov.br/EmissorNacional...")
        resp = session.get(
            'https://www.nfse.gov.br/EmissorNacional', 
            timeout=30, 
            verify=False,
            allow_redirects=True
        )
        
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code == 200:
            print("✅ Certificado funciona!")
            return True
        else:
            print(f"❌ Certificado retornou status {resp.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False
    finally:
        if session:
            session.close()

# ============================================
# TESTE DE CONVERSÃO PFX PARA PEM
# ============================================

def testar_conversao_pfx(pfx_path, senha):
    """
    Testa a conversão de PFX para PEM diretamente
    """
    print(f"\n{'='*60}")
    print("TESTE DE CONVERSÃO PFX PARA PEM")
    print(f"{'='*60}")
    print(f"Arquivo PFX: {pfx_path}")
    
    if not os.path.exists(pfx_path):
        print(f"❌ Arquivo não encontrado: {pfx_path}")
        return False
    
    # Configura ambiente
    configurar_ambiente_openssl()
    
    # Cria arquivo PEM temporário
    fd, pem_path = tempfile.mkstemp(suffix='.pem')
    os.close(fd)
    
    try:
        # Converte
        resultado = converter_pfx_para_pem(pfx_path, senha, pem_path)
        
        if resultado:
            print(f"\n✅ Conversão bem-sucedida!")
            print(f"Arquivo PEM: {pem_path}")
            
            # Mostra tamanho e primeiras linhas
            with open(pem_path, 'r') as f:
                conteudo = f.read()
                print(f"Tamanho: {len(conteudo)} bytes")
                print(f"Primeiras linhas:")
                print("\n".join(conteudo.split("\n")[:5]))
            
            return True
        else:
            print(f"\n❌ Conversão falhou")
            return False
            
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if os.path.exists(pem_path):
            os.remove(pem_path)

# ============================================
# EXEMPLO DE USO
# ============================================

def converter_pfx_para_cert_e_key(pfx_path, senha):
    """
    Converte PFX para dois arquivos separados: certificado e chave privada.
    Retorna tupla (cert_pem_path, key_pem_path)
    """
    # Cria arquivos temporários
    fd_cert, cert_pem_path = tempfile.mkstemp(suffix='.pem')
    os.close(fd_cert)
    fd_key, key_pem_path = tempfile.mkstemp(suffix='.pem')
    os.close(fd_key)
    
    try:
        # Python puro primeiro
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        
        with open(pfx_path, 'rb') as f:
            pfx_data = f.read()
        
        try:
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                pfx_data,
                senha.encode() if isinstance(senha, str) else senha,
                backend=default_backend()
            )
        except TypeError:
            private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
                pfx_data,
                senha.encode() if isinstance(senha, str) else senha
            )
        
        # Escreve certificado
        cert_data = b''
        if certificate:
            cert_data += certificate.public_bytes(serialization.Encoding.PEM)
        if additional_certs:
            for cert in additional_certs:
                cert_data += cert.public_bytes(serialization.Encoding.PEM)
        
        with open(cert_pem_path, 'wb') as f:
            f.write(cert_data)
        
        # Escreve chave privada
        if private_key:
            key_data = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            with open(key_pem_path, 'wb') as f:
                f.write(key_data)
        
        return cert_pem_path, key_pem_path
        
    except Exception as e:
        print(f"Erro na conversão separada: {e}")
        if os.path.exists(cert_pem_path):
            os.remove(cert_pem_path)
        if os.path.exists(key_pem_path):
            os.remove(key_pem_path)
        return None, None

if __name__ == "__main__":
    print("="*60)
    print("TESTE DE CERTIFICADO - HDOWLOADER")
    print("="*60)
    
    thumbprint = input("Digite o thumbprint do certificado: ").strip()
    senha = input("Digite a senha do certificado: ").strip()
    
    if not thumbprint or not senha:
        print("❌ Thumbprint e senha são obrigatórios!")
        exit(1)
    
    try:
        # Testa o certificado
        if testar_certificado(thumbprint, senha):
            print("\n✅ Certificado funcionando!")
        else:
            print("\n❌ Certificado não funciona")
            
    except Exception as e:
        print(f"\n❌ Erro: {e}")