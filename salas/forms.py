from django import forms
from .models import Sala, Recorrencia, Reserva


class SalaForm(forms.ModelForm):
    class Meta:
        model = Sala
        fields = ['nome', 'capacidade', 'descricao']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da sala'}),
            'capacidade': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Capacidade'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descrição'}),
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


class ReservaForm(forms.ModelForm):
    class Meta:
        model = Reserva
        fields = ['sala', 'responsavel', 'data_inicio', 'data_fim', 'descricao', 'recorrencia', 'status']
        widgets = {
            'sala': forms.Select(attrs={'class': 'form-control'}),
            'responsavel': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu nome'}),
            'data_inicio': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'data_fim': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Motivo da reserva'}),
            'recorrencia': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Mostra só salas e recorrências da organização do usuário
        self.fields['sala'].queryset = Sala.objects.filter(organizacao=org).order_by('nome')
        self.fields['recorrencia'].queryset = Recorrencia.objects.filter(organizacao=org)

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
