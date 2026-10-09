# Measured growth benchmark

This local experiment creates project documents and matching Brain memories. Four questions check exact facts while synthetic distractors repeat common search terms. No LLM or API is called.

CPU embedding model: `intfloat/multilingual-e5-small`. Approximate search budget: 180. Token count: cl100k_base (tiktoken).

Environment: 12th Gen Intel(R) Core(TM) i5-12450H (12 logical CPUs), Linux x86_64, Python 3.14.7, PyTorch 2.14.1+cpu, sqlite-vec 0.1.9.

## Savings by project size

Each row measures four questions in one shared session against the same number of project documents and indexed Brain memories. The Brain total includes one copy of agent instructions and MCP tool schemas. The conventional baseline is broad `rg` path discovery plus one selected file per question. A negative reduction means Brain uses more retrieval-context tokens.

The capped column applies an **8,000-token maximum to each measured conventional search output**. It is a token-accounting simulation; it does not verify that a clipped `rg` result still contains the needed file or fact.

| Project documents / indexed memories | Brain facts | Brain incl. setup | Broad search, uncapped | Reduction, uncapped | Reduction, 8k/query cap |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 4/4 | 1,342 | 1,156 | -16.09% | -16.09% |
| 44 | 4/4 | 1,342 | 2,276 | 41.04% | 41.04% |
| 164 | 4/4 | 1,342 | 5,636 | 76.19% | 76.19% |
| 1,000 | 4/4 | 1,342 | 29,044 | 95.38% | 95.38% |
| 5,000 | 4/4 | 1,342 | 157,028 | 99.15% | 95.81% |
| 10,000 | 4/4 | 1,342 | 317,028 | 99.58% | 95.81% |

These are **retrieval-context reductions**, not measured changes in a builder's total LLM tokens or bill. The uncapped path listing exceeds practical prompt sizes at the largest levels. Exact-keyword search can use fewer tokens than Brain after MCP setup. Search latency is reported below.

## Full measurements

| Documents | Facts found | Brain payload | Targeted `rg` + file | Broad `rg` + file | Savings vs targeted | Savings vs broad | Median search ms | New-chunk index s | DB MiB | Map MiB |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 4/4 | 582 | 1115 | 1156 | 47.80% | 49.65% | 15.84 | 0.00 | 1.61 | 0.02 |
| 44 | 4/4 | 582 | 1115 | 2276 | 47.80% | 74.43% | 29.81 | 0.56 | 1.96 | 0.03 |
| 164 | 4/4 | 582 | 1115 | 5636 | 47.80% | 89.67% | 74.35 | 2.31 | 3.04 | 0.08 |
| 1000 | 4/4 | 582 | 1115 | 29044 | 47.80% | 98.00% | 408.54 | 16.02 | 10.46 | 0.39 |
| 5000 | 4/4 | 582 | 1115 | 157028 | 47.80% | 99.63% | 2056.72 | 70.65 | 52.05 | 1.88 |
| 10000 | 4/4 | 582 | 1115 | 317028 | 47.80% | 99.82% | 3963.35 | 89.86 | 104.03 | 3.76 |

## MCP setup costs

These instruction counts describe the payload recorded in this benchmark run. The current onboarding protocol has expanded; rerun the benchmark to measure its updated setup cost. Initial inspection and memory authoring are additional agent costs.

The agent instructions contain **408 tokens** and the JSON schemas of the MCP tools contain **352 tokens**, or **760 tokens** together. These are measured text sizes, not observed client billing. If a client includes both for each of four fresh sessions:

| Documents | Brain including four setup copies | Savings vs targeted `rg` | Savings vs broad `rg` |
| ---: | ---: | ---: | ---: |
| 4 | 3622 | -224.84% | -213.32% |
| 44 | 3622 | -224.84% | -59.14% |
| 164 | 3622 | -224.84% | 35.73% |
| 1000 | 3622 | -224.84% | 87.53% |
| 5000 | 3622 | -224.84% | 97.69% |
| 10000 | 3622 | -224.84% | 98.86% |

If the same four questions share one setup copy in one session:

| Documents | Brain including one setup copy | Savings vs targeted `rg` | Savings vs broad `rg` |
| ---: | ---: | ---: | ---: |
| 4 | 1342 | -20.36% | -16.09% |
| 44 | 1342 | -20.36% | 41.04% |
| 164 | 1342 | -20.36% | 76.19% |
| 1000 | 1342 | -20.36% | 95.38% |
| 5000 | 1342 | -20.36% | 99.15% |
| 10000 | 1342 | -20.36% | 99.58% |

In a new Python process with no conversation history, the Brain found **4/4 facts** at the largest measured size. The stored memory Markdown totals **1,286,053 tokens**; it is not sent in full to the agent. The first query in that fresh process took **7874.45 ms**, including model startup.

## Method and limitations

`rg` columns count actual `rg -l` stdout plus the full text of one selected document. The targeted search uses an exact technical keyword and ideal file selection. The broad search uses terms shared by every synthetic document; its path listing grows with the corpus. Each question includes its own discovery output, even in the one-session calculation. The Brain column counts the actual `brain_search` context, including query, titles, and scores. Its `token_budget` is an internal approximation, while this report counts output with `cl100k_base`.

Instruction and schema costs depend on how each MCP client presents and bills them. No builder reasoning, retries, output, task success, or memory authoring cost was measured. The four facts and distractors were written for this benchmark, and the budget was chosen during development. These results show behavior on this corpus, not a universal saving rate. Search time includes checking Markdown for changes, query embedding, and ranking. It excludes process startup and the separately reported new-chunk indexing.

Run `python benchmarks/growth.py --profile full` after installing `.[benchmark]` and downloading the model. Raw results: `benchmarks/results/growth.json`. Use `--profile quick` for the 4/44/164-document smoke test.
