from django.urls import path, register_converter

from . import views


class TipoLancamento:
    """Aceita só material, deslocamento ou tempo na URL."""

    regex = '|'.join(views.TIPOS)

    def to_python(self, valor):
        return valor

    def to_url(self, valor):
        return valor


register_converter(TipoLancamento, 'tipo')

app_name = 'servicos'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('servicos/novo/', views.novo, name='novo'),
    path('servicos/<int:pk>/', views.detalhe, name='detalhe'),
    path('servicos/<int:pk>/editar/', views.editar, name='editar'),
    path('servicos/<int:pk>/preco/', views.definir_preco, name='preco'),
    path('servicos/<int:pk>/<tipo:tipo>/', views.adicionar_lancamento, name='adicionar'),
    path('servicos/<int:pk>/<tipo:tipo>/<int:lid>/', views.editar_lancamento, name='editar_lancamento'),
    path('servicos/<int:pk>/<tipo:tipo>/<int:lid>/remover/', views.remover_lancamento, name='remover'),
    path('configuracao/', views.configuracao, name='configuracao'),
]
