## Context

Ver `proposal.md` — Why, para a motivação, e `specs/implantacao-em-kubernetes/spec.md` para os requisitos. O que este documento acrescenta é o estado concreto que restringe as escolhas:

- **A aplicação não expõe sinais de ciclo de vida.** `/health` e `/ready` estão documentados no TRD e especificados na PRD correspondente, mas não existem em `src/` — não há `routers/health_router.py`, e `main.py` não registra blueprint algum além de `api` e `pages`. As sondas precisam ser construídas sobre o que existe.
- **`GET /` consulta o banco.** `page_router.list_events_page` lista eventos, logo a rota exercita a dependência — é a única rota existente que serve como indicador de prontidão real.
- **`GET /metrics` existe e é público.** Verificado na própria imagem: `prometheus-flask-exporter` registra `path='/metrics'` com `export_defaults=True`, na mesma porta 8000, sem autenticação.
- **`main.py:26` escreve em disco no import.** `os.makedirs(settings.PROMETHEUS_MULTIPROC_DIR, exist_ok=True)`, com padrão `/tmp/prometheus_multiproc`.
- **A imagem executa como UID 1000.** Verificado: `uid=1000(appuser) gid=1000(appuser)`.
- **A imagem já é publicada** em `marferrs/encontros-tech-pos`, com tag fixa e sem tag móvel aceitável (ADR 001).
- **Os clusters disponíveis são locais** (kind), sem rótulo de zona nos nós e sem controlador que atribua endereço externo.

## Goals / Non-Goals

**Goals:**

- Um artefato aplicável hoje, a um cluster real, exercitável de ponta a ponta — critério que motivou o ADR 003.
- Sustentar as garantias de topologia e disponibilidade do ADR 002 sem depender de infraestrutura que não existe.
- Endurecimento de pod conforme prática corrente, sem exigir alteração de código da aplicação.

**Non-Goals:**

- Implementar `/health` e `/ready`. As sondas são construídas sobre `GET /` e sobre a porta TCP, e serão trocadas quando os endpoints existirem.
- Mover `/metrics` para outra porta ou protegê-lo. Exigiria mudança de código.
- Balanceador específico de provedor, `Ingress`, política de rede, autoescalonamento e provisionamento de cluster/nós.

## Decisions

### D1 — Arquivo único multi-documento em `k8s/`

Todos os recursos em um só arquivo, aplicado por `kubectl apply -f k8s/<arquivo>.yaml`.

*Alternativas:* um arquivo por recurso (mais navegável, mas exige ordem de aplicação combinada ou `apply -f k8s/`); Helm (resolveria parametrização e ordenação por hooks, ao custo de introduzir ferramenta que o projeto não usa); Kustomize (overlays sem motor de template, mesma objeção menor). O projeto não tem linter, lockfile nem gerenciador de manifesto — arquivo único é coerente com essa economia de ferramenta.

*Consequência de ordenação:* `kubectl apply` de um arquivo aplica os documentos na ordem em que aparecem, sem reordenar por dependência. O `Namespace` é, por isso, o **primeiro documento**, e todos os demais recursos declaram `namespace` explicitamente.

### D2 — A ordem entre preparação de schema e réplicas não é imposta; é absorvida pela prontidão

`Job` e `Deployment` nascem no mesmo `apply` e iniciam concorrentemente. A garantia de que nenhuma réplica atenda antes do armazenamento existir **não** vem de ordenação, e sim da sonda de prontidão: sem tabela, `GET /` falha, a réplica não entra no balanceamento.

*Alternativas:* `initContainer` que aguarda o schema (duplicaria a verificação que a prontidão já faz, e prenderia o start do pod a uma lógica nova); hooks de pré-instalação (descartados junto com Helm em D1); aplicar em dois comandos (contraria o requisito de um comando).

Esse desenho tem um ganho: ele também cobre o caso de **perda** do schema, que a ordenação não cobriria — quando o pod do banco é substituído (rotina, pelo ADR 003), as réplicas saem do balanceamento sozinhas e voltam quando o `Job` é reexecutado.

O `Job` alcança o banco por tentativa e erro, não por espera declarada: `restartPolicy: OnFailure` com `backoffLimit` folgado substitui o `depends_on: service_healthy` que o Compose oferece e o Kubernetes não tem.

### D3 — Prontidão por `GET /`; vida por verificação de porta TCP

`readinessProbe: httpGet / :8000` e `livenessProbe: tcpSocket :8000`.

*Por que não `GET /` nas duas:* queda de banco faria a sonda de vida falhar nas três réplicas simultaneamente, e o orquestrador reiniciaria todas, nas três zonas, repetidamente — transformando falha de dependência em indisponibilidade própria, exatamente o que a PRD de health/ready registra como invariante a não violar.

*Por que não implementar `/health` e `/ready` primeiro:* decisão do usuário nesta sessão; fica como pré-requisito de aplicação, não desta change.

*Temporizações:* período de 10 s nas duas sondas (premissa da PRD), `timeoutSeconds: 3` na prontidão (limite de 3 s da PRD), `failureThreshold: 3`. `startupProbe` não é declarada: a aplicação inicializa rápido e a PRD já registra que a distinção "iniciando" vs "não pronto" não muda decisão alguma hoje.

### D4 — `Service` do tipo `LoadBalancer`, sem anotações de provedor

*Alternativas:* `ClusterIP` (não expõe — era a escolha anterior, revista pelo usuário); `NodePort` (expõe por porta de nó, endereço não gerenciado); `Ingress` (exige controlador que nenhuma decisão declara existir); `LoadBalancer` com anotação de NLB (exige o AWS Load Balancer Controller instalado, idem).

Sem anotação, o manifesto permanece portátil: em cluster local com `cloud-provider-kind` recebe endereço; em EKS, o provedor em árvore cria um balanceador clássico. A anotação de NLB é adição de uma linha quando houver controlador.

### D5 — Banco como carga sem identidade estável, com `strategy: Recreate`

Conforme ADR 003: sem volume, identidade estável não preserva nada. A estratégia de substituição é **`Recreate`**, não rolante: com armazenamento efêmero, dois pods coexistindo brevemente teriam **dados diferentes**, e o `Service` distribuiria conexões entre bancos divergentes. `Recreate` troca disponibilidade momentânea por consistência — e a indisponibilidade é absorvida pela prontidão das réplicas.

Armazenamento por `emptyDir` em `/var/lib/postgresql/data`.

### D6 — Nome do `Job` derivado de `SERVICE_VERSION`, substituído à mão

`Job` é imutável: reaplicar o mesmo nome falha. O nome carrega a versão (`schema-prep-<versão>`), e a substituição é manual — sem motor de template (D1), e coerente com a publicação manual de imagem já estabelecida pelo ADR 001. `ttlSecondsAfterFinished` recolhe os `Job` concluídos, para que o histórico não acumule indefinidamente.

### D7 — `Secret` presente no arquivo, com valores de exemplo a substituir

Tensão real entre dois requisitos da spec: "aplicável por um comando" e "o artefato versionado não contém valores reais". Resolução: o `Secret` existe no arquivo com valores **evidentemente de exemplo**, documentados como obrigatórios de substituir antes de qualquer uso que não seja local.

*Alternativas:* não declarar o `Secret` e exigir `kubectl create secret` antes (quebra o comando único); declarar com valores vazios (a aplicação falharia de forma obscura, sem ganho de segurança real).

Registro honesto do que isso significa: aplicar o arquivo sem substituir os valores executa a aplicação com `SECRET_KEY` conhecida e publicada. Como não há autenticação, sessão nem usuário no modelo de dados, o impacto prático hoje é baixo — mas é a mesma classe de problema que o ADR 001 registrou como consequência negativa, e não desaparece por estar em outro arquivo.

### D8 — `maxSurge: 0` e `maxUnavailable: 1` no rollout da aplicação

Não é preferência: com `topologySpreadConstraints` de `maxSkew: 1` e `whenUnsatisfiable: DoNotSchedule` sobre três zonas com três réplicas, um pod excedente teria de ir para uma zona que já tem uma réplica, levando a assimetria a 2 e sendo **recusado pelo escalonador** — o rollout ficaria preso com um pod pendente. Substituição sem excedente é a única compatível com a topologia decidida.

Durante o rollout há janela com duas réplicas, compatível com `minAvailable: 2` do orçamento de interrupção.

### D9 — Endurecimento: aplicação restritiva, banco com exceção documentada

Aplicação: `runAsNonRoot: true`, `runAsUser`/`runAsGroup: 1000` (UID verificado na imagem), `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`, `readOnlyRootFilesystem: true` e `automountServiceAccountToken: false` — a aplicação não fala com a API do cluster.

`readOnlyRootFilesystem: true` **quebraria o start** por causa de `main.py:26`, que cria `/tmp/prometheus_multiproc` no import. Um `emptyDir` montado em `/tmp` resolve sem tocar código, e `emptyDir` não é volume persistente reivindicado — permanece dentro da restrição de não usar PVC.

Banco: mantém sistema de arquivos raiz gravável, como **exceção explícita**. A imagem oficial do PostgreSQL escreve em vários caminhos próprios durante `initdb`, e persegui-los com montagens aumentaria a fragilidade sem ganho proporcional. Executa como usuário não-root da própria imagem, com as demais restrições aplicadas.

### D10 — Requisições e limites de recursos

Nenhum RNF declara desempenho. O critério é o nó de 2 vCPU e 2 GiB do ADR 002, com uma réplica por nó e agentes de nível de nó consumindo parte fixa.

| Carga | `requests` | `limits` |
| --- | --- | --- |
| Aplicação | 100m CPU, 128Mi | memória 256Mi, **sem limite de CPU** |
| Banco | 100m CPU, 256Mi | memória 512Mi, **sem limite de CPU** |
| `Job` de schema | 50m CPU, 128Mi | memória 256Mi |

Limite de memória existe para conter vizinho ruidoso; limite de CPU é omitido deliberadamente, porque estrangularia um servidor síncrono de processo único justamente sob rajada, sem proteger ninguém em um nó que executa uma réplica.

### D11 — Rótulos e referência de imagem

Rótulos recomendados pelo próprio Kubernetes: `app.kubernetes.io/name`, `instance`, `version`, `component`, `part-of`, `managed-by`. Seletores usam apenas o subconjunto estável (`name` + `component`), nunca `version`, que muda a cada publicação.

Imagem por `marferrs/encontros-tech-pos:<SERVICE_VERSION>`, com `imagePullPolicy: IfNotPresent` — a tag é imutável por decisão do ADR 001, logo repuxar a cada start não tem função.

### D12 — Ambiente de validação em kind, com três workers rotulados por zona

A entrega não é considerada concluída por inspeção do YAML: ela é validada contra um cluster Kubernetes em execução, criado com kind (v0.20.0, já instalado na máquina).

*Por que três workers e não um nó:* com `maxSkew: 1` e `DoNotSchedule` sobre `topology.kubernetes.io/zone`, um cluster de nó único deixaria duas das três réplicas permanentemente `Pending` — o ambiente não subiria, e a validação funcional seria impossível. O kind aceita `labels` por nó no próprio arquivo de configuração, então as três zonas fictícias são declaradas na criação do cluster, sem passo manual de rotulagem.

*Onde vive a configuração do cluster:* `kind-cluster.yaml` na **raiz** do repositório, e não em `k8s/`, que permanece com um único arquivo. O paralelo é o `docker-compose.yml`: os dois declaram como obter um ambiente local, e nenhum dos dois é manifesto da aplicação.

*Como a exposição externa é validada:* por `kubectl port-forward` sobre o `Service`. `cloud-provider-kind` não está instalado, e sem ele o `Service` do tipo `LoadBalancer` nunca recebe `EXTERNAL-IP` em kind. O encaminhamento de porta exercita seleção de endpoints, prontidão e distribuição entre réplicas — tudo o que o `Service` decide —, deixando de fora apenas a atribuição de endereço pelo provedor, que é comportamento do cluster e não do manifesto. Isso fica registrado como limitação verificada, não como item aprovado.

*Alternativas:* instalar `cloud-provider-kind` (validaria o caminho completo, ao custo de uma ferramenta nova e de um passo sujeito a rede); fixar `nodePort` no `Service` e mapear porta do host no kind (daria acesso direto por `localhost`, mas contaminaria o manifesto de produção com um valor existente apenas para viabilizar teste local).

*O caso negativo também é exercitado:* um cluster kind de nó único, sem rótulos de zona, serve para comprovar que as réplicas ficam `Pending` em vez de se concentrarem — o cenário que a spec declara e que só é observável num cluster sem zonas.

## Risks / Trade-offs

- **Sonda de prontidão poluindo a observabilidade de negócio** → `GET /` a cada 10 s, em três réplicas, são ~18 requisições por minuto contabilizadas como visualização de página real, com métricas e log de requisição inclusos. A PRD de health/ready trata isso como premissa a evitar (P16); aqui ele é assumido. Desaparece quando as sondas passarem a apontar para endpoints dedicados.
- **Prontidão mais custosa que uma verificação de saúde** → `GET /` renderiza a listagem completa, com consulta ao banco, a cada 10 s por réplica. Aceitável na escala atual; é desperdício, não risco.
- **Prontidão imprecisa** → `GET /` não distingue banco indisponível de armazenamento ausente; as duas condições produzem o mesmo sinal. Diagnóstico depende de log, não da sonda.
- **`/metrics` público** → exposto pelo `LoadBalancer`, sem autenticação, revelando rotas, contagens, latências e a versão exata da imagem. Aceito e registrado; mitigação exige código ou `Ingress`.
- **`SECRET_KEY` de exemplo aplicada sem substituição** → mitigação é documental (D7), não técnica.
- **Réplicas pendentes em cluster sem rótulo de zona** → efeito deliberado de `DoNotSchedule`. Mitigação: rotular os nós antes do `apply`, tarefa incluída na entrega.
- **`LoadBalancer` sem endereço em cluster local** → fica `<pending>` sem `cloud-provider-kind` ou equivalente; o serviço permanece alcançável pela porta de nó que o tipo aloca, e a validação funcional é feita por encaminhamento de porta (D12). A atribuição de endereço externo real permanece **não verificada** nesta entrega.
- **Baixar a imagem de nó do kind na primeira criação de cluster** → não há `kindest/node` em cache local; criar o cluster de teste depende de rede e baixa cerca de 1 GB. Mitigação: nenhuma técnica; é custo da primeira execução.
- **Perda total de dados a cada substituição do pod do banco** → consequência aceita no ADR 003. Aqui, a mitigação é operacional: reexecutar o `Job` de preparação, sem o que as réplicas permanecem vivas e fora do balanceamento.
- **Custo de balanceador em provedor de nuvem** → nenhum ADR previu; visível na primeira fatura, não no manifesto.

## Migration Plan

Não há ambiente anterior a migrar — o ambiente passa a existir. Sequência de primeira aplicação:

1. Rotular os nós com `topology.kubernetes.io/zone` (em cluster local; em provedor gerenciado o rótulo já existe).
2. Substituir os valores do `Secret` e a versão nas referências de imagem e no nome do `Job`.
3. `kubectl apply -f` do arquivo único.
4. Verificar a conclusão do `Job` de preparação, depois as três réplicas prontas e distribuídas, depois o endereço externo atribuído.

**Rollback:** reaplicar a versão anterior do arquivo, com a tag de imagem anterior e o nome de `Job` correspondente. Não há dado durável a preservar (ADR 003), então o rollback não tem etapa de dados. Remover o ambiente inteiro é apagar o `Namespace`.

## Open Questions

- Trocar as sondas para `/health` e `/ready` quando os endpoints existirem — resolvível depois, sem alterar spec, abordagem ou tarefas desta change.
- Anotar o `Service` para NLB, ou migrar para `Ingress`, quando houver controlador de balanceador no cluster.
- Fixar `max_connections` no container de banco: hoje o teto deixou de vir da classe de instância gerenciada (ADR 003) e passou a ser parâmetro ajustável, sem valor declarado. Só importa acima de sete réplicas.
