from pathlib import Path
import pytest
from app import store

SAMPLES=Path(__file__).resolve().parents[1]/'sample_data'

def correction():
    return {'limits_csv':(SAMPLES/'limits_corrected.csv').read_text(encoding='utf-8-sig'),
            'reports_csv':(SAMPLES/'retest_late.csv').read_text(encoding='utf-8-sig')}

@pytest.fixture
def signed(client):
    run=client.post('/api/runs',json={'sample':'clean.csv'}).get_json()
    client.post('/api/runs/'+run['run_id']+'/review',json={'version':run['review_version'],'decision':'通过'})
    return run['run_id']

def items_of(record):
    return {(i['sample_id'],i['analyte']):i for i in record['body']['diff']['items']}

def grades_of(record):
    return {g['batch']:g for g in record['body']['diff']['grades']}

def test_unsigned_run_rejected(client):
    run=client.post('/api/runs',json={'sample':'clean.csv'}).get_json()
    r=client.post('/api/runs/'+run['run_id']+'/revisions',json=correction())
    assert r.status_code==422 and r.get_json()['code']=='UNSIGNED'

def test_revision_joint_adjudication(client,signed):
    r=client.post('/api/runs/'+signed+'/revisions',json=correction())
    assert r.status_code==200
    rec=r.get_json();assert rec['status']=='生效' and rec['seq']==1
    grades=grades_of(rec)
    assert grades['B001']['old']=='FAIL' and grades['B001']['new']=='PASS' and grades['B001']['direction']=='升级'
    assert 'FAIL→PASS' in grades['B001']['reason']
    assert grades['B002']['direction']=='不变' and grades['B002']['new']=='FAIL'
    items=items_of(rec)
    assert items[('S001','P01')]['causes']==['限量更正','复检报告'] and items[('S001','P01')]['new']['report']=='00037'
    assert items[('S004','P01')]['causes']==['限量更正']
    assert items[('S004','P01')]['old']['code']=='PASS' and items[('S004','P01')]['new']['code']=='FAIL'
    assert items[('S004','P01')]['new']['limit']=='0.003'
    assert items[('S004','P02')]['new']['code']=='PASS'
    assert len(rec['body']['state']['calculations'])==24

def test_revision_idempotent_no_new_version(client,signed):
    a=client.post('/api/runs/'+signed+'/revisions',json=correction()).get_json()
    b=client.post('/api/runs/'+signed+'/revisions',json=correction()).get_json()
    assert a['id']==b['id'] and b['reused'] is True
    revisions=client.get('/api/runs/'+signed+'/revisions').get_json()
    assert len(revisions)==1 and revisions[0]['seq']==1
    ids=[c['id'] for c in b['body']['state']['calculations']]
    assert len(ids)==len(set(ids))

def test_failed_revision_keeps_old_conclusion(client,signed):
    before=client.get('/api/runs/'+signed).get_json()
    bad=correction();bad['limits_csv']='id,product\n1,2\n'
    r=client.post('/api/runs/'+signed+'/revisions',json=bad)
    assert r.status_code==422 and r.get_json()['code']=='LIMITS'
    revisions=client.get('/api/runs/'+signed+'/revisions').get_json()
    assert len(revisions)==1 and revisions[0]['status']=='失败' and revisions[0]['error']
    after=client.get('/api/runs/'+signed).get_json()
    assert after['calculations']==before['calculations'] and after['decision']=='通过'
    assert after['archive']['sha256']==before['archive']['sha256']

def test_failed_revision_rerun_no_duplicate(client,signed):
    bad=correction();bad['limits_csv']='id,product\n1,2\n'
    client.post('/api/runs/'+signed+'/revisions',json=bad)
    r=client.post('/api/runs/'+signed+'/revisions',json=bad)
    assert r.status_code==422
    assert len(client.get('/api/runs/'+signed+'/revisions').get_json())==1

def test_missing_item_protection(client,signed):
    limits='id,product,analyte,start,end,limit_mgkg,methods\nAPL-P01-V2C,苹果,P01,2026-07-01,2027-01-01,0.003,LC-MS/MS\n'
    r=client.post('/api/runs/'+signed+'/revisions',json={'limits_csv':limits,'reports_csv':''})
    assert r.status_code==422 and r.get_json()['code']=='REVISION' and '缺失' in r.get_json()['message']
    assert client.get('/api/runs/'+signed+'/revisions').get_json()[0]['status']=='失败'

def test_reports_only_correction(client,signed):
    r=client.post('/api/runs/'+signed+'/revisions',json={'limits_csv':'','reports_csv':correction()['reports_csv']})
    assert r.status_code==200
    rec=r.get_json();items=items_of(rec)
    assert items[('S001','P01')]['causes']==['复检报告'] and items[('S001','P01')]['new']['code']=='PASS'
    assert ('S004','P01') not in items
    assert grades_of(rec)['B001']['new']=='FAIL'

def test_limits_only_correction(client,signed):
    r=client.post('/api/runs/'+signed+'/revisions',json={'limits_csv':correction()['limits_csv'],'reports_csv':''})
    assert r.status_code==200
    rec=r.get_json();items=items_of(rec)
    assert items[('S001','P01')]['causes']==['限量更正'] and items[('S001','P01')]['new']['code']=='FAIL'
    assert all(g['new']=='FAIL' for g in grades_of(rec).values())

def test_empty_correction_rejected(client,signed):
    r=client.post('/api/runs/'+signed+'/revisions',json={})
    assert r.status_code==422 and r.get_json()['code']=='EMPTY'

def test_old_signature_basis_checkable(client,signed):
    before=client.get('/api/runs/'+signed).get_json()
    client.post('/api/runs/'+signed+'/revisions',json=correction())
    after=client.get('/api/runs/'+signed).get_json()
    assert after['calculations']==before['calculations'] and after['reconcile']==before['reconcile']
    assert after['review_version']==before['review_version'] and after['decision']=='通过'
    assert client.get('/api/archive/'+signed+'/export.csv').status_code==200

def test_revision_record_readable(client,signed):
    rec=client.post('/api/runs/'+signed+'/revisions',json=correction()).get_json()
    got=client.get('/api/runs/'+signed+'/revisions/'+rec['id']).get_json()
    assert got['id']==rec['id'] and got['body']['diff']['summary']['items_changed']>0
    assert got['body']['state']['archive']['sha256']!=client.get('/api/runs/'+signed).get_json()['archive']['sha256']
    assert client.get('/api/runs/'+signed+'/revisions/absent').status_code==404

def test_revision_page_shows_changes(client,signed):
    client.post('/api/runs/'+signed+'/revisions',json=correction())
    page=client.get('/m8_revision?run='+signed)
    assert page.status_code==200
    html=page.data.decode()
    assert '修订裁决' in html and '升级' in html and '限量更正' in html and '复检报告' in html and '签发依据' in html

def test_revision_records_survive_failed_and_effective(client,signed):
    bad=correction();bad['limits_csv']='id,product\n1,2\n'
    client.post('/api/runs/'+signed+'/revisions',json=bad)
    client.post('/api/runs/'+signed+'/revisions',json=correction())
    revisions=client.get('/api/runs/'+signed+'/revisions').get_json()
    assert [r['status'] for r in revisions]==['失败','生效'] and [r['seq'] for r in revisions]==[1,2]
