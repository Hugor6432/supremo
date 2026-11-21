# Reserva de Salas: de MVP (P1) a mini-SaaS (P2)

**Disciplina:** Laboratório de Programação Full Stack, Prof. Márcio Garrido

Sistema para cadastrar salas e marcar reservas nelas. Na P1 ele era um CRUD simples
(veja [RELATORIO_P1.md](RELATORIO_P1.md)). Na P2 virou um mini-SaaS: várias organizações usam o
mesmo sistema, cada pessoa tem um papel, há uma API REST e um dashboard.

- Situação das melhorias da P1: [MELHORIAS_P1.md](MELHORIAS_P1.md)
- Backlog da P2: [BACKLOG_P2.md](BACKLOG_P2.md)

## 1. O que o sistema faz

- **Organizações:** cada organização enxerga só as próprias salas, reservas e números.
- **Salas:** cadastro com capacidade, descrição, recursos (projetor, TV etc.) e a opção
  "exige aprovação". Cada sala tem uma página com os recursos e as próximas reservas.
- **Reservas:** a reserva fica no nome de quem a criou e nasce confirmada (ou pendente, se a sala
  exige aprovação). O sistema não deixa marcar duas reservas no mesmo horário da mesma sala.
- **Reservas recorrentes:** "toda semana até tal dia", por exemplo. O sistema cria uma reserva
  para cada data e, se alguma data estiver ocupada, não cria nenhuma.
- **Cancelar e excluir:** cancelar deixa a reserva no histórico e libera o horário. Excluir pelo
  site também não apaga do banco: o administrador pode restaurar pelo Admin.
- **Histórico:** o Admin mostra quem fez o quê (criou, editou, cancelou, aprovou, excluiu...).
- **Cadastro público:** a pessoa cria a própria conta em `/contas/cadastro/` e entra como usuário comum.
- **Dashboard:** responde a quatro perguntas do dono: quanto a organização reserva, quais salas
  são mais usadas, como as reservas evoluem mês a mês e quantas ficam confirmadas, pendentes ou
  canceladas. Tem filtro de período e exportação em CSV.
- **API REST** em `/api/` (salas, reservas, recursos, recorrências e dashboard), com as mesmas
  regras das telas.

## 2. Como rodar

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Site: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/
- Testes: `python manage.py test salas`

No Admin, crie uma **Organização** e depois os **Usuários**, escolhendo o tipo (Usuário,
Funcionário ou Administrador) e a organização. Quem não tem organização não acessa as telas do site.

## 3. Quem pode o quê

| Ação | Usuário | Funcionário | Administrador |
|---|:---:|:---:|:---:|
| Ver as salas e a página de cada sala | ✅ | ✅ | ✅ |
| Ver quem reservou cada horário da sala | ❌ só "Ocupado" | ✅ | ✅ |
| Criar reserva (única ou recorrente) | ✅ | ✅ | ✅ |
| Ver as próprias reservas | ✅ | ✅ | ✅ |
| Ver as reservas de outras pessoas | ❌ | ✅ | ✅ |
| Editar e cancelar as próprias reservas | ✅ só com mais de 24h | ✅ | ✅ |
| Editar e cancelar reservas de outras pessoas | ❌ | ✅ | ✅ |
| Aprovar e recusar reservas pendentes | ❌ | ✅ | ✅ |
| Excluir reservas | ❌ | ✅ | ✅ |
| Criar, editar e excluir salas e recursos | ❌ | ✅ | ✅ |
| Dashboard (números, ranking e status) | ❌ | ✅ | ✅ |
| Gráfico por mês e exportar CSV | ❌ | ❌ | ✅ |
| Admin (usuários, restaurar excluídos, histórico) | ❌ | ❌ | ✅ |

Funcionário é o papel `operador`. Administrador é o superusuário com organização. Quem não pode
fazer algo recebe 403, ou 404 quando a reserva é de outra pessoa. A API segue a mesma tabela.

## 4. Roteiro de isolamento

Executado em 10/11/2026 com duas organizações (**Escola Alfa**, usuária `ana`, e **Empresa Beta**,
usuário `bruno`) e um superusuário sem organização. **25 de 25 verificações passaram.**

- Sem login, o site manda para a tela de entrar; a API responde 403.
- Ana vê só as salas, recursos, recorrências e reservas da Alfa, nas telas e na API.
- Abrir, editar ou apagar uma sala ou reserva da Beta pelo endereço dá 404, e nada muda.
- Os selects do formulário de reserva mostram só salas da Alfa; um POST forjado com sala da Beta é recusado.
- O que Ana cria fica na Alfa, mesmo mandando `"organizacao"` de outra pela API.
- O nome da sala é único dentro de cada organização (a Alfa pode ter uma sala com o mesmo nome de uma da Beta).
- O superusuário sem organização recebe 403 no site e vê tudo no Admin.

Depois disso, o isolamento passou a ser conferido também pelos testes automáticos: telas, API,
série de reservas, página da sala, dashboard e CSV.

## 5. Testes

`python manage.py test salas` roda num banco de teste separado. **111 de 111 testes passaram.**

| Área | Testes |
|---|---:|
| Papéis, 24 horas, cancelamento e aprovação nas telas | 15 |
| API (permissões, 24 horas, conflito, isolamento) | 7 |
| Usuários: tipo no Admin, cadastro público e migração dos papéis | 15 |
| Responsável pela conta, recursos no cadastro da sala e página da sala | 18 |
| Reservas recorrentes | 13 |
| Exclusão registrada, restauração e histórico | 12 |
| Dashboard: tela, período, permissões, CSV e API | 22 |
| Usuário comum vê só as próprias reservas | 6 |
| Desempenho (número de consultas fixo nas telas principais) | 3 |
