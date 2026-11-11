from django.urls import path
from .api_views import SalaListCreate, SalaDetail

urlpatterns = [
    path('salas/', SalaListCreate.as_view(), name='api_salas'),
    path('salas/<int:pk>/', SalaDetail.as_view(), name='api_sala_detalhe'),
]
