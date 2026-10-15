# Local memory stability audit

Date: 2026-10-15. Scope: the standalone CLI and stdio MCP path, from canonical
Markdown through real local embeddings and SQLite vectors to returned context.
The verified local save/search contract passes the checks below. This is bounded
acceptance evidence, not a guarantee for every corpus, client or platform.

## Fixes

- Recreate ignored history directories on search/write; a fresh clone previously
  failed with `No such file or directory: .brain/history/searches.jsonl`.
- Preserve memory identity and vectors when Markdown files move or swap paths.
  Reject duplicate IDs instead of silently overwriting a record.
- Commit each index synchronization in one transaction. Build a replacement
  database before replacing the live index; embedding failures preserve it.
- Serialize writes and rebuilds with a per-project thread/process lock and use
  unique temporary Markdown filenames. Reads use a consistent SQLite snapshot.
- Restore a missing index even when remembering an unchanged fact.
- Validate embedding count, dimensions, finite components and nonzero vectors.
  Status exposes vector counts and missing/orphaned vectors; search rejects an
  inconsistent vector index with instructions to rebuild.
- Honor MCP tag filters and reject explicit zero search limits. Preserve stable
  keys across title changes and persist record data instead of ignoring it.
- Add agent CLI fallback and a retrieval check after saving. Initialization and
  MCP instruction upgrades preserve custom rules.
- Repair obsolete benchmark imports after the MCP module split. CI now fails
  when detailed or multilingual fact-recovery contracts regress.

## Acceptance evidence

`OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 .venv/bin/python -m pytest -q`:
**33 passed, 1 skipped**. Fish is unavailable. Existing tests include project
isolation, initialization/upgrades, installation shells, deletion, persistence,
map escaping and the sqlite-vec 4,096-neighbor boundary. New acceptance cases
in `tests/test_stability.py` cover:

- Checkout without ignored index/history directories and idempotent recovery.
- Renames, path swaps, duplicate IDs and deletions with matching chunk/vector IDs.
- Injected embedding failures during incremental synchronization and rebuild,
  retaining the previous database, followed by successful recovery.
- Real E5 vectors: 384 finite components, unit norm, stored float32/JSON
  agreement, agreement with a fresh passage embedding, independent NumPy cosine
  comparison, and Portuguese semantic matching against English memories.
- Updates replacing the old fact; missing-vector detection and rebuild repair.
- MCP initialize → remember → filtered paraphrased search → recoverable error
  → status, followed by retrieval from a separate process after server exit.
- Concurrent threads including a rebuild, plus three separate writer processes.
  Separate-process storage tests use fixed vectors; semantic tests use E5.
- MCP stable-key title updates, data/tag preservation and status updates for
  both keyed and legacy title-identified records.

Environment: Linux x86_64, Intel i5-12450H, Python 3.14.7,
PyTorch 2.14.1+cpu, sqlite-vec 0.1.9. No project content was sent to an embedding
or LLM service. Optional benchmark dependencies/tokenizer were downloaded.

Follow-up before publication: three other standalone Brains had their protocols
and shared-runtime MCP paths upgraded. All pre-existing canonical files were
preserved by hash, and searches plus real MCP initialize/status checks passed
with consistent vectors in each project. Backups were made before updating.

One follow-up suite run hit the existing 120-second deadline for a fresh-process
MCP search (32 passed, 1 failed, 1 skipped). The isolated test then passed in
27.50 seconds; a full rerun passed **33 tests, 1 skipped in 84.84 seconds**.
The timeout's cause was not established, and the deadline was not increased.
Cold-start timing varies on this machine; the passing results do not establish
a startup-latency guarantee. No data-integrity or returned-fact mismatch was
observed in that failure.

## Retrieval evidence

Raw detailed results: [stability-retrieval.json](benchmarks/results/stability-retrieval.json).
47 authored memories including competing summaries; 12 questions, each tested
with three budgets. Facts are checked in returned text, not just result titles.

| Estimated budget | Complete answers | Facts recovered |
| ---: | ---: | ---: |
| 180 | 10/12 | 30/36 |
| 500 | 12/12 | 36/36 |
| 900 | 12/12 | 36/36 |

Raw multilingual results: [stability-robustness.json](benchmarks/results/stability-robustness.json).
1,000 memories: four facts and 996 distractors. Twelve English/Portuguese
questions, each tested at 180 and 400 estimated tokens. At **both budgets**,
the correct memory ranked first for **12/12**, and the expected fact appeared
in the actual response for **12/12**. Warm median search was approximately
383 ms in this run; CPU threads were limited to two and other verification ran
concurrently, so this is not a controlled capacity measurement.

Reproduce after installing `.[test,benchmark]` and caching model/tokenizer:

```bash
python -m pytest -q
python benchmarks/retrieval_quality.py --label audit --output /tmp/retrieval.json --check
python benchmarks/robustness.py --check
```

The last command refreshes the ordinary robustness report; this audit keeps
separate raw outputs to preserve previous published measurements. If the
tokenizer cache is in a custom directory, set `TIKTOKEN_CACHE_DIR` accordingly.

## Agent use and limits

`AGENTS.md` points to the generated Brain protocol, and MCP initialization
returns it. The protocol asks the agent to search before work, save verified
facts after meaningful changes, and confirm recovery with a paraphrased query.
If MCP is unavailable, it requires `brain search` / `brain remember` through
the CLI. Search and change logs give evidence of actual operations.

The project's own audit knowledge was saved and checked with four paraphrased
queries about storage recovery, embedding consistency, missing-tool fallback and
readiness limits. All four recovered the required facts at budget 1,800/limit 4.
The initial compound durability question omitted a detail from a long memory;
shortening/splitting the records resolved it on recheck. The final local status
reported 16 memories, 23 chunks/vectors, no missing/orphaned vectors and
`index_consistent: true`. Coverage gaps are recorded in the "Memory coverage"
memory. These self-retrieval checks are distinct from application tests.

This audit session itself used the CLI fallback because Brain MCP tools were
not exposed in the active client. Transport acceptance used the real stdio MCP
server. These checks prove the interfaces work; they do not prove that every
external LLM/client obeys instructions. A client must load the protocol and
provide a working interface. Config generation alone does not establish that.

The retrieval fixtures are synthetic and authored, with few underlying facts;
they do not establish universal recall or task success. Tight budgets can omit
facts: use focused subquestions or raise the budget. Scores are relative ranks,
not confidence, and the best passage per document can omit another passage.
Memory can be stale; verify source before editing. No paired LLM productivity
or total token-cost study was performed.

This run did not validate a live linked remote service, external-client GUI
configuration, Docker, Windows/macOS, power-loss durability or large-corpus
performance beyond existing historical reports. CI is configured for Python
3.10/3.12; this local run used 3.14.7. Core writes remain in canonical Markdown
if later indexing fails, and future searches report that failure until fixed.
