from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User, Group
from core.models import Perfil
from .models import Sala, Recurso, Reserva, Recorrencia

# Remove Grupos do admin
admin.site.unregister(Group)

# Unregistar User primeiro
admin.site.unregister(User)

# Formulário customizado para Usuário
class UsuarioForm(forms.ModelForm):
    TIPO_CHOICES = [
        ('usuario', '👤 Usuário Normal'),
        ('admin', '🔐 Admin (Superuser)'),
    ]
    
    tipo_usuario = forms.ChoiceField(
        choices=TIPO_CHOICES,
        widget=forms.RadioSelect,
        label="Tipo de Usuário"
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password', 'is_active')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.is_superuser:
                self.fields['tipo_usuario'].initial = 'admin'
            else:
                self.fields['tipo_usuario'].initial = 'usuario'
    
    def save(self, commit=True):
        user = super().save(commit=False)
        tipo = self.cleaned_data.get('tipo_usuario')
        
        if tipo == 'admin':
            user.is_superuser = True
            user.is_staff = True
        else:
            user.is_superuser = False
            user.is_staff = False
        
        if commit:
            user.save()
        return user

# Perfil (organização do usuário) editado na mesma tela do usuário
class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name = "Organização do usuário"
    verbose_name_plural = "Organização do usuário"


# Customizar User Admin
class UsuarioAdmin(BaseUserAdmin):
    form = UsuarioForm
    inlines = [PerfilInline]
    
    fieldsets = (
        ('Informações Básicas', {'fields': ('username', 'email', 'first_name', 'last_name', 'password')}),
        ('Tipo de Usuário', {'fields': ('tipo_usuario',)}),
        ('Ativo', {'fields': ('is_active',)}),
    )
    
    list_display = ('username', 'email', 'organizacao_display', 'tipo_display', 'is_active')
    list_filter = ('is_superuser', 'is_active')
    search_fields = ('username', 'email')
    readonly_fields = ()
    
    def tipo_display(self, obj):
        if obj.is_superuser:
            return "🔐 Admin"
        else:
            return "👤 Usuário Normal"
    tipo_display.short_description = "Tipo"

    def organizacao_display(self, obj):
        perfil = getattr(obj, 'perfil', None)
        return perfil.organizacao if perfil else "—"
    organizacao_display.short_description = "Organização"

# Registrar User customizado
admin.site.register(User, UsuarioAdmin)


class RecursoInline(admin.TabularInline):
    model = Recurso
    extra = 1
    fields = ('nome', 'descricao')

@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    inlines = [RecursoInline]
    list_display = ('nome', 'organizacao', 'capacidade', 'total_recursos')
    list_filter = ('organizacao',)
    search_fields = ('nome',)
    
    def total_recursos(self, obj):
        return obj.recursos.count()
    total_recursos.short_description = "🔧 Recursos"

    def save_formset(self, request, form, formset, change):
        # Recursos cadastrados aqui ficam na mesma organização da sala
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

    def save_model(self, request, obj, form, change):
        # A organização do recurso é sempre a da sala
        obj.organizacao = obj.sala.organizacao
        super().save_model(request, obj, form, change)


@admin.register(Recorrencia)
class RecorrenciaAdmin(admin.ModelAdmin):
    list_display = ('frequencia', 'organizacao', 'data_inicio', 'data_fim', 'intervalo')
    list_filter = ('organizacao', 'frequencia')
    date_hierarchy = 'data_inicio'


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ('sala', 'organizacao', 'responsavel', 'data_inicio', 'status', 'tem_conflito')
    list_filter = ('organizacao', 'status', 'sala', 'data_inicio')
    search_fields = ('responsavel', 'sala__nome')
    date_hierarchy = 'data_inicio'
    fieldsets = (
        ('Informações Básicas', {'fields': ('sala', 'responsavel', 'descricao')}),
        ('Datas e Horários', {'fields': ('data_inicio', 'data_fim')}),
        ('Recorrência e Status', {'fields': ('recorrencia', 'status')}),
    )
    
    def save_model(self, request, obj, form, change):
        # A organização da reserva é sempre a da sala
        obj.organizacao = obj.sala.organizacao
        if obj.tem_conflito():
            raise ValueError('Existe conflito com outra reserva neste horário!')
        super().save_model(request, obj, form, change)
