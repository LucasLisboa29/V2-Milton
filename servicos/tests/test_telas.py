"""Testes de integração: telas, banco e regras que dependem de persistência."""

import uuid

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from servicos.models import Cliente, Configuracao, Servico, Tempo


class Base(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('divino', password='senha-de-teste-123')
        self.client.force_login(self.usuario)

    def criar_servico(self, local='EXTERNO', cliente='João Pereira'):
        resposta = self.client.post(reverse('servicos:novo'), {
            'cliente': cliente, 'descricao': 'Troca de alternador', 'data': '2026-10-20', 'local': local,
        })
        self.assertEqual(resposta.status_code, 302)
        return Servico.objects.latest('id')

    def lancar(self, servico, tipo, **dados):
        dados.setdefault('chave', str(uuid.uuid4()))
        return self.client.post(reverse('servicos:adicionar', args=[servico.pk, tipo]), dados)


class AcessoTest(TestCase):
    def test_ct20_sem_login_redireciona(self):
        for rota in [reverse('servicos:lista'), reverse('servicos:novo'), reverse('servicos:configuracao')]:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(resposta['Location'].startswith(reverse('login')))

    def test_login_bloqueia_depois_de_5_falhas(self):
        User.objects.create_user('divino', password='senha-de-teste-123')
        for _ in range(5):
            self.client.post(reverse('login'), {'username': 'divino', 'password': 'errada'})
        resposta = self.client.post(reverse('login'), {'username': 'divino', 'password': 'senha-de-teste-123'})
        self.assertEqual(resposta.status_code, 429)


class ServicoTest(Base):
    def test_ct01_sem_cliente_nao_salva(self):
        resposta = self.client.post(reverse('servicos:novo'), {
            'cliente': '', 'descricao': 'x', 'data': '2026-10-20', 'local': 'OFICINA'})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Informe o nome do cliente.')
        self.assertFalse(Servico.objects.exists())

    def test_cliente_reaproveitado_sem_diferenciar_acento(self):
        self.criar_servico(cliente='João Pereira')
        self.criar_servico(cliente='joao  pereira')
        self.assertEqual(Cliente.objects.count(), 1)

    def test_ct31_busca_sem_acento(self):
        self.criar_servico(cliente='João Pereira')
        self.criar_servico(cliente='Maria Souza')
        resposta = self.client.get(reverse('servicos:lista'), {'busca': 'joao'})
        self.assertContains(resposta, 'João Pereira')
        self.assertNotContains(resposta, 'Maria Souza')

    def test_edicao_com_versao_desatualizada_e_recusada(self):
        servico = self.criar_servico()
        dados = {'cliente': 'João Pereira', 'descricao': 'Novo texto', 'data': '2026-10-20',
                 'local': 'EXTERNO', 'versao': servico.versao}
        self.lancar(servico, 'tempo', tempo='1h')  # outra alteração incrementa a versão
        self.client.post(reverse('servicos:editar', args=[servico.pk]), dados)
        servico.refresh_from_db()
        self.assertEqual(servico.descricao, 'Troca de alternador')


class CicloCompletoTest(Base):
    """Roteiro da demonstração da Review 1 (Seção 14.3)."""

    def test_ct08_resultado_112_pela_tela(self):
        servico = self.criar_servico()
        self.lancar(servico, 'material', descricao='Escova', quantidade='2', valor_unitario='15,50')
        self.lancar(servico, 'material', descricao='Regulador', quantidade='1', valor_unitario='42,00')
        self.lancar(servico, 'deslocamento', data='2026-10-20', km='25')
        self.lancar(servico, 'tempo', tempo='1h30')
        self.lancar(servico, 'tempo', tempo='0h45')
        self.client.post(reverse('servicos:preco', args=[servico.pk]), {'preco': '350,00'})

        resposta = self.client.get(reverse('servicos:detalhe', args=[servico.pk]))
        self.assertContains(resposta, 'R$ 238,00')
        self.assertContains(resposta, 'Resultado do serviço: R$ 112,00')
        self.assertContains(resposta, '25 km × R$ 1,20 = R$ 30,00')
        self.assertContains(resposta, 'despesas fixas não entram')

    def test_ct09_prejuizo_em_destaque(self):
        servico = self.criar_servico(local='OFICINA')
        self.lancar(servico, 'tempo', tempo='4h')
        self.client.post(reverse('servicos:preco', args=[servico.pk]), {'preco': '200'})
        resposta = self.client.get(reverse('servicos:detalhe', args=[servico.pk]))
        self.assertContains(resposta, 'Prejuízo: − R$ 40,00')

    def test_ct03_remover_material_recalcula(self):
        servico = self.criar_servico(local='OFICINA')
        self.lancar(servico, 'material', descricao='A', quantidade='2', valor_unitario='15,50')
        self.lancar(servico, 'material', descricao='B', quantidade='1', valor_unitario='42,00')
        caro = servico.materiais.get(descricao='B')
        self.client.post(reverse('servicos:remover', args=[servico.pk, 'material', caro.pk]))
        self.assertEqual(servico.resumo().materiais, 3100)


class CopiaDeValoresTest(Base):
    def test_ct12_e_ct13_mudar_valor_da_hora_nao_altera_lancamentos_antigos(self):
        servico = self.criar_servico(local='OFICINA')
        self.lancar(servico, 'tempo', tempo='1h')

        self.client.post(reverse('servicos:configuracao'), {'valor_km': '1,20', 'valor_hora': '70,00'})
        self.assertEqual(Configuracao.atual().valor_hora_centavos, 7000)
        self.lancar(servico, 'tempo', tempo='1h')

        antigo, novo = servico.tempos.order_by('id')
        self.assertEqual(antigo.valor_hora_centavos, 6000)
        self.assertEqual(novo.valor_hora_centavos, 7000)

        # CT-13: editar os minutos do lançamento antigo mantém R$ 60,00.
        self.client.post(reverse('servicos:editar_lancamento', args=[servico.pk, 'tempo', antigo.pk]),
                         {'tempo': '2h'})
        antigo.refresh_from_db()
        self.assertEqual((antigo.minutos, antigo.valor_hora_centavos), (120, 6000))
        self.assertEqual(servico.resumo().mao_de_obra, 12000 + 7000)

    def test_configuracao_recusa_zero(self):
        resposta = self.client.post(reverse('servicos:configuracao'), {'valor_km': '0', 'valor_hora': '60'})
        self.assertContains(resposta, 'maior que zero')


class LancamentoTest(Base):
    def test_ct18_mesma_chave_duas_vezes_grava_um(self):
        servico = self.criar_servico(local='OFICINA')
        chave = str(uuid.uuid4())
        self.lancar(servico, 'tempo', tempo='1h', chave=chave)
        self.lancar(servico, 'tempo', tempo='1h', chave=chave)
        self.assertEqual(Tempo.objects.count(), 1)

    def test_ct17_tempo_ambiguo_oferece_opcoes(self):
        servico = self.criar_servico(local='OFICINA')
        resposta = self.lancar(servico, 'tempo', tempo='230')
        self.assertEqual(resposta.status_code, 422)
        self.assertContains(resposta, 'Você quis dizer 2h30 ou 230 min?', status_code=422)
        self.assertFalse(Tempo.objects.exists())

    def test_ct14_km_invalido_pela_tela(self):
        servico = self.criar_servico()
        for km in ['-10', 'abc', '0', '2500']:
            with self.subTest(km=km):
                self.assertEqual(self.lancar(servico, 'deslocamento', data='2026-10-20', km=km).status_code, 422)
        self.assertFalse(servico.deslocamentos.exists())

    def test_deslocamento_recusado_em_servico_de_oficina(self):
        servico = self.criar_servico(local='OFICINA')
        self.lancar(servico, 'deslocamento', data='2026-10-20', km='10')
        self.assertFalse(servico.deslocamentos.exists())

    def test_ct19_mudar_para_oficina_e_voltar(self):
        servico = self.criar_servico()
        self.lancar(servico, 'deslocamento', data='2026-10-20', km='25')
        servico.refresh_from_db()

        def mudar(local):
            servico.refresh_from_db()
            return self.client.post(reverse('servicos:editar', args=[servico.pk]), {
                'cliente': 'João Pereira', 'descricao': 'x', 'data': '2026-10-20',
                'local': local, 'versao': servico.versao}, follow=True)

        resposta = mudar('OFICINA')
        self.assertContains(resposta, 'Os km lançados deixam de contar')
        self.assertIsNone(Servico.objects.get(pk=servico.pk).resumo().deslocamento)

        mudar('EXTERNO')
        self.assertEqual(Servico.objects.get(pk=servico.pk).resumo().deslocamento, 3000)

    def test_cancelado_nao_aceita_lancamentos(self):
        servico = self.criar_servico(local='OFICINA')
        Servico.objects.filter(pk=servico.pk).update(situacao=Servico.Situacao.CANCELADO)
        self.lancar(servico, 'tempo', tempo='1h')
        self.assertFalse(Tempo.objects.exists())

    def test_lancamento_de_outro_servico_nao_e_editavel(self):
        a = self.criar_servico(local='OFICINA')
        b = self.criar_servico(local='OFICINA')
        self.lancar(a, 'tempo', tempo='1h')
        tempo = a.tempos.get()
        resposta = self.client.get(reverse('servicos:editar_lancamento', args=[b.pk, 'tempo', tempo.pk]))
        self.assertEqual(resposta.status_code, 404)
