## Why

Um catálogo de eventos vazio custa atrito recorrente em desenvolvimento (dez requisições manuais em `api-requests.http`), impossibilita ambientes efêmeros de pipeline (nenhum agente automatizado consegue disparar essas requisições), e o único conjunto de referência existente tem datas de 2024, já vencidas para demonstração. É necessária uma operação acionável, repetível e segura que leve um catálogo vazio a um catálogo de demonstração utilizável, sem risco de tocar em dado real.

## What Changes

- Novo script standalone de semeadura, executado a partir da mesma imagem da aplicação (mesmo padrão de `schema_prep.py`): acionamento explícito, nunca embutido na inicialização da aplicação.
- Insere os dez eventos de demonstração diretamente via `models.event.Event`, sem passar por `services/event_service.py` nem pelos routers — nenhum caminho de criação real é alterado, e nenhum evento de negócio (`log_business_event`) é emitido pela semeadura.
- Age apenas quando o catálogo está vazio (checagem seguida de inserção em uma única transação); catálogo com qualquer conteúdo, de qualquer origem, é reportado como sucesso sem nenhuma escrita.
- Título, descrição e local dos dez eventos derivam de `api-requests.http`; datas são recalculadas por deslocamento constante a partir das datas de referência (ordenadas cronologicamente), com o primeiro evento 3 dias após o acionamento e o último a aproximadamente dois meses — preservando o espaçamento relativo do conjunto original.
- Resultado sinalizado por código de saída (sucesso semeando, sucesso sem semear, falha), consumível por um agente automatizado sem interpretar texto, e por uma pessoa via log.
- Suíte de testes automatizados cobrindo catálogo vazio, catálogo com conteúdo, armazenamento indisponível e ausência de estado parcial após falha — usando sessão de banco mockada, no mesmo padrão de `test_event_service.py`, sem depender de um Postgres real.
- Acionamento simultâneo da semeadura (duas execuções ao mesmo tempo) é deliberadamente deixado sem proteção adicional, no mesmo espírito de `schema_prep.py`: a operação assume um único acionamento por vez.

## Capabilities

### New Capabilities
- `semeadura-de-eventos`: operação acionável que povoa um catálogo de eventos vazio com dez eventos de demonstração derivados de `api-requests.http`, com datas futuras recalculadas, de forma idempotente e atômica, sem afetar dado preexistente e sem distorcer a observabilidade de negócio da aplicação.

### Modified Capabilities

(nenhuma — a nova operação é isolada da aplicação em execução; `inicializacao-da-aplicacao` e `ambiente-de-desenvolvimento` continuam com seu comportamento atual inalterado, e o wiring de pipeline/ambiente que aciona a semeadura fica fora do escopo desta entrega)

## Impact

- **Código**: um novo script standalone (paralelo a `schema_prep.py`) na mesma imagem da aplicação, mais uma nova suíte de testes. Nenhum arquivo em `src/services/`, `src/routers/` ou `src/models/` é alterado.
- **Dependências**: nenhuma nova; reutiliza `core.settings` e `core.database` já existentes, sem configuração ou credencial próprias.
- **Blast radius**: limitado ao processo da própria semeadura e à tabela `events`. A operação roda fora do processo da aplicação e fora do seu ciclo de vida de inicialização, portanto nunca concorre com requisições em andamento nem com múltiplas instâncias da aplicação subindo.
- **Disponibilidade / HA**: a aplicação continua atendendo requisições normalmente durante e após a semeadura — nenhuma migração de schema, nenhum lock além da transação da própria inserção, nenhum reinício exigido. Uma semeadura travada ou lenta não afeta a aplicação já em execução, apenas o passo de pipeline que a aciona.
- **Rollback**: a operação é não destrutiva por construção — sua única ação possível é criar eventos, e apenas quando não há nenhum. Não existe "desfazer a semeadura" a projetar: reexecutá-la é sempre seguro, e uma falha no meio da execução não deixa estado parcial (tudo ou nada), então não há artefato para reverter. Caso o próprio script tenha defeito, o rollback é reverter o commit/imagem que o introduziu. Repopular um catálogo indesejado após um evento real ter sido cadastrado é, por decisão explícita do PRD de origem, sempre manual e fora do escopo desta feature (modo destrutivo não faz parte da entrega).
