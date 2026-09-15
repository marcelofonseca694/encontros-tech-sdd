
Material complementar da aula. O prompt abaixo é o artefato central: copie, cole no seu agente com o repositório aberto e gere o TRD baseline do seu projeto. Ele já embute o template completo do documento.

---

## Prompt — Geração do TRD inicial (baseline técnico)

Prompt único, copy-paste, que instrui o agente a documentar o **baseline técnico** do projeto lendo o repositório inteiro como fonte de verdade. Descreve o que o sistema **é hoje** (não o que deveria virar), embute o template literal do TRD e uma regra de verificação anti-alucinação que não vaza para o documento.

```
Você é um engenheiro documentando o BASELINE TÉCNICO deste projeto. Sua fonte de verdade é o REPOSITÓRIO INTEIRO já aberto — leia o código, os arquivos de configuração e a estrutura de pastas. Documente ESTE projeto como ele É hoje.

TAREFA: gerar o TRD inicial (Technical Requirements Document) do projeto em `docs/trd.md`.

REGRA CENTRAL: o TRD inicial descreve O QUE O SISTEMA É (o estado atual, o baseline), não o que ele deveria virar. Nada de recomendações, melhorias ou refactors. Decisões (por que X em vez de Y) ficam em ADRs; comportamento que muda fica em PRDs.

VERIFICAÇÃO INTERNA (anti-alucinação — NÃO vai pro documento): antes de escrever cada afirmação, confirme-a num arquivo real do repositório. Isso é raciocínio seu, não conteúdo: o documento final NÃO leva coluna de fonte, nem citações de `arquivo:linha`, nem marcações de premissa. Regras:
- Não suponha, não use conhecimento externo sobre "como projetos Flask costumam ser".
- Se nenhum arquivo sustenta uma afirmação, NÃO a escreva — não infira, não complete a lacuna.
- Onde o código não definir um valor esperado pelo template, escreva "Não definido" / "Não aplicável".
- O que for relevante mas você não conseguiu confirmar, me levante NA REVISÃO (na conversa, fora do arquivo) para eu decidir.

O documento final deve seguir EXATAMENTE este template — mesmos headings, mesma ordem, mesmas colunas. Não numere nem coloque os títulos em caixa-alta.

# TRD — <Projeto>

> Documento técnico global do projeto. Granularidade baixa: cobre o que é global e estável.
> Regras finas ficam em ADRs.

## Stack
Tabela com colunas: | Dimensão | Valor |
Dimensões: Linguagem principal, Runtime/plataforma, Framework principal, Banco de dados, Ferramentas de build, Gerenciador de pacotes.

## Arquitetura
### Padrão arquitetural
O padrão em camadas (router → service) em 1-2 linhas, e por que.
### Estrutura de pastas dominante
Árvore de 2 níveis em bloco de código, com 1 linha de responsabilidade por pasta.
### Módulos / camadas principais
Tabela com colunas: | Módulo | Responsabilidade |
### Rotas
Tabela com colunas: | Método | Rota | Handler | (separe API e páginas se existirem os dois).
### Modelo de dados
Uma tabela por entidade/tabela, com colunas: | Coluna | Tipo | Constraints/Default |.

## Requisitos Não-Funcionais
Tabela com colunas: | Dimensão | Requisito |
Inclua SEMPRE estas dimensões, nesta ordem: Performance, Disponibilidade/SLA, Escalabilidade, Segurança, Observabilidade. Onde o código não sustenta um valor, escreva "Não definido" — NÃO omita a linha.

## Dependências Externas
Tabela com colunas: | Serviço / Sistema | Tipo | Constraint relevante | Dono |
Só serviços/sistemas que impõem contrato (ex.: PostgreSQL). Não liste libs de build do lockfile. Se não houver, escreva "Nenhuma".

## Padrões
### Testes
Tabela com colunas: | Item | Valor | — linhas: Framework, Comando completo, Cobertura mínima, Estratégia.
### Estilo de código
Bullets: Linter, Formatter, Convenções de nomenclatura. O que não existir: "Não aplicável".
### Error handling
Prosa curta do padrão real.
### Logging
Bullets: Formato, Nível padrão, Biblioteca.
### Autenticação / autorização
Prosa curta — ou "Não aplicável".

## Decisões Globais (ADRs)
Tabela com colunas: | # | Título | Data | Status | Link |
Ainda não há ADR: deixe uma linha com *(nenhum ADR registrado)*. Os ADRs virão depois e serão indexados aqui.

Ao terminar, me mostre o TRD seção por seção para revisão ANTES de gravar o arquivo — e liste à parte (fora do documento) o que você NÃO conseguiu confirmar no código, pra eu decidir.
```
