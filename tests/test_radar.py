import json
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from radar.core import normalize, select, classify, deduplicate, timestamp, region
from radar.collectors import collect_board
from radar.store import LocalStore, GitHubStore, set_status, merge_jobs
from urllib.error import HTTPError

REF=datetime(2026,10,22,16,tzinfo=timezone.utc)
def job(**kwargs):
    return normalize(dict(title='Senior Data Engineer',company='Example',location='Dallas, TX',description='Contract role building Snowflake pipelines',employment='Contract',url='https://example.org/jobs/1',posted_at='2026-10-22T15:00:00Z',source='Test',**kwargs))
class EligibilityTests(unittest.TestCase):
    def test_negative_overrides_c2c(self):
        for text in ['C2C is not allowed','No C2C','W2 only','Only W-2','No third-party vendors','C2C accepted? W2 only.']:
            self.assertEqual(classify('Data Engineer',text,'Contract')['c2c'],'Not eligible / W2-only',text)
    def test_unspecified_is_included(self): self.assertEqual(len(select([job()],reference=REF)),1)
    def test_permanent_not_contract(self):
        c=classify('Data Engineer','Work with contract vendors','FullTime'); self.assertEqual(c['contract_type'],'Permanent / full-time')
    def test_rate(self): self.assertEqual(classify('ETL Engineer','$90–$110/hr','Contract')['hourly_rate'],'$90–$110/hr')
    def test_regions(self):
        self.assertEqual(region('Remote, United States'),'US remote')
        self.assertEqual(region('London, UK'),'Outside target / unverified')
        self.assertEqual(region('Remote, Canada'),'Outside target / unverified')
        self.assertEqual(region('Remote'),'Remote — country unverified')
    def test_title_relevance(self): self.assertFalse(classify('Account Executive','sell Databricks','Contract')['related'])
class FreshnessTests(unittest.TestCase):
    def test_unknown_excluded_from_hour_filter(self):
        j=job(); j['posted_at']=None
        self.assertEqual(select([j],hours=24,reference=REF),[])
    def test_boundary(self):
        self.assertEqual(len(select([job()],hours=1,reference=REF)),1)
    def test_future(self):
        j=job(); j['posted_at']='2026-10-23T15:00:00+00:00'
        self.assertEqual(select([j],hours=24,reference=REF),[])
    def test_date_only(self): self.assertIsNone(timestamp('2026-10-22'))
    def test_sort(self):
        a=job(); b=job(); b['posted_at']=None; c=job(); c['posted_at']='2026-10-22T14:00:00+00:00'
        self.assertEqual([j['posted_at'] for j in select([b,c,a],reference=REF)],[a['posted_at'],c['posted_at'],None])
class StorageTests(unittest.TestCase):
    def test_restart_and_independent_statuses(self):
        with tempfile.TemporaryDirectory() as d:
            p=d+'/test.db'; s=LocalStore(p); j=job(); merge_jobs(s,[j]); set_status(s,j,'save'); set_status(s,j,'viewed'); merge_jobs(s,[j])
            record=LocalStore(p).read('status',{})[j['id']]
            self.assertEqual(record['status'],'save'); self.assertTrue(record['viewed_at'])
            set_status(s,j,'applied'); self.assertEqual(s.read('status',{})[j['id']]['status'],'applied')
    def test_url_dedup(self):
        a=job(); b=job(); b['source']='Other'
        self.assertEqual(len(deduplicate([a,b])),1)
    def test_requisition_dedup(self):
        a=job(); b=job(); a['requisition_id']=b['requisition_id']='REQ1'; b['url']='https://other.org/1'; b['id']='other'; b['sources']=[{'source':'Other','url':b['url']}]
        rows=deduplicate([a,b]); self.assertEqual(len(rows),1); self.assertEqual(len(rows[0]['sources']),2)
    def test_distinct_requisitions_remain(self):
        a=job(); b=job(); b['url']='https://example.org/jobs/2'; b['id']='second'
        self.assertEqual(len(deduplicate([a,b])),2)
    def test_private_required(self):
        with patch.object(GitHubStore,'_request',return_value={'private':False}):
            with self.assertRaises(ValueError): GitHubStore('x/y','secret')
    def test_conflict_retry(self):
        s=object.__new__(GitHubStore); s.repo='x/y'; s.branch='main'
        with patch.object(s,'_read',side_effect=[({'a':1},'sha1'),({'a':1,'b':2},'sha2')]),patch.object(s,'_request',side_effect=[HTTPError('u',409,'Conflict',{},None),{}]),patch('radar.store.time.sleep'):
            result=s.mutate('status',{},lambda old:{**old,'c':3})
        self.assertEqual(result,{'a':1,'b':2,'c':3})
class CollectorTests(unittest.TestCase):
    def test_ashby_last_publish_not_original(self):
        payload={'jobs':[{'title':'Data Engineer','location':'US Remote','employmentType':'Contract','descriptionPlain':'Build ETL','jobUrl':'https://jobs.ashbyhq.com/x/1','publishedAt':'2026-10-22T15:00:00Z'}]}
        with patch('radar.collectors.get_json',return_value=payload): rows,_=collect_board({'type':'ashby','board':'x','company':'X'})
        self.assertIsNone(rows[0]['posted_at']); self.assertIsNotNone(rows[0]['publisher_time'])
    def test_greenhouse_update_not_original(self):
        payload={'jobs':[{'title':'Data Engineer','absolute_url':'https://boards.greenhouse.io/x/1','updated_at':'2026-10-22T15:00:00Z'}]}
        with patch('radar.collectors.get_json',return_value=payload): rows,_=collect_board({'type':'greenhouse','board':'x','company':'X'})
        self.assertIsNone(rows[0]['posted_at'])
    def test_unlisted_ashby_ignored(self):
        with patch('radar.collectors.get_json',return_value={'jobs':[{'isListed':False,'title':'Data Engineer'}]}): rows,_=collect_board({'type':'ashby','board':'x','company':'X'})
        self.assertEqual(rows,[])
if __name__=='__main__': unittest.main()
