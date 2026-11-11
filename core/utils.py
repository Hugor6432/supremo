from django.core.exceptions import PermissionDenied


def org_atual(request):
    """Um único lugar que define a organização do usuário logado.

    Nunca confie na organização vinda da URL ou do formulário: ela vem
    sempre do Perfil do usuário.

    Usuário sem Perfil (ex.: superusuário criado com createsuperuser)
    recebe 403 em vez de quebrar com RelatedObjectDoesNotExist.
    O comportamento definitivo (criar perfil, redirecionar ou bloquear)
    será decidido na Aula 15.
    """
    perfil = getattr(request.user, 'perfil', None)
    if perfil is None:
        raise PermissionDenied(
            "Seu usuário não está ligado a nenhuma organização. "
            "Peça ao administrador para criar o seu Perfil."
        )
    return perfil.organizacao
