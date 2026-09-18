## Why

O ADR 001 tirou a preparação de schema de dentro do processo da aplicação; a consequência registrada nas suas próprias "Consequências negativas" é que a ausência de armazenamento deixa de ser detectada na inicialização e passa a se manifestar na primeira consulta ao banco — mais tarde e mais perto do usuário. O PRD `docs/prds/prd-health-ready.md` e o TRD já descrevem o contrato de `/health` e `/ready` que fecha essa lacuna, mas nenhum dos dois existe em `src/`: `main.py` só registra os blueprints `api` e `pages`. Por isso, o manifesto Kubernetes (`k8s/encontros-tech.yaml`, entregue pela change `adicionar-manifesto-kubernetes`) teve que sondar prontidão por `GET /` — uma rota de negócio que renderiza a listagem completa e consulta o banco a cada 10s por réplica — e vida por verificação pura de porta TCP, justamente para nunca depender do banco. Essa escolha foi registrada como lacuna conhecida e questão em aberto naquela change: "trocar as sondas para `/health` e `/ready` quando os endpoints existirem".

Esta change implementa os endpoints e reconecta o manifesto a eles, fechando a lacuna nos dois lados.

## What Changes

- Adiciona `routers/health_router.py` (blueprint `health`, sem prefixo — nomes já fixados no TRD) com:
  - `GET /health`: sempre `200` enquanto o processo aceita requisições; nunca consulta o banco (P2/P3 do PRD, invariante 2).
  - `GET /ready`: `200` quando o banco está alcançável e a tabela de eventos é legível; `503` caso contrário.
- Checagem de conectividade do `/ready` limitada por `connect_timeout` na criação do engine (`core/database.py`), com teto padrão de **5 segundos**, configurável pela variável de ambiente `READY_DB_TIMEOUT_SECONDS`. O teto cobre só a fase de conexão — a consulta que comprova legibilidade (`SELECT 1` contra a tabela de eventos) roda sem teto próprio, decisão registrada em design.md.
- Corpo das duas respostas em JSON (`{"status": "ok"}` / `{"status": "not ready"}`), sem detalhe de infraestrutura.
- Causa do `503` registrada em log de nível **WARNING** (não ERROR), para diagnóstico sem tratar consulta rotineira do orquestrador como falha da aplicação.
- `/health` e `/ready` excluídos do rastreamento de métricas do `PrometheusMetrics` (`@metrics.do_not_track()`) e do log de requisição em `before_request`/`after_request` de `main.py`, para que o polling contínuo do orquestrador não distorça métricas e logs de negócio.
- `k8s/encontros-tech.yaml`: `readinessProbe` do Deployment `encontros-tech-app` troca `httpGet path: /` por `httpGet path: /ready`; `livenessProbe` troca `tcpSocket` por `httpGet path: /health` — seguro agora porque `/health` nunca toca o banco, motivo pelo qual `tcpSocket` foi escolhido originalmente. `timeoutSeconds` das duas sondas sobe de `3` para `6`, para acomodar o orçamento de 5s do `READY_DB_TIMEOUT_SECONDS` mais margem. `ConfigMap` ganha a chave `READY_DB_TIMEOUT_SECONDS`.
- `docs/prds/prd-health-ready.md` atualizado para refletir as decisões desta sessão: limite de 5s configurável (P13, critério de aceite 7), log em WARNING (P10, critério de aceite 3), corpo em JSON (P12), e a tabela de premissas marcada com o que foi confirmado.

Lacuna conhecida que esta change não resolve: `GET /metrics` continua público na mesma porta, sem autenticação — já registrado como risco aceito pela change anterior, inalterado aqui.

## Capabilities

### New Capabilities
- `sondas-de-saude`: contrato HTTP de `/health` (sinal de vida) e `/ready` (sinal de prontidão) para o orquestrador — independência entre os dois sinais, verificação de conectividade e de legibilidade do armazenamento com teto de tempo configurável, ausência de autenticação e de corpo revelador, natureza somente-leitura, log da causa de não-prontidão, e não-interferência com métricas e logs de tráfego de negócio.

### Modified Capabilities
Nenhuma. `implantacao-em-kubernetes` já exige, em texto abstrato, que "tráfego nunca alcança réplica incapaz de atender" e que "a decisão de reiniciar é independente do banco" — essa change troca o *mecanismo* que sustenta essas garantias (de `GET /` e `tcpSocket` para `/ready` e `/health`), mas não introduz nem altera requisito nenhum daquela capability: os números de sonda (`timeoutSeconds`, `periodSeconds`) já eram tratados como detalhe de design na change anterior (D3), não como texto de spec, e continuam sendo.

## Impact

- **Código:** `src/main.py` (novo blueprint, exclusão de métricas/log), `src/routers/health_router.py` (novo), `src/core/database.py` (`connect_timeout`), `src/core/settings.py` (`READY_DB_TIMEOUT_SECONDS`). Nenhuma rota, template ou modelo de negócio existente muda de comportamento.
- **Manifesto:** `k8s/encontros-tech.yaml` — só o container `app` (probes e `ConfigMap`); banco, `Job` de schema e `Service`s não mudam.
- **Documentação:** `docs/prds/prd-health-ready.md` atualizado (ver "What Changes"). `docs/trd.md` já documenta `/health`/`/ready` com o limite antigo de 3s — fica **desatualizado por esta change** nesse número específico; corrigir o TRD é tarefa de manutenção de documentação, fora do fluxo de specs, e não está incluída aqui (mesmo padrão que a change anterior já registrou como lacuna, sem resolver).
- **Blast radius:** alterações isoladas a duas rotas novas e à configuração de sondas de um único Deployment. Nenhuma rota de negócio (`/api/events/*`, páginas) muda de assinatura, comportamento ou tempo de resposta. O maior raio de efeito é indireto: se `/health` ou `/ready` tiverem defeito, o Kubernetes passa a agir sobre um sinal errado — reiniciando réplicas saudáveis ou mantendo réplicas incapazes no balanceamento — o que é exatamente o risco que motiva os critérios de aceite do PRD e a cobertura de testes automatizados exigida.
- **Disponibilidade / HA:** troca `livenessProbe` de verificação puramente TCP para HTTP aplicativo. Isso *aumenta* a precisão (detecta processo travado que ainda aceita conexões mas não responde) sem reintroduzir o acoplamento ao banco que motivou D3 originalmente, porque `/health` é, por contrato (P2/P3, invariante 2), independente do banco — testado explicitamente nos critérios de aceite. `readinessProbe` deixa de renderizar uma página completa a cada 10s por réplica, reduzindo custo por sondagem sem mudar a semântica de "réplica só recebe tráfego quando capaz de atender".
- **Rollback:** reverter é aplicar a versão anterior de `k8s/encontros-tech.yaml` (probes antigas) e/ou remover o registro do blueprint em `main.py`; como os dois endpoints são somente leitura e não introduzem estado, não há dado a migrar de volta. Reaplicar o manifesto anterior restaura o comportamento imediatamente, sem reiniciar o banco nem perder dados (que já são efêmeros por ADR 003).
- **Dependências externas:** nenhuma nova. Reaproveita `SQLAlchemy`/`psycopg2` e `prometheus-flask-exporter` já presentes.
