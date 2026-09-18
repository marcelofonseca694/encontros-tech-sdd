## Purpose

Define o ambiente de execução da aplicação como artefato declarado no repositório: o que sua aplicação faz existir em um cluster, quais garantias de topologia e de disponibilidade ele sustenta, como o ciclo de vida das réplicas é sinalizado ao orquestrador, como os segredos entram no ambiente sem estar na imagem, e qual superfície passa a ser alcançável de fora.

## ADDED Requirements

### Requirement: Ambiente de execução declarado e aplicável por um comando

O ambiente de execução SHALL existir como declaração versionada no repositório, em um único arquivo, aplicável a um cluster por um único comando. Nenhum recurso do ambiente SHALL depender de criação manual no cluster para que o ambiente funcione.

#### Scenario: Aplicação a partir de um clone recém-obtido

- **WHEN** a declaração é aplicada a um cluster vazio, a partir de um clone recém-obtido do repositório
- **THEN** o banco, a preparação de armazenamento, as réplicas da aplicação e sua exposição externa passam a existir, sem nenhum recurso criado à mão

#### Scenario: Reaplicação da mesma declaração

- **WHEN** a mesma declaração é aplicada novamente ao mesmo cluster, sem alteração de versão
- **THEN** a aplicação continua atendendo tráfego, e nenhuma etapa falha por já existir

### Requirement: Réplicas distribuídas por zona de disponibilidade

A aplicação SHALL executar em três réplicas, distribuídas no máximo uma por zona de disponibilidade. Quando a distribuição não puder ser satisfeita, as réplicas excedentes SHALL permanecer não agendadas, e SHALL NOT ser concentradas em uma mesma zona.

#### Scenario: Cluster com três zonas

- **WHEN** a declaração é aplicada a um cluster cujos nós estão distribuídos em três zonas de disponibilidade
- **THEN** cada zona passa a executar exatamente uma réplica da aplicação

#### Scenario: Cluster sem informação de zona

- **WHEN** a declaração é aplicada a um cluster cujos nós não declaram a zona a que pertencem
- **THEN** as réplicas permanecem não agendadas, e a violação do espalhamento fica visível como pendência em vez de acontecer silenciosamente

#### Scenario: Perda de uma zona

- **WHEN** uma zona de disponibilidade se torna indisponível
- **THEN** as réplicas das demais zonas continuam atendendo tráfego, sem depender da zona perdida

### Requirement: Disponibilidade mínima durante manutenção voluntária

Durante qualquer operação voluntária de manutenção sobre os nós, ao menos duas réplicas da aplicação SHALL permanecer disponíveis.

#### Scenario: Drenagem de um nó

- **WHEN** um nó que executa uma réplica é drenado deliberadamente
- **THEN** a réplica só é retirada se ao menos duas outras permanecerem disponíveis, e a operação aguarda enquanto essa condição não for atendida

### Requirement: Tráfego nunca alcança réplica incapaz de atender

Uma réplica SHALL receber tráfego somente quando for capaz de atender requisições de negócio. Enquanto o armazenamento de eventos não estiver preparado, ou enquanto o banco estiver inalcançável, nenhuma réplica SHALL receber tráfego — independentemente da ordem em que os recursos do ambiente passaram a existir.

#### Scenario: Aplicação do ambiente antes de o armazenamento estar preparado

- **WHEN** a declaração é aplicada e as réplicas iniciam antes de a preparação do armazenamento concluir
- **THEN** nenhuma réplica recebe tráfego enquanto a preparação não tiver concluído com sucesso

#### Scenario: Armazenamento preparado com as réplicas já em execução

- **WHEN** a preparação do armazenamento conclui com sucesso e as réplicas já estão em execução
- **THEN** as réplicas passam a receber tráfego sem que nenhuma precise ser reiniciada

#### Scenario: Banco torna-se indisponível

- **WHEN** o banco se torna indisponível com as réplicas em execução
- **THEN** todas as réplicas deixam de receber tráfego, e voltam a recebê-lo quando o banco retorna, sem reinício

### Requirement: Decisão de reiniciar é independente do banco

A decisão do orquestrador de reiniciar uma réplica SHALL depender apenas da capacidade do processo de atender conexões, e SHALL NOT depender da disponibilidade do banco de dados nem do estado do armazenamento.

#### Scenario: Banco indisponível de forma prolongada

- **WHEN** o banco permanece indisponível por tempo prolongado
- **THEN** nenhuma réplica é reiniciada em consequência disso, e todas permanecem em execução reportando incapacidade de atender

#### Scenario: Processo deixa de aceitar conexões

- **WHEN** o processo de uma réplica deixa de aceitar conexões na porta em que serve a aplicação
- **THEN** aquela réplica é reiniciada pelo orquestrador

### Requirement: Segredos entram pelo ambiente, nunca pelo artefato versionado

A credencial de banco de dados e o segredo de aplicação SHALL chegar às réplicas como configuração fornecida pelo ambiente. O artefato versionado no repositório SHALL NOT conter seus valores reais, e a imagem SHALL NOT contê-los em nenhuma camada.

#### Scenario: Inspeção do artefato versionado

- **WHEN** o artefato versionado no repositório é inspecionado por qualquer pessoa
- **THEN** nenhum valor real de credencial de banco ou de segredo de aplicação é obtido a partir dele

#### Scenario: Réplica em execução

- **WHEN** uma réplica inicia
- **THEN** ela recebe o endereço do banco, a credencial e o segredo de aplicação do ambiente, e inicia sem valor padrão embutido

### Requirement: Banco executa no cluster sem durabilidade, com endereço estável

O banco de dados SHALL executar como carga dentro do próprio cluster, com armazenamento efêmero, exposto às réplicas por um endereço de conexão único e estável. A substituição do pod do banco SHALL resultar em banco sem as estruturas de armazenamento, e essa condição SHALL ser tornada observável pelo ambiente em vez de produzir erro servido ao usuário.

#### Scenario: Substituição do pod do banco

- **WHEN** o pod do banco é reiniciado, reagendado ou substituído
- **THEN** o banco volta sem as estruturas de armazenamento de eventos e sem nenhum dado anterior, e nenhuma réplica da aplicação recebe tráfego até que a preparação seja reexecutada com sucesso

#### Scenario: Endereço de conexão após a substituição

- **WHEN** o pod do banco é substituído e passa a ter outro endereço de rede
- **THEN** o endereço de conexão que as réplicas usam permanece o mesmo, e nenhuma réplica precisa de reconfiguração ou reinício para voltar a usá-lo

### Requirement: Superfície exposta externamente

O ambiente SHALL expor a aplicação externamente por endereço próprio, atribuído pelo cluster, em uma única porta. Tudo o que a aplicação serve naquela porta SHALL ser considerado superfície pública, incluindo o que existe para fins de observabilidade.

#### Scenario: Acesso externo à aplicação

- **WHEN** um cliente externo ao cluster acessa o endereço atribuído ao ambiente
- **THEN** as páginas e a API da aplicação respondem, com o tráfego distribuído entre as réplicas capazes de atender

#### Scenario: Superfície de observabilidade na mesma porta

- **WHEN** a aplicação serve endpoints de observabilidade na mesma porta exposta
- **THEN** esses endpoints são alcançáveis externamente sem autenticação, condição que o ambiente declara explicitamente em vez de pressupor privacidade

### Requirement: Réplicas executam sem privilégio e com consumo declarado

As réplicas SHALL executar como usuário não administrativo, sem capacidade de escalar privilégio e sem escrita no sistema de arquivos da imagem. Cada réplica SHALL declarar o consumo de recursos que requisita e o teto que não pode exceder.

#### Scenario: Identidade de execução

- **WHEN** uma réplica está em execução
- **THEN** o processo da aplicação não executa como usuário administrativo, e não consegue obter privilégio adicional

#### Scenario: Escrita durante a inicialização

- **WHEN** a aplicação precisa escrever em disco durante sua inicialização
- **THEN** a escrita ocorre em área temporária dedicada e descartável, e o sistema de arquivos da imagem permanece somente leitura

#### Scenario: Consumo declarado

- **WHEN** o orquestrador decide onde colocar uma réplica
- **THEN** ele dispõe do consumo requisitado por ela, e a réplica não pode exceder o teto declarado

### Requirement: Versão em execução é identificável e fixa

O ambiente SHALL referenciar a aplicação por identificação de versão fixa, e SHALL NOT referenciar identificação móvel, de modo que o que está em execução seja determinável a partir da declaração.

#### Scenario: Determinação da versão em execução

- **WHEN** a declaração é inspecionada
- **THEN** a versão exata da aplicação que ela põe em execução é determinável, sem depender de qual artefato foi publicado por último

#### Scenario: Publicação de nova versão

- **WHEN** uma nova versão da aplicação é publicada
- **THEN** as réplicas em execução permanecem na versão declarada até que a declaração seja alterada e reaplicada
