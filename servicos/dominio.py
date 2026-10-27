"""Regras de cálculo do Custos por Serviço.

Este módulo não depende do Django (RNF-13): recebe números simples e devolve
números simples, para ser testado isoladamente.

Todo dinheiro é tratado em centavos inteiros (P-01). Quantidade e km são
``Decimal`` exatos; nunca ``float``. Cada lançamento é arredondado uma única
vez para o centavo, meia unidade para cima (RN-13), e os totais são somas de
centavos já arredondados.
"""

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

OFICINA = 'OFICINA'
EXTERNO = 'EXTERNO'

KM_MIN, KM_MAX = Decimal('0.1'), Decimal('2000')  # P-03
MINUTOS_MIN, MINUTOS_MAX = 1, 24 * 60  # P-04
QUANTIDADE_CASAS = 3  # P-02

PENDENCIA_DESLOCAMENTO = 'Deslocamento não informado'
PENDENCIA_HORAS = 'Horas não informadas'
PENDENCIA_PRECO = 'Preço não informado'


class ValorInvalido(ValueError):
    """Entrada recusada pela RN-11. A mensagem é exibida ao usuário."""


class TempoAmbiguo(ValueError):
    """Número sem unidade, como "230": o usuário precisa escolher (UC06-A1)."""

    def __init__(self, opcoes):
        self.opcoes = opcoes  # lista de (texto para reenviar, minutos)
        textos = ' ou '.join(texto for texto, _ in opcoes)
        super().__init__(f'Você quis dizer {textos}?')


# ---------------------------------------------------------------- cálculos

def arred(valor: Decimal) -> int:
    """Arredonda para o centavo inteiro, meia unidade para cima (RN-13)."""
    return int(Decimal(valor).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def custo_material(quantidade: Decimal, valor_unitario_centavos: int) -> int:
    """RN-02: quantidade × valor unitário, arredondado uma vez."""
    return arred(Decimal(quantidade) * valor_unitario_centavos)


def custo_deslocamento(km: Decimal, valor_km_centavos: int) -> int:
    """RN-03: km × valor por km copiado no lançamento."""
    return arred(Decimal(km) * valor_km_centavos)


def custo_tempo(minutos: int, valor_hora_centavos: int) -> int:
    """RN-04: multiplica antes de dividir, para não perder precisão."""
    return arred(Decimal(minutos * valor_hora_centavos) / 60)


@dataclass
class Resumo:
    materiais: int
    deslocamento: int | None  # None = "não se aplica" (serviço na oficina)
    mao_de_obra: int
    custo_total: int
    minutos_totais: int
    preco: int | None
    resultado: int | None
    saldo: int | None
    pendencias: list[str] = field(default_factory=list)

    @property
    def prejuizo(self) -> bool:
        return self.resultado is not None and self.resultado < 0


def calcular_resumo(local, preco_centavos, materiais, deslocamentos, tempos, recebido_centavos=0) -> Resumo:
    """Resumo do serviço (Seção 10.1 da especificação).

    ``materiais``: pares (quantidade, valor_unitario_centavos).
    ``deslocamentos``: pares (km, valor_km_centavos).
    ``tempos``: pares (minutos, valor_hora_centavos).

    Nunca inventa valores: dado ausente vira pendência (RN-09).
    """
    total_materiais = sum(custo_material(q, v) for q, v in materiais)

    # RN-14: em serviço de oficina os deslocamentos ficam guardados, mas não contam.
    if local == EXTERNO:
        total_deslocamento = sum(custo_deslocamento(km, v) for km, v in deslocamentos)
    else:
        total_deslocamento = None

    total_mao_de_obra = sum(custo_tempo(m, v) for m, v in tempos)
    custo_total = total_materiais + (total_deslocamento or 0) + total_mao_de_obra

    pendencias = []
    if local == EXTERNO and not deslocamentos:
        pendencias.append(PENDENCIA_DESLOCAMENTO)
    if not tempos:
        pendencias.append(PENDENCIA_HORAS)

    resultado = saldo = None
    if preco_centavos is None:
        pendencias.append(PENDENCIA_PRECO)
    else:
        resultado = preco_centavos - custo_total  # RN-07
        saldo = preco_centavos - recebido_centavos

    return Resumo(
        materiais=total_materiais,
        deslocamento=total_deslocamento,
        mao_de_obra=total_mao_de_obra,
        custo_total=custo_total,
        minutos_totais=sum(m for m, _ in tempos),
        preco=preco_centavos,
        resultado=resultado,
        saldo=saldo,
        pendencias=pendencias,
    )


# ------------------------------------------------- leitura do que é digitado

def _decimal_br(texto: str) -> Decimal:
    """Converte "1.234,56" ou "12,5" em Decimal. Recusa vazio e letras."""
    limpo = (texto or '').strip().replace('R$', '').replace(' ', '')
    if not limpo:
        raise ValorInvalido('Informe um valor.')
    if ',' in limpo:
        limpo = limpo.replace('.', '').replace(',', '.')
    if not re.fullmatch(r'-?\d+(\.\d+)?', limpo):
        raise ValorInvalido('Use só números. Exemplo: 12,5')
    try:
        return Decimal(limpo)
    except InvalidOperation:
        raise ValorInvalido('Use só números. Exemplo: 12,5')


def ler_dinheiro(texto: str, permitir_zero=True) -> int:
    """ "15,50" -> 1550 centavos. Aceita no máximo 2 casas decimais."""
    valor = _decimal_br(texto)
    if valor < 0 or (valor == 0 and not permitir_zero):
        raise ValorInvalido('O valor precisa ser maior que zero.' if not permitir_zero
                            else 'O valor não pode ser negativo.')
    if valor != valor.quantize(Decimal('0.01')):
        raise ValorInvalido('Use no máximo 2 casas decimais.')
    return int(valor * 100)


def ler_quantidade(texto: str) -> Decimal:
    """P-02: maior que zero, até 3 casas decimais (ex.: 2,5 m de fio)."""
    valor = _decimal_br(texto)
    if valor <= 0:
        raise ValorInvalido('A quantidade precisa ser maior que zero.')
    if valor != valor.quantize(Decimal(1).scaleb(-QUANTIDADE_CASAS)):
        raise ValorInvalido('Use no máximo 3 casas decimais.')
    return valor


def ler_km(texto: str) -> Decimal:
    """P-03: de 0,1 a 2.000 km, com 1 casa decimal."""
    valor = _decimal_br(texto)
    if valor <= 0:
        raise ValorInvalido('Os km precisam ser maiores que zero.')
    if valor != valor.quantize(Decimal('0.1')):
        raise ValorInvalido('Use no máximo 1 casa decimal. Exemplo: 12,5')
    if not (KM_MIN <= valor <= KM_MAX):
        raise ValorInvalido('Informe entre 0,1 e 2.000 km.')
    return valor


_RE_HORAS = re.compile(r'^(\d+)\s*h\s*(?:(\d+)\s*(?:min|m)?)?$')
_RE_DOIS_PONTOS = re.compile(r'^(\d+):(\d{2})$')
_RE_MINUTOS = re.compile(r'^(\d+)\s*(?:min|m)$')
_RE_HORAS_DECIMAIS = re.compile(r'^(\d+[.,]\d+)\s*h$')


def ler_tempo(texto: str) -> int:
    """Converte "2h30", "2:30", "150 min" ou "2,5h" em minutos (RF-12).

    Número sem unidade é ambíguo e levanta ``TempoAmbiguo`` com as opções.
    """
    t = (texto or '').strip().lower()
    if not t:
        raise ValorInvalido('Informe o tempo. Exemplo: 2h30')

    if m := _RE_HORAS.match(t):
        minutos_extra = int(m.group(2) or 0)
        if minutos_extra >= 60:
            raise ValorInvalido('Os minutos vão de 0 a 59. Exemplo: 2h30')
        minutos = int(m.group(1)) * 60 + minutos_extra
    elif m := _RE_DOIS_PONTOS.match(t):
        if int(m.group(2)) >= 60:
            raise ValorInvalido('Os minutos vão de 0 a 59. Exemplo: 2:30')
        minutos = int(m.group(1)) * 60 + int(m.group(2))
    elif m := _RE_MINUTOS.match(t):
        minutos = int(m.group(1))
    elif m := _RE_HORAS_DECIMAIS.match(t):
        minutos = arred(Decimal(m.group(1).replace(',', '.')) * 60)
    elif t.isdigit():
        raise TempoAmbiguo(_opcoes_numero_sem_unidade(int(t)))
    else:
        raise ValorInvalido('Não entendi o tempo. Use 2h30, 2:30 ou 150 min.')

    if not (MINUTOS_MIN <= minutos <= MINUTOS_MAX):
        raise ValorInvalido('O tempo precisa ficar entre 1 minuto e 24 horas.')
    return minutos


def _opcoes_numero_sem_unidade(n: int):
    """ "230" -> 2h30 ou 230 min; "3" -> 3h ou 3 min."""
    opcoes = []
    if n >= 100 and n % 100 < 60:
        horas, mins = divmod(n, 100)
        opcoes.append((f'{horas}h{mins:02d}', horas * 60 + mins))
    elif n < 100:
        opcoes.append((f'{n}h', n * 60))
    opcoes.append((f'{n} min', n))
    return [(texto, mins) for texto, mins in opcoes if MINUTOS_MIN <= mins <= MINUTOS_MAX]


# ------------------------------------------------------------- formatação

def formatar_reais(centavos: int | None) -> str:
    """1234 56 -> "R$ 1.234,56"; negativo -> "− R$ 38,00" (RNF-09)."""
    if centavos is None:
        return '—'
    sinal = '− ' if centavos < 0 else ''
    reais, cent = divmod(abs(centavos), 100)
    return f'{sinal}R$ {reais:,}'.replace(',', '.') + f',{cent:02d}'


def formatar_minutos(minutos: int) -> str:
    """135 -> "2 h 15 min"."""
    horas, mins = divmod(minutos, 60)
    if horas and mins:
        return f'{horas} h {mins:02d} min'
    if horas:
        return f'{horas} h'
    return f'{mins} min'


def formatar_decimal(valor: Decimal) -> str:
    """Decimal('12.500') -> "12,5" (sem zeros à direita)."""
    texto = format(Decimal(valor).normalize(), 'f')
    return texto.replace('.', ',')
