# Melhorias da P1

Pontos frágeis encontrados na revisão da P1 e a situação de cada um.

| Item | Situação |
|---|---|
| 1. Conflito de horário no Admin gera erro 500 | Pendente |
| 2. Regras de negócio espalhadas | Em parte |
| 3. `tem_conflito()` percorre as reservas em Python | Pendente |
| 4. Recurso preso a uma sala e responsável como texto | Em parte |
| 5. Configurações sensíveis no código e telas sem login | Em parte |
| 6. Senha editável no Admin salva sem criptografia | Corrigido |

## 1. Conflito de horário no Admin gera erro 500

`ReservaAdmin.save_model` ainda faz `raise ValueError` quando há conflito, e o Admin mostra uma
página de erro. Falta mover a checagem para um `clean()`, para o aviso aparecer no formulário.

## 2. Regras de negócio espalhadas

As regras de papel, dono e 24 horas ficaram no model (`pode_mexer` e `pode_alterar`) e são usadas
pelas telas e pela API. A regra "fim depois do início" ainda está repetida no form e no serializer,
e o Admin não passa por ela.

## 3. `tem_conflito()` percorre as reservas em Python

O método ainda carrega as reservas da sala e compara uma por uma. Falta trocar por uma consulta só:
`filter(data_inicio__lt=self.data_fim, data_fim__gt=self.data_inicio).exists()`.

## 4. Recurso preso a uma sala e responsável como texto

O dono da reserva agora é uma FK para `User` (`criado_por`), e o responsável é preenchido com o
nome de quem reservou. O `Recurso` continua ligado a uma única sala.

## 5. Configurações sensíveis no código e telas sem login

Todas as telas exigem login. `SECRET_KEY`, `DEBUG` e `ALLOWED_HOSTS` continuam fixos em
`settings.py`; falta lê-los de variáveis de ambiente.

## 6. Senha editável no Admin salva sem criptografia

Corrigido: o campo de senha ficou só leitura e a troca passa pelo formulário próprio do Admin.
