# TODO — Plano de trabalho

Resumo das tarefas pedidas pelo usuário, com status e prioridades.

## Sprint 1 — Autenticação & UI (em andamento)
- [x] Corrigir logout (agora `views.logout_view`) — status: feito
- [x] Perfil: mostrar dados completos do próprio usuário; redirecionar para cadastro se `Pessoa` ausente — status: feito
- [x] Validar upload de foto (tamanho/formato) em `PessoaForm` — status: feito
- [x] Sidebar: quando fechado mostrar apenas a letra `H`; corrigir overflow quando aberto — status: feito
- [x] Testes automatizados básicos (check_pages) — status: feito

## Sprint 2 — Empresa (CNPJ/CEP automation)
- [x] Auto-preenchimento por CNPJ (consulta Receita) — implementado (cache em memória)
- [x] API ViaCEP para preencher endereço por CEP — implementado (`/api/cep/`)
- [x] Integração UI: buscar por CNPJ/CEP no formulário de empresa — implementado (auto-fetch on blur)

## Sprint 3 — Certificados
- [x] Listar certificados (fallback seguro) — status: feito
- [x] Mostrar empresa dona de um certificado (AJAX) — status: feito (endpoint `certificados/info/`)
- [x] CRUD básico para certificados (upload, salvar, remover, baixar) — status: feito; resta mapear permissões completas e adicionar testes adicionais

## Sprint 4 — Conversor / DataLearn
- [x] DataLearn básico (layouts bancários ao converter PDF→OFX) — status: feito
- [ ] Conversor assíncrono (fila/Celery) + progresso real — implementar
- [x] Conversor bulk (múltiplos arquivos) — implementado
- [ ] Melhorar cobertura de formatos (LibreOffice, ImageMagick, PIL) — implementar

## Sprint 5 — Dashboards & Relatórios
- [ ] Dashboard geral com últimos downloads e links para re-download — implementar
- [ ] Dashboard por empresa (parser de XMLs) — implementar

## Permissões, CRUD e Segurança
- [x] Mapear permissões por recurso (Pessoa, Empresa, Certificado, Conversor) — implementado (ver `core/permissions.py`, tags `core.templatetags.permissions_tags` e validações nas views)
- [ ] Testes de autorização — implementar

## Notas / Observações
- Dependências a considerar: LibreOffice (soffice), OpenSSL, Celery + Redis (para filas)
- Migrações: `LayoutBancario` e `ArquivoConversao` já adicionados

---
Prioridade imediata: completar automação de criação/edição de empresa (CNPJ/CEP) e CRUD/permssões.  
Quer que eu continue agora com: (A) CNPJ+CEP automatizado ou (B) continuar UI/Auth+permissões?  
Responda A ou B ou diga outro item.