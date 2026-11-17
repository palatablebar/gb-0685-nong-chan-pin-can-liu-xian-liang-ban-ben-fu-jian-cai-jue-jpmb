RANK={'PASS':0,'UNCERTAIN':1,'FAIL':2}

def key(c):return (c['sample_id'],c['batch'],c['analyte'])

def brief(c):
    return {'report':c['id'],'code':c['code'],'limit':c['limit'],'standard':c['standard'],'replaces':c.get('replaces')}

def entry(k,c,causes):
    return {'sample_id':k[0],'batch':k[1],'analyte':k[2],'old':brief(c[0]) if c[0] else None,'new':brief(c[1]) if c[1] else None,'causes':causes}

def describe(c):
    old=c['old']['code'] if c['old'] else '—';new=c['new']['code'] if c['new'] else '—'
    return '%s/%s %s→%s（%s）'%(c['sample_id'],c['analyte'],old,new,'+'.join(c['causes']))

def diff_states(old,new):
    old_items={key(c):c for c in old.get('calculations',[])}
    new_items={key(c):c for c in new.get('calculations',[])}
    items=[];added=[];removed=[]
    for k in sorted(old_items.keys()&new_items.keys()):
        o,n=old_items[k],new_items[k];causes=[]
        if o['standard']!=n['standard'] or o['limit']!=n['limit']:causes.append('限量更正')
        if o['id']!=n['id']:causes.append('复检报告')
        if o['code']!=n['code'] or causes:items.append(entry(k,(o,n),causes))
    for k in sorted(new_items.keys()-old_items.keys()):added.append(entry(k,(None,new_items[k]),['复检报告']))
    for k in sorted(old_items.keys()-new_items.keys()):removed.append(entry(k,(old_items[k],None),['项目缺失']))
    old_g={g['batch']:g['code'] for g in old.get('reconcile',{}).get('grades',[])}
    new_g={g['batch']:g['code'] for g in new.get('reconcile',{}).get('grades',[])}
    grades=[]
    for b in sorted(set(old_g)|set(new_g)):
        o,n=old_g.get(b),new_g.get(b)
        if o is None:direction='新增批次'
        elif n is None:direction='移出批次'
        elif RANK[n]<RANK[o]:direction='升级'
        elif RANK[n]>RANK[o]:direction='降级'
        else:direction='不变'
        drivers=[c for c in items if c['batch']==b]
        if direction=='降级':drivers.sort(key=lambda c:RANK[c['new']['code']],reverse=True)
        elif direction=='升级':drivers.sort(key=lambda c:RANK[c['old']['code']],reverse=True)
        reason='；'.join(describe(c) for c in drivers[:4])
        if len(drivers)>4:reason+='；等%d项'%len(drivers)
        grades.append({'batch':b,'old':o,'new':n,'direction':direction,'changed':o!=n,'reason':reason or '—'})
    summary={'items_changed':len(items),'items_added':len(added),'items_removed':len(removed),
        'grades_changed':sum(1 for g in grades if g['changed']),
        'business_old':old.get('business'),'business_new':new.get('business')}
    return {'items':items,'added':added,'removed':removed,'grades':grades,'summary':summary}
