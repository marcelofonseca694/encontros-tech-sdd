---
adr_number: "003"
status: aceito
created: 2026-09-17
supersedes: ""
superseded_by: ""
---

# ADR 003: Executar o banco de dados como carga no próprio cluster, com armazenamento efêmero

## Contexto

O ADR 002 retirou o banco de dados do cluster e o colocou em serviço relacional gerenciado do provedor, com réplica síncrona de contingência, failover automático, backup nativo e recuperação a ponto no tempo. Registrou também, entre as alternativas recusadas, o banco como container dentro do cluster, justamente por prender a carga a uma zona e por transferir para a equipe responsabilidades que no serviço gerenciado existem por padrão.

A escrita do manifesto de implantação — trabalho que motivou esta decisão — expôs o que aquela escolha deixou em aberto: o ambiente descrito pelo ADR 002 não existe. Não há instância gerenciada provisionada, não há rede nem conta preparadas para recebê-la, e o único cluster disponível para receber o manifesto é local, de nó único conjunto sem rótulos de zona, na máquina de desenvolvimento. Um manifesto fiel ao ADR 002 referencia um endereço de banco que não existe em lugar nenhum e, por isso, não pode ser aplicado a cluster algum. Um artefato inaplicável não é um manifesto: é uma descrição de intenção.

O dado em questão tem, hoje, uma característica que pesa na decisão: ele é inteiramente reconstruível por operação de negócio. Não há conteúdo acumulado, histórico, nem informação cuja perda seja irrecuperável por outro meio — a única tabela do projeto guarda eventos cadastrados pela própria interface, e nenhum deles é fonte primária de nada.

As forças em tensão são três. A primeira é **aplicabilidade contra durabilidade**: um banco gerenciado protege o dado e bloqueia a existência do ambiente até que infraestrutura de nuvem seja provisionada, enquanto um banco no cluster torna o manifesto imediatamente aplicável e põe o dado em risco. A segunda é **fidelidade ao desenho de disponibilidade contra existência de um lugar onde exercitá-lo**: a topologia de três zonas do ADR 002 só tem valor se houver cluster onde ela seja observável, e não há. A terceira é **estado no cluster contra descartabilidade do cluster**: o ADR 002 registrou como ganho que nenhum estado permanecesse ali, e esta decisão devolve estado para dentro dele.

A decisão é tomada agora porque o manifesto exige um endereço de banco declarado, e não existe nenhum a declarar.

## Alternativas Consideradas

- **Manter o serviço relacional gerenciado do provedor** — preservaria backup automático, recuperação a ponto no tempo, failover automático e o alvo de tolerar a perda de uma zona de disponibilidade, todos obtidos sem trabalho adicional; em contrapartida condiciona a primeira aplicação do manifesto a provisionar conta, rede e instância na nuvem, trabalho que não começou e cujo prazo não está declarado, mantendo o artefato inaplicável enquanto isso e deixando a entrega do manifesto dependente de uma frente que não é dele.

- **Banco no cluster com volume persistente reivindicado** — daria durabilidade ao dado entre reinícios do pod e é a forma correta de declarar carga com estado em um orquestrador; porém exige carga com identidade estável em lugar de réplicas intercambiáveis, uma classe de armazenamento disponível no cluster, e decisões próprias de tamanho, expansão e retenção de volume. Some-se que o volume de bloco é de zona única e de anexação exclusiva, o que reintroduz exatamente a amarra de zona que o ADR 002 recusou. Fica **adiada, não recusada**: é o caminho para quando o dado passar a ter valor a proteger.

- **Apontar a aplicação dentro do cluster para o banco em container do ambiente de desenvolvimento, fora do cluster** — dispensaria qualquer carga de banco no manifesto e reaproveitaria o que o Compose já sobe; em troca faz o manifesto depender de um endereço de host da máquina de desenvolvimento, que varia conforme sistema operacional e driver de cluster, e acopla dois ambientes cujos ciclos de vida são independentes — derrubar o ambiente local passaria a derrubar o serviço no cluster.

- **Nenhum banco no manifesto, com o endereço deixado como configuração a preencher** — manteria o manifesto integralmente fiel ao ADR 002 e aplicável a qualquer cluster; entretanto o resultado observável da aplicação seria a preparação de schema falhando e três réplicas permanentemente não-prontas, de modo que o manifesto nunca seria exercitado de ponta a ponta e nenhum defeito nele seria descoberto antes de existir infraestrutura.

## Decisão

Adotamos o banco de dados como **carga executada dentro do próprio cluster**, com **armazenamento efêmero** — o dado existe apenas enquanto o pod existe — e **sem volume persistente reivindicado neste momento**.

Esta decisão revisa **exclusivamente** a escolha de banco de dados do ADR 002. Permanecem em vigor, sem alteração: o provedor de nuvem e o serviço de orquestração, o modo de compute por grupo de nós gerenciado, o perfil e a quantidade de nós, a capacidade interruptível, a topologia de três nós em três zonas, as três réplicas fixas da aplicação com restrição de espalhamento topológico e orçamento de interrupção, e o único processo de trabalho por container.

O banco é declarado como carga **sem identidade estável**, e não como conjunto com estado, porque sem volume não há nada que uma identidade estável preserve — a réplica que retorna após uma substituição não reencontra dado algum, e fingir continuidade por meio do nome seria descrever uma propriedade que não existe. É exposto por **endereço de serviço interno do cluster**, único e estável, e é esse endereço que a aplicação recebe como destino de conexão: a propriedade de endereço único que o ADR 002 obtinha por failover gerenciado é preservada, ainda que por mecanismo diferente e sem a garantia que aquele oferecia.

As credenciais do banco e o segredo da aplicação são fornecidos como **segredo do orquestrador**, externos ao código-fonte e à imagem. A pré-condição que o ADR 002 declarou bloqueante continua bloqueante, e é por aqui que passa a ser atendida.

A etapa de preparação de schema, separada do processo da aplicação pelo ADR 001, ganha uma responsabilidade que não tinha: como o banco nasce vazio a cada substituição do pod, ela deixa de ser etapa executada uma vez por publicação e passa a ser **condição de recuperação do serviço**.

A razão que pesou mais foi a **aplicabilidade do artefato**. Enquanto não existir instância gerenciada provisionada, uma decisão de banco que impede o ambiente de execução de existir é, hoje, pior do que uma decisão de banco que aceita risco sobre um dado inteiramente reconstruível. A ordem é deliberada: primeiro o manifesto aplicável e exercitável, depois a durabilidade do dado.

## Consequências

- **Positivas:**
  - O manifesto passa a ser aplicável a qualquer cluster, incluindo um cluster local, sem depender de provisionamento de infraestrutura na nuvem: o ambiente de execução deixa de estar bloqueado por uma frente de trabalho que não começou.
  - Não resta nenhuma dependência externa ao cluster para executar o serviço completo: banco, preparação de schema e aplicação sobem e descem por um único comando sobre um único arquivo.
  - A simetria entre desenvolvimento e produção, explicitamente reduzida pelo ADR 002, é recuperada: os dois ambientes voltam a executar o banco como container, e a assimetria de transporte cifrado, usuário e parâmetros de instância que o ADR 002 registrou como divergência conhecida deixa de existir.
  - O teto de conexões deixa de derivar da memória de uma classe de instância gerenciada e passa a ser parâmetro do próprio container, removendo o limite que o ADR 002 apontava como teto da escala futura da aplicação.
  - O custo recorrente do serviço gerenciado desaparece, e com ele o tráfego cobrado entre zonas entre as réplicas e a instância ativa do banco.

- **Negativas:**
  - **A perda do dado deixa de ser cenário excepcional e passa a ser rotina.** Qualquer reinício, atualização, correção de nó ou reagendamento do pod do banco apaga tudo. O ADR 002 recusou o banco no cluster alegando que a perda do volume seria perda definitiva; sem volume, não existe nem o volume que aquele cenário pressupunha perder.
  - O alvo de disponibilidade do ADR 002 — tolerar a perda de uma zona de disponibilidade sem indisponibilidade percebida — deixa de ser atendido. As três réplicas da aplicação continuam distribuídas em três zonas, mas todas dependem de um único pod de banco em uma única zona: a perda daquela zona é perda de serviço, e as réplicas sobreviventes apenas reportam não-prontidão de forma correta.
  - Backup automático e recuperação a ponto no tempo, que o ADR 002 obtinha por padrão do serviço gerenciado, deixam de existir e não são substituídos por nada.
  - A preparação de schema passa a fazer parte do caminho de recuperação, e não apenas da publicação. Enquanto não for reexecutada após uma substituição do pod do banco, a aplicação permanece viva e não-pronta, e nenhuma requisição de negócio é atendida.
  - O cluster deixa de ser descartável. O ADR 002 registrava como ganho que nenhum estado permanecesse nele; passa a permanecer estado sem durabilidade, que é a combinação mais desfavorável entre as duas propriedades.
  - O ciclo de vida do banco — versão, parâmetros de instância, correções de segurança — volta a ser responsabilidade da equipe, revertendo uma das economias do ADR 002.
  - Com capacidade interruptível nos nós, decisão mantida do ADR 002, a retirada de instância é evento normal: o pod do banco é reagendado com frequência esperada, e cada reagendamento é uma perda total de dados.

- **Neutras / trade-offs aceitos:**
  - O armazenamento efêmero é declaradamente provisório. O volume persistente foi adiado, não recusado, e adotá-lo depois exige rever a forma da carga para identidade estável e declarar classe de armazenamento, tamanho e retenção.
  - O endereço de conexão permanece único e estável, como no ADR 002, mas por ser nome de serviço do cluster e não por failover de instância. A aplicação não distingue os dois casos, e por isso não muda.
  - A verificação prévia de conexão no pool, exigida pelo ADR 002 para que o failover gerenciado se traduzisse em recuperação da aplicação, continua necessária — agora para a substituição do pod do banco.
  - A decisão é reversível a custo baixo do lado da aplicação: o endereço do banco é configuração externa à imagem, e voltar ao serviço gerenciado significa trocar o valor do segredo e remover a carga de banco do manifesto, sem tocar em código.
  - O dado ser hoje inteiramente reconstruível por operação de negócio é premissa desta decisão, não propriedade permanente do sistema. No momento em que deixar de ser verdade, esta decisão precisa ser reaberta.
