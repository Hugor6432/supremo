from rest_framework import generics

from core.utils import org_atual
from .models import Sala, Recurso, Recorrencia, Reserva
from .serializers import (
    SalaSerializer, RecursoSerializer, RecorrenciaSerializer, ReservaSerializer,
)


class DaOrganizacaoMixin:
    """Isolamento por organização na API (mesma regra de ouro das telas).

    - get_queryset: lista/detalha só registros da organização do usuário
      (ID de outra organização responde 404).
    - perform_create: a organização vem do usuário logado, nunca do JSON.
    """
    model = None

    def get_queryset(self):
        return self.model.objects.filter(organizacao=org_atual(self.request))

    def perform_create(self, serializer):
        serializer.save(organizacao=org_atual(self.request))


# ===== SALAS =====

class SalaListCreate(DaOrganizacaoMixin, generics.ListCreateAPIView):
    model = Sala
    serializer_class = SalaSerializer


class SalaDetail(DaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Sala
    serializer_class = SalaSerializer


# ===== RECURSOS =====

class RecursoListCreate(DaOrganizacaoMixin, generics.ListCreateAPIView):
    model = Recurso
    serializer_class = RecursoSerializer


class RecursoDetail(DaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Recurso
    serializer_class = RecursoSerializer


# ===== RECORRÊNCIAS =====

class RecorrenciaListCreate(DaOrganizacaoMixin, generics.ListCreateAPIView):
    model = Recorrencia
    serializer_class = RecorrenciaSerializer


class RecorrenciaDetail(DaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Recorrencia
    serializer_class = RecorrenciaSerializer


# ===== RESERVAS =====

class ReservaListCreate(DaOrganizacaoMixin, generics.ListCreateAPIView):
    model = Reserva
    serializer_class = ReservaSerializer


class ReservaDetail(DaOrganizacaoMixin, generics.RetrieveUpdateDestroyAPIView):
    model = Reserva
    serializer_class = ReservaSerializer
