# Publishing and maintaining Open Brain

The public repository is [Vini-create/Open-Brain](https://github.com/Vini-create/Open-Brain). The Python package and CLI are named `second-brain-local` and `brain` respectively.

Before publishing changes, use the relevant checks in
[Contributing](../CONTRIBUTING.md) and [Benchmarking](BENCHMARKS.md). Review
canonical `.brain/` Markdown and fixtures for public content; the root ignore
rules exclude indexes/history, not every knowledge file. Keep the English and
Portuguese READMEs consistent. The README's historical size-to-savings table is
checked against `benchmarks/results/growth.json` by the test suite.

In a normal Git checkout:

```bash
git status --short
git diff --check
git diff
```

Stage the intended files, inspect `git diff --cached`, commit with a description
of the final change and push the intended branch. Follow the repository's PR or
branch policy. Do not publish generated SQLite indexes, model weights or
machine-local MCP paths. If working from a source export, use a real clone for
publication so existing history is preserved.

After pushing, inspect [GitHub Actions](https://github.com/Vini-create/Open-Brain/actions)
for the pushed commit. Local results do not prove that a remote workflow passed.
CI runs tests, repository and multilingual benchmarks, a detailed fact-recovery
gate and quick growth. Its manual trigger runs full growth and scenarios.
Benchmark percentages describe retrieval context, not measured total LLM bills.

For a public test announcement, link the repository and its Portuguese README,
describe the project as an early local-memory release, and invite a save/search
test plus a fresh agent session. Link the issue chooser so people can report
their environment and a reproducible result. GitHub reads the root README,
CONTRIBUTING file and `.github/ISSUE_TEMPLATE/` files after they are pushed;
no separate documentation build is required.
