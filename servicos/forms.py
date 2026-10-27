"""Formulários. A conversão do que é digitado fica em ``dominio`` (RN-11)."""

import uuid

from django import forms
from django.utils import timezone

from . import dominio
from .models import Servico


def _campo_texto(rotulo, exemplo='', numerico=True, **kwargs):
    """Campo de texto livre: aceita vírgula ("12,5"), que o <input type=number> recusa."""
    attrs = {'placeholder': exemplo, 'autocomplete': 'off'}
    if numerico:
        attrs['inputmode'] = 'decimal'  # abre o teclado numérico no celular
    return forms.CharField(label=rotulo, widget=forms.TextInput(attrs=attrs), **kwargs)


def _ler(campo, funcao, valor, **kwargs):
    try:
        return funcao(valor, **kwargs)
    except dominio.ValorInvalido as erro:
        raise forms.ValidationError(str(erro), code=campo)


class ServicoForm(forms.Form):
    cliente = forms.CharField(
        label='Cliente', min_length=2, max_length=100,
        error_messages={'required': 'Informe o nome do cliente.',
                        'min_length': 'O nome precisa ter pelo menos 2 letras.'},
        widget=forms.TextInput(attrs={'list': 'clientes', 'autocomplete': 'off'}),
    )
    telefone = forms.CharField(label='Telefone (opcional)', max_length=20, required=False,
                               widget=forms.TextInput(attrs={'inputmode': 'tel'}))
    descricao = forms.CharField(
        label='O que foi feito', max_length=500,
        error_messages={'required': 'Descreva o serviço.'},
        widget=forms.Textarea(attrs={'rows': 2}),
    )
    data = forms.DateField(label='Data', initial=timezone.localdate,
                           widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    local = forms.ChoiceField(label='Local', choices=Servico.Local.choices, initial=Servico.Local.OFICINA,
                              widget=forms.RadioSelect)
    observacoes = forms.CharField(label='Observações (opcional)', required=False,
                                  widget=forms.Textarea(attrs={'rows': 2}))
    versao = forms.IntegerField(widget=forms.HiddenInput, required=False)

    def clean_cliente(self):
        return ' '.join(self.cleaned_data['cliente'].split())


class _LancamentoForm(forms.Form):
    # Uma chave nova a cada formulário aberto; o reenvio da mesma chave é ignorado (Seção 10.2).
    chave = forms.UUIDField(widget=forms.HiddenInput, required=False)
    tipo = ''  # prefixo dos ids no HTML: os três formulários ficam na mesma página

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('auto_id', f'{self.tipo}_%s')
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.setdefault('chave', uuid.uuid4())


class MaterialForm(_LancamentoForm):
    tipo = 'material'
    descricao = forms.CharField(label='Material', max_length=200,
                                error_messages={'required': 'Informe o material.'},
                                widget=forms.TextInput(attrs={'placeholder': 'Ex.: fio 2,5 mm'}))
    quantidade = _campo_texto('Quantidade', '1', initial='1')
    valor_unitario = _campo_texto('Valor unitário (R$)', '15,50')

    def clean_quantidade(self):
        return _ler('quantidade', dominio.ler_quantidade, self.cleaned_data['quantidade'])

    def clean_valor_unitario(self):
        # Zero é permitido: material fornecido pelo próprio cliente (RN-02).
        return _ler('valor_unitario', dominio.ler_dinheiro, self.cleaned_data['valor_unitario'])


class DeslocamentoForm(_LancamentoForm):
    tipo = 'deslocamento'
    data = forms.DateField(label='Data da visita', initial=timezone.localdate,
                           widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    km = _campo_texto('Km rodados (ida + volta)', '25')

    def clean_km(self):
        return _ler('km', dominio.ler_km, self.cleaned_data['km'])


class TempoForm(_LancamentoForm):
    tipo = 'tempo'
    tempo = _campo_texto('Tempo trabalhado', '2h30', numerico=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.opcoes_tempo = []  # preenchido quando o número vem sem unidade

    def clean_tempo(self):
        try:
            return dominio.ler_tempo(self.cleaned_data['tempo'])
        except dominio.TempoAmbiguo as ambiguo:
            self.opcoes_tempo = ambiguo.opcoes
            raise forms.ValidationError(str(ambiguo), code='ambiguo')
        except dominio.ValorInvalido as erro:
            raise forms.ValidationError(str(erro))


class PrecoForm(forms.Form):
    preco = _campo_texto('Preço cobrado (R$)', '350,00')

    def clean_preco(self):
        return _ler('preco', dominio.ler_dinheiro, self.cleaned_data['preco'])


class ConfiguracaoForm(forms.Form):
    valor_km = _campo_texto('Valor por km (R$)', '1,20')
    valor_hora = _campo_texto('Valor da hora (R$)', '60,00')

    def clean_valor_km(self):
        return _ler('valor_km', dominio.ler_dinheiro, self.cleaned_data['valor_km'], permitir_zero=False)

    def clean_valor_hora(self):
        return _ler('valor_hora', dominio.ler_dinheiro, self.cleaned_data['valor_hora'], permitir_zero=False)


def centavos_para_texto(centavos):
    """1550 -> "15,50", para preencher formulários de edição."""
    if centavos is None:
        return ''
    return dominio.formatar_reais(centavos).replace('R$ ', '').replace('.', '')
