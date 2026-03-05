# diagnostico_emissor.py
"""
Script de diagnóstico para o Emissor Nacional
"""

import requests
from bs4 import BeautifulSoup
import os
import tempfile
import subprocess
from urllib.parse import urljoin, quote

# ============================================
# FUNÇÕES AUXILIARES (cópia do certificado_service)
# ============================================

def criar_sessao_certificado_diagnostico(thumbprint, senha):
    """Versão simplificada para diagnóstico"""
    from core.certificado_service import criar_sessao_certificado
    return criar_sessao_certificado(thumbprint, senha)

# ============================================
# TESTES
# ============================================

def testar_url_completa(session, url, descricao):
    """Testa uma URL e mostra detalhes"""
    print(f"\n📌 {descricao}")
    print(f"   URL: {url}")
    
    try:
        resp = session.get(url, allow_redirects=True, timeout=30)
        print(f"   Status: {resp.status_code}")
        print(f"   URL final: {resp.url}")
        print(f"   Tamanho: {len(resp.text)} bytes")
        
        # Analisa o HTML retornado
        soup = BeautifulSoup(resp.text, 'html.parser')
        titulo = soup.find('title')
        if titulo:
            print(f"   Título: {titulo.text}")
        
        # Verifica se é página de login
        if 'Login' in resp.text or 'Acesso' in resp.text:
            print("   ⚠️ PARECE SER PÁGINA DE LOGIN")
        elif 'Notas' in resp.text or 'Emitidas' in resp.text:
            print("   ✅ PARECE SER ÁREA LOGADA")
            
        return resp
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return None

def diagnostico_completo(thumbprint, senha):
    """Executa diagnóstico completo"""
    print("="*70)
    print("🔍 DIAGNÓSTICO DO EMISSOR NACIONAL")
    print("="*70)
    print(f"Thumbprint: {thumbprint}")
    print(f"Senha: {'*' * len(senha)}")
    
    # 1. Criar sessão
    print("\n📌 1. Criando sessão com certificado...")
    session = criar_sessao_certificado_diagnostico(thumbprint, senha)
    
    if not session:
        print("❌ Falha ao criar sessão")
        return
    
    print("✅ Sessão criada")
    
    # 2. Testar URLs principais
    urls_teste = [
        ("Página inicial", "https://www.nfse.gov.br/EmissorNacional"),
        ("Login via certificado", "https://www.nfse.gov.br/EmissorNacional/Certificado"),
        ("Dashboard", "https://www.nfse.gov.br/EmissorNacional/Dashboard"),
        ("Notas Emitidas", "https://www.nfse.gov.br/EmissorNacional/Notas/Emitidas"),
        ("Notas Recebidas", "https://www.nfse.gov.br/EmissorNacional/Notas/Recebidas"),
    ]
    
    respostas = {}
    for desc, url in urls_teste:
        respostas[desc] = testar_url_completa(session, url, desc)
    
    # 3. Verificar cookies e headers
    print("\n📌 3. Cookies da sessão:")
    for cookie in session.cookies:
        print(f"   {cookie.name}: {cookie.value[:20]}...")
    
    # 4. Tentar buscar notas com data atual
    print("\n📌 4. Testando busca de notas...")
    data_atual = "2026-02-01"
    data_fim = "2026-02-28"
    
    data_inicio_fmt = data_atual.replace('-', '/')
    data_fim_fmt = data_fim.replace('-', '/')
    
    url_busca = f"https://www.nfse.gov.br/EmissorNacional/Notas/Recebidas?executar=1&busca=&datainicio={quote(data_inicio_fmt)}&datafim={quote(data_fim_fmt)}"
    
    resp = testar_url_completa(session, url_busca, "Busca de notas")
    
    # 5. Salvar HTML para análise
    if resp:
        with open("diagnostico_emissor.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print("\n📄 HTML salvo em 'diagnostico_emissor.html'")

if __name__ == "__main__":
    import sys
    sys.path.append('D:\\nfdowloader')
    
    thumbprint = input("Thumbprint: ").strip()
    senha = input("Senha: ").strip()
    
    diagnostico_completo(thumbprint, senha)