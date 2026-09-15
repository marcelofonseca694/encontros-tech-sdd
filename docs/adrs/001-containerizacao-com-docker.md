---
adr_number: "001"
status: aceito
created: 2026-09-15
supersedes: ""
superseded_by: ""
---

# ADR 001: Adotar containers Docker como unidade de empacotamento e execução

## Contexto

A aplicação é executada como processo Python direto, gerenciado pelo systemd, numa máquina onde o banco de dados já está provisionado. O comando de inicialização não existe em nenhum arquivo do repositório: é conhecimento operacional mantido fora dele. Consequentemente, quem clona o projeto não tem como saber como executá-lo, e preparar um ambiente de desenvolvimento exige prover a dependência de banco manualmente, a cada máquina, sem procedimento registrado.

A versão do interpretador Python também não é declarada em lugar nenhum do repositório — não há arquivo de pinagem de runtime. Ela é, na prática, aquela que estiver instalada em cada máquina.

Há ainda um defeito latente: a criação das tabelas do banco acontece durante o import do módulo de entrada, antes de a aplicação existir. Sob systemd, com um banco que está no ar há semanas, isso nunca falha. Sob qualquer execução com múltiplos processos de trabalho contra um banco recém-iniciado, passa a falhar de forma imediata e visível.

As forças em tensão são três. A primeira é **fidelidade contra conveniência**: um ambiente de desenvolvimento otimizado para ciclo rápido diverge daquilo que roda em produção, e a divergência esconde justamente as falhas de execução concorrente. A segunda é **atualidade contra viabilidade de build**: adotar a versão mais recente do interpretador implicaria compilar dependências a partir do código-fonte, incluindo uma que exige toolchain de outra linguagem. A terceira é **distribuição contra exposição**: publicar a imagem num repositório público torna distribuível tudo o que está dentro dela, inclusive o que hoje está no código-fonte e não deveria estar.

A decisão é tomada agora porque a containerização é pré-requisito para qualquer evolução do ambiente de execução, e porque o material de aula deste projeto depende de um procedimento de execução reproduzível.

## Alternativas Consideradas

- **Manter a execução direta sob systemd** — não exige mudança alguma e preserva o que já funciona em produção; em contrapartida, mantém o comando de inicialização fora do repositório, mantém o provisionamento de dependências como tarefa manual por máquina e deixa a versão do interpretador indefinida.

- **Ambiente de desenvolvimento otimizado para conveniência** — código do host montado dentro do container e servidor de desenvolvimento com recarga automática. Dá o ciclo de edição mais curto possível e dispensa reconstrução a cada alteração; em troca, o ambiente de desenvolvimento deixa de exercitar o mesmo servidor de aplicação que produção, e falhas de execução multi-processo só apareceriam depois do desenvolvimento, fora do alcance de quem as introduziu. Monta ainda um problema de propriedade de arquivos entre o usuário do container e o do host.

- **Imagem sobre distribuição enxuta baseada em musl** — produziria a menor imagem base disponível; porém o driver de acesso ao banco não publica artefatos pré-compilados para essa biblioteca C, forçando compilação a partir do fonte durante o build, o que exige ferramentas de compilação na imagem e resulta em imagem final maior que a alternativa escolhida.

- **Build em múltiplos estágios** — isolaria ferramentas de compilação fora da imagem final, prática recomendada quando há etapa de compilação. Este projeto não tem etapa de build e, na versão de interpretador escolhida, todas as dependências têm artefato pré-compilado — o estágio extra adicionaria complexidade sem retorno.

- **Adotar a versão mais recente do interpretador** — manteria o projeto na versão mais atual da linguagem; entretanto duas dependências pinadas não publicam artefatos pré-compilados para ela, e uma delas exigiria toolchain de outra linguagem dentro do processo de build, tornando-o lento e frágil. Acomodá-la exigiria atualizar as dependências pinadas, o que é decisão de outro escopo.

- **Preparar o schema dentro do processo da aplicação, no processo mestre antes da criação dos trabalhadores** — resolveria a concorrência entre processos com uma única alteração de configuração; porém o pool de conexões da aplicação é construído durante o import, de modo que nasceria antes da bifurcação e seria herdado pelos processos filhos, que passariam a compartilhar as mesmas conexões de rede com o banco. Trocaria uma falha visível na inicialização por corrupção intermitente em tempo de execução.

## Decisão

Adotamos o container Docker como unidade de empacotamento e execução da aplicação, substituindo a execução direta sob systemd.

Um único artefato de imagem atende desenvolvimento e produção, executado em ambos pelo mesmo servidor de aplicação de produção; a diferença entre ambientes existe apenas como configuração externa à imagem, nunca como imagem distinta. O ambiente de desenvolvimento é orquestrado por Docker Compose, que constrói e executa essa mesma imagem ao lado da dependência de banco de dados, condicionando a subida da aplicação à disponibilidade real da dependência — não à sua mera existência. O código-fonte não é montado a partir do host: a reconstrução da imagem é o mecanismo de propagação de alterações, automatizada pelo próprio Compose.

A versão do interpretador passa a ser declarada e fixada pela imagem, escolhida como a versão mais recente para a qual todas as dependências pinadas publicam artefatos pré-compilados, sobre distribuição base de propósito geral e em estágio único.

A preparação do schema do banco deixa de acontecer no processo da aplicação e passa a ser etapa separada e anterior, executada a partir da mesma imagem, da qual a aplicação depende para subir.

A imagem é publicada em repositório público no Docker Hub, para uma única arquitetura, com tag única derivada de uma fonte de versão única do projeto, congelada na imagem no momento do build. Não há tag móvel, e a publicação é manual.

A razão que pesou mais foi a **fidelidade entre desenvolvimento e produção**: todas as escolhas subordinadas — mesmo servidor de aplicação em ambos, ausência de montagem de código, diferença apenas por configuração — decorrem de recusar um ambiente de desenvolvimento que esconda o comportamento real do ambiente de execução.

## Consequências

- **Positivas:**
  - O procedimento de execução da aplicação passa a existir dentro do repositório, deixando de ser conhecimento operacional externo.
  - A versão do interpretador é declarada pela primeira vez na história do projeto, e deixa de variar por máquina.
  - O ambiente de desenvolvimento completo, incluindo a dependência de banco, passa a ser obtido por um comando, sem provisionamento manual.
  - O defeito de concorrência na criação do schema deixa de ser latente: é corrigido pela separação da etapa, em vez de mascarado pela estabilidade do ambiente.
  - A aplicação deixa de encerrar durante a inicialização quando o banco está indisponível.
  - A versão reportada pela aplicação não pode divergir da identificação da imagem que a contém, porque ambas derivam da mesma fonte no mesmo instante.

- **Negativas:**
  - Não há recarga automática de código: toda alteração exige reconstrução da imagem, ainda que automatizada. O ciclo de desenvolvimento fica mais longo que o de execução local direta.
  - Com tag única e publicação manual, uma publicação sem incremento prévio da versão sobrescreve silenciosamente uma imagem já distribuída, invalidando a suposição de que a identificação é estável.
  - O segredo de aplicação hoje fixo no código-fonte deixa de estar apenas no controle de versão e passa a ser distribuído dentro de imagem pública, extraível por qualquer pessoa. A decisão não o resolve; passa a exigir que seja resolvido.
  - A imagem serve uma única arquitetura: construí-la a partir de máquina de arquitetura diferente exige forçar a plataforma de destino explicitamente, sob pena de publicar artefato inexecutável no ambiente alvo.
  - A ausência de schema deixa de ser detectada na inicialização e passa a se manifestar na primeira consulta ao banco — mais tarde e mais perto do usuário.

- **Neutras / trade-offs aceitos:**
  - O ambiente de desenvolvimento é fiel ao processo de execução, não à topologia de produção: continua sendo uma única instância com banco local.
  - A evolução de schema já existente permanece descoberta — a etapa de preparação cria estruturas ausentes, não altera as existentes.
  - A definição de orquestração fora do Docker permanece fora do escopo desta decisão.
  - O contexto de build restrito ao diretório de código mantém documentação e configuração de teste fora da imagem, o que impede executar a suíte de testes dentro do container sem ajuste posterior.
  - A execução com múltiplos processos de trabalho faz as métricas passarem a ser contabilizadas por processo, e não pelo serviço como um todo, enquanto não houver agregação entre eles.
