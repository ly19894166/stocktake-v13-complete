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
    engine=CandidateEngine(all_items,vendors,meta.get('parameters'),meta.get('main_suppliers'))
    order,partners=linked_order(items,engine,True);lookup={x['记录ID']:x for x in items};hints={}
    for a in order:
        b=partners.get(a)
        if b is None:
            peers=engine.peers(a,limit=1);b=peers[0]['id'] if peers else None
        if b:
            peer=engine.items[b];pair=engine.pair(a,b)
            line=('疑似与'+peer['商品名称']+'串码' if pair['mix'] else 'A换B线索：'+peer['商品名称'])+'（待核实）'
            hints[a]={'related':line,
                      'group':'|'.join(sorted((a,b))) if a in partners else ''}
    return [lookup[k] for k in order],hints
