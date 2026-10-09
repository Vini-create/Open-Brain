# Repository-context benchmark

This experiment saves durable facts about Second Brain in a temporary local project, then asks ten questions (five topics and five paraphrases) in a fresh process. No LLM or API is called.

CPU embedding model: `intfloat/multilingual-e5-small`. Tokenizer: cl100k_base (tiktoken).

| Approximate budget | Questions with all facts | Selected source excerpts | Brain payload | Largest actual response | Savings vs excerpts | Savings vs whole files |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 150 | 8/10 | 13192 | 1222 | 143 | 90.74% | 97.17% |
| 250 | 10/10 | 13192 | 2010 | 219 | 84.76% | 95.34% |
| 400 | 10/10 | 13192 | 3184 | 345 | 75.86% | 92.62% |
| 600 | 10/10 | 13192 | 3224 | 350 | 75.56% | 92.53% |

The smallest tested budget with complete fact coverage was **250**. The measured retrieval payload fell from **13192** selected excerpt tokens to **2010** Brain tokens (**84.76%** less). The first search took **4824.69 ms** including model loading; the median of subsequent searches was **21.80 ms**.

## Questions at the selected budget

| Question ID | Excerpt tokens | Brain tokens | Payload savings | All facts found |
| --- | ---: | ---: | ---: | --- |
| indexacao | 1252 | 202 | 83.87% | yes |
| mcp | 2103 | 204 | 90.30% | yes |
| embedding | 539 | 205 | 61.97% | yes |
| historico | 1236 | 204 | 83.50% | yes |
| busca | 1455 | 211 | 85.50% | yes |
| indexacao_parafrase | 1254 | 199 | 84.13% | yes |
| mcp_parafrase | 2105 | 186 | 91.16% | yes |
| embedding_parafrase | 548 | 194 | 64.60% | yes |
| historico_parafrase | 1239 | 186 | 84.99% | yes |
| busca_parafrase | 1461 | 219 | 85.01% | yes |

## Actual search response

```text
QUERY
Preciso de chave de serviço externo para vetorizar memórias ou o modelo roda nesta máquina?

RESULTS

[project | 0.77]
Project overview
CLI Python com memórias Markdown, embeddings locais na CPU, índice SQLite + sqlite-vec e servidor MCP via stdio.

[decision | 0.76]
Embeddings locais em CPU
O modelo padrão é intfloat/multilingual-e5-small, com 384 dimensões, rodando na CPU. Não há provider nem API key. brain model download baixa pesos uma vez; o uso normal carrega apenas o cache local.

[rule | 0.73]
Privacidade local
O conteúdo do projeto não é enviado a API externa. Não há telemetria nem chamada a API de LLM. Busca e indexação funcionam offline após baixar os pesos do modelo uma vez.
```

## MCP setup sensitivity

Agent instructions: **408 tokens**. JSON tool schemas: **352 tokens**. If both are presented once for all ten questions, Brain totals **2770 tokens** (79.00% below excerpts). If presented in ten independent sessions, Brain totals **9610 tokens** (27.15% below excerpts). These are hypothetical prompt accounting scenarios; MCP clients can represent, resend, or cache schemas differently.

## Shared input sensitivity

The table adds the same non-retrieval input to both workflows for each of ten questions. It excludes MCP setup, memory authoring, output, and reasoning.

| Other input/question | Excerpt workflow | Brain workflow | Total input reduction |
| ---: | ---: | ---: | ---: |
| 0 | 13,192 | 2,010 | 84.76% |
| 500 | 18,192 | 7,010 | 61.47% |
| 1,000 | 23,192 | 12,010 | 48.21% |
| 5,000 | 63,192 | 52,010 | 17.70% |
| 10,000 | 113,192 | 102,010 | 9.88% |

## Interpretation

The excerpt baseline consists of source functions chosen in advance to answer each question; the whole-file baseline includes their full files. Each question is independent. The Brain side counts the exact returned context, including query, titles, and scores. The fixture questions and sample memory are in Portuguese to exercise multilingual retrieval. Fact checks require predefined strings in that response. This favors the authored memories and is not a blind evaluation. A coding agent still needs source code to implement and verify changes; a precise `rg` query may use fewer tokens. Model tokenizers differ.

The authored memory titles and contents total **521 tokens**. Persisted Markdown, including front matter and project documents, totals **1473 tokens**. The LLM cost of authoring and maintaining those memories was not measured. Neither were builder reasoning, retries, outputs, task quality, or total billed usage. This is measured retrieval context, not a measured end-to-end LLM saving.

To measure actual builder usage, run paired tasks in equivalent checkouts with the same model and harness, verify equal task quality, collect `codex exec --json` traces, and compare them with `benchmarks/compare_codex_traces.py`. Raw queries, excerpts, responses, and counts are in `benchmarks/results/latest.json`. Reproduce with `python benchmarks/measure.py` after installing `.[benchmark]` and downloading the embedding model.
