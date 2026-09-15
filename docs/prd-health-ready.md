# PRD — Endpoints de Saúde e Prontidão (`/health` e `/ready`)

**Status:** em revisão
**Data:** 2026-08-17
**Origem:** sessão de brainstorm sobre preparação da aplicação para operação em Kubernetes. Revisado em 2026-09-15 para incorporar o ADR 001, que retirou a preparação do schema de dentro do processo da aplicação

---

## 1. Contexto

**Produto.** Encontros Tech é uma aplicação web de cadastro e consulta de eventos, com interface de páginas e uma API. Depende de um banco de dados relacional para toda operação de negócio: sem ele, nenhuma funcionalidade útil existe.

**Estado atual.** A aplicação não expõe nenhum sinal de ciclo de vida para um orquestrador. A preparação do armazenamento de eventos não acontece mais dentro do processo da aplicação: por decisão do ADR 001, é etapa separada e anterior, executada a partir da mesma imagem, da qual a aplicação depende para subir. A aplicação, portanto, nunca cria estruturas — apenas as encontra prontas ou não —, e a ausência do armazenamento deixa de ser detectada na inicialização para se manifestar na primeira consulta ao banco, mais tarde e mais perto do usuário.

**Problema de negócio.** O destino da aplicação é operação em Kubernetes. Sem sinais de ciclo de vida, o orquestrador não consegue distinguir três situações que exigem respostas opostas:

| Situação real | Resposta correta | O que acontece hoje |
|---|---|---|
| Processo travado/corrompido | Reiniciar a instância | Nada — instância travada continua recebendo tráfego |
| Dependência externa indisponível | Parar de enviar tráfego, **não** reiniciar | Nada distingue dependência fora de aplicação quebrada — o tráfego continua chegando |
| Instância ainda inicializando | Aguardar antes de enviar tráfego | Tráfego chega antes da instância poder atender |

A consequência de negócio é dupla: **indisponibilidade percebida pelo usuário** (requisições roteadas para instâncias incapazes de atender, resultando em erro) e **operação cega** (nenhum sinal automatizável distingue falha da aplicação de falha de dependência, o que atrasa diagnóstico e recuperação).

**Objetivo.** Expor dois sinais distintos e independentes — "este processo está vivo" e "esta instância consegue atender tráfego agora" — de modo que o orquestrador possa reiniciar apenas o que está quebrado e rotear tráfego apenas para o que funciona.

---

## 2. Atores

| Ator | Natureza | Papel nesta feature |
|---|---|---|
| **Orquestrador** (Kubernetes) | Sistema automatizado | Consulta os dois endpoints em intervalo regular. Reinicia a instância quando o sinal de vida falha; remove a instância do balanceamento quando o sinal de prontidão falha. Não lê nem interpreta corpo de resposta — atua apenas sobre o código de status. |
| **Processo da aplicação** | Instância em execução | Responde aos dois sinais. Não prepara o armazenamento de eventos e não guarda memória de tentativa de preparo: cada consulta de prontidão avalia a condição corrente. |
| **Rotina de preparação de schema** | Etapa anterior e independente | Cria as estruturas ausentes do armazenamento antes de a aplicação subir (ADR 001). Não participa das verificações e não é consultada por elas — seu resultado é observado pela aplicação apenas como o armazenamento estar ou não legível. |
| **Banco de dados** | Dependência externa | Pode estar indisponível, disponível-mas-lento, ou disponível-sem-o-armazenamento-de-eventos-preparado. Cada estado precisa produzir um sinal de prontidão correto. |
| **Pessoa operadora** | Humano | Consome os mesmos endpoints manualmente em diagnóstico. Não é público-alvo primário: o contrato é desenhado para o orquestrador. |
| **Usuário final** | Humano | Não interage com os endpoints. É quem sofre a consequência de um sinal errado (erro ao acessar a aplicação). |

---

## 3. Predicados verificáveis

### Sinal de vida (`/health`)

**P1 — Vivo responde vivo**
Dado que o processo da aplicação está em execução e respondendo a requisições HTTP
Quando o orquestrador consulta `/health`
Então a resposta tem código de status `200`.

**P2 — Sinal de vida é independente de dependência externa**
Dado que o banco de dados está totalmente indisponível
Quando o orquestrador consulta `/health`
Então a resposta tem código de status `200`, indistinguível da resposta com o banco disponível.

**P3 — Sinal de vida não depende do estado do armazenamento**
Dado que o armazenamento de eventos não está preparado
Quando o orquestrador consulta `/health`
Então a resposta tem código de status `200`.

### Sinal de prontidão (`/ready`)

**P4 — Pronto quando consegue atender**
Dado que o banco de dados está disponível e o armazenamento de eventos está preparado e legível
Quando o orquestrador consulta `/ready`
Então a resposta tem código de status `200`.

**P5 — Não pronto quando a dependência está fora**
Dado que o banco de dados está indisponível
Quando o orquestrador consulta `/ready`
Então a resposta tem código de status `503`.

**P6 — Não pronto quando o armazenamento não está utilizável**
Dado que o banco de dados está disponível, porém o armazenamento de eventos não existe ou não é legível pela aplicação
Quando o orquestrador consulta `/ready`
Então a resposta tem código de status `503`.
*(Este predicado é a razão de o sinal de prontidão não se limitar a verificar conexão: uma instância conectada a um banco sem o armazenamento preparado falharia em toda requisição de negócio, e declarar-se pronta seria mentir.)*

**P7 — Prontidão acompanha a recuperação da dependência**
Dado que o armazenamento de eventos está preparado e o banco tornou-se indisponível em seguida
Quando o banco volta a ficar disponível
Então a próxima consulta a `/ready` responde `200`, sem necessidade de reiniciar a instância.

**P8 — Prontidão acompanha a preparação do armazenamento, sem reinício**
Dado que a etapa de preparação de schema não foi executada com sucesso e o armazenamento de eventos não existe
Quando a etapa é executada com sucesso, com a aplicação já em execução
Então a próxima consulta a `/ready` responde `200`, sem necessidade de reiniciar a instância.
*(Consequência do ADR 001: como a aplicação não prepara o armazenamento, ela também não guarda o resultado de uma tentativa de preparo. A prontidão passa a ser função exclusiva da condição corrente da dependência, e não do histórico da instância — o que elimina a classe de instância permanentemente não-pronta que existiria se o preparo ocorresse dentro do processo.)*

### Inicialização

**P9 — Dependência indisponível não impede a inicialização**
Dado que o banco de dados está indisponível
Quando o processo da aplicação é iniciado
Então o processo permanece em execução, `/health` responde `200` e `/ready` responde `503`.

**P10 — A causa da não-prontidão é registrada**
Dado que uma consulta a `/ready` resulta em `503`
Quando a resposta é produzida
Então a condição que a causou — banco inalcançável ou armazenamento ausente — fica registrada em log em nível de erro, permitindo diagnóstico posterior.
*(O registro precisa conviver com a cadência contínua de consulta, sem inundar o log: ver P16.)*

### Contrato de resposta

**P11 — O código de status é o contrato**
Dado qualquer consulta a `/health` ou `/ready`
Quando a resposta é produzida
Então o código de status é `200` (íntegro/pronto) ou `503` (não pronto), e nenhuma outra informação é necessária para o orquestrador decidir.

**P12 — Corpo mínimo, sem detalhe interno**
Dado qualquer consulta a `/health` ou `/ready`
Quando a resposta é produzida
Então o corpo não revela nome de host, endereço, credencial, versão de dependência, mensagem de erro do banco ou qualquer detalhe de topologia interna.
*(Premissa — confirme ou corrija: o corpo será um texto curto e estável, do tipo `ok` / `not ready`, suficiente para diagnóstico humano e inútil para reconhecimento. Alternativa é corpo vazio.)*

**P13 — Resposta conclusiva dentro de limite**
Dado que o banco de dados está inalcançável de forma que não recusa nem aceita conexão (pacotes descartados)
Quando o orquestrador consulta `/ready`
Então a resposta `503` é produzida em no máximo **3 segundos** *(premissa — confirme ou corrija: valor precisa ficar abaixo do tempo-limite que o orquestrador aplicará à consulta)*, e a consulta nunca fica pendente indefinidamente.

**P14 — Endpoints acessíveis sem autenticação**
Dado que o orquestrador não possui credenciais da aplicação
Quando ele consulta `/health` ou `/ready`
Então recebe resposta normalmente, sem qualquer etapa de autenticação ou autorização.

### Convivência com o tráfego real

**P15 — Verificação não altera dados**
Dado qualquer número de consultas a `/health` ou `/ready`
Quando elas são processadas
Então nenhum dado de negócio é criado, alterado ou removido, e nenhuma estrutura de armazenamento é criada ou modificada.

**P16 — Verificação não distorce a observabilidade do negócio**
Dado que os endpoints são consultados de forma contínua e repetitiva pelo orquestrador
Quando métricas e logs da aplicação são analisados
Então as consultas de saúde e prontidão não mascaram nem distorcem os indicadores de tráfego de negócio.
*(Premissa — confirme ou corrija: interpretação adotada é que essas consultas ficam fora das métricas de requisição e fora do log de requisições em nível informativo. Este ponto ficou em aberto no brainstorm.)*

**P17 — Instâncias avaliam a si mesmas**
Dado que várias instâncias da aplicação executam simultaneamente
Quando uma delas responde `/ready`
Então a resposta reflete exclusivamente a capacidade daquela instância, sem consultar ou depender do estado das demais.

---

## 4. Invariantes

1. **Uma instância que não consegue atender nunca se declara pronta.** Se uma requisição de leitura de evento falharia por indisponibilidade do banco ou por ausência do armazenamento, `/ready` não responde `200`.
2. **O sinal de vida nunca depende de dependência externa.** Nenhuma condição do banco de dados — indisponível, lento, sem schema — pode fazer `/health` falhar. Violar isso transforma uma falha isolada de dependência em reinício simultâneo de todas as instâncias.
3. **Falha de dependência nunca encerra o processo.** Em nenhum momento do ciclo de vida a indisponibilidade do banco pode derrubar a aplicação; ela deve permanecer viva e reportar não-prontidão.
4. **As verificações são somente leitura.** Nem `/health` nem `/ready` produzem efeito colateral sobre dados ou sobre a estrutura do armazenamento.
5. **Toda consulta termina.** Nenhuma consulta a `/health` ou `/ready` pode ficar pendente por tempo indefinido, em qualquer estado da dependência.
6. **As verificações jamais tornam a aplicação menos capaz de atender tráfego real.** O custo de responder aos sinais não pode ser causa de degradação do atendimento de negócio.
7. **O contrato é o código de status.** Nenhuma decisão do orquestrador depende de interpretar o corpo da resposta.
8. **Os dois sinais são independentes.** O estado de um nunca é derivado do outro.
9. **A prontidão não guarda estado.** A resposta de `/ready` reflete a condição corrente da dependência, nunca o histórico da instância. Duas instâncias iniciadas em momentos diferentes, sob a mesma condição de banco, respondem o mesmo.

---

## 5. Restrições

- **Sem autenticação.** Os endpoints precisam ser consultáveis por um agente sem credenciais.
- **Sem informação sensível.** Como consequência de não haver autenticação, o conteúdo exposto deve ser inútil para quem não é o operador legítimo.
- **Nomes estáveis.** `/health` e `/ready` passam a ser contrato entre a aplicação e a infraestrutura; alterá-los depois exige alteração coordenada da configuração de deploy. *(Premissa — confirme ou corrija: mantidos `/health` e `/ready`, e não as variantes `/healthz` e `/readyz`.)*
- **Sem colisão com o produto.** Os caminhos escolhidos não podem conflitar com rotas de página ou de API existentes nem restringir nomes de rota futuros de negócio.
- **Cadência de consulta.** O comportamento precisa se sustentar sob consulta contínua e repetitiva por instância. *(Premissa — confirme ou corrija: uma consulta a cada 10 segundos por endpoint, por instância.)*
- **Sem dependência de estado compartilhado.** Nenhuma instância pode precisar de coordenação com outras para responder aos sinais.
- **Sem alteração de comportamento do produto.** Nenhuma funcionalidade de eventos muda de comportamento observável em consequência desta feature. A inicialização deixar de ser fatal com o banco indisponível é consequência do ADR 001, não desta entrega; esta entrega apenas torna a condição observável pelo orquestrador.

---

## 6. Fora do escopo

| Item | Por quê |
|---|---|
| **Configuração das sondas nos manifestos de deploy** | Esta entrega cobre apenas o comportamento da aplicação. A imagem de container e o ambiente de execução já estão decididos nos ADRs 001 e 002; o que permanece fora é a configuração das sondas que consomem estes endpoints. Sem ela os endpoints não são consumidos por ninguém — fase seguinte, não omissão. |
| **Retirar a instância do balanceamento durante encerramento** (prontidão responder não-pronta ao receber sinal de término) | É o que entrega deploy sem erros para o usuário durante atualização, mas foi adiado: a maior parte do efeito pode ser obtida na configuração de deploy, sem tocar na aplicação. Fica registrado como lacuna conhecida — **enquanto não existir, atualizações da aplicação continuam podendo produzir erro para usuários em trânsito.** |
| **Preparar o armazenamento a partir da aplicação** (na inicialização, em segundo plano ou dentro da verificação) | A aplicação não prepara o armazenamento (ADR 001), e embutir preparo ou recuperação numa verificação de saúde criaria efeito colateral escondido, violando o invariante 4. Reexecutar a etapa de preparação é responsabilidade da orquestração. |
| **Gestão de versionamento de schema (migrations)** | A etapa de preparação cria estruturas ausentes e não altera as existentes (ADR 001). A evolução de um schema já existente permanece descoberta, com risco e escopo próprios. |
| **Sinal separado de "inicializando"** (startup) | A aplicação inicializa rapidamente e a distinção entre "iniciando" e "não pronto" não muda nenhuma decisão do orquestrador hoje. Reavaliar se o tempo de inicialização crescer. |
| **Verificação de outras dependências** | O banco de dados é a única dependência externa da aplicação hoje. |
| **Restringir os endpoints à rede interna** | Sem corpo informativo (P12), a exposição não carrega risco que justifique o custo. |
| **Painel, alerta ou relatório de saúde** | Consumo é automatizado pelo orquestrador; observabilidade humana já é atendida por métricas e logs existentes. |

---

## 7. Critérios de aceite

A feature está pronta quando **todos** os itens abaixo são verificáveis por observação direta:

**Comportamento**
1. Com o banco disponível e o armazenamento preparado: `/health` responde `200` e `/ready` responde `200`.
2. Com o banco parado: `/health` continua respondendo `200` e `/ready` responde `503`.
3. Iniciando a aplicação com o banco parado: o processo permanece em execução (não encerra), `/health` responde `200`, `/ready` responde `503`, e o log contém um registro de erro descrevendo a falha de acesso ao armazenamento.
4. Reativando o banco após o cenário 2 (armazenamento já havia sido preparado): `/ready` volta a `200` na consulta seguinte, sem reiniciar a aplicação.
5. Com o banco disponível e a etapa de preparação nunca executada: `/ready` responde `503`; após executar a etapa de preparação com sucesso, `/ready` responde `200` na consulta seguinte, **sem reiniciar a aplicação**.
6. Com o banco disponível mas com o armazenamento de eventos ausente: `/ready` responde `503`.
7. Com o banco inalcançável por descarte de pacotes: `/ready` responde `503` em até 3 segundos, medido de ponta a ponta.

**Contrato**
8. Nenhuma resposta dos dois endpoints contém detalhe de infraestrutura, mensagem de erro do banco ou dado de configuração.
9. Ambos respondem sem autenticação.
10. Após qualquer volume de consultas aos dois endpoints, a contagem de eventos cadastrados e a estrutura do armazenamento permanecem inalteradas.

**Observabilidade**
11. Após um período de consultas repetidas aos endpoints, as métricas e os logs de requisição de negócio permanecem interpretáveis, sem serem dominados pelas consultas de verificação. *(sujeito à confirmação da premissa em P16)*

**Verificação automatizada**
12. Existe suíte de testes automatizados cobrindo, no mínimo: `/health` com dependência disponível e indisponível; `/ready` nos três estados (pronto, dependência fora, armazenamento ausente); e a inicialização não-fatal com dependência indisponível.
13. A suíte roda junto com os testes existentes do projeto, em um único comando, sem depender de banco de dados real em execução.

---

## Premissas a confirmar

| # | Premissa | Onde aparece |
|---|---|---|
| 1 | Corpo da resposta é texto curto e estável (`ok` / `not ready`), não vazio | P12 |
| 2 | Limite de 3 segundos para resposta conclusiva do sinal de prontidão | P13, aceite 7 |
| 3 | Consultas de verificação ficam fora das métricas e do log de requisições | P16, aceite 11 |
| 4 | Nomes `/health` e `/ready` (não `/healthz` e `/readyz`) | Restrições |
| 5 | Cadência de uma consulta a cada 10 segundos por endpoint, por instância | Restrições |
