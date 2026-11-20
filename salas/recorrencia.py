import calendar
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.atividades import data_hora
from . import atividades
from .models import Recorrencia, Reserva

LIMITE_OCORRENCIAS = 100

REPETIR = [
    ('nao', 'Não repetir'),
    ('diaria', 'Todo dia'),
    ('semanal', 'Toda semana'),
    ('mensal', 'Todo mês'),
]


def soma_meses(valor, meses):
    # Mesmo dia nos meses seguintes; 31/01 vira 28/02 (ou 29) quando o mês é menor
    total = valor.month - 1 + meses
    ano, mes = valor.year + total // 12, total % 12 + 1
    dia = min(valor.day, calendar.monthrange(ano, mes)[1])
    return valor.replace(year=ano, month=mes, day=dia)


def _desloca(valor, frequencia, passos):
    if frequencia == 'diaria':
        return valor + timedelta(days=passos)
    if frequencia == 'semanal':
        return valor + timedelta(weeks=passos)
    return soma_meses(valor, passos)


def datas_da_serie(inicio, fim, frequencia, intervalo, ate):
    # Calcula no horário local para manter a mesma hora em todas as datas
    inicio_local = timezone.localtime(inicio).replace(tzinfo=None)
    duracao = fim - inicio
    ocorrencias = []
    passo = 0
    while len(ocorrencias) <= LIMITE_OCORRENCIAS:
        atual = _desloca(inicio_local, frequencia, passo * intervalo)
        if atual.date() > ate:
            break
        comeco = timezone.make_aware(atual)
        ocorrencias.append((comeco, comeco + duracao))
        passo += 1
    return ocorrencias


def planeja(sala, inicio, fim, frequencia, intervalo, ate):
    # Devolve (erros, ocorrências); erros são pares (campo ou None, mensagem)
    if ate is None:
        return [('ate', "Informe até quando a reserva se repete.")], []
    dia_inicio = timezone.localtime(inicio).date()
    if ate < dia_inicio:
        return [('ate', "A data final não pode ser antes do início da reserva.")], []
    if ate > soma_meses(dia_inicio, 12):
        return [('ate', "A repetição pode durar no máximo 1 ano.")], []

    ocorrencias = datas_da_serie(inicio, fim, frequencia, intervalo, ate)
    if len(ocorrencias) > LIMITE_OCORRENCIAS:
        return [(None, f"A série passaria de {LIMITE_OCORRENCIAS} reservas. "
                       "Escolha uma data final mais próxima ou um intervalo maior.")], []
    for atual, proxima in zip(ocorrencias, ocorrencias[1:]):
        if atual[1] > proxima[0]:
            return [(None, "Cada reserva da série terminaria depois do início da próxima. "
                           "Diminua a duração ou aumente o intervalo.")], []

    # Datas que já passaram não são criadas
    agora = timezone.now()
    futuras = [o for o in ocorrencias if o[0] > agora]
    if not futuras:
        return [(None, "Todas as datas dessa série já passaram.")], []

    # Confere todas antes de criar qualquer uma
    conflitos = [o for o in futuras if Reserva(sala=sala, data_inicio=o[0], data_fim=o[1]).tem_conflito()]
    if conflitos:
        datas = ', '.join(data_hora(o[0]) for o in conflitos)
        return [(None, f"Conflito! Estas datas já estão ocupadas nesta sala: {datas}. "
                       "Nenhuma reserva da série foi criada.")], []
    return [], futuras


def cria_serie(usuario, org, sala, ocorrencias, frequencia, intervalo, ate, descricao=''):
    # Cria a Recorrencia e todas as reservas juntas, ou nenhuma
    with transaction.atomic():
        recorrencia = Recorrencia.objects.create(
            organizacao=org,
            frequencia=frequencia,
            intervalo=intervalo,
            data_inicio=timezone.localtime(ocorrencias[0][0]).date(),
            data_fim=ate,
        )
        status = Reserva(sala=sala).status_inicial()
        reservas = [
            Reserva.objects.create(
                organizacao=org, sala=sala, data_inicio=comeco, data_fim=termino,
                descricao=descricao, recorrencia=recorrencia, status=status,
                criado_por=usuario, responsavel=usuario.username,
            )
            for comeco, termino in ocorrencias
        ]
        atividades.serie_criada(usuario, recorrencia, sala, reservas)
    return recorrencia, reservas


def mensagem_serie(reservas):
    primeira = timezone.localtime(reservas[0].data_inicio).strftime('%d/%m')
    ultima = timezone.localtime(reservas[-1].data_inicio).strftime('%d/%m')
    texto = f"Série criada: {len(reservas)} reservas de {primeira} a {ultima}."
    if reservas[0].status == 'pendente':
        texto += " Elas aguardam a aprovação de um operador."
    return texto
