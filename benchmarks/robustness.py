"""Evaluate multilingual query paraphrases against a synthetic local corpus."""

import json
import argparse
import statistics
import tempfile
from pathlib import Path

from second_brain.config import load_config
from second_brain.core import initialize, remember, search
from second_brain.storage import index

from growth import CASES, add_decoys, environment, source_document
from measure import counter

ROOT = Path(__file__).resolve().parents[1]
BUDGETS = (180, 400)
PARAPHRASES = {
    "auth": (
        "How is a reused refresh credential rejected?",
        "O que invalida o token anterior após renovar a sessão?",
    ),
    "queue": (
        "What makes payment processing safe when a message is delivered twice?",
        "Como evitar cobrança duplicada após redelivery da fila?",
    ),
    "tenant": (
        "Where is tenant isolation enforced for data reads?",
        "Em que camada a organização é filtrada nas consultas?",
    ),
    "audit": (
        "Which audit events survive cleanup, and for how long?",
        "Qual é a janela de retenção do log de auditoria?",
    ),
}


def run(project: Path) -> dict:
    project.mkdir(parents=True, exist_ok=True)
    initialize(project)
    docs = project / "docs"
    docs.mkdir()
    expected_ids = {}
    for case in CASES:
        (docs / f"{case['id']}.md").write_text(source_document(case), encoding="utf-8")
        result = remember(project, type=case["type"], title=case["title"],
                          content=f"What changed: {case['memory']} Why: {case['reason']}", importance=0.95)
        expected_ids[case["id"]] = result["id"]
    add_decoys(project, 0, 996)
    index(project, load_config(project))
    count_tokens, tokenizer = counter()
    questions = []
    for case in CASES:
        for form, question in enumerate((case["query"], *PARAPHRASES[case["id"]])):
            for budget in BUDGETS:
                result = search(project, question, limit=5, token_budget=budget)
                ids = [item["id"] for item in result["results"]]
                questions.append({"case": case["id"], "form": form, "query": question,
                                  "budget": budget, "top1": bool(ids and ids[0] == expected_ids[case["id"]]),
                                  "returned": expected_ids[case["id"]] in ids,
                                  "fact_in_context": case["fact"].casefold() in result["context"].casefold(),
                                  "actual_tokens": count_tokens(result["context"]),
                                  "duration_ms": result["duration_ms"], "returned_ids": ids})
    summaries = []
    for budget in BUDGETS:
        group = [item for item in questions if item["budget"] == budget]
        summaries.append({"budget": budget, "questions": len(group),
                          "top1": sum(item["top1"] for item in group),
                          "returned": sum(item["returned"] for item in group),
                          "fact_in_context": sum(item["fact_in_context"] for item in group),
                          "payload_tokens": sum(item["actual_tokens"] for item in group),
                          "median_ms": round(statistics.median(item["duration_ms"] for item in group), 2)})
    return {"environment": environment(), "model": load_config(project)["embedding"]["model"],
            "tokenizer": tokenizer, "documents": 1000, "fact_documents": len(CASES),
            "distractors": 996, "questions": questions, "summaries": summaries}


def markdown(report: dict) -> str:
    lines = ["# Multilingual retrieval robustness", "",
             "A separate local quality check uses four fact-bearing memories, 996 synthetic distractors "
             "that share common terms, and three fixed questions per fact: one original and two "
             "paraphrases in English or Portuguese. The questions were written before running this "
             "evaluation. No LLM or API is called.", "",
             f"Model: `{report['model']}` on CPU. Tokenizer: {report['tokenizer']}. "
             f"Corpus: {report['documents']:,} indexed memories and matching project documents. "
             f"Machine: {report['environment']['cpu_model']}.", "",
             "| Approximate budget/query | Questions | Correct memory first | Correct memory returned | Exact fact in context | Actual payload tokens | Median search ms |",
             "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in report["summaries"]:
        lines.append(f"| {row['budget']} | {row['questions']} | {row['top1']}/{row['questions']} | "
                     f"{row['returned']}/{row['questions']} | "
                     f"{row['fact_in_context']}/{row['questions']} | "
                     f"{row['payload_tokens']:,} | {row['median_ms']:.2f} |")
    lines += ["", "## Per-question evidence", "",
              "The fact check tests for a predefined unique string in the actual context returned to "
              "the agent. `top1` and `returned` compare document IDs; `returned` may include fewer than "
              "five items because of the budget.", "",
              "| Case | Form | Budget | Top 1 | Returned | Fact present | Payload tokens |",
              "| --- | --- | ---: | --- | --- | --- | ---: |"]
    for item in report["questions"]:
        form = ("original", "English paraphrase", "Portuguese paraphrase")[item["form"]]
        lines.append(f"| {item['case']} | {form} | {item['budget']} | "
                     f"{'yes' if item['top1'] else 'no'} | "
                     f"{'yes' if item['returned'] else 'no'} | "
                     f"{'yes' if item['fact_in_context'] else 'no'} | {item['actual_tokens']} |")
    lines += ["", "## Limits", "",
              "This is an authored synthetic set with only four underlying facts. The same facts "
              "appear in the growth benchmark, and the distractors are repetitive; the questions "
              "are not a blind production sample. The test does not compare actual builder token use "
              "or implementation success. It isolates how paraphrasing and response budgets affect "
              "local retrieval on this corpus.", "",
              "Reproduce with `python benchmarks/robustness.py` after installing `.[benchmark]` and "
              "downloading the embedding model. Raw questions, IDs, token counts, and latencies are "
              "in `benchmarks/results/robustness.json`."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Fail if any question loses its expected memory or fact')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="brain-robustness-") as folder:
        report = run(Path(folder))
    output = ROOT / "benchmarks/results"
    output.mkdir(exist_ok=True)
    (output / "robustness.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    (ROOT / "ROBUSTNESS_REPORT.md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))
    if args.check and any(row['returned'] != row['questions'] or row['fact_in_context'] != row['questions']
                          for row in report['summaries']):
        raise SystemExit('Retrieval regression: expected memory or fact missing')


if __name__ == "__main__":
    main()
