# Sistema de Permissões - Guia Prático

## 📌 Início Rápido

### Usuário Principal
- **Email:** hugomartinscavalcante@gmail.com
- **Papel:** Admin ✅
- **Permissões:** TODAS (90)

### Adicionar Novo Usuário

```bash
# Via Django shell
python manage.py shell

from django.contrib.auth.models import User
from core.models import Pessoa, Role

# 1. Criar usuário
user = User.objects.create_user(
    username='joao',
    email='joao@example.com',
    first_name='João',
    last_name='Silva',
    password='senha123'
)

# 2. Criar Pessoa
pessoa = Pessoa.objects.create(user=user, cpf='12345678901')

# 3. Atribuir papel
role = Role.objects.get(codename='operador')
pessoa.roles.add(role)

# Sair
exit()
```

### Ou Use Management Command

```bash
# Criar e atribuir papel
python manage.py manage_user_permissions joao --add-role operador
```

---

## 🎯 Papéis Disponíveis

```
┌─────────────────────────────────────────────────────────────┐
│ ADMIN (90 perms)                                            │
│ └─> Acesso completo ao sistema                             │
├─────────────────────────────────────────────────────────────┤
│ GESTOR (52 perms)                                           │
│ └─> Gerencia: empresas, usuários, downloads, relatórios    │
├─────────────────────────────────────────────────────────────┤
│ ANALISTA (28 perms)                                         │
│ └─> Gerencia: atendimentos, visualiza dados                │
├─────────────────────────────────────────────────────────────┤
│ OPERADOR (21 perms)                                         │
│ └─> Executa: downloads, conversões, tarefas                │
├─────────────────────────────────────────────────────────────┤
│ VISUALIZADOR (21 perms)                                     │
│ └─> Apenas leitura (sem create/edit/delete)                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔧 Comandos Principais

### 1. Atribuir Papel

```bash
# Adicionar papel
python manage.py manage_user_permissions joao --add-role operador

# Remover papel
python manage.py manage_user_permissions joao --remove-role operador

# Definir múltiplos papéis (substitui todos)
python manage.py manage_user_permissions joao --set-roles operador,analista
```

### 2. Gerenciar Permissões Diretas

```bash
# Adicionar permissão direta
python manage.py manage_user_permissions joao --add-perm empresa.edit

# Remover permissão
python manage.py manage_user_permissions joao --remove-perm empresa.edit

# Listar todas
python manage.py manage_user_permissions joao --list-perms
```

### 3. Diagnosticar

```bash
# Status geral
python manage.py check_permissions

# Usuário específico
python manage.py check_permissions --user joao

# Papel específico
python manage.py check_permissions --role gestor

# Módulo específico
python manage.py check_permissions --module empresa
```

### 4. Reset

```bash
# Remover TODAS as permissões de um usuário
python manage.py manage_user_permissions joao --reset
```

---

## 🔐 Permissões por Módulo

### empresa
- `empresa.view` - Visualizar
- `empresa.list` - Listar
- `empresa.create` - Criar
- `empresa.edit` - Editar
- `empresa.delete` - Deletar
- `empresa.manage` - Gerenciar
- `empresa.assign_users` - Atribuir usuários
- `empresa.view_financeiro` - Ver financeiro

### certificado
- `certificado.view` - Visualizar
- `certificado.upload` - Upload
- `certificado.edit` - Editar
- `certificado.delete` - Deletar
- `certificado.manage` - Gerenciar
- `certificado.test` - Testar
- `certificado.export` - Exportar
- `certificado.renew` - Renovar

### conversor
- `conversor.view` - Visualizar
- `conversor.upload` - Upload
- `conversor.convert` - Converter
- `conversor.download` - Download
- `conversor.delete` - Deletar
- `conversor.use` - Usar
- `conversor.manage` - Gerenciar
- `conversor.view_historico` - Histórico

### nfse_downloader
- `nfse_downloader.view` - Visualizar
- `nfse_downloader.list_empresas` - Listar
- `nfse_downloader.download_manual` - Download manual
- `nfse_downloader.download_agendado` - Agendado
- `nfse_downloader.view_historico` - Histórico
- `nfse_downloader.export_dados` - Exportar

### painel
- `painel.view` - Visualizar
- `painel.list_atendimentos` - Listar
- `painel.create_atendimento` - Criar
- `painel.edit_atendimento` - Editar
- `painel.close_atendimento` - Fechar
- `painel.delete_atendimento` - Deletar
- `painel.view_relatorio` - Relatório
- `painel.manage_chat` - Chat
- `painel.assign_analista` - Atribuir analista
- `painel.manage` - Gerenciar

### pessoa (usuários)
- `pessoa.view` - Visualizar
- `pessoa.list` - Listar
- `pessoa.create` - Criar
- `pessoa.edit` - Editar outros
- `pessoa.edit_self` - Editar si mesmo
- `pessoa.delete` - Deletar
- `pessoa.manage` - Gerenciar
- `pessoa.edit_permissions` - Editar perms
- `pessoa.edit_roles` - Editar roles
- `pessoa.view_permissions` - Ver perms

### role (papéis)
- `role.view` - Visualizar
- `role.list` - Listar
- `role.create` - Criar
- `role.edit` - Editar
- `role.delete` - Deletar
- `role.manage` - Gerenciar
- `role.assign_users` - Atribuir users
- `role.edit_permissions` - Editar perms

### nota_fiscal
- `nota_fiscal.view` - Visualizar
- `nota_fiscal.list` - Listar
- `nota_fiscal.view_pdf` - Ver PDF
- `nota_fiscal.view_xml` - Ver XML
- `nota_fiscal.download` - Download
- `nota_fiscal.delete` - Deletar
- `nota_fiscal.manage` - Gerenciar
- `nota_fiscal.export` - Exportar

### agendamento
- `agendamento.view` - Visualizar
- `agendamento.list` - Listar
- `agendamento.create` - Criar
- `agendamento.edit` - Editar
- `agendamento.delete` - Deletar
- `agendamento.manage` - Gerenciar
- `agendamento.pause` - Pausar
- `agendamento.resume` - Retomar

### relatorio
- `relatorio.view` - Visualizar
- `relatorio.list` - Listar
- `relatorio.create` - Criar
- `relatorio.export` - Exportar
- `relatorio.schedule` - Agendar
- `relatorio.manage` - Gerenciar

### sistema
- `sistema.view_logs` - Ver logs
- `sistema.view_config` - Ver config
- `sistema.edit_config` - Editar config
- `sistema.manage_users` - Gerenciar users
- `sistema.manage_roles` - Gerenciar roles
- `sistema.manage_permissions` - Gerenciar perms
- `sistema.backup` - Backup
- `sistema.restore` - Restore
- `sistema.monitor` - Monitorar
- `sistema.admin` - Admin

---

## 💻 Usar em Views

### Python

```python
from django.contrib.auth.decorators import login_required
from core.permissions import check_perm, can_edit_empresa

@login_required
def minha_view(request):
    # Verificação 1: Permissão simples
    if not check_perm(request.user, 'empresa.edit'):
        return HttpResponseForbidden("Sem permissão")
    
    # Verificação 2: Função específica
    if not can_edit_empresa(request.user):
        return HttpResponseForbidden("Sem permissão")
    
    return render(request, 'template.html')
```

### Template

```html
{% if user.pessoa.has_perm_code 'empresa.edit' %}
    <button>Editar</button>
{% endif %}
```

---

## 🐛 Troubleshooting

### Usuário sem permissões esperadas

```bash
# Verificar
python manage.py manage_user_permissions joao --list-perms

# Se faltam, adicionar
python manage.py manage_user_permissions joao --add-role operador
```

### Papel não aparece em usuário

```bash
# Verificar se papel existe
python manage.py check_permissions --role operador

# Se não existir, criar via setup
python manage.py setup_permissions
```

### Hugo sem permissões

```bash
# Reset total
python manage.py setup_permissions --reset --assign-hugo-admin
```

---

## 📊 Exemplo de Setup

### Usuários totais

```bash
# Hugo (Admin) - já configurado
python manage.py check_permissions --user hugomartinscavalcante@gmail.com

# Adicionar gerentes
for user in gerente1 gerente2 gerente3; do
    python manage.py manage_user_permissions $user --add-role gestor
done

# Adicionar operadores
for user in operador1 operador2 operador3; do
    python manage.py manage_user_permissions $user --add-role operador
done

# Verificar status
python manage.py check_permissions
```

---

## ✅ Checklist de Setup

- [ ] Sistema inicializado: `python manage.py setup_permissions`
- [ ] Hugo com acesso total: `python manage.py check_permissions --user hugomartinscavalcante@gmail.com`
- [ ] Usuários adicionados com papéis apropriados
- [ ] Permissões extras adicionadas se necessário
- [ ] Verificado em views e templates
- [ ] Documentação lida e compreendida

---

## 📚 Documentos Relacionados

- [PERMISSIONS_DOCUMENTATION.md](PERMISSIONS_DOCUMENTATION.md) - Documentação completa
- [PERMISSIONS_EXAMPLES.py](PERMISSIONS_EXAMPLES.py) - Exemplos de código
- [PERMISSIONS_SETUP_SUMMARY.md](PERMISSIONS_SETUP_SUMMARY.md) - Resumo técnico
- [core/permission_system.py](core/permission_system.py) - Código central
- [core/permissions.py](core/permissions.py) - Funções helpers

---

## 🎯 Quick Stats

| Item | Valor |
|------|-------|
| Total de Permissões | 90 |
| Total de Módulos | 11 |
| Total de Papéis | 5 |
| Permissão mais alta: Admin | 90 perms |
| Permissão mais baixa: Visualizador | 21 perms |
| Usuário admin: Hugo | ID=1 ✅ |

---

**Última atualização:** 2026-03-03  
**Status:** ✅ Pronto para produção
