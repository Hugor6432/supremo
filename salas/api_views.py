from rest_framework import generics
from .models import Sala, Recurso, Recorrencia, Reserva
from .serializers import (
    SalaSerializer, RecursoSerializer, RecorrenciaSerializer, ReservaSerializer,
)


# ===== SALAS =====

class SalaListCreate(generics.ListCreateAPIView):
    queryset = Sala.objects.all()
    serializer_class = SalaSerializer


class SalaDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Sala.objects.all()
    serializer_class = SalaSerializer


# ===== RECURSOS =====

class RecursoListCreate(generics.ListCreateAPIView):
    queryset = Recurso.objects.all()
    serializer_class = RecursoSerializer


class RecursoDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Recurso.objects.all()
    serializer_class = RecursoSerializer


# ===== RECORRÊNCIAS =====

class RecorrenciaListCreate(generics.ListCreateAPIView):
    queryset = Recorrencia.objects.all()
    serializer_class = RecorrenciaSerializer


class RecorrenciaDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Recorrencia.objects.all()
    serializer_class = RecorrenciaSerializer


# ===== RESERVAS =====

class ReservaListCreate(generics.ListCreateAPIView):
    queryset = Reserva.objects.all()
    serializer_class = ReservaSerializer


class ReservaDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Reserva.objects.all()
    serializer_class = ReservaSerializer
