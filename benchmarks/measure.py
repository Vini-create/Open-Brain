"""Reproducible, API-free measurement of builder context saved by Brain search."""

import argparse
import ast
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from second_brain.core import AGENT_INSTRUCTIONS, initialize, remember
from second_brain.mcp import TOOLS
from second_brain.storage import index
from second_brain.config import load_config

SOURCE_ROOT = Path(__file__).resolve().parents[1]
BUDGETS = [150, 250, 400, 600]

MEMORIES = [
    ("architecture", "Markdown é a fonte canônica",
     "As memórias duráveis ficam em Markdown com YAML Front Matter em .brain/project e .brain/knowledge. "
     "O SQLite é um índice descartável; brain rebuild reconstrói tudo dos arquivos Markdown.", 0.95),
    ("decision", "Indexação incremental por hash",
     "brain index compara o SHA-256 do Markdown com o hash no banco. Só documentos novos ou alterados "
     "geram embeddings; documentos sem mudança não são recalculados. brain rebuild força a reconstrução integral.", 0.95),
    ("decision", "Embeddings locais em CPU",
     "O modelo padrão é intfloat/multilingual-e5-small, com 384 dimensões, rodando na CPU. "
     "Não há provider nem API key. brain model download baixa pesos uma vez; o uso normal carrega apenas o cache local.", 0.95),
    ("architecture", "Índice vetorial SQLite",
     "Os vetores ficam em .brain/index/brain.db com sqlite-vec, tabela vec0 e distância cosseno. "
     "FAISS não é usado. Os Markdown continuam sendo a fonte canônica.", 0.9),
    ("feature", "Servidor MCP local",
     "brain init cria .mcp.json e .brain/mcp.json com o comando local. brain mcp --project CAMINHO "
     "serve via stdio as ferramentas brain_search, brain_remember e brain_status.", 0.95),
    ("rule", "Privacidade local",
     "O conteúdo do projeto não é enviado a API externa. Não há telemetria nem chamada a API de LLM. "
     "Busca e indexação funcionam offline após baixar os pesos do modelo uma vez.", 0.9),
    ("decision", "Ranking híbrido e orçamento",
     "brain_search combina similaridade vetorial via sqlite-vec (peso 0.55), palavras-chave (0.20), "
     "importance (0.15) e recency (0.10). token_budget limita o contexto retornado; o padrão é 2000 tokens aproximados.", 0.95),
    ("architecture", "Atualização de memórias e histórico",
     "brain_remember valida tipo, título e conteúdo, evita duplicatas por conteúdo, cria Markdown com YAML Front Matter "
     "e indexa automaticamente. A identidade usa tipo e título. Atualizações preservam metadata e guardam "
     "a versão anterior em .brain/history/versions/.", 0.95),
    ("feature", "Inicialização do projeto",
     "brain init cria .brain/project/idea.md, overview.md, goals.md, knowledge, config.json, index/brain.db, "
     "AGENT_BRAIN.md e configuração MCP. O agente deve buscar contexto antes de explorar código.", 0.85),
]

TASKS = [
    {"id": "indexacao", "query": "Editei um Markdown. Como reindexar só o necessário e reconstruir o índice?",
     "expected": ["SHA-256", "brain index", "brain rebuild"],
     "excerpts": [("src/second_brain/storage.py", "index"), ("src/second_brain/documents.py", "parse")]},
    {"id": "mcp", "query": "Como um agente novo conecta ao MCP local e quais ferramentas ele pode chamar?",
     "expected": [".mcp.json", "brain_search", "brain_remember", "brain_status"],
     "excerpts": [("src/second_brain/mcp.py", "TOOLS"), ("src/second_brain/mcp.py", "serve"),
                  ("src/second_brain/core.py", "initialize")]},
    {"id": "embedding", "query": "Qual modelo de embedding roda na CPU sem provider nem API key?",
     "expected": ["intfloat/multilingual-e5-small", "CPU", "API key"],
     "excerpts": [("src/second_brain/embedding.py", "_model"), ("src/second_brain/embedding.py", "embed"),
                  ("src/second_brain/config.py", "DEFAULT_CONFIG")]},
    {"id": "historico", "query": "Ao atualizar uma decisão, como evitar duplicatas e recuperar a versão anterior?",
     "expected": ["duplicatas", ".brain/history/versions/", "YAML"],
     "excerpts": [("src/second_brain/core.py", "remember"), ("src/second_brain/documents.py", "render")]},
    {"id": "busca", "query": "Como a busca combina vetores e palavras e limita o contexto enviado ao LLM?",
     "expected": ["0.55", "0.20", "token_budget", "sqlite-vec"],
     "excerpts": [("src/second_brain/core.py", "search"), ("src/second_brain/storage.py", "vector_scores"),
                  ("src/second_brain/config.py", "DEFAULT_CONFIG")]},
]

for item in TASKS:
    item["set"] = "principal"

PARAPHRASES = [
    ("indexacao_parafrase", "indexacao",
     "Mudamos uma decisão num arquivo .md. Como sincronizar a base sem processar tudo de novo?"),
    ("mcp_parafrase", "mcp",
     "Quero conectar um agente ao servidor do projeto. Qual configuração e quais operações ele recebe?"),
    ("embedding_parafrase", "embedding",
     "Preciso de chave de serviço externo para vetorizar memórias ou o modelo roda nesta máquina?"),
    ("historico_parafrase", "historico",
     "Onde fica o snapshot antigo quando mudo um conhecimento e como o sistema detecta repetição?"),
    ("busca_parafrase", "busca",
     "Qual fórmula prioriza memórias e como corto o tamanho do texto devolvido para o agente?"),
]
for new_id, base_id, query in PARAPHRASES:
    base = next(item for item in TASKS if item["id"] == base_id)
    TASKS.append({"id": new_id, "query": query, "expected": base["expected"],
                  "excerpts": base["excerpts"], "set": "paráfrase"})


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()


def counter():
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return lambda text: len(encoding.encode(text)), "cl100k_base (tiktoken)"
    except Exception as exc:
        raise RuntimeError(
            "This benchmark requires tiktoken and the cl100k_base tokenizer file. "
            "Install .[benchmark] and make the tokenizer available before measuring."
        ) from exc


def extract_symbol(path: Path, symbol: str) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        name = getattr(node, "name", None)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [target.id for target in targets if isinstance(target, ast.Name)]
            if symbol in names:
                return ast.get_source_segment(source, node) or ""
        elif name == symbol:
            return ast.get_source_segment(source, node) or ""
    raise ValueError(f"Symbol not found: {path}:{symbol}")


def prepare_project(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE_ROOT / "src" / "second_brain", destination / "src" / "second_brain",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(SOURCE_ROOT / "README.md", destination / "README.md")
    shutil.copy2(SOURCE_ROOT / "pyproject.toml", destination / "pyproject.toml")
    initialize(destination)
    brain = destination / ".brain" / "project"
    (brain / "idea.md").write_text(
        "# Ideia\n\nSecond Brain Local mantém conhecimento durável de projetos de software para agentes "
        "reduzirem releitura de código e tokens de contexto entre sessões.\n", encoding="utf-8")
    (brain / "overview.md").write_text(
        "# Visão operacional\n\nCLI Python com memórias Markdown, embeddings locais na CPU, "
        "índice SQLite + sqlite-vec e servidor MCP via stdio.\n", encoding="utf-8")
    (brain / "goals.md").write_text(
        "# Objetivos\n\nRecuperar decisões, arquitetura e regras em poucas memórias relevantes "
        "e reduzir o contexto enviado a agentes novos.\n", encoding="utf-8")
    index(destination, load_config(destination))
    for kind, title, content, importance in MEMORIES:
        remember(destination, type=kind, title=title, content=content, importance=importance,
                 status="implemented" if kind == "feature" else "active")


def worker(project: Path) -> None:
    from second_brain.core import search

    requests = json.load(sys.stdin)
    responses = []
    for task in requests:
        for budget in BUDGETS:
            found = search(project, task["query"], limit=5, token_budget=budget)
            responses.append({"id": task["id"], "budget": budget, "context": found["context"],
                              "ids": [item["id"] for item in found["results"]],
                              "latency_ms": found["duration_ms"]})
    print(json.dumps(responses, ensure_ascii=False))


def run(project: Path) -> dict:
    prepare_project(project)
    process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(project)],
                             input=json.dumps(TASKS), text=True, capture_output=True, check=True, timeout=300)
    found = {(item["id"], item["budget"]): item for item in json.loads(process.stdout)}
    tokens, method = counter()
    items = []
    for task in TASKS:
        excerpts = "QUERY\n" + task["query"] + "\n\n" + "\n\n".join(
            f"FILE {path} :: {symbol}\n{extract_symbol(SOURCE_ROOT / path, symbol)}"
            for path, symbol in task["excerpts"])
        paths = list(dict.fromkeys(path for path, _ in task["excerpts"]))
        whole_files = "QUERY\n" + task["query"] + "\n\n" + "\n\n".join(
            f"FILE {path}\n{(SOURCE_ROOT / path).read_text(encoding='utf-8')}" for path in paths)
        for budget in BUDGETS:
            result = found[(task["id"], budget)]
            missing = [fact for fact in task["expected"] if normalize(fact) not in normalize(result["context"])]
            items.append({"task": task["id"], "set": task["set"], "query": task["query"], "budget": budget,
                          "baseline_excerpt_tokens": tokens(excerpts), "baseline_whole_file_tokens": tokens(whole_files),
                          "brain_tokens": tokens(result["context"]), "all_facts_found": not missing,
                          "missing_facts": missing, "returned_ids": result["ids"],
                          "latency_ms": result["latency_ms"], "context": result["context"],
                          "baseline_symbols": task["excerpts"], "baseline_excerpt_text": excerpts,
                          "baseline_whole_file_paths": paths})
    summaries = []
    for budget in BUDGETS:
        group = [item for item in items if item["budget"] == budget]
        focused = sum(item["baseline_excerpt_tokens"] for item in group)
        whole = sum(item["baseline_whole_file_tokens"] for item in group)
        brain = sum(item["brain_tokens"] for item in group)
        summaries.append({"budget": budget, "tasks_with_all_facts": sum(item["all_facts_found"] for item in group),
                          "task_count": len(group), "focused_baseline_tokens": focused,
                          "whole_file_baseline_tokens": whole, "brain_tokens": brain,
                          "max_actual_tokens": max(item["brain_tokens"] for item in group),
                          "focused_savings_pct": round(100 * (1 - brain / focused), 2),
                          "whole_file_savings_pct": round(100 * (1 - brain / whole), 2),
                          "median_latency_ms": round(statistics.median(item["latency_ms"] for item in group), 2)})
    chosen = next((summary for summary in summaries if summary["tasks_with_all_facts"] == len(TASKS)
                   and summary["max_actual_tokens"] <= summary["budget"]), None)
    memory_text = "\n".join(f"{title}\n{content}" for _, title, content, _ in MEMORIES)
    brain = project / ".brain"
    stored_markdown = list((brain / "project").rglob("*.md")) + list((brain / "knowledge").rglob("*.md"))
    stored_markdown_tokens = sum(tokens(path.read_text(encoding="utf-8")) for path in stored_markdown)
    first_query_ms = items[0]["latency_ms"]
    warm_median_ms = round(statistics.median(item["latency_ms"] for item in items[1:]), 2)
    return {"method": method, "model": load_config(project)["embedding"]["model"],
            "scenario": "Dez consultas sobre cinco temas (cinco principais e cinco paráfrases) em um processo novo após a ingestão, sobre o código real deste repositório.",
            "one_time_memory_text_tokens": tokens(memory_text), "budgets": BUDGETS, "chosen_budget": chosen["budget"] if chosen else None,
            "agent_instruction_tokens": tokens(AGENT_INSTRUCTIONS),
            "mcp_tool_schema_tokens": tokens(json.dumps(TOOLS, ensure_ascii=False)),
            "stored_markdown_tokens": stored_markdown_tokens,
            "first_query_ms": first_query_ms, "warm_median_ms": warm_median_ms,
            "summaries": summaries, "tasks": items}


def markdown(report: dict) -> str:
    lines = ["# Repository-context benchmark", "",
             "This experiment saves durable facts about Second Brain in a temporary local project, "
             "then asks ten questions (five topics and five paraphrases) in a fresh process. "
             "No LLM or API is called.", "",
             f"CPU embedding model: `{report['model']}`. Tokenizer: {report['method']}.", "",
             "| Approximate budget | Questions with all facts | Selected source excerpts | Brain payload | Largest actual response | Savings vs excerpts | Savings vs whole files |",
             "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in report["summaries"]:
        lines.append(f"| {row['budget']} | {row['tasks_with_all_facts']}/{row['task_count']} | "
                     f"{row['focused_baseline_tokens']} | {row['brain_tokens']} | {row['max_actual_tokens']} | "
                     f"{row['focused_savings_pct']:.2f}% | {row['whole_file_savings_pct']:.2f}% |")
    chosen = next((row for row in report["summaries"] if row["budget"] == report["chosen_budget"]), None)
    if chosen:
        lines += ["", f"The smallest tested budget with complete fact coverage was "
                  f"**{chosen['budget']}**. The measured retrieval payload fell from "
                  f"**{chosen['focused_baseline_tokens']}** selected excerpt tokens to "
                  f"**{chosen['brain_tokens']}** Brain tokens "
                  f"(**{chosen['focused_savings_pct']:.2f}%** less). The first search took "
                  f"**{report['first_query_ms']:.2f} ms** including model loading; the median "
                  f"of subsequent searches was **{report['warm_median_ms']:.2f} ms**.", "",
                  "## Questions at the selected budget", "",
                  "| Question ID | Excerpt tokens | Brain tokens | Payload savings | All facts found |",
                  "| --- | ---: | ---: | ---: | --- |"]
        for item in report["tasks"]:
            if item["budget"] == chosen["budget"]:
                pct = 100 * (1 - item["brain_tokens"] / item["baseline_excerpt_tokens"])
                lines.append(f"| {item['task']} | {item['baseline_excerpt_tokens']} | "
                             f"{item['brain_tokens']} | {pct:.2f}% | "
                             f"{'yes' if item['all_facts_found'] else 'no'} |")
        sample = next(item for item in report["tasks"] if item["task"] == "embedding_parafrase"
                      and item["budget"] == chosen["budget"])
        lines += ["", "## Actual search response", "", "```text", sample["context"].strip(), "```"]
        protocol = report["agent_instruction_tokens"] + report["mcp_tool_schema_tokens"]
        once = chosen["brain_tokens"] + protocol
        each = chosen["brain_tokens"] + chosen["task_count"] * protocol
        lines += ["", "## MCP setup sensitivity", "",
                  f"Agent instructions: **{report['agent_instruction_tokens']} tokens**. JSON tool "
                  f"schemas: **{report['mcp_tool_schema_tokens']} tokens**. If both are presented "
                  f"once for all ten questions, Brain totals **{once} tokens** "
                  f"({100 * (1 - once / chosen['focused_baseline_tokens']):.2f}% below excerpts). "
                  f"If presented in ten independent sessions, Brain totals **{each} tokens** "
                  f"({100 * (1 - each / chosen['focused_baseline_tokens']):.2f}% below excerpts). "
                  "These are hypothetical prompt accounting scenarios; MCP clients can represent, "
                  "resend, or cache schemas differently.", "",
                  "## Shared input sensitivity", "",
                  "The table adds the same non-retrieval input to both workflows for each of ten "
                  "questions. It excludes MCP setup, memory authoring, output, and reasoning.", "",
                  "| Other input/question | Excerpt workflow | Brain workflow | Total input reduction |",
                  "| ---: | ---: | ---: | ---: |"]
        for common in (0, 500, 1_000, 5_000, 10_000):
            baseline = chosen["focused_baseline_tokens"] + common * chosen["task_count"]
            brain = chosen["brain_tokens"] + common * chosen["task_count"]
            lines.append(f"| {common:,} | {baseline:,} | {brain:,} | "
                         f"{100 * (1 - brain / baseline):.2f}% |")
    lines += ["", "## Interpretation", "",
              "The excerpt baseline consists of source functions chosen in advance to answer each "
              "question; the whole-file baseline includes their full files. Each question is "
              "independent. The Brain side counts the exact returned context, including query, "
              "titles, and scores. The fixture questions and sample memory are in Portuguese to "
              "exercise multilingual retrieval. Fact checks require predefined strings in that "
              "response. This "
              "favors the authored memories and is not a blind evaluation. A coding agent still "
              "needs source code to implement and verify changes; a precise `rg` query may use fewer "
              "tokens. Model tokenizers differ.", "",
              f"The authored memory titles and contents total **{report['one_time_memory_text_tokens']} "
              f"tokens**. Persisted Markdown, including front matter and project documents, totals "
              f"**{report['stored_markdown_tokens']} tokens**. The LLM cost of authoring and "
              "maintaining those memories was not measured. Neither were builder reasoning, retries, "
              "outputs, task quality, or total billed usage. This is measured retrieval context, "
              "not a measured end-to-end LLM saving.", "",
              "To measure actual builder usage, run paired tasks in equivalent checkouts with the "
              "same model and harness, verify equal task quality, collect `codex exec --json` traces, "
              "and compare them with `benchmarks/compare_codex_traces.py`. Raw queries, excerpts, "
              "responses, and counts are in `benchmarks/results/latest.json`. Reproduce with "
              "`python benchmarks/measure.py` after installing `.[benchmark]` and downloading the "
              "embedding model."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--workdir", type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return
    if args.workdir:
        if args.workdir.exists() and any(args.workdir.iterdir()):
            raise SystemExit("--workdir must point to an empty directory")
        report = run(args.workdir)
    else:
        with tempfile.TemporaryDirectory(prefix="brain-benchmark-") as folder:
            report = run(Path(folder))
    output = SOURCE_ROOT / "benchmarks" / "results"
    output.mkdir(parents=True, exist_ok=True)
    (output / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (SOURCE_ROOT / "BENCHMARK_REPORT.md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    if report["chosen_budget"] is None:
        raise SystemExit("Benchmark failed: no budget recovered all facts within the actual output limit")


if __name__ == "__main__":
    main()
