"""只读派生的01问题入口；不写复盘、原因或核查状态，不改变正式审核。"""
from collections import Counter
from decimal import Decimal as D
from core import decimal_value,valid_count,newest_diff,current_total,validate_all,summary
from reporting import money

def issue_model(items,meta,engine):
    counts={field:Counter(x.get(field) for x in items) for field in ('商品编码','商品条码','记录ID')};byid={}
    for x in items:
        key=x['记录ID'];diff=newest_diff(x);cost=decimal_value(x.get('成本价'));reviewed=valid_count(x.get('复盘实数'))
        missing_reason=reviewed and diff not in (None,0) and (not str(x.get('备注') or '').strip() or decimal_value(x.get('备注')) is not None)
        invalid=bool(validate_all([x])) or any(x.get(f) and counts[f][x[f]]>1 for f in counts)
        unresolved=bool(engine.count(key) or engine.count(key,'swap')) and not engine.resolved(key,meta.get('pair_proofs',{})) and x.get('核实结论','') not in ('已排除','无需调整') and not (x.get('核实结论')=='确认并附单据' and str(x.get('相关单号') or '').strip())
        initial=decimal_value(x.get('初盘数'));total=current_total(x);change=None if initial is None or total is None else total-initial
        significant=reviewed and change is not None and (abs(change)>=20 or abs(change)>=2 and abs(change)>=abs(initial)*D('.5'))
        byid[key]={'pending':not reviewed,'missing_cost':cost is None,'missing_code':not x.get('商品编码') or not x.get('商品条码'),
            'missing_reason':bool(missing_reason),'invalid':bool(invalid),'export_issue':bool(not reviewed or invalid or missing_reason or unresolved),
            'significant_change':bool(significant)}
    s=summary(items,meta.get('sales_cost'));cost=decimal_value(meta.get('sales_cost'));net=s['净差异']
    rate=None if cost is None or cost<=0 or net is None else max(D(0),-net)/cost*1000
    progress={k:sum(r[k] for r in byid.values()) for k in ('pending','missing_cost','missing_code','missing_reason','export_issue')}
    progress['net_loss_rate']=None if rate is None else money(rate)
    return byid,progress
