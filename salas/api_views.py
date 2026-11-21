from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import eh_administrador_completo, org_atual
from . import atividades, dashboard as metricas, recorrencia
from .models import Sala, Recurso, Recorrencia, Reserva
from .forms import PeriodoForm
from .permissoes import EhOperadorParaEscrita, PodeAlterarReserva, PodeVerDashboard
from .serializers import (
    SalaSerializer, RecursoSerializer, RecorrenciaSerializer, ReservaSerializer,
)


class DaOrganizacaoMixin:
    # Mostra e grava só dados da organização do usuário
    model = None

    def get_queryset(self):
        return self.model.objects.filter(organizacao=org_atual(self.request))

    def perform_create(self, serializer):
        serializer.save(organizacao=org_atual(self.request))


class SoOperadorEscreveMixin:
    # Salas, recursos e recorrências: escrita só para operador e administrador
    permission_classes = [IsAuthenticated, EhOperadorParaEscrita]


# ===== SALAS =====

class SalaListCreate(SoOperadorEscreveMixin, DaOrganizacaoMixin, generics.ListCreateAPIView):
    model = Sala
    serializer_class = SalaSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        sala = serializer.save(organizacao=org_atual(self.request))
        atividades.sala(self.request.user, 'criou', sala)


class SalaDetail(SoOperadorEscreveMixin, DaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Sala
    serializer_class = SalaSerializer

    @transaction.atomic
    def perform_update(self, serializer):
        sala = serializer.save()
        atividades.sala(self.request.user, 'editou', sala)

    @transaction.atomic
    def perform_destroy(self, instance):
        # Como no site: só marca como excluída
        instance.excluir(self.request.user)
        atividades.sala(self.request.user, 'excluiu', instance)


# ===== RECURSOS =====

class RecursoListCreate(SoOperadorEscreveMixin, DaOrganizacaoMixin, generics.ListCreateAPIView):
    model = Recurso
    serializer_class = RecursoSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        recurso = serializer.save(organizacao=org_atual(self.request))
        atividades.recurso(self.request.user, 'adicionou', recurso)


class RecursoDetail(SoOperadorEscreveMixin, DaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Recurso
    serializer_class = RecursoSerializer

    @transaction.atomic
    def perform_update(self, serializer):
        recurso = serializer.save()
        atividades.recurso(self.request.user, 'editou', recurso)

    @transaction.atomic
    def perform_destroy(self, instance):
        atividades.recurso(self.request.user, 'removeu', instance)
        instance.delete()


# ===== RECORRÊNCIAS =====

class RecorrenciaListCreate(SoOperadorEscreveMixin, DaOrganizacaoMixin, generics.ListCreateAPIView):
    model = Recorrencia
    serializer_class = RecorrenciaSerializer


class RecorrenciaDetail(SoOperadorEscreveMixin, DaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Recorrencia
    serializer_class = RecorrenciaSerializer


# ===== RESERVAS =====

class ReservaListCreate(DaOrganizacaoMixin, generics.ListCreateAPIView):
    model = Reserva
    serializer_class = ReservaSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        if dados.get('repetir', 'nao') == 'nao':
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        # Série: devolve a recorrência criada e todas as reservas
        serie, reservas = recorrencia.cria_serie(
            request.user, org_atual(request), dados['sala'], serializer.ocorrencias,
            dados['repetir'], dados.get('a_cada') or 1, dados['ate'], dados.get('descricao') or '',
        )
        corpo = {
            'recorrencia': serie.id,
            'total': len(reservas),
            'reservas': ReservaSerializer(reservas, many=True, context=self.get_serializer_context()).data,
        }
        return Response(corpo, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def perform_create(self, serializer):
        # Dono e status definidos pelo sistema, como nas telas
        sala = serializer.validated_data['sala']
        reserva = serializer.save(
            organizacao=org_atual(self.request),
            criado_por=self.request.user,
            responsavel=self.request.user.username,
            status=Reserva(sala=sala).status_inicial(),
        )
        atividades.reserva(self.request.user, 'criou', reserva)


class ReservaDetail(DaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Reserva
    serializer_class = ReservaSerializer
    permission_classes = [IsAuthenticated, PodeAlterarReserva]

    @transaction.atomic
    def perform_update(self, serializer):
        reserva = serializer.save()
        atividades.reserva(self.request.user, 'editou', reserva)

    @transaction.atomic
    def perform_destroy(self, instance):
        # Como no site: só marca como excluída
        instance.excluir(self.request.user)
        atividades.reserva(self.request.user, 'excluiu', instance)


class ReservaAcaoBase(DaOrganizacaoMixin, generics.GenericAPIView):
    # Base das ações POST que só mudam o status
    model = Reserva
    serializer_class = ReservaSerializer

    @transaction.atomic
    def muda_status(self, reserva, novo_status, acao):
        reserva.status = novo_status
        reserva.save(update_fields=['status'])
        atividades.reserva(self.request.user, acao, reserva)
        return Response(self.get_serializer(reserva).data)

    def erro(self, mensagem):
        return Response({'detail': mensagem}, status=status.HTTP_400_BAD_REQUEST)


class ReservaCancelar(ReservaAcaoBase):
    permission_classes = [IsAuthenticated, PodeAlterarReserva]

    def post(self, request, pk):
        reserva = self.get_object()
        if reserva.status == 'cancelada':
            return self.erro('Esta reserva já está cancelada.')
        return self.muda_status(reserva, 'cancelada', 'cancelou')


class ReservaAprovar(ReservaAcaoBase):
    permission_classes = [IsAuthenticated, EhOperadorParaEscrita]
    novo_status = 'confirmada'
    acao = 'aprovou'

    def post(self, request, pk):
        reserva = self.get_object()
        if reserva.status != 'pendente':
            return self.erro('Só reservas pendentes podem ser aprovadas ou recusadas.')
        return self.muda_status(reserva, self.novo_status, self.acao)


class ReservaRecusar(ReservaAprovar):
    novo_status = 'cancelada'
    acao = 'recusou'


# ===== DASHBOARD =====

class Dashboard(APIView):
    # Mesmos números da tela; a série por mês só vai para o administrador
    permission_classes = [IsAuthenticated, PodeVerDashboard]

    def get(self, request):
        form = PeriodoForm(request.query_params or None)
        inicio = fim = None
        if form.is_bound:
            if not form.is_valid():
                return Response({'erros': form.errors}, status=status.HTTP_400_BAD_REQUEST)
            inicio, fim = form.cleaned_data.get('inicio'), form.cleaned_data.get('fim')
        completo = eh_administrador_completo(request.user)
        dados = metricas.resumo(org_atual(request), inicio, fim, com_serie=completo)
        dados['periodo'] = {'inicio': inicio, 'fim': fim}
        return Response(dados)
