import base64,csv,hashlib,io,json
from pathlib import Path
from app.config import REQUIRED
from app.errors import DomainError
from app.workflow import run
from app.modules.m1_ingest.decode import decode
from app.modules.m3_versions.standards import parse as parse_limits
from app.modules.m8_revision.diff import diff_states

def revision_id(run_id,limits_csv,reports_csv):
    payload=json.dumps({'run':run_id,'limits':limits_csv,'reports':reports_csv},sort_keys=True,ensure_ascii=False)
    return 'R'+hashlib.sha256(payload.encode('utf-8')).hexdigest()[:19]

def correction_samples():
    base=Path(__file__).resolve().parents[3]/'sample_data';out={'limits':'','reports':''}
    for key,name in [('limits','limits_corrected.csv'),('reports','retest_late.csv')]:
        try:out[key]=(base/name).read_text(encoding='utf-8-sig')
        except OSError:pass
    return out

def merge_reports(base_bytes,reports_csv):
    base_text,_=decode(base_bytes)
    reader=csv.reader(io.StringIO(base_text,newline=''))
    try:header=[h.strip().lstrip('\ufeff') for h in next(reader)]
    except StopIteration:raise DomainError('REPORTS','原始报告表头缺失')
    late=csv.reader(io.StringIO(reports_csv,newline=''))
    try:late_header=[h.strip().lstrip('\ufeff') for h in next(late)]
    except StopIteration:raise DomainError('REPORTS','复检报告为空')
    if not set(REQUIRED)<=set(late_header):raise DomainError('REPORTS','复检报告表头缺失')
    out=io.StringIO(newline='');writer=csv.writer(out);count=0
    for row in late:
        if not row or not any(s.strip() for s in row):continue
        if len(row)!=len(late_header):raise DomainError('REPORTS','复检报告列数不齐')
        aligned={late_header[i]:row[i] for i in range(len(late_header))}
        writer.writerow([aligned.get(h,'') for h in header]);count+=1
    if not count:raise DomainError('REPORTS','复检报告无数据行')
    text=base_text if base_text.endswith('\n') else base_text+'\n'
    return (text+out.getvalue()).encode('utf-8')

def validate_revision(old,new):
    if not new.get('reconcile',{}).get('balanced'):raise DomainError('REVISION','更正后对账未平')
    old_keys={(c['sample_id'],c['batch'],c['analyte']) for c in old.get('calculations',[])}
    new_keys={(c['sample_id'],c['batch'],c['analyte']) for c in new.get('calculations',[])}
    missing=sorted(old_keys-new_keys)
    if missing:raise DomainError('REVISION','更正导致已签发项目缺失：'+'、'.join('/'.join(k) for k in missing[:3]))

def adjudicate(base,limits_csv,reports_csv):
    params=dict(base.get('manifest',{}).get('parameters') or {})
    if limits_csv:
        parse_limits(limits_csv)
        params['limits_csv']=limits_csv
    content=base64.b64decode(base['source_b64'])
    if reports_csv:content=merge_reports(content,reports_csv)
    new_state=run(content,params)
    validate_revision(base,new_state)
    return {'diff':diff_states(base,new_state),'state':new_state}
