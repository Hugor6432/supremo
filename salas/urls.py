from django.urls import path
from . import views

urlpatterns = [
    # Salas
    path('salas/', views.lista_salas, name='lista_salas'),
    path('salas/criar/', views.criar_sala, name='criar_sala'),
    path('salas/<int:id>/', views.detalhes_sala, name='detalhes_sala'),
    path('salas/<int:id>/editar/', views.editar_sala, name='editar_sala'),
    path('salas/<int:id>/deletar/', views.deletar_sala, name='deletar_sala'),
    
    # Reservas
    path('reservas/', views.lista_reservas, name='lista_reservas'),
    path('reservas/criar/', views.criar_reserva, name='criar_reserva'),
    path('reservas/<int:id>/editar/', views.editar_reserva, name='editar_reserva'),
    path('reservas/<int:id>/deletar/', views.deletar_reserva, name='deletar_reserva'),
    path('reservas/<int:id>/cancelar/', views.cancelar_reserva, name='cancelar_reserva'),
    path('reservas/<int:id>/cancelar-serie/', views.cancelar_serie, name='cancelar_serie'),
    path('reservas/<int:id>/aprovar/', views.aprovar_reserva, name='aprovar_reserva'),
    path('reservas/<int:id>/recusar/', views.recusar_reserva, name='recusar_reserva'),
    path('reservas/<int:id>/', views.detalhes_reserva, name='detalhes_reserva'),
]
