# Multilingual retrieval robustness

A separate local quality check uses four fact-bearing memories, 996 synthetic distractors that share common terms, and three fixed questions per fact: one original and two paraphrases in English or Portuguese. The questions were written before running this evaluation. No LLM or API is called.

Model: `intfloat/multilingual-e5-small` on CPU. Tokenizer: cl100k_base (tiktoken). Corpus: 1,000 indexed memories and matching project documents. Machine: 12th Gen Intel(R) Core(TM) i5-12450H.

| Approximate budget/query | Questions | Correct memory first | Correct memory returned | Exact fact in context | Actual payload tokens | Median search ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 180 | 12 | 12/12 | 12/12 | 12/12 | 1,667 | 433.61 |
| 400 | 12 | 12/12 | 12/12 | 12/12 | 3,818 | 432.38 |

## Per-question evidence

The fact check tests for a predefined unique string in the actual context returned to the agent. `top1` and `returned` compare document IDs; `returned` may include fewer than five items because of the budget.

| Case | Form | Budget | Top 1 | Returned | Fact present | Payload tokens |
| --- | --- | ---: | --- | --- | --- | ---: |
| auth | original | 180 | yes | yes | yes | 138 |
| auth | original | 400 | yes | yes | yes | 322 |
| auth | English paraphrase | 180 | yes | yes | yes | 134 |
| auth | English paraphrase | 400 | yes | yes | yes | 315 |
| auth | Portuguese paraphrase | 180 | yes | yes | yes | 138 |
| auth | Portuguese paraphrase | 400 | yes | yes | yes | 320 |
| queue | original | 180 | yes | yes | yes | 141 |
| queue | original | 400 | yes | yes | yes | 316 |
| queue | English paraphrase | 180 | yes | yes | yes | 135 |
| queue | English paraphrase | 400 | yes | yes | yes | 311 |
| queue | Portuguese paraphrase | 180 | yes | yes | yes | 140 |
| queue | Portuguese paraphrase | 400 | yes | yes | yes | 319 |
| tenant | original | 180 | yes | yes | yes | 141 |
| tenant | original | 400 | yes | yes | yes | 320 |
| tenant | English paraphrase | 180 | yes | yes | yes | 136 |
| tenant | English paraphrase | 400 | yes | yes | yes | 316 |
| tenant | Portuguese paraphrase | 180 | yes | yes | yes | 143 |
| tenant | Portuguese paraphrase | 400 | yes | yes | yes | 320 |
| audit | original | 180 | yes | yes | yes | 137 |
| audit | original | 400 | yes | yes | yes | 319 |
| audit | English paraphrase | 180 | yes | yes | yes | 142 |
| audit | English paraphrase | 400 | yes | yes | yes | 318 |
| audit | Portuguese paraphrase | 180 | yes | yes | yes | 142 |
| audit | Portuguese paraphrase | 400 | yes | yes | yes | 322 |

## Limits

This is an authored synthetic set with only four underlying facts. The same facts appear in the growth benchmark, and the distractors are repetitive; the questions are not a blind production sample. The test does not compare actual builder token use or implementation success. It isolates how paraphrasing and response budgets affect local retrieval on this corpus.

Reproduce with `python benchmarks/robustness.py` after installing `.[benchmark]` and downloading the embedding model. Raw questions, IDs, token counts, and latencies are in `benchmarks/results/robustness.json`.
