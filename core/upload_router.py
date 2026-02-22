"""
Roteador unificado para uploads - SOLUÇÃO DEFINITIVA
Direciona para a view correta baseado nos parâmetros da requisição
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

@login_required
@csrf_exempt
def upload_router(request):
    """
    Roteia requisições de upload para as views especializadas
    """
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)
    
    print("\n" + "="*60)
    print("📤 UPLOAD ROUTER")
    print("="*60)
    print(f"POST data: {request.POST}")
    print(f"FILES: {list(request.FILES.keys())}")
    
    arquivo = request.FILES.get('arquivo')
    
    # Caso especial: arquivo ZIP (pode vir do frontend)
    if arquivo and arquivo.name.endswith('.zip'):
        print(f"📦 Arquivo ZIP detectado: {arquivo.name}")
        print("🔄 Redirecionando para processamento especial de ZIP")
        from .views_conversor import processar_zip_upload
        return processar_zip_upload(request)
    
    # Caso 1: Upload para conversor (tem formato_destino)
    if request.POST.get('formato_destino'):
        print("📄 Roteando para conversor")
        from .views_conversor import upload_arquivo_conversor
        return upload_arquivo_conversor(request)
    
    # Caso 2: Upload de certificado temporário (tem empresa_id e certificado)
    if request.POST.get('empresa_id') and request.FILES.get('certificado'):
        print("🔐 Roteando para upload de certificado")
        from .views import upload_certificado_temporario
        return upload_certificado_temporario(request)
    
    # Caso 3: Upload de certificado da loja (tem thumbprint e empresa_id)
    if request.POST.get('thumbprint') and request.POST.get('empresa_id'):
        print("🔑 Roteando para salvar certificado")
        from .views import salvar_certificado
        return salvar_certificado(request)
    
    print("❌ Tipo de upload não identificado")
    return JsonResponse({
        'erro': 'Tipo de upload não identificado',
        'dados_recebidos': {
            'post_keys': list(request.POST.keys()),
            'file_keys': list(request.FILES.keys())
        }
    }, status=400)