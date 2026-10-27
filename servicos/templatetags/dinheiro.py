from django import template

from .. import dominio

register = template.Library()


@register.filter
def reais(centavos):
    """{{ 35000|reais }} -> "R$ 350,00"."""
    return dominio.formatar_reais(centavos)


@register.filter
def duracao(minutos):
    """{{ 135|duracao }} -> "2 h 15 min"."""
    return dominio.formatar_minutos(minutos)


@register.filter
def decimal_br(valor):
    """{{ km|decimal_br }} -> "12,5"."""
    return dominio.formatar_decimal(valor)
