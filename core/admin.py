from django.contrib import admin
from .models import Pessoa, Empresa, Agendamento, HistoricoDownload, NotaFiscal

@admin.register(Pessoa)
class PessoaAdmin(admin.ModelAdmin):
    list_display = ("user", "cpf", "telefone", "ativo", "data_cadastro")
    search_fields = ("user__username", "cpf")

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome_fantasia", "cnpj", "tipo", "ativo", "data_cadastro")
    search_fields = ("nome_fantasia", "cnpj")
    list_filter = ("tipo", "ativo")

@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ("empresa", "tipo_nota", "dia_mes", "ativo", "horario_preferencial")
    list_filter = ("tipo_nota", "ativo")

@admin.register(HistoricoDownload)
class HistoricoDownloadAdmin(admin.ModelAdmin):
    list_display = ("empresa", "usuario", "tipo_nota", "data_inicio", "data_fim", "quantidade_notas", "quantidade_sucesso", "status")
    list_filter = ("tipo_nota", "status")

@admin.register(NotaFiscal)
class NotaFiscalAdmin(admin.ModelAdmin):
    list_display = ("empresa", "numero", "chave_acesso", "data_emissao", "valor", "tipo", "data_download")
    search_fields = ("numero", "chave_acesso")
    list_filter = ("tipo",)
