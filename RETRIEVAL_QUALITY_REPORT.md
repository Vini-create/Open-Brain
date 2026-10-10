# Detailed retrieval quality comparison

## Measured results

The same fixed public corpus and queries were run on the previous engine (`4045ab8`) and the updated engine. Both used local CPU `intfloat/multilingual-e5-small` embeddings. No LLM or embedding API was called.

The corpus has **47 memories**: four focused contracts, three project summaries and forty integration summaries competing for the same vocabulary. Twelve questions use ordinary language rather than filenames or function names. Each question requires three predefined facts; a complete answer must contain all three in the actual returned context. No tags or type filters were supplied.

| Estimated budget per question | Before: complete answers | After: complete answers | Before: facts recovered | After: facts recovered | Before: actual tokens, all 12 queries | After: actual tokens, all 12 queries |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 180 | 6/12 | 10/12 | 18/36 | 30/36 | 1,225 | 1,265 |
| 500 | 6/12 | 12/12 | 18/36 | 36/36 | 3,223 | 3,226 |
| 900 | 6/12 | 12/12 | 18/36 | 36/36 | 4,601 | 4,275 |

**At 500 estimated tokens, complete fact recovery improved from 50% to 100% with essentially the same measured payload** (3,223 versus 3,226 tokens across twelve queries). This demonstrates better retrieval at a bounded context size; it is not a measurement of total LLM token saving. Actual token counts use `cl100k_base`, while CLI budgets use the documented character estimate.

## What changed

- Smaller, sentence-aware overlapping passages; title and tags inform local embeddings.
- English/Portuguese common words are excluded from keyword coverage.
- Cosine scores are calibrated within the filtered candidate set before applying hybrid weights.
- Budgets of at least 350 estimated tokens reserve room for up to three memories.
- Truncation selects query-matching sentence windows rather than always taking the introduction.
- Existing indexes automatically refresh their passage format once; Markdown stays canonical.
- Agent instructions now include a detailed coverage checklist and incremental updates for contracts, state transitions, failure cases and validation.

## Remaining failures at 180 tokens

- **storage**: Where does conversation history live and when is it removed? Missing: SQLite, workspace.db, 45 days.
- **transport**: How is the desktop connection established and kept up to date? Missing: 127.0.0.1, SSE, /health.

## Reproduce

Install the benchmark dependencies and download the public embedding weights as described in [Installation](docs/INSTALLATION.md). The first `tiktoken` use may download its public tokenizer file; it does not send project text to an API.

```sh
python benchmarks/retrieval_quality.py --label improved --output /tmp/retrieval-after.json
```

For a paired comparison, export or check out commit `4045ab8` separately, then run the **same current benchmark file** with the old package selected through `PYTHONPATH`:

```sh
PYTHONPATH=/absolute/path/to/old-checkout/src python benchmarks/retrieval_quality.py --label before-4045ab8 --output /tmp/retrieval-before.json
```

Raw evidence: [before](benchmarks/results/retrieval-before.json), [after](benchmarks/results/retrieval-after.json), [corpus and queries](benchmarks/retrieval_quality.py). The fixture is public and contains no private Jarvis project content.

## Limits

This is an authored development set, not a blind production evaluation. Its forty integration distractors are repetitive, and there are only four underlying subjects. It measures exact fact strings in context, not understanding, successful implementation or total builder usage. It does not establish universal recall or massive-project latency. Scores are relative within each query and candidate set, not probabilities. A large stored corpus cannot guarantee that unrecorded details are available or that every fact fits in one short answer. Source audits and focused follow-up searches remain necessary.

Earlier token-saving and growth reports describe the previous engine and their recorded runs; these retrieval changes do not retroactively update those measurements.
