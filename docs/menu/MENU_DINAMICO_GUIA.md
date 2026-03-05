# 📋 Sistema de Menu Dinâmico - Guia Completo

## 🎯 O que foi criado

Um sistema **100% configurável** de menu lateral que mostra APENAS o que o usuário pode fazer, baseado em suas permissões.

### Arquivos Criados:
1. **`core/menu_config.py`** - Configuração centralizada do menu
2. **`core/templatetags/menu_tags.py`** - Template tags para renderizar menu
3. **`core/context_processors.py`** - Context processor para passar dados ao template
4. **`core/templates/core/tags/menu_items.html`** - Template para renderizar items
5. **`nfse_downloader/settings.py`** - Atualizado com context processors

---

## 💡 Como Funciona

### 1. **Configuração Centralizada** (`menu_config.py`)

Define todos os itens do menu com suas permissões:

```python
MENU_CONFIG = {
    'empresa': [
        {
            'label': 'Empresas',
            'icon': 'bi-building',
            'url_name': 'empresa_list',
            'url_pattern': '/empresas',
            'permission': 'empresa.view',  # ← QUEM TEM ISSO VE O ITEM
            'submenu': [...]
        }
    ]
}
```

### 2. **Renderização Automática**

Adicionado ao `base.html`:

```django-html
{% load menu_tags %}
{% render_menu %}
```

Automaticamente mostra apenas items que o usuário tem permissão!

### 3. **Context Processor**

Adicionado ao `settings.py`:

```python
'core.context_processors.menu_context',  # Menu em template
'core.context_processors.permissions_context',  # Perms helper
```

Agora `{{ menu_items }}` está disponível em TODOS os templates.

---

## 🔧 Como Usar em Templates

### Verificar Permissão Simples

```django-html
{% load menu_tags %}

<!-- Template tag -->
{% if request.user|has_perm:'empresa.edit' %}
    <button>Editar Empresa</button>
{% endif %}

<!-- Ou mais semântico -->
{% if request.user|has_perm:'empresa.view' %}
    <a href="{% url 'empresa_list' %}">Ver Empresas</a>
{% endif %}
```

### Mostrar/Esconder Botões

```django-html
{# Listar #}
{% if request.user|has_perm:'empresa.list' %}
    <a href="{% url 'empresa_list' %}" class="btn btn-primary">Ver Todas</a>
{% endif %}

{# Criar #}
{% if request.user|has_perm:'empresa.create' %}
    <a href="{% url 'empresa_create' %}" class="btn btn-success">Criar Empresa</a>
{% endif %}

{# Editar #}
{% if request.user|has_perm:'empresa.edit' %}
    <button class="btn btn-warning">Editar</button>
{% endif %}

{# Deletar (mais restritivo) #}
{% if request.user|has_perm:'empresa.delete' %}
    <button class="btn btn-danger">Deletar</button>
{% endif %}
```

### Menus Contextuais

```django-html
<!-- Menu em detalhe de empresa -->
<div class="action-buttons">
    {% if request.user|has_perm:'empresa.edit' %}
        <a href="{% url 'empresa_edit' empresa.id %}" class="btn btn-sm btn-warning">✏️ Editar</a>
    {% endif %}
    
    {% if request.user|has_perm:'certificado.upload' %}
        <a href="{% url 'certificado_create' %}?empresa={{ empresa.id }}" class="btn btn-sm btn-info">📜 Upload Cert</a>
    {% endif %}
    
    {% if request.user|has_perm:'nfse_downloader.download_manual' %}
        <a href="{% url 'download_manual' %}?empresa={{ empresa.id }}" class="btn btn-sm btn-success">⬇️ Download</a>
    {% endif %}
    
    {% if request.user|has_perm:'empresa.delete' %}
        <a href="#delete-modal" class="btn btn-sm btn-danger">🗑️ Deletar</a>
    {% endif %}
</div>
```

---

## 🎨 Como Personalizar o Menu

### Adicionar Novo Item

No `menu_config.py`:

```python
MENU_CONFIG = {
    'meu_novo_modulo': [
        {
            'label': 'Novo Módulo',
            'icon': 'bi-star',  # Bootstrap Icons
            'url_name': 'novo_modulo_index',
            'url_pattern': '/novo-modulo',
            'permission': 'novo_modulo.view',
            'order': 85,
            'submenu': [
                {
                    'label': 'Ação 1',
                    'icon': 'bi-plus-circle',
                    'url_name': 'novo_modulo_criar',
                    'permission': 'novo_modulo.create',
                },
            ]
        }
    ]
}
```

O menu se atualiza automaticamente!

### Adicionar Novo Submenu

```python
'painel': [
    {
        'label': 'OS / Painel',
        'icon': 'bi-kanban',
        'permission': 'painel.view',
        'submenu': [
            # Novo subitem
            {
                'label': 'Filas de Atendimento',
                'icon': 'bi-diagram-2',
                'url_name': 'painel:filas',
                'permission': 'painel.manage_chat',  # Só veem quem tem isso
            },
        ]
    }
]
```

### Reordernar Menu

Cada item tem `'order'`:

```python
'order': 10,  # Principal
'order': 20,  # Empresas
'order': 30,  # Certificados
'order': 100, # Usuários (admin)
'order': 200, # Perfil (sempre no final)
```

---

## 🔒 Regras de Permissão

### Mostrar Item
- Usuário tem a permissão? **SIM** → Mostra
- Usuário é superuser? **SIM** → Mostra tudo
- `permission: None`? **SIM** → Mostra sempre

### Subitems
Se o item pai tem permissão, mas um subitem NÃO:
- Subitem é filtrado automaticamente
- Se NÃO tem nenhum subitem visível, o menu pai NÃO é mostrado

**Exemplo:**
```
User: Operador (não tem admin)
Painel
├─ Meu Painel ✅
├─ Dashboard ❌ (requer admin)
├─ Secretaria ✅
└─ Departamentos ❌ (requer admin)

Menu é mostrado porque tem pelo menos 1 subitem visível
```

---

## 📦 Permissões do Menu

### Módulo: Downloads
```
nfse_downloader.view            → Vê o item "Download Rápido"
nfse_downloader.view_historico  → Vê "Histórico"
agendamento.view                → Vê "Programar Downloads"
```

### Módulo: Empresas
```
empresa.view                    → Vê o item "Empresas"
empresa.list                    → Vê "Listar"
empresa.create                  → Vê "Criar Empresa"
```

### Módulo: Certificados
```
certificado.view                → Vê "Certificados"
certificado.upload              → Vê "Upload"
certificado.test                → Vê "Testar"
```

### Módulo: Painel (Atendimentos)
```
painel.view                     → Vê "OS / Painel"
painel.view_relatorio           → Vê "Dashboard/Relatórios"
painel.manage_chat              → Vê "Chat"
sistema.manage_users            → Vê "Departamentos"
```

### Módulo: Admin (Configurações)
```
pessoa.view                     → Vê "Usuários"
pessoa.create                   → Vê "Criar Usuário"
role.manage                     → Vê "Gerenciar Papéis"
sistema.view_config             → Vê "Configurações"
sistema.edit_config             → Vê "Editar Configurações"
```

---

## 📝 Exemplos de Uso em Views

### Proteger View + Mostrar no Menu

```python
from django.contrib.auth.decorators import login_required
from core.permissions import can_edit_empresa

@login_required
def editar_empresa(request, empresa_id):
    # Verificar permissão
    if not can_edit_empresa(request.user):
        return HttpResponseForbidden("Acesso negado")
    
    # ... resto da view
```

O item "Editar" aparece no menu só se:
1. Usuário está logado
2. Tem permissão `empresa.edit` (direto ou via role)

---

## 🚀 Checklist de Implementação

- ✅ Menu dinâmico criado
- ✅ Context processor adicionado ao settings
- ✅ Template tag criado
- ✅ base.html atualizado
- ✅ Documentação ✓
- [ ] Testar com diferentes papéis
- [ ] Testar com usuário admin
- [ ] Testar com usuário operador
- [ ] Testar com usuário visualizador

---

## 🐛 Troubleshooting

### Menu não aparece
```
✓ Verificar: user.is_authenticated?
✓ Verificar: Pessoa associada ao User?
✓ Verificar: Permissões do usuário?
```

### Subitem desaparece
```
✓ Verificar: Pai tem permissão principal
✓ Verificar: Subitem tem permissão?
✓ Se nenhum subitem visível, pai some
```

### URL não funciona
```
✓ Verificar: url_name existe em urls.py?
✓ Verificar: app:nome (ex: painel:index)?
✓ Deixar template tag detectar automaticamente
```

---

## 📚 Referência Rápida

| Onde Usar | Como | Exemplo |
|-----------|------|---------|
| Template | `\|has_perm` | `{% if user\|has_perm:'empresa.edit' %}` |
| Template | `\|has_perm` em loop | `{% for item in items %}{% if user\|has_perm:item.perm %}` |
| Python | `check_perm()` | `check_perm(user, 'empresa.edit')` |
| Python | Função helper | `can_edit_empresa(user)` |
| Menu | Config de permissão | `'permission': 'empresa.edit'` |
| Menu | Sem permissão | `'permission': None` |

---

## ✨ Vantagens do Sistema

✅ **Segurança**: Usuário vê APENAS o que pode fazer
✅ **UX Melhorada**: Sem botões desabilitados, sem "acesso negado"
✅ **Escalável**: Adicionar módulo = adicionar à config
✅ **Flexível**: Fácil mudar ordem, icones, labels
✅ **Manutenível**: Tudo em um lugar (menu_config.py)
✅ **Testável**: Menu é gerado deterministically
✅ **Performático**: Cache de menu por papel

---

Qualquer dúvida, refira-se aos exemplos acima ou aos arquivos criados! 🚀
