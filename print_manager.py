"""按需选择、稳定序号、原PDF快照重印。打印行为不改复盘数量。"""
import hashlib
import io
import uuid
from core import valid_count,newest_diff,current_amount,num,current_total,json_bytes
from storage import now
from pdf_renderer import render_pdf

MODES={'remaining':'未填实数且仍有差异（默认）','new':'从未出单的未复盘差异','difference':'当前仍有差异（含已复盘）','all':'全部商品（可额外选择）'}

def printable_items(items,mode='remaining',categories=None,sort='category',printed_ids=()):
    if mode not in MODES:raise ValueError('未知打印范围')
    result=[]
    for x in items:
        if mode in ('remaining','new') and valid_count(x.get('复盘实数')):continue
        if mode in ('remaining','new') and newest_diff(x)==0:continue
        if mode=='new' and x['记录ID'] in printed_ids:continue
        if mode=='difference' and newest_diff(x)==0:continue
        if categories is not None and (x['大类'] or '未分类') not in categories:continue
        result.append(x)
    if sort=='category':result.sort(key=lambda x:x['序号'])
    elif sort=='amount':result.sort(key=lambda x:(-abs(current_amount(x) or 0),x['序号']))
    elif sort=='source':result.sort(key=lambda x:(x['来源'],x['工作表'],x['原始行号']))
    else:raise ValueError('未知排序')
    return result

def snapshot_rows(items):
    rows=[]
    for x in items:
        if newest_diff(x) is None or current_total(x) is None:
            raise ValueError('含无法计算的商品，请先核对初盘原件')
        rows.append({'sequence':x['序号'],'category':x['大类'] or '未分类',
          'name':x['商品名称'],'barcode':x['商品条码'],'code':x['商品编码'],
          'system':num(x['系统数']),'initial':num(x['初盘数']),
          'difference':num(newest_diff(x)),'current_total':num(current_total(x)),
          'recount':num(x['复盘实数']),'note':x.get('备注',''),'source_id':x['记录ID']})
    return rows

def selection_hash(items,meta,mode,sort,categories):
    return hashlib.sha256(json_bytes([snapshot_rows(items),meta,mode,sort,categories])).hexdigest()

def make_pdf(items,meta,batch,pid='PREVIEW',time=None,scope='剩余未复盘'):
    if not items:raise ValueError('本次范围无商品，不生成空白PDF')
    fp=io.BytesIO()
    pages=render_pdf(fp,snapshot_rows(items),meta['store'],meta['period'],batch,pid,time or now(),scope)
    return fp.getvalue(),pages

def generate_print(store,batch,items,meta,mode,sort,categories,revision):
    pid='P'+uuid.uuid4().hex[:20];time=now()
    pdf,pages=make_pdf(items,meta,batch,pid,time,MODES[mode])
    snap={'id':pid,'batch':batch,'time':time,'parent':None,'mode':mode,'sort':sort,
          'categories':categories,'rows':snapshot_rows(items),'count':len(items),'pages':pages,
          'revision':revision,'store':meta['store'],'period':meta['period'],
          'pdf_sha256':hashlib.sha256(pdf).hexdigest()}
    store.add_print(batch,snap,pdf,revision)
    return snap,pdf

def reprint(store,batch,ident,revision):
    old=next((p for p in store.prints(batch) if p['id']==ident),None)
    if old is None:raise ValueError('没有找到历史打印批次')
    pdf=store.print_pdf(batch,ident)
    snap={**old,'id':'P'+uuid.uuid4().hex[:20],'time':now(),'parent':ident,'mode':'repeat'}
    store.add_print(batch,snap,pdf,revision)
    return snap,pdf
