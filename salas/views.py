import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.utils import eh_administrador_completo, eh_operador, org_atual, exige_operador
from . import atividades, dashboard as metricas, recorrencia
from .models import Sala, Recurso, Reserva
from .forms import PeriodoForm, RecursoFormSet, ReservaCriacaoForm, ReservaForm, SalaForm


# ===== VIEWS DE SALAS =====

@login_required
def lista_salas(request):
    org = org_atual(request)

    # Feature 1 - Busca e Filtro
    busca = request.GET.get('q', '').strip()
    capacidade = request.GET.get('capacidade', '')
    recurso = request.GET.get('recurso', '')

    salas = Sala.objects.filter(organizacao=org)

    # Busca no nome OU na descrição da sala
    if busca:
        salas = salas.filter(Q(nome__icontains=busca) | Q(descricao__icontains=busca))

    if capacidade.isdigit():
        salas = salas.filter(capacidade__gte=int(capacidade))

    if recurso:
        salas = salas.filter(recursos__nome=recurso)

    # Recursos carregados de uma vez, sem uma consulta por sala
    salas = salas.distinct().order_by('nome').prefetch_related('recursos')

    contexto = {
        'salas': salas,
        'recursos': Recurso.objects.filter(organizacao=org)
                                   .values_list('nome', flat=True).distinct().order_by('nome'),
        'opcoes_capacidade': [5, 10, 20, 50, 100],
        'capacidade_selecionada': capacidade,
        'recurso_selecionado': recurso,
    }
    return render(request, 'salas/lista_salas.html', contexto)


@login_required
def detalhes_sala(request, id):
    org = org_atual(request)
    sala = get_object_or_404(Sala, id=id, organizacao=org)
    # Próximas reservas que ocupam a sala (as canceladas não ocupam)
    proximas = (
        sala.reservas.filter(status__in=['confirmada', 'pendente'], data_fim__gte=timezone.now())
        .select_related('criado_por')
        .order_by('data_inicio')
    )
    contexto = {'sala': sala, 'recursos': sala.recursos.all(), 'proximas': proximas}
    return render(request, 'salas/detalhes_sala.html', contexto)


def _salva_recursos(formset, sala, org, usuario):
    # Recursos ficam na organização da sala; cada mudança vai para o histórico
    formset.instance = sala
    formset.save(commit=False)
    for recurso in formset.new_objects:
        recurso.organizacao = org
        recurso.save()
        atividades.recurso(usuario, 'adicionou', recurso)
    for recurso, _campos in formset.changed_objects:
        recurso.save()
        atividades.recurso(usuario, 'editou', recurso)
    for recurso in formset.deleted_objects:
        atividades.recurso(usuario, 'removeu', recurso)
        recurso.delete()


@login_required
def criar_sala(request):
    org = org_atual(request)
    exige_operador(request)
    if request.method == 'POST':
        form = SalaForm(request.POST, org=org)
        formset = RecursoFormSet(request.POST, instance=Sala(), prefix='recursos')
        if form.is_valid() and formset.is_valid():
            # Sala e recursos são salvos juntos ou nada é salvo
            with transaction.atomic():
                sala = form.save(commit=False)
                sala.organizacao = org
                sala.save()
                atividades.sala(request.user, 'criou', sala)
                _salva_recursos(formset, sala, org, request.user)
            messages.success(request, 'Sala criada com sucesso!')
            return redirect('lista_salas')
    else:
        form = SalaForm(org=org)
        formset = RecursoFormSet(instance=Sala(), prefix='recursos')
    return render(request, 'salas/criar_sala.html', {'form': form, 'formset': formset})


@login_required
def editar_sala(request, id):
    org = org_atual(request)
    exige_operador(request)
    sala = get_object_or_404(Sala, id=id, organizacao=org)
    if request.method == 'POST':
        form = SalaForm(request.POST, instance=sala, org=org)
        formset = RecursoFormSet(request.POST, instance=sala, prefix='recursos')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                if form.has_changed():
                    atividades.sala(request.user, 'editou', sala)
                _salva_recursos(formset, sala, org, request.user)
            messages.success(request, 'Sala atualizada com sucesso!')
            return redirect('lista_salas')
    else:
        form = SalaForm(instance=sala, org=org)
        formset = RecursoFormSet(instance=sala, prefix='recursos')
    return render(request, 'salas/editar_sala.html', {'form': form, 'formset': formset, 'sala': sala})


@login_required
def deletar_sala(request, id):
    org = org_atual(request)
    exige_operador(request)
    sala = get_object_or_404(Sala, id=id, organizacao=org)
    if request.method == 'POST':
        # Só marca como excluída; o Admin pode restaurar
        with transaction.atomic():
            sala.excluir(request.user)
            atividades.sala(request.user, 'excluiu', sala)
        messages.success(request, 'Sala excluída com sucesso!')
        return redirect('lista_salas')
    return render(request, 'salas/deletar_sala.html', {'sala': sala})


# ===== VIEWS DE RESERVAS =====

def reservas_visiveis(request, org):
    # Usuário comum enxerga só as próprias reservas; funcionário e administrador, todas da organização
    reservas = Reserva.objects.filter(organizacao=org)
    if not eh_operador(request):
        reservas = reservas.filter(criado_por=request.user)
    return reservas


def _checa_dono(request, reserva):
    if not reserva.pode_mexer(request.user):
        raise PermissionDenied(reserva.MSG_NAO_E_DONO)


@login_required
def lista_reservas(request):
    org = org_atual(request)
    reservas = (
        reservas_visiveis(request, org)
        .select_related('sala', 'recorrencia', 'criado_por')
        .prefetch_related('sala__recursos')
    )
    # Diz ao template quais botões cada reserva pode mostrar
    for reserva in reservas:
        reserva.pode_alterar_aqui = reserva.pode_alterar(request.user)
    return render(request, 'salas/lista_reservas.html', {'reservas': reservas})


@login_required
def criar_reserva(request):
    org = org_atual(request)
    if request.method == 'POST':
        form = ReservaCriacaoForm(request.POST, org=org)
        if form.is_valid() and form.cleaned_data['repetir'] != 'nao':
            # Série: o formulário já conferiu conflito em todas as datas
            dados = form.cleaned_data
            _, reservas = recorrencia.cria_serie(
                request.user, org, dados['sala'], form.ocorrencias,
                dados['repetir'], dados['a_cada'], dados['ate'], dados.get('descricao') or '',
            )
            messages.success(request, recorrencia.mensagem_serie(reservas))
            return redirect('lista_reservas')
        if form.is_valid():
            reserva = form.save(commit=False)
            reserva.organizacao = org
            reserva.criado_por = request.user
            reserva.responsavel = request.user.username
            reserva.status = reserva.status_inicial()
            if reserva.tem_conflito():
                messages.error(request, 'Conflito! Já existe uma reserva neste horário para esta sala.')
                return render(request, 'salas/criar_reserva.html', {'form': form})
            with transaction.atomic():
                reserva.save()
                atividades.reserva(request.user, 'criou', reserva)
            if reserva.status == 'pendente':
                messages.success(request, 'Reserva criada! Ela aguarda a aprovação de um operador.')
            else:
                messages.success(request, 'Reserva criada e confirmada!')
            return redirect('lista_reservas')
    else:
        # "Reservar esta sala" já traz a sala escolhida, se ela for da organização
        sala_id = request.GET.get('sala', '')
        inicial = {}
        if sala_id.isdigit() and Sala.objects.filter(id=sala_id, organizacao=org).exists():
            inicial['sala'] = int(sala_id)
        form = ReservaCriacaoForm(org=org, initial=inicial)
    return render(request, 'salas/criar_reserva.html', {'form': form})


@login_required
def editar_reserva(request, id):
    org = org_atual(request)
    reserva = get_object_or_404(reservas_visiveis(request, org), id=id)
    _checa_dono(request, reserva)
    # Checa antes do form, que altera a instância ao validar
    bloqueada = not reserva.pode_alterar(request.user)
    if request.method == 'POST':
        form = ReservaForm(request.POST, instance=reserva, org=org)
        if form.is_valid():
            if bloqueada:
                form.add_error(None, Reserva.MSG_24H)
            else:
                reserva_atualizada = form.save(commit=False)
                if reserva_atualizada.tem_conflito():
                    messages.error(request, 'Conflito! Já existe uma reserva neste horário para esta sala.')
                    return render(request, 'salas/editar_reserva.html', {'form': form, 'reserva': reserva})
                with transaction.atomic():
                    reserva_atualizada.save()
                    atividades.reserva(request.user, 'editou', reserva_atualizada)
                messages.success(request, 'Reserva atualizada com sucesso!')
                return redirect('lista_reservas')
    else:
        form = ReservaForm(instance=reserva, org=org)
    contexto = {'form': form, 'reserva': reserva, 'bloqueada': bloqueada}
    return render(request, 'salas/editar_reserva.html', contexto)


@login_required
def cancelar_reserva(request, id):
    org = org_atual(request)
    reserva = get_object_or_404(reservas_visiveis(request, org), id=id)
    _checa_dono(request, reserva)
    erro = None
    if reserva.status == 'cancelada':
        erro = 'Esta reserva já está cancelada.'
    elif not reserva.pode_alterar(request.user):
        erro = Reserva.MSG_24H
    if request.method == 'POST' and not erro:
        with transaction.atomic():
            reserva.status = 'cancelada'
            reserva.save(update_fields=['status'])
            atividades.reserva(request.user, 'cancelou', reserva)
        messages.success(request, 'Reserva cancelada. O horário ficou livre.')
        return redirect('lista_reservas')
    return render(request, 'salas/cancelar_reserva.html', {'reserva': reserva, 'erro': erro})


@login_required
@require_POST
def cancelar_serie(request, id):
    org = org_atual(request)
    reserva = get_object_or_404(reservas_visiveis(request, org), id=id)
    _checa_dono(request, reserva)
    if reserva.recorrencia is None:
        messages.error(request, 'Esta reserva não faz parte de uma série.')
        return redirect('cancelar_reserva', id=reserva.id)
    # Esta e as próximas ocorrências futuras que ainda estão ativas
    proximas = Reserva.objects.filter(
        organizacao=org, recorrencia=reserva.recorrencia,
        data_inicio__gte=reserva.data_inicio, data_inicio__gt=timezone.now(),
    ).exclude(status='cancelada').order_by('data_inicio')
    permitidas = [r for r in proximas if r.pode_alterar(request.user)]
    ficaram = len(proximas) - len(permitidas)
    if permitidas:
        with transaction.atomic():
            Reserva.objects.filter(id__in=[r.id for r in permitidas]).update(status='cancelada')
            atividades.serie_cancelada(request.user, reserva.recorrencia, reserva.sala,
                                       len(permitidas), permitidas[0].data_inicio)
    texto = f'{len(permitidas)} reserva(s) da série cancelada(s).'
    if ficaram:
        texto += f' {ficaram} ficaram ativas porque faltam menos de 24 horas para o início.'
    (messages.success if permitidas else messages.warning)(request, texto)
    return redirect('lista_reservas')


def _decide_pendente(request, id, novo_status, acao, texto):
    # Aprovar e recusar: só operador, só reserva pendente
    org = org_atual(request)
    exige_operador(request)
    reserva = get_object_or_404(Reserva, id=id, organizacao=org)
    if reserva.status != 'pendente':
        messages.error(request, 'Só reservas pendentes podem ser aprovadas ou recusadas.')
    else:
        with transaction.atomic():
            reserva.status = novo_status
            reserva.save(update_fields=['status'])
            atividades.reserva(request.user, acao, reserva)
        messages.success(request, texto)
    return redirect('lista_reservas')


@login_required
@require_POST
def aprovar_reserva(request, id):
    return _decide_pendente(request, id, 'confirmada', 'aprovou', 'Reserva aprovada e confirmada!')


@login_required
@require_POST
def recusar_reserva(request, id):
    return _decide_pendente(request, id, 'cancelada', 'recusou', 'Reserva recusada.')


@login_required
def deletar_reserva(request, id):
    org = org_atual(request)
    exige_operador(request)
    reserva = get_object_or_404(Reserva, id=id, organizacao=org)
    if request.method == 'POST':
        # Só marca como excluída; o horário fica livre e o Admin pode restaurar
        with transaction.atomic():
            reserva.excluir(request.user)
            atividades.reserva(request.user, 'excluiu', reserva)
        messages.success(request, 'Reserva excluída com sucesso!')
        return redirect('lista_reservas')
    return render(request, 'salas/deletar_reserva.html', {'reserva': reserva})


@login_required
def detalhes_reserva(request, id):
    org = org_atual(request)
    reserva = get_object_or_404(reservas_visiveis(request, org), id=id)
    contexto = {'reserva': reserva, 'pode_alterar': reserva.pode_alterar(request.user)}
    return render(request, 'salas/detalhes_reserva.html', contexto)


# ===== DASHBOARD =====

def periodo_do_request(request):
    # Data inválida não quebra a tela: o filtro é ignorado e o erro aparece no formulário
    form = PeriodoForm(request.GET or None)
    if form.is_valid():
        return form, form.cleaned_data.get('inicio'), form.cleaned_data.get('fim')
    return form, None, None


@login_required
def dashboard(request):
    org = org_atual(request)
    exige_operador(request)
    form, inicio, fim = periodo_do_request(request)
    completo = eh_administrador_completo(request.user)
    contexto = {
        'form': form,
        'completo': completo,
        'periodo_inicio': inicio,
        'periodo_fim': fim,
        **metricas.resumo(org, inicio, fim, com_serie=completo),
    }
    return render(request, 'salas/dashboard.html', contexto)


# Começos que o Excel interpretaria como fórmula
INICIOS_PERIGOSOS = ('=', '+', '-', '@', '\t', '\r')


def celula_segura(valor):
    texto = '' if valor is None else str(valor)
    return "'" + texto if texto.startswith(INICIOS_PERIGOSOS) else texto


@login_required
def exportar_dashboard(request):
    org = org_atual(request)
    if not eh_administrador_completo(request.user):
        raise PermissionDenied("Só o administrador pode exportar as reservas.")
    _, inicio, fim = periodo_do_request(request)
    reservas = (
        metricas.base(org, inicio, fim)
        .select_related('sala', 'criado_por')
        .order_by('data_inicio')
    )
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = 'attachment; filename="reservas.csv"'
    # BOM para o Excel reconhecer o UTF-8; ";" é o separador do Excel em português
    resposta.write('\ufeff')
    escritor = csv.writer(resposta, delimiter=';')
    escritor.writerow(['Sala', 'Reservado por', 'E-mail', 'Início', 'Fim', 'Status'])
    formato = '%d/%m/%Y %H:%M'
    for reserva in reservas:
        dono = reserva.criado_por
        escritor.writerow([celula_segura(valor) for valor in [
            reserva.sala.nome,
            dono.username if dono else reserva.responsavel,
            dono.email if dono else '',
            timezone.localtime(reserva.data_inicio).strftime(formato),
            timezone.localtime(reserva.data_fim).strftime(formato),
            reserva.get_status_display(),
        ]])
    return resposta
