## 1. Configuração

- [x] 1.1 Adicionar `READY_DB_TIMEOUT_SECONDS: int = int(os.getenv("READY_DB_TIMEOUT_SECONDS", "5"))` em `src/core/settings.py`, e verificar com `python3 -c "from core.settings import settings; print(settings.READY_DB_TIMEOUT_SECONDS)"` (executado a partir de `src/`) que o padrão é `5` sem a variável definida, e reflete o valor da variável quando definida.
- [x] 1.2 Aplicar `connect_args={"connect_timeout": settings.READY_DB_TIMEOUT_SECONDS}` ao `create_engine` em `src/core/database.py` (D2/D3 de design.md — engine único, não um segundo engine). Verificar chamando `engine.connect()` contra um `DATABASE_URL` apontando para um host que descarta pacotes (ex.: um IP não roteável) e confirmar que a exceção ocorre em torno do teto configurado, não indefinidamente.

## 2. Endpoints de saúde

- [x] 2.1 Criar `src/routers/health_router.py` com blueprint `health` e `GET /health`: responde `200` com corpo `{"status": "ok"}` sem tocar o banco. Verificar com um teste que faz a chamada sem qualquer mock de banco configurado e confirma `200`.
- [x] 2.2 Implementar `GET /ready` em `health_router.py`: abre conexão via `get_db()`/engine (D2), executa a consulta real contra a tabela `events` (D4 — `SELECT 1 FROM events LIMIT 1` ou equivalente via `Event`), responde `200`/`{"status": "ok"}` em sucesso. Verificar com teste que mocka uma consulta bem-sucedida e confirma `200`.
- [x] 2.3 Tratar falha de conexão e falha de consulta em `/ready` como `503`/`{"status": "not ready"}`, registrando a causa em `logger.warning(...)` (D6 — não ERROR). Verificar com dois testes: um simulando falha de conexão, outro simulando tabela ausente/consulta falhando, confirmando `503` e uma chamada a `logger.warning` em cada caso.
- [x] 2.4 Registrar o blueprint em `src/main.py`: `app.register_blueprint(health_router.bp)`, sem `url_prefix` (D1). Verificar com `flask routes` (ou teste de app context) que `/health` e `/ready` aparecem sem prefixo, ao lado de `/api/events` e `/`.

## 3. Exclusão de métricas e log de requisição

- [x] 3.1 Aplicar `@metrics.do_not_track()` em `health()` e `ready()` (D5). Verificar consultando `/metrics` após bater em `/health` e `/ready` repetidas vezes, e confirmando que os contadores de `flask_http_request_duration_seconds` para esses dois paths não aparecem ou não incrementam.
- [x] 3.2 Adicionar checagem de `request.path` no início de `before_request` e `after_request` em `main.py`, retornando antes de `g.start_time`/`log_request` quando o path for `/health` ou `/ready` (D5). Verificar com teste que captura o logger e confirma zero chamadas de log de requisição (INFO) ao consultar as duas rotas, mesmo repetidamente.

## 4. Testes automatizados

- [x] 4.1 Criar `src/tests/routers/test_health_router.py` cobrindo os cenários do PRD e de `specs/sondas-de-saude/spec.md`: `/health` sempre `200` (com e sem mock de falha de banco); `/ready` nos três estados (pronto, banco indisponível, armazenamento ausente/ilegível); corpo JSON em cada caso; ausência de autenticação. Usar `unittest.mock.MagicMock`/`patch`, no mesmo padrão de `tests/services/test_event_service.py` — sem banco real.
- [x] 4.2 Adicionar teste que mede o tempo de resposta de `/ready` contra uma conexão que nunca é aceita nem recusada, confirmando que a resposta chega dentro do teto configurado, não indefinidamente (P13). Implementado com um `engine` real apontando para um endereço não roteável (`10.255.255.1`), em vez de um mock com `side_effect` bloqueante — é a única forma de exercitar o `connect_timeout` de verdade (a lógica de tempo está no psycopg2/SO, não no código da aplicação), sem depender de nenhum banco de dados real em execução.
- [x] 4.3 Rodar a suíte completa com `cd src && python -m pytest tests/ -q` e confirmar que os testes novos rodam junto com os existentes, em um único comando, sem qualquer banco real em execução (critério de aceite 13). Resultado: 14 passed em 2.61s.

## 5. Manifesto Kubernetes

- [x] 5.1 Em `k8s/encontros-tech.yaml`, trocar `readinessProbe.httpGet.path` de `/` para `/ready` e `livenessProbe` de `tcpSocket` para `httpGet path: /health` (mesma porta 8000), no container `app` do Deployment `encontros-tech-app` (D8). Verificar com `kubectl apply --dry-run=client -f k8s/encontros-tech.yaml` sem erro de validação.
- [x] 5.2 Atualizar `timeoutSeconds` de `3` para `6` nas duas sondas do mesmo container (D8). Verificar por inspeção do YAML aplicado (`kubectl get deployment encontros-tech-app -o yaml` após apply) que os dois valores refletem `6`.
- [x] 5.3 Adicionar `READY_DB_TIMEOUT_SECONDS: "5"` ao `ConfigMap` `encontros-tech-config` (D8). Verificar com `kubectl get configmap encontros-tech-config -o yaml` após apply.

## 6. Documentação

- [x] 6.1 Atualizar `docs/prds/prd-health-ready.md`: P10 e critério de aceite 3 (erro → warning), P12 (corpo definido como JSON), P13 e critério de aceite 7 (3s → 5s, escopo só no connect, configurável via `READY_DB_TIMEOUT_SECONDS`), critério de aceite 11 (remover ressalva de premissa em aberto), e a tabela "Premissas a confirmar" (linhas 1-3 marcadas como confirmadas). Verificar por leitura comparando cada trecho alterado com as decisões registradas em `design.md`.

## 7. Verificação de ponta a ponta (gate)

- [x] 7.1 Subir o ambiente local com `docker compose up --build`, aguardar `schema_prep` concluir, e confirmar `curl -i http://localhost:8000/health` → `200` e `curl -i http://localhost:8000/ready` → `200` (critério de aceite 1).
- [x] 7.2 Parar o container `db` (`docker compose stop db`) com a aplicação em execução: confirmar `/health` continua `200` e `/ready` passa a `503`, e que o log do serviço `app` registra a causa em nível WARNING (critérios de aceite 2 e 3 parcial — reinicialização coberta em 7.3).
- [x] 7.3 Com `db` ainda parado, reiniciar o serviço `app` (`docker compose restart app`): confirmar que o processo sobe e permanece em execução, `/health` responde `200`, `/ready` responde `503`, e o log contém o registro de warning descrevendo a falha de acesso ao armazenamento (critério de aceite 3).
- [x] 7.4 Reativar o banco (`docker compose start db`): confirmar que `/ready` volta a `200` na consulta seguinte, sem reiniciar `app` (critério de aceite 4).
- [x] 7.5 Aplicar `k8s/encontros-tech.yaml` atualizado a um cluster kind (`kind-cluster.yaml`, mesmo procedimento da change anterior) e confirmar as três réplicas do Deployment `encontros-tech-app` chegando a `Ready` via as sondas novas, com `kubectl get pods -n encontros-tech -w`. Executado em cluster `encontros-tech-test` efêmero (criado e removido nesta sessão): `deployment encontros-tech-app` chegou a `3/3` `READY`, uma réplica por zona (`worker`/`worker2`/`worker3`), com `readinessProbe`/`livenessProbe` apontando para `/ready`/`/health` e `timeoutSeconds: 6` confirmados via `kubectl get deployment -o jsonpath`.
