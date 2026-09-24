from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Sala, Reserva
from .forms import ReservaForm, SalaForm


# ===== VIEWS DE SALAS =====

def lista_salas(request):
    salas = Sala.objects.all()
    return render(request, 'salas/lista_salas.html', {'salas': salas})


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
