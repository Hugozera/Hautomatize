# teste_selenium_direto.py
"""
Teste direto do Selenium sem o Django
"""

import os
import sys
from pathlib import Path

# Adiciona o diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("="*80)
print("🚀 TESTE DIRETO DO SELENIUM")
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

# Importa a função do selenium_service
from core.selenium_service import baixar_com_selenium

# Cria empresa
empresa = EmpresaSimulada(
    nome="FARMAIVI (TESTE)",
    thumbprint=thumbprint,
    senha=senha,
    cert_path=certificado_path
)

# Verifica se já existem cookies para decidir modo
cookies_path = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), f"cookies_{thumbprint[:8]}.pkl")
modo = "AUTOMÁTICO (sem janela)" if os.path.exists(cookies_path) else "VISÍVEL (primeira vez)"

print(f"\n📌 Modo: {modo}")
print(f"📌 Cookies: {cookies_path}")
print(f"   {'✅ Existem' if os.path.exists(cookies_path) else '❌ Não existem'} cookies salvos")
print("\n" + "="*80)

# Executa o download (sem parâmetro headless - agora é automático)
resultado = baixar_com_selenium(
    empresa=empresa,
    tipo="recebidas",
    data_inicio="2026-02-01",
    data_fim="2026-02-28",
    pasta_destino="D:\\nfdowloader\\downloads_teste"
)

print(f"\n✅ Teste concluído: {resultado}")