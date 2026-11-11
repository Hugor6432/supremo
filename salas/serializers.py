from rest_framework import serializers

from core.utils import org_atual
from .models import Sala, Recurso, Recorrencia, Reserva


def _org_do_request(serializer):
    request = serializer.context.get('request')
    return org_atual(request) if request else None


class FiltraPorOrganizacaoMixin:
    """Os campos de relacionamento (sala, recorrencia) só aceitam IDs da
    organização do usuário. É o equivalente na API aos selects filtrados
    do formulário: um ID de outra organização vira erro 400.

    O campo organizacao NÃO está em fields: ela é gravada pela view
    (perform_create), nunca vem do JSON.
    """
    campos_da_org = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        org = _org_do_request(self)
        for campo, model in self.campos_da_org.items():
            if campo in self.fields:
                self.fields[campo].queryset = model.objects.filter(organizacao=org)


class SalaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sala
        fields = ['id', 'nome', 'capacidade', 'descricao']

    def validate_capacidade(self, value):
        if value <= 0:
            raise serializers.ValidationError("A capacidade deve ser maior que zero.")
        return value

    def validate_nome(self, value):
        # Unicidade por organização (mesma regra do SalaForm.clean_nome)
        duplicadas = Sala.objects.filter(organizacao=_org_do_request(self), nome__iexact=value)
        if self.instance:
            duplicadas = duplicadas.exclude(pk=self.instance.pk)
        if duplicadas.exists():
            raise serializers.ValidationError("Já existe uma sala com esse nome na sua organização.")
        return value


class RecursoSerializer(FiltraPorOrganizacaoMixin, serializers.ModelSerializer):
    campos_da_org = {'sala': Sala}

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


class ReservaSerializer(FiltraPorOrganizacaoMixin, serializers.ModelSerializer):
    campos_da_org = {'sala': Sala, 'recorrencia': Recorrencia}

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
