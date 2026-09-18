## 1. Estrutura e configuração base

- [x] 1.1 Criar `k8s/encontros-tech.yaml` com o documento de `Namespace` como **primeiro** documento do arquivo, e verificar que `kubectl apply -f k8s/encontros-tech.yaml --dry-run=client` não reporta erro
- [x] 1.2 Adicionar o `ConfigMap` com a configuração não sensível (`APP_TITLE`, `DEBUG`, `HOST`, `PORT`, `SERVICE_NAME`, `LOG_LEVEL`, `LOG_FORMAT`), sem `SERVICE_VERSION` — que vem fixada da imagem —, e verificar que nenhum valor sensível está presente
- [x] 1.3 Adicionar o `Secret` com `SECRET_KEY` e `DATABASE_URL` em valores evidentemente de exemplo (D7), com comentário no próprio arquivo declarando a obrigação de substituí-los, e verificar que `DATABASE_URL` aponta para o nome de serviço interno do banco
- [x] 1.4 Aplicar os rótulos recomendados (`app.kubernetes.io/name`, `instance`, `version`, `component`, `part-of`, `managed-by`) a todos os recursos, mantendo seletores restritos a `name` + `component`, e verificar que nenhum seletor referencia `version`

## 2. Banco de dados no cluster

- [x] 2.1 Adicionar a carga do PostgreSQL com `strategy: Recreate`, uma réplica, armazenamento por `emptyDir` em `/var/lib/postgresql/data` e credenciais lidas do `Secret`, e verificar que nenhum `PersistentVolumeClaim` existe no arquivo (`grep -c PersistentVolumeClaim` retorna 0)
- [x] 2.2 Adicionar `readinessProbe` e `livenessProbe` do banco por `pg_isready`, e verificar que o pod só é reportado pronto quando aceita conexões
- [x] 2.3 Adicionar o `Service` interno do banco (`ClusterIP`) e verificar que o nome de serviço resolve de dentro do cluster e corresponde exatamente ao host usado na `DATABASE_URL` do `Secret`
- [x] 2.4 Declarar `securityContext` e recursos do banco conforme D9 e D10 (não-root, sem escalonamento de privilégio, sistema de arquivos raiz gravável como exceção documentada em comentário), e verificar que o pod inicia e completa `initdb`

## 3. Preparação de schema

- [x] 3.1 Adicionar o `Job` de preparação com nome derivado de `SERVICE_VERSION` (`schema-prep-<versão>`), `restartPolicy: OnFailure`, `backoffLimit` folgado e `ttlSecondsAfterFinished`, e verificar que o `Job` conclui com sucesso mesmo quando aplicado antes de o banco aceitar conexões (as tentativas iniciais falham e uma posterior conclui)
- [x] 3.2 Verificar que o `Job` executa a mesma imagem da aplicação com o comando `python3 schema_prep.py`, e que seu código de saída é o que determina sucesso ou falha do `Job`
- [x] 3.3 Declarar `securityContext` e recursos do `Job` conforme D9 e D10, incluindo `emptyDir` em `/tmp`, e verificar que a execução conclui com o sistema de arquivos raiz somente leitura

## 4. Aplicação

- [x] 4.1 Adicionar o `Deployment` da aplicação com três réplicas, imagem por tag fixa `marferrs/encontros-tech-pos:<SERVICE_VERSION>` e `imagePullPolicy: IfNotPresent`, e verificar que o arquivo não contém a tag `latest` em nenhum lugar
- [x] 4.2 Declarar `envFrom` apontando para o `ConfigMap` e para o `Secret`, e verificar numa réplica em execução que `DATABASE_URL` e `SECRET_KEY` chegaram do ambiente e não da imagem
- [x] 4.3 Declarar `topologySpreadConstraints` com `maxSkew: 1`, `topologyKey: topology.kubernetes.io/zone` e `whenUnsatisfiable: DoNotSchedule`, e verificar em cluster de três zonas que há exatamente uma réplica por zona
- [x] 4.4 Declarar `strategy: RollingUpdate` com `maxSurge: 0` e `maxUnavailable: 1` (D8), e verificar que um rollout conclui sem nenhum pod ficando `Pending` por recusa do escalonador
- [x] 4.5 Declarar `readinessProbe` por `httpGet` em `/` na porta 8000, com período de 10 s, `timeoutSeconds: 3` e `failureThreshold: 3`, e verificar que a réplica só entra no balanceamento quando `GET /` responde com sucesso
- [x] 4.6 Declarar `livenessProbe` por `tcpSocket` na porta 8000 e verificar que, com o banco parado, nenhuma réplica é reiniciada (contador de restarts permanece inalterado) embora todas saiam do balanceamento
- [x] 4.7 Declarar `securityContext` completo conforme D9 (`runAsNonRoot`, UID/GID 1000, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`, `readOnlyRootFilesystem: true`) e `automountServiceAccountToken: false`, e verificar que o pod inicia — o que exige o `emptyDir` da tarefa 4.8
- [x] 4.8 Montar `emptyDir` em `/tmp` e verificar que a criação de `/tmp/prometheus_multiproc` por `main.py:26` ocorre sem erro com o sistema de arquivos raiz somente leitura
- [x] 4.9 Declarar requisições e limites de recursos conforme D10, e verificar que o pod é agendado e que nenhum limite de CPU está declarado

## 5. Exposição e disponibilidade

- [x] 5.1 Adicionar o `Service` da aplicação com `type: LoadBalancer`, porta única e sem anotações de provedor, e verificar que o tráfego externo alcança a aplicação e é distribuído entre as réplicas prontas
- [x] 5.2 Adicionar o `PodDisruptionBudget` com `minAvailable: 2` e verificar, drenando um nó, que a operação respeita o limite em vez de reduzir a disponibilidade abaixo de duas réplicas
- [x] 5.3 Registrar em comentário no próprio arquivo que `/metrics` fica publicamente alcançável pela porta exposta, e verificar que a advertência está presente junto à declaração do `Service`

## 6. Documentação

- [x] 6.1 Corrigir em `docs/trd.md` a afirmação de que o cluster consome `/health` e `/ready` como probes, substituindo pelas sondas efetivamente declaradas, e verificar que nenhuma outra passagem do TRD contradiz o manifesto
- [x] 6.2 Incluir `k8s/` e `kind-cluster.yaml` na estrutura de pastas dominante do `docs/trd.md` e verificar que a descrição corresponde ao conteúdo do repositório

## 7. Validação em cluster Kubernetes real (kind)

Grupo final da entrega: nada aqui é simulado ou inferido do YAML. Cada verificação é feita contra um cluster Kubernetes em execução, e a entrega não está concluída enquanto qualquer item deste grupo falhar.

### Preparar o ambiente de teste

- [x] 7.1 Criar `kind-cluster.yaml` na raiz do repositório com um nó de controle e **três nós worker**, cada worker declarando `labels: topology.kubernetes.io/zone` com um valor distinto, e verificar que `kind create cluster --name encontros-tech-test --config kind-cluster.yaml` conclui e que `kubectl get nodes -L topology.kubernetes.io/zone` lista quatro nós `Ready` com as três zonas distintas presentes
- [x] 7.2 Disponibilizar a imagem da aplicação no cluster por `kind load docker-image marferrs/encontros-tech-pos:<versão> --name encontros-tech-test`, e verificar que a tag carregada é exatamente a referenciada no manifesto (nunca `latest`)

### Aplicar e observar a subida

- [x] 7.3 Aplicar o manifesto inteiro num cluster vazio com **um único comando** e verificar que nenhum recurso precisou ser criado à mão para o ambiente funcionar
- [x] 7.4 Verificar que o `Job` de preparação de schema conclui com sucesso (`kubectl get job` reporta conclusão), inclusive tendo iniciado antes de o banco aceitar conexões — as tentativas iniciais falham e uma posterior conclui
- [x] 7.5 Verificar que as três réplicas alcançam `Ready` e que `kubectl get pods -o wide` mostra **exatamente uma réplica por zona**, confirmando o espalhamento topológico
- [x] 7.6 Verificar que nenhum pod permanece `Pending` e que `kubectl describe` não reporta recusa do escalonador por violação de `maxSkew`

### Provar que a aplicação funciona

- [x] 7.7 Abrir `kubectl port-forward` sobre o `Service` da aplicação e verificar que `GET /` responde `200` com a página de listagem renderizada
- [x] 7.8 Criar um evento por `POST /api/events/` e verificar que a resposta traz o identificador e o `edit_token`
- [x] 7.9 Verificar que o evento criado aparece em `GET /api/events/` e na página `GET /`, confirmando que a escrita chegou ao banco que executa no cluster
- [x] 7.10 Editar o evento por `PUT /api/events/by-token/<edit_token>` e verificar que a alteração persiste numa nova leitura
- [x] 7.11 Verificar que `GET /` atendido repetidamente é servido por mais de uma réplica — pelo nome de host injetado na página ou pelos logs das réplicas —, confirmando distribuição de tráfego
- [x] 7.12 Verificar que a busca por `search` na página e na API responde corretamente contra os dados criados, confirmando que o schema preparado pelo `Job` atende as consultas de negócio

### Provar os comportamentos de ciclo de vida decididos

- [x] 7.13 Apagar o pod do banco e verificar o comportamento do ADR 003: o banco volta **vazio**, as três réplicas deixam de receber tráfego, e o contador de restarts das réplicas permanece **inalterado** — a falha de dependência não virou reinício
- [x] 7.14 Reexecutar o `Job` de preparação após a substituição do banco e verificar que as três réplicas voltam a atender **sem nenhum reinício**, e que os eventos criados antes não existem mais
- [x] 7.15 Escalar o banco para zero réplicas e verificar que nenhuma réplica da aplicação é reiniciada e nenhuma recebe tráfego; restaurá-lo e verificar que todas voltam a atender sem reinício, comprovando que a verificação prévia do pool descarta conexões mortas — **achado**: escalar a 0 e voltar recria o pod do banco (mesmo `emptyDir` novo do ADR 003), apagando o schema como em 7.13; a API respondeu `500` até o `Job` ser reexecutado (mesma mecânica de 7.14). O que era diretamente verificável sem contradizer o requisito "Substituição do pod do banco" do spec (nenhuma réplica reiniciada; nenhuma recebe tráfego enquanto o banco está fora) foi confirmado, e a recuperação sem reinício após reexecutar o `Job` também foi confirmada — provando `pool_pre_ping` uma vez que o schema volta a existir
- [x] 7.16 Drenar um nó que executa uma réplica e verificar que o orçamento de interrupção mantém ao menos duas réplicas disponíveis, bloqueando a operação enquanto isso não for possível
- [x] 7.17 Disparar um novo rollout e verificar que ele conclui sem nenhum pod `Pending`, confirmando que `maxSurge: 0` é compatível com o espalhamento por zona
- [x] 7.18 Reaplicar o manifesto sem alterar a versão e verificar que a aplicação segue atendendo e que nenhuma etapa falha por recurso já existente

### Provar o endurecimento e registrar limites

- [x] 7.19 Verificar dentro de uma réplica em execução que `id` reporta UID 1000, que a escrita na raiz do sistema de arquivos falha, e que `/tmp` é gravável — comprovando `readOnlyRootFilesystem` com `emptyDir`
- [x] 7.20 Verificar que `SECRET_KEY` e `DATABASE_URL` chegaram do ambiente, e que nenhum dos dois valores existe em qualquer camada da imagem
- [x] 7.21 Verificar que `GET /metrics` responde pela mesma porta exposta, sem autenticação, confirmando por observação a lacuna que a proposta registra em vez de presumir privacidade
- [x] 7.22 Verificar que o `Service` do tipo `LoadBalancer` permanece com `EXTERNAL-IP` em `<pending>` neste cluster, registrando que a atribuição de endereço externo real não é verificável sem `cloud-provider-kind` e que a validação funcional foi feita por encaminhamento de porta
- [x] 7.23 Aplicar o manifesto num cluster kind de nó único, sem rótulos de zona, e verificar que as réplicas permanecem `Pending` em vez de se concentrarem numa zona, comprovando o efeito deliberado de `DoNotSchedule`

### Encerrar

- [x] 7.24 Registrar o resultado de cada verificação deste grupo, indicando explicitamente o que não pôde ser verificado no ambiente local e por quê
- [x] 7.25 Destruir os clusters de teste (`kind delete cluster --name encontros-tech-test` e o de nó único) e verificar que nenhum recurso do teste permanece na máquina
