from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import main
from fastapi.testclient import TestClient

def test_public_routes_and_security(monkeypatch,tmp_path):
    monkeypatch.setattr(main,'DB',tmp_path/'public.sqlite3')
    monkeypatch.setattr(main.suis,'programs',lambda:[{'code':'CS','name':'CS'}])
    with TestClient(main.app) as c:
        assert c.get('/health').status_code==200
        response=c.get('/')
        assert response.status_code==200
        assert "frame-ancestors 'none'" in response.headers['content-security-policy']
        assert '/static/local-data.js' in response.text
        assert c.get('/api/profile/private').status_code==404
        assert c.post('/api/profile',json={'program':'CS','term':'202501'}).status_code==404
        assert c.post('/api/restore',json={}).status_code==404
        assert c.post('/api/course-credit-cache',json={'codes':['CS 201']*1001}).status_code==422
        assert c.post('/api/course-credit-cache',content='x'*65537).status_code==413

def test_personal_data_not_in_source():
    source=(main.ROOT/'main.py').read_text(encoding='utf-8')
    assert 'CREATE TABLE IF NOT EXISTS profiles' not in source
    assert "@app.post('/api/profile')" not in source
    assert not list(main.ROOT.glob('*.sqlite3'))
