from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.shortcuts import redirect, render

from .forms import CadastroForm


def cadastro(request):
    # Quem já está logado não precisa criar conta
    if request.user.is_authenticated:
        return redirect('lista_salas')
    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            # Usuário e Perfil são criados juntos ou nenhum dos dois
            with transaction.atomic():
                user = form.save()
            login(request, user)
            messages.success(request, 'Conta criada! Você já pode reservar salas.')
            return redirect('lista_salas')
    else:
        form = CadastroForm()
    return render(request, 'registration/cadastro.html', {'form': form})
