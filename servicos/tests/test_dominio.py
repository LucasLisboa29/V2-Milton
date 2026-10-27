"""Testes do módulo de cálculo, com os valores dos casos de aceitação (Seção 15.2).

Não usam banco nem Django: ``SimpleTestCase`` roda em milissegundos.
"""

from decimal import Decimal

from django.test import SimpleTestCase

from servicos import dominio as d

HORA = 6000  # R$ 60,00
KM = 120  # R$ 1,20


class CustosTest(SimpleTestCase):
    def test_ct02_materiais(self):
        materiais = [(Decimal('2'), 1550), (Decimal('1'), 4200)]
        self.assertEqual(sum(d.custo_material(q, v) for q, v in materiais), 7300)

    def test_ct04_deslocamento_25km(self):
        self.assertEqual(d.custo_deslocamento(Decimal('25'), KM), 3000)

    def test_ct05_deslocamento_12_5km(self):
        self.assertEqual(d.custo_deslocamento(Decimal('12.5'), KM), 1500)

    def test_ct07_horas_em_partes(self):
        # 1h30 + 0h45 = 135 min = 2,25 h -> R$ 135,00
        self.assertEqual(d.custo_tempo(90, HORA) + d.custo_tempo(45, HORA), 13500)

    def test_ct15_quantidade_fracionada(self):
        self.assertEqual(d.custo_material(Decimal('2.5'), 390), 975)

    def test_ct16_meia_unidade_para_cima(self):
        # 1,5 × R$ 0,03 = 4,5 centavos -> 5
        self.assertEqual(d.custo_material(Decimal('1.5'), 3), 5)

    def test_tempo_multiplica_antes_de_dividir(self):
        # 7 min a R$ 60,00/h = R$ 7,00. Dividir primeiro (7/60 = 0,1166...) arriscaria perder centavos.
        self.assertEqual(d.custo_tempo(7, HORA), 700)
        # 1 min a R$ 70,00/h = 116,67 centavos -> 117
        self.assertEqual(d.custo_tempo(1, 7000), 117)


class ResumoTest(SimpleTestCase):
    def _servico_completo(self, preco):
        return d.calcular_resumo(
            local=d.EXTERNO,
            preco_centavos=preco,
            materiais=[(Decimal('2'), 1550), (Decimal('1'), 4200)],
            deslocamentos=[(Decimal('25'), KM)],
            tempos=[(90, HORA), (45, HORA)],
        )

    def test_ct08_ciclo_completo_resultado_112(self):
        r = self._servico_completo(35000)
        self.assertEqual(r.materiais, 7300)
        self.assertEqual(r.deslocamento, 3000)
        self.assertEqual(r.mao_de_obra, 13500)
        self.assertEqual(r.custo_total, 23800)
        self.assertEqual(r.resultado, 11200)
        self.assertFalse(r.prejuizo)
        self.assertEqual(r.pendencias, [])

    def test_ct09_prejuizo(self):
        r = self._servico_completo(20000)
        self.assertEqual(r.resultado, -3800)
        self.assertTrue(r.prejuizo)

    def test_ct06_oficina_nao_tem_deslocamento_nem_pendencia(self):
        r = d.calcular_resumo(d.OFICINA, 10000, [], [], [(60, HORA)])
        self.assertIsNone(r.deslocamento)
        self.assertNotIn(d.PENDENCIA_DESLOCAMENTO, r.pendencias)

    def test_ct10_sem_preco_mostra_custos_e_pendencia(self):
        r = self._servico_completo(None)
        self.assertEqual(r.custo_total, 23800)
        self.assertIsNone(r.resultado)
        self.assertEqual(r.pendencias, [d.PENDENCIA_PRECO])

    def test_ct11_externo_sem_km(self):
        r = d.calcular_resumo(d.EXTERNO, 10000, [], [], [(60, HORA)])
        self.assertEqual(r.pendencias, [d.PENDENCIA_DESLOCAMENTO])
        self.assertEqual(r.deslocamento, 0)

    def test_sem_horas_vira_pendencia(self):
        r = d.calcular_resumo(d.OFICINA, 10000, [], [], [])
        self.assertEqual(r.pendencias, [d.PENDENCIA_HORAS])

    def test_rn14_km_guardados_nao_contam_na_oficina(self):
        r = d.calcular_resumo(d.OFICINA, None, [], [(Decimal('25'), KM)], [])
        self.assertIsNone(r.deslocamento)
        self.assertEqual(r.custo_total, 0)

    def test_valores_copiados_diferentes_por_lancamento(self):
        # RN-05: um lançamento a R$ 60/h e outro a R$ 70/h convivem no mesmo serviço.
        r = d.calcular_resumo(d.OFICINA, None, [], [], [(60, 6000), (60, 7000)])
        self.assertEqual(r.mao_de_obra, 13000)


class LeituraTest(SimpleTestCase):
    def test_dinheiro(self):
        self.assertEqual(d.ler_dinheiro('15,50'), 1550)
        self.assertEqual(d.ler_dinheiro('R$ 1.234,56'), 123456)
        self.assertEqual(d.ler_dinheiro('350'), 35000)
        self.assertEqual(d.ler_dinheiro('0'), 0)

    def test_dinheiro_invalido(self):
        for texto in ['', 'abc', '-5', '1,234']:
            with self.subTest(texto=texto), self.assertRaises(d.ValorInvalido):
                d.ler_dinheiro(texto)
        with self.assertRaises(d.ValorInvalido):
            d.ler_dinheiro('0', permitir_zero=False)

    def test_ct14_km_invalido(self):
        for texto in ['-10', 'abc', '0', '2500', '', '1,25']:
            with self.subTest(texto=texto), self.assertRaises(d.ValorInvalido):
                d.ler_km(texto)

    def test_km_valido(self):
        self.assertEqual(d.ler_km('12,5'), Decimal('12.5'))
        self.assertEqual(d.ler_km('2000'), Decimal('2000'))

    def test_quantidade(self):
        self.assertEqual(d.ler_quantidade('2,5'), Decimal('2.5'))
        self.assertEqual(d.ler_quantidade('0,125'), Decimal('0.125'))
        for texto in ['0', '-1', '1,2345']:
            with self.subTest(texto=texto), self.assertRaises(d.ValorInvalido):
                d.ler_quantidade(texto)

    def test_tempo_formatos_aceitos(self):
        casos = {'2h30': 150, '2h': 120, '2 h 30 min': 150, '2:30': 150, '0:45': 45,
                 '150 min': 150, '150min': 150, '45m': 45, '2,5h': 150, '1H30': 90}
        for texto, minutos in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(d.ler_tempo(texto), minutos)

    def test_ct17_numero_sem_unidade_e_ambiguo(self):
        with self.assertRaises(d.TempoAmbiguo) as ctx:
            d.ler_tempo('230')
        self.assertEqual(ctx.exception.opcoes, [('2h30', 150), ('230 min', 230)])
        self.assertIn('2h30 ou 230 min', str(ctx.exception))

    def test_tempo_fora_dos_limites(self):
        for texto in ['0 min', '25h', '0h', '2h75', '2:75', 'abc', '']:
            with self.subTest(texto=texto), self.assertRaises(d.ValorInvalido):
                d.ler_tempo(texto)


class FormatacaoTest(SimpleTestCase):
    def test_reais(self):
        self.assertEqual(d.formatar_reais(35000), 'R$ 350,00')
        self.assertEqual(d.formatar_reais(123456), 'R$ 1.234,56')
        self.assertEqual(d.formatar_reais(-3800), '− R$ 38,00')
        self.assertEqual(d.formatar_reais(5), 'R$ 0,05')
        self.assertEqual(d.formatar_reais(None), '—')

    def test_minutos(self):
        self.assertEqual(d.formatar_minutos(135), '2 h 15 min')
        self.assertEqual(d.formatar_minutos(120), '2 h')
        self.assertEqual(d.formatar_minutos(45), '45 min')

    def test_decimal(self):
        self.assertEqual(d.formatar_decimal(Decimal('12.500')), '12,5')
        self.assertEqual(d.formatar_decimal(Decimal('25.0')), '25')
