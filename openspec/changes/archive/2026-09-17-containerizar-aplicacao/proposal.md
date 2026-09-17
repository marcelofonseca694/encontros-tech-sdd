## Why

O ADR 001 foi aceito e decidiu o container Docker como unidade de empacotamento e execução, mas a decisão nunca foi realizada em código. O Docker que existia no repositório foi removido no commit `0f5bbad`, antes do ADR, e o que restou contradiz a decisão em pontos concretos: não há procedimento de execução no repositório, a versão do interpretador varia por máquina, e a criação das tabelas acontece durante o import de `src/main.py` — o defeito de concorrência que o ADR 001 se recusou a mascarar.

Três cláusulas do ADR não são implementáveis apenas com infraestrutura: elas exigem alteração da aplicação. Por isso este change vai além do Dockerfile e do Compose.

## What Changes

**Empacotamento**
- Novo `src/Dockerfile`, com contexto de build restrito a `./src`, estágio único e versão de interpretador fixada pela imagem base.
- Novo `src/.dockerignore`, recuperável de `0f5bbad^`, que já excluía `tests/` e `.env`.
- A identificação de versão da imagem e a versão reportada pela aplicação passam a derivar da mesma fonte no mesmo instante do build.

**Preparação de schema**
- Novo `src/schema_prep.py`: a preparação do schema vira etapa acionável separada, executada a partir da mesma imagem, sinalizando resultado por código de saída.
- **BREAKING** — `src/main.py` deixa de executar `Base.metadata.create_all()` no import. Executar a aplicação contra um banco não preparado deixa de falhar na inicialização e passa a falhar na primeira consulta de negócio, mais tarde e mais perto do usuário. É a consequência que o ADR 001 registra e aceita.

**Configuração e resiliência**
- **BREAKING** — `SECRET_KEY` deixa de ter valor fixo em `src/main.py` e passa a ser obrigatória no ambiente: sem ela a aplicação não sobe. Hoje o valor `'your-secret-key-here'` está no código-fonte e seria distribuído dentro de imagem pública.
- `src/core/database.py` passa a usar verificação prévia de conexão e reciclagem, para que a recuperação da dependência se traduza em recuperação da aplicação, sem reinício.

**Ambiente de desenvolvimento e teste**
- Novo `docker-compose.yml` na raiz, para desenvolvimento e teste manual apenas, subindo banco, preparação de schema e aplicação com um comando, e condicionando cada etapa à conclusão real da anterior.
- O Compose não lê `.env` nem usa interpolação `${...}`: todos os valores são literais de desenvolvimento. O Compose carrega automaticamente um `.env` vizinho para interpolação, e ausência de `${...}` é o que efetivamente garante independência desse arquivo.
- `.env.exemple` ganha `SECRET_KEY` e perde a menção a variáveis "usadas pelo docker-compose", que passa a ser falsa.

## Capabilities

### New Capabilities

- `empacotamento-em-container`: a aplicação como artefato de imagem única — o que entra na imagem, o que é proibido entrar, e como a versão do artefato se relaciona com a versão que a aplicação reporta.
- `preparacao-de-schema`: a preparação do armazenamento de eventos como operação acionável, separada e anterior à aplicação, com contrato de resultado legível por agente automatizado.
- `inicializacao-da-aplicacao`: o que a aplicação exige do ambiente para subir, o que ela deixa de fazer durante a inicialização, e como se comporta quando a dependência de banco está ausente ou se recupera.
- `ambiente-de-desenvolvimento`: o ambiente local completo obtido por um comando, sua ordem de subida e as superfícies que expõe para exercício manual.

### Modified Capabilities

Nenhuma. O projeto ainda não possui specs — `openspec list --specs` não retorna nenhuma capability.

## Impact

**Código afetado**
- `src/main.py` — remoção da criação de tabelas no import e da `SECRET_KEY` fixa
- `src/core/settings.py` — `SECRET_KEY` sem valor padrão
- `src/core/database.py` — parâmetros de resiliência do pool
- `src/schema_prep.py`, `src/Dockerfile`, `src/.dockerignore`, `docker-compose.yml`, `.env.exemple` — novos ou alterados

**Documentação**
- Realiza o ADR 001 e converge o `docs/trd.md` com o código: hoje o TRD descreve o estado-alvo como se fosse o presente.

**Fora do escopo**
- `/health` e `/ready` (`docs/prds/prd-health-ready.md`) e semeadura (`docs/prds/prd-seed.md`) — ambos os PRDs estão "em revisão", com premissas ainda não confirmadas.
- Manifestos de Kubernetes e o cluster EKS do ADR 002.
- Automação da publicação no Docker Hub, que o ADR 001 mantém manual.
- Executar a suíte de testes dentro do container: o contexto de build em `./src` mantém `pytest.ini` fora da imagem, e o TRD registra esse custo como aceito.
