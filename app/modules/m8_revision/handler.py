from flask import Blueprint,request,jsonify,render_template
from app import store
from app.config import TITLE,SHORT,MODULES
from app.errors import DomainError
from app.modules.m8_revision import service

bp=Blueprint('m8_revision',__name__)

def latest_run_id():
    history=store.history()
    return history[0]['id'] if history else None

def pick(revisions,rev_id):
    if rev_id:
        found=[r for r in revisions if r['id']==rev_id]
        if not found:raise DomainError('NOT_FOUND','修订记录不存在',404)
        return found[0]
    effective=[r for r in revisions if r['status']=='生效']
    return effective[-1] if effective else (revisions[-1] if revisions else None)

@bp.get('/m8_revision')
def screen():
    run_id=request.args.get('run') or latest_run_id()
    if not run_id:raise DomainError('NOT_FOUND','批次不存在',404)
    base=store.get(run_id);revisions=store.revisions_for(run_id)
    revision=pick(revisions,request.args.get('rev'))
    return render_template('m8_revision.html',title=TITLE,short=SHORT,modules=MODULES,current=len(MODULES),
        data=base,run=base,history=store.history(),revisions=revisions,revision=revision,
        signed=base['decision']=='通过',samples=service.correction_samples())

@bp.get('/api/m8_revision')
def overview():
    run_id=latest_run_id()
    if not run_id:return jsonify(signed=False,revisions=[])
    base=store.get(run_id)
    return jsonify(run_id=run_id,decision=base['decision'],signed=base['decision']=='通过',
        revisions=[{k:r[k] for k in ('id','seq','status','error','created_at')} for r in store.revisions_for(run_id)])

@bp.get('/api/runs/<run_id>/revisions')
def list_revisions(run_id):
    store.get(run_id)
    return jsonify(store.revisions_for(run_id))

@bp.get('/api/runs/<run_id>/revisions/<rev_id>')
def read_revision(run_id,rev_id):
    record=store.get_revision(rev_id)
    if record['run_id']!=run_id:raise DomainError('NOT_FOUND','修订记录不存在',404)
    return jsonify(record)

@bp.post('/api/runs/<run_id>/revisions')
def submit(run_id):
    base=store.get(run_id)
    if base['decision']!='通过':raise DomainError('UNSIGNED','批次未签字出证，不能修订')
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise DomainError('PAYLOAD','请求必须是对象')
    limits=data.get('limits_csv') or '';reports=data.get('reports_csv') or ''
    if not isinstance(limits,str) or not isinstance(reports,str):raise DomainError('PAYLOAD','更正内容必须是文本')
    limits,reports=limits.strip(),reports.strip()
    if not limits and not reports:raise DomainError('EMPTY','未提交更正内容')
    rev_id=service.revision_id(run_id,limits,reports)
    existing=store.find_revision(rev_id)
    if existing:
        existing['reused']=True
        if existing['status']=='失败':
            return jsonify(code='REVISION',message=existing['error']+'，旧版结论保持有效',revision=existing),422
        return jsonify(existing)
    try:
        outcome=service.adjudicate(base,limits,reports)
    except DomainError as e:
        record=store.save_revision(rev_id,run_id,'失败','%s: %s'%(e.code,e.message),None)
        return jsonify(code=e.code,message=e.message+'，旧版结论保持有效',revision=record),422
    return jsonify(store.save_revision(rev_id,run_id,'生效',None,outcome))
