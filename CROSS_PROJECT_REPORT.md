# Cross-project retrieval validation

## Scope

Five independent, synthetic projects cover payment deduplication and inventory, late-arriving data and atomic publication, offline mobile edits and privacy, infrastructure releases and credential rotation, and game prediction and crash-safe saves. These subjects and questions differ from the desktop-memory benchmark used to develop the previous ranking changes.

Each project contains 14 memories: three focused contracts, three summaries and eight distinct distractors. The 30 fixed questions (English and Portuguese) each require three specific facts. They were authored before the initial run; the ranking implementation was not changed during this evaluation. No tags or type filters were used. The default limit is eight results.

These are memory-retrieval simulations, not tests of five real applications. All embeddings and searches ran locally on CPU with `intfloat/multilingual-e5-small`; no LLM API was used.

## Complete fact recovery

| Project | 180 estimated tokens | 500 estimated tokens | 900 estimated tokens |
| --- | ---: | ---: | ---: |
| Commerce | 6/6 | 6/6 | 6/6 |
| Data pipeline | 5/6 | 6/6 | 6/6 |
| Mobile notes | 4/6 | 6/6 | 6/6 |
| Infrastructure | 6/6 | 6/6 | 6/6 |
| Multiplayer game | 4/6 | 5/6 | 5/6 |
| **Total** | **25/30** | **29/30** | **29/30** |

**At 500 estimated tokens: 29/30 complete answers (96.7%), or 87/90 expected facts.** At 180 estimated tokens: 25/30 (83.3%). These percentages apply to this authored set, not all possible projects.

## Remaining default-search failure

- Project: Multiplayer game
- Question: Como a simulação corrige uma divergência com o servidor sem perder os comandos do jogador?
- Missing facts: 8 frames, state_digest, confirmed_tick.

Raising the budget to 900 did not fix this case: the correct memory was outside the returned candidates. A more specific follow-up recovered all three facts at 500 estimated tokens:

> Qual é a janela de rollback e como o cliente reconcilia seu estado com a simulação confirmada do servidor?

**The follow-up was authored after inspecting the failure.** It is recorded separately and does not turn the original 29/30 result into 30/30. The model and hybrid ranking can still miss a broad multilingual paraphrase.

## Result-limit sensitivity

The initial run used an explicit limit of five results: 28/30 questions were complete at both 500 and 900 estimated tokens. Repeating the identical questions with the product default of eight results recovered one additional case. Both raw runs are retained; the original questions were not replaced.

## Operational checks

**30/30 checks passed** across five projects:

- Incremental indexing did not re-embed unchanged memories.
- A fresh CLI process reopened each local Brain and found the expected record count.
- Sixty searches using other projects’ questions returned no foreign knowledge IDs.
- Replacing a memory removed its obsolete indexed passage.
- Deleting a memory removed its document and chunks from the index.
- Five fresh MCP server processes returned the same context as direct search, without tool errors.

The temporary project roots and their indexes were separate; only public embedding weights were shared. The private Jarvis Brain was not modified by these simulations.

## Tokens and limits

- Budget 180: 3,054 actual `cl100k_base` response tokens across 30 queries.
- Budget 500: 8,536 actual `cl100k_base` response tokens across 30 queries.
- Budget 900: 8,937 actual `cl100k_base` response tokens across 30 queries.

CLI budgets are character estimates, not exact tokenizer caps. These output counts do not measure total LLM usage or savings. The corpora are small, authored and not a blind production sample; these tests do not establish large-project latency or universal semantic recall. A successful fact-string check is not proof of application correctness or complete source coverage. Focused follow-up and source verification remain necessary.

## Reproduce

Install the benchmark dependencies and public model weights following [Installation](docs/INSTALLATION.md), then:

```sh
python benchmarks/cross_project.py
python benchmarks/cross_project.py --limit 5 --output /tmp/cross-project-limit5.json
```

Evidence: [fixed fixtures](benchmarks/fixtures/cross-project.json), [default-limit results](benchmarks/results/cross-project.json), [initial limit-five results](benchmarks/results/cross-project-limit5.json), [script](benchmarks/cross_project.py). The result includes the fixture SHA-256, every original question, recovered facts, actual tokens, operational checks and the explicitly marked refinement.
