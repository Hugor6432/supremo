from django.utils import timezone

from .models import RegistroAtividade


def registra(usuario, acao, objeto, descricao, organizacao=None):
    # Grava uma linha no histórico; a organização vem do objeto quando não é informada
    return RegistroAtividade.objects.create(
        usuario=usuario if getattr(usuario, 'is_authenticated', False) else None,
        organizacao=organizacao or getattr(objeto, 'organizacao', None),
        acao=acao,
        tipo_objeto=str(objeto._meta.verbose_name),
        objeto_id=objeto.pk,
        descricao=descricao,
    )


def data_hora(valor):
    return timezone.localtime(valor).strftime('%d/%m/%Y %H:%M')
