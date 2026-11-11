from rest_framework import serializers
from .models import Sala, Recurso, Recorrencia, Reserva


class SalaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sala
        fields = ['id', 'nome', 'capacidade', 'descricao']

    def validate_capacidade(self, value):
        if value <= 0:
            raise serializers.ValidationError("A capacidade deve ser maior que zero.")
        return value


class RecursoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recurso
        fields = ['id', 'nome', 'descricao', 'sala']


class RecorrenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recorrencia
        fields = ['id', 'frequencia', 'data_inicio', 'data_fim', 'intervalo']

    def validate_intervalo(self, value):
        if value < 1:
            raise serializers.ValidationError("O intervalo deve ser pelo menos 1.")
        return value

    def validate(self, data):
        data_inicio = data.get('data_inicio', getattr(self.instance, 'data_inicio', None))
        data_fim = data.get('data_fim', getattr(self.instance, 'data_fim', None))
        if data_inicio and data_fim and data_fim < data_inicio:
            raise serializers.ValidationError(
                "A data de fim da recorrência não pode ser antes da data de início."
            )
        return data


class ReservaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reserva
        fields = ['id', 'sala', 'responsavel', 'data_inicio', 'data_fim',
                  'descricao', 'recorrencia', 'status']

    def validate(self, data):
        # Mesmas regras do ReservaForm e das views da P1, agora também na API.
        # Em PATCH, os campos que não vieram são lidos da reserva existente.
        def valor(campo):
            return data.get(campo, getattr(self.instance, campo, None))

        data_inicio = valor('data_inicio')
        data_fim = valor('data_fim')

        # Regra da Feature 2: término depois do início
        if data_inicio and data_fim and data_fim <= data_inicio:
            raise serializers.ValidationError(
                "O horário de término da reserva deve ser depois do horário de início."
            )

        # Conflito de horário, reaproveitando Reserva.tem_conflito()
        reserva = Reserva(
            id=getattr(self.instance, 'id', None),
            sala=valor('sala'),
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        if valor('status') != 'cancelada' and reserva.tem_conflito():
            raise serializers.ValidationError(
                "Conflito! Já existe uma reserva neste horário para esta sala."
            )
        return data
