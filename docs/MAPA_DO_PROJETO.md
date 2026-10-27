# Mapa do projeto

Guia para a equipe saber **onde está cada coisa** e **o que cada coisa faz**, inclusive durante a apresentação. Os códigos entre parênteses (RN-05, US-04, CT-08) são da especificação do Grupo 2.

## 1. As pastas em 30 segundos

```
custos-por-servico/
├─ config/               Configuração geral do Django (não tem regra de negócio)
├─ servicos/             O SISTEMA: tudo que o Divino usa está aqui
│  ├─ dominio.py         ★ As contas (custos, resultado, arredondamento)
│  ├─ models.py          As tabelas do banco
│  ├─ forms.py           A validação do que é digitado
│  ├─ views.py           O que acontece em cada tela
│  ├─ urls.py            Qual endereço abre qual tela
│  ├─ middleware.py      Bloqueia tudo sem login
│  ├─ templates/         O HTML das telas
│  ├─ static/            O CSS (visual para celular)
│  ├─ templatetags/      Formatação de R$ e horas no HTML
│  ├─ migrations/        Criação das tabelas (gerado pelo Django)
│  └─ tests/             Os 44 testes automáticos
├─ docs/                 Este guia
├─ .github/workflows/    Roda os testes no GitHub a cada push
├─ README.md             Como rodar, deploy e roteiro da demonstração
├─ requirements.txt      Bibliotecas usadas
└─ manage.py             Comando do Django (runserver, migrate, test)
```

**A ideia em camadas** (Seção 13.1 da especificação):

```
Tela (templates)  →  views.py  →  forms.py  →  dominio.py  →  models.py  →  banco
   o que vê        o que faz      valida o      faz as         guarda os
                                  que digitou   contas         dados
```

O `dominio.py` não conhece Django nem banco: recebe números e devolve números. Por isso é fácil de testar e de explicar.

## 2. Cada arquivo, o que faz

### `servicos/dominio.py` ★ o coração do sistema

| Função | O que faz | Regra |
|---|---|---|
| `arred` | Arredonda para o centavo, meia unidade para cima (4,5 → 5) | RN-13 |
| `custo_material` | quantidade × valor unitário | RN-02 |
| `custo_deslocamento` | km × valor por km | RN-03 |
| `custo_tempo` | minutos × valor da hora ÷ 60 (multiplica **antes** de dividir) | RN-04 |
| `calcular_resumo` | Soma tudo, calcula resultado, saldo e pendências | RN-06 a RN-09, RN-14 |
| `Resumo` | O "pacote" com os totais que a tela mostra; `prejuizo` diz se o resultado é negativo | RN-08 |
| `ler_dinheiro` | "15,50" → 1550 centavos | RN-11 |
| `ler_quantidade` | "2,5" → 2.5 (até 3 casas) | P-02 |
| `ler_km` | "12,5" → 12.5 (de 0,1 a 2.000) | P-03 |
| `ler_tempo` | "2h30", "2:30", "150 min", "2,5h" → minutos; "230" pergunta | RF-12, UC06 |
| `formatar_reais` | 35000 → "R$ 350,00"; −3800 → "− R$ 38,00" | RNF-09 |
| `formatar_minutos` | 135 → "2 h 15 min" | — |

### `servicos/models.py` — as tabelas

| Classe | Tabela | Detalhe importante |
|---|---|---|
| `Configuracao` | Valor por km e valor da hora | Uma linha só; `atual()` pega ou cria |
| `Cliente` | Nome e telefone | `nome_busca` sem acento: "joao" acha "João"; `obter_ou_criar` evita cliente repetido (D-03) |
| `Servico` | O atendimento | `preco_centavos`, `local`, `situacao`, `versao`; `resumo()` chama o `dominio` |
| `Material` | Lançamento de material | `conta` monta o texto "2 × R$ 15,50 = R$ 31,00" |
| `Deslocamento` | Lançamento de km | Guarda `valor_km_centavos` **copiado** no dia (RN-05) |
| `Tempo` | Lançamento de horas | Guarda `valor_hora_centavos` **copiado** no dia (RN-05) |
| `Lancamento` | Base dos três acima | `chave_idempotencia`: impede lançamento duplicado |

Nenhum total fica gravado no banco. O resumo é sempre recalculado a partir dos lançamentos (RN-12).

### `servicos/views.py` — o que cada tela faz

| Função | Tela / ação | História |
|---|---|---|
| `EntrarView` | Login; bloqueia após 5 tentativas erradas | US-01 |
| `configuracao` | Tela "Valores" (km e hora) | US-01 |
| `lista` | Lista de serviços + busca por cliente | US-08 |
| `novo` | Cadastrar serviço | US-02 |
| `editar` | Editar serviço; confere a `versao`; avisa se externo virou oficina | US-07 |
| `detalhe` | Tela do serviço com resumo e lançamentos | US-06 |
| `definir_preco` | Salvar o preço cobrado | US-06 |
| `adicionar_lancamento` | + Material / + Km / + Horas (com trava e anti-duplicação) | US-03, 04, 05 |
| `editar_lancamento` / `remover_lancamento` | Editar ou remover um lançamento | US-07 |
| `_aplicar` | Copia o valor do km/hora **só na criação**; editar mantém o valor antigo | RN-05 |

### Outros arquivos de `servicos/`

| Arquivo | O que faz |
|---|---|
| `forms.py` | Um formulário por tela (`ServicoForm`, `MaterialForm`, `DeslocamentoForm`, `TempoForm`, `PrecoForm`, `ConfiguracaoForm`). Cada `clean_...` usa uma função `ler_...` do `dominio`. Cada formulário de lançamento leva uma `chave` única escondida. |
| `urls.py` | Liga endereços a views. Ex.: `/servicos/1/tempo/` → `adicionar_lancamento`. |
| `middleware.py` | `LoginObrigatorioMiddleware`: sem login, qualquer endereço manda para a tela de entrar (RNF-05). |
| `templatetags/dinheiro.py` | Filtros usados no HTML: `\|reais`, `\|duracao`, `\|decimal_br`. |
| `static/servicos/estilo.css` | Visual pensado para celular: botões de 44 px, texto de 16 px, sem rolagem lateral (RNF-01). |

### `servicos/templates/servicos/` — as telas

| Arquivo | Tela |
|---|---|
| `base.html` | Moldura de todas as telas (topo, mensagens, trava de toque duplo no botão) |
| `entrar.html` | Login |
| `lista.html` | Lista de serviços com busca |
| `servico_form.html` | Novo serviço / editar serviço |
| `detalhe.html` | Resumo, preço, pendências, materiais, km e horas |
| `lancamento_form.html` | Editar um lançamento |
| `configuracao.html` | Valor por km e da hora |
| `_campos.html`, `_botoes_lancamento.html` | Pedaços reaproveitados (campos de formulário e botões Editar/Remover) |

### `config/` — configuração

| Arquivo | O que faz |
|---|---|
| `settings.py` | Idioma pt-BR, fuso de São Paulo, banco (SQLite no PC, PostgreSQL na Vercel), segurança do cookie de sessão, DEBUG desligado na Vercel |
| `urls.py` | Endereços de entrar/sair + inclui os de `servicos` |
| `wsgi.py`, `asgi.py` | Ponto de entrada do servidor (gerado pelo Django) |

### `servicos/tests/` — os testes

| Arquivo | O que testa |
|---|---|
| `test_dominio.py` | Só as contas e a leitura do que é digitado. Usa os valores dos CT da especificação (CT-02 a CT-17). |
| `test_telas.py` | Telas + banco: login obrigatório, ciclo completo dando R$ 112,00, cópia de valores, anti-duplicação, busca sem acento, versão desatualizada. |

Rodar: `python manage.py test` (no GitHub roda sozinho a cada push).

## 3. Onde está cada história do Sprint 1

| História | Tela | Código principal | Teste |
|---|---|---|---|
| US-01 Entrar e configurar valores | `entrar.html`, `configuracao.html` | `EntrarView`, `configuracao`, `middleware.py` | `AcessoTest`, `CopiaDeValoresTest` |
| US-02 Cadastrar serviço | `servico_form.html` | `novo`, `Cliente.obter_ou_criar` | `ServicoTest` |
| US-03 Lançar materiais | `detalhe.html` (+ Material) | `adicionar_lancamento`, `custo_material` | `test_ct02`, `test_ct03`, `test_ct15`, `test_ct16` |
| US-04 Lançar deslocamento | `detalhe.html` (+ Km) | `adicionar_lancamento`, `custo_deslocamento`, `ler_km` | `test_ct04`, `test_ct05`, `test_ct14` |
| US-05 Lançar horas | `detalhe.html` (+ Horas) | `adicionar_lancamento`, `custo_tempo`, `ler_tempo` | `test_ct07`, `test_ct17`, `test_ct18` |
| US-06 Ver custo e resultado | `detalhe.html` (Resumo) | `calcular_resumo`, `definir_preco` | `test_ct08`, `test_ct09`, `test_ct10`, `test_ct11` |
| US-07 Corrigir serviço | `servico_form.html`, `lancamento_form.html` | `editar`, `editar_lancamento`, `remover_lancamento` | `test_ct19`, `test_edicao_com_versao...` |
| US-08 Buscar pelo cliente (adiantada) | `lista.html` | `lista`, `normalizar` | `test_ct31` |

## 4. O caminho de um clique: "+ Horas" com "1h30"

Bom para explicar como as peças se encaixam:

1. **Tela** (`detalhe.html`): o Divino digita "1h30" e toca em *Salvar horas*. O formulário envia junto uma `chave` única.
2. **Endereço** (`urls.py`): `/servicos/1/tempo/` chama `adicionar_lancamento`.
3. **Validação** (`forms.py`, `TempoForm.clean_tempo`): chama `dominio.ler_tempo("1h30")` → 90 minutos.
4. **Trava** (`views.py`, `_servico_travado`): trava o serviço no banco enquanto grava.
5. **Anti-duplicação**: se a mesma `chave` já existe, não grava de novo (toque duplo).
6. **Cópia do valor** (`_aplicar`): lê R$ 60,00 da `Configuracao` e grava **no próprio lançamento**.
7. **Banco** (`models.py`, `Tempo`): salva 90 minutos + R$ 60,00/h.
8. **Volta para a tela**: `detalhe` chama `servico.resumo()` → `dominio.calcular_resumo` refaz todas as contas → a tela mostra "1 h 30 min × R$ 60,00/h = R$ 90,00".

## 5. Perguntas que o professor pode fazer

**Por que guardar dinheiro em centavos?**
Porque `float` erra contas simples (0,1 + 0,2 dá 0,30000000000000004). Em centavos inteiros (R$ 1,20 = 120) não há erro. Quantidade e km usam `Decimal`, que é exato. Ver `dominio.py`.

**Se o Divino aumentar o valor da hora, os serviços antigos mudam?**
Não. Cada lançamento guarda o valor do dia em que foi feito (`valor_hora_centavos` em `Tempo`). Só os lançamentos novos usam o valor novo. Teste: `test_ct12_e_ct13...`.

**E se ele tocar duas vezes em "Salvar" com internet ruim?**
Cada formulário tem uma `chave` única. O servidor só grava a primeira vez. Teste: `test_ct18...`.

**Por que o resultado não é chamado de lucro?**
Porque aluguel, luz e outras despesas fixas não entram na conta. A tela avisa isso (RN-10).

**Onde o resultado é calculado, no navegador ou no servidor?**
Sempre no servidor (`calcular_resumo`). Nenhum total fica gravado no banco: é recalculado toda vez a partir dos lançamentos (RN-12).

**O que acontece se o serviço externo virar "oficina"?**
Os km ficam guardados mas param de contar, e o sistema avisa. Voltando para externo, eles voltam (RN-14, `test_ct19`).

**Como a IA foi usada?**
O Claude Code leu a especificação do Grupo 2, propôs a estrutura e gerou o código e os testes. A equipe escolheu a stack (Django), revisou o código, testou a demonstração no navegador e fez o deploy na Vercel. Cada regra no código tem um comentário com o código da especificação (RN-xx), o que facilita conferir.

**Por que Django?**
Já traz login, banco e formulários prontos, o que coube no prazo de um Sprint. O `Decimal` do Python resolve a precisão do dinheiro.

## 6. O que fica para o Sprint 2

Situação do serviço (concluir, reabrir, cancelar), recebimentos e lista "a receber", orçamento, painel do mês, excluir serviço, filtros por período e situação, recuperação de acesso. Lista completa no `README.md`.
