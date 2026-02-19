# teste_simples.py
import requests
from core.certificado_service import criar_sessao_certificado

thumbprint = "30BD94A507A8B767FF9CE8ADAFE73EF357327171"
senha = "123456"

print("1. Criando sessão...")
session = criar_sessao_certificado(thumbprint, senha)

print("2. Tentando acessar Notas Recebidas...")
resp = session.get("https://www.nfse.gov.br/EmissorNacional/Notas/Recebidas", allow_redirects=True)

print(f"Status: {resp.status_code}")
print(f"URL final: {resp.url}")
print(f"Tamanho: {len(resp.text)} bytes")

with open("teste_simples.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
print("HTML salvo em teste_simples.html")