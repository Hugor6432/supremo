from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.utils import org_atual
from .models import Sala, Recurso, Recorrencia, Reserva
from .permissoes import EhOperadorParaEscrita, PodeAlterarReserva
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


class SalaDetail(SoOperadorEscreveMixin, DaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Sala
    serializer_class = SalaSerializer


# ===== RECURSOS =====

class RecursoListCreate(SoOperadorEscreveMixin, DaOrganizacaoMixin, generics.ListCreateAPIView):
    model = Recurso
    serializer_class = RecursoSerializer


class RecursoDetail(SoOperadorEscreveMixin, DaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Recurso
    serializer_class = RecursoSerializer


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

    def perform_create(self, serializer):
        # Dono e status definidos pelo sistema, como nas telas
        sala = serializer.validated_data['sala']
        serializer.save(
            organizacao=org_atual(self.request),
            criado_por=self.request.user,
            responsavel=self.request.user.username,
            status=Reserva(sala=sala).status_inicial(),
        )


class ReservaDetail(DaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Reserva
    serializer_class = ReservaSerializer
    permission_classes = [IsAuthenticated, PodeAlterarReserva]


class ReservaAcaoBase(DaOrganizacaoMixin, generics.GenericAPIView):
    # Base das ações POST que só mudam o status
    model = Reserva
    serializer_class = ReservaSerializer

    def muda_status(self, reserva, novo_status):
        reserva.status = novo_status
        reserva.save(update_fields=['status'])
        return Response(self.get_serializer(reserva).data)

    def erro(self, mensagem):
        return Response({'detail': mensagem}, status=status.HTTP_400_BAD_REQUEST)


class ReservaCancelar(ReservaAcaoBase):
    permission_classes = [IsAuthenticated, PodeAlterarReserva]

    def post(self, request, pk):
        reserva = self.get_object()
        if reserva.status == 'cancelada':
            return self.erro('Esta reserva já está cancelada.')
        return self.muda_status(reserva, 'cancelada')


class ReservaAprovar(ReservaAcaoBase):
    permission_classes = [IsAuthenticated, EhOperadorParaEscrita]
    novo_status = 'confirmada'

    def post(self, request, pk):
        reserva = self.get_object()
        if reserva.status != 'pendente':
            return self.erro('Só reservas pendentes podem ser aprovadas ou recusadas.')
        return self.muda_status(reserva, self.novo_status)


class ReservaRecusar(ReservaAprovar):
    novo_status = 'cancelada'
