# Scripts de Teste e Debug

Esta pasta contém scripts auxiliares para teste, debug e diagnóstico do sistema.

## 📋 Scripts de Teste

### Testes de Certificados
- **test_pfx_conversion.py** - Testa conversão de certificados PFX
- **test_provider_path.py** - Verifica paths de providers de certificados
- **test_python_pkcs12.py** - Testa manipulação PKCS12
- **diagnose_openssl.py** - Diagnóstico de OpenSSL

### Testes de Permissões e Usuários
- **test_user_empresas.py** - Testa associação usuário-empresa
- **check_hugo_perms.py** - Verifica permissões do usuário Hugo
- **check_hugo_user.py** - Verifica configuração do usuário Hugo
- **verify_hugo_permissions.py** - Validação completa de permissões Hugo
- **test_hugo_perms_simple.py** - Teste simplificado de permissões Hugo
- **check_user_companies.py** - Verifica empresas associadas a usuários

### Testes de Navegador/Automação
- **teste_navegador.py** - Testes de automação de navegador
- **teste_selenium_direto.py** - Testes diretos com Selenium
- **testplay.py** - Testes com Playwright
- **testar_bb.py** - Testes específicos do Banco do Brasil

### Testes de Sistema
- **test.py** - Script de teste geral
- **test_fixes.py** - Testes de correções implementadas
- **teste_simples.py** - Testes simplificados

### Debug e Diagnóstico
- **debug_modal_snippet.py** - Debug de modais (snippet 1)
- **debug_modal_snippet2.py** - Debug de modais (snippet 2)
- **diagnostico_emissor.py** - Diagnóstico do emissor de NFSe

### Utilitários
- **associate_all_empresas.py** - Associa todas empresas a um usuário
- **summary_changes.py** - Resumo de mudanças no sistema
- **emissor_cliente.py** - Cliente para emissor de NFSe

## 📁 Subpastas

### `/certs`
Certificados de teste:
- **teste.pem** - Certificado de teste em formato PEM
- **teste.pfx** - Certificado de teste em formato PFX

## 📄 Arquivos de Teste

- **teste_simples.html** - Arquivo HTML para testes
- **secretaria_rendered.html** - Template renderizado de secretaria
- **test_page0.png** - Screenshot de teste
- **script_output.txt** - Saída de scripts de teste

## ⚠️ Aviso

Estes scripts são para **desenvolvimento e debug apenas**. Não devem ser executados em produção.
