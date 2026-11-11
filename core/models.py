from django.contrib.auth.models import User
from django.db import models


class Organizacao(models.Model):
    nome = models.CharField(max_length=120)
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = "Organização"
        verbose_name_plural = "Organizações"


class DaOrganizacao(models.Model):
    # Base para os models que pertencem a uma organização
    organizacao = models.ForeignKey(
        'core.Organizacao',
        on_delete=models.PROTECT,
    )

    class Meta:
        abstract = True


class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    organizacao = models.ForeignKey(Organizacao, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.usuario.username} ({self.organizacao})"

    class Meta:
        verbose_name_plural = "Perfis"
