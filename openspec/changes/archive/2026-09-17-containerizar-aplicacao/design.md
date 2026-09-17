## Context

Ver `proposal.md` — Why. O que molda a abordagem, além daquilo:

- **O ADR 001 já decidiu a forma.** Imagem única para dev e produção, estágio único, distribuição base de propósito geral, sem montagem de código, preparação de schema como etapa anterior. Este design realiza essas decisões; não as reabre.
- **O TRD descreve o alvo como se fosse o presente.** `docs/trd.md` documenta `schema_prep`, `pool_pre_ping`, `SECRET_KEY` externa e blueprint de saúde. Só o último está fora deste escopo; os três primeiros não existem no código e são criados aqui.
- **Docker já existiu e foi removido** no commit `0f5bbad`. O Dockerfile removido usava base sem tag, quatro processos de trabalho e `depends_on` sem condição — os três pontos que o ADR 001 argumenta contra. Ele serve de referência do que não repetir; o `.dockerignore` removido, ao contrário, é reaproveitável.
- **O Compose é só de desenvolvimento e teste manual.** Decisão do usuário nesta sessão, que também determinou ausência de `.env`.
- **Sem `/ready` neste escopo.** Os PRDs de saúde/prontidão e de semeadura estão "em revisão", com premissas não confirmadas.

## Goals / Non-Goals

**Goals:**

- Realizar as cláusulas do ADR 001 que exigem alteração da aplicação, e não apenas as que cabem em infraestrutura.
- Manter a superfície de alteração no código Python mínima: apenas o que o ADR exige.
- Deixar o ambiente local utilizável sem nenhuma configuração prévia por parte de quem clona.

**Non-Goals:**

- Fidelidade à topologia de produção. O ambiente local é fiel ao *processo* de execução (mesmo servidor de aplicação, mesma imagem), não ao desenho de réplicas e zonas do ADR 002.
- Evolução de schema já existente (migrations). A preparação cria estruturas ausentes e não altera as existentes.
- Automatizar a publicação da imagem. O ADR 001 a mantém manual.

## Decisions

### Dockerfile em `src/`, contexto de build `./src`

Fixado pelo TRD e reafirmado pelo usuário. O contexto restrito mantém `pytest.ini`, `docs/` e `.env.exemple` fora da imagem.

*Alternativa:* Dockerfile na raiz com contexto `.`, que permitiria rodar a suíte dentro do container. Rejeitada — contraria o TRD, e o custo já está registrado como aceito.

### Imagem base `python:3.13-slim`

Debian atende "distribuição base de propósito geral". O ADR rejeita explicitamente a base musl, porque o driver de banco não publica artefatos pré-compilados para ela e o build passaria a compilar a partir do fonte.

*Alternativas:* imagem completa (maior, sem ganho — não há etapa de compilação); versão de interpretador mais recente que 3.13 (rejeitada pelo ADR: dependências fixadas não publicam artefatos pré-compilados para ela).

**A premissa de que todas as 16 dependências têm artefato pré-compilado para 3.13 deve ser verificada no primeiro build**, e não assumida a partir do TRD.

### `SERVICE_VERSION` como argumento de build

`ARG SERVICE_VERSION` promovido a variável de ambiente da imagem, e a mesma expressão usada para nomear a tag. É o único arranjo que torna estruturalmente impossível a divergência que o TRD proíbe entre a versão reportada em `app_info` e a identificação da imagem.

O build SHALL falhar se o argumento não for informado, em vez de assumir um valor padrão — um padrão silencioso reintroduziria exatamente a divergência que este arranjo existe para eliminar.

### Um processo de trabalho, porta configurável

O Dockerfile antigo fixava a porta no comando do servidor enquanto o Compose a parametrizava no mapeamento — com porta diferente de 8000, o mapeamento apontaria para onde ninguém escuta. O comando passa a ligar-se à porta vinda do ambiente.

### `PROMETHEUS_MULTIPROC_DIR` não é definido na imagem

A biblioteca de métricas só ativa o modo multiprocesso quando essa variável está presente no ambiente. Com um único processo de trabalho, esse modo é custo sem retorno: exige diretório gravável e limpeza entre execuções, para agregar um processo só. `src/main.py` mantém a criação do diretório — inofensiva e fora do escopo do ADR.

### `schema_prep.py` no topo de `src/`

Módulo no mesmo nível de `main.py`, importando a base declarativa de `models.event`. Preserva a convenção do projeto (sem `__init__.py`, imports absolutos a partir da raiz de `src`) e permite que a mesma imagem sirva dois pontos de entrada, mudando apenas o comando.

*Alternativa:* preparar o schema no processo mestre do servidor, antes da criação dos trabalhadores. Rejeitada pelo ADR 001 — o pool de conexões nasce durante o import e seria herdado pelos processos filhos, trocando uma falha visível na inicialização por corrupção intermitente.

### `SECRET_KEY` sem valor padrão

`core/settings.py` passa a exigir a variável; sua ausência impede a subida. O valor hoje fixo em `src/main.py` seria distribuído dentro de imagem pública.

*Alternativa:* padrão de desenvolvimento. Rejeitada — um padrão embutido é, por construção, um segredo dentro da imagem, e vale para produção tão bem quanto para desenvolvimento.

O ambiente local fornece um literal de desenvolvimento pelo Compose, de modo que a exigência não cria atrito para quem clona.

### Compose sem interpolação `${...}`

O Compose carrega automaticamente um `.env` vizinho ao arquivo para interpolação, mesmo sem `env_file:`. Portanto, "não usar `.env`" só é garantido pela ausência de `${...}`: todos os valores são literais.

*Alternativa:* `${VAR:-default}`, que sobe sem `.env` mas muda de comportamento se um existir. Rejeitada — é precisamente a dependência implícita que se quis eliminar.

### Ordenação por condição, não por existência

Banco com verificação de saúde própria; preparação de schema condicionada à saúde do banco; aplicação condicionada à *conclusão bem-sucedida* da preparação. O `depends_on` simples do Compose antigo garantia apenas que o container do banco existia.

### Volume nomeado para os dados do banco

*Alternativa:* o bind `./.postgres-data` do Compose antigo. Rejeitada — cria diretório pertencente ao superusuário dentro da árvore do repositório.

### Porta 8000 na máquina local

`api-requests.http` declara `@baseUrl = http://localhost:8000`. Manter a porta faz do arquivo que já existe a ferramenta de exercício manual do ambiente, sem edição.

### Usuário não-root no container

O TRD não decide. Adotado porque a imagem é pública e o custo é uma linha.

## Risks / Trade-offs

- **Ausência de schema deixa de ser detectada na inicialização** → dentro do Compose, a ordenação por conclusão da preparação cobre o caso. Fora dele, executar a imagem avulsa contra banco não preparado falha só na primeira consulta de negócio. Mitigação real é `/ready`, fora deste escopo; registrar como lacuna conhecida.
- **`SECRET_KEY` obrigatória quebra qualquer execução existente** → mitigado por `.env.exemple` atualizado e por mensagem de erro que nomeia a variável ausente. É quebra deliberada: falhar alto é o objetivo.
- **Ciclo de desenvolvimento mais longo**, sem recarga automática → trade-off aceito explicitamente pelo ADR 001, em favor da fidelidade ao ambiente de execução.
- **Premissa de artefatos pré-compilados para 3.13** → verificar no primeiro build; se falhar, a decisão de versão de interpretador volta à mesa antes de qualquer outra tarefa.
- **Publicação manual com tag única** → publicar sem incrementar a versão sobrescreve silenciosamente uma imagem já distribuída. Fora do escopo de automação; permanece risco operacional documentado.
- **Assimetria dev × produção no banco** → container com superusuário e sem transporte cifrado, contra serviço gerenciado com usuário restrito e cifrado. Já registrada no ADR 002 como consequência aceita.

## Migration Plan

1. `src/schema_prep.py`, `src/core/settings.py` e `src/core/database.py` — as alterações de aplicação, verificáveis sem container.
2. `src/main.py` — remoção da criação de tabelas e da `SECRET_KEY` fixa. A partir daqui, executar a aplicação exige schema previamente preparado.
3. `src/Dockerfile` e `src/.dockerignore` — primeiro build, que também verifica a premissa de versão de interpretador.
4. `docker-compose.yml` e `.env.exemple` — ambiente completo e sua documentação.

**Rollback:** reverter os commits. Os arquivos novos são aditivos; as quatro alterações em código são pontuais e isoladas. Nenhuma alteração de schema ou de dado é introduzida, então não há estado a desfazer.

## Open Questions

- Nome e namespace do repositório de imagens no registro público, necessários apenas para a publicação manual. Não bloqueia o ambiente local nem nenhuma tarefa deste change.
