from django.contrib.auth.models import User
from django.db import models


class Organizacao(models.Model):
    """O "inquilino" do sistema: a empresa/escola dona das salas e reservas."""
    nome = models.CharField(max_length=120)
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Organização"
        verbose_name_plural = "Organizações"


class DaOrganizacao(models.Model):
    """Base abstrata: todo model de negócio herda e ganha a FK para a organização.

    abstract = True -> o Django não cria tabela para esta classe;
    o campo é copiado para cada model filho.
    """
    organizacao = models.ForeignKey(
        'core.Organizacao',
        on_delete=models.PROTECT,
    )

    class Meta:
        abstract = True


class Perfil(models.Model):
    """Liga o usuário do Django à organização dele."""
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    organizacao = models.ForeignKey(Organizacao, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.usuario.username} ({self.organizacao})"

    class Meta:
        verbose_name_plural = "Perfis"
