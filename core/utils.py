from django.core.exceptions import PermissionDenied

from .models import Perfil


def org_atual(request):
    # Usuário sem perfil não acessa as telas (superusuário ganha um no middleware)
    perfil = getattr(request.user, 'perfil', None)
    if perfil is None:
        raise PermissionDenied(
            "Seu usuário não está ligado a nenhuma organização. "
            "Peça ao administrador para criar o seu Perfil."
        )
    return perfil.organizacao


def papel_do_usuario(user):
    perfil = getattr(user, 'perfil', None)
    return perfil.papel if perfil else None


def eh_operador_usuario(user):
    # Operador e administrador gerenciam salas e todas as reservas
    return papel_do_usuario(user) in (Perfil.OPERADOR, Perfil.ADMINISTRADOR)


def papel_atual(request):
    return papel_do_usuario(request.user)


def eh_operador(request):
    return eh_operador_usuario(request.user)


def eh_administrador(request):
    return papel_atual(request) == Perfil.ADMINISTRADOR


def exige_operador(request):
    if not eh_operador(request):
        raise PermissionDenied("Só operadores e administradores podem fazer isso.")


def eh_administrador_completo(user):
    # Superusuário com perfil de administrador: vê tudo no dashboard
    return user.is_superuser and papel_do_usuario(user) == Perfil.ADMINISTRADOR
