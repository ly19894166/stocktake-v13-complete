"""01悬浮导出：每次预览/下载均重新读取全批次，保留既有正式阻断。"""
import base64,hashlib,io
from core import current_total,num,validate_all,export_blockers,create_company_xls,json_bytes
from intelligence import engine_for
from balance_service import supplier_signature

def export_signature(revision,state):
    return hashlib.sha256(json_bytes([revision,supplier_signature(state)])).hexdigest()

def current_draft_xls(items):
    """只读当前快照，三列不补假值；与正式候选的严格入口分开。"""
    import xlwt
    if len(items)>65535:raise ValueError('XLS最多65535条明细，请核实批次范围')
    book=xlwt.Workbook(encoding='utf-8');sheet=book.add_sheet('当前核对草稿_未核实')
    text=xlwt.easyxf(num_format_str='@')
    for c,h in enumerate(('商品编码','商品条码','数量')):sheet.write(0,c,h)
    for r,item in enumerate(items,1):
        sheet.write(r,0,str(item.get('商品编码') or ''),text);sheet.write(r,1,str(item.get('商品条码') or ''),text)
        value=current_total(item)
        sheet.write(r,2,'' if value is None else str(value) if len(value.as_tuple().digits)>15 else float(value))
    for c,width in enumerate((18,25,18)):sheet.col(c).width=width*256
    stream=io.BytesIO();book.save(stream);return stream.getvalue()

def snapshot(store,batch,request):
    with store.db:
        store.db.execute('BEGIN')
        items,_,state,rev=store.load(batch);engine=engine_for(items,state)
        blockers=export_blockers(items,state['meta'],state['vendors'],engine=engine);errors=validate_all(items)
        blob=create_company_xls(items,state['meta'],state['vendors'],engine=engine) if not blockers else None
        draft=current_draft_xls(items)
        result={'id':request,'batch':batch,'revision':rev,'signature':export_signature(rev,state),'store':state['meta']['store'],'period':state['meta']['period'],
            'count':len(items),'done':sum(x.get('复盘实数') is not None for x in items),'remaining':sum(x.get('复盘实数') is None for x in items),
            'errors':errors,'blockers':blockers,'coverage':bool(state['meta'].get('coverage')),'evidence':bool(state['meta'].get('evidence')),
            'headers':['商品编码','商品条码','数量'],'rows':[[x['商品编码'],x['商品条码'],str(current_total(x)) if current_total(x) is not None else None] for x in items],
            'xls':base64.b64encode(blob).decode('ascii') if blob else None,'sha256':hashlib.sha256(blob).hexdigest() if blob else None,
            'draft_xls':base64.b64encode(draft).decode('ascii'),'draft_sha256':hashlib.sha256(draft).hexdigest(),'draft_status':'当前核对草稿·未核实，不代表审批通过，不可作为正式系统上传候选'}
        return result
