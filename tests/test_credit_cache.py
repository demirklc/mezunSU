import sys,time
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import main,suis
from fastapi.testclient import TestClient

def test_persistent_credit_cache_and_batch_read(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DB',str(tmp_path/'planner.sqlite3'))
    detail={'code':'MATH 101','engineering':0,'basic':5,'prerequisites':None,'source_url':'https://example.org'}
    with TestClient(main.app) as c,patch.object(suis,'course_credit',return_value=detail) as upstream:
        assert c.post('/api/course-credit-cache',json={'codes':['MATH 101']}).json()=={'credits':{}}
        assert upstream.call_count==0
        assert c.get('/api/course-credit/MATH%20101').json()['basic']==5
        assert c.get('/api/course-credit/MATH%20101').json()['_cache']['fresh']
        assert upstream.call_count==1
        batch=c.post('/api/course-credit-cache',json={'codes':['MATH 101']}).json()
        assert batch['credits']['MATH 101']['basic']==5
        assert upstream.call_count==1
        assert (tmp_path/'course_credit_cache.sqlite3').exists()
        # New connection still serves stored data without SUIS.
        assert main.cached_credit('MATH 101')['basic']==5
        assert upstream.call_count==1
        assert c.post('/api/course-credit-cache',json={'codes':['bad code']}).status_code==400

def test_expiry_failure_backoff_and_stale_fallback(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DB',str(tmp_path/'planner.sqlite3'))
    detail={'code':'MATH 101','engineering':0,'basic':5,'source_url':'https://example.org'}
    with patch.object(suis,'course_credit',return_value=detail):main.cached_credit('MATH 101')
    with main.credit_connection() as db:db.execute('UPDATE credit_cache SET fetched_at=?',(time.time()-main.CREDIT_TTL-10,))
    with patch.object(suis,'course_credit',side_effect=suis.UpstreamError('offline')) as upstream:
        value=main.cached_credit('MATH 101')
        assert value['basic']==5 and not value['_cache']['fresh']
        assert value['_unavailable']
        main.cached_credit('MATH 101');assert upstream.call_count==1
        value=main.cached_credit('CS 999')
        assert value['basic'] is None
        main.cached_credit('CS 999');assert upstream.call_count==2

def test_concurrent_requests_share_one_fetch(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'DB',str(tmp_path/'planner.sqlite3'))
    detail={'code':'CS 201','engineering':6,'basic':0}
    with patch.object(suis,'course_credit',return_value=detail) as upstream,ThreadPoolExecutor(max_workers=2) as pool:
        values=list(pool.map(main.cached_credit,['CS 201','CS 201']))
        assert all(v['engineering']==6 for v in values)
        assert upstream.call_count==1
