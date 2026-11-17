import csv,io
from pathlib import Path
from decimal import Decimal,InvalidOperation
from datetime import date
from app.errors import DomainError

FIELDS=['id','product','analyte','start','end','limit_mgkg','methods']

def parse(text):
    reader=csv.DictReader(io.StringIO(text,newline=''))
    header=[h.strip().lstrip('\ufeff') for h in reader.fieldnames or []]
    if not set(FIELDS)<=set(header):raise DomainError('LIMITS','限量表缺少必需列')
    rows=[]
    for line,row in enumerate(reader,2):
        item={k:(row.get(k) or '').strip() for k in FIELDS}
        try:
            if not item['id'] or not item['product'] or not item['analyte'] or not item['methods']:raise ValueError
            start=date.fromisoformat(item['start']);end=date.fromisoformat(item['end'])
            if not start<end:raise ValueError
            limit=Decimal(item['limit_mgkg'])
            if not limit.is_finite() or limit<=0:raise ValueError
        except (ValueError,InvalidOperation):raise DomainError('LIMITS','限量表第%d行无效'%line)
        rows.append(item)
    if not rows:raise DomainError('LIMITS','限量表无有效行')
    return rows

def standards(text=None):
    if text is not None:return parse(text)
    path=Path(__file__).resolve().parents[3]/'sample_data'/'limits.csv'
    with path.open(encoding='utf-8-sig',newline='') as f:return parse(f.read())

def choose(row, limits):
    candidates=[l for l in limits if l['product']==row['product'] and l['analyte']==row['analyte'] and l['start']<=row['sampled']<l['end']]
    if len(candidates)!=1:raise DomainError('VERSION','采样日期的限量版本缺失或重叠')
    limit=candidates[0]
    if row['method'] not in limit['methods'].split('|'):raise DomainError('METHOD','检测方法不在标准适用范围')
    return {'standard_id':limit['id'],'limit':str(Decimal(limit['limit_mgkg'])),'methods':limit['methods'],'standard_start':limit['start'],'standard_end':limit['end']}
