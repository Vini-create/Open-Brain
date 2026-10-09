"""Measure real retrieval payloads as a local project accumulates documents.

No LLM is called. The comparison includes stdout from actual rg discovery and
actual Brain search output, counted with the same tokenizer.
"""

import argparse
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from second_brain.config import load_config
from second_brain.core import AGENT_INSTRUCTIONS, initialize, remember, search
from second_brain.documents import now, render
from second_brain.mcp import TOOLS
from second_brain.storage import index

from measure import counter
from project_scenarios import measured_size_savings

ROOT = Path(__file__).resolve().parents[1]
QUICK_LEVELS = (0, 40, 160)
FULL_LEVELS = (0, 40, 160, 996, 4996, 9996)
BUDGET = 180
CASES = (
    {
        "id": "auth", "type": "decision", "title": "Rotação de refresh token",
        "query": "Como é feita a rotação do refresh token na autenticação?",
        "needle": "rotation_nonce", "fact": "rotation_nonce",
        "memory": "Refresh token usa cookie HTTPOnly e gira a cada renovação. O servidor compara rotation_nonce e invalida o token anterior para impedir replay.",
        "reason": "Uma credencial capturada não pode continuar válida após a renovação.",
    },
    {
        "id": "queue", "type": "rule", "title": "Idempotência de pagamentos",
        "query": "Como evitamos mensagens duplicadas na fila de pagamentos?",
        "needle": "event_id", "fact": "event_id",
        "memory": "O consumidor de pagamentos grava event_id antes do efeito financeiro e ignora entregas repetidas. A confirmação da fila só ocorre após commit.",
        "reason": "A fila pode entregar a mesma mensagem mais de uma vez.",
    },
    {
        "id": "tenant", "type": "architecture", "title": "Isolamento entre organizações",
        "query": "Como isolar dados entre organizações?",
        "needle": "organization_id", "fact": "organization_id",
        "memory": "Toda consulta de dados de cliente aplica organization_id no repositório; handlers recebem o tenant da sessão autenticada.",
        "reason": "Evitar leitura cruzada entre organizações.",
    },
    {
        "id": "audit", "type": "constraint", "title": "Retenção de auditoria",
        "query": "Quanto tempo os registros de auditoria são guardados?",
        "needle": "180 dias", "fact": "180 dias",
        "memory": "Registros de auditoria são retidos por 180 dias. A limpeza diária remove apenas registros mais antigos e preserva eventos sob investigação.",
        "reason": "Equilibrar rastreabilidade e tamanho do armazenamento local.",
    },
)


def environment() -> dict:
    cpu_model = platform.processor()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    return {"os": platform.system(), "architecture": platform.machine(),
            "python": platform.python_version(), "cpu_model": cpu_model or "unreported",
            "logical_cpus": os.cpu_count(),
            "torch": importlib.metadata.version("torch"),
            "sqlite_vec": importlib.metadata.version("sqlite-vec")}


def source_document(case: dict) -> str:
    return (
        f"# {case['title']}\n\n"
        f"## Problema\n\n{case['reason']} Esta nota descreve a regra operacional e como ela se relaciona "
        "com o desenvolvimento do serviço. O fluxo passa por handler, serviço, repositório e persistência. "
        "Mudanças devem manter a separação entre camadas e os testes de integração.\n\n"
        f"## Decisão atual\n\n{case['memory']}\n\n"
        "## Implementação e verificação\n\nAntes de alterar o fluxo, revise as chamadas afetadas, as condições de "
        "erro e os testes. Após a alteração, valide o caminho principal e a recuperação em caso de falha. "
        "As funções auxiliares da implementação vivem em módulos distintos, então esta nota deve ser "
        "conferida com o código quando for necessário editar.\n\n"
        "## Histórico\n\nA decisão foi tomada para manter comportamento previsível entre sessões. "
        "A documentação anterior descrevia apenas o caso feliz; esta versão também explicita o motivo "
        "e o efeito sobre outros componentes.\n"
    )


def add_decoys(project: Path, start: int, end: int) -> None:
    docs = project / "docs"
    knowledge = project / ".brain" / "knowledge" / "decisions"
    timestamp = now()
    for number in range(start, end):
        title = f"Nota operacional {number:03d}"
        detail = f"O módulo {number:03d} tem configuração interna de lote {number * 17 + 3}."
        (docs / f"note-{number:03d}.md").write_text(
            f"# {title}\n\nAutenticação, organizações, fila e auditoria aparecem neste módulo. "
            f"{detail}\n\nOs detalhes estão na configuração do serviço e nos testes locais.\n",
            encoding="utf-8",
        )
        metadata = {
            "id": f"decision-synthetic-{number:03d}", "type": "decision", "title": title,
            "tags": [], "importance": 0.2, "status": "active", "created_at": timestamp,
            "updated_at": timestamp, "related": [],
        }
        (knowledge / f"decision-synthetic-{number:03d}.md").write_text(
            render(metadata, f"# {title}\n\n{detail} Usa autenticação, organizações, fila e auditoria."),
            encoding="utf-8",
        )


def rg_output(project: Path, pattern: str, *, fixed: bool = False) -> str:
    command = ["rg", "-l", "-i"]
    if fixed:
        command.append("-F")
    command += [pattern, "docs"]
    result = subprocess.run(command, cwd=project, text=True, capture_output=True, check=True)
    return result.stdout


def worker(project: Path) -> None:
    responses = []
    for case in CASES:
        result = search(project, case["query"], limit=5, token_budget=BUDGET)
        responses.append({"id": case["id"], "context": result["context"],
                          "duration_ms": result["duration_ms"]})
    print(json.dumps(responses, ensure_ascii=False))


def run(project: Path, levels: tuple[int, ...] = FULL_LEVELS) -> dict:
    project.mkdir(parents=True, exist_ok=True)
    initialize(project)
    docs = project / "docs"
    docs.mkdir()
    for case in CASES:
        (docs / f"{case['id']}.md").write_text(source_document(case), encoding="utf-8")
        remember(project, type=case["type"], title=case["title"],
                 content=f"O que mudou: {case['memory']} Por quê: {case['reason']}", importance=0.95)
    tokens, method = counter()
    results = []
    previous = 0
    for decoys in levels:
        add_decoys(project, previous, decoys)
        index_started = time.monotonic()
        indexed = index(project, load_config(project))
        index_ms = round((time.monotonic() - index_started) * 1000, 2)
        previous = decoys
        discovery = rg_output(project, "autenticação|organizações|fila|auditoria")
        cases = []
        for case in CASES:
            found = search(project, case["query"], limit=5, token_budget=BUDGET)
            selected = docs / f"{case['id']}.md"
            excerpt = f"FILE docs/{selected.name}\n{selected.read_text(encoding='utf-8')}"
            targeted = rg_output(project, case["needle"], fixed=True)
            targeted_tokens = tokens(targeted + excerpt)
            broad_tokens = tokens(discovery + excerpt)
            brain_tokens = tokens(found["context"])
            cases.append({"id": case["id"], "fact_found": case["fact"].casefold() in found["context"].casefold(),
                          "brain_tokens": brain_tokens, "targeted_rg_tokens": targeted_tokens,
                          "broad_rg_tokens": broad_tokens, "latency_ms": found["duration_ms"]})
        results.append({"source_documents": decoys + len(CASES), "brain_memories": decoys + len(CASES),
                        "newly_embedded": indexed["embedded_chunks"], "cases": cases,
                        "incremental_index_ms": index_ms,
                        "database_bytes": (project / ".brain/index/brain.db").stat().st_size,
                        "map_bytes": (project / ".brain/map.html").stat().st_size,
                        "facts_found": sum(item["fact_found"] for item in cases),
                        "brain_tokens": sum(item["brain_tokens"] for item in cases),
                        "targeted_rg_tokens": sum(item["targeted_rg_tokens"] for item in cases),
                        "broad_rg_tokens": sum(item["broad_rg_tokens"] for item in cases),
                        "median_search_ms": round(statistics.median(item["latency_ms"] for item in cases), 2)})
    process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(project)],
                             text=True, capture_output=True, check=True, timeout=180)
    cold = json.loads(process.stdout)
    cold_facts = sum(case["fact"].casefold() in next(item for item in cold if item["id"] == case["id"])["context"].casefold()
                     for case in CASES)
    memory_tokens = sum(tokens(path.read_text(encoding="utf-8"))
                        for path in (project / ".brain" / "knowledge").rglob("*.md"))
    return {"tokenizer": method, "model": load_config(project)["embedding"]["model"],
            "environment": environment(),
            "approximate_search_budget": BUDGET,
            "agent_instruction_tokens": tokens(AGENT_INSTRUCTIONS),
            "mcp_tool_schema_tokens": tokens(json.dumps(TOOLS, ensure_ascii=False)),
            "levels": results, "fresh_process_facts_found": cold_facts,
            "fresh_process_queries": len(CASES),
            "fresh_process_first_ms": cold[0]["duration_ms"],
            "persisted_memory_tokens": memory_tokens}


def markdown(report: dict, *, result_name: str = "growth.json") -> str:
    cap = 8_000
    size_rows = measured_size_savings(report, cap_per_query=cap)
    lines = ["# Measured growth benchmark", "",
             "This local experiment creates project documents and matching Brain memories. Four "
             "questions check exact facts while synthetic distractors repeat common search terms. "
             "No LLM or API is called.", "",
             f"CPU embedding model: `{report['model']}`. Approximate search budget: "
             f"{report['approximate_search_budget']}. Token count: {report['tokenizer']}.", "",
             f"Environment: {report['environment']['cpu_model']} "
             f"({report['environment']['logical_cpus']} logical CPUs), "
             f"{report['environment']['os']} {report['environment']['architecture']}, "
             f"Python {report['environment']['python']}, "
             f"PyTorch {report['environment']['torch']}, "
             f"sqlite-vec {report['environment']['sqlite_vec']}.", "",
             "## Savings by project size", "",
             "Each row measures four questions in one shared session against the same number of "
             "project documents and indexed Brain memories. The Brain total includes one copy of "
             "agent instructions and MCP tool schemas. The conventional baseline is broad `rg` "
             "path discovery plus one selected file per question. A negative reduction means Brain "
             "uses more retrieval-context tokens.", "",
             f"The capped column applies an **{cap:,}-token maximum to each measured conventional "
             "search output**. It is a token-accounting simulation; it does not verify that a "
             "clipped `rg` result still contains the needed file or fact.", "",
             "| Project documents / indexed memories | Brain facts | Brain incl. setup | Broad search, uncapped | Reduction, uncapped | Reduction, 8k/query cap |",
             "| ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in size_rows:
        lines.append(f"| {row['documents']:,} | {row['facts_found']}/{row['questions']} | "
                     f"{row['brain_with_setup_tokens']:,} | "
                     f"{row['baseline_uncapped_tokens']:,} | "
                     f"{row['uncapped_reduction_pct']:.2f}% | "
                     f"{row['capped_reduction_pct']:.2f}% |")
    lines += ["", "These are **retrieval-context reductions**, not measured changes in a builder's "
              "total LLM tokens or bill. The uncapped path listing exceeds practical prompt sizes "
              "at the largest levels. Exact-keyword search can use fewer tokens than Brain after "
              "MCP setup. Search latency is reported below.", "",
              "## Full measurements", "",
             "| Documents | Facts found | Brain payload | Targeted `rg` + file | Broad `rg` + file | Savings vs targeted | Savings vs broad | Median search ms | New-chunk index s | DB MiB | Map MiB |",
             "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for level in report["levels"]:
        brain = level["brain_tokens"]
        targeted = level["targeted_rg_tokens"]
        broad = level["broad_rg_tokens"]
        lines.append(f"| {level['source_documents']} | {level['facts_found']}/{len(CASES)} | {brain} | {targeted} | {broad} | "
                     f"{100 * (1 - brain / targeted):.2f}% | {100 * (1 - brain / broad):.2f}% | "
                     f"{level['median_search_ms']:.2f} | "
                     f"{level['incremental_index_ms'] / 1000:.2f} | "
                     f"{level['database_bytes'] / 1048576:.2f} | "
                     f"{level['map_bytes'] / 1048576:.2f} |")
    protocol = report["agent_instruction_tokens"] + report["mcp_tool_schema_tokens"]
    lines += ["", "## MCP setup costs", "",
              f"The agent instructions contain **{report['agent_instruction_tokens']} tokens** "
              f"and the JSON schemas of the MCP tools contain **{report['mcp_tool_schema_tokens']} "
              f"tokens**, or **{protocol} tokens** together. These are measured text sizes, not "
              "observed client billing. If a client includes both for each of four fresh sessions:", "",
              "| Documents | Brain including four setup copies | Savings vs targeted `rg` | Savings vs broad `rg` |",
              "| ---: | ---: | ---: | ---: |"]
    for level in report["levels"]:
        total = level["brain_tokens"] + len(CASES) * protocol
        lines.append(f"| {level['source_documents']} | {total} | "
                     f"{100 * (1 - total / level['targeted_rg_tokens']):.2f}% | "
                     f"{100 * (1 - total / level['broad_rg_tokens']):.2f}% |")
    lines += ["", "If the same four questions share one setup copy in one session:", "",
              "| Documents | Brain including one setup copy | Savings vs targeted `rg` | Savings vs broad `rg` |",
              "| ---: | ---: | ---: | ---: |"]
    for level in report["levels"]:
        total = level["brain_tokens"] + protocol
        lines.append(f"| {level['source_documents']} | {total} | "
                     f"{100 * (1 - total / level['targeted_rg_tokens']):.2f}% | "
                     f"{100 * (1 - total / level['broad_rg_tokens']):.2f}% |")
    lines += ["", f"In a new Python process with no conversation history, the Brain found "
              f"**{report['fresh_process_facts_found']}/{report['fresh_process_queries']} facts** "
              f"at the largest measured size. The stored memory Markdown totals "
              f"**{report['persisted_memory_tokens']:,} tokens**; it is not sent in full to the agent. "
              f"The first query in that fresh process took "
              f"**{report['fresh_process_first_ms']:.2f} ms**, including model startup.", "",
              "## Method and limitations", "",
              "`rg` columns count actual `rg -l` stdout plus the full text of one selected document. "
              "The targeted search uses an exact technical keyword and ideal file selection. The broad "
              "search uses terms shared by every synthetic document; its path listing grows with the "
              "corpus. Each question includes its own discovery output, even in the one-session "
              "calculation. The Brain column counts the actual `brain_search` context, including query, "
              "titles, and scores. Its `token_budget` is an internal approximation, while this report "
              "counts output with `cl100k_base`.", "",
              "Instruction and schema costs depend on how each MCP client presents and bills them. "
              "No builder reasoning, retries, output, task success, or memory authoring cost was measured. "
              "The four facts and distractors were written for this benchmark, and the budget was "
              "chosen during development. These results show behavior on this corpus, not a universal "
              "saving rate. Search time includes checking Markdown for changes, query embedding, and "
              "ranking. It excludes process startup and the separately reported new-chunk indexing.", "",
              f"Run `python benchmarks/growth.py --profile "
              f"{'quick' if result_name == 'growth-quick.json' else 'full'}` after installing "
              f"`.[benchmark]` and downloading the model. Raw results: "
              f"`benchmarks/results/{result_name}`. "
              "Use `--profile quick` for the 4/44/164-document smoke test."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--profile", choices=("quick", "full"), default="full")
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return
    with tempfile.TemporaryDirectory(prefix="brain-growth-") as folder:
        report = run(Path(folder), QUICK_LEVELS if args.profile == "quick" else FULL_LEVELS)
    output = ROOT / "benchmarks" / "results"
    output.mkdir(exist_ok=True)
    result_name = "growth-quick.json" if args.profile == "quick" else "growth.json"
    report_name = "GROWTH_QUICK_REPORT.md" if args.profile == "quick" else "GROWTH_REPORT.md"
    (output / result_name).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rendered = markdown(report, result_name=result_name)
    (ROOT / report_name).write_text(rendered, encoding="utf-8")
    print(rendered)
    if report["fresh_process_facts_found"] != len(CASES) or any(
        level["facts_found"] != len(CASES) or level["brain_tokens"] >= level["targeted_rg_tokens"]
        for level in report["levels"]
    ):
        raise SystemExit("Benchmark failed: incomplete fact retrieval or no savings against targeted rg")


if __name__ == "__main__":
    main()
