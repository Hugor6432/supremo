from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import Reserva

# Ordem e rótulos da distribuição, com as cores das etiquetas de status
STATUS = [
    ('confirmada', 'Confirmada'),
    ('pendente', 'Pendente'),
    ('cancelada', 'Cancelada'),
]


def _comeco_do_dia(dia):
    return timezone.make_aware(datetime.combine(dia, time.min))


def base(org, inicio=None, fim=None):
    # Reservas da organização, sem as excluídas, no período escolhido (dias inclusos)
    reservas = Reserva.objects.filter(organizacao=org, excluida_em__isnull=True)
    if inicio:
        reservas = reservas.filter(data_inicio__gte=_comeco_do_dia(inicio))
    if fim:
        reservas = reservas.filter(data_inicio__lt=_comeco_do_dia(fim + timedelta(days=1)))
    return reservas


def kpis(reservas):
    # Uma consulta só para todos os números
    return reservas.aggregate(
        total=Count('id'),
        confirmadas=Count('id', filter=Q(status='confirmada')),
        pendentes=Count('id', filter=Q(status='pendente')),
        canceladas=Count('id', filter=Q(status='cancelada')),
        pessoas=Count('criado_por', distinct=True),
    )


def reservas_da_semana(org):
    # Confirmadas ou pendentes de segunda a domingo da semana atual; ignora o filtro de período
    hoje = timezone.localdate()
    segunda = hoje - timedelta(days=hoje.weekday())
    return Reserva.objects.filter(
        organizacao=org,
        excluida_em__isnull=True,
        status__in=['confirmada', 'pendente'],
        data_inicio__gte=_comeco_do_dia(segunda),
        data_inicio__lt=_comeco_do_dia(segunda + timedelta(days=7)),
    ).count()


def ranking(reservas, limite=5):
    # Salas mais reservadas, sem contar as canceladas
    linhas = (
        reservas.exclude(status='cancelada')
        .values('sala_id', 'sala__nome')
        .annotate(total=Count('id'))
        .order_by('-total', 'sala__nome')[:limite]
    )
    return [{'sala_id': l['sala_id'], 'sala': l['sala__nome'], 'total': l['total']} for l in linhas]


def por_mes(reservas):
    linhas = (
        reservas.annotate(mes=TruncMonth('data_inicio'))
        .values('mes')
        .annotate(total=Count('id'))
        .order_by('mes')
    )
    return [{'mes': l['mes'].strftime('%m/%Y'), 'total': l['total']} for l in linhas]


def por_status(reservas):
    contagem = dict(reservas.values('status').annotate(total=Count('id')).order_by().values_list('status', 'total'))
    soma = sum(contagem.values())
    return [
        {
            'status': status,
            'rotulo': rotulo,
            'total': contagem.get(status, 0),
            'percentual': round(100 * contagem.get(status, 0) / soma) if soma else 0,
        }
        for status, rotulo in STATUS
    ]


def resumo(org, inicio=None, fim=None, com_serie=False):
    # Tudo o que a tela e a API mostram, a partir da mesma base
    reservas = base(org, inicio, fim)
    dados = {
        'kpis': {**kpis(reservas), 'semana': reservas_da_semana(org)},
        'ranking': ranking(reservas),
        'por_status': por_status(reservas),
    }
    if com_serie:
        dados['por_mes'] = por_mes(reservas)
    return dados
