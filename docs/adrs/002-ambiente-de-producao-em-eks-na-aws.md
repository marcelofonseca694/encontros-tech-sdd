---
adr_number: "002"
status: aceito
created: 2026-09-15
supersedes: ""
superseded_by: ""
---

# ADR 002: Executar a aplicação em cluster EKS dedicado na AWS, com o banco de dados em serviço gerenciado

## Contexto

O ADR 001 estabeleceu o container como unidade de empacotamento e execução, e registrou explicitamente que a definição de orquestração fora do Docker permanecia fora do seu escopo. O projeto tem, hoje, um artefato distribuível e nenhum lugar declarado onde ele execute: não existe ambiente de produção definido, nem provedor, nem serviço, nem topologia.

A aplicação é uma aplicação web sem estado próprio. Toda a informação que precisa sobreviver a um reinício está no banco de dados relacional, e a única credencial de autorização viaja no próprio recurso. Não há sessão em memória, fila, cache nem processamento em segundo plano. Isso significa que qualquer número de cópias do processo é intercambiável, e que a disponibilidade do serviço é, na prática, a disponibilidade do banco de dados.

O banco, por sua vez, é descrito no documento técnico do projeto como dependência externa cujo dono não está definido. Ele existe em desenvolvimento como container ao lado da aplicação, orquestrado pelo Compose, conforme o ADR 001. Em produção, não existe em lugar nenhum.

Nenhum requisito não-funcional está declarado: desempenho, disponibilidade e escalabilidade constam como não definidos. A consequência é que o dimensionamento desta decisão não pode ser justificado por carga — não há carga conhecida a atender. Ele precisa de outro critério, e o critério adotado aqui é o menor arranjo que ainda tolera a perda de uma zona de disponibilidade sem indisponibilidade percebida.

As forças em tensão são três. A primeira é **padrão organizacional contra superfície operacional**: a organização tem Kubernetes como padrão e competência instalada para operá-lo, enquanto a aplicação é pequena o bastante para que plataformas de menor superfície fossem mais baratas e exigissem menos manutenção. A segunda é **disponibilidade contra partes móveis**: tolerar a perda de uma zona exige redundância nas duas camadas, e cada camada redundante é custo recorrente e mais coisa para falhar. A terceira é **fidelidade entre ambientes contra responsabilidade sobre o estado**: o ADR 001 elegeu a fidelidade entre desenvolvimento e produção como força dominante, e manter o banco como container preservaria essa simetria — ao preço de transferir backup, recuperação e substituição de instância para dentro do cluster, onde nada disso existe por padrão.

A decisão é tomada agora porque o pré-requisito que a bloqueava foi cumprido pelo ADR 001, e porque um artefato sem destino declarado não é um ambiente de produção.

## Alternativas Consideradas

- **Serviço de orquestração proprietário do provedor** — teria menor superfície operacional, integração nativa com o restante da nuvem e nenhum custo de plano de controle; em contrapartida, diverge do padrão de orquestração já adotado pela organização, criando uma segunda cadeia de ferramentas, um segundo modelo mental e um runbook paralelo mantido apenas por este projeto.

- **Modo de compute sem gestão de nós** — eliminaria o provisionamento de instâncias e transferiria o ciclo de vida do sistema operacional para o provedor, e nesta escala custaria menos do que nós dedicados, por cobrar apenas a capacidade que cada réplica declara. Porém não executa cargas de nível de nó, o que inviabiliza os agentes de coleta e de segurança previstos para o ambiente, e retira o controle sobre colocação e o acesso à instância para diagnóstico.

- **Banco de dados como container dentro do cluster** — preservaria a simetria com o ambiente de desenvolvimento, que é a força dominante do ADR 001, e dispensaria um serviço adicional. Em troca, o volume de bloco é de zona única e de anexação exclusiva: prende a carga a uma zona, obriga estratégia de substituição com indisponibilidade a cada atualização, e faz de backup, recuperação a ponto no tempo e substituição de instância responsabilidades que passariam a não existir por padrão. A perda do volume seria perda definitiva dos dados.

- **Redundância do banco por réplica de leitura** — custa praticamente o mesmo que a réplica síncrona de contingência; entretanto não oferece failover automático, exige promoção manual e irreversível, tem como perda de dados o atraso da replicação e altera o endereço de conexão, obrigando rotação de configuração e reinício de todas as réplicas da aplicação. Soma-se que a camada de acesso a dados mantém uma conexão única, sem separação entre leitura e escrita, de modo que a réplica também não aliviaria carga alguma.

- **Instâncias de porte inferior ao escolhido** — reduziriam o custo dos nós; porém o teto de endereços de rede por instância e a reserva fixa do agente de nó consomem a maior parte da capacidade dos perfis menores, deixando pouco espaço para a própria aplicação. O limite não decorre da carga da aplicação, e sim do custo fixo da plataforma sobre cada nó.

- **Família de processador de melhor relação entre preço e desempenho** — reduziria o custo dos nós em cerca de um quinto; entretanto a imagem publicada serve uma única arquitetura, conforme o ADR 001, e adotá-la exigiria reabrir aquela decisão para produzir imagem de múltiplas arquiteturas.

- **Capacidade sob demanda para todos os nós** — eliminaria interrupções involuntárias de instância; em contrapartida custa várias vezes mais para uma carga sem estado, que é exatamente o caso em que a interrupção é absorvida por reescalonamento sem perda.

- **Múltiplos processos de trabalho por container** — aumentaria a vazão por réplica sem aumentar o número de réplicas; porém multiplica o número de conexões abertas contra o banco, cujo teto deriva da memória da instância, e mantém a contabilização de métricas fragmentada por processo, problema já registrado como consequência do ADR 001.

## Decisão

Adotamos a AWS como provedor de nuvem, decorrência da parceria já existente, e o EKS como serviço de execução da aplicação, em **cluster dedicado a este projeto**.

O compute é provido por **grupo de nós gerenciado**, e não pelo modo sem gestão de nós, porque o ambiente prevê agentes executados em nível de nó — condição que o modo alternativo não atende. Não há segregação em múltiplos grupos: como nenhuma carga com estado permanece no cluster, não há o que segregar.

O perfil de nó é o menor que ainda comporta o custo fixo da plataforma acima de si: dois núcleos e dois gigabytes de memória, em família de uso geral com capacidade expansível, declarada junto a equivalentes de outras famílias para ampliar os conjuntos de capacidade disponíveis. A arquitetura permanece a mesma da imagem publicada pelo ADR 001. A capacidade é **interruptível**, escolha que a ausência de estado na aplicação torna segura e que reduz substancialmente o custo dos nós.

A topologia é de **três nós distribuídos em três zonas de disponibilidade**, com mínimo e desejado iguais a três e teto de seis, reservado à substituição de nós durante atualização. A aplicação executa em **três réplicas fixas, uma por zona**, garantidas por restrição de espalhamento topológico e protegidas por orçamento de interrupção que mantém ao menos duas réplicas disponíveis durante qualquer operação de manutenção. Não há elasticidade automática: três réplicas são um número declarado, não um comportamento. Cada container executa **um único processo de trabalho**, o que mantém o total de conexões contra o banco em menos da metade do teto da instância e devolve às métricas a possibilidade de agregação por réplica.

O banco de dados passa a ser **serviço relacional gerenciado do provedor**, retirado do cluster, na menor classe de instância disponível e sobre família de melhor relação entre preço e desempenho — possível aqui, e não nos nós, porque a arquitetura do processador do banco é invisível para a imagem da aplicação. A redundância é por **réplica síncrona de contingência em outra zona, com failover automático e endereço de conexão único**, e não por réplica de leitura.

Esta decisão declara pré-condições. Não pode ser executada antes de: existir o indicador de prontidão da aplicação, sem o qual três réplicas apenas distribuem erro por três zonas durante cada atualização; a camada de acesso a dados verificar a conexão antes de usá-la, sem o que o failover automático do banco não se traduz em recuperação da aplicação; a preparação do schema deixar de acontecer durante o import do módulo de entrada, conforme já decidido no ADR 001 e ainda não implementado, sob pena de três réplicas concorrerem pela mesma criação; e os segredos da aplicação e do banco existirem fora do código-fonte e fora da imagem.

A razão que pesou mais foi o **alinhamento ao padrão operacional da organização**. Todas as escolhas subordinadas — modo de compute, perfil de nó, tipo de capacidade, topologia — decorrem de aceitar a plataforma padrão como dada e então torná-la a mais barata e a mais disponível possível dentro dos limites dela, em vez de escolher a plataforma que esta aplicação isoladamente justificaria.

## Consequências

- **Positivas:**
  - O ambiente de execução da aplicação passa a existir como decisão registrada, encerrando a lacuna deixada em aberto pelo ADR 001.
  - A perda de uma zona de disponibilidade deixa de ser perda de serviço: a aplicação continua em duas zonas e o banco assume a instância de contingência automaticamente, sem alteração de configuração.
  - A dependência de banco de dados ganha dono declarado, deixando de ser a dependência sem responsável descrita no documento técnico.
  - Backup automático e recuperação a ponto no tempo do banco passam a existir por padrão, em vez de serem trabalho a ser especificado.
  - Nenhum estado permanece no cluster: qualquer nó, e o cluster inteiro, tornam-se descartáveis e reconstruíveis sem perda.
  - A capacidade interruptível reduz o custo dos nós em relação à capacidade sob demanda equivalente, sem reduzir a disponibilidade projetada.
  - As métricas voltam a ser agregáveis por réplica, revertendo parcialmente a fragmentação por processo registrada no ADR 001.

- **Negativas:**
  - O plano de controle do cluster dedicado e os nós representam custo recorrente que não existia, e que não é diluído por nenhuma outra carga — o cluster serve a uma única aplicação.
  - A aplicação de correções ao sistema operacional dos nós e o ciclo de vida das versões do cluster passam a ser responsabilidade da equipe, consequência direta de preferir o grupo de nós gerenciado ao modo sem gestão de nós.
  - Com capacidade interruptível, a retirada de instâncias passa a ser evento normal e não excepcional; com apenas três nós, interrupções simultâneas no mesmo conjunto de capacidade reduzem a capacidade abaixo do desenho até o reprovisionamento.
  - A simetria entre desenvolvimento e produção, força dominante do ADR 001, é reduzida: desenvolvimento executa o banco como container, com superusuário e sem transporte cifrado, enquanto produção executa serviço gerenciado com usuário restrito, cifrado e com parâmetros distintos. Divergências de configuração de banco passam a existir sem serem exercitadas em desenvolvimento.
  - O número de réplicas é fixo: não há resposta automática a aumento de carga, e alterá-lo exige mudança de manifesto e novo ciclo de publicação.
  - O teto de conexões do banco, derivado da memória da instância escolhida, limita o número de réplicas possíveis antes de qualquer limite de processamento ser atingido. A escala futura esbarra no banco, não nos nós.
  - Tráfego entre zonas de disponibilidade passa a ser cobrado, porque as réplicas da aplicação estão em três zonas e a instância ativa do banco está em uma.
  - A imagem de arquitetura única herdada do ADR 001 impede adotar a família de nós de melhor relação entre preço e desempenho, custo que permanece até aquela decisão ser reaberta.
  - Os segredos da aplicação e do banco tornam-se bloqueantes: esta decisão não os resolve, mas passa a exigir que sejam resolvidos antes de qualquer execução.

- **Neutras / trade-offs aceitos:**
  - A disponibilidade projetada é por zona, não por região: a perda de uma região continua sendo perda de serviço, e nada nesta decisão a endereça.
  - O cluster é dedicado: não há compartilhamento de plano de controle nem economia de escala com outras cargas da organização.
  - Exposição externa, repositório de imagens, infraestrutura como código e entrega contínua permanecem fora do escopo desta decisão.
  - A escolha de capacidade interruptível é reversível a custo baixo, por ser atributo do grupo de nós e não do desenho da aplicação.
  - Um único processo de trabalho por container troca vazão por réplica pela previsibilidade de consumo e pelo controle do número de conexões; com três réplicas e sem requisito de desempenho declarado, a vazão perdida não tem beneficiário identificável.
  - A agregação de métricas entre réplicas continua inexistente: a fragmentação deixa de ser por processo e passa a ser por réplica.
