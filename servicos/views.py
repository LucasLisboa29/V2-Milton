from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import dominio
from .forms import (ConfiguracaoForm, DeslocamentoForm, MaterialForm, PrecoForm, ServicoForm, TempoForm,
                    centavos_para_texto)
from .models import Cliente, Configuracao, Deslocamento, Material, Servico, Tempo, normalizar

# ------------------------------------------------------------------ acesso

TENTATIVAS_MAX = 5
BLOQUEIO_SEGUNDOS = 15 * 60


class EntrarView(auth_views.LoginView):
    """UC01: depois de 5 falhas em 15 min, aguardar 15 min. Mensagem de erro genérica."""

    template_name = 'servicos/entrar.html'
    redirect_authenticated_user = True

    def _chave(self):
        return f'login-falhas:{self.request.META.get("REMOTE_ADDR", "")}'

    def post(self, request, *args, **kwargs):
        if cache.get(self._chave(), 0) >= TENTATIVAS_MAX:
            form = self.get_form()
            form.add_error(None, 'Muitas tentativas. Aguarde 15 minutos e tente de novo.')
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        chave = self._chave()
        cache.set(chave, cache.get(chave, 0) + 1, BLOQUEIO_SEGUNDOS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._chave())
        return super().form_valid(form)


def configuracao(request):
    """RF-02: os novos valores valem só para os próximos lançamentos (RN-05)."""
    config = Configuracao.atual()
    if request.method == 'POST':
        form = ConfiguracaoForm(request.POST)
        if form.is_valid():
            config.valor_km_centavos = form.cleaned_data['valor_km']
            config.valor_hora_centavos = form.cleaned_data['valor_hora']
            config.save()
            messages.success(request, 'Valores salvos. Eles valem para os próximos lançamentos.')
            return redirect('servicos:lista')
    else:
        form = ConfiguracaoForm(initial={
            'valor_km': centavos_para_texto(config.valor_km_centavos),
            'valor_hora': centavos_para_texto(config.valor_hora_centavos),
        })
    return render(request, 'servicos/configuracao.html', {'form': form, 'config': config})


# ---------------------------------------------------------------- serviços

def lista(request):
    """RF-06 e RF-22: do mais recente para o mais antigo, com busca por cliente."""
    busca = request.GET.get('busca', '').strip()
    servicos = (Servico.objects.select_related('cliente')
                .prefetch_related('materiais', 'deslocamentos', 'tempos'))
    if busca:
        servicos = servicos.filter(cliente__nome_busca__contains=normalizar(busca))
    linhas = [(s, s.resumo()) for s in servicos]
    return render(request, 'servicos/lista.html', {'linhas': linhas, 'busca': busca})


def _contexto_form_servico(form, servico=None):
    return {'form': form, 'servico': servico, 'clientes': Cliente.objects.values_list('nome', flat=True)}


def novo(request):
    """UC03: cadastra e abre o detalhe, pronto para os lançamentos."""
    if request.method == 'POST':
        form = ServicoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            servico = Servico.objects.create(
                cliente=Cliente.obter_ou_criar(dados['cliente'], dados['telefone']),
                descricao=dados['descricao'], data=dados['data'], local=dados['local'],
                observacoes=dados['observacoes'],
            )
            messages.success(request, f'Serviço {servico.codigo} criado.')
            return redirect('servicos:detalhe', pk=servico.pk)
    else:
        form = ServicoForm()
    return render(request, 'servicos/servico_form.html', _contexto_form_servico(form))


def editar(request, pk):
    """UC08: confere a versão para não sobrescrever uma edição feita em outra aba."""
    servico = get_object_or_404(Servico.objects.select_related('cliente'), pk=pk)
    if request.method == 'POST':
        form = ServicoForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            with transaction.atomic():
                servico = Servico.objects.select_for_update().get(pk=pk)
                if dados['versao'] != servico.versao:
                    messages.warning(request, 'O serviço foi alterado em outro lugar. Confira e edite de novo.')
                    return redirect('servicos:editar', pk=pk)
                saiu_de_externo = (servico.local == Servico.Local.EXTERNO
                                   and dados['local'] == Servico.Local.OFICINA)
                servico.cliente = Cliente.obter_ou_criar(dados['cliente'], dados['telefone'])
                servico.descricao = dados['descricao']
                servico.data = dados['data']
                servico.local = dados['local']
                servico.observacoes = dados['observacoes']
                servico.versao = F('versao') + 1
                servico.save()
            if saiu_de_externo and servico.deslocamentos.exists():
                # RN-14 / mensagem padrão da Seção 11.4.
                messages.warning(request, 'Os km lançados deixam de contar porque o serviço agora é na '
                                          'oficina. Eles voltam se você mudar de novo.')
            messages.success(request, 'Serviço atualizado.')
            return redirect('servicos:detalhe', pk=pk)
    else:
        form = ServicoForm(initial={
            'cliente': servico.cliente.nome, 'telefone': servico.cliente.telefone,
            'descricao': servico.descricao, 'data': servico.data, 'local': servico.local,
            'observacoes': servico.observacoes, 'versao': servico.versao,
        })
    return render(request, 'servicos/servico_form.html', _contexto_form_servico(form, servico))


def detalhe(request, pk, forms_com_erro=None):
    """T04: lançamentos, resumo calculado no servidor e pendências."""
    servico = get_object_or_404(
        Servico.objects.select_related('cliente').prefetch_related('materiais', 'deslocamentos', 'tempos'),
        pk=pk,
    )
    forms_com_erro = forms_com_erro or {}
    contexto = {
        'servico': servico,
        'resumo': servico.resumo(),
        'config': Configuracao.atual(),
        'form_material': forms_com_erro.get('material', MaterialForm()),
        'form_deslocamento': forms_com_erro.get('deslocamento', DeslocamentoForm()),
        'form_tempo': forms_com_erro.get('tempo', TempoForm()),
        'form_preco': forms_com_erro.get('preco', PrecoForm(
            initial={'preco': centavos_para_texto(servico.preco_centavos)})),
        'aberto': next(iter(forms_com_erro), ''),
    }
    status = 422 if forms_com_erro else 200
    return render(request, 'servicos/detalhe.html', contexto, status=status)


@require_POST
def definir_preco(request, pk):
    """RF-14. O resultado é recalculado no servidor (RN-12)."""
    form = PrecoForm(request.POST)
    if not form.is_valid():
        return detalhe(request, pk, {'preco': form})
    with transaction.atomic():
        servico = get_object_or_404(Servico.objects.select_for_update(), pk=pk)
        servico.preco_centavos = form.cleaned_data['preco']
        servico.versao = F('versao') + 1
        servico.save(update_fields=['preco_centavos', 'versao'])
    messages.success(request, 'Preço salvo.')
    return redirect('servicos:detalhe', pk=pk)


# ------------------------------------------------------------- lançamentos

TIPOS = {
    'material': (Material, MaterialForm),
    'deslocamento': (Deslocamento, DeslocamentoForm),
    'tempo': (Tempo, TempoForm),
}


def _aplicar(tipo, lancamento, dados, config):
    """Copia os campos do formulário para o lançamento.

    RN-05: o valor por km / da hora só é copiado da configuração na criação.
    Editar um lançamento antigo mantém o valor que ele já tinha (CT-13).
    """
    if tipo == 'material':
        lancamento.descricao = dados['descricao']
        lancamento.quantidade = dados['quantidade']
        lancamento.valor_unitario_centavos = dados['valor_unitario']
    elif tipo == 'deslocamento':
        lancamento.data = dados['data']
        lancamento.km = dados['km']
        if lancamento.pk is None:
            lancamento.valor_km_centavos = config.valor_km_centavos
    else:
        lancamento.minutos = dados['tempo']
        if lancamento.pk is None:
            lancamento.valor_hora_centavos = config.valor_hora_centavos


class LancamentoNaoPermitido(Exception):
    pass


def _servico_travado(pk):
    """Trava o serviço durante o lançamento (Seção 10.2) e confere se aceita lançamentos."""
    servico = get_object_or_404(Servico.objects.select_for_update(), pk=pk)
    if not servico.aceita_lancamentos:
        raise LancamentoNaoPermitido('Este serviço está cancelado e não aceita lançamentos.')
    return servico


@require_POST
def adicionar_lancamento(request, pk, tipo):
    Modelo, Form = TIPOS[tipo]
    form = Form(request.POST)
    if not form.is_valid():
        return detalhe(request, pk, {tipo: form})

    chave = form.cleaned_data['chave']
    try:
        with transaction.atomic():
            servico = _servico_travado(pk)
            if tipo == 'deslocamento' and servico.local != Servico.Local.EXTERNO:
                raise LancamentoNaoPermitido('Deslocamento só existe em serviço externo.')
            if chave and Modelo.objects.filter(chave_idempotencia=chave).exists():
                # Toque duplo ou reenvio depois de queda de conexão: nada novo é criado (CT-18).
                return redirect('servicos:detalhe', pk=pk)
            lancamento = Modelo(servico=servico, chave_idempotencia=chave)
            _aplicar(tipo, lancamento, form.cleaned_data, Configuracao.atual())
            lancamento.save()
            Servico.objects.filter(pk=pk).update(versao=F('versao') + 1)
    except LancamentoNaoPermitido as erro:
        messages.error(request, str(erro))
    except IntegrityError:
        pass  # a mesma chave chegou em paralelo; o primeiro lançamento já foi gravado
    return redirect('servicos:detalhe', pk=pk)


def editar_lancamento(request, pk, tipo, lid):
    Modelo, Form = TIPOS[tipo]
    lancamento = get_object_or_404(Modelo, pk=lid, servico_id=pk)
    if request.method == 'POST':
        form = Form(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    _servico_travado(pk)
                    _aplicar(tipo, lancamento, form.cleaned_data, Configuracao.atual())
                    lancamento.save()
                    Servico.objects.filter(pk=pk).update(versao=F('versao') + 1)
            except LancamentoNaoPermitido as erro:
                messages.error(request, str(erro))
            else:
                messages.success(request, 'Lançamento atualizado.')
            return redirect('servicos:detalhe', pk=pk)
    else:
        form = Form(initial=_inicial(tipo, lancamento))
    return render(request, 'servicos/lancamento_form.html',
                  {'form': form, 'servico': lancamento.servico, 'tipo': tipo, 'lancamento': lancamento})


def _inicial(tipo, lancamento):
    if tipo == 'material':
        return {'descricao': lancamento.descricao,
                'quantidade': dominio.formatar_decimal(lancamento.quantidade),
                'valor_unitario': centavos_para_texto(lancamento.valor_unitario_centavos)}
    if tipo == 'deslocamento':
        return {'data': lancamento.data, 'km': dominio.formatar_decimal(lancamento.km)}
    return {'tempo': f'{lancamento.minutos} min'}


@require_POST
def remover_lancamento(request, pk, tipo, lid):
    Modelo, _ = TIPOS[tipo]
    try:
        with transaction.atomic():
            _servico_travado(pk)
            get_object_or_404(Modelo, pk=lid, servico_id=pk).delete()
            Servico.objects.filter(pk=pk).update(versao=F('versao') + 1)
    except LancamentoNaoPermitido as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, 'Lançamento removido.')
    return redirect('servicos:detalhe', pk=pk)
