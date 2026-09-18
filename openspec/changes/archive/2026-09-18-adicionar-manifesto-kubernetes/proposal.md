## Why

Os ADRs 001, 002 e 003 decidiram o ambiente de execução da aplicação — imagem única, cluster Kubernetes, três réplicas em três zonas, banco como carga no próprio cluster — mas nenhum artefato do repositório declara esse ambiente. A aplicação tem imagem distribuível e nenhum lugar declarado onde executar: o mesmo tipo de lacuna que o ADR 002 fechou no plano da decisão permanece aberto no plano do artefato. Sem manifesto, as decisões registradas não são aplicáveis nem verificáveis, e o ADR 003 foi tomado justamente para que o manifesto pudesse ser aplicado a um cluster existente.

## What Changes

- Adiciona o diretório `k8s/` com **um único arquivo YAML multi-documento** que declara o ambiente de execução completo: `Namespace`, `ConfigMap` de configuração não sensível, `Secret` de credenciais, banco PostgreSQL como carga com armazenamento efêmero e seu `Service` interno, `Job` de preparação de schema, `Deployment` da aplicação e seu `Service` de exposição externa, e `PodDisruptionBudget`.
- Declara a topologia decidida no ADR 002: três réplicas fixas, espalhamento topológico por zona com `whenUnsatisfiable: DoNotSchedule`, e orçamento de interrupção com `minAvailable: 2`.
- Declara o banco conforme o ADR 003: carga sem identidade estável, sem volume persistente, endereço de conexão estável por nome de serviço interno.
- Declara a preparação de schema como `Job` concluído antes do rollout das réplicas, com nome derivado de `SERVICE_VERSION` — um `Job` é imutável, e sem nome variável por versão a reaplicação do arquivo falha.
- **Decide a exposição externa, que o ADR 002 deixou explicitamente fora de escopo**: `Service` do tipo `LoadBalancer`, sem anotações específicas de provedor, para não depender de controlador de balanceador que nenhuma decisão declara existir.
- Configura as sondas de ciclo de vida sobre o que existe hoje na aplicação: prontidão por `GET /` e vida por verificação de porta TCP. **Não** usa `/health` e `/ready`, que são documentados no TRD e na PRD correspondente mas **não existem no código**.
- Fornece `SECRET_KEY` e `DATABASE_URL` como `Secret` do Kubernetes, atendendo a pré-condição que os ADRs 001 e 002 declararam bloqueante: segredos fora do código-fonte e fora da imagem pública.
- Aplica endurecimento de pod: execução como usuário não-root (UID 1000, o `appuser` da imagem), sistema de arquivos raiz somente leitura com `emptyDir` em `/tmp`, remoção de capacidades e proibição de escalonamento de privilégio, além de requisições e limites de recursos declarados.

Lacunas conhecidas que esta change registra em vez de resolver:

- **`/metrics` fica público.** O `prometheus-flask-exporter` registra `/metrics` na mesma porta 8000, sem autenticação; o `Service` do tipo `LoadBalancer` publica isso na internet junto com a aplicação, expondo caminhos, contagens, latências e a versão exata da imagem. Risco aceito e documentado, não mitigado.
- **Prontidão imprecisa.** `GET /` não distingue "banco indisponível" de "armazenamento não preparado", distinção que a PRD de health/ready especifica. É substituto funcional até os endpoints existirem.
- **Perda de dados é rotina.** Consequência do ADR 003, não desta change: cada substituição do pod do banco apaga tudo e exige reexecução do `Job`.
- **Nós precisam de rótulo de zona.** Com `DoNotSchedule` sobre `topology.kubernetes.io/zone`, o escalonador exclui nós sem esse rótulo — em cluster local, as réplicas ficam pendentes até que os nós sejam rotulados.

## Capabilities

### New Capabilities
- `implantacao-em-kubernetes`: declara o ambiente de execução da aplicação como artefato versionado no repositório — o que é declarado, quais garantias de topologia e disponibilidade o manifesto sustenta, como o ciclo de vida das réplicas é sinalizado ao orquestrador, como os segredos entram no ambiente sem estar na imagem, e qual superfície fica exposta externamente.

### Modified Capabilities
Nenhuma. As capacidades existentes descrevem comportamento da aplicação e do seu empacotamento, e nenhum deles muda: `empacotamento-em-container` continua descrevendo a mesma imagem, `inicializacao-da-aplicacao` os mesmos requisitos de ambiente, `preparacao-de-schema` a mesma rotina com o mesmo contrato de código de saída, e `ambiente-de-desenvolvimento` o mesmo ambiente local por Compose. O que esta change acrescenta é o ambiente onde essa aplicação executa, não uma alteração no que ela faz.

## Impact

- **Novo:** diretório `k8s/` com um arquivo YAML, e `kind-cluster.yaml` na raiz — configuração do cluster de validação, fora de `k8s/`, que permanece com arquivo único. Nenhum código de aplicação é alterado.
- **Validação:** a entrega se encerra com um grupo de tarefas que cria um cluster kind de três workers rotulados por zona, aplica o manifesto, exercita a aplicação de ponta a ponta e comprova os comportamentos de ciclo de vida decididos nos ADRs 002 e 003. Inspeção de YAML não conta como verificação.
- **Documentação:** `docs/trd.md` precisa ser corrigido em dois pontos que esta change torna falsos — a afirmação de que o cluster "consome `/health` e `/ready` como probes", e a estrutura de pastas, que passa a incluir `k8s/`. As rotas `/health`/`/ready` e o módulo `routers.health_router` seguem documentados no TRD sem existirem no código; esta change não os implementa e não remove essa inexatidão, apenas deixa de depender dela.
- **Dependências externas:** exige imagem já publicada em `marferrs/encontros-tech-pos` com tag fixa correspondente a `SERVICE_VERSION` (o ADR 001 proíbe tag móvel, logo `latest` não é aceitável no manifesto).
- **Pré-condições de ambiente:** nós rotulados com `topology.kubernetes.io/zone`; valores reais do `Secret` fornecidos fora do repositório; em cluster local, algo que atribua endereço externo ao `LoadBalancer` (`cloud-provider-kind` ou equivalente), sem o que o serviço fica alcançável apenas pela porta de nó.
- **Custo:** em provedor de nuvem, `type: LoadBalancer` provisiona balanceador — custo recorrente novo, não previsto em nenhum ADR.
- **Não incluído:** infraestrutura como código do cluster e dos nós, entrega contínua, publicação da imagem, `Ingress`, política de rede e implementação de `/health` e `/ready`.
