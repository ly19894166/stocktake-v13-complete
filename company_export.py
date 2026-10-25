"""01悬浮导出：每次预览/下载均重新读取全批次，保留既有正式阻断。"""
import base64,hashlib
from core import current_total,num,validate_all,export_blockers,create_company_xls,json_bytes
from intelligence import engine_for
from balance_service import supplier_signature

def export_signature(revision,state):
    return hashlib.sha256(json_bytes([revision,supplier_signature(state)])).hexdigest()

def snapshot(store,batch,request):
    with store.db:
        store.db.execute('BEGIN')
        items,_,state,rev=store.load(batch);engine=engine_for(items,state)
        blockers=export_blockers(items,state['meta'],state['vendors'],engine=engine);errors=validate_all(items)
        blob=create_company_xls(items,state['meta'],state['vendors'],engine=engine) if not blockers else None
        result={'id':request,'batch':batch,'revision':rev,'signature':export_signature(rev,state),'store':state['meta']['store'],'period':state['meta']['period'],
            'count':len(items),'done':sum(x.get('复盘实数') is not None for x in items),'remaining':sum(x.get('复盘实数') is None for x in items),
            'errors':errors,'blockers':blockers,'coverage':bool(state['meta'].get('coverage')),'evidence':bool(state['meta'].get('evidence')),
            'headers':['商品编码','商品条码','数量'],'rows':[[x['商品编码'],x['商品条码'],str(current_total(x)) if current_total(x) is not None else None] for x in items],
            'xls':base64.b64encode(blob).decode('ascii') if blob else None,'sha256':hashlib.sha256(blob).hexdigest() if blob else None}
        return result
