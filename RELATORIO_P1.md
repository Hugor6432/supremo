# Relatório P1 – Sistema de Reserva de Salas

**Disciplina:** Laboratório de Programação Full Stack – Prof. Márcio Garrido
**Projeto escolhido:** 8. Reserva de Salas

## 1. Sobre o projeto

O sistema serve para cadastrar salas e marcar reservas nelas. Ele tem CRUD completo (criar, listar, editar e excluir) de **Salas** e **Reservas**. Pelo painel Admin também dá para cadastrar **Recursos** (projetor, ar-condicionado etc.) e **Recorrências**. Além disso, o sistema já avisava quando duas reservas da mesma sala caíam no mesmo horário.

Para o P1, acrescentei as duas features obrigatórias descritas abaixo.

## 2. Feature 1 – Busca e filtro na lista de salas

**Onde fica:** na página **Salas** (`/salas/`), acima da lista.

**O que faz:**

- **Campo de busca:** a pessoa digita um texto e o sistema mostra só as salas que têm esse texto no **nome** ou na **descrição**. Não importa se o texto está em maiúscula ou minúscula (uso `icontains`).
- **Filtro por capacidade mínima:** um `<select>` com as opções 5+, 10+, 20+, 50+ e 100+ pessoas.
- **Filtro por recurso:** um `<select>` com os recursos cadastrados (ex.: "Projetor"). Aparecem só as salas que têm aquele recurso.
- Os filtros funcionam **sozinhos ou juntos**. Exemplo: buscar "laboratório" com capacidade de 20+ e recurso "Projetor".
- Depois de pesquisar, o termo **continua escrito no campo** (`value="{{ request.GET.q }}"`), e os selects continuam com a opção escolhida.
- Se nada for encontrado, aparece a mensagem **"Nenhuma sala encontrada com esses filtros"**, com um botão para limpar os filtros. Isso usa o `{% empty %}` do `{% for %}`.

**Como fiz:** na view `lista_salas` ([salas/views.py](salas/views.py)), leio os parâmetros com `request.GET.get('q')`, `request.GET.get('capacidade')` e `request.GET.get('recurso')`. Aplico um `.filter()` para cada filtro que estiver preenchido.

**Desafio extra (Q):** usei `Q()` para buscar o texto no nome **ou** na descrição na mesma consulta:

```python
salas = salas.filter(Q(nome__icontains=busca) | Q(descricao__icontains=busca))
```

O `|` significa "OU". Sem o `Q()`, eu só conseguiria filtrar por um campo de cada vez, ou teria que exigir que o texto estivesse nos dois campos ao mesmo tempo.

**Por que escolhi esses campos:**

- **Nome:** é assim que as pessoas conhecem a sala ("Sala 101", "Auditório"). A descrição também entra na busca porque às vezes a pessoa lembra só de um detalhe, como "2º andar".
- **Capacidade:** é a primeira coisa que alguém pergunta quando vai marcar uma reunião: "cabe todo mundo?". Por isso o filtro é de capacidade **mínima**. Se eu preciso de uma sala para 20 pessoas, qualquer sala com 20 lugares ou mais serve.
- **Recurso:** muitas reservas dependem de um equipamento. Por exemplo, uma apresentação precisa de projetor.

**O que aconteceria sem essa feature:** com muitas salas cadastradas, a pessoa teria que olhar a lista inteira, uma por uma, para achar uma sala que caiba o grupo e tenha o equipamento necessário.

## 3. Feature 2 – Validação customizada no formulário

**Regra escolhida:** o **horário de término da reserva precisa ser depois do horário de início**.

**Onde fica:** no `ReservaForm` ([salas/forms.py](salas/forms.py)). Por isso a regra vale tanto para **criar** quanto para **editar** uma reserva.

**Como fiz:** sobrescrevi o método `clean()` do ModelForm:

```python
def clean(self):
    cleaned_data = super().clean()
    data_inicio = self.cleaned_data.get('data_inicio')
    data_fim = self.cleaned_data.get('data_fim')

    if data_inicio and data_fim and data_fim <= data_inicio:
        raise forms.ValidationError(
            "O horário de término da reserva deve ser depois do horário de início."
        )
    return cleaned_data
```

- Usei o `clean()`, e não um `clean_data_fim()`, porque a regra compara **dois campos**. No `clean()` os dois já estão disponíveis.
- O `if data_inicio and data_fim` evita erro quando um dos campos está vazio ou inválido. Nesse caso, o próprio Django já mostra o aviso de "campo obrigatório".
- Como os formulários de reserva mostram os campos um por um, e não com `{{ form.as_p }}`, acrescentei `{{ form.non_field_errors }}` nos templates `criar_reserva.html` e `editar_reserva.html`. Sem isso, a mensagem de erro não apareceria na tela.

**Por que escolhi essa regra:** uma reserva é um **intervalo de tempo**. Se o fim vem antes do início, ou é igual a ele, a reserva não faz sentido: ela teria duração zero ou negativa.

**O que aconteceria sem essa regra:**

1. O banco de dados aceitaria reservas impossíveis, como "das 15h às 14h".
2. A checagem de **conflito de horário** que o sistema já tinha poderia dar resultado errado. Ela compara intervalos e parte do princípio de que o início vem antes do fim. Uma reserva "de trás para frente" poderia deixar passar um conflito ou apontar um conflito que não existe.

Então essa validação também protege outra regra importante do sistema.

## 4. Como testar

1. Rode o projeto (`python manage.py runserver`) e abra `http://127.0.0.1:8000/salas/`.
2. **Feature 1:** cadastre algumas salas com capacidades diferentes e adicione recursos pelo Admin. Depois teste a busca, os dois filtros e as combinações. Pesquise um nome que não existe para ver a mensagem de "nenhuma sala encontrada".
3. **Feature 2:** vá em **Reservas → Nova Reserva** e coloque o fim antes do início, ou igual a ele. A reserva não é salva e aparece a mensagem de erro em vermelho.

## 5. Arquivos alterados

| Arquivo | O que mudou |
|---|---|
| `salas/views.py` | Busca e filtros na view `lista_salas` (Feature 1) |
| `templates/salas/lista_salas.html` | Formulário de busca/filtro e mensagem com `{% empty %}` (Feature 1) |
| `salas/forms.py` | Método `clean()` no `ReservaForm` (Feature 2) |
| `templates/salas/criar_reserva.html` e `editar_reserva.html` | Exibição do erro da validação (Feature 2) |
