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
