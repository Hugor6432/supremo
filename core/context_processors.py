from .utils import papel_do_usuario, eh_operador_usuario


def papel(request):
    return {
        'papel': papel_do_usuario(request.user),
        'eh_operador': eh_operador_usuario(request.user),
    }
