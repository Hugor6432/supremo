from .utils import papel_do_usuario, eh_operador_usuario


def papel(request):
    # Deixa o papel disponível em todos os templates
    return {
        'papel': papel_do_usuario(request.user),
        'eh_operador': eh_operador_usuario(request.user),
    }
