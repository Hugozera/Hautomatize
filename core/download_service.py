"""
Serviço de download de NFSe
HDowloader - Download Automático de NFSe
"""
import sys
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

# Força saída imediata no console
try:
    sys.stdout.reconfigure(line_buffering=True)
except:
    # Se não funcionar, usa o método alternativo
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
print("🔵 DOWNLOAD_SERVICE.PY CARREGADO")
print("="*70)
sys.stdout.flush()

# Importa as funções necessárias
try:
    print("🔵 Importando selenium_service...")
    sys.stdout.flush()
    from .selenium_service import baixar_com_selenium
    print("✅ selenium_service importado com sucesso!")
    sys.stdout.flush()
    
    print("🔵 Importando navegador_service...")
    sys.stdout.flush()
    from .navegador_service import criar_sessao_navegador
    print("✅ navegador_service importado com sucesso!")
    sys.stdout.flush()
    
    print("🔵 Importando certificado_service...")
    sys.stdout.flush()
    from .certificado_service import criar_sessao_certificado, criar_sessao_com_arquivo
    print("✅ certificado_service importado com sucesso!")
    sys.stdout.flush()
    
except ImportError as e:
    print(f"❌ Erro ao importar serviços: {e}")
    print("Verifique se todos os arquivos existem na pasta core/")
    print("Arquivos necessários:")
    print("  - selenium_service.py")
    print("  - navegador_service.py")
    print("  - certificado_service.py")
    sys.stdout.flush()
    raise

def baixar_nota(session, url, pasta_destino, numero_nota):
    """
    Baixa uma única nota fiscal
    
    Args:
        session: Sessão autenticada
        url: URL da nota para download
        pasta_destino: Pasta onde salvar o arquivo
        numero_nota: Número da nota para nome do arquivo
    
    Returns:
        bool: True se baixou com sucesso, False caso contrário
    """
    try:
        print(f"⬇️ Baixando nota {numero_nota}...")
        sys.stdout.flush()
        
        resp = session.get(url, timeout=30)
        
        if resp.status_code == 200:
            # Determina o tipo de arquivo pelo Content-Type
            content_type = resp.headers.get('Content-Type', '').lower()
            
            if 'pdf' in content_type:
                extensao = '.pdf'
            elif 'xml' in content_type:
                extensao = '.xml'
            elif 'application/octet-stream' in content_type:
                # Tenta identificar pela URL
                if '.pdf' in url.lower():
                    extensao = '.pdf'
                elif '.xml' in url.lower():
                    extensao = '.xml'
                else:
                    extensao = '.pdf'  # padrão
            else:
                extensao = '.pdf'  # padrão
            
            caminho = os.path.join(pasta_destino, f"{numero_nota}{extensao}")
            
            # Salva o arquivo
            with open(caminho, 'wb') as f:
                f.write(resp.content)
            
            print(f"✅ Nota {numero_nota} baixada com sucesso ({os.path.getsize(caminho)} bytes)")
            sys.stdout.flush()
            return True
        else:
            print(f"❌ Erro {resp.status_code} ao baixar nota {numero_nota}")
            sys.stdout.flush()
            return False
            
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout ao baixar nota {numero_nota}")
        sys.stdout.flush()
        return False
    except Exception as e:
        print(f"❌ Erro ao baixar nota {numero_nota}: {e}")
        sys.stdout.flush()
        return False

def download_em_massa(empresa, tipo, data_inicio, data_fim, pasta_destino, url_base, senha):
    """
    Função principal usando Selenium com certificado da empresa
    
    Args:
        empresa: Objeto Empresa do Django
        tipo: 'emitidas' ou 'recebidas'
        data_inicio: YYYY-MM-DD
        data_fim: YYYY-MM-DD
        pasta_destino: Pasta onde salvar
        url_base: URL base (não usado no Selenium)
        senha: Senha do certificado
    
    Returns:
        tuple: (total_notas, baixadas)
    """
    print("\n" + "="*80)
    print("🚀 DOWNLOAD SERVICE CHAMANDO SELENIUM")
    print("="*80)
    print(f"📌 TIMESTAMP: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🏢 Empresa: {empresa.nome_fantasia} (ID: {empresa.pk})")
    print(f"📋 Tipo: {tipo}")
    print(f"📅 Período: {data_inicio} a {data_fim}")
    print(f"📁 Pasta: {pasta_destino}")
    print(f"🔐 Certificado: {empresa.certificado_arquivo.path if empresa.certificado_arquivo else 'Nenhum'}")
    print(f"🔐 Senha: {'*' * len(senha) if senha else 'Vazia'}")
    sys.stdout.flush()
    
    try:
        # Verifica se o certificado existe
        if not empresa.certificado_arquivo:
            error_msg = "Empresa não possui arquivo de certificado!"
            print(f"❌ {error_msg}")
            sys.stdout.flush()
            raise Exception(error_msg)
        
        cert_path = empresa.certificado_arquivo.path
        print(f"📌 Caminho do certificado: {cert_path}")
        sys.stdout.flush()
        
        if not os.path.exists(cert_path):
            error_msg = f"Arquivo de certificado não encontrado: {cert_path}"
            print(f"❌ {error_msg}")
            sys.stdout.flush()
            raise Exception(error_msg)
        
        cert_size = os.path.getsize(cert_path)
        print(f"✅ Certificado encontrado! Tamanho: {cert_size} bytes")
        sys.stdout.flush()
        
        # Cria pasta de destino
        os.makedirs(pasta_destino, exist_ok=True)
        print(f"✅ Pasta criada/verificada: {pasta_destino}")
        sys.stdout.flush()
        
        # Testa permissão de escrita
        teste_path = os.path.join(pasta_destino, 'teste_escrita.txt')
        try:
            with open(teste_path, 'w') as f:
                f.write('teste')
            os.remove(teste_path)
            print(f"✅ Pasta com permissão de escrita")
        except Exception as e:
            print(f"⚠️ Aviso: Pasta sem permissão de escrita? {e}")
        sys.stdout.flush()
        
        # Chama o Selenium
        print("\n" + "="*50)
        print("🤖 CHAMANDO SELENIUM AGORA...")
        print("="*50)
        sys.stdout.flush()
        
        resultado = baixar_com_selenium(
            empresa=empresa,
            tipo=tipo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            pasta_destino=pasta_destino,
            headless=False  # False para debug, True para produção
        )
        
        print("\n" + "="*50)
        print(f"✅ SELENIUM RETORNOU!")
        print(f"📊 Resultado: {resultado}")
        print("="*50)
        sys.stdout.flush()
        
        # Processa o resultado
        if isinstance(resultado, tuple) and len(resultado) >= 2:
            total, baixadas = resultado[0], resultado[1]
        else:
            total, baixadas = 0, 0
        
        print(f"📊 Total de notas: {total}")
        print(f"✅ Baixadas: {baixadas}")
        print(f"❌ Falhas: {total - baixadas}")
        sys.stdout.flush()
        
        return total, baixadas
        
    except Exception as e:
        print(f"\n❌ ERRO no download_service: {e}")
        sys.stdout.flush()
        print("\n📋 Traceback completo:")
        traceback.print_exc()
        sys.stdout.flush()
        raise

def download_em_massa_com_arquivo(cert_path, senha, tipo, data_inicio, data_fim, pasta_destino, url_base):
    """
    Versão alternativa que usa um arquivo .pfx salvo em vez de thumbprint
    
    Args:
        cert_path (str): Caminho para o arquivo .pfx
        senha (str): Senha do certificado
        tipo (str): 'emitidas' ou 'recebidas'
        data_inicio (str): Data inicial no formato YYYY-MM-DD
        data_fim (str): Data final no formato YYYY-MM-DD
        pasta_destino (str): Pasta onde salvar os arquivos
        url_base (str): URL base para o tipo de nota
    
    Returns:
        tuple: (total_notas, notas_baixadas)
    """
    print("\n" + "="*80)
    print("🚀 DOWNLOAD EM MASSA (COM ARQUIVO)")
    print("="*80)
    print(f"📌 TIMESTAMP: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📌 Arquivo certificado: {cert_path}")
    print(f"📌 Tipo: {tipo}")
    print(f"📌 Período: {data_inicio} a {data_fim}")
    print(f"📁 Pasta: {pasta_destino}")
    sys.stdout.flush()
    
    # Verifica se o arquivo existe
    if not os.path.exists(cert_path):
        error_msg = f"Arquivo de certificado não encontrado: {cert_path}"
        print(f"❌ {error_msg}")
        sys.stdout.flush()
        raise Exception(error_msg)
    
    print(f"✅ Certificado encontrado! Tamanho: {os.path.getsize(cert_path)} bytes")
    sys.stdout.flush()
    
    session = None
    try:
        # Tenta criar sessão com arquivo de certificado
        print("\n🔐 Criando sessão com arquivo de certificado...")
        sys.stdout.flush()
        
        try:
            session = criar_sessao_com_arquivo(cert_path, senha)
            print("✅ Sessão criada com sucesso via certificado_service!")
        except Exception as e:
            print(f"⚠️ Não foi possível criar sessão com certificado_service: {e}")
            print("Continuando com Selenium...")
        sys.stdout.flush()
        
        # Cria um objeto empresa simulado
        class EmpresaSimulada:
            def __init__(self, cert_path, senha):
                self.pk = 0
                self.nome_fantasia = f"Empresa com certificado ({os.path.basename(cert_path)})"
                self.certificado_thumbprint = "ARQUIVO"
                self.certificado_senha = senha
                self.certificado_arquivo = self
                self.path = cert_path
            
            def __str__(self):
                return self.nome_fantasia
        
        empresa_simulada = EmpresaSimulada(cert_path, senha)
        print(f"✅ Empresa simulada criada: {empresa_simulada.nome_fantasia}")
        sys.stdout.flush()
        
        # Usa a função principal com Selenium
        return download_em_massa(
            empresa=empresa_simulada,
            tipo=tipo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            pasta_destino=pasta_destino,
            url_base=url_base,
            senha=senha
        )
        
    except Exception as e:
        print(f"❌ ERRO no download_em_massa_com_arquivo: {e}")
        sys.stdout.flush()
        traceback.print_exc()
        raise
    finally:
        if session:
            try:
                session.close()
                print("🔒 Sessão encerrada.")
                sys.stdout.flush()
            except:
                pass

# Função de teste para uso direto
if __name__ == "__main__":
    print("="*80)
    print("🔧 TESTE DIRETO DO DOWNLOAD SERVICE")
    print("="*80)
    print("Este arquivo não deve ser executado diretamente.")
    print("Use através das views do Django ou crie um script de teste específico.")
    print("\nPara testar, execute:")
    print("  python manage.py shell")
    print("  from core.download_service import download_em_massa")
    print("  # ... teste com dados reais ...")
    print("="*80)