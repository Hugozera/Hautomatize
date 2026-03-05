# Sistema de Permissões - Documentação

## 📋 Visão Geral

O sistema de permissões foi reconstruído com uma arquitetura **modular e escalável**. As permissões são organizadas em:

1. **Módulos**: Componentes principais do sistema (empresa, certificado, conversor, etc.)
2. **Operações**: Ações dentro de cada módulo (view, edit, delete, create, manage, etc.)
3. **Papéis (Roles)**: Combinações pré-definidas de permissões para usuários
4. **Pessoas**: Usuários que podem ter permissões diretas e/ou papéis

---

## 🏗️ Arquitetura

### Estrutura de Permissão

```
permissão = "modulo.operacao"

Exemplos:
- empresa.view          → visualizar empresas
- empresa.edit          → editar empresas
- certificado.manage    → gerenciar certificados
- conversor.use         → usar conversor
- nota_fiscal.download  → baixar notas fiscais
```

### Módulos Principais

| Módulo | Descrição | Permissões |
|--------|-----------|-----------|
| `nfse_downloader` | Download de notas fiscais | view, list_empresas, download_manual, view_historico, export_dados |
| `empresa` | Gestão de empresas | view, list, create, edit, delete, manage, assign_users, view_financeiro |
| `certificado` | Gestão de certificados | view, upload, edit, delete, manage, test, export, renew |
| `conversor` | Conversão de arquivos | view, upload, convert, download, delete, use, manage, view_historico |
| `nota_fiscal` | Nota fiscal | view, list, view_pdf, view_xml, download, delete, manage, export |
| `painel` | Painel de atendimento | view, list_atendimentos, create_atendimento, edit_atendimento, close_atendimento, view_relatorio, manage_chat, assign_analista, manage |
| `pessoa` | Gestão de usuários | view, list, create, edit, edit_self, delete, manage, edit_permissions, edit_roles, view_permissions |
| `role` | Gestão de papéis | view, list, create, edit, delete, manage, assign_users, edit_permissions |
| `agendamento` | Agendamentos | view, list, create, edit, delete, manage, pause, resume |
| `relatorio` | Relatórios | view, list, create, export, schedule, manage |
| `sistema` | Administração | view_logs, view_config, edit_config, manage_users, manage_roles, manage_permissions, backup, restore, monitor, admin |

---

## 👤 Papéis Pré-definidos

### 1. **Admin** 
- Acesso total ao sistema
- Pode gerenciar todos os módulos, usuários e configurações
- Todas as 100+ permissões

### 2. **Gestor**
- Gerencia empresas, usuários, downloads e relatórios
- Sem acesso a configurações do sistema
- ~60 permissões

### 3. **Analista**
- Gerencia atendimentos (painel)
- Visualiza empresas e dados
- Sem permissão para editar configs ou deletar
- ~40 permissões

### 4. **Operador**
- Executa downloads, conversões e tarefas operacionais
- Sem permissão para editar configurações
- ~30 permissões

### 5. **Visualizador**
- Apenas leitura de dados
- Sem permissão para criar, editar ou deletar
- ~15 permissões

---

## 🚀 Como Usar

### 1. Inicializar o Sistema

```bash
# Cria todos os papéis e atribui permissões ao Hugo (id=1)
python manage.py setup_permissions

# Com verbose:
python manage.py setup_permissions --verbose-perms

# Reset + recriação (cuidado!):
python manage.py setup_permissions --reset
```

### 2. Gerenciar Permissões de Usuários

```bash
# Listar permissões de um usuário
python manage.py manage_user_permissions hugomartinscavalcante --list-perms

# Adicionar papél a um usuário
python manage.py manage_user_permissions joao --add-role gestor

# Remover papel
python manage.py manage_user_permissions joao --remove-role gestor

# Definir múltiplos papéis (substitui todos)
python manage.py manage_user_permissions joao --set-roles analista,operador

# Adicionar permissão direta a um usuário
python manage.py manage_user_permissions joao --add-perm empresa.edit

# Remover permissão direta
python manage.py manage_user_permissions joao --remove-perm empresa.edit

# Reset total (remove tudo)
python manage.py manage_user_permissions joao --reset
```

### 3. Diagnosticar Permissões

```bash
# Resumo geral do sistema
python manage.py check_permissions

# Diagnosticar usuário específico
python manage.py check_permissions --user hugomartinscavalcante

# Ver detalhes de um papel
python manage.py check_permissions --role admin

# Ver permissões de um módulo
python manage.py check_permissions --module empresa
```

---

## 💻 Usando em Views e Templates

### Verificar Permissões em Python

```python
from core.permissions import (
    check_perm,
    can_view_empresa,
    can_edit_empresa,
    can_manage_certificado,
    get_user_permissions,
)

# Verificar permissão simples
if check_perm(request.user, 'empresa.edit'):
    # fazer algo

# Usar função específica
if can_edit_empresa(request.user):
    # permitir edição

# Obter todas as permissões
perms = get_user_permissions(request.user)
print(f"Usuário tem {len(perms)} permissões")
```

### Decoradores em Views

```python
from django.contrib.auth.decorators import login_required
from core.permissions import check_perm
from django.http import HttpResponseForbidden

def view_empresas(request):
    if not check_perm(request.user, 'empresa.view'):
        return HttpResponseForbidden()
    # seu código aqui
```

### Verificar em Templates

```html
{% if user.is_authenticated %}
    {% if user.pessoa.has_perm_code 'empresa.edit' %}
        <button>Editar Empresa</button>
    {% endif %}
{% endif %}
```

---

## 📊 Modelos de Dados

### Role (Papel)

```python
class Role(models.Model):
    name = CharField()                          # Ex: "Administrador"
    codename = CharField(unique=True)           # Ex: "admin"
    descricao = TextField()                     # Descrição do papel
    permissions = TextField()                   # Permissões separadas por vírgula
    pessoas = ManyToManyField(Pessoa)          # Usuários com este papel
    ativo = BooleanField(default=True)
    criado_em = DateTimeField(auto_now_add=True)
```

### Pessoa (Usuário)

```python
class Pessoa(models.Model):
    user = OneToOneField(User)
    cpf = CharField()
    telefone = CharField()
    foto = ImageField()
    ativo = BooleanField()
    
    # Permissões
    permissions = TextField()                  # Permissões diretas
    roles = ManyToManyField(Role)              # Papéis atribuídos
    
    def perm_list(self):
        """Retorna todas as permissões (diretas + via roles)"""
        
    def has_perm_code(self, code):
        """Verifica se tem uma permissão específica"""
```

---

## 🔐 Usuário Principal (Hugo)

### Configuração Pré-estabelecida

- **Username**: hugomartinscavalcante
- **ID**: 1 (no banco de dados)
- **Papéis**: Admin
- **Permissões**: **TODAS** (100+ permissões)

### Primeira Execução

```bash
# Se Hugo não existir, será criado automaticamente
python manage.py setup_permissions --assign-hugo-admin

# Verificar:
python manage.py check_permissions --user hugomartinscavalcante
```

---

## 🛠️ Adicionando Novos Usuários

### Opção 1: Via Django Admin

1. Criar usuário em `/admin/auth/user/`
2. Criar objeto Pessoa vinculado
3. Atribuir papéis ou permissões

### Opção 2: Via Management Command

```bash
# Criar usuário e atribuir papéis
python manage.py manage_user_permissions novo_usuario --add-role operador
```

### Opção 3: Via Django Shell

```python
from django.contrib.auth.models import User
from core.models import Pessoa, Role

# Criar usuário
user = User.objects.create_user(
    username='joao',
    email='joao@example.com',
    first_name='João',
    last_name='Silva'
)

# Criar Pessoa
pessoa = Pessoa.objects.create(
    user=user,
    cpf='12345678901',
    ativo=True
)

# Atribuir papel
role = Role.objects.get(codename='operador')
pessoa.roles.add(role)
```

---

## 📝 Estrutura de Permissões Detalhada

### Módulo: NFSE Downloader

| Permissão | Descrição |
|-----------|-----------|
| `nfse_downloader.view` | Pode visualizar dashboard do downloader |
| `nfse_downloader.list_empresas` | Pode listar empresas |
| `nfse_downloader.download_manual` | Pode executar downloads manuais |
| `nfse_downloader.download_agendado` | Pode acionar downloads agendados |
| `nfse_downloader.view_historico` | Pode visualizar histórico de downloads |
| `nfse_downloader.export_dados` | Pode exportar dados de downloads |

### Módulo: Empresa

| Permissão | Descrição |
|-----------|-----------|
| `empresa.view` | Pode visualizar dados da empresa |
| `empresa.list` | Pode listar todas as empresas |
| `empresa.create` | Pode criar nova empresa |
| `empresa.edit` | Pode editar dados da empresa |
| `empresa.delete` | Pode deletar empresa |
| `empresa.manage` | Pode gerenciar empresa (completo) |
| `empresa.assign_users` | Pode atribuir usuários à empresa |
| `empresa.view_financeiro` | Pode visualizar dados financeiros |

### Módulo: Certificado

| Permissão | Descrição |
|-----------|-----------|
| `certificado.view` | Pode visualizar certificados |
| `certificado.upload` | Pode fazer upload de certificado |
| `certificado.edit` | Pode editar dados do certificado |
| `certificado.delete` | Pode deletar certificado |
| `certificado.manage` | Pode gerenciar certificados (completo) |
| `certificado.test` | Pode testar certificado |
| `certificado.export` | Pode exportar certificado |
| `certificado.renew` | Pode renovar certificado |

### Módulo: Conversor

| Permissão | Descrição |
|-----------|-----------|
| `conversor.view` | Pode visualizar conversor |
| `conversor.upload` | Pode fazer upload de arquivo |
| `conversor.convert` | Pode executar conversão |
| `conversor.download` | Pode baixar arquivo convertido |
| `conversor.delete` | Pode deletar conversão |
| `conversor.use` | Pode usar conversor (geral) |
| `conversor.manage` | Pode gerenciar conversões (completo) |
| `conversor.view_historico` | Pode visualizar histórico de conversões |

---

## 🔗 Hierarquia de Permissões

A permissão `manage` geralmente implica acesso completo a um módulo:
- `empresa.manage` → pode fazer tudo com empresas
- `certificado.manage` → pode fazer tudo com certificados
- `sistema.admin` → acesso administrativo completo

---

## 🐛 Troubleshooting

### Usuário sem permissões mesmo após atribuir papel

**Solução**: Limpar cache ou recarregar página.

```bash
# Verificar permissões:
python manage.py manage_user_permissions username --list-perms

# Reset e reassign:
python manage.py manage_user_permissions username --reset
python manage.py manage_user_permissions username --add-role admin
```

### Hugo sem permissões na primeira vez

**Solução**: Executar setup novamente:

```bash
python manage.py setup_permissions --reset --assign-hugo-admin
```

### Papel não aparece em um usuário

**Solução**: Confirmar que o papel existe e está ativo:

```bash
python manage.py check_permissions --role admin
```

---

## 📚 Arquivos Principais

- **`core/permission_system.py`** - Definição centralizada de permissões e papéis
- **`core/permissions.py`** - Funções helper para verificação de permissões
- **`core/models.py`** - Modelos `Pessoa` e `Role`
- **`core/management/commands/setup_permissions.py`** - Inicializar sistema
- **`core/management/commands/manage_user_permissions.py`** - Gerenciar usuários
- **`core/management/commands/check_permissions.py`** - Diagnosticar permissões

---

## 🎯 Próximas Etapas

1. ✅ Sistema de permissões implementado
2. ⏳ Adicionar verificações de permissão em todas as views
3. ⏳ Adicionar filtros de permissão em templates
4. ⏳ Criar interface de gerenciamento de permissões no Django Admin
5. ⏳ Adicionar logs de auditoria para alterações de permissões
6. ⏳ Documentação de permissões em cada view

---

## 📞 Suporte

Para mais informações sobre o sistema de permissões, consulte:
- `core/permission_system.py` - Definições
- `core/permissions.py` - Funções helper
- Django shell: `python manage.py shell`

```python
from core.permission_system import print_permission_map, print_role_map
print_permission_map()  # Ver todas as permissões
print_role_map()        # Ver todos os papéis
```
