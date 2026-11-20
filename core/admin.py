from django.contrib import admin
from .models import Organizacao, Perfil, RegistroAtividade


@admin.register(Organizacao)
class OrganizacaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'criada_em')
    search_fields = ('nome',)


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'organizacao', 'papel')
    list_filter = ('organizacao', 'papel')
    search_fields = ('usuario__username',)


@admin.register(RegistroAtividade)
class RegistroAtividadeAdmin(admin.ModelAdmin):
    # Só leitura: ninguém cria nem edita; só o superusuário pode apagar
    list_display = ('quando', 'usuario', 'organizacao', 'acao', 'tipo_objeto', 'objeto_id', 'descricao')
    list_filter = ('acao', 'organizacao', 'usuario', ('quando', admin.DateFieldListFilter))
    search_fields = ('descricao',)
    date_hierarchy = 'quando'
    list_select_related = ('usuario', 'organizacao')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
