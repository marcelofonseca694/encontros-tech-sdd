# Relatório de validação — grupo 7 (cluster kind real)

Executado em 2026-09-18, contra clusters kind reais criados para esta entrega (`encontros-tech-test`, 4 nós; `encontros-tech-single`, 1 nó). Nenhum item foi inferido do YAML.

## Achados que exigiram correção no manifesto durante a validação

- **Imagem publicada desatualizada.** `marferrs/encontros-tech-pos:11edf50` (tag publicada mais recente) ainda cria tabelas no import de `main.py`, comportamento anterior à separação do `schema_prep.py` (ADR 001). Isso quebra a suposição do manifesto de que o `Job` é a única etapa que toca o schema. Para validar o manifesto — não a publicação da imagem, fora de escopo desta change —, foi construída localmente uma imagem a partir do `src/` atual, tag `31a4721` (hash do commit em `HEAD` no início da validação), e carregada nos clusters de teste via `kind load docker-image`. O manifesto em si não referencia essa tag; ela existiu apenas para os clusters de teste.
- **`initdb` falhava com `capabilities.drop: [ALL]` sobre `emptyDir`.** O container do banco (uid 70) não conseguia `chmod` o diretório de dados porque o `emptyDir` nasce de propriedade do kubelet (root) e `CAP_FOWNER` estava removida. Corrigido com um `initContainer` transitório (`fix-data-dir-ownership`), rodando como root apenas com `CHOWN` adicionada, que ajusta a posse do volume antes do container principal — que mantém o endurecimento de D9 sem alteração. Sem essa correção, a tarefa 2.4 não seria satisfeita (`initdb` nunca completava).

## Resultado por item

| Item | Resultado |
| --- | --- |
| 7.1 | OK — `kind create cluster` com `kind-cluster.yaml` produziu 4 nós `Ready`, 3 zonas distintas (`zone-a/b/c`) nos workers |
| 7.2 | OK — `kind load docker-image` confirmado nos 4 nós via `crictl images`; tag sempre `31a4721`, nunca `latest` |
| 7.3 | OK — `kubectl apply -f` único criou os 9 recursos sem nenhuma criação manual |
| 7.4 | OK — `Job` completou com sucesso após 5 tentativas falhas (banco ainda não aceitava conexões), confirmando `backoffLimit`/`OnFailure` |
| 7.5 | OK — 3 réplicas `Ready`, uma por zona (`worker`=zone-a, `worker2`=zone-b, `worker3`=zone-c) |
| 7.6 | OK — nenhum pod `Pending` no cluster de 3 zonas; sem eventos de recusa por `maxSkew` |
| 7.7 | OK — `port-forward` + `GET /` → `200` com a página renderizada |
| 7.8 | OK — `POST /api/events/` retornou `id` e `edit_token` |
| 7.9 | OK — evento presente em `GET /api/events/` e em `GET /` |
| 7.10 | OK — `PUT /api/events/by-token/<token>` persistiu a edição numa releitura |
| 7.11 | OK — tráfego via `Service` (não via `port-forward`, que fixa um único backend) distribuído entre as 3 réplicas em 20 requisições |
| 7.12 | OK — busca por `search` respondeu corretamente na API e na página |
| 7.13 | OK — pod do banco apagado: banco voltou vazio (`GET /api/events/` → 500), réplicas saíram do `Service` (endpoints vazios), contador de restarts permaneceu 0 |
| 7.14 | OK — `Job` recriado (nome imutável exigiu apagar o `Job` concluído antes de reaplicar) concluiu, réplicas voltaram a atender sem nenhum reinício, evento anterior não existe mais |
| 7.15 | Parcial, com achado registrado — escalar o banco a 0 e voltar **também substitui o pod** (mesmo efeito de 7.13/7.14), o que a redação da tarefa não menciona. O que é diretamente verificável sem contradizer a spec foi confirmado: nenhum reinício das réplicas, nenhum tráfego enquanto o banco esteve fora, e recuperação sem reinício **depois de reexecutar o `Job`** — que é o comportamento que a spec realmente descreve para substituição do pod do banco |
| 7.16 | OK — drenar o primeiro nó reduziu a 2 réplicas disponíveis (a terceira ficou `Pending`, sem outra zona livre); tentar drenar um segundo nó foi bloqueado repetidamente pelo `PodDisruptionBudget` (`Cannot evict pod as it would violate the pod's disruption budget`) até o timeout |
| 7.17 | OK — `rollout restart` concluiu com sucesso; nenhum pod `Pending`; nenhum evento `FailedScheduling` durante o rollout (o único evento desse tipo era residual do teste de drenagem anterior) |
| 7.18 | OK — reaplicação sem mudar a versão não falhou em nenhum recurso; aplicação continuou respondendo `200` |
| 7.19 | OK — `id` reportou uid 1000; escrita na raiz falhou (`Read-only file system`); `/tmp` gravável |
| 7.20 | OK — `DATABASE_URL`/`SECRET_KEY` presentes no ambiente do processo; busca pelos valores de exemplo no histórico da imagem e no tar completo da imagem não encontrou ocorrência |
| 7.21 | OK — `GET /metrics` respondeu `200` sem autenticação, na mesma porta 8000 |
| 7.22 | OK — `Service` do tipo `LoadBalancer` permaneceu com `EXTERNAL-IP <pending>` durante toda a validação (sem `cloud-provider-kind`); validação funcional feita por `port-forward` e por acesso direto ao `Service` de dentro do cluster |
| 7.23 | OK — cluster kind de nó único (`encontros-tech-single`, sem `kind-cluster.yaml`, sem rótulo de zona): as 3 réplicas ficaram `Pending`, evento `FailedScheduling` citando explicitamente "didn't match pod topology spread constraints (missing required label)" — nenhuma se concentrou no único nó |
| 7.25 | Ver seção "Encerramento" abaixo |

## O que não pôde ser verificado neste ambiente, e por quê

- **Atribuição real de `EXTERNAL-IP` pelo provedor de nuvem.** kind não tem controlador de `LoadBalancer` sem `cloud-provider-kind` (não instalado nesta validação, por decisão registrada em D12). O `Service` permanece `<pending>` indefinidamente; isso é limitação do ambiente de teste local, não do manifesto. A distribuição de tráfego entre réplicas prontas — o que o `Service` de fato decide — foi verificada por outro caminho (curl de dentro do cluster contra o `ClusterIP` automático do `Service`).
- **Custo e comportamento de balanceador em nuvem real** (AWS ELB/NLB) — fora do alcance de um cluster kind por definição; não há o que testar localmente.
- **Perda real de uma zona de disponibilidade inteira** (spec, "Perda de uma zona") — kind simula zonas por rótulo, não por falha de infraestrutura real; não há como derrubar fisicamente uma "zona" fictícia. O comportamento equivalente mais próximo verificável localmente — drenar o nó de uma zona — foi coberto por 7.16.

## Encerramento

Ambos os clusters de teste (`encontros-tech-test` e `encontros-tech-single`) foram destruídos ao final desta validação, junto com a imagem local de teste `marferrs/encontros-tech-pos:31a4721`; ver 7.25 em `tasks.md` para a confirmação.
