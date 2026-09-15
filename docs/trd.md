# TRD — Encontros Tech

> Documento técnico global do projeto. Granularidade baixa: cobre o que é global e estável.
> Regras finas ficam em ADRs.

## Stack

| Dimensão | Valor |
|---|---|
| Linguagem principal | Python 3.14.6 |
| Runtime/plataforma | Processo Python único. Servidor embutido do Flask via `app.run` quando executado diretamente; Gunicorn declarado como dependência, sem comando de inicialização definido no repositório |
| Framework principal | Flask 3.0.0, com Jinja2 3.1.6 para renderização de páginas |
| Banco de dados | PostgreSQL, acessado via SQLAlchemy 2.0.43 e driver psycopg2-binary 2.9.10 |
| Ferramentas de build | Não aplicável — não há etapa de build, empacotamento ou bundling no repositório |
| Gerenciador de pacotes | pip, a partir de `src/requirements.txt` com 16 dependências de versão fixada. Não há lockfile nem `pyproject.toml` |

## Arquitetura

### Padrão arquitetural

Camadas: `router → service → model`, com schemas Pydantic na fronteira de entrada e saída. Existem duas superfícies de entrada — uma API JSON e um conjunto de páginas HTML — implementadas como blueprints Flask distintos que consomem o mesmo módulo de serviço, de modo que a regra de negócio e o acesso ao banco existem em um único ponto.

### Estrutura de pastas dominante

```
docs/            # PRDs do projeto
prompts/         # Prompts usados para gerar a documentação
src/             # Todo o código da aplicação
├── core/        # Configurações, conexão com o banco e logging
├── models/      # Entidade SQLAlchemy e declaração das tabelas
├── schemas/     # Modelos Pydantic de entrada e saída
├── services/    # Regra de negócio e operações sobre o banco
├── routers/     # Blueprints Flask: API JSON e páginas HTML
├── templates/   # Templates Jinja2
├── static/      # CSS e JavaScript servidos pela aplicação
└── tests/       # Testes automatizados, espelhando a estrutura de src
```

Na raiz: `pytest.ini`, `api-requests.http` e dois arquivos de exemplo de variáveis de ambiente (`.env.exemple` na raiz e `src/.env.example`). O ponto de entrada é `src/main.py`. Não há arquivos `__init__.py` em nenhum diretório.

### Módulos / camadas principais

| Módulo | Responsabilidade |
|---|---|
| `main` | Configura o logging, cria as tabelas no banco, instancia a aplicação Flask, registra métricas Prometheus, instala os middlewares de requisição e registra os blueprints |
| `core.settings` | Carrega variáveis de ambiente e expõe uma instância única de configuração |
| `core.database` | Cria o engine SQLAlchemy e fornece sessões de banco por meio de um gerenciador de contexto |
| `core.logging` | Configura o logger da aplicação e oferece funções auxiliares para registrar requisições, operações de banco e eventos de negócio |
| `models.event` | Declara a base SQLAlchemy e a entidade `Event` |
| `schemas.event` | Define os modelos Pydantic de criação, atualização e saída de evento |
| `services.event_service` | Concentra criação, consulta e atualização de eventos, além da exceção `EventNotFoundError` |
| `routers.api_router` | Blueprint da API JSON, registrado sob `/api/events` |
| `routers.page_router` | Blueprint das páginas HTML, registrado na raiz, incluindo o processamento dos formulários |

### Rotas

API — blueprint `api`, registrado com prefixo `/api/events`:

| Método | Rota | Handler |
|---|---|---|
| POST | `/api/events/` | `api_router.create_event` |
| GET | `/api/events/` | `api_router.read_events` |
| GET | `/api/events/by-token/<edit_token>` | `api_router.get_event_by_token` |
| PUT | `/api/events/by-token/<edit_token>` | `api_router.update_event` |

Páginas — blueprint `pages`, registrado sem prefixo:

| Método | Rota | Handler |
|---|---|---|
| GET | `/` | `page_router.list_events_page` |
| GET | `/events/new` | `page_router.new_event_page` |
| GET | `/events/<int:event_id>` | `page_router.event_detail_page` |
| GET | `/events/edit/<edit_token>` | `page_router.edit_event_page` |
| POST | `/events/` | `page_router.create_event_form` |
| POST | `/events/edit/<edit_token>` | `page_router.update_event_form` |

A listagem em `GET /` e em `GET /api/events/` aceita o parâmetro `search`, aplicado como busca parcial e sem distinção de maiúsculas sobre título, descrição e local. A rota da API aceita ainda `skip` e `limit`, com padrões 0 e 100.

### Modelo de dados

Tabela `events` — única tabela do projeto, sem chaves estrangeiras ou relacionamentos:

| Coluna | Tipo | Constraints/Default |
|---|---|---|
| `id` | Integer | Chave primária, indexada |
| `title` | String | Indexada |
| `description` | Text | Nenhuma |
| `date` | DateTime | Default `datetime.datetime.utcnow` |
| `location` | String | Nenhuma |
| `edit_token` | String | Única, indexada, default gerado como UUID4 em formato texto |

O campo `technologies` existe nos schemas Pydantic como lista de texto e é anexado ao objeto retornado em memória após criação e atualização, mas não possui coluna correspondente e não é persistido.

## Requisitos Não-Funcionais

| Dimensão | Requisito |
|---|---|
| Performance | Não definido |
| Disponibilidade/SLA | Não definido |
| Escalabilidade | Não definido |
| Segurança | Não há requisito formal declarado. O que existe no código: nenhum endpoint exige autenticação; a alteração de um evento é autorizada exclusivamente pela posse do `edit_token`; a `SECRET_KEY` do Flask está fixa no código-fonte |
| Observabilidade | Logs em stdout com formato fixo contendo data, nível, logger, função, linha e mensagem, com cores quando a saída é um terminal e o formato configurado é `colored`; métricas expostas via `prometheus-flask-exporter`, incluindo a métrica informativa `app_info` com a versão do serviço; middlewares que registram método, caminho, status e duração de cada requisição; funções dedicadas para registrar operações de banco e eventos de negócio; o nome do host do processo é injetado nas páginas renderizadas |

## Dependências Externas

| Serviço / Sistema | Tipo | Constraint relevante | Dono |
|---|---|---|---|
| PostgreSQL | Banco de dados relacional | Endereço e credenciais definidos por `DATABASE_URL`. A aplicação executa a criação das tabelas durante a inicialização, antes de a aplicação Flask existir | Não definido |
| cdn.jsdelivr.net | CDN de terceiros | As páginas carregam Bootstrap 5.3.0 (CSS e JS) e Bootstrap Icons diretamente do CDN; não há cópia local desses recursos | Não definido |

## Padrões

### Testes

| Item | Valor |
|---|---|
| Framework | pytest 8.3.4 |
| Comando completo | Não definido — nenhum script, Makefile, pipeline ou documento do repositório define um comando de execução; `pytest.ini` declara apenas `pythonpath = .` |
| Cobertura mínima | Não definido — não há ferramenta nem configuração de cobertura no repositório |
| Estratégia | Testes unitários com a sessão de banco substituída por `MagicMock`, sem banco real. Um único arquivo, `src/tests/services/test_event_service.py`, com sete testes, cobrindo apenas a camada de serviço. Não há testes de rota, de schema ou de integração |

### Estilo de código

- **Linter:** Não aplicável — não há configuração de linter no repositório
- **Formatter:** Não aplicável — não há configuração de formatter no repositório
- **Convenções de nomenclatura:** módulos, funções e variáveis em `snake_case`; classes em `PascalCase`; constantes em maiúsculas; identificadores de código em inglês, enquanto comentários, docstrings e mensagens de log são em português; módulos nomeados pela entidade dentro de pastas nomeadas pela camada (`services/event_service.py`, `models/event.py`); imports internos absolutos a partir da raiz de `src`

### Error handling

Cada handler de rota envolve sua execução em `try/except`. A camada de serviço registra o erro em log, executa `rollback` nas operações de escrita e relança a exceção; a decisão sobre a resposta é sempre do router. O serviço define uma exceção própria, `EventNotFoundError`, lançada quando uma consulta por identificador ou por token não encontra registro.

As duas superfícies tratam as mesmas condições de formas diferentes. Na API, `EventNotFoundError` resulta em `abort(404)`, `ValueError` em `abort(400)` com a mensagem de validação, e qualquer outra exceção em `abort(500)` com mensagem genérica. Nas páginas, `EventNotFoundError` renderiza o template `events/not_found.html` nas rotas de leitura, e nos formulários gera mensagem via `flash` seguida de redirecionamento; `ValueError` e exceções genéricas nos formulários também produzem `flash` e redirecionamento de volta ao formulário de origem. A falha na página de listagem renderiza um template `error.html` com status 500.

### Logging

- **Formato:** texto de linha única com campos separados por barra vertical — `asctime | levelname | name | funcName:lineno | message` —, escrito em stdout. Quando `LOG_FORMAT` é `colored` e a saída é um terminal, o nível recebe cor ANSI. Eventos de negócio e operações de banco usam prefixos fixos, `BUSINESS |` e `DB |`, com pares chave-valor
- **Nível padrão:** `INFO`; passa a `DEBUG` quando a variável `DEBUG` é verdadeira. Os loggers de `sqlalchemy.engine` e `urllib3` são fixados em `WARNING`
- **Biblioteca:** módulo `logging` da biblioteca padrão, configurado em `core/logging.py`. A aplicação Flask reaproveita os handlers e o nível do logger principal

### Autenticação / autorização

Não há autenticação. Nenhuma rota exige credencial, sessão ou identificação de usuário, e não existe conceito de usuário no modelo de dados. A autorização de escrita sobre um evento existente é feita por posse de segredo: o `edit_token` gerado na criação é o único dado que permite acessar as rotas de edição, tanto na API quanto nas páginas. Criar e ler eventos não exige nada.

## Decisões Globais (ADRs)

| # | Título | Data | Status | Link |
|---|---|---|---|---|
| — | *(nenhum ADR registrado)* | — | — | — |
