# TRD — Encontros Tech

> Documento técnico global do projeto. Granularidade baixa: cobre o que é global e estável.
> Regras finas ficam em ADRs.

## Stack

| Dimensão | Valor |
| --- | --- |
| Linguagem principal | Python 3.13, declarada e fixada pela imagem de container — a versão mais recente para a qual todas as 16 dependências pinadas publicam artefatos pré-compilados. Deixa de variar por máquina |
| Runtime/plataforma | Container Docker como unidade de empacotamento e execução, em imagem única para desenvolvimento e produção. Servidor de aplicação Gunicorn 21.2.0 nos dois ambientes, com **um único processo de trabalho por container**. Desenvolvimento: Docker Compose, construindo e executando a mesma imagem ao lado do banco, condicionando a subida da aplicação à disponibilidade real da dependência. Produção: cluster Amazon EKS dedicado na AWS, três réplicas em três zonas de disponibilidade. A diferença entre ambientes existe apenas como configuração externa à imagem, nunca como imagem distinta |
| Framework principal | Flask 3.0.0, com Jinja2 3.1.6 para renderização de páginas |
| Banco de dados | PostgreSQL, acessado via SQLAlchemy 2.0.43 e driver psycopg2-binary 2.9.10. Produção: container PostgreSQL executado como carga dentro do próprio cluster, sem identidade estável e com **armazenamento efêmero** — sem volume persistente reivindicado —, exposto por endereço de serviço interno único e estável (ADR 003, que revisa a escolha de banco do ADR 002). Desenvolvimento: container PostgreSQL orquestrado por Docker Compose. Os dois ambientes voltam a executar o banco como container |
| Ferramentas de build | Build de imagem Docker em estágio único, sobre distribuição base de propósito geral, com contexto restrito a `src/`. Não há etapa de compilação — todas as dependências pinadas têm artefato pré-compilado na versão de interpretador escolhida. Publicação manual em repositório público no Docker Hub, arquitetura única (`linux/amd64`), com tag única derivada de `SERVICE_VERSION` e congelada na imagem no momento do build; não há tag móvel |
| Gerenciador de pacotes | pip, a partir de `src/requirements.txt` com 16 dependências de versão fixada. Não há lockfile nem `pyproject.toml` |

## Arquitetura

### Padrão arquitetural

Camadas: `router → service → model`, com schemas Pydantic na fronteira de entrada e saída. Existem duas superfícies de entrada — uma API JSON e um conjunto de páginas HTML — implementadas como blueprints Flask distintos que consomem o mesmo módulo de serviço, de modo que a regra de negócio e o acesso ao banco existem em um único ponto.

A preparação do schema do banco não acontece dentro do processo da aplicação: é etapa separada e anterior, executada a partir da mesma imagem, da qual a aplicação depende para subir. Em produção ela executa como Job do Kubernetes, concluído antes do rollout das réplicas, de modo que réplicas subindo em paralelo nunca concorrem pela mesma criação de estruturas. Com o banco em armazenamento efêmero (ADR 003), essa etapa deixa de ser executada uma única vez por publicação e passa a ser **condição de recuperação do serviço**: a cada substituição do pod do banco, o banco nasce vazio e o Job precisa ser reexecutado, sem o que as réplicas permanecem vivas e não-prontas.

Em produção a aplicação executa como três réplicas idênticas e intercambiáveis, uma por zona de disponibilidade, garantidas por restrição de espalhamento topológico (`topologySpreadConstraints`, `maxSkew: 1`, `topologyKey: topology.kubernetes.io/zone`, `whenUnsatisfiable: DoNotSchedule`) e protegidas por orçamento de interrupção (`PodDisruptionBudget`, `minAvailable: 2`). A aplicação não mantém estado próprio entre requisições — toda informação persistente está no banco —, o que torna as réplicas substituíveis sem coordenação e viabiliza o uso de capacidade interruptível nos nós.

### Estrutura de pastas dominante

```
docs/            # PRDs do projeto
└── adrs/        # Decisões arquiteturais registradas
k8s/             # Manifesto de implantação em Kubernetes (arquivo único, multi-documento)
prompts/         # Prompts usados para gerar a documentação
src/             # Todo o código da aplicação — também o contexto de build da imagem
├── core/        # Configurações, conexão com o banco e logging
├── models/      # Entidade SQLAlchemy e declaração das tabelas
├── schemas/     # Modelos Pydantic de entrada e saída
├── services/    # Regra de negócio e operações sobre o banco
├── routers/     # Blueprints Flask: API JSON, páginas HTML e sinais de saúde
├── templates/   # Templates Jinja2
├── static/      # CSS e JavaScript servidos pela aplicação
└── tests/       # Testes automatizados, espelhando a estrutura de src
```

Na raiz: `pytest.ini`, `api-requests.http`, `docker-compose.yml`, `kind-cluster.yaml` (configuração do cluster kind usado para validar o manifesto de `k8s/`, não manifesto da aplicação) e dois arquivos de exemplo de variáveis de ambiente (`.env.exemple` na raiz e `src/.env.example`). O `Dockerfile` fica em `src/`, junto ao contexto de build — `pytest.ini` e `docs/` ficam, por isso, fora da imagem. O ponto de entrada da aplicação é `src/main.py`. Não há arquivos `__init__.py` em nenhum diretório.

### Módulos / camadas principais

| Módulo | Responsabilidade |
| --- | --- |
| `main` | Configura o logging, instancia a aplicação Flask, registra métricas Prometheus, instala os middlewares de requisição e registra os blueprints. **Não prepara o schema do banco** e não encerra o processo quando o banco está indisponível |
| `schema_prep` | Rotina de preparação de schema, executada a partir da mesma imagem como etapa anterior e independente da aplicação. Cria estruturas ausentes; não altera estruturas existentes. Sinaliza resultado por código de saída |
| `core.settings` | Carrega variáveis de ambiente e expõe uma instância única de configuração |
| `core.database` | Cria o engine SQLAlchemy e fornece sessões de banco por meio de um gerenciador de contexto. O engine usa verificação prévia de conexão (`pool_pre_ping=True`) e reciclagem (`pool_recycle=300`) — condição para que a substituição do pod do banco se traduza em recuperação da aplicação, e não em erro servido depois de a dependência já ter voltado |
| `core.logging` | Configura o logger da aplicação e oferece funções auxiliares para registrar requisições, operações de banco e eventos de negócio |
| `models.event` | Declara a base SQLAlchemy e a entidade `Event` |
| `schemas.event` | Define os modelos Pydantic de criação, atualização e saída de evento |
| `services.event_service` | Concentra criação, consulta e atualização de eventos, além da exceção `EventNotFoundError` |
| `routers.api_router` | Blueprint da API JSON, registrado sob `/api/events` |
| `routers.page_router` | Blueprint das páginas HTML, registrado na raiz, incluindo o processamento dos formulários |
| `routers.health_router` | Blueprint dos sinais de vida e prontidão, registrado sem prefixo. Somente leitura, sem efeito colateral sobre dados ou estruturas |

### Rotas

API — blueprint `api`, registrado com prefixo `/api/events`:

| Método | Rota | Handler |
| --- | --- | --- |
| POST | `/api/events/` | `api_router.create_event` |
| GET | `/api/events/` | `api_router.read_events` |
| GET | `/api/events/by-token/<edit_token>` | `api_router.get_event_by_token` |
| PUT | `/api/events/by-token/<edit_token>` | `api_router.update_event` |

Páginas — blueprint `pages`, registrado sem prefixo:

| Método | Rota | Handler |
| --- | --- | --- |
| GET | `/` | `page_router.list_events_page` |
| GET | `/events/new` | `page_router.new_event_page` |
| GET | `/events/<int:event_id>` | `page_router.event_detail_page` |
| GET | `/events/edit/<edit_token>` | `page_router.edit_event_page` |
| POST | `/events/` | `page_router.create_event_form` |
| POST | `/events/edit/<edit_token>` | `page_router.update_event_form` |

A listagem em `GET /` e em `GET /api/events/` aceita o parâmetro `search`, aplicado como busca parcial e sem distinção de maiúsculas sobre título, descrição e local. A rota da API aceita ainda `skip` e `limit`, com padrões 0 e 100.

Saúde e prontidão — blueprint `health`, registrado sem prefixo:

| Método | Rota | Handler |
| --- | --- | --- |
| GET | `/health` | `health_router.health` |
| GET | `/ready` | `health_router.ready` |

Contrato com a infraestrutura, especificado no PRD de health/ready: ambas respondem exclusivamente `200` ou `503`, sem corpo informativo, sem autenticação e sem efeito colateral sobre dados ou estruturas. `/health` nunca depende do banco. `/ready` responde `503` quando o banco está indisponível ou quando o armazenamento de eventos não é legível pela aplicação, e responde em no máximo 3 segundos em qualquer estado da dependência. A resposta reflete exclusivamente a capacidade da instância consultada, sem depender do estado das demais. Os nomes `/health` e `/ready` são contrato entre a aplicação e a configuração de deploy: alterá-los exige alteração coordenada das probes.

### Modelo de dados

Tabela `events` — única tabela do projeto, sem chaves estrangeiras ou relacionamentos:

| Coluna | Tipo | Constraints/Default |
| --- | --- | --- |
| `id` | Integer | Chave primária, indexada |
| `title` | String | Indexada |
| `description` | Text | Nenhuma |
| `date` | DateTime | Default `datetime.datetime.utcnow` |
| `location` | String | Nenhuma |
| `edit_token` | String | Única, indexada, default gerado como UUID4 em formato texto |

O campo `technologies` existe nos schemas Pydantic como lista de texto e é anexado ao objeto retornado em memória após criação e atualização, mas não possui coluna correspondente e não é persistido.

## Requisitos Não-Funcionais

| Dimensão | Requisito |
| --- | --- |
| Performance | Não há alvo de vazão ou latência declarado. Fixado um processo de trabalho por container, trocando vazão por réplica por previsibilidade de consumo e controle do número de conexões abertas contra o banco. Limite explícito: `/ready` responde em no máximo 3 segundos em qualquer estado da dependência |
| Disponibilidade/SLA | Alvo declarado no ADR 002: tolerar a perda de **uma** zona de disponibilidade sem indisponibilidade percebida, dentro de **uma única região**. **Esse alvo não é atendido hoje** (ADR 003): a aplicação mantém três réplicas, uma por zona, com `minAvailable: 2` durante manutenção, e nós em três zonas — mínimo 3, desejado 3, teto 6, este reservado à substituição de nós durante atualização —, mas todas as réplicas dependem de um **único pod de banco em uma única zona**, com armazenamento efêmero. A perda daquela zona é perda de serviço, e as réplicas sobreviventes apenas reportam não-prontidão. Não há réplica de contingência, failover, backup nem recuperação a ponto no tempo; o RPO é total a cada substituição do pod do banco. Não há SLA formal contratado. Perda de região é perda de serviço e não é endereçada. Com nós de capacidade interruptível, a retirada de instância é evento normal — o que torna o reagendamento do pod do banco, e portanto a perda de dados, ocorrência esperada e não excepcional |
| Escalabilidade | Três réplicas fixas, sem escalonamento automático — o número é declarado no manifesto, não é comportamento; alterá-lo exige nova publicação. O teto de conexões deixa de derivar da memória de uma classe de instância gerenciada e passa a ser **parâmetro do próprio container de banco** (ADR 003), removendo o limite de aproximadamente 7 réplicas que a classe `db.t4g.micro` impunha. O consumo continua sendo de 15 conexões por processo (`pool_size=5` mais `max_overflow=10`), 45 no total com três réplicas, agora contra um teto ajustável |
| Segurança | Não há requisito formal declarado. Nenhum endpoint exige autenticação, inclusive `/health` e `/ready`; a alteração de um evento é autorizada exclusivamente pela posse do `edit_token`. A `SECRET_KEY` do Flask e a credencial do banco em `DATABASE_URL` são obrigatoriamente externas ao código-fonte e à imagem — condição bloqueante para execução em produção, dado que a imagem é publicada em repositório público e tudo o que está nela é extraível por qualquer pessoa; em produção ambas são fornecidas como Secret do Kubernetes (ADR 003). Com o banco dentro do cluster, o tráfego até ele não atravessa a rede do provedor e deixa de ter transporte cifrado e usuário administrativo distinto do de aplicação, propriedades que o serviço gerenciado oferecia. Os corpos de `/health` e `/ready` não revelam nome de host, endereço, credencial, versão de dependência ou qualquer detalhe de topologia interna |
| Observabilidade | Logs em stdout com formato fixo contendo data, nível, logger, função, linha e mensagem, com cores quando a saída é um terminal e o formato configurado é `colored`; métricas expostas via `prometheus-flask-exporter`, incluindo a métrica informativa `app_info`, cuja versão não pode divergir da identificação da imagem que a contém, por derivarem da mesma fonte no mesmo instante; middlewares que registram método, caminho, status e duração de cada requisição; funções dedicadas para registrar operações de banco e eventos de negócio; o nome do host do processo é injetado nas páginas renderizadas. Com um processo de trabalho por container, as métricas voltam a ser agregáveis por réplica; a agregação **entre** réplicas continua inexistente. A coleta de logs e os sinais de segurança do ambiente são responsabilidade de agentes executados em nível de nó, consumindo o stdout do container — requisito que determinou o modo de compute do cluster |

## Dependências Externas

| Serviço / Sistema | Tipo | Constraint relevante | Dono |
| --- | --- | --- | --- |
| PostgreSQL (container no cluster) | Banco de dados relacional autogerido, dentro do cluster | Endereço e credenciais definidos por `DATABASE_URL`, externas à imagem, fornecidas como Secret do Kubernetes. Carga sem identidade estável, **armazenamento efêmero, sem volume persistente** (ADR 003): cada substituição do pod apaga todos os dados e exige reexecução do Job de preparação de schema. Endereço de conexão único e estável por nome de serviço interno. Sem réplica de contingência, sem failover, sem backup e sem recuperação a ponto no tempo. Versão, parâmetros e correções são responsabilidade da equipe. Em desenvolvimento é o mesmo container PostgreSQL, via Compose — a assimetria de TLS, usuário e parâmetros de instância que existia com o serviço gerenciado deixa de existir | Equipe de DevOps |
| Amazon EKS | Plataforma de orquestração de containers | Cluster dedicado a este projeto, sem compartilhamento de plano de controle nem economia de escala com outras cargas. Grupo de nós gerenciado, capacidade interruptível, 2 vCPU e 2 GiB em família de uso geral com capacidade expansível (`t3.small` e equivalentes de outras famílias, declarados em conjunto para ampliar os conjuntos de capacidade disponíveis), arquitetura `linux/amd64`. Correções de sistema operacional dos nós e ciclo de vida das versões do cluster são responsabilidade da equipe. `/health` e `/ready` não existem no código; as sondas declaradas no manifesto (`k8s/encontros-tech.yaml`) usam o que existe hoje — prontidão por `GET /` na porta 8000 e vida por verificação de porta TCP na mesma porta — e o código de saída da preparação de schema como condição de rollout | Equipe de DevOps |
| Docker Hub | Registro público de imagens | Publicação manual, arquitetura única, tag única sem tag móvel: publicar sem incrementar `SERVICE_VERSION` sobrescreve silenciosamente uma imagem já distribuída. Tudo o que está na imagem é publicamente extraível | Equipe de DevOps |
| cdn.jsdelivr.net | CDN de terceiros | As páginas carregam Bootstrap 5.3.0 (CSS e JS) e Bootstrap Icons diretamente do CDN; não há cópia local desses recursos | Não definido |

## Padrões

### Testes

| Item | Valor |
| --- | --- |
| Framework | pytest 8.3.4 |
| Comando completo | Não definido — nenhum script, Makefile, pipeline ou documento do repositório define um comando de execução; `pytest.ini` declara apenas `pythonpath = .` |
| Cobertura mínima | Não definido — não há ferramenta nem configuração de cobertura no repositório |
| Estratégia | Testes unitários com a sessão de banco substituída por `MagicMock`, sem banco real. Um único arquivo, `src/tests/services/test_event_service.py`, com sete testes, cobrindo apenas a camada de serviço. Não há testes de rota, de schema ou de integração. O contexto de build restrito a `src/` mantém `pytest.ini` fora da imagem, o que impede executar a suíte dentro do container sem ajuste do contexto ou do arquivo de configuração |

### Estilo de código

- **Linter:** Não aplicável — não há configuração de linter no repositório
- **Formatter:** Não aplicável — não há configuração de formatter no repositório
- **Convenções de nomenclatura:** módulos, funções e variáveis em `snake_case`; classes em `PascalCase`; constantes em maiúsculas; identificadores de código em inglês, enquanto comentários, docstrings e mensagens de log são em português; módulos nomeados pela entidade dentro de pastas nomeadas pela camada (`services/event_service.py`, `models/event.py`); imports internos absolutos a partir da raiz de `src`

### Error handling

Cada handler de rota envolve sua execução em `try/except`. A camada de serviço registra o erro em log, executa `rollback` nas operações de escrita e relança a exceção; a decisão sobre a resposta é sempre do router. O serviço define uma exceção própria, `EventNotFoundError`, lançada quando uma consulta por identificador ou por token não encontra registro.

As duas superfícies tratam as mesmas condições de formas diferentes. Na API, `EventNotFoundError` resulta em `abort(404)`, `ValueError` em `abort(400)` com a mensagem de validação, e qualquer outra exceção em `abort(500)` com mensagem genérica. Nas páginas, `EventNotFoundError` renderiza o template `events/not_found.html` nas rotas de leitura, e nos formulários gera mensagem via `flash` seguida de redirecionamento; `ValueError` e exceções genéricas nos formulários também produzem `flash` e redirecionamento de volta ao formulário de origem. A falha na página de listagem renderiza um template `error.html` com status 500.

A indisponibilidade do banco na inicialização não encerra o processo: a aplicação sobe, `/health` responde `200` e `/ready` responde `503` até a dependência voltar, sem necessidade de reiniciar a instância. Em contrapartida, a ausência de schema deixa de ser detectada na inicialização e passa a se manifestar na primeira consulta ao banco — mais tarde e mais perto do usuário —, sendo `/ready` o mecanismo que impede o tráfego de alcançar uma instância nessa condição — condição que, com banco em armazenamento efêmero (ADR 003), passa a ocorrer sempre que o pod do banco é substituído, até que o Job de preparação de schema seja reexecutado. Na substituição do pod do banco, o endereço de conexão permanece o mesmo e o endereço de rede muda; a verificação prévia do pool descarta as conexões mortas, sem o que a aplicação continuaria servindo erro depois de a dependência já ter se recuperado.

### Logging

- **Formato:** texto de linha única com campos separados por barra vertical — `asctime | levelname | name | funcName:lineno | message` —, escrito em stdout. Quando `LOG_FORMAT` é `colored` e a saída é um terminal, o nível recebe cor ANSI. Eventos de negócio e operações de banco usam prefixos fixos, `BUSINESS |` e `DB |`, com pares chave-valor
- **Nível padrão:** `INFO`; passa a `DEBUG` quando a variável `DEBUG` é verdadeira. Os loggers de `sqlalchemy.engine` e `urllib3` são fixados em `WARNING`
- **Biblioteca:** módulo `logging` da biblioteca padrão, configurado em `core/logging.py`. A aplicação Flask reaproveita os handlers e o nível do logger principal
- **Coleta:** stdout do container, consumido por agente executado em nível de nó no cluster. A aplicação não escreve arquivos de log nem conhece o destino final

### Autenticação / autorização

Não há autenticação. Nenhuma rota exige credencial, sessão ou identificação de usuário, e não existe conceito de usuário no modelo de dados. A autorização de escrita sobre um evento existente é feita por posse de segredo: o `edit_token` gerado na criação é o único dado que permite acessar as rotas de edição, tanto na API quanto nas páginas. Criar e ler eventos não exige nada.

## Decisões Globais (ADRs)

| # | Título | Data | Status | Link |
| --- | --- | --- | --- | --- |
| 001 | Adotar containers Docker como unidade de empacotamento e execução | 2026-09-15 | aceito | [adrs/001](adrs/001-containerizacao-com-docker.md) |
| 002 | Executar a aplicação em cluster EKS dedicado na AWS, com o banco de dados em serviço gerenciado | 2026-09-15 | aceito | [adrs/002](adrs/002-ambiente-de-producao-em-eks-na-aws.md) |
| 003 | Executar o banco de dados como carga no próprio cluster, com armazenamento efêmero — revisa apenas a escolha de banco do ADR 002 | 2026-09-17 | aceito | [adrs/003](adrs/003-banco-de-dados-no-cluster.md) |
