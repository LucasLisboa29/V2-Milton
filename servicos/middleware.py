from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.urls import reverse

ROTAS_PUBLICAS = ('/static/',)


class LoginObrigatorioMiddleware:
    """RNF-05/06: sem login, nenhuma tela ou dado é acessível."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        caminho = request.path
        publica = caminho == reverse(settings.LOGIN_URL) or caminho.startswith(ROTAS_PUBLICAS)
        if not publica and not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        return self.get_response(request)
