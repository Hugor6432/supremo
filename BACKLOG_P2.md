# Backlog da P2: Reserva de Salas como mini-SaaS

Os quatro pilares da P2 divididos em tarefas.
Cada linha deve virar **uma issue no GitHub**, com o rótulo do pilar
(`multi-organizacao`, `perfis`, `api`, `dashboard`, `melhorias-p1`).
Nenhuma tarefa é maior do que uma sessão de trabalho.

## Pilar 1: Multi-organização · rótulo `multi-organizacao`

- [x] Criar app `core` com o model `Organizacao`
- [x] Criar a base abstrata `DaOrganizacao` e herdar em `Sala`, `Recurso`, `Recorrencia` e `Reserva`
- [x] Migração em 3 etapas (FK nula → organização padrão → FK obrigatória)
- [x] Model `Perfil` ligando `User` à `Organizacao`, registrado no Admin
- [x] Exigir login e filtrar todas as views por `org_atual(request)`
- [x] Filtrar os selects do `ReservaForm` (sala e recorrência) pela organização
- [x] Nome de sala único por organização (`UniqueConstraint`) com tratamento no `clean()` do form
- [x] Filtrar a API por organização (`get_queryset` e `perform_create`)
- [x] Rodar o roteiro de isolamento com dois usuários e anotar no README

## Pilar 2: Perfis de acesso · rótulo `perfis`

- [x] Campo `papel` no `Perfil` (administrador, operador e usuário)
- [x] Decidir o comportamento de usuário sem `Perfil` (continua recebendo 403 nas telas)
- [x] Restringir telas por papel (só operador e administrador gerenciam salas)
- [x] Restringir endpoints da API por papel (permissão customizada do DRF)
- [x] Mostrar ou esconder botões nos templates conforme o papel
- [x] Dono da reserva (`criado_por`), cancelamento com regra das 24 horas e aprovação opcional

## Pilar 3: API REST · rótulo `api`

- [x] Instalar o DRF e exigir autenticação (`IsAuthenticated`)
- [x] API de `Sala` (primeira API)
- [x] API de `Reserva`, `Recurso` e `Recorrencia`
- [ ] Mostrar o nome da sala na reserva (`StringRelatedField` ou serializer aninhado)
- [ ] Filtros na API (ex.: reservas por sala e por status)
- [ ] Testes automatizados da API

## Pilar 4: Dashboard · rótulo `dashboard`

- [x] Tela de dashboard com métricas da organização
- [x] Salas mais reservadas (`values` + `annotate(Count)`)
- [x] Reservas por status e reservas da semana
- [ ] Taxa de ocupação por sala

## Melhorias da P1 · rótulo `melhorias-p1`

- [ ] Itens listados em [MELHORIAS_P1.md](MELHORIAS_P1.md)
