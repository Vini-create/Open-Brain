# Publishing and maintaining Open Brain

The public repository is [Vini-create/Open-Brain](https://github.com/Vini-create/Open-Brain). The Python package and CLI are named `second-brain-local` and `brain` respectively.

Before publishing changes, run the checks in [Benchmarking](BENCHMARKS.md), review generated `.brain/` Markdown and benchmark fixtures for public content, and check that the README's size-to-savings table matches `benchmarks/results/growth.json`. The test suite checks that table. `.gitignore` excludes the virtual environment, local index, history, and machine-specific MCP configuration.

In a normal Git checkout:

```bash
git status
git add .
git commit -m "Describe the change"
git push origin main
```

If working from a source export without Git history, clone the public repository and copy changed source files into that checkout before committing. Do not publish the generated SQLite index or machine-local MCP paths.

GitHub Actions runs tests and a quick growth benchmark on pushes and pull requests. Its manual trigger runs the full growth benchmark and analytical scenario generation. Benchmark percentages describe retrieval context under the documented baselines, not measured end-to-end LLM bills.
