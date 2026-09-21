## Context

Ver `proposal.md` — Why, para a motivação, e `specs/sondas-de-saude/spec.md` para os requisitos. O que este documento acrescenta é o estado concreto do código e as decisões técnicas tomadas em sessão de exploração antes desta proposta.

- `src/main.py` registra hoje só os blueprints `api` (`/api/events`) e `pages` (`/`). Nenhum blueprint de saúde existe. `before_request`/`after_request` são globais: logam toda requisição em INFO e alimentam `PrometheusMetrics(app)`, que mede toda rota registrada.
- `src/core/database.py` tem um único `engine` (`create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_recycle=300)`), sem `connect_timeout`, compartilhado por toda a aplicação via `get_db()`.
- `src/models/event.py` declara `Event` com `__tablename__ = 'events'` — única tabela do domínio.
- `src/schema_prep.py` roda `Base.metadata.create_all` como etapa separada (ADR 001); a aplicação nunca cria estrutura.
- `k8s/encontros-tech.yaml` já sonda o Deployment `encontros-tech-app`: `readinessProbe` por `httpGet path: /` (rota de negócio, consulta o banco) e `livenessProbe` por `tcpSocket`, ambas com `timeoutSeconds: 3`, `periodSeconds: 10`. Essa escolha foi registrada como lacuna conhecida na change anterior (`adicionar-manifesto-kubernetes`, D3): "por que não implementar `/health` e `/ready` primeiro: decisão do usuário [naquela] sessão; fica como pré-requisito de aplicação, não daquela change."
- `docs/trd.md` já documenta o contrato de `/health` e `/ready`, incluindo o módulo `routers.health_router`, o blueprint `health` sem prefixo, e os nomes de função `health_router.health` / `health_router.ready` — escrito antes da implementação existir.

## Goals / Non-Goals

**Goals:**
- Implementar `/health` e `/ready` exatamente como o TRD já os nomeia, para que a documentação pare de descrever código inexistente.
- Rewire das duas sondas do manifesto para os endpoints novos, sem alterar nenhuma outra parte do Deployment.
- Limite de tempo do `/ready` configurável sem rebuild de imagem.

**Non-Goals:**
- Mover ou proteger `/metrics` — fora de escopo, lacuna aceita pela change anterior e mantida aqui.
- `startupProbe` dedicada — a PRD já registra que a distinção "iniciando" vs "não pronto" não muda decisão nenhuma do orquestrador hoje.
- Qualquer alteração de rota, template ou comportamento de negócio existente.
- Reabrir ADR 001 ou ADR 003 (preparação de schema fora do processo, banco efêmero no cluster) — ambos permanecem como estão; este design só observa o que eles decidiram.

## Decisions

### D1 — Módulo e nomes já fixados pelo TRD

`src/routers/health_router.py`, blueprint `health`, registrado em `main.py` sem `url_prefix` (mesmo padrão de `pages`). Funções `health()` e `ready()`. Não há decisão a tomar aqui: o TRD já compromete esses nomes como contrato público (`docs/trd.md:61,87,91-92`); implementar com nome diferente criaria uma segunda divergência entre documentação e código, na direção oposta à que esta change resolve.

### D2 — Um único engine compartilhado, com `connect_timeout` aplicado globalmente

`connect_args={"connect_timeout": settings.READY_DB_TIMEOUT_SECONDS}` entra no `create_engine` existente em `core/database.py` — não um engine paralelo dedicado a `/ready`.

*Por quê:* um segundo engine duplicaria pool e configuração de conexão para o mesmo banco, sem ganho comportamental: o `engine` atual já não tem nenhum teto de conexão, então aplicar um teto de 5s (padrão) a ele é estritamente mais seguro que o estado atual, inclusive para tráfego de negócio que precise abrir uma conexão nova com o banco fora do ar — hoje isso pode ficar pendente por tempo indefinido (limite de SO), depois disso falha em até `READY_DB_TIMEOUT_SECONDS`. Nenhum invariante da PRD proíbe isso; o invariante 6 (verificação não pode degradar tráfego real) é sobre o *custo* das checagens, não sobre dar um teto a algo que hoje não tem nenhum.

*Alternativa considerada:* engine dedicado só para a checagem de `/ready`, isolando o teto de tempo do caminho de negócio. Rejeitada por complexidade duplicada sem benefício: o caminho de negócio só ganha com o teto, nunca perde.

### D3 — Variável de ambiente `READY_DB_TIMEOUT_SECONDS`, padrão 5

Nova entrada em `Settings` (`core/settings.py`), seguindo o padrão existente (`int(os.getenv("READY_DB_TIMEOUT_SECONDS", "5"))`). Cobre **só a fase de conexão** (`connect_timeout` do psycopg2) — decisão explícita do usuário nesta sessão, não a checagem inteira de `/ready`.

*Consequência aceita:* a consulta que prova legibilidade (D4) roda sem teto próprio. Documentado em Risks/Trade-offs.

### D4 — Prontidão do armazenamento comprovada por consulta real, não por catálogo

`/ready`, após confirmar conexão, executa `db.execute(select(Event).limit(1))` (ou `text("SELECT 1 FROM events LIMIT 1")` equivalente) em vez de checar existência de tabela via `information_schema` ou `Base.metadata`.

*Por quê:* P6 do PRD diz "não existe **ou não é legível**" — uma checagem de catálogo prova existência, não permissão de leitura. A consulta real já é quase gratuita: a conexão para ela é a mesma que `/ready` abre para testar o banco (D2), então o custo marginal é uma consulta indexada por chave primária contra uma tabela vazia ou pequena.

*Alternativa considerada:* `information_schema.tables` — mais barata, mas não comprova legibilidade; rejeitada porque o predicado que ela deixaria de cobrir (permissão) é justamente o que distingue P6 de uma checagem trivial de presença.

### D5 — Exclusão total de `/health` e `/ready` de métricas e log de requisição

- **Métricas:** decorator `@metrics.do_not_track()` do próprio `prometheus-flask-exporter` em `health()` e `ready()` — mecanismo nativo da biblioteca já em uso, sem lógica condicional adicional.
- **Log de requisição:** `before_request`/`after_request` em `main.py` ganham uma checagem de `request.path` no início (`if request.path in {"/health", "/ready"}: return` antes de qualquer `g.start_time` ou chamada a `log_request`). Não existe decorator equivalente ao de métricas para o log manual da aplicação, então a exclusão é uma checagem explícita.

*Por quê exclusão total, não parcial:* decisão do usuário nesta sessão. Cobre P16 (consultas de saúde fora das métricas e do log de requisições de negócio) sem exceção.

*Risco aceito:* acoplamento por string de path. Mitigação: os nomes `/health`/`/ready` já são contrato fixo (restrição do PRD, D1 aqui), então o acoplamento não é mais frágil do que o resto do sistema já assume.

### D6 — Causa do `503` logada em WARNING, dentro do próprio handler

O log da causa (P10) acontece dentro de `ready()`, não nos hooks globais excluídos por D5 — são mecanismos independentes: D5 remove o log *genérico* de requisição; este é um log de negócio deliberado, igual a `log_business_event` já usado nos outros routers. Nível **WARNING**, não ERROR — decisão do usuário nesta sessão, substituindo o valor original do PRD: uma dependência fora do ar é uma condição operacional esperada sob consulta contínua a cada 10s, não uma falha da aplicação.

### D7 — Corpo em JSON, via `jsonify`

`{"status": "ok"}` para `/health` e para `/ready` pronto; `{"status": "not ready"}` para `/ready` não pronto. Consistente com o resto da API (`api_router.py` usa `jsonify` em toda resposta).

### D8 — Sondas do manifesto apontam para os endpoints novos, com `timeoutSeconds: 6`

Em `k8s/encontros-tech.yaml`, container `app`:
- `readinessProbe.httpGet.path`: `/` → `/ready`.
- `livenessProbe`: `tcpSocket` → `httpGet path: /health`. Seguro agora porque `/health` nunca toca o banco (D1 da change anterior escolheu `tcpSocket` exatamente para evitar esse acoplamento; `/health` sustenta a mesma garantia por contrato de aplicação, testado nos critérios de aceite).
- `timeoutSeconds`: `3` → `6` nas duas sondas — decisão do usuário nesta sessão, para acomodar o orçamento de `READY_DB_TIMEOUT_SECONDS=5` (D3) mais margem para a consulta de D4, que não tem teto próprio. `periodSeconds: 10` não muda.
- `ConfigMap` (`encontros-tech-config`) ganha `READY_DB_TIMEOUT_SECONDS: "5"`.

*Por que não mudar `periodSeconds` ou `failureThreshold`:* nenhuma decisão desta sessão os afeta; `6 < 10` preserva a relação entre timeout e período sem sobreposição de sondagens.

### D9 — Atualização do PRD é tarefa desta change, TRD não é

`docs/prds/prd-health-ready.md` é o documento de comportamento desta feature (Dado/Quando/Então) e está desatualizado nos próprios pontos que esta sessão decidiu (3s→5s, erro→warning, corpo em aberto→JSON): atualizá-lo é parte de fechar o ciclo desta change, viabilizada como tarefa em `tasks.md`.

`docs/trd.md` é verdade técnica global e, por convenção do projeto (`openspec/config.yaml`), é para consultar, não reescrever a partir de uma change — mesmo padrão que a change anterior já seguiu ao registrar a desatualização do TRD como lacuna, sem corrigi-la. O número de 3s no TRD (`docs/trd.md:94,115`) fica desatualizado por esta change; a correção é tarefa de manutenção de documentação fora deste fluxo.

## Risks / Trade-offs

- **Consulta de legibilidade (D4) sem teto próprio** → em tese, uma conexão TCP bem-sucedida seguida de uma query que nunca retorna deixaria `/ready` pendente além do orçamento combinado. Aceito pelo usuário nesta sessão (Cenário A); mitigado parcialmente por `pool_pre_ping=True`, que já invalida conexões mortas antes de reuso.
- **`connect_timeout` global muda comportamento observável de conexões de negócio** → hoje uma tentativa de nova conexão sob banco fora do ar pode ficar pendente por tempo indefinido; depois desta change, falha em até `READY_DB_TIMEOUT_SECONDS`. Efeito colateral positivo (D2), mas é uma mudança de comportamento fora do texto literal da PRD — sinalizado aqui para não ser descoberto como surpresa depois.
- **Acoplamento por string de path nos hooks globais (D5)** → renomear `/health`/`/ready` sem atualizar `main.py` reintroduziria poluição de log/métrica silenciosamente. Mitigação: os nomes são contrato fixo (restrição do PRD), já testado.
- **`timeoutSeconds: 6` nas sondas é maior que antes** → uma réplica travada demora até 6s a mais por tentativa para ser detectada como não-pronta ou morta, com `failureThreshold: 3` isso adiciona até ~9s ao pior caso de detecção. Aceito como custo direto da decisão do usuário de dar 5s ao connect mais margem.
- **Sequenciamento do rollout** → se o manifesto for reaplicado com as sondas novas antes de a imagem com `/health`/`/ready` existir publicada, as réplicas nunca ficam prontas (`404` nas sondas). Ver Migration Plan.

## Migration Plan

1. Implementar e testar `/health`/`/ready` localmente (Compose), sem tocar no manifesto.
2. Publicar nova imagem com `SERVICE_VERSION` incrementado (ADR 001 — tag fixa, sem tag móvel).
3. Atualizar `k8s/encontros-tech.yaml`: sondas (D8), `ConfigMap` (D8), tag `<SERVICE_VERSION>` nas referências de imagem e no nome do `Job`.
4. `kubectl apply -f k8s/encontros-tech.yaml`. Sob `RollingUpdate` com `maxSurge: 0` (decisão já existente, D8 da change anterior), cada réplica só é substituída quando a nova já responde `/ready`.
5. Verificar as três réplicas prontas via `/ready` e o log de warning ausente em condição normal.

**Rollback:** reaplicar a versão anterior do manifesto (sondas antigas, tag de imagem anterior). Sem dado durável envolvido (ADR 003) e sem alteração de schema, o rollback não tem etapa de dados — é reversível a qualquer momento.
