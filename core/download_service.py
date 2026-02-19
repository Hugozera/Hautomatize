"""
Serviço de download de NFSe
HDowloader - Download Automático de NFSe
"""
import sys
import os
import time
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

print("\n" + "="*80)
print("🔵 DOWNLOAD_SERVICE.PY CARREGADO")
print("="*80)
sys.stdout.flush()

# Importa o Playwright
try:
    from .playwright_service import baixar_com_playwright
    print("✅ playwright_service importado com sucesso!")
    sys.stdout.flush()
except ImportError as e:
    print(f"❌ Erro ao importar playwright_service: {e}")
    print("Verifique se o arquivo playwright_service.py existe na pasta core/")
    sys.stdout.flush()
    raise


def download_em_massa(empresa, tipo, data_inicio, data_fim, pasta_destino, url_base=None, senha=None):
    """
    Função principal usando Playwright com certificado da empresa

    Args:
        empresa: Objeto Empresa do Django
        tipo: 'emitidas' ou 'recebidas'
        data_inicio: YYYY-MM-DD
        data_fim: YYYY-MM-DD
        pasta_destino: Pasta onde salvar
        url_base: Não usado no Playwright (mantido para compatibilidade)
        senha: Não usado no Playwright (já está na empresa)

    Returns:
        tuple: (total_notas, baixadas)
    """
    print("\n" + "="*80)
    print("🚀 DOWNLOAD SERVICE CHAMANDO PLAYWRIGHT")
    print("="*80)
    print(f"🏢 Empresa: {empresa.nome_fantasia}")
    print(f"📋 Tipo: {tipo}")
    print(f"📅 Período: {data_inicio} a {data_fim}")
    print(f"📁 Pasta: {pasta_destino}")
    print(f"🔐 Certificado: {empresa.certificado_arquivo.path if empresa.certificado_arquivo else 'Nenhum'}")
    sys.stdout.flush()

    try:
        # Verifica se o certificado existe
        if not empresa.certificado_arquivo:
            error_msg = "Empresa não possui arquivo de certificado!"
            print(f"❌ {error_msg}")
            sys.stdout.flush()
            raise Exception(error_msg)

        cert_path = empresa.certificado_arquivo.path
        if not os.path.exists(cert_path):
            error_msg = f"Arquivo de certificado não encontrado: {cert_path}"
            print(f"❌ {error_msg}")
            sys.stdout.flush()
            raise Exception(error_msg)

        print(f"✅ Certificado encontrado! Tamanho: {os.path.getsize(cert_path)} bytes")
        sys.stdout.flush()

        # Chama o Playwright (headless=True para produção)
        print("\n🤖 CHAMANDO PLAYWRIGHT...")
        sys.stdout.flush()

        resultado = baixar_com_playwright(
            empresa=empresa,
            tipo=tipo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            pasta_destino=pasta_destino,
            headless=True  # True = automático (sem janela)
        )

        print(f"\n✅ PLAYWRIGHT RETORNOU: {resultado}")
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
        traceback.print_exc()
        raise