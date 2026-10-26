"""只改变找货展示与打印顺序，不合并商品或修改库存。"""
from core import initial_diff,newest_diff,changes,decimal_value,current_amount
from intelligence import CandidateEngine

def quantity(value):
    value=decimal_value(value)
    return '未知' if value is None else format(value,'f').rstrip('0').rstrip('.') if '.' in format(value,'f') else str(value)

def change_description(x):
    before,after=initial_diff(x),newest_diff(x)
    if x.get('复盘实数') is None:return '未复盘'
    if before is None or after is None:return '数据待核实'
    c=changes(x);delta=c['复盘变化量']
    if delta==0:return '实数已确认 · 差异为0' if after==0 else '与初盘一致'
    labels=[]
    if c['找回数量'] and c['找回数量']>0:labels.append('找回'+quantity(c['找回数量'])+'件')
    elif c['盘盈减少量'] and c['盘盈减少量']>0:labels.append('盘盈减少'+quantity(c['盘盈减少量'])+'件')
    elif after<before:labels.append(('盘亏增加' if after<0 else '盘盈减少')+quantity(abs(delta))+'件')
    else:labels.append(('盘盈增加' if after>0 else '盘亏减少')+quantity(abs(delta))+'件')
    if after==0:labels.append('差异归零')
    elif before*after<0:labels.append(('转为盘盈' if after>0 else '转为盘亏')+quantity(abs(after))+'件')
    return ' · '.join(labels)

def linked_order(items,engine=None,loss_first=False):
    """每条真实记录只出现一次。优先采用最强尚未排入的对应商品。"""
    engine=engine or CandidateEngine(items,[])
    available={x['记录ID'] for x in items};base=sorted(items,key=lambda x:
        ((0 if newest_diff(x) is not None and newest_diff(x)<0 else 1) if loss_first else 0,
         -abs(current_amount(x) or 0),x['序号']))
    ids=[];partners={}
    for x in base:
        a=x['记录ID']
        if a not in available:continue
        available.remove(a);ids.append(a)
        # 先利用引擎的画像缓存；若前3条已排入，精确选择剩余最强候选。
        best=next((p['id'] for p in engine.peers(a) if p['id'] in available),None)
        if best is None:
            rest=engine.neighbors(a,'all')&available
            if rest:best=min(rest,key=lambda b:engine.pair(a,b)['sort'])
        if best is not None:
            available.remove(best);ids.append(best);partners[a]=best;partners[best]=a
    assert len(ids)==len(items) and len(set(ids))==len(items)
    return ids,partners

def print_layout(items,all_items,vendors,meta):
    """现场纸单仅按档案分类/确认路线找货，不输出智能配对内容。"""
    return print_order(items,'category',meta.get('print_route',[])),{}

def print_order(items,sort='category',route=()):
    if sort=='sequence':return sorted(items,key=lambda x:x['序号'])
    if sort=='amount':return sorted(items,key=lambda x:(-abs(current_amount(x) or 0),x['序号']))
    if sort=='source':return sorted(items,key=lambda x:(x['来源'],x['工作表'],x['原始行号']))
    if sort not in ('category','field'):raise ValueError('未知打印排序')
    ranks={str(value):i for i,value in enumerate(route)}
    return sorted(items,key=lambda x:(ranks.get(x.get('大类') or '未分类',len(ranks)),
        str(x.get('大类') or '未分类'),str(x.get('中类') or ''),x['序号']))
