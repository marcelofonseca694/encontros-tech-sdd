# sondas-de-saude Specification

## Purpose

Expõe dois sinais HTTP distintos e independentes para o orquestrador — "este processo está vivo" (`/health`) e "esta instância consegue atender tráfego de negócio agora" (`/ready`) — de modo que ele reinicie apenas o que está quebrado e roteie tráfego apenas para o que funciona. Origem: `docs/prds/prd-health-ready.md`.

## Requirements

### Requirement: Sinal de vida nunca depende de dependência externa
`GET /health` SHALL responder `200` sempre que o processo estiver em execução e aceitando requisições HTTP, independentemente do estado do banco de dados ou do armazenamento de eventos. Nenhuma verificação de dependência externa SHALL ocorrer dentro de `/health`.

Predicados do PRD: P1, P2, P3.

#### Scenario: Vivo responde vivo
- **WHEN** o processo da aplicação está em execução e respondendo a requisições HTTP
- **THEN** `GET /health` responde `200`

#### Scenario: Banco totalmente indisponível não afeta o sinal de vida
- **WHEN** o banco de dados está totalmente indisponível
- **THEN** `GET /health` responde `200`, indistinguível da resposta com o banco disponível

#### Scenario: Armazenamento não preparado não afeta o sinal de vida
- **WHEN** o armazenamento de eventos não está preparado
- **THEN** `GET /health` responde `200`

### Requirement: Sinal de prontidão reflete a capacidade real de atender tráfego de negócio
`GET /ready` SHALL responder `200` somente quando o banco de dados está alcançável e o armazenamento de eventos existe e é legível pela aplicação. SHALL responder `503` quando qualquer uma dessas duas condições não for satisfeita.

Predicados do PRD: P4, P5, P6.

#### Scenario: Pronto quando consegue atender
- **WHEN** o banco de dados está disponível e o armazenamento de eventos está preparado e legível
- **THEN** `GET /ready` responde `200`

#### Scenario: Não pronto quando a dependência está fora
- **WHEN** o banco de dados está indisponível
- **THEN** `GET /ready` responde `503`

#### Scenario: Não pronto quando o armazenamento não é legível
- **WHEN** o banco de dados está disponível, porém o armazenamento de eventos não existe ou não é legível pela aplicação
- **THEN** `GET /ready` responde `503`

### Requirement: Prontidão não guarda estado da instância
A resposta de `/ready` SHALL refletir exclusivamente a condição corrente da dependência e do armazenamento, nunca o histórico da instância. A aplicação SHALL NOT reter memória de uma tentativa anterior de verificação.

Predicados do PRD: P7, P8, invariante 9.

#### Scenario: Prontidão acompanha a recuperação do banco, sem reinício
- **WHEN** o armazenamento de eventos está preparado, o banco tornou-se indisponível e depois volta a ficar disponível
- **THEN** a próxima consulta a `/ready` responde `200`, sem que a instância seja reiniciada

#### Scenario: Prontidão acompanha a preparação do armazenamento, sem reinício
- **WHEN** a etapa de preparação de schema não foi executada com sucesso e, com a aplicação já em execução, passa a ser executada com sucesso
- **THEN** a próxima consulta a `/ready` responde `200`, sem que a instância seja reiniciada

### Requirement: Inicialização não é bloqueada pela indisponibilidade da dependência
Ao iniciar com o banco de dados indisponível, o processo SHALL permanecer em execução, `GET /health` SHALL responder `200` e `GET /ready` SHALL responder `503`.

Predicados do PRD: P9.

#### Scenario: Início com o banco parado
- **WHEN** o processo da aplicação é iniciado e o banco de dados está indisponível
- **THEN** o processo permanece em execução, `GET /health` responde `200` e `GET /ready` responde `503`

### Requirement: Verificação de prontidão é limitada no tempo, com limite configurável
A fase de conexão ao banco de dados feita por `/ready` SHALL ser limitada a um teto máximo, de modo que a resposta seja sempre conclusiva dentro desse limite mesmo quando a conexão não é recusada nem aceita. O teto SHALL ter um valor padrão e SHALL ser configurável por variável de ambiente, sem alteração de código.

Predicados do PRD: P13.

#### Scenario: Banco inalcançável por descarte de pacotes
- **WHEN** o banco de dados está inalcançável de forma que não recusa nem aceita conexão
- **THEN** `GET /ready` responde `503` dentro do teto de tempo configurado, e a consulta nunca fica pendente além dele

#### Scenario: Teto de tempo alterado por configuração
- **WHEN** o valor do teto é alterado pela variável de ambiente correspondente, sem alteração de código, e a aplicação é reiniciada com o novo valor
- **THEN** o comportamento do cenário anterior passa a respeitar o novo teto, não mais o padrão

### Requirement: Causa da não-prontidão é registrada para diagnóstico
Toda vez que `/ready` responde `503`, a condição que causou a resposta — banco inalcançável ou armazenamento ausente/não legível — SHALL ficar registrada em log, em nível que permita diagnóstico sem ser tratada como falha crítica da aplicação.

Predicados do PRD: P10.

#### Scenario: Causa registrada a cada 503
- **WHEN** uma consulta a `/ready` resulta em `503`
- **THEN** a condição que a causou fica registrada em log, em nível de warning

### Requirement: O contrato de resposta é o código de status, sem corpo revelador
Toda resposta de `/health` e `/ready` SHALL comunicar seu resultado exclusivamente pelo código de status HTTP (`200` ou `503`). O corpo SHALL ser curto, estável e SHALL NOT conter nome de host, endereço, credencial, versão de dependência, mensagem de erro do banco ou qualquer detalhe de topologia interna.

Predicados do PRD: P11, P12.

#### Scenario: Decisão do orquestrador não depende do corpo
- **WHEN** qualquer consulta a `/health` ou `/ready` é respondida
- **THEN** o código de status por si só é suficiente para o orquestrador decidir, sem interpretar o corpo

#### Scenario: Corpo não revela detalhe interno
- **WHEN** qualquer consulta a `/health` ou `/ready` é respondida
- **THEN** o corpo não contém nome de host, endereço, credencial, versão de dependência, mensagem de erro do banco ou detalhe de topologia interna

### Requirement: Endpoints acessíveis sem autenticação
`/health` e `/ready` SHALL responder sem exigir autenticação ou autorização.

Predicados do PRD: P14.

#### Scenario: Consulta sem credenciais
- **WHEN** um agente sem credenciais da aplicação consulta `/health` ou `/ready`
- **THEN** ele recebe resposta normalmente, sem qualquer etapa de autenticação

### Requirement: Verificações são somente leitura
Nenhuma consulta a `/health` ou `/ready`, em qualquer volume, SHALL criar, alterar ou remover dado de negócio nem estrutura de armazenamento.

Predicados do PRD: P15, invariante 4.

#### Scenario: Nenhum efeito colateral sobre dados ou estruturas
- **WHEN** qualquer número de consultas a `/health` ou `/ready` é processado
- **THEN** nenhum dado de negócio é criado, alterado ou removido, e nenhuma estrutura de armazenamento é criada ou modificada

### Requirement: Consultas de verificação não distorcem a observabilidade de negócio
As consultas a `/health` e `/ready` SHALL ficar fora das métricas de requisição e fora do log de requisições de negócio, mesmo sob consulta contínua e repetitiva.

Predicados do PRD: P16.

#### Scenario: Consulta contínua não aparece nas métricas nem no log de negócio
- **WHEN** `/health` e `/ready` são consultados de forma contínua e repetitiva
- **THEN** essas consultas não são contabilizadas nas métricas de requisição nem registradas no log de requisições de negócio

### Requirement: Cada instância avalia exclusivamente a si mesma
A resposta de `/ready` de uma instância SHALL refletir exclusivamente a capacidade daquela instância, sem consultar ou depender do estado de outras instâncias em execução simultânea.

Predicados do PRD: P17, invariante 8.

#### Scenario: Múltiplas instâncias sob a mesma condição de banco
- **WHEN** várias instâncias da aplicação executam simultaneamente sob a mesma condição de banco de dados
- **THEN** cada uma responde `/ready` com base apenas na própria verificação, e todas respondem de forma consistente entre si sem se consultarem
