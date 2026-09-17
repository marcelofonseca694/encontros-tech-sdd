# empacotamento-em-container Specification

## Purpose

Define a aplicação como artefato de imagem única: o que a imagem contém, o que é proibido conter, e como a identificação do artefato se relaciona com a versão que a aplicação reporta em execução.

## Requirements

### Requirement: Artefato único para todos os ambientes

O sistema SHALL ser empacotado como uma única imagem de container, usada sem distinção em desenvolvimento e em produção. A diferença entre ambientes SHALL existir exclusivamente como configuração externa à imagem, nunca como imagem distinta.

#### Scenario: Mesma imagem em ambientes diferentes

- **WHEN** a mesma imagem é executada em desenvolvimento e em produção
- **THEN** o artefato é bit a bit idêntico nos dois ambientes, e apenas os valores de configuração fornecidos pelo ambiente diferem

#### Scenario: Servidor de aplicação idêntico entre ambientes

- **WHEN** a aplicação é executada em qualquer ambiente
- **THEN** ela é servida pelo mesmo servidor de aplicação de produção, e não por um servidor de desenvolvimento

### Requirement: Versão de interpretador declarada pela imagem

A imagem SHALL fixar a versão do interpretador da linguagem, de modo que ela não dependa da máquina onde o build ocorre. A versão escolhida SHALL ser aquela para a qual todas as dependências fixadas do projeto publicam artefatos pré-compilados.

#### Scenario: Build em máquinas diferentes

- **WHEN** a imagem é construída em duas máquinas com interpretadores locais distintos
- **THEN** ambas as imagens resultantes contêm a mesma versão de interpretador

#### Scenario: Build sem etapa de compilação

- **WHEN** as dependências são instaladas durante o build
- **THEN** nenhuma dependência é compilada a partir do código-fonte, e a imagem não contém ferramentas de compilação

### Requirement: Segredos nunca residem na imagem

A imagem SHALL NOT conter o segredo de aplicação nem credenciais de banco de dados, em nenhuma camada, dado que ela é publicada em registro público e todo o seu conteúdo é extraível por qualquer pessoa.

#### Scenario: Inspeção da imagem construída

- **WHEN** as camadas e as variáveis de ambiente da imagem são inspecionadas
- **THEN** nenhum segredo de aplicação e nenhuma credencial de banco são encontrados

### Requirement: Identificação do artefato e versão reportada não divergem

A identificação de versão da imagem e a versão que a aplicação reporta em execução SHALL derivar da mesma fonte, no mesmo instante do build.

#### Scenario: Versão reportada pela aplicação

- **WHEN** a aplicação em execução expõe sua versão
- **THEN** o valor reportado é idêntico à identificação de versão da imagem que a contém

#### Scenario: Build sem versão informada

- **WHEN** a imagem é construída sem que uma versão seja informada ao build
- **THEN** o build falha, em vez de produzir uma imagem cuja versão reportada seja arbitrária

### Requirement: Um processo de trabalho por container

O container SHALL executar um único processo de trabalho da aplicação, trocando vazão por previsibilidade de consumo e por controle do número de conexões abertas contra o banco.

#### Scenario: Contagem de conexões contra o banco

- **WHEN** um container está em execução e atendendo requisições
- **THEN** o número de conexões que ele abre contra o banco é o de um único processo de trabalho

#### Scenario: Métricas de uma instância

- **WHEN** as métricas de um container são coletadas
- **THEN** elas refletem a instância inteira, sem necessidade de agregação entre processos internos

### Requirement: Conteúdo da imagem restrito ao código da aplicação

A imagem SHALL conter apenas o que é necessário para executar a aplicação. Documentação, configuração de teste e a suíte de testes SHALL NOT estar presentes.

#### Scenario: Suíte de testes e documentação

- **WHEN** o conteúdo da imagem é inspecionado
- **THEN** a suíte de testes, a configuração de teste e a documentação do projeto não estão presentes

#### Scenario: Arquivo de configuração local

- **WHEN** um arquivo de variáveis de ambiente local existe na máquina onde o build ocorre
- **THEN** ele não é incorporado à imagem
