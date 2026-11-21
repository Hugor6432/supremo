from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField, UserCreationForm
from django.contrib.auth.models import User, Group
from core.models import Organizacao, Perfil
from .models import Sala, Recurso, Reserva, Recorrencia

admin.site.unregister(Group)

admin.site.unregister(User)

class TipoUsuarioCampos(forms.Form):
    # Um campo só define o acesso ao Admin e o papel no site
    TIPO_CHOICES = [
        (Perfil.USUARIO, 'Usuário'),
        (Perfil.OPERADOR, 'Funcionário'),
        (Perfil.ADMINISTRADOR, 'Administrador'),
    ]

    tipo_usuario = forms.ChoiceField(
        choices=TIPO_CHOICES,
        widget=forms.RadioSelect,
        label="Tipo de usuário",
        help_text="Usuário e Funcionário usam só o site. Administrador também entra no Admin.",
    )
    organizacao = forms.ModelChoiceField(
        queryset=Organizacao.objects.order_by('nome'),
        required=False,
        label="Organização",
        help_text="Obrigatória para Usuário e Funcionário.",
    )

    def preenche_iniciais(self, user):
        # Superusuário é Administrador; papel administrador sem superusuário vira Funcionário
        perfil = getattr(user, 'perfil', None)
        if user.is_superuser:
            tipo = Perfil.ADMINISTRADOR
        elif perfil and perfil.papel in (Perfil.OPERADOR, Perfil.ADMINISTRADOR):
            tipo = Perfil.OPERADOR
        else:
            tipo = Perfil.USUARIO
        self.fields['tipo_usuario'].initial = tipo
        if perfil:
            self.fields['organizacao'].initial = perfil.organizacao_id

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo_usuario')
        if tipo and tipo != Perfil.ADMINISTRADOR and not cleaned_data.get('organizacao'):
            self.add_error('organizacao', "Escolha a organização para Usuário e Funcionário.")
        return cleaned_data

    def aplica_tipo(self, user):
        eh_admin = self.cleaned_data['tipo_usuario'] == Perfil.ADMINISTRADOR
        user.is_superuser = eh_admin
        user.is_staff = eh_admin

    def salva_perfil(self, user):
        # Chamado depois que o usuário já foi salvo
        organizacao = self.cleaned_data.get('organizacao')
        if organizacao is None:
            # Administrador sem organização usa só o Admin
            Perfil.objects.filter(usuario=user).delete()
            return
        Perfil.objects.update_or_create(
            usuario=user,
            defaults={'organizacao': organizacao, 'papel': self.cleaned_data['tipo_usuario']},
        )


class UsuarioForm(TipoUsuarioCampos, forms.ModelForm):
    password = ReadOnlyPasswordHashField(label="Senha", help_text='Para trocar a senha, use <a href="../password/">este formulário</a>.')

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.preenche_iniciais(self.instance)

    def save(self, commit=True):
        user = super().save(commit=False)
        self.aplica_tipo(user)
        if commit:
            user.save()
            self.salva_perfil(user)
        return user


# Criação: tudo numa tela só, senha com criptografia
class UsuarioCriacaoForm(TipoUsuarioCampos, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

    def save(self, commit=True):
        user = super().save(commit=False)
        self.aplica_tipo(user)
        if commit:
            user.save()
            self.salva_perfil(user)
        return user


class UsuarioAdmin(BaseUserAdmin):
    form = UsuarioForm
    add_form = UsuarioCriacaoForm

    fieldsets = (
        ('Informações Básicas', {'fields': ('username', 'email', 'first_name', 'last_name', 'password')}),
        ('Tipo de usuário', {'fields': ('tipo_usuario',)}),
        ('Organização do usuário', {'fields': ('organizacao',)}),
        ('Ativo', {'fields': ('is_active',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'tipo_usuario', 'organizacao'),
        }),
    )

    list_display = ('username', 'email', 'organizacao_display', 'tipo_display', 'is_active')
    list_filter = ('is_superuser', 'is_active')
    search_fields = ('username', 'email')
    readonly_fields = ()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # O Admin salva com commit=False; o Perfil precisa do usuário já salvo
        form.salva_perfil(obj)

    def tipo_display(self, obj):
        if obj.is_superuser:
            return "Administrador"
        perfil = getattr(obj, 'perfil', None)
        if perfil and perfil.papel in (Perfil.OPERADOR, Perfil.ADMINISTRADOR):
            return "Funcionário"
        return "Usuário"
    tipo_display.short_description = "Tipo"

    def organizacao_display(self, obj):
        perfil = getattr(obj, 'perfil', None)
        return perfil.organizacao if perfil else "—"
    organizacao_display.short_description = "Organização"

admin.site.register(User, UsuarioAdmin)


class ExcluidaFilter(admin.SimpleListFilter):
    title = "Excluída"
    parameter_name = 'excluida'

    def lookups(self, request, model_admin):
        return [('sim', 'Sim'), ('nao', 'Não')]

    def queryset(self, request, queryset):
        if self.value() == 'sim':
            return queryset.filter(excluida_em__isnull=False)
        if self.value() == 'nao':
            return queryset.filter(excluida_em__isnull=True)
        return queryset


class ExclusaoSuaveAdmin(admin.ModelAdmin):
    # No Admin aparecem também os excluídos, que podem ser restaurados ou apagados de vez
    actions = ['restaurar_selecionadas']

    def get_queryset(self, request):
        queryset = self.model.todos.get_queryset()
        ordering = self.get_ordering(request)
        return queryset.order_by(*ordering) if ordering else queryset

    def motivo_para_nao_restaurar(self, obj):
        return None

    @admin.action(description="Restaurar selecionadas")
    def restaurar_selecionadas(self, request, queryset):
        restauradas = 0
        for obj in queryset.filter(excluida_em__isnull=False):
            motivo = self.motivo_para_nao_restaurar(obj)
            if motivo:
                self.message_user(request, f"Não foi possível restaurar {obj}: {motivo}", messages.WARNING)
                continue
            obj.restaurar()
            restauradas += 1
        if restauradas:
            self.message_user(request, f"{restauradas} item(ns) restaurado(s).", messages.SUCCESS)


class RecursoInline(admin.TabularInline):
    model = Recurso
    extra = 1
    fields = ('nome', 'descricao')

    def get_queryset(self, request):
        return Recurso.todos.all()

@admin.register(Sala)
class SalaAdmin(ExclusaoSuaveAdmin):
    inlines = [RecursoInline]
    list_display = ('nome', 'organizacao', 'capacidade', 'exige_aprovacao', 'total_recursos',
                    'excluida_em', 'excluida_por')
    list_filter = ('organizacao', ExcluidaFilter)
    search_fields = ('nome',)
    
    def total_recursos(self, obj):
        return Recurso.todos.filter(sala=obj).count()
    total_recursos.short_description = "🔧 Recursos"

    def motivo_para_nao_restaurar(self, obj):
        if Sala.objects.filter(organizacao=obj.organizacao, nome__iexact=obj.nome).exists():
            return "já existe outra sala ativa com esse nome."
        return None

    def save_formset(self, request, form, formset, change):
        # Recursos ficam na organização da sala
        recursos = formset.save(commit=False)
        for recurso in recursos:
            recurso.organizacao = form.instance.organizacao
            recurso.save()
        for recurso in formset.deleted_objects:
            recurso.delete()

@admin.register(Recurso)
class RecursoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'sala', 'organizacao', 'descricao')
    list_filter = ('organizacao', 'sala')
    search_fields = ('nome', 'sala__nome')
    exclude = ('organizacao',)

    def get_queryset(self, request):
        return Recurso.todos.all()

    def save_model(self, request, obj, form, change):
        obj.organizacao = obj.sala.organizacao
        super().save_model(request, obj, form, change)


@admin.register(Recorrencia)
class RecorrenciaAdmin(admin.ModelAdmin):
    list_display = ('frequencia', 'organizacao', 'data_inicio', 'data_fim', 'intervalo')
    list_filter = ('organizacao', 'frequencia')
    date_hierarchy = 'data_inicio'


@admin.register(Reserva)
class ReservaAdmin(ExclusaoSuaveAdmin):
    list_display = ('sala', 'organizacao', 'reservado_por', 'email_de_quem_reservou', 'data_inicio', 'status',
                    'tem_conflito', 'excluida_em', 'excluida_por')
    list_filter = ('organizacao', 'status', 'sala', 'data_inicio', ExcluidaFilter)
    search_fields = ('responsavel', 'sala__nome', 'criado_por__username', 'criado_por__email')
    date_hierarchy = 'data_inicio'
    fieldsets = (
        ('Informações Básicas', {'fields': ('sala', 'responsavel', 'descricao')}),
        ('Datas e Horários', {'fields': ('data_inicio', 'data_fim')}),
        ('Recorrência e Status', {'fields': ('recorrencia', 'status', 'criado_por')}),
    )
    readonly_fields = ('criado_por',)
    list_select_related = ('sala', 'organizacao', 'criado_por')

    def motivo_para_nao_restaurar(self, obj):
        if obj.sala.excluida_em:
            return "a sala dela está excluída."
        if obj.status != 'cancelada' and obj.tem_conflito():
            return "o horário já foi ocupado por outra reserva."
        return None

    @admin.display(description="Reservado por", ordering='criado_por__username')
    def reservado_por(self, obj):
        # Reservas antigas sem conta mostram o texto do campo responsavel
        return obj.criado_por.username if obj.criado_por else obj.responsavel

    @admin.display(description="E-mail", ordering='criado_por__email')
    def email_de_quem_reservou(self, obj):
        if obj.criado_por is None:
            return "—"
        return obj.criado_por.email or "sem e-mail"
    
    def save_model(self, request, obj, form, change):
        obj.organizacao = obj.sala.organizacao
        if not change:
            obj.criado_por = request.user
        if obj.tem_conflito():
            raise ValueError('Existe conflito com outra reserva neste horário!')
        super().save_model(request, obj, form, change)
