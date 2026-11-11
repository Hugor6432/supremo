# Melhorias da P1

Revisão do projeto entregue na P1 antes de começar a P2 (Aula 13).
Cada item aponta um ponto frágil e o que deve ser feito.

## 1. Conflito de horário no Admin gera erro 500

**Onde:** `salas/admin.py`, método `ReservaAdmin.save_model`.

**Problema:** quando há conflito, o código faz `raise ValueError(...)`. No Admin isso aparece como
uma página de erro do servidor, e não como uma mensagem de validação no formulário.

**Correção:** mover a checagem de conflito para um lugar que gere `ValidationError`
(o `clean()` do model ou do form do Admin), para a mensagem aparecer em vermelho no formulário.

## 2. Regras de negócio espalhadas em vários lugares

**Onde:** `salas/forms.py` (fim depois do início), `salas/views.py` e `salas/admin.py` (conflito).

**Problema:** a regra "fim depois do início" só vale no `ReservaForm`; o Admin e a futura API
não passam por ela. A checagem de conflito é chamada à mão em três lugares diferentes.

**Correção:** deixar cada regra em um lugar principal e reaproveitar esse lugar no form,
no Admin e no serializer da API.

## 3. `tem_conflito()` percorre as reservas em Python

**Onde:** `salas/models.py`, `Reserva.tem_conflito`.

**Problema:** o método carrega todas as reservas da sala e compara uma por uma num `for`.
Com muitas reservas, fica lento.

**Correção:** fazer a comparação no banco, com uma única consulta:
`filter(data_inicio__lt=self.data_fim, data_fim__gt=self.data_inicio).exists()`.

## 4. Recurso preso a uma sala e responsável como texto livre

**Onde:** `salas/models.py`, models `Recurso` e `Reserva`.

**Problema:** cada `Recurso` tem FK para uma única sala, então "Projetor" é cadastrado de novo em
cada sala. Já o `responsavel` da reserva é um texto livre, sem ligação com o usuário que fez a reserva.

**Correção:** avaliar transformar `Recurso` em catálogo com `ManyToManyField` em `Sala`, e trocar
`responsavel` por uma FK para `User` quando entrar o login (Aula 15).

## 5. Configurações sensíveis no código e telas sem login

**Onde:** `reservas/settings.py` e `salas/views.py`.

**Problema:** `SECRET_KEY` fixa no código, `DEBUG = True` e `ALLOWED_HOSTS = ['*']`. Além disso,
qualquer pessoa sem login consegue criar, editar e apagar salas e reservas.

**Correção:** ler `SECRET_KEY` e `DEBUG` de variáveis de ambiente (`.env` fora do Git) e exigir
login em todas as telas (`@login_required`), o que já é necessário para a multi-organização.

---

## Situação

| Item | Status |
|---|---|
| 1. Erro 500 no Admin | Pendente |
| 2. Regras espalhadas | Pendente |
| 3. `tem_conflito()` em Python | Pendente |
| 4. Recurso e responsável | Pendente |
| 5. Configurações e login | Em andamento: login exigido nas telas na Aula 14 |
