import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import suis
import main


@pytest.mark.parametrize('code,label', [
    ('201901', '2019-2020 Güz'),
    ('201902', '2019-2020 Bahar'),
    ('202501', '2025-2026 Güz'),
    ('202502', '2025-2026 Bahar'),
    ('199901', '1999-2000 Güz'),
    ('201903', '2019-2020 Yaz'),
    ('202508', 'SUIS 202508 · Dönem adı doğrulanmadı'),
])
def test_labels(code, label):
    assert suis.term_label(code) == label


def test_invalid_label():
    with pytest.raises(ValueError):
        suis.term_label('2025 1')


def test_official_suis_snapshot():
    # Public BSCS entry-term select fetched on 2026-10-08; no student data.
    source = Path(__file__).parent / 'fixtures' / 'suis_bscs_terms.html'
    soup = BeautifulSoup(source.read_text(encoding='utf-8'), 'html.parser')
    with patch.object(suis, 'html', return_value=soup):
        rows = suis.terms('BSCS')
    official = {}
    for option in soup.select('option[value]'):
        season, year = option.get_text(' ', strip=True).split()
        official[option['value']] = f'{year} {season}'
    assert len(rows) == len(official) == 84
    assert {row['code']: row['label'] for row in rows} == official
    assert [row['code'] for row in rows[:3]] == ['202601', '202602', '202603']


def test_terms_api_and_original_code_roundtrip(tmp_path, monkeypatch):
    # Mixed SUIS link/option formats, duplicates and unknown suffixes.
    soup = BeautifulSoup('''
        <a href="/prod/SU_DEGREE.p_degree_detail?P_TERM=201902">2020 Spring</a>
        <a href="/prod/SU_DEGREE.p_degree_detail?P_TERM=201901">2019 Fall</a>
        <option value="201901">duplicate</option>
        <option value="202502">Spring</option>
        <option value="202501">Fall</option>
        <option value="201903">unknown</option>
        <option value="2025 1">invalid</option>
    ''', 'html.parser')
    monkeypatch.setattr(main, 'DB', str(tmp_path / 'planner.sqlite3'))
    with TestClient(main.app) as client, patch.object(suis, 'html', return_value=soup) as upstream:
        response = client.get('/api/terms/BSCS')
        assert response.status_code == 200
        assert response.json() == [
            {'code': t, 'label': suis.term_label(t)}
            for t in ['202501', '202502', '201901', '201902', '201903']
        ]
        selected = response.json()[3]['code']
        upstream.reset_mock()
        curriculum = client.get('/api/curriculum/BSCS/' + selected)
        assert curriculum.status_code == 200
        assert curriculum.json()['term'] == '201902'
        assert 'P_TERM=201902' in curriculum.json()['source_url']
        assert upstream.call_args.args[1]['P_TERM'] == '201902'
