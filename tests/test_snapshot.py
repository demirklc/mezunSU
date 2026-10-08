import importlib.util
from pathlib import Path
import json
spec=importlib.util.spec_from_file_location('snapshot',Path(__file__).resolve().parents[1]/'scripts/snapshot.py')
snapshot=importlib.util.module_from_spec(spec);spec.loader.exec_module(snapshot)

def test_snapshot_keeps_verified_curriculum_on_failure(tmp_path,monkeypatch):
    monkeypatch.setattr(snapshot,'ROOT',tmp_path)
    old={'updated_at':0,'courses':[{'code':'CS 201'}],'requirements':[{'name':'Zorunlu Dersler'}]}
    target=tmp_path/'curriculum/BSCS/201901.json';snapshot.write(target,old)
    monkeypatch.setattr(snapshot.suis,'terms',lambda c:[{'code':'201901','label':'2019-2020 Güz'}])
    def fail(*args):raise snapshot.suis.UpstreamError('offline')
    monkeypatch.setattr(snapshot.suis,'detail',fail)
    snapshot.program('BSCS')
    assert snapshot.read(target,{})==old
    assert snapshot.read(tmp_path/'status/BSCS.json',{})['failed']==['201901']

def test_snapshot_aliases_merge_categories():
    d=snapshot.normalize({'courses':[{'code':'CS 210','categories':['A']},{'code':'DSA 210','categories':['B']}]})
    assert len(d['courses'])==1
    assert d['courses'][0]['code']=='DSA 210'
    assert d['courses'][0]['categories']==['A','B']
