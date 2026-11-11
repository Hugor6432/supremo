from rest_framework import serializers
from .models import Sala


class SalaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sala
        fields = ['id', 'nome', 'capacidade', 'descricao']

    def validate_capacidade(self, value):
        if value <= 0:
            raise serializers.ValidationError("A capacidade deve ser maior que zero.")
        return value
