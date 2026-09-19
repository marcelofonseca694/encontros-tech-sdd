## Context

Ver `proposal.md` — Why, para a motivação, e `specs/semeadura-de-eventos/spec.md` para os requisitos. O que este documento acrescenta é o estado concreto do código e as decisões técnicas tomadas em sessão de exploração antes desta proposta.

- `src/schema_prep.py:1-27` já é o molde de "operação acionável, mesma imagem, resultado por código de saída" que o PRD pede (ADR 001): importa `settings`/`logging`/`engine`, define `main() -> int`, chama `sys.exit(main())`.
- `src/services/event_service.py:13-44` (`create_event`) é o único caminho de criação hoje, e chama incondicionalmente `log_business_event(logger, "EVENT_CREATED", ...)` (linhas 31-36). `src/routers/api_router.py:26-32` chama um segundo `log_business_event("API_EVENT_CREATED", ...)` na camada de rota. Nenhum dos dois é alcançado por um script que nunca importa `routers/` nem chama `event_service`.
- `src/models/event.py:15` já gera `edit_token` por `default=lambda: str(uuid.uuid4())` na própria coluna — dispara em qualquer `INSERT`, independente do caminho de código usado.
- `technologies` (`src/schemas/event.py:10`) nunca é persistido — `event_service.create_event`/`update_event` só o atribuem como atributo transiente na resposta imediata (comentário nas linhas 27 e 126 de `event_service.py`). Qualquer evento relido do banco (listagem, busca, detalhe) não tem esse atributo, e o Pydantic cai no default `[]`. Isso já vale para eventos reais hoje, não é algo que a semeadura precisa replicar.
- `docs/adrs/001-containerizacao-com-docker.md`: decide que a preparação de schema roda "a partir da mesma imagem, etapa separada e anterior" — mesma forma que este design adota para a semeadura.
- `docs/adrs/003-banco-de-dados-no-cluster.md`: o banco em produção roda como carga sem volume persistente — qualquer substituição do pod apaga todo o dado, real ou semeado. Reforça por que a semeadura precisa ser segura para reexecutar (P5), e por que não há necessidade de um modo destrutivo próprio: o ambiente real já não garante durabilidade nenhuma.
- `docs/trd.md:52` documenta a linha de `schema_prep` na tabela de componentes; não há linha equivalente para semeadura — fica como lacuna de documentação, não coberta por este design.

## Goals / Non-Goals

**Goals:**
- Um script standalone, a partir da mesma imagem, que checa o catálogo, insere os dez eventos numa única transação quando vazio, e sinaliza o desfecho por código de saída.
- Conjunto de dados de referência (título, descrição, local) separado da lógica de decisão, editável sem tocar código.
- Suíte de testes automatizados com sessão de banco mockada, no mesmo padrão de `test_event_service.py`, sem depender de um Postgres real.

**Non-Goals:**
- Wiring de `docker-compose.yml`, manifesto Kubernetes ou pipeline — a proposta já delimita isso como fora de escopo; este design entrega o script e seu contrato, não onde ele é chamado.
- Qualquer trava contra acionamento concorrente da própria semeadura — decisão explícita da sessão de exploração.
- Tocar `event_service`, os routers, ou o modelo `Event` — o caminho de criação real da aplicação permanece intocado.

## Decisions

### D1 — Novo script `seed.py`, mesmo formato de `schema_prep.py`

Mesma estrutura de `src/schema_prep.py`: `main() -> int` chamado por `sys.exit(main())`, logger via `setup_logging(...)`, settings via `core.settings`.

*Alternativa considerada:* expor a semeadura como comando da própria aplicação Flask (ex.: `flask seed`). Rejeitada porque acoplaria a semeadura ao processo da aplicação, contrariando P1/invariante 3 (iniciar a aplicação nunca semeia) e o padrão já estabelecido por `schema_prep.py` de operação standalone e independente.

### D2 — Inserção direta via `models.event.Event`, bypassando `event_service`

A sessão obtida por `core.database.get_db()` monta os dez `Event(...)` diretamente e faz `db.add_all(...)` — nunca chama `event_service.create_event`. Isso evita as duas chamadas a `log_business_event` (serviço e router) descritas em Context, resolvendo P17 por construção, sem introduzir nenhuma ramificação condicional no único caminho de criação usado pela aplicação real. `edit_token` continua vindo do `default` da coluna, então P14 é satisfeito sem lógica adicional.

*Alternativa considerada:* adicionar um parâmetro (`silent: bool`) a `event_service.create_event` para suprimir o log quando chamado pela semeadura. Rejeitada na sessão de exploração: acrescentaria um galho condicional a código de produção só para servir a um chamador que a aplicação em si nunca invoca.

### D3 — Checagem de vazio e inserção na mesma transação, sem trava adicional

`SELECT` de existência seguido de `db.add_all([...])` e um único `db.commit()`. Sob o isolamento padrão do Postgres (READ COMMITTED) isso não impede duas execuções simultâneas de ambas verem o catálogo vazio e inserirem — essa proteção foi deliberadamente descartada na sessão de exploração, assumindo acionamento único por vez, no mesmo espírito de `schema_prep.py` (que também não se protege contra `CREATE TABLE` concorrente). A atomicidade "tudo ou nada" (P7) vem da própria transação: qualquer exceção antes do commit não deixa nenhuma linha gravada.

### D4 — Conjunto de referência em um módulo de dados separado

Os dez eventos (título, descrição, local, data de referência) vivem em uma estrutura própria (ex.: `seed_data.py`), importada por `seed.py`. Satisfaz a restrição do PRD de conjunto "editável sem alterar lógica": adicionar, trocar ou remover um evento de demonstração é editar essa estrutura, não a função que decide se semeia.

As datas de referência são extraídas de `api-requests.http` e ordenadas cronologicamente antes de qualquer cálculo — a ordem dos dez blocos no arquivo não é a ordem das datas (ex.: o quarto bloco, 25/fev/2024, aparece depois do terceiro, 5/mar/2024).

### D5 — Deslocamento constante de datas, primeiro evento 3 dias após o acionamento

`offset = (agora + 3 dias) - data_de_referência_mais_antiga`; o mesmo `offset` é somado às dez datas já ordenadas. Preserva exatamente a ordem e o espaçamento relativo do conjunto de referência (P10) por aritmética de calendário, sem nenhuma lógica de escala. O span do conjunto de referência é 55 dias (15/fev a 10/abr/2024); com o deslocamento, o último evento cai a aproximadamente 58 dias do acionamento — dentro de "aproximadamente dois meses" (Premissa 1 do PRD, confirmada nesta sessão).

*Alternativa considerada:* escalar os intervalos proporcionalmente para caber num span fixo de exatamente 60 dias. Rejeitada por adicionar uma transformação sem necessidade — o span original já cai dentro da margem de "aproximadamente", e preservar os deltas exatos é mais simples e mais fácil de testar do que preservar proporções.

### D6 — Resultado por código de saída, mesmo padrão de `schema_prep.py`

`main()` retorna `int`; `sys.exit(main())` sinaliza sucesso (`0`) ou falha (`1`) sem exigir interpretação de texto (P16). Diferente de `schema_prep.py`, há dois casos de sucesso — "semeou" e "não semeou porque o catálogo já tinha conteúdo" — que mapeiam ambos para `0`; só uma falha efetiva mapeia para `1`. Uma mensagem de log em INFO distingue os dois casos de sucesso para quem lê a saída (P15), sem afetar o código de saída.

## Risks / Trade-offs

- **Sem trava contra acionamento concorrente (D3)** → duas execuções simultâneas da semeadura podem ambas ver o catálogo vazio e inserir vinte eventos em vez de dez. Mitigação: nenhuma nesta entrega — risco aceito deliberadamente pelo usuário. Se a operação real do pipeline vier a acionar a semeadura em paralelo, esta decisão precisa ser revisitada.
- **Span de ~58 dias, não exatamente 60 (D5)** → consequência direta de preservar o espaçamento relativo exato em vez de escalar para um número redondo. "Aproximadamente dois meses" no PRD já é uma aproximação; aceito como está.
- **Banco efêmero em produção (ADR 003)** → qualquer substituição do pod do banco apaga os eventos semeados junto com qualquer dado real, exigindo reacionar a semeadura como parte da recuperação — mesma situação que a preparação de schema já enfrenta. Coberto pelo design porque P5 garante que reacionar é seguro; decidir *quando* reacionar é decisão de pipeline, fora do escopo desta entrega.

## Migration Plan

1. Implementar `seed_data.py` (conjunto de referência) e `seed.py` (checagem, inserção, código de saída), seguindo D1-D6.
2. Testar localmente contra o Postgres do `docker-compose.yml` existente, por execução manual do script dentro do container da aplicação — sem alterar `docker-compose.yml` nesta entrega.
3. Escrever a suíte de testes automatizados com sessão mockada, cobrindo catálogo vazio, catálogo com conteúdo, armazenamento indisponível e ausência de estado parcial após falha no meio da execução.

**Rollback:** a operação nunca é destrutiva — sua única ação possível é criar eventos, e apenas quando não há nenhum. Não há estado de dado a reverter; se o próprio script tiver defeito, o rollback é reverter o commit ou a imagem que o introduziu.
