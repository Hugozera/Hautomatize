# ⚡ QUICK REFERENCE - Permissões e Menu Dinâmico

## 🆘 Preciso fazer X, o que fazer?

### "Quero que só Admin veja um item no menu"
```python
# em core/menu_config.py
{
    'label': 'Admin Only',
    'permission': 'sistema.admin',  # ← Só admin tem isso
}
```

### "Quero proteger minha view"
```python
# em views.py
@login_required
def minha_view(request):
    if not can_fazer_algo(request.user):
        return HttpResponseForbidden("Acesso negado")
```

### "Quero mostrar botão só se tem permissão"
```django-html
{# em template #}
{% if request.user|has_perm:'modulo.acao' %}
    <button>Fazer algo</button>
{% endif %}
```

### "Quero adicionar novo submenu"
```python
# em core/menu_config.py
'empresa': [
    {
        'label': 'Empresas',
        'submenu': [
            {
                'label': 'Novo Subitem',
                'permission': 'empresa.view',
            }
        ]
    }
]
```

### "Quero criar novo papel"
```bash
# Terminal
python manage.py shell

>>> from core.models import Role
>>> role = Role.objects.create(
...     codename='meu_papel',
...     nome='Meu Papel'
... )
```

### "Quero atribuir papel a usuário"
```bash
python manage.py manage_user_permissions usuario --add-role meu_papel
```

### "Quero remover papel de usuário"
```bash
python manage.py manage_user_permissions usuario --remove-role meu_papel
```

### "Quero ver permissões de usuário"
```bash
python manage.py manage_user_permissions usuario --list-perms
```

---

## 🎨 Permissões Mais Comuns

```
empresa.view       - Ver empresas
empresa.list       - Listar todas
empresa.create     - Criar nova
empresa.edit       - Editar
empresa.delete     - Deletar
empresa.manage     - Controle total

certificado.upload - Fazer upload
certificado.manage - Controle total

nfse_downloader.download_manual - Download manual

conversor.use      - Usar conversor

painel.view        - Ver painel

pessoa.view        - Ver usuário
pessoa.create      - Criar usuário
person.manage      - Controle total usuários

sistema.admin      - Admin total
```

---

## 💻 Comandos Importantes

```bash
# Setup inicial (cria papéis e atribui Hugo)
python manage.py setup_permissions --reset

# Gerenciar user
python manage.py manage_user_permissions username --list-perms
python manage.py manage_user_permissions username --add-role operador
python manage.py manage_user_permissions username --remove-role operador

# Diagnosticar
python manage.py check_permissions
python manage.py check_permissions --user username
python manage.py check_permissions --role admin

# Testes
python manage.py test core.tests.test_menu_system --verbosity=2
python manage.py test core.tests.test_permissions --verbosity=2
```

---

## 📂 Arquivos Principais

| Arquivo | Qual Pacote |
|---------|---------|
| `core/permission_system.py` | Permissões + Papéis |
| `core/permissions.py` | Funções helper |
| `core/menu_config.py` | Menu config |
| `core/context_processors.py` | Context proc |
| `core/templatetags/menu_tags.py` | Template tags |
| `core/templates/core/tags/menu_items.html` | Template menu |

---

## 🎬 Demo Quick

```python
# 1. Verificar se user tem perm
from core.permissions import check_perm
check_perm(user, 'empresa.edit')  # → True/False

# 2. Usando função helper
from core.permissions import can_edit_empresa
can_edit_empresa(user)  # → True/False

# 3. Múltiplas perms (QUALQUER UMA)
from core.permissions import user_has_any_permission
user_has_any_permission(user, 'empresa.view', 'empresa.edit')  # → True se tem alguma

# 4. Múltiplas perms (TODAS)
from core.permissions import user_has_all_permissions
user_has_all_permissions(user, 'empresa.view', 'empresa.list')  # → True se tem todas

# 5. Em template
{% load menu_tags %}
{% if user|has_perm:'empresa.edit' %}
    <button>Editar</button>
{% endif %}

# 6. Obter todos os items do menu
from core.menu_config import get_menu_items
items = get_menu_items(user, pessoa)
```

---

## 🐛 Debug Rápido

```python
# Verificar permissões do user
user = User.objects.get(username='teste')
pessoa = user.pessoa
print(pessoa.get_all_permissions())  # Lista tudo

# Verificar papéis do user
print(pessoa.roles.all())  # User's roles

# Verificar se é superuser
print(user.is_superuser)  # True se admin

# Testar permissão específica
from core.permissions import check_perm
print(check_perm(user, 'empresa.edit'))  # Resultado
```

---

## ✅ Checklist Rápido

- [ ] Menu dinâmico funcionando?
- [ ] Login/logout funcionando?
- [ ] Admin vê tudo no menu?
- [ ] Operador vê só suas coisas?
- [ ] View protegida retorna 403 sem perm?
- [ ] Botão desaparece sem perm?
- [ ] Testes passando?

---

## 📖 Documentação Completa

| Doc | Assunto |
|-----|---------|
| `CAMADAS_PERMISSOES_RESUMO.md` | Visão geral do sistema |
| `MENU_DINAMICO_GUIA.md` | Como usar menu dinâmico |
| `VIEWS_PROTEGIDAS_EXEMPLOS.py` | Exemplos de views |
| `IMPLEMENTACAO_CHECKLIST.md` | O que fazer agora |
| `PERMISSIONS_DOCUMENTATION.md` | Permissões detalhadas |

---

## 🎯 Resumo em 1 Linha

**Você agora tem um sistema de permissões em 4 camadas pronto para usar: permissões granulares → papéis → menu dinâmico → views protegidas.**

---

Need help? Check the docs above! 📚
