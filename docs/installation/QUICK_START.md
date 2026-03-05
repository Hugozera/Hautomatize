# 🚀 Quick Start - Interface Visual de Permissões

## 5 Minutos para Começar

### 1️⃣ Verificar Instalação

```bash
# Entrar no diretório do projeto
cd c:\Hautomatize

# Ativar ambiente Python
python -m venv venv
venv\Scripts\activate

# Verificar Django
python manage.py --version
```

### 2️⃣ Setup Inicial (Fazer uma única vez)

```bash
# Criar permissões e papéis
python manage.py setup_permissions --reset --assign-hugo-admin

# Esperado:
# ✅ Criando 5 papéis...
# ✅ Admin: 90 permissões
# ✅ Hugo atribuído como Admin
```

### 3️⃣ Acessar Interface

1. Abra: `http://localhost:8000/admin/`
2. Faça login com Hugo ou outro super user
3. Vá até: **Core > Pessoas**
4. Clique em **Adicionar Pessoa** ou edite uma existente

### 4️⃣ Usar Formulário

**Seção de Papéis (Roles)**
```
┌─ Admin ─┐
│ ✓ 90    │  ← Clique no card para selecionar
│ perms   │
└─────────┘
```

**Seção de Permissões**
```
🔍 Buscar permissão...    ← Digite para filtrar
[➕ Expandir All]

► Empresa               ← Clique para expandir
  ☑ Ver empresa
  ☑ Adicionar empresa
```

### 5️⃣ Salvar & Verificar

```bash
# Após salvar no formulário, verificar:
python manage.py check_permissions --user hugo_martins

# Esperado:
# ✅ Hugo Martins: 90 permissões, Papel Admin
```

---

## 📋 Tarefas Comuns

### Criar Novo Usuário

```bash
# Opção 1: Via formulário (recomendado)
http://localhost:8000/admin/core/pessoa/add/

# Opção 2: Via management command
python manage.py manage_user_permissions \
    --user novo_usuario \
    --add-role gestor
```

### Remover Permissão

```bash
python manage.py manage_user_permissions \
    --user usuario \
    --remove-perm download_nota
```

### Ver Permissões de Usuário

```bash
python manage.py check_permissions --user username
# or
python manage.py manage_user_permissions --user username --list-perms
```

### Ver Todos os Papéis

```bash
python manage.py check_permissions --role gestor
python manage.py check_permissions --role analista
# ... etc
```

---

## 🎯 Casos de Uso Rápidos

### Case 1: Gestor Comercial
```bash
# Papel: Gestor (já tem 52 permissões)
# Adicional: download_nota

python manage.py manage_user_permissions \
    --user gerente_01 \
    --add-role gestor \
    --add-perm download_nota
```

### Case 2: Operador Limitado
```bash
# Papel: Operador (21 permissões)
# Sem adicionais

python manage.py manage_user_permissions \
    --user operador_01 \
    --add-role operador
```

### Case 3: Visualizador Apenas
```bash
# Papel: Visualizador (21 permissões)

python manage.py manage_user_permissions \
    --user viewer_01 \
    --add-role visualizador
```

---

## 🔍 Troubleshooting Rápido

| Problema | Solução |
|----------|---------|
| CSS não carrega | `python manage.py collectstatic --noinput` |
| JavaScript erro | Verificar console (F12) |
| Permissões não salvam | Verificar se model tem campos 'roles' |
| Formulário lento | Aguarde (primeira carga é mais pesada) |
| Cards não aparecem | Certificar que roles foram criadas |

---

## 📊 Referência Rápida

### Hierarquia de Papéis
```
Admin (90)
├── Gestor (52)
├── Analista (28)
├── Operador (21)
└── Visualizador (21)
```

### 11 Módulos
```
1. empresa          6. painel
2. certificado      7. pessoa
3. nfse_downloader  8. role
4. nota_fiscal      9. agendamento
5. conversor        10. relatorio
                    11. sistema
```

---

## 🎓 Próximos Passos

1. ✅ **Hoje**: Setup inicial + criar 2-3 usuários
2. ✅ **Semana**: Testar todas features do formulário
3. ✅ **Próximo**: Integrar checks em views da aplicação

---

## 💡 Dicas Pro

✨ **Search Tip**: Digitar "nota" encontra "download_nota", "view_nfse", etc.

✨ **Bulk Tip**: Clicar "Expandir All" antes de atribuir para ver tudo de uma vez

✨ **Summary Tip**: Assistir badges atualizarem em tempo real = feedback visual perfeito

✨ **Mobile Tip**: Interface funciona perfeito em tablet e celular

---

## 🆘 Precisa de Ajuda?

### Documentação Completa
- `VISUAL_INTERFACE_README.md` - Interface detalhada
- `PERMISSIONS_DOCUMENTATION.md` - Sistema técnico
- `VISUAL_PERMISSION_EXAMPLES.py` - Exemplos de código

### Testes
- `VISUAL_FORM_TESTING.md` - Como validar tudo

### Perguntas via Python Shell
```python
python manage.py shell

from core.models import Pessoa
from core.permissions import check_perm

# Listar todos usuários
Pessoa.objects.values_list('user__username', flat=True)

# Verificar permissão específica
check_perm(user, 'view_empresa')
```

---

## ✅ Checklist de Primeiro Uso

- [ ] Executei `setup_permissions`
- [ ] Acessei formulário de pessoa
- [ ] Criei novo usuário
- [ ] Atribuí papel (role)
- [ ] Adicionei permissão direta
- [ ] Salvei formulário
- [ ] Verifiquei com management command
- [ ] Testei em mobile
- [ ] Funcionou! 🎉

---

**Pronto para começar? Vá para o admin agora!**

`http://localhost:8000/admin/core/pessoa/`

---

*Last Updated: 2024*
*Quick Start Version 1.0*
