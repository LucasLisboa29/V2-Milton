from django.contrib.auth import views as auth_views
from django.urls import include, path

from servicos.views import EntrarView

urlpatterns = [
    path('entrar/', EntrarView.as_view(), name='login'),
    path('sair/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('servicos.urls')),
]
