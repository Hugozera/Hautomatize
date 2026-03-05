"""
Teste direto do Playwright sem o Django
Baixa notas do Emissor Nacional
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Adiciona o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("="*80)
print("🚀 TESTE DIRETO DO PLAYWRIGHT")
print("="*80)

# Configurações
thumbprint = "30BD94A507A8B767FF9CE8ADAFE73EF357327171"
senha = "123456"  # ← USE A SENHA CORRETA

# Procura por qualquer arquivo .pfx na pasta
pasta_cert = Path("D:/nfdowloader/media/certificados")
arquivos_pfx = list(pasta_cert.glob("*.pfx"))

if arquivos_pfx:
    certificado_path = str(arquivos_pfx[0])
    print(f"✅ Certificado encontrado: {certificado_path}")

    # Se não for certificado.pfx, renomeia automaticamente
    if "certificado.pfx" not in certificado_path:
        novo_nome = pasta_cert / "certificado.pfx"
        try:
            os.rename(certificado_path, novo_nome)
            certificado_path = str(novo_nome)
            print(f"✅ Renomeado para: {certificado_path}")
        except:
            print(f"⚠️ Não foi possível renomear, usando original: {certificado_path}")
else:
    print("❌ Nenhum certificado .pfx encontrado na pasta")
    print("Por favor, exporte o certificado com o comando:")
    print('certutil -user -exportPFX My 30BD94A507A8B767FF9CE8ADAFE73EF357327171 "D:\\nfdowloader\\media\\certificados\\certificado.pfx" -p 123456')
    sys.exit(1)

# Cria um objeto empresa simulado
class EmpresaSimulada:
    def __init__(self, nome, thumbprint, senha, cert_path):
        self.nome_fantasia = nome
        self.certificado_thumbprint = thumbprint
        self.certificado_senha = senha
        self.certificado_arquivo = self
        self.path = cert_path

    def __str__(self):
        return self.nome_fantasia

# Importa a função do playwright_service
try:
    from core.playwright_service import baixar_com_playwright
    print("✅ playwright_service importado com sucesso!")
except ImportError as e:
    print(f"❌ Erro ao importar playwright_service: {e}")
    print("Verifique se o arquivo playwright_service.py existe na pasta core/")
    sys.exit(1)

# Cria empresa
empresa = EmpresaSimulada(
    nome="FARMAIVI (TESTE)",
    thumbprint=thumbprint,
    senha=senha,
    cert_path=certificado_path
)

# Verifica cookies
cookies_path = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), f"cookies_{thumbprint[:8]}.pkl")
modo = "AUTOMÁTICO" if os.path.exists(cookies_path) else "PRIMEIRA VEZ (vai pedir certificado)"

print(f"\n📌 Modo: {modo}")
print(f"📌 Cookies: {cookies_path}")
print(f"   {'✅ Existem' if os.path.exists(cookies_path) else '❌ Não existem'} cookies salvos")
print("\n" + "="*80)

# Opções de período
print("\n📅 Opções de período:")
print("   1 - Fevereiro/2026 (mês com notas)")
print("   2 - Janeiro/2026 (mês sem notas)")
print("   3 - Últimos 30 dias")
print("   4 - Escolher manualmente")
opcao_periodo = input("Digite 1, 2, 3 ou 4 [1]: ").strip() or "1"

if opcao_periodo == "1":
    data_inicio = "2026-02-01"
    data_fim = "2026-02-28"
    print(f"📅 Período selecionado: {data_inicio} a {data_fim}")
elif opcao_periodo == "2":
    data_inicio = "2026-01-01"
    data_fim = "2026-01-31"
    print(f"📅 Período selecionado: {data_inicio} a {data_fim}")
elif opcao_periodo == "3":
    hoje = datetime.now()
    data_fim = hoje.strftime("%Y-%m-%d")
    data_inicio = (hoje - timedelta(days=30)).strftime("%Y-%m-%d")
    print(f"📅 Período selecionado: {data_inicio} a {data_fim}")
else:
    data_inicio = input("Data início (YYYY-MM-DD): ").strip()
    data_fim = input("Data fim (YYYY-MM-DD): ").strip()

# Pergunta o tipo de nota
print("\n📋 Tipo de nota:")
print("   1 - Recebidas (compras)")
print("   2 - Emitidas (vendas)")
opcao_tipo = input("Digite 1 ou 2 [1]: ").strip() or "1"

tipo = "recebidas" if opcao_tipo == "1" else "emitidas"
print(f"📋 Tipo selecionado: {tipo}")

# Pergunta o modo de execução
print("\n🎯 Modo de execução:")
print("   1 - Automático (headless, sem janela)")
print("   2 - Visível (com janela, para debug)")
opcao = input("Digite 1 ou 2 [1]: ").strip() or "1"

headless = (opcao == "1")
print(f"👁️ Modo: {'AUTOMÁTICO' if headless else 'VISÍVEL'}")

# Define pasta de destino
pasta_download = f"D:\\nfdowloader\\downloads_{tipo}_{data_inicio}_a_{data_fim}"
print(f"📁 Pasta de download: {pasta_download}")

print("\n" + "="*80)
print("🚀 INICIANDO DOWNLOAD...")
print("="*80)

# Executa o download
resultado = baixar_com_playwright(
    empresa=empresa,
    tipo=tipo,
    data_inicio=data_inicio,
    data_fim=data_fim,
    pasta_destino=pasta_download,
    headless=headless
)

print(f"\n✅ Teste concluído!")
print(f"📊 Resultado: {resultado}")
print(f"📁 Arquivos salvos em: {pasta_download}")

# Lista os arquivos baixados
if os.path.exists(pasta_download):
    arquivos = os.listdir(pasta_download)
    if arquivos:
        print(f"\n📁 Arquivos baixados ({len(arquivos)}):")
        for arquivo in sorted(arquivos)[:10]:  # Mostra os 10 primeiros
            tamanho = os.path.getsize(os.path.join(pasta_download, arquivo))
            print(f"   📄 {arquivo} - {tamanho:,} bytes".replace(',', '.'))
        if len(arquivos) > 10:
            print(f"   ... e mais {len(arquivos) - 10} arquivo(s)")
    else:
        print("\n📁 Nenhum arquivo baixado")

print("\n" + "="*80)