"""只读卓不凡专项金额：正式实数与独立建议分开，不产生任何业务写入。"""
from decimal import Decimal as D
from core import current_amount,current_total,decimal_value,valid_count
from reporting import money
from supplier_policy import SupplierDirectory,effective_vendors
from exchange_rules import eligibility
from balance_service import identity,supplier_signature

def dashboard(items,state,revision,run=None):
    directory=SupplierDirectory(effective_vendors(state),state['meta']);classes=directory.classify_all(items)
    chosen=[x for x in items if classes[x['记录ID']]['status']=='zbf'];byid={x['记录ID']:x for x in chosen}
    amounts={x['记录ID']:current_amount(x) for x in chosen};unknown=[k for k,v in amounts.items() if v is None]
    missing=[x['记录ID'] for x in chosen if decimal_value(x.get('成本价')) is None]
    related=[x for x in items if directory.zbf_review(x)]
    known_gain=sum((v for v in amounts.values() if v is not None and v>0),D(0));known_loss=sum((v for v in amounts.values() if v is not None and v<0),D(0))
    net=None if unknown else known_gain+known_loss
    plan=(run or {}).get('plan') or {'rows':{},'relations':[]};fresh=bool(run and run['revision']==revision and run['signature']==supplier_signature(state))
    pending=[key for key,row in plan['rows'].items() if key in byid and row['stage']=='pending' and fresh]
    allowed=eligibility(items,effective_vendors(state),state['meta']);relations=[];verified=0
    for rel in plan['relations']:
        a,b=rel['a'],rel['b'];legs=[plan['rows'].get(k,{}) for k in (a,b)]
        valid=fresh and rel['status']=='verified' and all(k in byid and allowed[k]['eligible'] and allowed[k]['group']==leg.get('group') and leg.get('stage')=='confirmed' and bool(str(leg.get('note') or '').strip()) and identity(byid[k])==leg.get('identity') and decimal_value(byid[k].get('复盘实数'))==decimal_value(leg.get('confirmed')) for k,leg in zip((a,b),legs))
        if valid:
            valid=all(decimal_value(leg.get('base_total')) is not None for leg in legs) and sum((current_total(byid[k]) for k in (a,b)),D(0))==sum((decimal_value(leg['base_total']) for leg in legs),D(0))
        verified+=bool(valid)
        relations.append({'a':a,'b':b,'quantity':rel.get('q'),'status':rel['status'],'valid':bool(valid),'stale':not fresh,'awaiting':sum(leg.get('stage')=='pending' for leg in legs) if fresh else 0})
    reviewed=sum(valid_count(x.get('复盘实数')) for x in chosen);unmatched=[{'id':k,'reason':row.get('reason','待核实')} for k,row in plan['rows'].items() if k in byid and row['stage'] in ('unmatched','rejected')]
    risks=[]
    if len(chosen)>reviewed:risks.append(f'尚有{len(chosen)-reviewed}条未复盘，当前金额为复盘测算')
    if unknown:risks.append(f'{len(unknown)}条金额不完整，其中{len(missing)}条缺成本，不按0元处理')
    if related:risks.append(f'{len(related)}条卓不凡归属待核实，未计入已确认范围金额')
    if pending:risks.append(f'{len(pending)}条A换B建议仍待现场确认，未计入正式金额')
    if run and not fresh:risks.append('原建议版本已过期，请重新计算并核对关系')
    if not run:risks.append('暂无当前A换B建议，仅展示已保存盘点金额')
    if unmatched:risks.append(f'{len(unmatched)}条无法唯一匹配或已驳回，需继续核对')
    status='incomplete' if net is None else 'zero' if net==0 else 'loss' if net<0 else 'gain'
    message='金额不完整，暂不能计算距平账差额' if net is None else '当前金额已平' if net==0 else ('当前净盘亏，还差' if net<0 else '当前净盘盈，多出')+money(abs(net))+'元'
    def top(positive):
        rows=sorted((x for x in chosen if amounts[x['记录ID']] is not None and (amounts[x['记录ID']]>0 if positive else amounts[x['记录ID']]<0)),key=lambda x:(-abs(amounts[x['记录ID']]),x['序号']))
        return [{'id':x['记录ID'],'amount':money(amounts[x['记录ID']])} for x in rows[:10]]
    return {'total':len(chosen),'reviewed':reviewed,'unreviewed':len(chosen)-reviewed,'gain':None if unknown else money(known_gain),'loss':None if unknown else money(known_loss),'net':None if net is None else money(net),'distance':None if net is None else money(abs(net)),
        'known_gain':money(known_gain),'known_loss':money(known_loss),'status':status,'message':message,'missing_amount':len(unknown),'missing_cost':len(missing),'supplier_pending':len(related),'pending_suggestions':len(pending),'pending_ids':pending,'verified_relations':verified,'plan_current':fresh,'risks':risks,
        'analysis':{'gains':top(True),'losses':top(False),'relations':relations,'unmatched':unmatched,'missing_cost_ids':missing,'unreviewed_ids':[x['记录ID'] for x in chosen if not valid_count(x.get('复盘实数'))],'supplier_pending_ids':[x['记录ID'] for x in related]},'final_approved':False,'formal_balance_complete':False}
