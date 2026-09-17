## Purpose

Define o ambiente local completo obtido por um único comando, destinado a desenvolvimento e a teste manual: sua ordem de subida, as superfícies que expõe para exercício à mão, e sua independência de arquivos de configuração locais.

## ADDED Requirements

### Requirement: Ambiente completo por um comando

O repositório SHALL conter a definição de um ambiente local que, a partir de um clone recém-obtido e com um único comando, deixe a aplicação e sua dependência de banco em execução, sem provisionamento manual de nenhuma das partes.

#### Scenario: Clone recém-obtido

- **WHEN** alguém clona o repositório e aciona o comando de subida do ambiente
- **THEN** o banco de dados, a preparação de schema e a aplicação executam, e a aplicação passa a atender requisições

#### Scenario: Procedimento de execução no repositório

- **WHEN** alguém precisa saber como executar a aplicação
- **THEN** a resposta está no repositório, e não depende de conhecimento operacional mantido fora dele

### Requirement: Subida condicionada à conclusão real de cada etapa

Cada etapa do ambiente SHALL iniciar apenas quando a etapa anterior estiver comprovadamente concluída, e não apenas quando existir.

#### Scenario: Aplicação aguarda a preparação de schema

- **WHEN** o ambiente é acionado
- **THEN** a aplicação só inicia depois que a preparação de schema termina com resultado de sucesso

#### Scenario: Preparação aguarda o banco aceitar conexões

- **WHEN** o ambiente é acionado e o banco ainda está inicializando
- **THEN** a preparação de schema só é acionada depois que o banco passa a aceitar conexões, e não apenas depois que seu container existe

#### Scenario: Falha na preparação de schema

- **WHEN** a preparação de schema termina com resultado de falha
- **THEN** a aplicação não é iniciada

### Requirement: Independência de arquivo de configuração local

A definição do ambiente SHALL NOT depender de um arquivo de variáveis de ambiente local, nem ter seu comportamento alterado pela presença ou ausência de um.

#### Scenario: Sem arquivo de ambiente local

- **WHEN** o ambiente é acionado sem que exista um arquivo de variáveis de ambiente local
- **THEN** ele sobe integralmente, com valores de desenvolvimento próprios

#### Scenario: Com arquivo de ambiente local presente

- **WHEN** o ambiente é acionado com um arquivo de variáveis de ambiente local presente no repositório
- **THEN** o ambiente se comporta de forma idêntica ao cenário anterior, e nenhum valor desse arquivo é consumido

### Requirement: Superfícies expostas para exercício manual

O ambiente SHALL expor a aplicação e o banco de dados na máquina local, de modo que ambos possam ser exercitados à mão durante o desenvolvimento.

#### Scenario: Exercício da API pelo arquivo de requisições existente

- **WHEN** as requisições mantidas em `api-requests.http` são disparadas contra o ambiente em execução
- **THEN** elas alcançam a aplicação sem que o arquivo precise ser editado

#### Scenario: Inspeção do banco por cliente externo

- **WHEN** um cliente de banco de dados na máquina local se conecta ao ambiente
- **THEN** a conexão é aceita e o conteúdo do armazenamento pode ser inspecionado

### Requirement: Propagação de alterações por reconstrução

O código-fonte SHALL NOT ser montado a partir da máquina local para dentro do container. A reconstrução da imagem SHALL ser o mecanismo de propagação de alterações de código.

#### Scenario: Alteração de código sem reconstrução

- **WHEN** um arquivo de `src/` é alterado e o ambiente em execução não é reconstruído
- **THEN** a aplicação em execução continua servindo o código anterior

#### Scenario: Alteração de código com reconstrução

- **WHEN** o ambiente é acionado novamente com reconstrução após uma alteração em `src/`
- **THEN** a aplicação passa a servir o código alterado

### Requirement: Ambiente destinado a desenvolvimento e teste

O ambiente definido SHALL servir apenas a desenvolvimento e teste manual, e SHALL NOT ser apresentado como caminho de execução em produção.

#### Scenario: Valores de configuração do ambiente local

- **WHEN** os valores de configuração usados pelo ambiente local são examinados
- **THEN** eles são reconhecíveis como valores de desenvolvimento, e sua presença no controle de versão não expõe nenhum segredo de produção
