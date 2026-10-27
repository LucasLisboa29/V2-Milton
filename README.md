# Custos por Serviço

Sistema web (para celular) que soma materiais, deslocamento e horas de cada serviço do Divino e mostra quanto sobrou depois de cobrar.

Projeto da V2 de **Projeto e Desenvolvimento de Software** (2026/2), feito a partir da especificação do Grupo 2 (*Especificação de Software — Gestão de Custos por Serviço do Divino*, v1.0). Os códigos entre parênteses (RN-05, CT-08...) remetem a essa especificação.

## Stack

- Python 3.12 + Django 5.2 (telas renderizadas no servidor, sem framework de front-end)
- SQLite em desenvolvimento
- Testes com o `unittest` do próprio Django

## Como rodar

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # cria o usuário do Divino
python manage.py runserver
```

Abra http://localhost:8000 e entre com o usuário criado.

## Testes

```bash
python manage.py test
```

São 44 testes, incluindo os casos de aceitação da especificação (CT-01 a CT-20 e CT-31).

## Organização do código

| Arquivo | O que faz |
|---|---|
| `servicos/dominio.py` | **Núcleo do sistema.** Fórmulas de custo e resultado, arredondamento, leitura de "2h30" / "12,5" / "R$ 15,50". Não depende do Django. |
| `servicos/models.py` | Tabelas: configuração, cliente, serviço e os três lançamentos (material, deslocamento, tempo). |
| `servicos/forms.py` | Validação do que é digitado (usa as funções de `dominio`). |
| `servicos/views.py` | Telas: lista, cadastro, detalhe com resumo, lançamentos, preço, configuração e login. |
| `servicos/middleware.py` | Bloqueia todas as telas sem login. |
| `servicos/templates/` e `static/` | HTML e CSS, pensados primeiro para celular. |
| `servicos/tests/` | `test_dominio.py` testa só as contas; `test_telas.py` testa telas + banco. |

## Decisões importantes

- **Dinheiro em centavos inteiros** (P-01). R$ 1,20 é guardado como `120`. Quantidade e km usam `Decimal`, nunca `float`.
- **Arredondamento uma vez por lançamento**, meia unidade para cima (RN-13). Os totais somam centavos já arredondados.
- **Cópia de valores** (RN-05): cada deslocamento guarda o valor do km do dia e cada tempo guarda o valor da hora do dia. Mudar a configuração não altera serviços antigos.
- **Nada de total gravado no banco** (RN-12): o resumo é sempre recalculado no servidor a partir dos lançamentos.
- **Sem lançamento duplicado** (RNF-04): cada formulário leva uma chave única (`chave_idempotencia`). Se o mesmo envio chegar duas vezes, só o primeiro é gravado.
- **Versão do serviço** (UC08): a edição confere a versão para não sobrescrever uma alteração feita em outra aba.

## Sprint 1 — o que está pronto

Meta: *"O Divino lança um serviço completo e vê o resultado."*

- [x] US-01 Login (com bloqueio após 5 tentativas) e configuração do valor por km e da hora
- [x] US-02 Cadastrar serviço (cliente reaproveitado e sugerido ao digitar)
- [x] US-03 Lançar materiais
- [x] US-04 Lançar deslocamento (só em serviço externo)
- [x] US-05 Lançar horas ("2h30", "2:30", "150 min"; "230" pergunta o que se quis dizer)
- [x] US-06 Resumo com custo total, resultado, prejuízo em destaque e pendências
- [x] US-07 Editar serviço e lançamentos (mudança externo → oficina com aviso)
- [x] Busca pelo nome do cliente (adiantada do Sprint 2)

## Sprint 2 — a fazer

- [ ] US-09 Situação do serviço: concluir, reabrir, cancelar (com motivo) e histórico de eventos
- [ ] US-10 Recebimentos e lista "a receber"
- [ ] US-11 Orçamento (aprovar / recusar)
- [ ] US-12 Painel do mês
- [ ] US-07 Excluir serviço sem recebimentos
- [ ] US-08 Filtros por período e situação
- [ ] RF-03 Recuperação de acesso por código
- [ ] Deploy em homologação

## Roteiro da demonstração (Review 1)

1. Entrar e abrir **+ Novo serviço**: cliente "João Pereira", local **Externo**.
2. **+ Material**: 2 × 15,50 e 1 × 42,00 → materiais R$ 73,00.
3. **+ Km**: 25 → R$ 30,00 (aparece "25 km × R$ 1,20 = R$ 30,00").
4. **+ Horas**: 1h30 e depois 0h45 → R$ 135,00.
5. Preço cobrado 350,00 → custo R$ 238,00 e **resultado R$ 112,00**.
6. Em **Valores**, mudar a hora para 70,00 e voltar ao serviço: o resultado continua R$ 112,00.
