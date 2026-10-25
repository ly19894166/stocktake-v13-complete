"""可换货资格统一规则。资格不代表已核实换货，也不抵销任何盘点数量。"""
from datetime import date
from core import as_code
from supplier_policy import SupplierDirectory

def eligibility(items,vendors,meta=None,catalog=()):
    meta=meta or {};directory=SupplierDirectory(vendors,meta);entries={r['商品条码']:r for r in catalog}
    result={}
    for x in items:
        c=directory.classify(x);entry=entries.get(as_code(x['商品条码']));group='';source='';reason='未取得换货资格'
        if c['status']=='zbf':
            group='zbf:'+(c['code'] or 'canonical-without-code');source='卓不凡规则';reason=c['reason']
        elif entry and entry.get('是否启用') is True:
            if entry.get('商品编码')!=x.get('商品编码'):
                reason='条码对应商品编码不一致，资格待核实'
            elif entry.get('生效日期','9999')>directory.today.isoformat():
                reason='尚未到本批次基准日的生效日期'
            elif entry.get('换货组','').strip():
                group='manual:'+entry['换货组'].strip();source='人工加入';reason=entry.get('备注及依据','')
        result[x['记录ID']]={'eligible':bool(group),'group':group,'source':source,'reason':reason,'supplier':c}
    return result
