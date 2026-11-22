from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from .models import Organizacao, Perfil

MSG_ESCOLHA_ORG = "Escolha a sua organização para usar o site"


class PerfilSuperusuarioMiddleware:
    # Superusuário criado com "createsuperuser" não tem Perfil.
    # Ao entrar no site, ganha um Perfil de administrador na organização.

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if (
            user is not None
            and user.is_authenticated
            and user.is_superuser
            and getattr(user, 'perfil', None) is None
            and not self.caminho_livre(request.path_info)
        ):
            resposta = self.cria_perfil(request, user)
            if resposta is not None:
                return resposta
        return self.get_response(request)

    @staticmethod
    def caminho_livre(caminho):
        # Admin, login/logout e arquivos estáticos não precisam de Perfil
        livres = [reverse('admin:index'), '/contas/']
        if settings.STATIC_URL:
            livres.append('/' + settings.STATIC_URL.lstrip('/'))
        return any(caminho.startswith(p) for p in livres)

    @staticmethod
    def cria_perfil(request, user):
        organizacoes = list(Organizacao.objects.all()[:2])
        if len(organizacoes) > 1:
            messages.info(request, MSG_ESCOLHA_ORG)
            return redirect('admin:auth_user_change', user.pk)
        if organizacoes:
            org = organizacoes[0]
        else:
            org = Organizacao.objects.create(nome="Minha Organização")
        Perfil.objects.create(usuario=user, organizacao=org, papel=Perfil.ADMINISTRADOR)
        return None
