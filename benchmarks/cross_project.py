"""Fixed cross-project development evaluation. No LLM calls or source downloads."""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from second_brain.config import TYPES, load_config
from second_brain.core import initialize, remember, search
from second_brain.documents import document_id, now, render
from second_brain.storage import connect, index
from measure import counter

FIXTURE = Path(__file__).with_name('fixtures') / 'cross-project.json'


def run(limit=None):
    fixtures = json.loads(FIXTURE.read_text())
    count, tokenizer = counter()
    rows, checks = [], []
    with tempfile.TemporaryDirectory(prefix='brain-cross-project-') as folder:
        roots = {p['name']: Path(folder) / p['name'] for p in fixtures}
        for p in fixtures:
            root = roots[p['name']]
            initialize(root)
            for case in p['cases']:
                meta = dict(id=document_id(case['type'], case['title']), type=case['type'],
                            title=case['title'], importance=0.8, tags=[], updated_at=now())
                path = root / '.brain/knowledge' / TYPES[case['type']] / (meta['id'] + '.md')
                path.write_text(render(meta, case['content']))
            for i, content in enumerate(p['distractors']):
                title = f"Subsystem {i}: {content.split('.')[0]}"
                meta = dict(id=document_id('feature',title),type='feature',title=title,
                            importance=0.9,tags=[],updated_at=now())
                (root/'.brain/knowledge/features'/(meta['id']+'.md')).write_text(render(meta,content))
            summary = p['description'] + ' ' + ' '.join(c['title'] for c in p['cases'])
            for name in ('idea','overview','goals'):
                (root/'.brain/project'/(name+'.md')).write_text('# '+name+'\n\n'+summary)
            index(root,load_config(root))
        for p in fixtures:
            root = roots[p['name']]
            for case in p['cases']:
                for language, question in zip(('en','pt'),case['queries']):
                    for budget in (180,500,900):
                        result=search(root,question,token_budget=budget,limit=limit)
                        present=[f for f in case['facts'] if f.casefold() in result['context'].casefold()]
                        expected_id=document_id(case['type'],case['title'])
                        rows.append(dict(project=p['name'],case=case['title'],language=language,query=question,
                                         budget=budget,expected_facts=case['facts'],present=present,
                                         complete=len(present)==len(case['facts']),tokens=count(result['context']),
                                         correct_memory_returned=expected_id in [r['id'] for r in result['results']],
                                         duration_ms=result['duration_ms'],estimated_tokens=result['estimated_tokens']))
                        assert result['estimated_tokens']<=budget
            checks.append(dict(project=p['name'],check='incremental_index',passed=index(root,load_config(root))['embedded_chunks']==0))
            # A new process reads the existing local index (not Python model cache).
            process=subprocess.run([sys.executable,'-m','second_brain','status','--project',str(root)],capture_output=True,text=True)
            restarted=json.loads(process.stdout) if process.returncode==0 else {}
            checks.append(dict(project=p['name'],check='restart_status',passed=restarted.get('memories')==14 and restarted.get('active') is True))
            question=p['cases'][0]['queries'][0]
            requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},
                      {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'brain_search','arguments':{'query':question,'token_budget':500,**({'limit':limit} if limit is not None else {})}}}]
            process=subprocess.run([sys.executable,'-m','second_brain','mcp','--project',str(root)],
                                   input='\n'.join(json.dumps(r) for r in requests)+'\n',capture_output=True,text=True)
            replies=[json.loads(line) for line in process.stdout.splitlines() if line.strip()]
            tool=next((r.get('result',{}) for r in replies if r.get('id')==2),{})
            direct=search(root,question,token_budget=500,limit=limit)
            content=tool.get('content',[])
            checks.append(dict(project=p['name'],check='fresh_process_mcp_search',passed=process.returncode==0
                               and not tool.get('isError',False) and bool(content)
                               and content[0].get('text')==direct['context']))
        # An explicit follow-up for the newly observed Portuguese game miss.
        # Authored after the first run: this is a refinement, not a held-out query.
        refinement_query='Qual é a janela de rollback e como o cliente reconcilia seu estado com a simulação confirmada do servidor?'
        refined=search(roots['multiplayer-game'],refinement_query,token_budget=500)
        facts=fixtures[-1]['cases'][0]['facts']
        refinement=dict(query=refinement_query,authored_after_initial_run=True,
                        expected_facts=facts,present=[f for f in facts if f.casefold() in refined['context'].casefold()],
                        tokens=count(refined['context']))
        # Ask each project the other projects' questions; detect foreign unique IDs.
        for p in fixtures:
            root=roots[p['name']]
            foreign_ids={document_id(c['type'],c['title']) for other in fixtures if other['name']!=p['name'] for c in other['cases']}
            passed=True
            for other in fixtures:
                if other['name']==p['name']: continue
                for c in other['cases']:
                    result=search(root,c['queries'][0],token_budget=500)
                    passed &= not bool(foreign_ids & {r['id'] for r in result['results']})
            checks.append(dict(project=p['name'],check='cross_project_isolation_12_queries',passed=passed))
            case=p['cases'][0]
            marker=p['name']+'_updated_contract'
            updated=remember(root,type=case['type'],title=case['title'],content='Current replacement policy: '+marker)
            r=search(root,'What is the current replacement policy?',token_budget=500)
            with connect(root,load_config(root)) as db:
                texts=[row[0] for row in db.execute('SELECT text FROM chunks WHERE document_id=?',(updated['id'],))]
            checks.append(dict(project=p['name'],check='replacement_removes_stale_chunks',passed=marker in r['context'] and all(case['content'] not in t for t in texts)))
            (root/updated['path']).unlink()
            deleted=index(root,load_config(root))
            with connect(root,load_config(root)) as db:
                remaining=db.execute('SELECT count(*) FROM chunks WHERE document_id=?',(updated['id'],)).fetchone()[0]
            checks.append(dict(project=p['name'],check='deleted_memory_removed',passed=deleted['deleted_documents']==1 and remaining==0))
        summaries=[]
        for p in fixtures:
            for budget in (180,500,900):
                group=[r for r in rows if r['project']==p['name'] and r['budget']==budget]
                summaries.append(dict(project=p['name'],budget=budget,questions=len(group),complete=sum(r['complete'] for r in group),facts=sum(len(r['present']) for r in group),expected_facts=18,tokens=sum(r['tokens'] for r in group)))
        return dict(fixture_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),projects=5,memories_per_project=14,
                    retrieval_limit=limit if limit is not None else load_config(next(iter(roots.values())))['retrieval']['default_limit'],
                    model=load_config(next(iter(roots.values())))['embedding']['model'],tokenizer=tokenizer,
                    rows=rows,summaries=summaries,checks=checks,refinement=refinement)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--limit',type=int,default=None,help='Override the configured result limit.')
    parser.add_argument('--output',type=Path,default=Path('benchmarks/results/cross-project.json'))
    args=parser.parse_args()
    report=run(args.limit)
    args.output.parent.mkdir(exist_ok=True,parents=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'summaries':report['summaries'],'checks':report['checks']},indent=2))
