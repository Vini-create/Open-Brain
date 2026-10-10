"""Fixed synthetic retrieval cases with competing summaries; no LLM calls.
Run the same file with PYTHONPATH pointing to each engine being compared.
"""
import argparse
import json
import tempfile
from pathlib import Path

from second_brain.config import load_config
from second_brain.core import initialize, remember, search
from second_brain.documents import now, render, document_id
from second_brain.storage import index
from measure import counter

CASES = [
    ("storage", "Session persistence and cleanup", "architecture",
     "Sessions and messages persist locally in SQLite at data/workspace.db. Cleanup removes messages after 45 days, but pinned sessions never expire.",
     ["SQLite", "workspace.db", "45 days"],
     ["Where does conversation history live and when is it removed?", "What survives closing the app, and how long is chat retained?", "How are old conversations stored and cleaned up?"]),
    ("permissions", "External folder authorization", "rule",
     "Access outside the active workspace requires human approval. The permission is single-use and scoped to the exact path and read/write mode. Repeated access requests require another approval.",
     ["single-use", "exact path", "human approval"],
     ["Can a tool open a folder outside the workspace?", "How is permission granted to read files beyond the project directory?", "What stops an approved tool from accessing other folders?"]),
    ("transport", "Desktop requests and live updates", "architecture",
     "Desktop requests use a loopback HTTP server at 127.0.0.1 with an ephemeral port. Live status updates arrive over SSE. The UI waits for /health before connecting and reconnects with exponential backoff.",
     ["127.0.0.1", "SSE", "/health"],
     ["How does the desktop screen talk to the backend and receive live changes?", "How do requests and streaming updates reach the user interface?", "How is the desktop connection established and kept up to date?"]),
    ("validation", "Backend and frontend validation commands", "constraint",
     "Validate server changes with go test ./.... Validate the web interface with npm --prefix web test. Run npm --prefix web run build to check the TypeScript production build. Socket tests need permission to bind localhost.",
     ["go test ./...", "npm --prefix web test", "npm --prefix web run build"],
     ["Which checks should I run after modifying the server or web screen?", "How do I test both sides of the app and verify the production build?", "What commands validate backend changes and the frontend?"]),
]


def run(label):
    count, tokenizer = counter()
    with tempfile.TemporaryDirectory(prefix="brain-quality-") as folder:
        root = Path(folder)
        initialize(root)
        for name, title, kind, body, facts, queries in CASES:
            remember(root, type=kind, title=title, content=body, tags=[name], importance=0.8)
        summary = ("This desktop project combines conversation history, cleanup, permissions, "
                   "workspace tools, backend requests, live status updates, a web interface, "
                   "and frontend/server validation. Modules collaborate to manage sessions, "
                   "connect the desktop, authorize external folders, and validate changes. "
                   "Implementation contracts are recorded in focused subsystem memories.")
        for name in ("idea", "overview", "goals"):
            (root / '.brain/project' / (name + '.md')).write_text('# Project ' + name + '\n\n' + summary)
        for i in range(40):
            title = f"Module {i} integration overview"
            meta = dict(id=document_id('feature', title), type='feature', title=title,
                        tags=['integration'], importance=0.9, updated_at=now())
            path = root / '.brain/knowledge/features' / (meta['id'] + '.md')
            path.write_text(render(meta, summary + f" Module {i} also publishes diagnostics for its own integration."))
        index(root, load_config(root))
        rows=[]
        for name, title, kind, body, facts, queries in CASES:
            for q in queries:
                for budget in (180, 500, 900):
                    r=search(root,q,limit=5,token_budget=budget)
                    present=[f for f in facts if f.casefold() in r['context'].casefold()]
                    rows.append(dict(case=name,query=q,budget=budget,facts=facts,present=present,
                                     complete=len(present)==len(facts),tokens=count(r['context']),
                                     titles=[x['title'] for x in r['results']],duration_ms=r['duration_ms']))
        return dict(engine=label, corpus_memories=47, tokenizer=tokenizer,
                    model=load_config(root)['embedding']['model'], rows=rows,
                    summaries=[dict(budget=b,questions=12,complete=sum(r['complete'] for r in rows if r['budget']==b),
                                    facts=sum(len(r['present']) for r in rows if r['budget']==b),expected_facts=36,
                                    tokens=sum(r['tokens'] for r in rows if r['budget']==b)) for b in (180,500,900)])


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--label',default='current')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=run(args.label)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['summaries'],indent=2))
