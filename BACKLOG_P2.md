# Backlog da P2: Reserva de Salas como mini-SaaS

Os quatro pilares da P2 divididos em tarefas, como pedido na Aula 13.
Cada linha deve virar **uma issue no GitHub**, com o rótulo do pilar
(`multi-organizacao`, `perfis`, `api`, `dashboard`, `melhorias-p1`).
Nenhuma tarefa é maior do que uma sessão de aula.

## Pilar 1: Multi-organização (Aula 14) · rótulo `multi-organizacao`

- [ ] Criar app `core` com o model `Organizacao`
- [ ] Criar a base abstrata `DaOrganizacao` e herdar em `Sala`, `Recurso`, `Recorrencia` e `Reserva`
- [ ] Migração em 3 etapas (FK nula → organização padrão → FK obrigatória)
- [ ] Model `Perfil` ligando `User` à `Organizacao`, registrado no Admin
- [ ] Exigir login e filtrar todas as views por `org_atual(request)`
- [ ] Filtrar os selects do `ReservaForm` (sala e recorrência) pela organização
- [ ] Nome de sala único por organização (`UniqueConstraint`) com tratamento no `clean()` do form
- [ ] Filtrar a API por organização (`get_queryset` e `perform_create`)
- [ ] Rodar o roteiro de isolamento com dois usuários e anotar no README

## Pilar 2: Perfis de acesso (Aula 15) · rótulo `perfis`

- [ ] Campo `papel` no `Perfil` (administrador e operador)
- [ ] Decidir o comportamento de usuário sem `Perfil`
- [ ] Restringir telas por papel (ex.: só administrador cria, edita e apaga salas)
- [ ] Restringir endpoints da API por papel (permissão customizada do DRF)
- [ ] Mostrar ou esconder botões nos templates conforme o papel

## Pilar 3: API REST (Aula 16) · rótulo `api`

- [x] Instalar o DRF e exigir autenticação (`IsAuthenticated`)
- [x] API de `Sala` (primeira API da Aula 13)
- [x] API de `Reserva`, `Recurso` e `Recorrencia` (tarefa de casa da Aula 13)
- [ ] Mostrar o nome da sala na reserva (`StringRelatedField` ou serializer aninhado)
- [ ] Filtros na API (ex.: reservas por sala e por status)
- [ ] Testes automatizados da API

## Pilar 4: Dashboard (Aula 17) · rótulo `dashboard`

- [ ] Tela de dashboard com métricas da organização
- [ ] Salas mais reservadas (`values` + `annotate(Count)`)
- [ ] Reservas por status e reservas da semana
- [ ] Taxa de ocupação por sala

## Melhorias da P1 · rótulo `melhorias-p1`

- [ ] Itens listados em [MELHORIAS_P1.md](MELHORIAS_P1.md)
