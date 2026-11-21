from django import forms
from . import recorrencia
from .models import Sala, Recurso, Reserva


class SalaForm(forms.ModelForm):
    class Meta:
        model = Sala
        fields = ['nome', 'capacidade', 'descricao', 'exige_aprovacao']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da sala'}),
            'capacidade': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Capacidade'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descrição'}),
            'exige_aprovacao': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.org = org

    # Não deixa repetir o nome da sala na mesma organização
    def clean_nome(self):
        nome = self.cleaned_data['nome']
        duplicadas = Sala.objects.filter(organizacao=self.org, nome__iexact=nome)
        if self.instance.pk:
            duplicadas = duplicadas.exclude(pk=self.instance.pk)
        if duplicadas.exists():
            raise forms.ValidationError("Já existe uma sala com esse nome na sua organização.")
        return nome


# Recursos cadastrados junto com a sala; linhas em branco são ignoradas
RecursoFormSet = forms.inlineformset_factory(
    Sala, Recurso,
    fields=['nome', 'descricao'],
    extra=1,
    can_delete=True,
    can_delete_extra=False,
    widgets={
        'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome (ex.: Projetor)'}),
        'descricao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descrição (opcional)'}),
    },
)


class ReservaForm(forms.ModelForm):
    class Meta:
        model = Reserva
        # Status, criado_por e responsavel são definidos pelo sistema
        # A recorrência é criada pelo sistema a partir dos campos de repetição
        fields = ['sala', 'data_inicio', 'data_fim', 'descricao']
        widgets = {
            'sala': forms.Select(attrs={'class': 'form-control'}),
            'data_inicio': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'data_fim': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Motivo da reserva'}),
        }

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Mostra só salas da organização do usuário
        self.fields['sala'].queryset = Sala.objects.filter(organizacao=org).order_by('nome')

    # Feature 2 - Validação customizada
    def clean(self):
        cleaned_data = super().clean()
        data_inicio = self.cleaned_data.get('data_inicio')
        data_fim = self.cleaned_data.get('data_fim')

        # Só compara se as duas datas foram preenchidas corretamente
        if data_inicio and data_fim and data_fim <= data_inicio:
            raise forms.ValidationError(
                "O horário de término da reserva deve ser depois do horário de início."
            )
        return cleaned_data


class ReservaCriacaoForm(ReservaForm):
    # Criação: a pessoa escolhe se a reserva se repete
    repetir = forms.ChoiceField(
        choices=recorrencia.REPETIR, required=False, initial='nao', label="Repetir",
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    a_cada = forms.IntegerField(
        min_value=1, required=False, initial=1, label="A cada",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    )
    ate = forms.DateField(
        required=False, label="Até",
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ocorrencias = []

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data['repetir'] = cleaned_data.get('repetir') or 'nao'
        cleaned_data['a_cada'] = cleaned_data.get('a_cada') or 1
        if cleaned_data['repetir'] == 'nao' or self.errors:
            return cleaned_data
        erros, self.ocorrencias = recorrencia.planeja(
            cleaned_data['sala'], cleaned_data['data_inicio'], cleaned_data['data_fim'],
            cleaned_data['repetir'], cleaned_data['a_cada'], cleaned_data.get('ate'),
        )
        for campo, mensagem in erros:
            self.add_error(campo, mensagem)
        return cleaned_data


class PeriodoForm(forms.Form):
    # Filtro do dashboard; os dois dias entram no período
    inicio = forms.DateField(
        required=False, label="De",
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
    )
    fim = forms.DateField(
        required=False, label="Até",
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
    )

    def clean(self):
        cleaned_data = super().clean()
        inicio, fim = cleaned_data.get('inicio'), cleaned_data.get('fim')
        if inicio and fim and fim < inicio:
            raise forms.ValidationError("A data final não pode ser antes da data inicial.")
        return cleaned_data
