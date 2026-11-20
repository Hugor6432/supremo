from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('salas.api_urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('contas/cadastro/', core_views.cadastro, name='cadastro'),
    path('contas/', include('django.contrib.auth.urls')),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('', include('salas.urls')),
]
