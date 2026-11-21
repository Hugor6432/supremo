# Reserva de Salas: de MVP (P1) a mini-SaaS (P2)

**Disciplina:** Laboratório de Programação Full Stack, Prof. Márcio Garrido

Sistema para cadastrar salas e marcar reservas nelas. A P1 está descrita em
[RELATORIO_P1.md](RELATORIO_P1.md) e os comandos para rodar no Windows estão em
[README_WINDOWS.md](README_WINDOWS.md).

- Melhorias pendentes da P1: [MELHORIAS_P1.md](MELHORIAS_P1.md)
- Backlog da P2: [BACKLOG_P2.md](BACKLOG_P2.md)

---

## API REST com Django REST Framework

A API fica em `/api/` e exige login (`IsAuthenticated`, autenticação por sessão do Django).
Para entrar pela Browsable API, use o link "Log in" no canto da página (`/api-auth/login/`).

| Recurso | Listar / criar | Detalhar / atualizar / apagar |
|---|---|---|
| Salas | `GET` `POST` `/api/salas/` | `GET` `PUT` `PATCH` `DELETE` `/api/salas/<id>/` |
| Reservas | `GET` `POST` `/api/reservas/` | `GET` `PUT` `PATCH` `DELETE` `/api/reservas/<id>/` |
| Recursos | `GET` `POST` `/api/recursos/` | `GET` `PUT` `PATCH` `DELETE` `/api/recursos/<id>/` |
| Recorrências | `GET` `POST` `/api/recorrencias/` | `GET` `PUT` `PATCH` `DELETE` `/api/recorrencias/<id>/` |

Ações de reserva (`POST`): `/api/reservas/<id>/cancelar/`, `/api/reservas/<id>/aprovar/` e
`/api/reservas/<id>/recusar/`. Os campos `status` e `criado_por` são só leitura.

Dashboard (`GET`): `/api/dashboard/?inicio=AAAA-MM-DD&fim=AAAA-MM-DD` (veja a seção Dashboard).

Arquivos: `salas/serializers.py`, `salas/api_views.py` e `salas/api_urls.py`.

Validações da API (respondem `400` com a mensagem em JSON):

- Reserva: término depois do início (mesma regra da Feature 2) e conflito de horário (reaproveita `Reserva.tem_conflito()`).
- Sala: capacidade maior que zero e nome único dentro da organização.
- Recorrência: intervalo de pelo menos 1 e data de fim que não seja antes do início.

---

## Multi-organização (coluna discriminadora)

Cada organização usa o mesmo sistema e o mesmo banco, mas enxerga **só os seus dados**.

**Como foi feito**

- App `core` com `Organizacao`, a base abstrata `DaOrganizacao` (FK `organizacao`) e o `Perfil`
  (liga o `User` à organização).
- `Sala`, `Recurso`, `Recorrencia` e `Reserva` herdam de `DaOrganizacao`.
- Migração em 3 etapas, sem perder os dados da P1:
  1. `0002_organizacao_nula`: FK com `null=True`
  2. `0003_dados_org`: `RunPython` coloca tudo na **"Organização padrão"**
  3. `0004_organizacao_obrigatoria`: FK passa a ser obrigatória
- `0005_sala_nome_unico_por_org`: nome de sala único **por organização** (`UniqueConstraint`),
  tratado no `clean_nome()` do `SalaForm` para não estourar `IntegrityError`.
- `core/utils.py` → `org_atual(request)`: o único lugar que define a organização do usuário.
- Todas as views têm `@login_required`, todas as consultas usam `filter(organizacao=org)` e todo
  `get_object_or_404` recebe `organizacao=org`. Ao criar, `commit=False` grava a organização do usuário.
- Os selects de sala e recorrência do `ReservaForm` só mostram opções da organização.
- Na API: `get_queryset()` filtra, `perform_create()` grava a organização do usuário, e
  `organizacao` não está nos `fields` do serializer.
- **Usuário sem Perfil** (ex.: o superusuário do `createsuperuser`) recebe uma página **403**
  em vez de erro 500. Ele continua usando só o Admin (decisão mantida nos perfis de acesso).

**Antes de migrar o seu banco:** faça uma cópia do `db.sqlite3` (backup) e depois rode
`python manage.py migrate`. Os dados que já existiam vão para a "Organização padrão".

**Como cadastrar organizações e usuários (pelo Admin)**

1. Entre em `/admin/` com o superusuário.
2. Em **Organizações**, crie duas, por exemplo "Escola Alfa" e "Empresa Beta".
3. Em **Usuários**, crie um usuário para cada uma. Na tela de edição do usuário, preencha
   **Organização do usuário** (é o Perfil).
4. Entre no site (`/contas/login/`) com cada usuário e rode o roteiro abaixo.

### Roteiro de isolamento: resultado

Executado em 10/11/2026 com duas organizações (**Escola Alfa**, usuário `ana`, e **Empresa Beta**,
usuário `bruno`) e um superusuário sem Perfil. **25 de 25 verificações passaram.**

| # | Cenário | Esperado | Resultado |
|---|---|---|---|
| 1 | Sem login, abrir `/salas/` | Redireciona para o login | ✅ |
| 2 | Ana abre a lista de salas | Vê só as salas da Alfa | ✅ |
| 3 | Filtro de recursos da lista de salas da Ana | Só recursos da Alfa | ✅ |
| 4 | Ana abre `/salas/ID-da-Beta/editar/` | 404 | ✅ |
| 5 | Ana tenta apagar uma sala da Beta | 404, sala continua existindo | ✅ |
| 6 | Ana abre `/reservas/ID-da-Beta/` | 404 | ✅ |
| 7 | Ana abre `/reservas/ID-da-Beta/editar/` | 404 | ✅ |
| 8 | Ana abre a lista de reservas | Não aparece reserva da Beta | ✅ |
| 9 | Ana cria uma sala | Gravada na Alfa | ✅ |
| 10 | Formulário de reserva da Ana | Selects só com salas e recorrências da Alfa | ✅ |
| 11 | Ana envia POST forjado com o ID de uma sala da Beta | Recusado pelo formulário | ✅ |
| 12 | Ana cria uma reserva | Gravada na Alfa | ✅ |
| 13 | Ana cadastra uma sala com o mesmo nome de uma sala da Beta | Permitido (unicidade por organização) | ✅ |
| 14 | Ana repete o nome de uma sala da própria Alfa | Mensagem de erro no formulário | ✅ |
| 15 | Superusuário sem Perfil abre `/salas/` | 403 (não quebra) | ✅ |
| 16 | Superusuário no Admin | Vê todas as organizações | ✅ |
| 17 | API sem login | 403 | ✅ |
| 18 | API: Ana lista salas | Só salas da Alfa | ✅ |
| 19 | API: Ana pede `/api/salas/ID-da-Beta/` | 404 | ✅ |
| 20 | API: Ana tenta apagar reserva da Beta | 404, reserva continua existindo | ✅ |
| 21 | API: Ana lista reservas, recursos e recorrências | Só os da Alfa | ✅ |
| 22 | API: Ana cria sala mandando `"organizacao": <id da Beta>` | Ignorado, gravada na Alfa | ✅ |
| 23 | API: Ana cria reserva com sala da Beta | 400 | ✅ |
| 24 | API: Ana cria recurso na sua sala | Gravado na Alfa | ✅ |
| 25 | API: superusuário sem Perfil | 403 | ✅ |

### Revisão de views e templates

- `salas/views.py`: todas as views exigem login e filtram pela organização.
- `salas/forms.py`: os selects `sala` e `recorrencia` e a checagem de nome duplicado filtram pela organização.
- `salas/api_views.py` e `salas/serializers.py`: listagem, detalhe, criação e campos de relacionamento filtram pela organização.
- `salas/models.py`: `tem_conflito()` compara só reservas da mesma organização e da mesma sala.
- Templates: as únicas consultas são `sala.recursos.all` e `reserva.tem_conflito`, sempre a partir
  de uma sala ou reserva que já veio filtrada pela organização. Nenhuma consulta solta.
- Admin: o superusuário vê tudo, com coluna e filtro por organização. Recursos e reservas criados
  no Admin herdam a organização da sala.

---

## Perfis de acesso

Cada `Perfil` tem um **papel**: `administrador`, `operador` ou `usuario` (padrão: `usuario`).
A migração `core/0002_perfil_papel` transformou os perfis que já existiam em `administrador`.
O papel é escolhido no Admin, na parte **Organização do usuário** da tela do usuário.

| Ação | Usuário | Operador | Administrador |
|---|:---:|:---:|:---:|
| Ver salas e reservas da própria organização | ✅ | ✅ | ✅ |
| Criar reserva | ✅ | ✅ | ✅ |
| Editar / cancelar as **próprias** reservas | ✅ só com mais de 24h | ✅ | ✅ |
| Editar / cancelar reservas de **outras pessoas** | ❌ | ✅ | ✅ |
| Aprovar / recusar reservas pendentes | ❌ | ✅ | ✅ |
| Apagar reserva de vez | ❌ | ✅ | ✅ |
| Criar / editar / apagar salas | ❌ | ✅ | ✅ |
| Escrever em recursos e recorrências pela API | ❌ | ✅ | ✅ |

Quem não pode recebe **403**. A regra das 24 horas aparece como mensagem de erro no formulário
(na API, `403` com a mensagem). Os botões que o papel não pode usar ficam escondidos.

**Como foi feito**

- `core/utils.py`: `papel_atual`, `eh_operador`, `eh_administrador` e `exige_operador` (403).
- `core/context_processors.py`: deixa `papel` e `eh_operador` disponíveis em todos os templates.
- `Reserva.criado_por` (FK para `User`, nula nas reservas antigas) é preenchido com o usuário logado,
  no site e na API. Não aparece no formulário.
- As regras ficam no model: `Reserva.pode_mexer(user)` (dono ou operador) e
  `Reserva.pode_alterar(user)` (mais a regra das 24h). Telas e API usam os mesmos métodos.
- API: `salas/permissoes.py` com `EhOperadorParaEscrita` e `PodeAlterarReserva` (permissões do DRF).

**Status automático e aprovação**

- O status não é mais escolhido no formulário. A reserva nasce **confirmada**.
- Se a sala tiver **Exige aprovação** (`Sala.exige_aprovacao`, padrão desligado), a reserva nasce
  **pendente** e o operador vê os botões **Aprovar** (vira confirmada) e **Recusar** (vira cancelada).
- **Cancelar** muda o status para `cancelada`, sem apagar. Reservas canceladas não bloqueiam o
  horário: `tem_conflito()` só compara reservas pendentes e confirmadas.

### Testes automatizados: resultado

`python manage.py check` e `python manage.py makemigrations --check` sem pendências.
`python manage.py test salas` roda num banco de teste separado. **23 de 23 testes passaram.**

| # | Cenário | Esperado | Resultado |
|---|---|---|---|
| 1 | Usuário cria, edita ou apaga sala | 403 | ✅ |
| 2 | Operador e administrador criam sala | Sala criada | ✅ |
| 3 | Botão "Nova Sala" para usuário / operador | Escondido / visível | ✅ |
| 4 | Reserva em sala comum | Nasce confirmada, com `criado_por` | ✅ |
| 5 | POST forjado com `status=cancelada` | Ignorado | ✅ |
| 6 | Reserva em sala com aprovação | Nasce pendente; usuário não aprova (403); operador aprova | ✅ |
| 7 | Operador recusa reserva pendente | Vira cancelada | ✅ |
| 8 | Usuário cancela a própria reserva com mais de 24h | Cancelada (não apagada) | ✅ |
| 9 | Usuário cancela ou edita a própria com menos de 24h | Recusado com mensagem | ✅ |
| 10 | Usuário cancela ou edita reserva de outro | 403 | ✅ |
| 11 | Operador cancela com menos de 24h | Cancelada | ✅ |
| 12 | Apagar reserva de vez | Usuário 403; administrador apaga | ✅ |
| 13 | Horário cancelado | Fica livre para nova reserva | ✅ |
| 14 | Botões da lista de reservas para usuário | Só nas reservas dele | ✅ |
| 15 | Isolamento nas telas (inclusive operador) | 404 para reservas de outra organização | ✅ |
| 16 | API: usuário cria sala | 403; operador cria (201) | ✅ |
| 17 | API: criar reserva mandando `status=cancelada` | Confirmada, com dono; `status` ignorado | ✅ |
| 18 | API: aprovação | Pendente; usuário 403; operador aprova | ✅ |
| 19 | API: cancelar própria >24h / <24h / de outro / operador <24h | 200 / 403 / 403 / 200 | ✅ |
| 20 | API: editar e apagar | Mesmas regras das telas | ✅ |
| 21 | API: horário cancelado | Fica livre (antes 400, depois 201) | ✅ |
| 22 | API: isolamento entre organizações | 404 e 400 para dados de outra organização | ✅ |
| 23 | Migração dos papéis | Perfis existentes viram administrador | ✅ |

---

## Dashboard

Tela em `/dashboard/` com os números da organização do usuário. As métricas ficam em
`salas/dashboard.py` e partem todas de uma base só: reservas da organização, sem as excluídas
(`excluida_em` nulo) e no período escolhido. A tela, a exportação e a API usam as mesmas funções.

### As perguntas do dono e a métrica de cada uma

| # | Pergunta | Métrica | Como é calculada |
|---|---|---|---|
| 1 | Quanto a organização reserva? | Cartões: total, confirmadas, pendentes, canceladas, pessoas que reservaram e reservas desta semana | Um `aggregate` com `Count(filter=Q(...))` e `Count('criado_por', distinct=True)`; a semana (segunda a domingo, confirmadas e pendentes) não depende do filtro de período |
| 2 | Quais salas são mais usadas? | Ranking das 5 salas mais reservadas | `values('sala')` + `annotate(Count)`, sem as canceladas |
| 3 | Como as reservas evoluem mês a mês? | Gráfico de barras por mês (Chart.js) | `TruncMonth('data_inicio')` + `annotate(Count)` + `order_by` no fim, mês em MM/AAAA |
| 4 | Quantas reservas ficam confirmadas, pendentes ou canceladas? | Distribuição por status, com as cores das etiquetas | `values('status')` + `annotate(Count)` |

**Filtro de período:** `PeriodoForm` com `inicio` e `fim` (opcionais, os dois dias entram). Data
inválida ou fim antes do início mostram o erro no formulário e o filtro é ignorado, sem erro 500
(na API, resposta `400` com os erros).

**Gráfico:** Chart.js 4.4.6 servido pelo próprio projeto (`static/js/chart.umd.js`), código em
`static/js/dashboard.js` e dados passados com `json_script`.

### Quem vê o quê

| Recurso | Usuário | Funcionário | Administrador |
|---|:---:|:---:|:---:|
| Link "Dashboard" na barra | ❌ | ✅ | ✅ |
| Cartões, ranking e distribuição por status | ❌ (403) | ✅ | ✅ |
| Gráfico de reservas por mês | ❌ | ❌ | ✅ |
| Exportar CSV (`/dashboard/exportar/`) | ❌ (403) | ❌ (403) | ✅ |
| API `/api/dashboard/` | ❌ (403) | ✅ sem a série por mês | ✅ completa |

Administrador aqui é o superusuário com perfil de administrador. Quem tem papel administrador sem
ser superusuário é tratado como funcionário, igual ao Admin.

**Exportar CSV:** `reservas.csv` em UTF-8 com BOM e `;` como separador (abre direto no Excel em
português), com as colunas sala, reservado por, e-mail, início, fim e status. Respeita o período.
Células que começam com `=`, `+`, `-`, `@`, tabulação ou quebra de linha ganham um apóstrofo na frente
para o Excel não executar fórmulas.

### Desempenho

Medido com `CaptureQueriesContext` antes e depois:

| Tela | Antes (2 salas → 6 salas) | Depois | Correção |
|---|---|---|---|
| Lista de salas | 12 → 24 consultas | 7, fixo | `prefetch_related('recursos')` |
| Lista de reservas | 17 → 41 consultas | 6, fixo | `prefetch_related('sala__recursos')` |
| Detalhes da sala | 7 | 7, fixo | já usava `select_related` |
| Dashboard | (novo) | 9, fixo | uma consulta por métrica |
| Exportar CSV | (novo) | 5, fixo | `select_related('sala', 'criado_por')` |

Índices novos em `Reserva`: `data_inicio` e `status` (migração `0009_indices_reserva`). Os números
ficam travados com `assertNumQueries` nos testes.

### Testes do dashboard: resultado

`python manage.py check` e `makemigrations --check` sem pendências.
`python manage.py test salas`: **105 de 105 testes passaram** (25 deles do dashboard e do desempenho).

| # | Cenário | Esperado | Resultado |
|---|---|---|---|
| 1 | Org A com 3 reservas e org B com 5 | A vê 3 | ✅ |
| 2 | Filtro de período (início, fim e os dois) | Conta só as reservas do período, dias inclusos | ✅ |
| 3 | Reservas excluídas | Não entram em nenhuma métrica | ✅ |
| 4 | Dashboard sem dados | Abre com zeros e "Sem dados no período" | ✅ |
| 5 | Data inválida ou fim antes do início na URL | 200 com erro no formulário, filtro ignorado | ✅ |
| 6 | Números, ranking (5 primeiras, sem canceladas), distribuição e série por mês | Valores conferidos um a um | ✅ |
| 7 | Reservas desta semana | Só confirmadas e pendentes de segunda a domingo, sem depender do período | ✅ |
| 8 | Funcionário (e administrador sem superusuário) | Vê o dashboard, sem gráfico e sem exportar (403) | ✅ |
| 9 | Usuário comum | 403 na tela, na exportação e na API | ✅ |
| 10 | CSV | Colunas certas, só da organização, sem excluídas, respeita o período | ✅ |
| 11 | CSV com `=`, `+`, `-` e `@` | Células protegidas com apóstrofo | ✅ |
| 12 | API do dashboard | Mesmos números da tela; funcionário sem série; data inválida 400 | ✅ |
| 13 | `assertNumQueries` | Listas, detalhes da sala, dashboard e CSV com número fixo de consultas | ✅ |

### Conferência de isolamento entre organizações

Todas as métricas partem de `base()`, que filtra `organizacao=org_atual(request)` antes de qualquer
outra coisa; a tela, o CSV e a API não fazem consultas fora dela.

| Verificação | Esperado | Resultado |
|---|---|---|
| Dashboard da org A com dados nas duas organizações | Só os números da A; salas da B não aparecem no ranking | ✅ |
| CSV do administrador da org A | Nenhuma linha da org B | ✅ |
| API com administrador da org B | Só as reservas da B | ✅ |
| Reservas desta semana | Reserva da org B na mesma semana não entra | ✅ |
