from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Organizacao, Perfil


class CadastroForm(UserCreationForm):
    # Cadastro público: a conta sempre nasce como usuário comum
    email = forms.EmailField(label="E-mail")
    organizacao = forms.ModelChoiceField(
        queryset=Organizacao.objects.order_by('nome'),
        label="Organização",
        empty_label="Escolha a sua organização",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Com uma organização só, ela já vem selecionada
        organizacoes = self.fields['organizacao'].queryset
        if organizacoes.count() == 1:
            self.fields['organizacao'].initial = organizacoes.first().pk
        for campo in self.fields.values():
            campo.widget.attrs['class'] = 'form-select' if isinstance(campo.widget, forms.Select) else 'form-control'

    def save(self, commit=True):
        user = super().save(commit=False)
        # Nada que venha do formulário muda o nível de acesso
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
            Perfil.objects.create(
                usuario=user,
                organizacao=self.cleaned_data['organizacao'],
                papel=Perfil.USUARIO,
            )
        return user
