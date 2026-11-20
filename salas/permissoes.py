from rest_framework import permissions

from core.utils import eh_operador_usuario
from .models import Reserva

MSG_SO_OPERADOR = "Só operadores e administradores podem fazer isso."


class EhOperadorParaEscrita(permissions.BasePermission):
    # Leitura para todos da organização; escrita só para operador e administrador
    message = MSG_SO_OPERADOR

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return eh_operador_usuario(request.user)


class PodeAlterarReserva(permissions.BasePermission):
    # Mesmas regras das telas: dono + 24h para usuário; operador pode tudo
    message = Reserva.MSG_NAO_E_DONO

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.method == 'DELETE':
            self.message = MSG_SO_OPERADOR
            return eh_operador_usuario(request.user)
        if not obj.pode_mexer(request.user):
            self.message = Reserva.MSG_NAO_E_DONO
            return False
        if not obj.pode_alterar(request.user):
            self.message = Reserva.MSG_24H
            return False
        return True
