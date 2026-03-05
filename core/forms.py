from django import forms
from django.contrib.auth.models import User
import os
from .models import Pessoa, Empresa, Agendamento

# helper to keep permissions choices in sync with the matrix

def _permission_choices():
    """Retorna tuplas agrupadas por módulo com códigos e rótulos.

    Retorna estrutura para optgroups, cada item é (module_label, [(code,label),...]).
    """
    from .permissions import all_permission_codes
    # mapeamentos para rotulagem mais amigável
    friendly = {
        'departamento': 'Departamento',
        'analista': 'Analista',
        'atendimento': 'Atendimento',
        'empresa': 'Empresa',
        'pessoa': 'Usuário',
        'certificado': 'Certificado',
        'conversor': 'Conversor',
        'sieg': 'SIEG',
        'agendamento': 'Agendamento',
        'download': 'Download',
        'historico': 'Histórico',
    }
    action_map = {
        'add': 'Cadastrar',
        'edit': 'Editar',
        'change': 'Editar',
        'delete': 'Excluir',
        'view': 'Visualizar',
        'manage': 'Gerenciar',
        'use': 'Utilizar',
    }
    modules = {}
    for code in all_permission_codes():
        if '.' in code:
            mod, action = code.split('.', 1)
        else:
            mod, action = code, ''
        label = f"{friendly.get(mod, mod.capitalize())} – {action_map.get(action, action)}"
        modules.setdefault(mod, []).append((code, label))
    # convert to list of tuples for choicegroups
    grouped = []
    for mod in sorted(modules.keys()):
        grouped.append((friendly.get(mod, mod.capitalize()), modules[mod]))
    return grouped


class PessoaForm(forms.ModelForm):
    username = forms.CharField(max_length=150, required=True, label='Usuário')
    first_name = forms.CharField(max_length=150, required=True, label='Nome')
    last_name = forms.CharField(max_length=150, required=True, label='Sobrenome')
    email = forms.EmailField(required=True, label='E-mail')
    password = forms.CharField(widget=forms.PasswordInput, required=False, label='Senha')
    password_confirm = forms.CharField(widget=forms.PasswordInput, required=False, label='Confirme a senha')

    permissions = forms.MultipleChoiceField(
        choices=_permission_choices(),
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        label='Permissões diretas'
    )

    class Meta:
        model = Pessoa
        fields = ['cpf', 'telefone', 'foto', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['username'].initial = self.instance.user.username
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['password'].required = False
            self.fields['password_confirm'].required = False
            self.initial['permissions'] = [p for p in (self.instance.permissions or '').split(',') if p]
        else:
            self.fields['password'].required = True
            self.fields['password_confirm'].required = True

        # style classes for new fields (checkbox lists)
        self.fields['permissions'].widget.attrs.update({'class': 'form-check'})

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            return username
        from django.contrib.auth.models import User
        # Se for edição, ignore o próprio usuário
        if self.instance and self.instance.pk and getattr(self.instance, 'user', None):
            if User.objects.filter(username=username).exclude(pk=self.instance.user.pk).exists():
                raise forms.ValidationError('Nome de usuário já em uso.')
        else:
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError('Nome de usuário já em uso.')
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        password_confirm = cleaned.get('password_confirm')
        
        if password or password_confirm:
            if password != password_confirm:
                self.add_error('password_confirm', 'As senhas não coincidem.')
        
        # Validar CPF
        cpf = cleaned.get('cpf')
        if cpf:
            # Implementar validação de CPF
            pass
        
        return cleaned

    def clean_foto(self):
        foto = self.cleaned_data.get('foto')
        if foto:
            # Limite 2 MB
            if getattr(foto, 'size', 0) > 2 * 1024 * 1024:
                raise forms.ValidationError('Foto muito grande. Tamanho máximo: 2 MB.')
            # Extensões permitidas
            ext = os.path.splitext(foto.name)[1].lower()
            if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                raise forms.ValidationError('Formatos permitidos: JPG, PNG, WEBP.')
        return foto

    def save(self, commit=True):
        pessoa = super().save(commit=False)
        
        # Redimensionar imagem se foi feito upload
        if pessoa.foto and hasattr(pessoa.foto, 'file'):
            self._resize_image(pessoa.foto)
        
        if not pessoa.pk:
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                email=self.cleaned_data['email'],
                password=self.cleaned_data['password'],
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name']
            )
            pessoa.user = user
        else:
            user = pessoa.user
            user.username = self.cleaned_data['username']
            user.email = self.cleaned_data['email']
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            
            if self.cleaned_data.get('password'):
                user.set_password(self.cleaned_data['password'])
            
            user.save()
        
        # atribui permissões diretas
        pessoa.permissions = ','.join(self.cleaned_data.get('permissions') or [])
        if commit:
            pessoa.save()
        
        return pessoa

    def _resize_image(self, image_field):
        """Redimensiona a imagem para tamanho máximo de 300x300px"""
        from PIL import Image
        from io import BytesIO
        from django.core.files.base import ContentFile
        
        try:
            img = Image.open(image_field.file)
            
            # Limite máximo
            max_size = (300, 300)
            
            # Se imagem é maior que o limite, redimensionar
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Converter para RGB se for PNG com alpha
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = rgb_img
                
                # Salvar em BytesIO
                img_io = BytesIO()
                img.save(img_io, format='JPEG', quality=85, optimize=True)
                img_io.seek(0)
                
                # Substituir arquivo
                image_field.save(
                    os.path.splitext(image_field.name)[0] + '.jpg',
                    ContentFile(img_io.read()),
                    save=False
                )
        except Exception as e:
            # Se houver erro, apenas deixar como está
            pass

class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = [
            'cnpj', 'razao_social', 'nome_fantasia', 'inscricao_municipal', 
            'inscricao_estadual', 'tipo', 'ativo', 'cep', 'logradouro', 
            'numero', 'complemento', 'bairro', 'municipio', 'uf',
            'certificado_thumbprint', 'certificado_senha', 
            'certificado_validade', 'certificado_emitente'
        ]
        widgets = {
            'cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00.000.000/0000-00'}),
            'cep': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00000-000'}),
            'certificado_senha': forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
            'certificado_validade': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Adicionar classes Bootstrap
        for field in self.fields:
            if not isinstance(self.fields[field].widget, (forms.CheckboxInput, forms.RadioSelect)):
                if 'class' not in self.fields[field].widget.attrs:
                    self.fields[field].widget.attrs['class'] = 'form-control'
        
        # Ajustar campo ativo
        self.fields['ativo'].widget.attrs['class'] = 'form-check-input'





class AgendamentoForm(forms.ModelForm):
    class Meta:
        model = Agendamento
        fields = '__all__'
        widgets = {
            'horario_preferencial': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'ultima_execucao': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'proxima_execucao': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if not isinstance(self.fields[field].widget, (forms.CheckboxInput, forms.RadioSelect)):
                if 'class' not in self.fields[field].widget.attrs:
                    self.fields[field].widget.attrs['class'] = 'form-control'
        self.fields['ativo'].widget.attrs['class'] = 'form-check-input'
        self.fields['notificar_email'].widget.attrs['class'] = 'form-check-input'
        self.fields['compactar_auto'].widget.attrs['class'] = 'form-check-input'
