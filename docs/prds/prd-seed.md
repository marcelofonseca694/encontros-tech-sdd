# PRD — Semeadura de Eventos de Demonstração (Seed)

**Status:** em revisão
**Data:** 2026-09-08
**Origem:** sessão de brainstorm sobre automatizar a população inicial do catálogo de eventos

---

## 1. Contexto

**Produto.** Encontros Tech é uma aplicação web de cadastro e consulta de eventos, com interface de páginas e uma API. Um evento é composto por título, descrição, data, local e um token de edição — o token é a única credencial que autoriza alterar um evento depois de criado.

**Estado atual.** Uma instalação recém-preparada não contém nenhum evento. A primeira coisa que qualquer pessoa vê é a tela de catálogo vazio. Para obter um catálogo utilizável, existe hoje um conjunto de dez requisições de criação mantidas à mão em `api-requests.http`, disparadas uma a uma por um cliente REST. Isso funciona para uma pessoa em frente ao editor e não funciona para mais nada.

**Problema de negócio.** A ausência de dados iniciais custa em três frentes:

| Situação | O que se deseja | O que acontece hoje |
|---|---|---|
| Desenvolvimento local | Abrir a aplicação e ver um catálogo representativo | Dez disparos manuais, ou uma tela vazia |
| Pipeline automatizada | Um ambiente com dados conhecidos, sem intervenção humana | Impossível — não há como um agente automatizado disparar as requisições do arquivo |
| Demonstração | Catálogo com eventos que fazem sentido na data de hoje | As datas do conjunto de referência são de 2024 e já venceram |

A consequência é dupla: **atrito recorrente** (todo ambiente novo exige o mesmo trabalho manual) e **impossibilidade de automação** (nenhum ambiente efêmero pode nascer com dados sem uma pessoa presente).

**Objetivo.** Existir uma operação acionável — por uma pessoa ou por um agente automatizado — que leve um catálogo vazio a um catálogo de demonstração utilizável, de forma repetível e sem risco de danificar dados existentes.

---

## 2. Atores

| Ator | Natureza | Papel nesta feature |
|---|---|---|
| **Pessoa desenvolvedora** | Humano | Aciona a semeadura ao preparar um ambiente local. Precisa entender, pela saída, o que aconteceu. |
| **Agente automatizado** (pipeline CI/CD) | Sistema | Aciona a semeadura como um passo entre subir o ambiente e executar verificações. Decide continuar ou abortar a partir do resultado, sem interpretar texto. |
| **Rotina de semeadura** | Operação acionável | Avalia o estado do catálogo e, apenas quando ele está vazio, cria o conjunto de eventos de demonstração. Reporta o que fez. |
| **Aplicação Encontros Tech** | Processo em execução | Prepara o armazenamento de eventos durante sua inicialização. Não participa da semeadura e não sabe que foi semeada. |
| **Armazenamento de eventos** | Dependência | Pode estar não preparado, vazio, ou já conter eventos — de origem semeada, humana ou mista. Cada estado produz um resultado distinto. |
| **Usuário final** | Humano | Consome os eventos semeados como consumiria qualquer outro. Não distingue uns dos outros, e não deve conseguir distinguir. |

---

## 3. Predicados verificáveis

### Acionamento

**P1 — Iniciar a aplicação nunca semeia**
Dado que o armazenamento de eventos está vazio
Quando a aplicação é iniciada, por qualquer meio e com qualquer número de processos simultâneos
Então nenhum evento passa a existir em consequência da inicialização.

**P2 — Semeadura em catálogo vazio**
Dado que o armazenamento de eventos está preparado e não contém nenhum evento
Quando a semeadura é acionada
Então o conjunto completo de eventos de demonstração passa a existir, e a operação é reportada como bem-sucedida.

**P3 — Armazenamento não preparado é falha**
Dado que o armazenamento de eventos não está preparado, ou está inacessível
Quando a semeadura é acionada
Então nenhum evento passa a existir, a operação é reportada como falha, e a causa fica registrada de forma que permita diagnóstico.
*(Este predicado é a razão de a semeadura não preparar o armazenamento por conta própria: se o armazenamento não está pronto, a aplicação também não está, e mascarar isso esconderia a falha real.)*

### Idempotência

**P4 — Catálogo não vazio é inviolável**
Dado que o armazenamento contém pelo menos um evento, de qualquer origem
Quando a semeadura é acionada
Então nenhum evento é criado, alterado ou removido, e a operação é reportada como **bem-sucedida**.
*(Reportar sucesso é deliberado: "o catálogo já tem conteúdo" é o estado desejado, não um erro. Uma pipeline não deve quebrar por acionar a semeadura duas vezes.)*

**P5 — Repetição é inofensiva**
Dado que a semeadura já foi executada com sucesso
Quando é acionada novamente, qualquer número de vezes
Então a quantidade e o conteúdo dos eventos permanecem idênticos ao resultado da primeira execução.

**P6 — Evento humano bloqueia a semeadura**
Dado que o armazenamento estava vazio e uma pessoa cadastrou um evento pela aplicação
Quando a semeadura é acionada
Então nada é criado, e o catálogo permanece com apenas aquele evento.
*(Consequência aceita: quem quiser um catálogo de demonstração a partir daí precisa esvaziar o armazenamento por fora desta feature. O custo é atrito ocasional em desenvolvimento; o benefício é que a regra que protege o dado da pessoa é a mesma que impede a semeadura de tocar em um ambiente real, sem depender de nenhuma configuração adicional.)*

### Atomicidade

**P7 — Tudo ou nada**
Dado que a semeadura está em curso e encontra uma falha antes de concluir
Quando a operação termina
Então o armazenamento fica exatamente como estava antes do acionamento, sem nenhum evento parcialmente semeado, e a operação é reportada como falha.

**P8 — Falha não impede nova tentativa**
Dado que uma semeadura falhou por qualquer causa
Quando a causa é corrigida e a semeadura é acionada novamente
Então ela executa integralmente, como se fosse a primeira execução.
*(Sem P7, este predicado seria impossível: um catálogo parcialmente semeado deixaria de estar vazio e, por P4, nunca mais seria completado — o estado parcial se tornaria permanente.)*

### Conteúdo semeado

**P9 — Eventos de demonstração são eventos futuros**
Dado que a semeadura é acionada em qualquer data
Quando os eventos passam a existir
Então todos têm data posterior ao instante do acionamento.
*(Este predicado é a razão de as datas não serem copiadas do conjunto de referência: datas fixas envelhecem, e a aplicação não filtra eventos passados em lugar nenhum — um catálogo semeado com datas vencidas abriria mostrando eventos de anos atrás.)*

**P10 — Distribuição temporal preservada**
Dado o conjunto de eventos semeados
Quando suas datas são comparadas entre si
Então mantêm a ordem cronológica e o espaçamento relativo do conjunto de referência, deslocadas por uma constante de forma que o primeiro evento caia 3 dias após o acionamento e o último aproximadamente dois meses depois (58 dias, preservando o span original de 55 dias entre as dez datas de referência).

**P11 — Conteúdo derivado do conjunto de referência**
Dado o conjunto de eventos semeados
Quando é comparado com o conjunto de dez eventos hoje mantido em `api-requests.http`
Então corresponde a todos os dez, com título, descrição e local preservados, e apenas as datas reajustadas conforme P9 e P10.

**P12 — Sem informação de tecnologias**
Dado que o armazenamento de eventos não registra tecnologias associadas a um evento
Quando os eventos são semeados
Então nenhuma informação de tecnologia é registrada nem prometida, e a ausência dela não é reportada como erro.

**P13 — Eventos semeados são indistinguíveis de eventos reais**
Dado um evento semeado
Quando é consultado por qualquer caminho da aplicação — listagem, busca, detalhe, edição por token
Então se comporta exatamente como um evento cadastrado por uma pessoa, e nenhum campo, marcação ou caminho permite identificá-lo como semeado.
*(Consequência aceita: não existe forma de remover "apenas os eventos semeados". Isso é coerente com P4 e P6 — a unidade de decisão desta feature é o catálogo inteiro, nunca um subconjunto.)*

**P14 — Token de edição próprio e imprevisível**
Dado o conjunto de eventos semeados
Quando os tokens de edição são examinados
Então cada evento possui um token único, não derivável de seu conteúdo e não reproduzível entre duas execuções da semeadura.
*(Este predicado renuncia deliberadamente a URLs de edição previsíveis para verificação automatizada. O token é o único controle de acesso do produto: um token conhecido publicamente, se alcançasse um ambiente real, autorizaria qualquer pessoa a alterar aquele evento.)*

### Resultado e observabilidade

**P15 — Resultado inteligível para pessoas**
Dado qualquer acionamento da semeadura
Quando a operação termina
Então fica registrado qual dos três desfechos ocorreu — semeou e quantos eventos criou, não semeou porque o catálogo já tinha conteúdo, ou falhou e por quê.

**P16 — Sucesso e falha distinguíveis sem interpretar texto**
Dado um agente automatizado que aciona a semeadura
Quando a operação termina
Então o agente distingue sucesso de falha sem analisar mensagens, sendo "semeou" e "não semeou porque já havia conteúdo" ambos sucesso, e apenas falha efetiva reportada como falha.

**P17 — Semeadura não distorce a observabilidade do negócio**
Dado que a semeadura criou eventos
Quando os indicadores e registros de negócio da aplicação são analisados
Então as criações de demonstração não aparecem como criações de evento de negócio.
*(Semear é preparação de ambiente, não atividade de negócio. Contá-las junto tornaria qualquer indicador de "eventos criados" inútil em ambientes semeados.)*

### Convivência com o produto

**P18 — Nenhuma funcionalidade muda de comportamento**
Dado que a semeadura passa a existir
Quando qualquer funcionalidade de eventos é exercitada
Então seu comportamento observável é idêntico ao anterior, e a aplicação funciona igualmente em um catálogo semeado ou vazio.

**P19 — Semear não interrompe o atendimento**
Dado que a aplicação está em execução atendendo requisições
Quando a semeadura é acionada
Então o atendimento não é interrompido nem passa a produzir erro.

---

## 4. Invariantes

1. **A semeadura nunca altera nem remove dado preexistente.** Sua única ação possível sobre o armazenamento é criar eventos, e apenas quando não há nenhum.
2. **O armazenamento nunca fica parcialmente semeado.** Todo acionamento termina com o catálogo vazio, ou com o conjunto completo, ou exatamente como estava.
3. **Iniciar a aplicação nunca semeia.** Nenhuma etapa do ciclo de vida da aplicação cria eventos de demonstração.
4. **Semear nunca é pré-requisito para a aplicação funcionar.** Um catálogo vazio é um estado válido e integralmente operante do produto.
5. **Eventos semeados são indistinguíveis de eventos reais**, para o usuário final e para a própria aplicação.
6. **Nenhum token de edição é previsível ou reproduzível**, independentemente da origem do evento.
7. **A regra de catálogo vazio é a única condição de segurança.** Não existe uma segunda trava que possa ser desativada, esquecida ou configurada errado.

---

## 5. Restrições

- **Acionamento explícito.** A semeadura só ocorre quando alguém ou algo a aciona deliberadamente. Nenhum acionamento implícito, automático ou embutido em outra operação.
- **Ordem de execução.** A semeadura pressupõe o armazenamento de eventos já preparado. Como a preparação acontece hoje durante a inicialização da aplicação, isso significa que a semeadura só é acionável depois de a aplicação ter subido ao menos uma vez no ambiente. *(Premissa — confirme ou corrija: em pipeline, o passo anterior aguarda a aplicação responder antes de acionar a semeadura. Quando os sinais de prontidão descritos em `prd-health-ready.md` existirem, o sinal de prontidão passa a ser o critério correto dessa espera, e nenhuma alteração desta feature será necessária.)*
- **Mesmo armazenamento da aplicação.** A semeadura atua sobre o mesmo catálogo que a aplicação usa, com a mesma configuração de ambiente. Não possui configuração, credencial ou endereço próprios. *(Premissa — confirme ou corrija.)*
- **Conjunto de dados editável sem alterar lógica.** Trocar, acrescentar ou remover um evento de demonstração é uma alteração de dado, não de comportamento — não deve exigir compreensão da regra de semeadura. *(Premissa — confirme ou corrija.)*
- **`api-requests.http` permanece.** Continua sendo o único artefato que exercita o campo de tecnologias na entrada da API, algo que a semeadura não faz por P12. Os dois convivem com propósitos distintos e não se substituem.
- **Sem restrição por ambiente.** A semeadura não pergunta em que ambiente está: por P4, um catálogo com conteúdo já a impede de agir, e um ambiente real nunca tem catálogo vazio.

---

## 6. Fora do escopo

| Item | Por quê |
|---|---|
| **Modo destrutivo** (esvaziar o catálogo antes de semear) | Seria o único caminho desta feature capaz de destruir dado. O ganho é evitar uma limpeza manual ocasional em desenvolvimento; o custo é um comando que, apontado para o armazenamento errado, é irreversível. Decidido explicitamente: repopular após P6 é sempre manual. |
| **Semeadura durante a inicialização da aplicação** | Colidiria com os invariantes de `prd-health-ready.md` — a inicialização não pode depender do armazenamento nem falhar por causa dele. Além disso, com múltiplos processos de aplicação, a semeadura ocorreria uma vez por processo, sem coordenação. |
| **Registrar tecnologias dos eventos** | O armazenamento de eventos não possui esse conceito hoje. Incluí-lo transformaria esta entrega em uma alteração do modelo de dados, com risco e escopo próprios. Fica registrado como lacuna conhecida — **os eventos semeados são mais pobres que suas versões em `api-requests.http`.** |
| **Reconciliar ou atualizar eventos já existentes** | Exigiria uma chave estável por evento, que hoje não existe, e reintroduziria a possibilidade de a semeadura alterar dado — o oposto do invariante 1. |
| **Tokens de edição fixos e conhecidos** | Ver P14. Facilitaria verificação automatizada da edição, ao custo de expor o único controle de acesso do produto. |
| **Marcar a origem de um evento** (semeado × cadastrado) | Ver P13. Tornaria possível remover apenas os semeados, mas acrescentaria ao modelo de dados um conceito que só existe para servir a esta feature, visível a todo o produto. |
| **Semeadura de outras entidades** | Evento é a única entidade do produto hoje. |
| **Definição da pipeline** (etapas, ambiente, orquestração) | Esta entrega descreve uma operação acionável e seu contrato de resultado. Como e onde a pipeline a aciona é decisão de infraestrutura, fora do comportamento do produto. |
| **Aposentar `api-requests.http`** | Ver restrições: ele cobre um campo que a semeadura não cobre. |

---

## 7. Critérios de aceite

A feature está pronta quando **todos** os itens abaixo são verificáveis por observação direta:

**Comportamento**
1. Com o armazenamento preparado e vazio, acionar a semeadura resulta em dez eventos no catálogo e resultado de sucesso.
2. Acionar a semeadura imediatamente depois resulta em nenhuma alteração — os mesmos dez eventos, com os mesmos identificadores e tokens — e resultado de sucesso.
3. Com o armazenamento vazio, cadastrar um único evento pela aplicação e então acionar a semeadura resulta em nenhuma alteração: o catálogo permanece com aquele único evento.
4. Com o armazenamento inacessível ou não preparado, acionar a semeadura resulta em falha, sem nenhum evento criado, com a causa registrada.
5. Interromper a semeadura no meio da execução deixa o catálogo vazio; acionar novamente em seguida produz os dez eventos.
6. Iniciar a aplicação sobre um catálogo vazio, por qualquer meio, não cria nenhum evento.

**Conteúdo**
7. Todos os eventos semeados têm data posterior ao instante do acionamento; o primeiro cai 3 dias após o acionamento, e o intervalo até o último é de aproximadamente dois meses (58 dias).
8. Título, descrição e local de cada evento semeado correspondem aos do evento equivalente em `api-requests.http`.
9. Os dez eventos possuem tokens de edição distintos entre si; duas semeaduras em armazenamentos limpos produzem vinte tokens distintos.
10. Cada evento semeado é acessível por listagem, busca, detalhe e edição por token exatamente como um evento cadastrado pela aplicação.

**Contrato de resultado**
11. Um agente automatizado distingue os três desfechos sem interpretar texto: semeou e já-havia-conteúdo são sucesso, falha é falha.
12. A saída de cada um dos três desfechos permite a uma pessoa entender o que ocorreu sem consultar código.

**Observabilidade**
13. Após uma semeadura, os indicadores e registros de negócio não contabilizam as criações de demonstração como criação de evento.

**Verificação automatizada**
14. Existe suíte de testes automatizados cobrindo, no mínimo: semeadura em catálogo vazio, semeadura bloqueada por catálogo com conteúdo, falha por armazenamento indisponível, e ausência de estado parcial após falha no meio da execução.
15. A suíte roda junto com os testes existentes do projeto, em um único comando, sem depender de um armazenamento real em execução.

---

## Premissas confirmadas

| # | Premissa | Onde aparece | Confirmação |
|---|---|---|---|
| 1 | Distribuição das datas: primeiro evento poucos dias à frente, último cerca de dois meses depois | P10, aceite 7 | Confirmado: primeiro evento 3 dias após o acionamento, deslocamento constante que preserva o span original de 55 dias entre as dez datas de referência (último evento a 58 dias) |
| 2 | Em pipeline, a espera pela aplicação precede o acionamento da semeadura; o sinal de prontidão de `prd-health-ready.md`, quando existir, passa a ser o critério dessa espera | Restrições | Confirmado: `/health` e `/ready` já existem (`add-health-ready-endpoints`) |
| 3 | A semeadura usa a mesma configuração de armazenamento da aplicação, sem configuração própria | Restrições | Confirmado: `seed.py` reutiliza `core.settings`/`core.database` sem configuração própria |
| 4 | O conjunto de eventos de demonstração é alterável como dado, sem exigir alteração da regra de semeadura | Restrições | Confirmado: conjunto de referência isolado em `seed_data.py`, separado da lógica de `seed.py` |
| 5 | Cobertura por testes automatizados, nos mesmos moldes do PRD de saúde e prontidão | Aceite 14 e 15 | Confirmado: `src/tests/test_seed.py`, sessão mockada, sem banco real |
