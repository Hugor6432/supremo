from django import forms
from .models import Sala, Recurso, Reserva


class SalaForm(forms.ModelForm):
    class Meta:
        model = Sala
        fields = ['nome', 'capacidade', 'descricao']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da sala'}),
            'capacidade': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Capacidade'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descrição'}),
        }


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
