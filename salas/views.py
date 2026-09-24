from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from .models import Sala, Recurso, Reserva
from .forms import ReservaForm, SalaForm


# ===== VIEWS DE SALAS =====

def lista_salas(request):
    # Feature 1 - Busca e Filtro
    busca = request.GET.get('q', '').strip()
    capacidade = request.GET.get('capacidade', '')
    recurso = request.GET.get('recurso', '')

    salas = Sala.objects.all()

    # Busca por texto: procura no nome OU na descrição da sala (Q = desafio extra)
    if busca:
        salas = salas.filter(Q(nome__icontains=busca) | Q(descricao__icontains=busca))

    # Filtro por capacidade mínima
    if capacidade.isdigit():
        salas = salas.filter(capacidade__gte=int(capacidade))

    # Filtro por recurso disponível na sala
    if recurso:
        salas = salas.filter(recursos__nome=recurso)

    salas = salas.distinct().order_by('nome')

    contexto = {
        'salas': salas,
        'recursos': Recurso.objects.values_list('nome', flat=True).distinct().order_by('nome'),
        'opcoes_capacidade': [5, 10, 20, 50, 100],
        'capacidade_selecionada': capacidade,
        'recurso_selecionado': recurso,
    }
    return render(request, 'salas/lista_salas.html', contexto)


def criar_sala(request):
    if request.method == 'POST':
        form = SalaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Sala criada com sucesso! Adicione recursos no Admin.')
            return redirect('lista_salas')
    else:
        form = SalaForm()
    return render(request, 'salas/criar_sala.html', {'form': form})


def editar_sala(request, id):
    sala = get_object_or_404(Sala, id=id)
    if request.method == 'POST':
        form = SalaForm(request.POST, instance=sala)
        if form.is_valid():
            form.save()
            messages.success(request, 'Sala atualizada com sucesso!')
            return redirect('lista_salas')
    else:
        form = SalaForm(instance=sala)
    return render(request, 'salas/editar_sala.html', {'form': form, 'sala': sala})


def deletar_sala(request, id):
    sala = get_object_or_404(Sala, id=id)
    if request.method == 'POST':
        sala.delete()
        messages.success(request, 'Sala deletada com sucesso!')
        return redirect('lista_salas')
    return render(request, 'salas/deletar_sala.html', {'sala': sala})


# ===== VIEWS DE RESERVAS =====

def lista_reservas(request):
    reservas = Reserva.objects.all()
    return render(request, 'salas/lista_reservas.html', {'reservas': reservas})


def criar_reserva(request):
    if request.method == 'POST':
        form = ReservaForm(request.POST)
        if form.is_valid():
            reserva = form.save(commit=False)
            if reserva.tem_conflito():
                messages.error(request, 'Conflito! Já existe uma reserva neste horário para esta sala.')
                return render(request, 'salas/criar_reserva.html', {'form': form})
            reserva.save()
            messages.success(request, 'Reserva criada com sucesso!')
            return redirect('lista_reservas')
    else:
        form = ReservaForm()
    return render(request, 'salas/criar_reserva.html', {'form': form})


def editar_reserva(request, id):
    reserva = get_object_or_404(Reserva, id=id)
    if request.method == 'POST':
        form = ReservaForm(request.POST, instance=reserva)
        if form.is_valid():
            reserva_atualizada = form.save(commit=False)
            if reserva_atualizada.tem_conflito():
                messages.error(request, 'Conflito! Já existe uma reserva neste horário para esta sala.')
                return render(request, 'salas/editar_reserva.html', {'form': form, 'reserva': reserva})
            reserva_atualizada.save()
            messages.success(request, 'Reserva atualizada com sucesso!')
            return redirect('lista_reservas')
    else:
        form = ReservaForm(instance=reserva)
    return render(request, 'salas/editar_reserva.html', {'form': form, 'reserva': reserva})


def deletar_reserva(request, id):
    reserva = get_object_or_404(Reserva, id=id)
    if request.method == 'POST':
        reserva.delete()
        messages.success(request, 'Reserva deletada com sucesso!')
        return redirect('lista_reservas')
    return render(request, 'salas/deletar_reserva.html', {'reserva': reserva})


def detalhes_reserva(request, id):
    reserva = get_object_or_404(Reserva, id=id)
    return render(request, 'salas/detalhes_reserva.html', {'reserva': reserva})
