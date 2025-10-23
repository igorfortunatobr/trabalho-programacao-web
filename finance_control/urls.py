"""
Configuração de URLs para o projeto finance_control.

A lista `urlpatterns` direciona URLs para views. Para mais informações, veja:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Exemplos:
Views funcionais
    1. Adicione uma importação:  from my_app import views
    2. Adicione uma URL à urlpatterns:  path('', views.home, name='home')
Views baseadas em classes
    1. Adicione uma importação:  from other_app.views import Home
    2. Adicione uma URL à urlpatterns:  path('', Home.as_view(), name='home')
Incluindo outra URLconf
    1. Importe a função include(): from django.urls import include, path
    2. Adicione uma URL à urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('core.urls')),
]