from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import DaOrganizacao, ExclusaoSuave
from core.utils import eh_operador_usuario


class SalasAtivas(models.Manager):
    # Salas excluídas pelo site somem de todas as telas e da API
    def get_queryset(self):
        return super().get_queryset().filter(excluida_em__isnull=True)


class RecursosAtivos(models.Manager):
    # Recursos de sala excluída também somem
    def get_queryset(self):
        return super().get_queryset().filter(sala__excluida_em__isnull=True)


class ReservasAtivas(models.Manager):
    # Reserva excluída, ou de sala excluída, some e não bloqueia horário
    def get_queryset(self):
        return super().get_queryset().filter(excluida_em__isnull=True, sala__excluida_em__isnull=True)


class Sala(DaOrganizacao, ExclusaoSuave):
    nome = models.CharField(max_length=100)
    capacidade = models.IntegerField()
    descricao = models.TextField(blank=True, null=True)
    exige_aprovacao = models.BooleanField(
        default=False,
        help_text="Reservas novas ficam pendentes até um operador aprovar.",
    )

    objects = SalasAtivas()
    todos = models.Manager()
    
    def __str__(self):
        return f"{self.nome} ({self.capacidade} pessoas)"
    
    class Meta:
        verbose_name_plural = "Salas"
        constraints = [
            # Vale só entre salas ativas: uma sala excluída libera o nome
            models.UniqueConstraint(
                fields=['organizacao', 'nome'],
                condition=models.Q(excluida_em__isnull=True),
                name='sala_nome_unico_por_org',
            ),
        ]


class Recurso(DaOrganizacao):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    sala = models.ForeignKey(Sala, on_delete=models.CASCADE, related_name='recursos')

    objects = RecursosAtivos()
    todos = models.Manager()
    
    def __str__(self):
        return f"{self.nome} - {self.sala.nome}"


class Recorrencia(DaOrganizacao):
    FREQUENCIAS = [
        ('diaria', 'Diária'),
        ('semanal', 'Semanal'),
        ('mensal', 'Mensal'),
    ]
    
    frequencia = models.CharField(max_length=20, choices=FREQUENCIAS)
    data_inicio = models.DateField()
    data_fim = models.DateField(blank=True, null=True)
    intervalo = models.IntegerField(default=1, help_text="A cada quantos dias/semanas/meses?")
    
    def __str__(self):
        return f"{self.get_frequencia_display()} - A cada {self.intervalo}"

    @property
    def resumo(self):
        # Ex.: "semanal, a cada 1, até 18/12"
        texto = f"{self.get_frequencia_display().lower()}, a cada {self.intervalo}"
        if self.data_fim:
            texto += f", até {self.data_fim.strftime('%d/%m')}"
        return texto

    @property
    def rotulo(self):
        return f"Recorrente ({self.resumo})"
    
    class Meta:
        verbose_name = "recorrência"
        verbose_name_plural = "Recorrências"


class Reserva(DaOrganizacao, ExclusaoSuave):
    STATUSOS = [
        ('pendente', 'Pendente'),
        ('confirmada', 'Confirmada'),
        ('cancelada', 'Cancelada'),
    ]
    
    sala = models.ForeignKey(Sala, on_delete=models.CASCADE, related_name='reservas')
    data_inicio = models.DateTimeField()
    data_fim = models.DateTimeField()
    responsavel = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    recorrencia = models.ForeignKey(Recorrencia, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUSOS, default='pendente')
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservas_criadas',
    )

    objects = ReservasAtivas()
    todos = models.Manager()

    MSG_24H = "Só é possível editar ou cancelar a reserva com mais de 24 horas de antecedência."
    MSG_NAO_E_DONO = "Você só pode editar ou cancelar as reservas que você criou."
    
    def __str__(self):
        return f"{self.sala.nome} - {self.data_inicio.strftime('%d/%m/%Y %H:%M')}"

    @property
    def responsavel_exibicao(self):
        # Conta de quem reservou; reservas antigas mostram o texto do campo responsavel
        if self.criado_por_id is None:
            return self.responsavel
        return f"{self.criado_por.username} · {self.criado_por.email or 'sem e-mail'}"

    def status_inicial(self):
        # Sala com aprovação começa pendente; as outras já nascem confirmadas
        return 'pendente' if self.sala.exige_aprovacao else 'confirmada'

    def faltam_mais_de_24h(self):
        return self.data_inicio - timezone.now() > timedelta(hours=24)

    def eh_dono(self, user):
        return self.criado_por_id is not None and self.criado_por_id == user.id

    def pode_mexer(self, user):
        # Operador mexe em qualquer reserva; usuário só nas próprias
        return eh_operador_usuario(user) or self.eh_dono(user)

    def pode_alterar(self, user):
        # Editar e cancelar: usuário precisa de mais de 24h de antecedência
        if eh_operador_usuario(user):
            return True
        return self.eh_dono(user) and self.faltam_mais_de_24h()
    
    def tem_conflito(self):
        conflitantes = Reserva.objects.filter(
            organizacao_id=self.sala.organizacao_id,
            sala=self.sala,
            status__in=['confirmada', 'pendente']
        ).exclude(id=self.id)
        
        for reserva in conflitantes:
            if not (self.data_fim <= reserva.data_inicio or self.data_inicio >= reserva.data_fim):
                return True
        return False
    
    class Meta:
        verbose_name_plural = "Reservas"
        ordering = ['-data_inicio']
        # Listas, conflito e dashboard filtram por data e status
        indexes = [
            models.Index(fields=['data_inicio'], name='reserva_data_inicio_idx'),
            models.Index(fields=['status'], name='reserva_status_idx'),
        ]
