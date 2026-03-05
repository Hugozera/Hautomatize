from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import os

def validar_cpf(value):
    # Implementar validação de CPF
    return value


class Conversa(models.Model):
    """
    Conversa entre duas ou mais pessoas
    """
    participantes = models.ManyToManyField('Pessoa', related_name='conversas')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-atualizado_em']


class AnexoMensagem(models.Model):
    """
    Arquivo anexado a uma mensagem
    """
    arquivo = models.FileField(upload_to='chat_anexos/%Y/%m/%d/')
    nome_original = models.CharField(max_length=255)
    tamanho = models.IntegerField(help_text='Tamanho em bytes')
    tipo = models.CharField(max_length=100, help_text='MIME type')
    criado_em = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.nome_original


class Mensagem(models.Model):
    """
    Mensagem em uma conversa ou atendimento
    """
    conversa = models.ForeignKey('Conversa', on_delete=models.CASCADE, null=True, blank=True, related_name='mensagens')
    # Use a distinct related_name to avoid clashing with painel.ChatMessage.mensagens
    atendimento = models.ForeignKey('painel.Atendimento', on_delete=models.CASCADE, null=True, blank=True, related_name='mensagens_core', related_query_name='mensagens_core')
    remetente = models.ForeignKey('Pessoa', on_delete=models.SET_NULL, null=True, related_name='mensagens_enviadas')
    conteudo = models.TextField(blank=True)
    anexos = models.ManyToManyField(AnexoMensagem, blank=True, related_name='mensagens')
    criado_em = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)
    lida_em = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['criado_em']
        indexes = [
            models.Index(fields=['conversa', 'criado_em']),
            models.Index(fields=['atendimento', 'criado_em']),
        ]
    
    def __str__(self):
        return f'Mensagem {self.id} - {self.criado_em}'
    
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
        """Retorna lista de códigos de permissões atribuídas diretamente à pessoa."""
        return [p.strip() for p in (self.permissions or '').split(',') if p.strip()]

    @property
    def usuario(self):
        """Compatibilidade: alias para o campo `user` usado nos templates e views antigos."""
        return self.user

    @property
    def nome(self):
        """Compatibilidade: nome completo do usuário."""
        return self.user.get_full_name() or self.user.username

    @property
    def cargo(self):
        """Compatibilidade: cargo/exibição rápida (não persistido)."""
        return ''

    @property
    def departamento(self):
        """Compatibilidade: retorna None quando não há departamento modelado aqui."""
        return None

    def has_perm_code(self, code):
        """Retorna True se o usuário tem a permissão diretamente atribuída."""
        return code in self.perm_list()

    def save(self, *args, **kwargs):
        """Redimensiona imagem antes de salvar."""
        if self.foto:
            self._resize_image()
        super().save(*args, **kwargs)

    def _resize_image(self):
        """Redimensiona a imagem para máximo de 300x300px."""
        from PIL import Image
        from io import BytesIO
        from django.core.files.base import ContentFile
        
        try:
            img = Image.open(self.foto.file)
            
            # Limite máximo
            max_size = (300, 300)
            
            # Se imagem é maior que o limite, redimensionar
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Converter para RGB se for PNG com alpha
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        rgb_img.paste(img, mask=img.split()[-1])
                    else:
                        rgb_img.paste(img)
                    img = rgb_img
                
                # Salvar em BytesIO
                img_io = BytesIO()
                img.save(img_io, format='JPEG', quality=85, optimize=True)
                img_io.seek(0)
                
                # Substituir arquivo
                import os
                filename = os.path.splitext(self.foto.name)[0] + '.jpg'
                self.foto.save(
                    filename,
                    ContentFile(img_io.read()),
                    save=False
                )
        except Exception:
            # Se houver erro ao redimensionar, deixar como está
            pass

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
    certificado_antigo = models.BooleanField(default=False)
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
 

# --- Models migrated from painel app ---
class Departamento(models.Model):
    nome = models.CharField(max_length=50)

    def __str__(self):
        return self.nome

    class Meta:
        app_label = 'painel'
        permissions = []


class Analista(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE)
    disponivel = models.BooleanField(default=True)
    disponivel_em = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    class Meta:
        app_label = 'painel'
        permissions = []


class Atendimento(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('atendendo', 'Atendendo'),
        ('finalizado', 'Finalizado'),
    ]
    departamento = models.ForeignKey(Departamento, on_delete=models.CASCADE)
    analista = models.ForeignKey(Analista, on_delete=models.SET_NULL, null=True, blank=True)
    empresa_obj = models.ForeignKey(Empresa, on_delete=models.SET_NULL, null=True, blank=True, related_name='atendimentos')
    empresa = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')
    criado_em = models.DateTimeField(auto_now_add=True)
    iniciado_em = models.DateTimeField(null=True, blank=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)
    motivo = models.TextField(blank=True)
    resolucao = models.TextField(blank=True)
    historico = models.TextField(blank=True)

    class Meta:
        app_label = 'painel'
        permissions = []

    def __str__(self):
        return f"{self.departamento} - {self.empresa} ({self.status})"


class AtendimentoAnexo(models.Model):
    """Arquivos enviados durante um atendimento (prints, logs, etc.)."""
    atendimento = models.ForeignKey(Atendimento, on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField(upload_to='painel/anexos/')
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anexo {self.id} - {self.atendimento}"

    class Meta:
        app_label = 'painel'
        verbose_name = 'Anexo de Atendimento'
        verbose_name_plural = 'Anexos de Atendimento'


class ChatMessage(models.Model):
    """Mensagens do chat vinculadas a um Atendimento.

    Armazenadas para histórico e recuperação quando um usuário abrir o chat.
    """
    atendimento = models.ForeignKey(Atendimento, on_delete=models.CASCADE, related_name='mensagens')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.criado_em}] {self.user or 'Anon'}: {self.message[:40]}"

    class Meta:
        app_label = 'painel'
        verbose_name = 'Mensagem de Chat'
        verbose_name_plural = 'Mensagens de Chat'
        ordering = ['criado_em']


class ChatPresence(models.Model):
    """Registro simples de presença/estado online por Atendimento."""
    atendimento = models.ForeignKey(Atendimento, on_delete=models.CASCADE, related_name='presences')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_username()} @ {self.atendimento_id} - {'online' if self.active else 'offline'}"

    class Meta:
        app_label = 'painel'
        verbose_name = 'Presença de Chat'
        verbose_name_plural = 'Presenças de Chat'
        unique_together = (('atendimento', 'user'),)


class Conversation(models.Model):
    """Conversa entre usuários e/ou vinculada a uma Empresa.

    Pode ser usada para conversas gerais (tipo Teams) entre usuários, ou
    conversas relacionadas a uma `Empresa` (suporte ao cliente).
    """
    title = models.CharField(max_length=200, blank=True)
    empresa = models.ForeignKey('core.Empresa', null=True, blank=True, on_delete=models.SET_NULL)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.title:
            return self.title
        if self.empresa:
            return f"Conversa: {self.empresa.nome_fantasia}"
        return f"Conversa #{self.id}"


class ConversationParticipant(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    last_read = models.DateTimeField(null=True, blank=True)
    joined_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('conversation', 'user'),)


class ConversationMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField()
    attachments = models.JSONField(default=list, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.criado_em}] {self.user or 'Anon'}: {self.message[:40]}"

    class Meta:
        ordering = ['criado_em']


class Notification(models.Model):
    """Simple server-side notification for chat push delivery.

    - `user`: recipient user
    - `payload`: JSON payload to send via notifier WS
    - `delivered`: whether it has been forwarded to an active notifier socket
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    payload = models.JSONField()
    created = models.DateTimeField(auto_now_add=True)
    delivered = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created']


# `SiegCredential` removed: SIEG integration now uses a global key configured
# in settings (`SIEG_API_KEY`) or the `SIEG_API_KEY` environment variable.
# The migration to delete the model is included under core/migrations/.