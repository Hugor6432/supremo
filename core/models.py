from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


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


class ExclusaoSuave(models.Model):
    # Excluir pelo site só marca o registro; o Admin pode restaurar ou apagar de vez
    excluida_em = models.DateTimeField("Excluída em", null=True, blank=True)
    excluida_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name="Excluída por",
    )

    class Meta:
        abstract = True

    def excluir(self, usuario):
        self.excluida_em = timezone.now()
        self.excluida_por = usuario
        self.save(update_fields=['excluida_em', 'excluida_por'])

    def restaurar(self):
        self.excluida_em = None
        self.excluida_por = None
        self.save(update_fields=['excluida_em', 'excluida_por'])


class Perfil(models.Model):
    ADMINISTRADOR = 'administrador'
    OPERADOR = 'operador'
    USUARIO = 'usuario'
    PAPEIS = [
        (ADMINISTRADOR, 'Administrador'),
        (OPERADOR, 'Funcionário'),
        (USUARIO, 'Usuário'),
    ]

    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    organizacao = models.ForeignKey(Organizacao, on_delete=models.PROTECT)
    papel = models.CharField(max_length=20, choices=PAPEIS, default=USUARIO)

    def __str__(self):
        return f"{self.usuario.username} ({self.organizacao})"

    class Meta:
        verbose_name_plural = "Perfis"


class RegistroAtividade(models.Model):
    # Histórico do que cada pessoa fez no site e na API
    ACOES = [
        ('criou', 'Criou'),
        ('editou', 'Editou'),
        ('cancelou', 'Cancelou'),
        ('aprovou', 'Aprovou'),
        ('recusou', 'Recusou'),
        ('excluiu', 'Excluiu'),
        ('adicionou', 'Adicionou'),
        ('removeu', 'Removeu'),
        ('cadastrou', 'Cadastrou conta'),
    ]

    quando = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    organizacao = models.ForeignKey(Organizacao, on_delete=models.SET_NULL, null=True, blank=True)
    acao = models.CharField("Ação", max_length=20, choices=ACOES)
    tipo_objeto = models.CharField("Tipo do objeto", max_length=50)
    objeto_id = models.PositiveIntegerField("ID do objeto", null=True, blank=True)
    descricao = models.TextField("Descrição")

    def __str__(self):
        return self.descricao

    class Meta:
        verbose_name = "Registro de atividade"
        verbose_name_plural = "Registro de atividades"
        ordering = ['-quando']
