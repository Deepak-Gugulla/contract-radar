import json
from pathlib import Path
from radar.collectors import collect
from radar.store import get_store, merge_jobs
from radar.core import select

def main():
    boards=json.loads(Path('sources.json').read_text())['sources']
    jobs,health=collect(boards)
    store=get_store(); result=merge_jobs(store,jobs,health)
    print(json.dumps({'health':health,'related_jobs':len(jobs),'eligible_contracts':len(select(result['jobs']))},indent=2))
    if health and not any(h['ok'] for h in health): raise SystemExit('Every source failed; previous jobs preserved')
if __name__=='__main__': main()
