# Repository-context benchmark

This experiment saves durable facts about Second Brain in a temporary local project, then asks ten questions (five topics and five paraphrases) in a fresh process. No LLM or API is called.

CPU embedding model: `intfloat/multilingual-e5-small`. Tokenizer: cl100k_base (tiktoken).

| Approximate budget | Questions with all facts | Selected source excerpts | Brain payload | Largest actual response | Savings vs excerpts | Savings vs whole files |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 150 | 8/10 | 13392 | 1222 | 143 | 90.88% | 97.20% |
| 250 | 10/10 | 13392 | 2010 | 219 | 84.99% | 95.40% |
| 400 | 10/10 | 13392 | 3184 | 345 | 76.22% | 92.71% |
| 600 | 10/10 | 13392 | 3224 | 350 | 75.93% | 92.62% |

The smallest tested budget with complete fact coverage was **250**. The measured retrieval payload fell from **13392** selected excerpt tokens to **2010** Brain tokens (**84.99%** less). The first search took **4167.01 ms** including model loading; the median of subsequent searches was **16.67 ms**.

## Questions at the selected budget

| Question ID | Excerpt tokens | Brain tokens | Payload savings | All facts found |
| --- | ---: | ---: | ---: | --- |
| indexacao | 1290 | 202 | 84.34% | yes |
| mcp | 2165 | 204 | 90.58% | yes |
| embedding | 539 | 205 | 61.97% | yes |
| historico | 1236 | 204 | 83.50% | yes |
| busca | 1455 | 211 | 85.50% | yes |
| indexacao_parafrase | 1292 | 199 | 84.60% | yes |
| mcp_parafrase | 2167 | 186 | 91.42% | yes |
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

The instruction counts below describe the payload recorded in this benchmark run. The current onboarding protocol has expanded; rerun the benchmark for its updated setup cost. Initial project inspection and memory authoring remain additional costs.

Agent instructions: **408 tokens**. JSON tool schemas: **352 tokens**. If both are presented once for all ten questions, Brain totals **2770 tokens** (79.32% below excerpts). If presented in ten independent sessions, Brain totals **9610 tokens** (28.24% below excerpts). These are hypothetical prompt accounting scenarios; MCP clients can represent, resend, or cache schemas differently.

## Shared input sensitivity

The table adds the same non-retrieval input to both workflows for each of ten questions. It excludes MCP setup, memory authoring, output, and reasoning.

| Other input/question | Excerpt workflow | Brain workflow | Total input reduction |
| ---: | ---: | ---: | ---: |
| 0 | 13,392 | 2,010 | 84.99% |
| 500 | 18,392 | 7,010 | 61.89% |
| 1,000 | 23,392 | 12,010 | 48.66% |
| 5,000 | 63,392 | 52,010 | 17.95% |
| 10,000 | 113,392 | 102,010 | 10.04% |

## Interpretation

The excerpt baseline consists of source functions chosen in advance to answer each question; the whole-file baseline includes their full files. Each question is independent. The Brain side counts the exact returned context, including query, titles, and scores. The fixture questions and sample memory are in Portuguese to exercise multilingual retrieval. Fact checks require predefined strings in that response. This favors the authored memories and is not a blind evaluation. A coding agent still needs source code to implement and verify changes; a precise `rg` query may use fewer tokens. Model tokenizers differ.

The authored memory titles and contents total **521 tokens**. Persisted Markdown, including front matter and project documents, totals **1473 tokens**. The LLM cost of authoring and maintaining those memories was not measured. Neither were builder reasoning, retries, outputs, task quality, or total billed usage. This is measured retrieval context, not a measured end-to-end LLM saving.

To measure actual builder usage, run paired tasks in equivalent checkouts with the same model and harness, verify equal task quality, collect `codex exec --json` traces, and compare them with `benchmarks/compare_codex_traces.py`. Raw queries, excerpts, responses, and counts are in `benchmarks/results/latest.json`. Reproduce with `python benchmarks/measure.py` after installing `.[benchmark]` and downloading the embedding model.
