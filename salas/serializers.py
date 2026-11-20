from rest_framework import serializers

from core.utils import org_atual
from . import recorrencia as series
from .models import Sala, Recurso, Recorrencia, Reserva


def _org_do_request(serializer):
    request = serializer.context.get('request')
    return org_atual(request) if request else None


class FiltraPorOrganizacaoMixin:
    # Sala e recorrência só aceitam registros da organização do usuário
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
        fields = ['id', 'nome', 'capacidade', 'descricao', 'exige_aprovacao']

    def validate_capacidade(self, value):
        if value <= 0:
            raise serializers.ValidationError("A capacidade deve ser maior que zero.")
        return value

    def validate_nome(self, value):
        # Não deixa repetir o nome da sala na mesma organização
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
    campos_da_org = {'sala': Sala}
    # Repetição: só ao criar, como no formulário do site
    repetir = serializers.ChoiceField(choices=series.REPETIR, write_only=True, required=False, default='nao')
    a_cada = serializers.IntegerField(write_only=True, required=False, min_value=1, default=1)
    ate = serializers.DateField(write_only=True, required=False, allow_null=True, default=None)
    criado_por_usuario = serializers.SerializerMethodField()
    criado_por_email = serializers.SerializerMethodField()

    class Meta:
        model = Reserva
        fields = ['id', 'sala', 'responsavel', 'data_inicio', 'data_fim',
                  'descricao', 'recorrencia', 'status', 'criado_por',
                  'criado_por_usuario', 'criado_por_email', 'repetir', 'a_cada', 'ate']
        # Status muda pelas ações cancelar/aprovar/recusar; responsável vem da conta
        read_only_fields = ['status', 'criado_por', 'responsavel', 'recorrencia']

    def get_criado_por_usuario(self, obj):
        return obj.criado_por.username if obj.criado_por else None

    def get_criado_por_email(self, obj):
        return obj.criado_por.email if obj.criado_por else None

    def validate(self, data):
        # No PATCH, usa os valores atuais da reserva para os campos que não vieram
        def valor(campo):
            return data.get(campo, getattr(self.instance, campo, None))

        data_inicio = valor('data_inicio')
        data_fim = valor('data_fim')

        # Término depois do início
        if data_inicio and data_fim and data_fim <= data_inicio:
            raise serializers.ValidationError(
                "O horário de término da reserva deve ser depois do horário de início."
            )

        # Série: confere limites e conflito em todas as datas
        self.ocorrencias = []
        if self.instance is None and data.get('repetir', 'nao') != 'nao':
            erros, self.ocorrencias = series.planeja(
                valor('sala'), data_inicio, data_fim, data['repetir'], data.get('a_cada') or 1, data.get('ate'),
            )
            if erros:
                raise serializers.ValidationError({campo or 'non_field_errors': [mensagem] for campo, mensagem in erros})
            return data

        # Conflito de horário
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

    def _sem_repeticao(self, validated_data):
        for campo in ('repetir', 'a_cada', 'ate'):
            validated_data.pop(campo, None)
        return validated_data

    def create(self, validated_data):
        return super().create(self._sem_repeticao(validated_data))

    def update(self, instance, validated_data):
        # Na edição a recorrência não muda
        return super().update(instance, self._sem_repeticao(validated_data))
