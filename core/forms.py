from django import forms
from django.contrib.auth.models import User
import os
from .models import Pessoa, Empresa, Agendamento, Role

# helper to keep permissions choices in sync with the matrix

def _permission_choices():
    """Retorna tuplas (valor, rótulo) para cada código de permissão.

    Usa a lista completa retornada por `all_permission_codes` para garantir que
    códigos adicionais (como `download.manage` ou `role.manage`) apareçam nos
    checkboxes mesmo quando não faziam parte da matriz original.
    """
    from .permissions import all_permission_codes
    choices = []
    for code in all_permission_codes():
        # exibe 'empresa.edit' como 'Empresa – edit' para humanizar
        if '.' in code:
            model, action = code.split('.', 1)
            label = f"{model.capitalize()} – {action}"
        else:
            label = code
        choices.append((code, label))
    return choices


class PessoaForm(forms.ModelForm):
    username = forms.CharField(max_length=150, required=True, label='Usuário')
    first_name = forms.CharField(max_length=150, required=True, label='Nome')
    last_name = forms.CharField(max_length=150, required=True, label='Sobrenome')
    email = forms.EmailField(required=True, label='E-mail')
    password = forms.CharField(widget=forms.PasswordInput, required=False, label='Senha')
    password_confirm = forms.CharField(widget=forms.PasswordInput, required=False, label='Confirme a senha')

    # associação de roles e permissões diretas
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.filter(ativo=True),
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
        required=False,
        label='Papéis (roles)'
    )
    permissions = forms.MultipleChoiceField(
        choices=_permission_choices(),
        widget=forms.CheckboxSelectMultiple,
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
            # roles / permissions initial values
            self.initial['roles'] = self.instance.roles.filter(ativo=True)
            self.initial['permissions'] = [p for p in (self.instance.permissions or '').split(',') if p]
        else:
            self.fields['password'].required = True
            self.fields['password_confirm'].required = True

        # style classes for new fields
        self.fields['roles'].widget.attrs.update({'class': 'form-select', 'size': '6'})
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
        
        # atribui permissões e roles antes de salvar m2m
        pessoa.permissions = ','.join(self.cleaned_data.get('permissions') or [])
        if commit:
            pessoa.save()
            # atualizar roles também
            if 'roles' in self.cleaned_data:
                pessoa.roles.set(self.cleaned_data['roles'])
        
        return pessoa

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




class RoleForm(forms.ModelForm):
    # override field so we can expose checkboxes instead of a textarea
    permissions = forms.MultipleChoiceField(
        choices=_permission_choices(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Permissões'
    )

    class Meta:
        model = Role
        fields = ['name', 'codename', 'descricao', 'permissions', 'pessoas', 'ativo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            # 'permissions' widget removed; using explicit field above
            'pessoas': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'codename': forms.TextInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # when editing, populate the checkbox field from the stored comma list
        if self.instance and self.instance.pk:
            perm_list = self.instance.perm_list()
            # ensure keystyle (already stored codes not including model prefix?)
            # stored values already look like 'empresa.edit' etc., so just use them
            self.initial['permissions'] = perm_list

        # add bootstrap classes for custom field widgets
        self.fields['permissions'].widget.attrs.update({'class': 'form-check'})
        self.fields['pessoas'].widget.attrs.update({'class': 'form-select', 'size': '6'})

    def clean_permissions(self):
        # the widget returns a list; store comma separated string
        perms = self.cleaned_data.get('permissions') or []
        return ','.join(perms)
