# Benchmarking and token claims

This project has three levels of evidence. **Measured retrieval payload** is the exact text returned by a local search. **Projected payload** is arithmetic using measured calibration values and explicit assumptions. **Actual builder usage** requires paired runs of the same task with and without Brain; that measurement has not been collected for this repository.

| Evidence | Script | Output | What it checks |
| --- | --- | --- | --- |
| Repository questions | `benchmarks/measure.py` | [`BENCHMARK_REPORT.md`](../BENCHMARK_REPORT.md) | Ten questions, selected source excerpts, multiple budgets, exact fact strings. |
| Growing synthetic corpus | `benchmarks/growth.py --profile full` | [`GROWTH_REPORT.md`](../GROWTH_REPORT.md) | 4 to 10,000 documents, four facts, targeted and broad `rg`, new-process recall, latency. |
| Query paraphrases | `benchmarks/robustness.py` | [`ROBUSTNESS_REPORT.md`](../ROBUSTNESS_REPORT.md) | Twelve English/Portuguese questions, two budgets, first-result and returned-context accuracy. |
| Different project domains | `benchmarks/cross_project.py` | [`CROSS_PROJECT_REPORT.md`](../CROSS_PROJECT_REPORT.md) | Five independent synthetic projects, 30 questions, three budgets, isolation, updates, deletion and fresh-process MCP. |
| Giant-project arithmetic | `benchmarks/project_scenarios.py` | [`SCENARIOS.md`](SCENARIOS.md) | 20k to 1M documents under stated retrieval, MCP, session, and common-input assumptions. |
| Paired builder traces | `benchmarks/compare_codex_traces.py` | JSON output when traces are supplied | Actual input, cache, output, and total counters for provided comparable runs. |

## Reproduce the measured benchmarks

After following [Installation guide](INSTALLATION.md) and downloading the model:

```bash
python -m pip install -e '.[test,benchmark]'
python -m pytest -q
python benchmarks/measure.py
python benchmarks/robustness.py
python benchmarks/growth.py --profile full
python benchmarks/project_scenarios.py
```

The scripts require `rg` and `tiktoken`'s `cl100k_base` tokenizer file. The tokenizer file may need one initial public download. If it is unavailable, measurement fails rather than silently switching to an estimate. `growth.py --profile quick` runs only 4, 44, and 164 documents and writes ignored `GROWTH_QUICK_REPORT.md` and `growth-quick.json`, preserving the published full measurements. `full` also measures 1,000, 5,000, and 10,000. A full run embeds thousands of local texts on CPU and takes longer than the unit tests.

The growth report records the CPU, Python, PyTorch, and sqlite-vec versions used for its latency and index-size numbers. Token counts are based on actual returned text; timing depends on hardware and cache state.
Its index timing now includes regeneration of the per-project `map.html`, and it reports the map's disk size separately from SQLite.

The README's size-to-savings table is calculated from `benchmarks/results/growth.json`. For each size, it adds one measured copy of agent instructions and MCP tool schemas to the four Brain responses, then compares that with four broad `rg` discovery outputs plus selected files. Its capped column applies `min(actual_tokens, 8000)` to **each** conventional response before summing. The cap is simulated accounting on measured output; it is not a run that verifies fact retrieval after truncation. The uncapped column can be much larger than a real model prompt.

Those setup counts describe the instruction payload recorded in that run. The current onboarding instructions include an additional project-coverage audit. Reproduce the benchmark to measure the current instruction cost; initial code inspection, memory creation, and subsequent memory maintenance are additional agent costs that the retrieval table does not measure.

## How to read the numbers

`brain_search` returns the query and selected titles, scores, and snippets. These output tokens are measured with `cl100k_base`. The CLI's `--token-budget` is a rough local bound based on characters, so measured output may differ from the requested number. The stored Markdown corpus is **not** automatically put into the agent prompt. The agent may still read source code to implement a change.

The targeted baseline runs `rg` with a technical keyword that identifies the right document, then reads that document. This is a strong conventional workflow and can beat Brain after MCP setup. The broad baseline uses terms shared by many synthetic documents and includes the `rg -l` path list plus one document for each question. It models a costly discovery path, not every way a skilled agent might search. Both baselines have their exact output counted with the same tokenizer.

The [robustness report](../ROBUSTNESS_REPORT.md) examines query wording rather than a code-search baseline. It checks whether the correct memory ranks first, appears among returned items, and contributes its exact fact to the token-bounded response. It includes English and Portuguese paraphrases but still uses authored synthetic facts.

Instruction Markdown and MCP schemas have their own prompt cost. Reports show one copy per shared session and a copy per fresh session. Some clients may resend or cache these differently. Adding common prompt input reduces the **percentage** of total input saved even when absolute retrieval savings stay the same. Creating and updating memories also has a cost; it is unmeasured in the empirical benchmark and explicitly hypothetical where added in scenario projections.

## Large projects: measured and hypothetical

The growth benchmark measures recall and latency through 10,000 synthetic documents. The [large-project scenarios](SCENARIOS.md) extend the observed broad-discovery token slope to 20,000, 100,000, and 1,000,000 documents while assuming Brain returns the same payload and facts. The uncapped `rg` projections can exceed a model context window; capped scenarios show a more bounded comparison, but cannot establish which facts would survive the cap. **No search, indexing, retrieval-quality, or builder-token result has been measured above 10,000 documents.**

The current hybrid ranker scores every chunk. Indexing time and search latency can become more important than prompt size at large scales. Use the empirical latency column as the observed range, and measure your own corpus before treating the projections as a capacity claim.

## What would prove end-to-end savings

Use two equivalent checkouts and the same model, client, tasks, and fresh-session policy. Preload Brain memories in one checkout. Verify both runs finish the tasks to equivalent quality. Collect actual token usage per turn, including cached input, output, and reasoning when available, plus file reads, MCP calls, elapsed time, and memory-authoring effort. Repeat across projects and task types. `benchmarks/compare_codex_traces.py` computes paired totals from supplied JSONL traces; it does not run a builder or invent usage. Until such a study exists, the public claim is **reduced retrieval context in the measured scenarios**, not a universal reduction in LLM bills.
## Current retrieval quality

The [paired retrieval comparison](../RETRIEVAL_QUALITY_REPORT.md) measures
the newer search implementation against `4045ab8` with identical authored
memories, queries and budgets. It measures fact recovery and actual response
tokens. Older savings reports retain their historical engine measurements;
they should not be read as measurements of the updated retrieval engine.
