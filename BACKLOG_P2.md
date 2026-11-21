# Backlog da P2: Reserva de Salas como mini-SaaS

Os quatro pilares da P2 divididos em tarefas, cada uma com o rótulo do pilar
(`multi-organizacao`, `perfis`, `api`, `dashboard`, `melhorias-p1`).

## Pilar 1: Multi-organização · `multi-organizacao`

- [x] App `core` com o model `Organizacao`
- [x] Base abstrata `DaOrganizacao` em `Sala`, `Recurso`, `Recorrencia` e `Reserva`
- [x] Migração em 3 etapas (FK nula → organização padrão → FK obrigatória)
- [x] `Perfil` ligando `User` à `Organizacao`
- [x] Login exigido e todas as views filtradas por `org_atual(request)`
- [x] Select de sala do formulário de reserva filtrado pela organização
- [x] Nome de sala único por organização
- [x] API filtrada por organização
- [x] Roteiro de isolamento executado e anotado no README

## Pilar 2: Perfis de acesso · `perfis`

- [x] Papéis administrador, funcionário (`operador`) e usuário
- [x] Usuário sem perfil recebe 403 nas telas
- [x] Telas restritas por papel
- [x] API restrita por papel (permissões do DRF)
- [x] Botões mostrados conforme o papel
- [x] Dono da reserva, regra das 24 horas e aprovação opcional
- [x] Usuário comum vê só as próprias reservas

## Pilar 3: API REST · `api`

- [x] DRF com autenticação obrigatória
- [x] API de `Sala`, `Reserva`, `Recurso` e `Recorrencia`
- [x] Testes automatizados da API
- [ ] Nome da sala na resposta da reserva (hoje vem só o id)
- [ ] Filtros na API (por sala e por status)

## Pilar 4: Dashboard · `dashboard`

- [x] Tela com as métricas da organização
- [x] Salas mais reservadas
- [x] Reservas por status e reservas da semana
- [ ] Taxa de ocupação por sala

## Melhorias da P1 · `melhorias-p1`

- [ ] Itens de [MELHORIAS_P1.md](MELHORIAS_P1.md): 1 corrigido, 3 em parte, 2 pendentes

## Feito além do backlog

- Tipo de usuário no Admin define o papel; cadastro público de conta
- Recursos cadastrados nas telas de sala; página de detalhes da sala
- Reservas recorrentes sem conflito, com cancelamento da série
- Exclusão registrada com restauração no Admin e histórico de atividades
- Exportação em CSV e API do dashboard
