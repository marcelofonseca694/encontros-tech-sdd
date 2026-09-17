## 1. Alterações na aplicação

- [x] 1.1 Tornar `SECRET_KEY` obrigatória em `src/core/settings.py`, sem valor padrão, e verificar que importar as configurações sem a variável definida falha com mensagem que nomeia a variável ausente, e que com a variável definida o valor é carregado
- [x] 1.2 Adicionar verificação prévia de conexão e reciclagem ao engine em `src/core/database.py`, e verificar inspecionando o engine criado que ambos os parâmetros estão ativos
- [x] 1.3 Criar `src/schema_prep.py` como ponto de entrada independente que cria as estruturas ausentes e sinaliza por código de saída, e verificar que contra um banco vazio a tabela `events` passa a existir com código de saída 0, contra um banco já preparado nada é alterado com código de saída 0, e contra um banco parado nenhuma estrutura é criada, o código de saída é diferente de 0 e a causa fica registrada em log
- [x] 1.4 Remover de `src/main.py` a chamada de criação de tabelas, seu import de `models.event` e a `SECRET_KEY` fixa, passando a obtê-la das configurações, e verificar que nenhuma estrutura é criada ao iniciar a aplicação contra um banco vazio
- [x] 1.5 (fora do escopo original — descoberto e corrigido durante a validação 5.3, com autorização do usuário) Corrigir `src/routers/api_router.py`: os handlers de `create`, `read_events`, `get_event_by_token` e `update_event` chamavam `.model_dump()` diretamente no objeto ORM `Event` retornado por `event_service`, o que sempre resultava em `500 Internal Server Error` (o `Event` ORM não tem `model_dump`; só o schema Pydantic `schemas.event.Event` tem). Cada handler agora converte com `Event.model_validate(result)` antes de serializar

## 2. Imagem de container

- [x] 2.1 Recuperar `src/.dockerignore` de `0f5bbad^` e verificar que as entradas que excluem `tests/` e `.env` estão presentes (ajuste adicional descoberto na validação 5.5: `.dockerignore` original de `0f5bbad^` não excluía `.env.example`, que por isso aparecia na imagem construída; adicionada a entrada `.env.example`)
- [x] 2.2 Criar `src/Dockerfile` sobre `python:3.13-slim`, em estágio único, com `SERVICE_VERSION` como argumento de build promovido a variável de ambiente, usuário não-root e servidor de aplicação com um processo de trabalho ligado à porta vinda do ambiente, e verificar que o build com o argumento informado conclui e que o build sem o argumento falha
- [x] 2.3 Verificar na saída do build que nenhuma das 16 dependências é compilada a partir do código-fonte; se alguma exigir compilação, interromper e reabrir a decisão de versão do interpretador antes de seguir

## 3. Ambiente de desenvolvimento e teste

- [x] 3.1 Criar `docker-compose.yml` na raiz com banco, preparação de schema e aplicação, usando apenas valores literais, sem interpolação `${...}`, e volume nomeado para os dados
- [x] 3.2 Condicionar a preparação de schema à saúde do banco e a aplicação à conclusão bem-sucedida da preparação
- [x] 3.3 Expor a aplicação em `8000` e o banco em `5432` na máquina local

## 4. Documentação

- [x] 4.1 Atualizar `.env.exemple` acrescentando `SECRET_KEY` e removendo a menção a variáveis "usadas pelo docker-compose", e verificar que o arquivo descreve apenas o que a execução fora do Compose exige

## 5. Validação executada

Esta bateria é executada de fato, contra o ambiente real, e cada item só é dado por concluído com a saída observada do comando. Ela exercita os cenários declarados nos specs.

- [x] 5.1 Executar `pytest` na raiz e confirmar que os sete testes de `src/tests/services/test_event_service.py` passam após as alterações do grupo 1
- [x] 5.2 Partindo de estado limpo (`docker compose down -v`), executar `docker compose up --build` e confirmar na saída que a ordem de subida foi banco saudável, depois preparação de schema concluída com código de saída 0, depois aplicação
- [x] 5.3 Com o ambiente no ar, disparar as requisições de `api-requests.http` sem editar o arquivo e confirmar que criar, listar, consultar por identificador e editar por token funcionam pela API, e que a página inicial responde
- [x] 5.4 Conectar um cliente de banco a `localhost:5432` e confirmar que a tabela `events` existe e contém os eventos criados no item anterior
- [x] 5.5 Inspecionar a imagem construída e confirmar que `pytest.ini`, `docs/`, `tests/` e arquivos `.env` estão ausentes, e que nenhum segredo de aplicação ou credencial de banco aparece nas camadas ou nas variáveis de ambiente
- [x] 5.6 Confirmar que a versão reportada pela aplicação em execução é idêntica ao valor usado para identificar a imagem
- [x] 5.7 Parar o container do banco com a aplicação atendendo e confirmar que o processo da aplicação permanece em execução sem reiniciar; subir o banco novamente e confirmar que as requisições de negócio voltam a ser atendidas sem reiniciar a aplicação
- [x] 5.8 Forçar a preparação de schema a falhar (banco inalcançável) e confirmar que a aplicação não chega a ser iniciada
- [x] 5.9 Remover `SECRET_KEY` da configuração do ambiente e confirmar que a aplicação não sobe, com a causa identificável na saída
- [x] 5.10 Criar um `.env` na raiz com valores divergentes dos do Compose, subir o ambiente e confirmar que nenhum comportamento muda
- [x] 5.11 Alterar um arquivo de `src/`, confirmar que o ambiente em execução continua servindo o código anterior, e confirmar que após subir novamente com reconstrução o código alterado passa a valer
- [x] 5.12 Encerrar com `docker compose down -v` e repetir o item 5.2 do zero, confirmando que o ambiente sobe de forma repetível a partir de um estado limpo
