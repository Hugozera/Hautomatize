import os
import sys

# Adiciona o diretório atual ao path
sys.path.append(os.path.dirname(__file__))

from core.conversor_service import converter_arquivo

def testar_conversao():
    print("="*50)
    print("CONVERSOR UNIVERSAL PDF → OFX")
    print("="*50)
    
    pdf_path = os.path.join(os.path.dirname(__file__), 'PDFS', 'jamel.pdf')
    
    if not os.path.exists(pdf_path):
        print(f"❌ Arquivo não encontrado: {pdf_path}")
        return
    
    print(f"📄 Arquivo: {pdf_path}")
    
    # Converter
    resultado, erro = converter_arquivo(pdf_path, 'ofx')
    
    if resultado:
        print(f"\n✅ CONVERSÃO BEM-SUCEDIDA!")
        print(f"📁 Arquivo: {resultado}")
        
        # Mostrar estatísticas
        with open(resultado, 'r', encoding='utf-8') as f:
            conteudo = f.read()
            num_transacoes = conteudo.count('<STMTTRN>')
            print(f"💰 Transações: {num_transacoes}")
            print(f"📊 Tamanho: {os.path.getsize(resultado)} bytes")
    else:
        print(f"\n❌ FALHOU: {erro}")

if __name__ == "__main__":
    testar_conversao()