# Reserva de Salas: de MVP (P1) a mini-SaaS (P2)

**Disciplina:** Laboratório de Programação Full Stack, Prof. Márcio Garrido

Sistema para cadastrar salas e marcar reservas nelas. A P1 está descrita em
[RELATORIO_P1.md](RELATORIO_P1.md) e os comandos para rodar no Windows estão em
[README_WINDOWS.md](README_WINDOWS.md).

- Melhorias pendentes da P1: [MELHORIAS_P1.md](MELHORIAS_P1.md)
- Backlog da P2: [BACKLOG_P2.md](BACKLOG_P2.md)

---

## Aula 13: API REST com Django REST Framework

A API fica em `/api/` e exige login (`IsAuthenticated`, autenticação por sessão do Django).
Para entrar pela Browsable API, use o link "Log in" no canto da página (`/api-auth/login/`).

| Recurso | Listar / criar | Detalhar / atualizar / apagar |
|---|---|---|
| Salas | `GET` `POST` `/api/salas/` | `GET` `PUT` `PATCH` `DELETE` `/api/salas/<id>/` |
| Reservas | `GET` `POST` `/api/reservas/` | `GET` `PUT` `PATCH` `DELETE` `/api/reservas/<id>/` |
| Recursos | `GET` `POST` `/api/recursos/` | `GET` `PUT` `PATCH` `DELETE` `/api/recursos/<id>/` |
| Recorrências | `GET` `POST` `/api/recorrencias/` | `GET` `PUT` `PATCH` `DELETE` `/api/recorrencias/<id>/` |

Arquivos: `salas/serializers.py`, `salas/api_views.py` e `salas/api_urls.py`.

Validações da API (respondem `400` com a mensagem em JSON):

- Reserva: término depois do início (mesma regra da Feature 2) e conflito de horário (reaproveita `Reserva.tem_conflito()`).
- Sala: capacidade maior que zero e nome único dentro da organização.
- Recorrência: intervalo de pelo menos 1 e data de fim que não seja antes do início.

---

## Aula 14: Multi-organização (coluna discriminadora)

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
  em vez de erro 500. A decisão definitiva fica para a Aula 15.

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

### Revisão de views e templates (tarefa de casa da Aula 14)

- `salas/views.py`: as 9 views exigem login e filtram pela organização.
- `salas/forms.py`: os selects `sala` e `recorrencia` e a checagem de nome duplicado filtram pela organização.
- `salas/api_views.py` e `salas/serializers.py`: listagem, detalhe, criação e campos de relacionamento filtram pela organização.
- `salas/models.py`: `tem_conflito()` compara só reservas da mesma organização e da mesma sala.
- Templates: as únicas consultas são `sala.recursos.all` e `reserva.tem_conflito`, sempre a partir
  de uma sala ou reserva que já veio filtrada pela organização. Nenhuma consulta solta.
- Admin: o superusuário vê tudo, com coluna e filtro por organização. Recursos e reservas criados
  no Admin herdam a organização da sala.
