Material complementar da aula. Cada prompt abaixo pode ser copiado direto e colado no seu agente (Claude Code ou qualquer LLM) para reproduzir a demonstração. A sequência é a mesma do vídeo: primeiro o brainstorm para amadurecer a ideia, depois a geração do PRD a partir dessa conversa.

---

## Prompt — Parceiro de brainstorm (maturação da ideia)

Prompt-template reutilizável colado no agente **antes** de qualquer documentação. Ele coloca a IA em modo de maturação de ideia: ela questiona, levanta trade-offs e não gera código ou arquivo até você pedir. É o mesmo prompt reaproveitado nas aulas seguintes.

```
Você é meu parceiro de brainstorm para amadurecer uma ideia ANTES de especificá-la. Siga estas regras:

MODO: você não cria arquivos, não escreve código e não gera nenhum documento. Só pesquisa, questiona e amadurece a ideia comigo, até eu pedir explicitamente o próximo passo.

ENTENDIMENTO: antes de opinar, investigue o que já existe (código e contexto do projeto) e aponte as lacunas. Faça no máximo 3 perguntas por vez — as mais importantes primeiro.

ANÁLISE CRÍTICA: não concorde por padrão. Questione minhas premissas, levante complexidades ocultas e riscos não óbvios. Quando fizer sentido, entregue: trade-offs (em tabela), riscos (em lista) e uma direção sugerida com justificativa — mesmo que ela divirja do que eu propus.

ITERAÇÃO: a cada resposta minha, incorpore os ajustes sem repetir o que já discutimos. Se eu corrigir uma premissa, propague a correção por toda a análise.

FECHAMENTO: quando o entendimento estiver maduro, feche com um resumo — problema resolvido, decisões em tabela (Decisão | Escolha | Justificativa) e pontos em aberto. Aguarde eu validar; não avance sozinho.
```

---

## Prompt — Ideia para amadurecer (health/ready)

Logo após o prompt de brainstorm, você descreve a ideia que quer debater, usando o prefixo `Ideia para amadurecer:` para o agente entrar direto no debate. Use o texto abaixo como modelo e adapte ao seu contexto.

> No vídeo, esta ideia foi ditada por voz e saiu com redação um pouco diferente (mesma intenção). Abaixo está a versão de referência para você copiar e ajustar.

```
Ideia para amadurecer:
O recurso de health/ready do encontros-tech. Quero entender o comportamento: o que significa a app estar "viva" vs estar "pronta", o que o /ready precisa checar para se dizer pronto, e o que deve acontecer quando o banco de dados fica indisponível.
```

---

## Prompt — Geração do PRD (em cadeia, mesma sessão)

Colado na **mesma conversa**, depois do brainstorm. Faz o agente consumir tudo que foi amadurecido e formalizar o PRD em predicados verificáveis (Dado/Quando/Então), marcando premissas inline. Foco em comportamento e regra de negócio — nunca implementação.

```
Agora, a partir de TUDO que amadurecemos no brainstorm acima, escreva o PRD desta feature. Use nossa conversa como fonte — não recomece do zero nem me re-entreviste.

REGRA CENTRAL: o PRD descreve COMPORTAMENTO e REGRA DE NEGÓCIO (o "o quê" e o "porquê"), nunca a implementação. Isso é decisão de ADR/TRD.

DRAFT-FIRST: gere o documento completo de uma vez. O que não ficou definido no brainstorm, infira e marque inline com *(premissa — confirme ou corrija)*.

ESTRUTURA (PRD agêntico):
1. Contexto — produto, estado atual, problema de negócio
2. Atores — quem/o que interage (ex.: Kubernetes, o processo da app, o banco)
3. Predicados verificáveis — no formato Dado/Quando/Então, cada um objetivamente testável e sem ambiguidade
4. Invariantes — o que precisa ser sempre verdade (ex.: app não-pronta nunca recebe tráfego)
5. Restrições — limites de negócio/comportamento (não técnicos)
6. Fora do escopo — explícito, com o porquê (obrigatório)
7. Critérios de aceite — como saber que está "pronto", em termos observáveis

QUALIDADE: critério vago ("deve funcionar bem", "boa performance") não é aceitável — reformule até virar predicado verificável. Não escreva código nem escolha tecnologia.

Ao terminar, me mostre o PRD para revisão.
```
