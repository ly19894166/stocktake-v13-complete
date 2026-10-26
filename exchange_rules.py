"""可换货资格统一规则。资格不代表已核实换货，也不抵销任何盘点数量。"""
from supplier_policy import SupplierDirectory

def eligibility(items,vendors,meta=None,catalog=()):
    meta=meta or {};directory=SupplierDirectory(vendors,meta)
    result={}
    for x in items:
        c=directory.classify(x);group='';source='';reason='仅已确认卓不凡具有A换B资格；人工档案仅留历史'
        if c['status']=='zbf':
            group='zbf:'+(c['code'] or 'canonical-without-code');source='卓不凡规则';reason=c['reason']
        result[x['记录ID']]={'eligible':bool(group),'group':group,'source':source,'reason':reason,'supplier':c}
    return result
