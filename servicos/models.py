import unicodedata
from decimal import Decimal

from django.db import models
from django.utils import timezone

from . import dominio


def normalizar(texto: str) -> str:
    """Tira acentos e maiúsculas, para a busca "joao" achar "João" (CT-31)."""
    sem_acento = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode()
    return ' '.join(sem_acento.lower().split())


class Configuracao(models.Model):
    """Valores usados nos próximos lançamentos (RF-02). Existe uma única linha."""

    valor_km_centavos = models.PositiveIntegerField(default=120)  # R$ 1,20
    valor_hora_centavos = models.PositiveIntegerField(default=6000)  # R$ 60,00
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'configuração'
        verbose_name_plural = 'configuração'

    @classmethod
    def atual(cls):
        return cls.objects.get_or_create(pk=1)[0]


class Cliente(models.Model):
    """Cliente do Divino. Só nome e telefone (P-11, minimização LGPD)."""

    nome = models.CharField(max_length=100)
    nome_busca = models.CharField(max_length=100, unique=True, editable=False)
    telefone = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome_busca = normalizar(self.nome)
        super().save(*args, **kwargs)

    @classmethod
    def obter_ou_criar(cls, nome: str, telefone: str = ''):
        """D-03: "João" e "joão" são o mesmo cliente."""
        nome = ' '.join(nome.split())
        cliente = cls.objects.filter(nome_busca=normalizar(nome)).first()
        if cliente is None:
            cliente = cls.objects.create(nome=nome, telefone=telefone)
        elif telefone and not cliente.telefone:
            cliente.telefone = telefone
            cliente.save(update_fields=['telefone'])
        return cliente


class Servico(models.Model):
    class Local(models.TextChoices):
        OFICINA = dominio.OFICINA, 'Oficina'
        EXTERNO = dominio.EXTERNO, 'Externo'

    class Situacao(models.TextChoices):
        # D-01. As transições entre situações entram no Sprint 2.
        ORCAMENTO = 'ORCAMENTO', 'Orçamento'
        EM_ANDAMENTO = 'EM_ANDAMENTO', 'Em andamento'
        CONCLUIDO = 'CONCLUIDO', 'Concluído'
        RECEBIDO = 'RECEBIDO', 'Recebido'
        CANCELADO = 'CANCELADO', 'Cancelado'

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='servicos')
    descricao = models.CharField(max_length=500)
    data = models.DateField(default=timezone.localdate)
    local = models.CharField(max_length=10, choices=Local.choices, default=Local.OFICINA)
    situacao = models.CharField(max_length=15, choices=Situacao.choices, default=Situacao.EM_ANDAMENTO)
    preco_centavos = models.PositiveIntegerField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    # Incrementada a cada alteração, para não sobrescrever edição feita em outra aba (UC08-E2).
    versao = models.PositiveIntegerField(default=1)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data', '-id']

    def __str__(self):
        return f'{self.codigo} {self.cliente}'

    @property
    def codigo(self):
        return f'S-{self.pk:04d}' if self.pk else 'S-????'

    @property
    def aceita_lancamentos(self):
        # RN-16; a confirmação em RECEBIDO entra com os recebimentos no Sprint 2.
        return self.situacao != self.Situacao.CANCELADO

    def resumo(self) -> dominio.Resumo:
        """Sempre recalculado a partir dos lançamentos (RN-12): nada de total gravado."""
        return dominio.calcular_resumo(
            local=self.local,
            preco_centavos=self.preco_centavos,
            materiais=[(m.quantidade, m.valor_unitario_centavos) for m in self.materiais.all()],
            deslocamentos=[(d.km, d.valor_km_centavos) for d in self.deslocamentos.all()],
            tempos=[(t.minutos, t.valor_hora_centavos) for t in self.tempos.all()],
        )


class Lancamento(models.Model):
    """Base dos três tipos de lançamento (RN-01: sempre ligado a um serviço)."""

    # Gerada pelo formulário; um toque duplo em "Salvar" não cria dois lançamentos (RNF-04).
    chave_idempotencia = models.UUIDField(unique=True, null=True, blank=True, editable=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ['criado_em', 'id']


class Material(Lancamento):
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name='materiais')
    descricao = models.CharField(max_length=200)
    quantidade = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal('1'))
    valor_unitario_centavos = models.PositiveIntegerField()

    @property
    def custo(self):
        return dominio.custo_material(self.quantidade, self.valor_unitario_centavos)

    @property
    def conta(self):
        return (f'{dominio.formatar_decimal(self.quantidade)} × '
                f'{dominio.formatar_reais(self.valor_unitario_centavos)} = {dominio.formatar_reais(self.custo)}')


class Deslocamento(Lancamento):
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name='deslocamentos')
    data = models.DateField(default=timezone.localdate)
    km = models.DecimalField(max_digits=6, decimal_places=1)
    # RN-05: cópia do valor por km vigente no momento do lançamento.
    valor_km_centavos = models.PositiveIntegerField(editable=False)

    @property
    def custo(self):
        return dominio.custo_deslocamento(self.km, self.valor_km_centavos)

    @property
    def conta(self):
        return (f'{dominio.formatar_decimal(self.km)} km × '
                f'{dominio.formatar_reais(self.valor_km_centavos)} = {dominio.formatar_reais(self.custo)}')


class Tempo(Lancamento):
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE, related_name='tempos')
    minutos = models.PositiveIntegerField()
    # RN-05: cópia do valor da hora vigente no momento do lançamento.
    valor_hora_centavos = models.PositiveIntegerField(editable=False)

    @property
    def custo(self):
        return dominio.custo_tempo(self.minutos, self.valor_hora_centavos)

    @property
    def conta(self):
        return (f'{dominio.formatar_minutos(self.minutos)} × '
                f'{dominio.formatar_reais(self.valor_hora_centavos)}/h = {dominio.formatar_reais(self.custo)}')
