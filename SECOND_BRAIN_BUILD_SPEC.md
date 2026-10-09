# Second Brain Local — Build Spec

## 1. Objetivo

Construir uma primeira versão **100% local** de um Second Brain para agentes de IA que constroem software.

A ideia é reduzir o gasto de tokens causado por:

- recontextualizar o mesmo projeto em diferentes harnesses/agentes;
- reler arquivos e diretórios para redescobrir decisões já tomadas;
- manter histórico enorme na janela de contexto;
- explicar novamente arquitetura, regras e intenção do projeto;
- perder contexto entre sessões.

O Second Brain deve funcionar como uma **memória persistente, pesquisável e legível por humanos**, consultada pelo agente antes de sair explorando o projeto.

Não deve usar API paga de LLM.

---

# 2. Fluxo principal

Dentro de qualquer projeto:

```bash
brain init
```

Isso cria o cérebro local:

```text
meu-projeto/
├── src/
├── ...
└── .brain/
    ├── README.md
    ├── project/
    │   ├── idea.md
    │   ├── overview.md
    │   └── goals.md
    │
    ├── knowledge/
    │   ├── architecture/
    │   ├── decisions/
    │   ├── rules/
    │   ├── dependencies/
    │   ├── bugs/
    │   ├── features/
    │   ├── constraints/
    │   ├── rationale/
    │   └── next-steps/
    │
    ├── index/
    │   └── brain.db
    │
    ├── history/
    ├── config.json
    └── AGENT_BRAIN.md
```

O agente builder deve conseguir:

```text
salvar conhecimento
        ↓
gerar embedding local
        ↓
indexar
        ↓
buscar semanticamente depois
```

---

# 3. Princípio central

O repositório já guarda o código.

O Second Brain deve guardar principalmente **o conhecimento que o agente normalmente teria de redescobrir**.

Exemplos:

- ideia do projeto;
- problema que o projeto resolve;
- visão e objetivo;
- público;
- arquitetura;
- decisões;
- regras;
- dependências conceituais;
- bugs conhecidos;
- motivos das escolhas;
- estado das features;
- restrições;
- próximos passos;
- conhecimento importante descoberto durante implementação.

Não duplicar código inteiro sem necessidade.

---

# 4. Project Context

O Brain precisa conseguir contextualizar um agente novo sem o usuário ter de explicar novamente o projeto.

## `.brain/project/idea.md`

Deve responder:

```text
O que é esse projeto?
Por que ele existe?
Qual problema resolve?
Para quem?
Qual é a visão original?
Qual é a proposta de valor?
```

Exemplo:

```md
# Ideia

O produto é uma plataforma que...

## Problema

...

## Público

...

## Proposta de valor

...

## Visão

...
```

## `.brain/project/overview.md`

Resumo operacional atual:

```text
stack;
arquitetura geral;
componentes principais;
estado atual;
principais fluxos.
```

## `.brain/project/goals.md`

```text
objetivos atuais;
prioridades;
o que NÃO é prioridade;
roadmap de curto prazo.
```

---

# 5. Tipos de memória

O Brain deve tratar cada informação como um tipo explícito.

## Architecture

Como o sistema está organizado.

Exemplos:

- camadas;
- serviços;
- banco;
- frontend/backend;
- autenticação;
- infraestrutura.

---

## Decisions

Escolhas já tomadas.

Exemplo:

```text
Usaremos JWT + refresh token HTTPOnly.
```

Guardar também o motivo quando existir.

---

## Rules

Regras que não devem ser violadas.

Exemplo:

```text
Handlers nunca acessam o banco diretamente.
```

---

## Dependencies

Dependências conceituais entre partes do sistema.

Exemplo:

```text
Billing depende de Organization e Subscription.
```

Não confundir com dependências de package manager.

---

## Bugs

Bugs conhecidos ou comportamento inesperado ainda relevante.

---

## Features

Estado atual de funcionalidades.

Estados sugeridos:

```text
idea
planned
in_progress
implemented
deprecated
blocked
```

---

## Constraints

Restrições técnicas ou de produto.

Exemplos:

```text
Precisa rodar em CPU.
Não adicionar Redis nesta versão.
Precisa continuar compatível com PostgreSQL.
```

---

## Rationale

Motivos por trás de decisões.

Exemplo:

```text
Escolhemos pgvector para evitar manter um segundo banco.
```

---

## Next Steps

Próximas ações relevantes.

Não usar como sistema de tarefas completo.

Guardar apenas próximos passos que ajudam um novo agente a entender para onde o projeto está indo.

---

# 6. Formato dos documentos

Toda memória deve continuar sendo Markdown legível por humanos.

Usar YAML Front Matter.

Exemplo:

```md
---
id: decision-auth-refresh-token
type: decision
title: Estratégia de refresh token
tags:
  - auth
  - security
importance: 0.9
status: active
created_at: 2026-10-09T09:00:00-03:00
updated_at: 2026-10-09T09:00:00-03:00
related:
  - architecture-auth
  - rule-http-only
---

# Estratégia de refresh token

O refresh token será armazenado em cookie HTTPOnly.

## Motivo

Reduzir exposição a ataques XSS.

## Impacto

O frontend não acessa diretamente o refresh token.
```

---

# 7. Ferramentas principais

A V1 deve expor poucas ferramentas.

## `brain_remember`

Salva uma memória durável.

Interface conceitual:

```text
brain_remember(
    type,
    title,
    content,
    tags?,
    importance?,
    related?
)
```

Responsabilidades:

1. validar entrada;
2. criar ou atualizar `.md`;
3. gerar embedding local;
4. atualizar índice;
5. preservar metadata;
6. evitar duplicações óbvias;
7. registrar alteração no histórico.

---

## `brain_search`

Busca contexto relevante.

Interface:

```text
brain_search(
    query,
    types?,
    tags?,
    limit?,
    token_budget?
)
```

Fluxo:

```text
query
↓
embedding local
↓
vector search
↓
keyword search
↓
metadata filtering
↓
ranking
↓
deduplicação
↓
token budget
↓
contexto final
```

Resultado deve ser otimizado para consumo por LLM.

Exemplo:

```text
QUERY
"Como funciona autenticação?"

RESULTS

[decision | 0.95]
Refresh token usa cookie HTTPOnly.

[architecture | 0.92]
Auth segue Handler → Service → Repository.

[rule | 0.87]
Handlers não acessam PostgreSQL diretamente.
```

---

# 8. Retrieval

Não usar apenas cosine similarity.

A V1 pode usar ranking simples e determinístico.

Exemplo:

```text
score =
    0.55 * vector_similarity
  + 0.20 * keyword_score
  + 0.15 * importance
  + 0.10 * recency
```

Os pesos devem ficar configuráveis.

Posteriormente será possível adicionar:

- graph relevance;
- task classification;
- reranking;
- learning-to-rank;
- modelos treinados com histórico real.

Não implementar isso agora se atrasar o MVP.

---

# 9. Embeddings

Requisitos:

- execução local;
- CPU;
- sem API;
- modelo pequeno;
- rápido;
- fácil de distribuir.

Modelo inicial sugerido:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Registrar em `config.json`:

```json
{
  "embedding": {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "dimensions": 384,
    "distance": "cosine"
  }
}
```

O modelo deve ficar explicitamente documentado para permitir reconstrução futura do índice.

---

# 10. Armazenamento vetorial

Preferência para V1:

```text
SQLite + sqlite-vec
```

Objetivo:

- um único arquivo;
- portátil;
- local;
- zero serviço externo;
- instalação simples.

Arquivo:

```text
.brain/index/brain.db
```

Os `.md` são a fonte canônica.

O índice pode ser apagado e reconstruído a qualquer momento.

---

# 11. CLI

Comandos mínimos:

```bash
brain init
brain status
brain index
brain search "query"
brain remember
brain rebuild
```

## `brain init`

- cria `.brain`;
- cria estrutura padrão;
- cria `config.json`;
- cria `AGENT_BRAIN.md`;
- inicializa banco;
- configura integração MCP se possível.

## `brain status`

Exemplo:

```text
Brain: active
Memories: 47
Indexed chunks: 83
Embedding model: all-MiniLM-L6-v2
Last update: 2 minutes ago
```

## `brain index`

Indexa documentos novos ou alterados.

Não recalcular embeddings de arquivos que não mudaram.

## `brain rebuild`

Reconstrói todo o índice a partir dos Markdown.

---

# 12. Integração com agentes

A integração principal deve ser via MCP local.

O servidor deve expor inicialmente:

```text
brain_search
brain_remember
brain_status
```

Opcional:

```text
brain_get
brain_update
```

Não expor dezenas de ferramentas.

---

# 13. `AGENT_BRAIN.md`

O `brain init` deve gerar automaticamente este documento.

Ele serve para qualquer LLM/harness entender como usar o Brain.

Conteúdo base:

```md
# Second Brain — Agent Instructions

Este projeto possui memória persistente em `.brain/`.

## Antes de explorar o projeto

Quando precisar descobrir:

- arquitetura;
- decisões anteriores;
- regras;
- intenção do projeto;
- estado de features;
- bugs conhecidos;
- restrições;
- motivos de escolhas;
- próximos passos;

consulte primeiro `brain_search`.

Evite varrer o repositório inteiro para redescobrir conhecimento que pode estar no Brain.

## Quando salvar memória

Use `brain_remember` ao descobrir ou definir informação durável que será útil em sessões futuras.

Salve:

- novas decisões;
- mudanças arquiteturais;
- regras;
- restrições;
- comportamento importante;
- motivos de decisões;
- estado relevante de features;
- bugs conhecidos;
- próximos passos relevantes.

## Não salvar

Não use o Brain como dump de conversa.

Não salve:

- código inteiro;
- logs temporários;
- detalhes triviais;
- mensagens irrelevantes;
- informações facilmente deriváveis do código;
- cada passo da implementação.

Prefira informação condensada e durável.

## Regra de eficiência

Search before rediscovering.
Remember after learning.
```

---

# 14. Atualização automática de contexto

O agente deve poder atualizar o Brain durante o desenvolvimento.

Fluxo:

```text
usuário pede feature
↓
agente consulta Brain
↓
implementa
↓
identifica conhecimento durável novo
↓
brain_remember
↓
Brain atualizado
```

Exemplo:

Após implementar OAuth:

```text
brain_remember(
  type="feature",
  title="Google OAuth",
  content="Google OAuth implementado usando callback /auth/google/callback...",
  tags=["auth", "oauth"],
  importance=0.8
)
```

---

# 15. Histórico

Não sobrescrever silenciosamente conhecimento importante.

Guardar histórico mínimo de alterações.

Sugestão:

```text
.brain/history/
```

Ou tabela de versões no SQLite.

Deve ser possível saber:

```text
o que mudou;
quando;
qual documento;
versão anterior.
```

Não precisa de UI na V1.

---

# 16. Evitar lixo no Brain

Esse é um requisito importante.

O Brain não pode virar um depósito infinito.

Antes de salvar:

```text
é durável?
é útil em outra sessão?
não está facilmente disponível no código?
não é duplicado?
```

Se a resposta for majoritariamente não, não salvar.

Criar uma política simples de memória.

---

# 17. Token Budget

`brain_search` deve aceitar um orçamento aproximado.

Exemplo:

```text
brain_search(
  query="auth architecture",
  token_budget=1500
)
```

O sistema deve selecionar as melhores memórias que caibam nesse orçamento.

Objetivo:

```text
máxima relevância
/
mínimo contexto
```

---

# 18. Observabilidade

Registrar localmente:

```text
query;
resultados retornados;
scores;
quantidade aproximada de tokens;
tempo da busca;
memórias consultadas.
```

Não registrar conteúdo sensível fora da máquina.

Isso será importante depois para medir se o sistema realmente economiza contexto.

---

# 19. Benchmark futuro

A arquitetura deve permitir comparar:

```text
SEM BRAIN
vs
COM BRAIN
```

Métricas futuras:

- input tokens;
- quantidade de arquivos abertos pelo agente;
- tempo até encontrar contexto;
- número de buscas;
- first-shot success;
- retries;
- custo estimado;
- tamanho do contexto retornado.

Não precisa construir benchmark completo na V1, mas deixar logs suficientes para isso.

---

# 20. Segurança e privacidade

A V1 é local-first.

Requisitos:

- nenhum conteúdo enviado para API externa;
- nenhuma telemetria por padrão;
- embeddings gerados localmente;
- banco local;
- conhecimento continua dentro do repositório/máquina.

Adicionar `.brain/index/` ao `.gitignore` por padrão.

Os Markdown podem ou não ser versionados conforme configuração do usuário.

---

# 21. Configuração

Exemplo:

```json
{
  "version": 1,
  "embedding": {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "dimensions": 384,
    "distance": "cosine"
  },
  "retrieval": {
    "default_limit": 8,
    "default_token_budget": 2000,
    "vector_weight": 0.55,
    "keyword_weight": 0.20,
    "importance_weight": 0.15,
    "recency_weight": 0.10
  },
  "storage": {
    "database": ".brain/index/brain.db"
  }
}
```

---

# 22. Stack sugerida

Para a V1:

```text
Language       Python
CLI            Typer
MCP            Python MCP SDK
Embeddings     sentence-transformers / ONNX
Vector DB      SQLite + sqlite-vec
Markdown       arquivos locais
Metadata       YAML front matter
Validation     Pydantic
```

Priorizar simplicidade e velocidade de implementação.

---

# 23. Não objetivos da V1

Não construir agora:

- interface web;
- cloud;
- autenticação;
- billing;
- colaboração;
- multi-user;
- sincronização remota;
- LLM própria;
- geração de ideias;
- knowledge graph sofisticado;
- modelos de ML treinados;
- reranker neural pesado.

Primeiro provar:

> Um agente com memória local pesquisável gasta menos contexto e redescobre menos informação.

---

# 24. Critérios de aceite

A V1 está pronta quando:

1. `brain init` funciona em um projeto novo.
2. `.brain/` é criado corretamente.
3. `AGENT_BRAIN.md` explica para qualquer agente como usar o sistema.
4. O usuário consegue registrar a ideia inicial do projeto.
5. `brain_remember` cria memória Markdown estruturada.
6. A memória é indexada automaticamente.
7. Embeddings são gerados localmente.
8. `brain_search` retorna conhecimento semanticamente relevante.
9. A busca respeita um token budget.
10. Nenhuma API de LLM é necessária.
11. O MCP permite que um agente consulte e atualize o Brain.
12. O índice pode ser reconstruído integralmente a partir dos `.md`.
13. Alterar um documento reindexa somente o necessário.
14. O agente consegue iniciar uma nova sessão e entender a ideia e decisões principais usando o Brain.
15. Todo o sistema roda localmente em CPU.

---

# 25. Fluxo de teste principal

Criar projeto:

```bash
mkdir brain-test
cd brain-test
brain init
```

Registrar:

```text
Ideia:
API SaaS para gerenciamento de projetos.

Arquitetura:
FastAPI + PostgreSQL.

Decisão:
Usar JWT com refresh token HTTPOnly.

Regra:
Router nunca acessa DB diretamente.
```

Encerrar sessão.

Abrir um novo agente sem histórico anterior.

Perguntar:

```text
"Implemente autenticação."
```

O agente deve consultar o Brain e recuperar automaticamente:

```text
ideia do projeto;
FastAPI + PostgreSQL;
JWT;
refresh HTTPOnly;
regra de separação Router/DB.
```

Sem o usuário precisar contextualizar novamente.

---

# 26. Princípio final

O Second Brain não existe para substituir o repositório nem para acumular informação.

Ele existe para armazenar o **conhecimento comprimido do projeto**.

A regra do sistema é:

> **Search before rediscovering. Remember after learning.**

O objetivo final é permitir que diferentes agentes e diferentes sessões trabalhem sobre o mesmo projeto sem recomeçar cognitivamente do zero.
