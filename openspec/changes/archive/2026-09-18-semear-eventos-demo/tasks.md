## 1. Conjunto de dados de referência

- [x] 1.1 Criar `src/seed_data.py` com os dez eventos de demonstração (título, descrição, local, data de referência) extraídos de `api-requests.http`, ordenados cronologicamente por data de referência (D4 de design.md — a ordem dos blocos no arquivo não é a ordem das datas). Verificar com `python3 -c "from seed_data import REFERENCE_EVENTS; assert len(REFERENCE_EVENTS) == 10; assert REFERENCE_EVENTS == sorted(REFERENCE_EVENTS, key=lambda e: e['reference_date'])"` (executado a partir de `src/`).

## 2. Script de semeadura

- [x] 2.1 Criar `src/seed.py` na mesma estrutura de `src/schema_prep.py` (D1): `main() -> int` chamado por `sys.exit(main())`, logger via `setup_logging(...)`. Verificar que `python3 seed.py` (a partir de `src/`, sem banco disponível) encerra com código de saída diferente de zero, sem lançar traceback não tratado.
- [x] 2.2 Implementar a checagem de catálogo vazio dentro de uma sessão obtida por `core.database.get_db()` (D3). Verificar com teste unitário que, dada uma sessão mockada cuja consulta retorna um evento existente, nenhuma escrita é tentada.
- [x] 2.3 Implementar o cálculo de datas por deslocamento constante (D5): `offset = (agora + timedelta(days=3)) - min(data de referência)`, somado a cada uma das dez datas já ordenadas. Verificar com teste unitário que, para uma data de referência fixa conhecida, as dez datas calculadas preservam os mesmos intervalos relativos do conjunto de referência e a primeira cai exatamente 3 dias após o instante do acionamento.
- [x] 2.4 Implementar a inserção dos dez `models.event.Event` diretamente (sem passar por `services/event_service.py`), com `db.add_all(...)` seguido de um único `db.commit()` dentro da mesma transação da checagem de vazio (D2, D3). Verificar com teste unitário que `event_service.create_event` nunca é chamado (patch/spy) durante a semeadura.
- [x] 2.5 Sinalizar os três desfechos — semeou, não semeou por já haver conteúdo, falhou — por log em INFO/ERROR e código de saída `0`/`0`/`1` (D6; P15, P16). Verificar com três testes unitários, um por desfecho, checando a mensagem de log e o valor retornado por `main()`.
- [x] 2.6 Tratar armazenamento não preparado ou inacessível como falha: capturar a exceção de conexão/consulta, registrar a causa em log de forma diagnosticável, garantir rollback (nenhuma linha parcial) e retornar código de falha (P3, P7). Verificar com teste unitário que mocka uma exceção na checagem inicial e confirma `db.rollback()` (ou ausência de `commit`) e retorno de falha.

## 3. Testes automatizados

- [x] 3.1 Criar `src/tests/test_seed.py`, no mesmo padrão de sessão mockada (`unittest.mock.MagicMock`) de `tests/services/test_event_service.py`, cobrindo os cenários de `specs/semeadura-de-eventos/spec.md`: catálogo vazio cria os dez eventos; catálogo com qualquer conteúdo (inclusive um único evento cadastrado por pessoa) não altera nada e reporta sucesso; armazenamento indisponível reporta falha sem criar nada; falha no meio da execução não deixa estado parcial; repetição após sucesso mantém quantidade e conteúdo idênticos; todas as datas semeadas são futuras e preservam ordem/espaçamento relativo; dois lotes de tokens gerados em execuções distintas não coincidem entre si nem com o conteúdo dos eventos.
- [x] 3.2 Rodar a suíte completa com `cd src && python -m pytest tests/ -q` e confirmar que os testes novos passam junto com os existentes, em um único comando, sem depender de nenhum banco real em execução (critério de aceite 15).

## 4. Verificação de ponta a ponta (gate)

- [x] 4.1 Subir o ambiente local (`docker compose up --build`) com o catálogo vazio, acionar a semeadura manualmente (ex.: `docker compose run --rm app python3 seed.py`) e confirmar via `GET http://localhost:8000/api/events/` que os dez eventos existem, com título/descrição/local correspondentes a `api-requests.http` e datas futuras (critérios de aceite 1, 7, 8).
- [x] 4.2 Acionar a semeadura novamente em seguida e confirmar, pela mesma consulta, que a quantidade, os ids e os `edit_token` permanecem idênticos à execução anterior, e o processo termina com código de sucesso (critério de aceite 2).
- [x] 4.3 Com um catálogo vazio, cadastrar um único evento via `api-requests.http` e acionar a semeadura: confirmar que o catálogo permanece com apenas aquele evento e a semeadura termina com código de sucesso (critérios de aceite 3, 11).
- [x] 4.4 Parar o banco (`docker compose stop db`) e acionar a semeadura: confirmar código de saída de falha, nenhum evento criado ao reativar o banco e conferir o catálogo, e a causa registrada no log do processo de semeadura (critério de aceite 4).
- [x] 4.5 Após a semeadura bem-sucedida em 4.1, inspecionar o log de negócio da aplicação (`log_business_event`) e confirmar que nenhum `EVENT_CREATED`/`API_EVENT_CREATED` foi emitido pela semeadura — apenas os eventos criados via API real, se houver, aparecem ali (critério de aceite 13, P17).

## 5. Documentação

- [x] 5.1 Atualizar `docs/prds/prd-seed.md`: marcar as Premissas 1, 3, 4 e 5 da tabela "Premissas a confirmar" como confirmadas, e ajustar P10/critério de aceite 7 para registrar o deslocamento constante com primeiro evento 3 dias após o acionamento (em vez de "poucos dias", ainda em aberto). Verificar por leitura, comparando cada trecho alterado com as decisões registradas em `design.md` (D4, D5).
