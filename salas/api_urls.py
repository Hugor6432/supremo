from django.urls import path
from . import api_views

urlpatterns = [
    path('salas/', api_views.SalaListCreate.as_view(), name='api_salas'),
    path('salas/<int:pk>/', api_views.SalaDetail.as_view(), name='api_sala_detalhe'),

    path('recursos/', api_views.RecursoListCreate.as_view(), name='api_recursos'),
    path('recursos/<int:pk>/', api_views.RecursoDetail.as_view(), name='api_recurso_detalhe'),

    path('recorrencias/', api_views.RecorrenciaListCreate.as_view(), name='api_recorrencias'),
    path('recorrencias/<int:pk>/', api_views.RecorrenciaDetail.as_view(), name='api_recorrencia_detalhe'),

    path('reservas/', api_views.ReservaListCreate.as_view(), name='api_reservas'),
    path('reservas/<int:pk>/', api_views.ReservaDetail.as_view(), name='api_reserva_detalhe'),
]
