"""01/02/03共用的供应商归属。目录和确认信息仅在本机，不硬编码真实供应商编码。"""
from collections import defaultdict
from datetime import datetime,date
from zoneinfo import ZoneInfo
from core import default_vendors,as_code

CANONICAL='卓不凡'
ALIASES={CANONICAL,'桌不凡'}

def effective_vendors(state,local=None):
    rows=state.get('vendors',[])+(default_vendors() if local is None else local)
    unique={tuple(sorted((k,str(v)) for k,v in row.items())):row for row in rows}
    return list(unique.values())

class SupplierDirectory:
    def __init__(self,vendors,meta=None,today=None):
        self.meta=meta or {};self.today=today or datetime.now(ZoneInfo('Asia/Shanghai')).date()
        self.groups=defaultdict(list);names=defaultdict(set);self.invalid=set()
        for row in vendors:
            bc=as_code(row.get('商品条码'));code=as_code(row.get('供货商编码'));name=str(row.get('供货商名称') or '').strip()
            if not bc:continue
            try:
                start=self._date(row.get('生效日期'));end=self._date(row.get('失效日期'))
            except ValueError:self.invalid.add(bc);continue
            if start and start>self.today or end and end<self.today:continue
            self.groups[bc].append((code,name))
            if code:names[code].add(name)
        self.zbf_codes={code for code,ns in names.items() if CANONICAL in ns and ns<=ALIASES}
        self.ambiguous_codes={code for code,ns in names.items() if len(ns)>1 and not ns<=ALIASES}
        # 人工确认仅允许目录内实际存在的编码，不能凭空增加商品名单。
        self.zbf_codes.update(code for code in self.meta.get('zbf_confirmed_codes',[]) if code in names)

    @staticmethod
    def _date(value):
        if value in (None,''):return None
        if isinstance(value,datetime):return value.date()
        if isinstance(value,date):return value
        return date.fromisoformat(str(value).strip()[:10])

    def classify(self,item):
        bc=as_code(item.get('商品条码'));rows=self.groups.get(bc,[])
        pending=lambda reason:{'status':'pending','name':'供货商待确认','code':'','reason':reason}
        if bc in self.invalid:return pending('目录有效日期无法确认')
        if not rows:return pending('本机有效目录未匹配完整条码')
        selected=self.meta.get('supplier_codes',{}).get(bc)
        if selected:rows=[r for r in rows if r[0]==selected]
        elif self.meta.get('main_suppliers',{}).get(bc):
            selected_name=self.meta['main_suppliers'][bc]
            rows=[r for r in rows if r[1]==selected_name]
        codes={c for c,n in rows};names={n for c,n in rows}
        if len(codes)!=1 or not next(iter(codes),''):return pending('多供应商冲突或缺少唯一有效供应商编码')
        code=next(iter(codes))
        if code in self.zbf_codes:return {'status':'zbf','name':CANONICAL,'code':code,'reason':'完整条码及有效供应商编码已确认'}
        if code in self.ambiguous_codes:return pending('同一供应商编码对应不同目录名称，尚未核实')
        if names&ALIASES:return pending('名称别名尚未与已确认的卓不凡编码对应')
        if len(names)!=1 or not next(iter(names),''):return pending('同一编码的供应商名称存在冲突')
        return {'status':'other','name':next(iter(names)),'code':code,'reason':'有效目录唯一编码'}

    def classify_all(self,items):return {x['记录ID']:self.classify(x) for x in items}
