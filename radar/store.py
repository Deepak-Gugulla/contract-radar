"""Local SQLite for development; private GitHub JSON documents for durable deployment.
Compare-and-swap retries merge concurrent refresh/status operations; statuses are a
separate document so collection cannot clobber Save/Skip/Applied/Viewed events.
"""
import base64
import json
import os
import sqlite3
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from .core import deduplicate, now

class LocalStore:
    durable=False
    def __init__(self,path='data/local.sqlite'):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.path=path
        with sqlite3.connect(path) as db: db.execute('CREATE TABLE IF NOT EXISTS documents (name TEXT PRIMARY KEY, body TEXT NOT NULL)')
    def read(self,name,default):
        with sqlite3.connect(self.path) as db:
            row=db.execute('SELECT body FROM documents WHERE name=?',(name,)).fetchone()
        return json.loads(row[0]) if row else default
    def mutate(self,name,default,fn):
        with sqlite3.connect(self.path,timeout=30) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT body FROM documents WHERE name=?',(name,)).fetchone()
            value=fn(json.loads(row[0]) if row else default)
            db.execute('INSERT OR REPLACE INTO documents VALUES (?,?)',(name,json.dumps(value)))
        return value

class GitHubStore:
    durable=True
    def __init__(self,repo,token,branch='main'):
        if not repo or not token: raise ValueError('DATA_REPO and DATA_TOKEN are required')
        self.repo=repo; self.token=token; self.branch=branch
        # Refuse accidental public storage of personal application history.
        meta=self._request(f'https://api.github.com/repos/{repo}')
        if not meta.get('private'): raise ValueError('DATA_REPO must be private')
    def _request(self,url,data=None,method=None):
        req=Request(url,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'ContractRadar','Content-Type':'application/json'})
        with urlopen(req,timeout=30) as r: return json.load(r)
    def _read(self,name,default):
        from urllib.parse import quote
        url=f'https://api.github.com/repos/{self.repo}/contents/data/{name}.json'
        try:
            meta=self._request(url+'?ref='+quote(self.branch,safe=''))
            content=meta.get('content')
            if not content:  # Contents API omits inline data above 1 MB.
                blob=self._request(f'https://api.github.com/repos/{self.repo}/git/blobs/{meta["sha"]}')
                content=blob['content']
            return json.loads(base64.b64decode(content)),meta['sha']
        except HTTPError as e:
            if e.code==404: return default,None
            raise
    def read(self,name,default): return self._read(name,default)[0]
    def mutate(self,name,default,fn):
        for attempt in range(5):
            current,sha=self._read(name,default); updated=fn(current)
            if updated==current: return updated
            payload={'message':'Update '+name,'branch':self.branch,'content':base64.b64encode(json.dumps(updated,ensure_ascii=False).encode()).decode()}
            if sha: payload['sha']=sha
            try:
                self._request(f'https://api.github.com/repos/{self.repo}/contents/data/{name}.json',payload,'PUT')
                return updated
            except HTTPError as e:
                if e.code not in (409,422) or attempt==4: raise
                time.sleep(.5*(attempt+1))
        raise RuntimeError('Concurrent updates could not be merged')

def get_store(config=None):
    config=config or os.environ
    if config.get('DATA_REPO') and config.get('DATA_TOKEN'):
        return GitHubStore(config['DATA_REPO'],config['DATA_TOKEN'],config.get('DATA_BRANCH','main'))
    if config.get('REQUIRE_DURABLE','false').lower()=='true':
        raise ValueError('Durable storage is required; configure DATA_REPO and DATA_TOKEN')
    return LocalStore(config.get('LOCAL_DB','data/local.sqlite'))

def merge_jobs(store,jobs,health=None):
    def merge(old):
        combined=deduplicate(old.get('jobs',[])+jobs)
        # Bound the active catalog; user history remains separately persisted.
        return {'jobs':combined[-5000:],'health':health if health is not None else old.get('health',[]),'refreshed_at':now() if health is not None else old.get('refreshed_at')}
    return store.mutate('catalog',{'jobs':[]},merge)

def set_status(store,job,action):
    if action not in ('save','skip','applied','viewed','reset'): raise ValueError('Unknown action')
    def update(old):
        records=dict(old); record=dict(records.get(job['id'],{})); record['job']=job
        if action=='reset': record={'job':job}
        elif action=='viewed': record['viewed_at']=now()
        else: record['status']=action; record['status_at']=now()
        records[job['id']]=record
        return records
    return store.mutate('status',{},update)
