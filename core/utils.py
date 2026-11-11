from django.core.exceptions import PermissionDenied


def org_atual(request):
    # Usuário sem perfil (ex.: superusuário) não acessa as telas
    perfil = getattr(request.user, 'perfil', None)
    if perfil is None:
        raise PermissionDenied(
            "Seu usuário não está ligado a nenhuma organização. "
            "Peça ao administrador para criar o seu Perfil."
        )
    return perfil.organizacao
