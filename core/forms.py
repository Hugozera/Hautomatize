from django import forms
from django.contrib.auth.models import User
from .models import Pessoa, Empresa, Agendamento

class PessoaForm(forms.ModelForm):
    username = forms.CharField(max_length=150, required=True, label='Usuário')
    first_name = forms.CharField(max_length=150, required=True, label='Nome')
    last_name = forms.CharField(max_length=150, required=True, label='Sobrenome')
    email = forms.EmailField(required=True, label='E-mail')
    password = forms.CharField(widget=forms.PasswordInput, required=False, label='Senha')
    password_confirm = forms.CharField(widget=forms.PasswordInput, required=False, label='Confirme a senha')

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
        else:
            self.fields['password'].required = True
            self.fields['password_confirm'].required = True

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
        
        if commit:
            pessoa.save()
        
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