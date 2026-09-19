# semeadura-de-eventos Specification

## Purpose

Operação acionável que leva um catálogo de eventos vazio a um catálogo de demonstração utilizável, criando dez eventos derivados de `api-requests.http` de forma idempotente e atômica, sem afetar dado preexistente nem a observabilidade de negócio da aplicação. Origem: `docs/prds/prd-seed.md`.

## Requirements

### Requirement: Acionamento é sempre explícito e nunca parte da inicialização da aplicação
A semeadura SHALL ser executada apenas por acionamento explícito e deliberado, nunca como consequência de iniciar a aplicação, por qualquer meio e com qualquer número de processos simultâneos da aplicação.

Predicados do PRD: P1, invariante 3.

#### Scenario: Iniciar a aplicação nunca semeia
- **WHEN** a aplicação é iniciada sobre um armazenamento de eventos vazio, por qualquer meio e com qualquer número de processos simultâneos
- **THEN** nenhum evento passa a existir em consequência da inicialização

### Requirement: Semeadura em catálogo vazio cria o conjunto completo
Quando acionada contra um armazenamento preparado e vazio, a semeadura SHALL criar o conjunto completo de dez eventos de demonstração e reportar sucesso.

Predicados do PRD: P2.

#### Scenario: Catálogo vazio
- **WHEN** o armazenamento de eventos está preparado e não contém nenhum evento, e a semeadura é acionada
- **THEN** os dez eventos de demonstração passam a existir e a operação é reportada como bem-sucedida

### Requirement: Armazenamento não preparado ou inacessível é falha
Quando o armazenamento de eventos não está preparado ou está inacessível, a semeadura SHALL NOT criar nenhum evento e SHALL reportar falha, com a causa registrada de forma que permita diagnóstico.

Predicados do PRD: P3.

#### Scenario: Armazenamento não preparado ou inalcançável
- **WHEN** a semeadura é acionada e o armazenamento de eventos não está preparado, ou está inacessível
- **THEN** nenhum evento passa a existir, a operação é reportada como falha, e a causa fica registrada de forma que permita diagnóstico

### Requirement: Catálogo com qualquer conteúdo é inviolável
Quando o armazenamento contém pelo menos um evento, de qualquer origem, a semeadura SHALL NOT criar, alterar ou remover nenhum evento, e SHALL reportar sucesso. Esta é a única condição avaliada pela semeadura antes de agir.

Predicados do PRD: P4, P6, invariante 1, invariante 7.

#### Scenario: Catálogo com conteúdo de qualquer origem
- **WHEN** o armazenamento contém pelo menos um evento, de qualquer origem, e a semeadura é acionada
- **THEN** nenhum evento é criado, alterado ou removido, e a operação é reportada como bem-sucedida

#### Scenario: Evento cadastrado por pessoa bloqueia a semeadura
- **WHEN** o armazenamento estava vazio, uma pessoa cadastra um evento pela aplicação, e a semeadura é acionada em seguida
- **THEN** nada é criado, e o catálogo permanece com apenas aquele evento

### Requirement: Repetição da semeadura é inofensiva
Repetir o acionamento da semeadura, qualquer número de vezes, SHALL manter a quantidade e o conteúdo dos eventos idênticos ao resultado da primeira execução bem-sucedida.

Predicados do PRD: P5.

#### Scenario: Acionamentos sucessivos
- **WHEN** a semeadura já foi executada com sucesso e é acionada novamente, qualquer número de vezes
- **THEN** a quantidade e o conteúdo dos eventos permanecem idênticos ao resultado da primeira execução

### Requirement: Criação é atômica — tudo ou nada
Se a semeadura encontrar uma falha antes de concluir, o armazenamento SHALL ficar exatamente como estava antes do acionamento, sem nenhum evento parcialmente criado, e a operação SHALL reportar falha. Uma falha corrigida SHALL permitir que uma nova execução complete integralmente, como se fosse a primeira.

Predicados do PRD: P7, P8, invariante 2.

#### Scenario: Falha no meio da execução
- **WHEN** a semeadura está em curso e encontra uma falha antes de concluir
- **THEN** o armazenamento fica exatamente como estava antes do acionamento, sem nenhum evento parcialmente semeado, e a operação é reportada como falha

#### Scenario: Nova tentativa após falha corrigida
- **WHEN** uma semeadura anterior falhou, a causa é corrigida, e a semeadura é acionada novamente
- **THEN** ela executa integralmente, criando o conjunto completo, como se fosse a primeira execução

### Requirement: Eventos semeados têm datas futuras que preservam a distribuição do conjunto de referência
Todos os eventos semeados SHALL ter data posterior ao instante do acionamento. As datas SHALL manter, entre si, a mesma ordem cronológica e o mesmo espaçamento relativo das datas de referência em `api-requests.http` (ordenadas cronologicamente, não pela ordem dos blocos no arquivo), deslocadas por uma constante de forma que o primeiro evento caia 3 dias após o acionamento.

Predicados do PRD: P9, P10.

#### Scenario: Todas as datas são futuras
- **WHEN** a semeadura é acionada em qualquer data
- **THEN** todos os eventos criados têm data posterior ao instante do acionamento

#### Scenario: Ordem e espaçamento preservados
- **WHEN** as datas dos eventos semeados são comparadas entre si
- **THEN** mantêm a mesma ordem cronológica e o mesmo espaçamento relativo das datas de referência em `api-requests.http`, com o primeiro evento 3 dias após o acionamento e o último aproximadamente dois meses depois

### Requirement: Conteúdo semeado deriva do conjunto de referência, sem tecnologias
Título, descrição e local de cada evento semeado SHALL corresponder ao evento equivalente em `api-requests.http`. Nenhuma informação de tecnologias SHALL ser registrada ou prometida pela semeadura, e sua ausência SHALL NOT ser reportada como erro.

Predicados do PRD: P11, P12.

#### Scenario: Conteúdo corresponde ao conjunto de referência
- **WHEN** os eventos semeados são comparados com os dez eventos de `api-requests.http`
- **THEN** título, descrição e local de cada um correspondem, e apenas as datas foram reajustadas

#### Scenario: Ausência de tecnologias não é erro
- **WHEN** os eventos são semeados
- **THEN** nenhuma informação de tecnologia é registrada, e a operação não reporta essa ausência como erro

### Requirement: Evento semeado é indistinguível de evento real
Um evento semeado SHALL se comportar, por qualquer caminho de consulta da aplicação — listagem, busca, detalhe, edição por token — exatamente como um evento cadastrado por uma pessoa. Nenhum campo, marcação ou caminho SHALL permitir identificá-lo como semeado.

Predicados do PRD: P13, invariante 5.

#### Scenario: Acesso por qualquer caminho da aplicação
- **WHEN** um evento semeado é consultado por listagem, busca, detalhe ou edição por token
- **THEN** ele se comporta exatamente como um evento cadastrado por uma pessoa, sem nenhum campo ou marcação que o identifique como semeado

### Requirement: Token de edição próprio e imprevisível
Cada evento semeado SHALL possuir um token de edição único, não derivável de seu conteúdo, e SHALL NOT ser reproduzível entre duas execuções da semeadura.

Predicados do PRD: P14, invariante 6.

#### Scenario: Tokens distintos entre execuções
- **WHEN** duas semeaduras são executadas em armazenamentos limpos e seus tokens são comparados
- **THEN** todos os tokens são distintos entre si e não derivam do conteúdo dos eventos

### Requirement: Resultado é inteligível para pessoas e distinguível por agente automatizado sem interpretar texto
Ao final de qualquer acionamento, SHALL ficar registrado qual dos três desfechos ocorreu — semeou e quantos eventos criou, não semeou porque o catálogo já tinha conteúdo, ou falhou e por quê — de forma legível por uma pessoa sem consultar código. O desfecho SHALL também ser sinalizado de modo que um agente automatizado distinga sucesso de falha sem interpretar mensagens, sendo "semeou" e "não semeou porque já havia conteúdo" ambos sucesso, e apenas falha efetiva reportada como falha.

Predicados do PRD: P15, P16.

#### Scenario: Pessoa entende o desfecho pela saída
- **WHEN** qualquer acionamento da semeadura termina
- **THEN** uma pessoa consegue entender, pela saída, qual dos três desfechos ocorreu, sem consultar código

#### Scenario: Agente automatizado distingue sucesso de falha sem interpretar texto
- **WHEN** um agente automatizado aciona a semeadura
- **THEN** ele distingue sucesso (semeou, ou não semeou por já haver conteúdo) de falha, sem analisar a saída textual

### Requirement: Semeadura não distorce a observabilidade de negócio nem interrompe o atendimento
As criações de eventos feitas pela semeadura SHALL NOT aparecer nos indicadores e registros de negócio da aplicação como criações de evento. Acionar a semeadura, em qualquer desfecho, SHALL NOT interromper o atendimento da aplicação em execução nem produzir erro nela.

Predicados do PRD: P17, P19.

#### Scenario: Criações de demonstração fora dos indicadores de negócio
- **WHEN** a semeadura cria eventos
- **THEN** os indicadores e registros de negócio da aplicação não contabilizam essas criações como criação de evento

#### Scenario: Atendimento não é afetado
- **WHEN** a semeadura é acionada com a aplicação em execução atendendo requisições
- **THEN** o atendimento não é interrompido nem passa a produzir erro

### Requirement: Nenhuma funcionalidade existente muda de comportamento
A existência da semeadura SHALL NOT alterar o comportamento observável de nenhuma funcionalidade de eventos. A aplicação SHALL funcionar igualmente sobre um catálogo semeado ou vazio.

Predicados do PRD: P18, invariante 4.

#### Scenario: Comportamento observável inalterado
- **WHEN** qualquer funcionalidade de eventos é exercitada, com a semeadura existindo no sistema
- **THEN** seu comportamento observável é idêntico ao anterior à existência da semeadura
