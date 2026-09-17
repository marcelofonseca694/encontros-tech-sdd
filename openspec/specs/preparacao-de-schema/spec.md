# preparacao-de-schema Specification

## Purpose

Define a preparação do armazenamento de eventos como operação acionável, separada e anterior à aplicação, com um contrato de resultado que um agente automatizado possa consumir sem interpretar texto.

## Requirements

### Requirement: Preparação é operação separada e acionável

A preparação do schema do banco SHALL ser uma operação acionada deliberadamente, executada a partir da mesma imagem da aplicação, e independente do processo da aplicação.

#### Scenario: Acionamento a partir da mesma imagem

- **WHEN** a preparação de schema é acionada
- **THEN** ela executa a partir da mesma imagem que serve a aplicação, sem exigir um segundo artefato

#### Scenario: Preparação sem aplicação em execução

- **WHEN** a preparação de schema é acionada sem que nenhuma instância da aplicação esteja em execução
- **THEN** ela executa integralmente e reporta seu resultado

### Requirement: A aplicação nunca prepara o schema

O processo da aplicação SHALL NOT criar, alterar ou remover estruturas do banco de dados, em nenhum momento do seu ciclo de vida.

#### Scenario: Aplicação iniciada contra banco sem estruturas

- **WHEN** a aplicação é iniciada contra um banco disponível e sem as estruturas de armazenamento de eventos
- **THEN** nenhuma estrutura passa a existir em consequência da inicialização

#### Scenario: Múltiplas instâncias iniciando simultaneamente

- **WHEN** várias instâncias da aplicação são iniciadas ao mesmo tempo contra o mesmo banco
- **THEN** nenhuma delas tenta criar estruturas, e portanto nenhuma concorre com outra pela mesma criação

### Requirement: Cria estruturas ausentes sem alterar as existentes

A preparação SHALL criar as estruturas de armazenamento ausentes e SHALL NOT alterar ou remover estruturas já existentes.

#### Scenario: Banco sem nenhuma estrutura

- **WHEN** a preparação é acionada contra um banco disponível e sem as estruturas de armazenamento de eventos
- **THEN** as estruturas passam a existir e a operação é reportada como bem-sucedida

#### Scenario: Banco já preparado

- **WHEN** a preparação é acionada contra um banco cujas estruturas já existem
- **THEN** nenhuma estrutura é alterada ou removida, nenhum dado existente é afetado, e a operação é reportada como bem-sucedida

### Requirement: Resultado sinalizado por código de saída

A preparação SHALL sinalizar seu resultado por código de saída, de modo que um agente automatizado distinga sucesso de falha sem interpretar mensagens.

#### Scenario: Preparação bem-sucedida

- **WHEN** a preparação conclui sem erro
- **THEN** o código de saída indica sucesso

#### Scenario: Banco indisponível

- **WHEN** a preparação é acionada e o banco está indisponível ou inalcançável
- **THEN** nenhuma estrutura é criada, o código de saída indica falha, e a causa fica registrada em log de forma que permita diagnóstico

#### Scenario: Consumo do resultado por um orquestrador

- **WHEN** um agente automatizado condiciona a subida da aplicação ao resultado da preparação
- **THEN** ele decide continuar ou abortar apenas pelo código de saída, sem analisar a saída textual
