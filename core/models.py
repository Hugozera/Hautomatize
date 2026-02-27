from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import os

def validar_cpf(value):
    # Implementar validação de CPF
    return value

class Pessoa(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='pessoa')
    cpf = models.CharField(max_length=14, unique=True, validators=[validar_cpf])
    telefone = models.CharField(max_length=20, blank=True)
    foto = models.ImageField(upload_to='fotos/', blank=True, null=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)
    # Token para agente local (usado pelo cliente-side agent)
    client_api_token = models.CharField(max_length=64, blank=True, null=True)
    permissions = models.TextField(blank=True, help_text='Códigos de permissão separados por vírgula, ex.: empresa.edit,certificado.manage')

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    def perm_list(self):
        """Retorna lista de códigos atribuídos diretamente à pessoa (mais roles)."""
        own = [p.strip() for p in (self.permissions or '').split(',') if p.strip()]
        # acrescentar permissões dos roles vinculados
        for role in self.roles.all():
            for p in role.perm_list():
                if p not in own:
                    own.append(p)
        return own

    class Meta:
        verbose_name = 'Pessoa'
        verbose_name_plural = 'Pessoas'


class Role(models.Model):
    """Papel (role) simples para agrupar permissões customizadas.

    - `permissions` armazena códigos separados por vírgula (ex.: "empresa.edit,certificado.manage").
    - Relacionamento ManyToMany com `Pessoa` permite atribuir papéis a usuários.
    """
    name = models.CharField(max_length=100, unique=True)
    codename = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    permissions = models.TextField(blank=True, help_text='Códigos de permissão separados por vírgula, ex.: empresa.edit,certificado.manage')
    pessoas = models.ManyToManyField(Pessoa, related_name='roles', blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def perm_list(self):
        return [p.strip() for p in (self.permissions or '').split(',') if p.strip()]

    class Meta:
        verbose_name = 'Papel (Role)'
        verbose_name_plural = 'Papéis (Roles)'


class Empresa(models.Model):
    TIPO_CHOICES = [
        ('matriz', 'Matriz'),
        ('filial', 'Filial')
    ]
    
    cnpj = models.CharField(max_length=18, unique=True)
    razao_social = models.CharField(max_length=200)
    nome_fantasia = models.CharField(max_length=200)
    inscricao_municipal = models.CharField(max_length=50, blank=True)
    inscricao_estadual = models.CharField(max_length=50, blank=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='matriz')
    ativo = models.BooleanField(default=True)
    usuarios = models.ManyToManyField(Pessoa, related_name='empresas', blank=True)
    
    # Endereço
    cep = models.CharField(max_length=9, blank=True)
    logradouro = models.CharField(max_length=200, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    complemento = models.CharField(max_length=100, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    municipio = models.CharField(max_length=100, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    
    # Certificado
    certificado_thumbprint = models.CharField(max_length=40, blank=True)
    certificado_senha = models.CharField(max_length=255, blank=True)  # Criptografar
    certificado_validade = models.DateField(null=True, blank=True)
    certificado_emitente = models.CharField(max_length=255, blank=True)
    certificado_arquivo = models.FileField(upload_to='certificados/', blank=True, null=True)
    ultimo_zip = models.FileField(upload_to='empresas/zips/', blank=True, null=True,
                                   help_text='Último arquivo ZIP gerado para esta empresa')
    
    data_cadastro = models.DateTimeField(auto_now_add=True)
    ultimo_download = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.nome_fantasia or self.razao_social

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering = ['nome_fantasia']

class Agendamento(models.Model):
    TIPO_NOTA_CHOICES = [
        ('entrada', 'Entrada'),
        ('saida', 'Saída'),
        ('ambos', 'Ambos')
    ]
    
    PERIODO_FIM_CHOICES = [
        ('ultimo_dia', 'Último dia do mês'),
        ('fixo', 'Dia fixo')
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='agendamentos')
    tipo_nota = models.CharField(max_length=10, choices=TIPO_NOTA_CHOICES)
    dia_mes = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(31)])
    periodo_inicio = models.IntegerField(default=1)
    periodo_fim_tipo = models.CharField(max_length=10, choices=PERIODO_FIM_CHOICES, default='ultimo_dia')
    periodo_fim_dia = models.IntegerField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    horario_preferencial = models.TimeField(default='23:00')
    notificar_email = models.BooleanField(default=False)
    compactar_auto = models.BooleanField(default=True)
    ultima_execucao = models.DateTimeField(null=True, blank=True)
    proxima_execucao = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.empresa.nome_fantasia} - {self.get_tipo_nota_display()} - Dia {self.dia_mes}"
class TarefaDownload(models.Model):
    """Modelo para rastrear tarefas de download em andamento"""
    STATUS_CHOICES = [
        ('aguardando', 'Aguardando'),
        ('processando', 'Processando'),
        ('extraindo_links', 'Extraindo Links'),
        ('baixando', 'Baixando Notas'),
        ('concluido', 'Concluído'),
        ('erro', 'Erro'),
        ('zipando', 'Zipando Arquivos'),
    ]
    
    usuario = models.ForeignKey(Pessoa, on_delete=models.CASCADE, null=True, blank=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    tipo_nota = models.CharField(max_length=10)  # 'emitidas' ou 'recebidas'
    data_inicio = models.DateField()
    data_fim = models.DateField()
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_inicio_execucao = models.DateTimeField(null=True, blank=True)
    data_fim_execucao = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='aguardando')
    progresso = models.IntegerField(default=0)  # 0 a 100
    mensagem = models.TextField(blank=True)
    
    total_notas = models.IntegerField(default=0)
    notas_baixadas = models.IntegerField(default=0)
    notas_erro = models.IntegerField(default=0)
    
    pasta_destino = models.CharField(max_length=500, blank=True)
    arquivo_zip = models.FileField(upload_to='zips/', blank=True, null=True)
    
    logs = models.TextField(blank=True)  # Para debug
    
    def __str__(self):
        return f"{self.empresa.nome_fantasia} - {self.tipo_nota} - {self.data_inicio} a {self.data_fim}"
    
    class Meta:
        ordering = ['-data_criacao']
    class Meta:
        verbose_name = 'Agendamento'
        verbose_name_plural = 'Agendamentos'

class HistoricoDownload(models.Model):
    STATUS_CHOICES = [
        ('sucesso', 'Sucesso'),
        ('parcial', 'Parcial'),
        ('erro', 'Erro')
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.SET_NULL, null=True, related_name='historicos')
    usuario = models.ForeignKey(Pessoa, on_delete=models.SET_NULL, null=True)
    tipo_nota = models.CharField(max_length=10)
    data_inicio = models.DateTimeField()
    data_fim = models.DateTimeField(null=True, blank=True)
    periodo_busca_inicio = models.DateField()
    periodo_busca_fim = models.DateField()
    quantidade_notas = models.IntegerField(default=0)
    quantidade_sucesso = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='erro')
    arquivo_zip = models.FileField(upload_to='zips/', blank=True, null=True)
    log_detalhado = models.TextField(blank=True)

    def __str__(self):
        return f"{self.empresa} - {self.data_inicio.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        verbose_name = 'Histórico de Download'
        verbose_name_plural = 'Históricos de Download'
        ordering = ['-data_inicio']
class ArquivoConversao(models.Model):
    """Modelo para arquivos enviados para conversão"""
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('convertendo', 'Convertendo'),
        ('concluido', 'Concluído'),
        ('erro', 'Erro'),
    ]
    
    usuario = models.ForeignKey(Pessoa, on_delete=models.CASCADE, null=True, blank=True)
    arquivo_original = models.FileField(upload_to='conversor/originais/')
    arquivo_convertido = models.FileField(upload_to='conversor/convertidos/', blank=True, null=True)
    nome_original = models.CharField(max_length=255)
    formato_origem = models.CharField(max_length=10)
    formato_destino = models.CharField(max_length=10)
    tamanho_original = models.IntegerField(default=0)  # em bytes
    tamanho_convertido = models.IntegerField(default=0, null=True, blank=True)
    banco = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    mensagem_erro = models.TextField(blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_conversao = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.nome_original} → {self.formato_destino}"
    
    class Meta:
        ordering = ['-data_criacao']


class LayoutBancario(models.Model):
    """Layouts aprendidos de extratos bancários por banco.
    Usado pelo conversor para gerar PDFs com aparência semelhante ao original.
    """
    nome = models.CharField(max_length=100, unique=True)
    identificadores = models.TextField(blank=True, help_text='Palavras-chave separadas por vírgula para detectar o banco no texto do PDF/OFX')
    template_html = models.TextField(blank=True, help_text='HTML usado como template para gerar o PDF a partir do OFX')
    exemplo_pdf = models.FileField(upload_to='conversor/layout_examples/', blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = 'Layout Bancário'
        verbose_name_plural = 'Layouts Bancários'


class NotaFiscal(models.Model):
    TIPO_CHOICES = [
        ('entrada', 'Entrada'),
        ('saida', 'Saída')
    ]
    
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='notas')
    historico = models.ForeignKey(HistoricoDownload, on_delete=models.CASCADE, related_name='notas')
    numero = models.CharField(max_length=50)
    chave_acesso = models.CharField(max_length=44, unique=True)
    data_emissao = models.DateField()
    valor = models.DecimalField(max_digits=15, decimal_places=2)
    tomador_cnpj = models.CharField(max_length=18, blank=True)
    tomador_nome = models.CharField(max_length=200, blank=True)
    arquivo_pdf = models.FileField(upload_to='pdfs/')
    arquivo_xml = models.FileField(upload_to='xmls/', blank=True, null=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    data_download = models.DateTimeField(auto_now_add=True)
    impostos = models.JSONField(blank=True, null=True,
                                help_text='Dicionário com valores de impostos extraídos do XML')

    def __str__(self):
        return f"{self.numero} - {self.data_emissao}"

    class Meta:
        verbose_name = 'Nota Fiscal'
        verbose_name_plural = 'Notas Fiscais'
        ordering = ['-data_emissao']