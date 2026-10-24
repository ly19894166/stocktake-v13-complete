"""新任务的候选条件与排序：实时派生；不写人工原因、不抵销库存。"""
from __future__ import annotations
from collections import defaultdict,Counter
from decimal import Decimal as D
import heapq
import re
from core import decimal_value,rounded,newest_diff,current_total,current_amount,valid_count,supplier_map

DEFAULT_PARAMETERS={'cost_tolerance':False,'quantity_multiple':3,'quantity_large':20,
                    'high_amount':100,'priority_limit':20,'retail_tolerance':'0.01'}
EMPTY=frozenset()

def cents(v):
    v=decimal_value(v)
    return None if v is None else rounded(v,2)

def supplier_for(vendors,main=None):
    result=supplier_map(vendors)
    groups=defaultdict(set)
    for row in vendors:
        if row.get('商品条码') and row.get('供货商名称'):
            groups[str(row['商品条码'])].add(str(row['供货商名称']))
    for bc,name in (main or {}).items():
        if name in groups[bc]:result[bc]=name
    return result

class CandidateEngine:
    def __init__(self,items,vendors,parameters=None,main=None):
        self.items={x['记录ID']:x for x in items}
        self.parameters={**DEFAULT_PARAMETERS,**(parameters or {})}
        self.suppliers=supplier_for(vendors,main)
        self.diff={k:newest_diff(x) for k,x in self.items.items()}
        self.cost={k:cents(x.get('成本价')) for k,x in self.items.items()}
        self.index=defaultdict(set);self.vendor_index=defaultdict(set);self.barcodes=defaultdict(set)
        self._cache={}
        for key,x in self.items.items():
            self.barcodes[x['商品条码']].add(key)
            d=self.diff[key];c=self.cost[key]
            if d is None or d==0 or not x['商品条码']:continue
            sign=1 if d>0 else -1
            if c is not None:
                for field in ('部类','大类','中类'):
                    value=x.get(field) or (x.get('业务品类') if field=='中类' else '')
                    if value:self.index[field,str(value),c,sign].add(key)
            vendor=self.suppliers.get(x['商品条码'],'未在目录')
            if vendor not in ('','未在目录','多供货商·待核实'):
                self.vendor_index[vendor,sign].add(key)
        self._unique_barcodes=len(self.barcodes)==len(items)
        self._peer_cache={}

    def raw_neighbors(self,key,kind='mix'):
        x=self.items[key];d=self.diff[key];c=self.cost[key]
        if not x['商品条码'] or d is None or d==0:return EMPTY
        if kind=='all':
            mix,swap=self.raw_neighbors(key),self.raw_neighbors(key,'swap')
            if not mix:return swap
            if not swap:return mix
            sig=('all',id(mix),id(swap))
            if sig not in self._cache:self._cache[sig]=mix|swap
            return self._cache[sig]
        sign=-1 if d>0 else 1
        if kind=='swap':
            result=self.vendor_index.get((self.suppliers.get(x['商品条码']),sign),EMPTY)
        else:
            if c is None:return EMPTY
            classes=tuple(x.get(f) or (x.get('业务品类') if f=='中类' else '') for f in ('部类','大类','中类'))
            signature=(classes,c,sign,bool(self.parameters['cost_tolerance']))
            if signature not in self._cache:
                result=set()
                prices=(c-D('.01'),c,c+D('.01')) if self.parameters['cost_tolerance'] else (c,)
                for field,val in zip(('部类','大类','中类'),classes):
                    if val:
                        for price in prices:result.update(self.index.get((field,str(val),price,sign),()))
                self._cache[signature]=result
            result=self._cache[signature]
        return result

    def neighbors(self,key,kind='mix'):
        return self.raw_neighbors(key,kind)-self.barcodes[self.items[key]['商品条码']]

    def count(self,key,kind='mix'):
        raw=self.raw_neighbors(key,kind)
        own=self.barcodes[self.items[key]['商品条码']]
        return len(raw)-sum(k in raw for k in own)

    def resolved(self,key,proofs):
        raw=self.raw_neighbors(key,'all');total=self.count(key,'all')
        if not total:return True
        if not proofs:return False
        if getattr(self,'_proofs_id',None)!=id(proofs):
            self._proofs_id=id(proofs);self._proofs=defaultdict(set)
            byseq={str(x['序号']):k for k,x in self.items.items()}
            for pair,v in proofs.items():
                if not str(v.get('说明','')).strip():continue
                parts=pair.split('|')
                if len(parts)==2 and all(p in byseq for p in parts):
                    a,b=(byseq[p] for p in parts);self._proofs[a].add(b);self._proofs[b].add(a)
        return sum(k in raw and self.items[k]['商品条码']!=self.items[key]['商品条码'] for k in self._proofs[key])==total

    def pair(self,a,b):
        x,y=self.items[a],self.items[b]
        if x['商品条码']==y['商品条码']:return None
        mix=b in self.raw_neighbors(a);swap=b in self.raw_neighbors(a,'swap')
        if not mix and not swap:return None
        level,category=0,''
        for field,label,n in (('中类','同中类',3),('大类','同大类',2),('部类','同部类',1)):
            if x.get(field) and x[field]==y.get(field):level,category=n,label;break
        retail_a,retail_b=cents(x.get('零售价')),cents(y.get('零售价'))
        same_retail=retail_a is not None and retail_b is not None and retail_a==retail_b
        same_brand=bool(x.get('品牌') and x.get('品牌')==y.get('品牌'))
        same_spec=bool(x.get('销售规格') and x.get('销售规格')==y.get('销售规格'))
        balanced=self.diff[a]+self.diff[b]==0
        overlap=min(abs(self.diff[a]),abs(self.diff[b]))
        amount=overlap*min(self.cost[a] or 0,self.cost[b] or 0)
        strength=(1+level if mix else 0)+int(same_retail)+int(balanced)
        confidence='较强线索' if strength>=5 else '一般线索' if strength>=3 else '弱线索'
        evidence=[category if mix else '',('成本按分相同' if self.cost[a]==self.cost[b] else '已启用成本±0.01元容差') if mix else '',
                  '同供货商' if swap else '', '售价相同' if same_retail else
                  '缺售价·待补证据' if retail_a is None or retail_b is None else '售价不同·需核规格',
                  '反向数量相等' if balanced else '反向差异可解释部分数量',
                  '品牌相同' if same_brand else '', '规格相同' if same_spec else '']
        return {'a':a,'b':b,'kind':'疑似串码串销＋同供应商A换B' if mix and swap else '疑似串码串销' if mix else '同供应商A换B候选',
          'mix':mix,'swap':swap,'level':level,'confidence':confidence,'strength':strength,
          'overlap':float(overlap),'amount_overlap':float(rounded(amount,2)),
          'evidence':'；'.join(v for v in evidence if v),'category_match':category,
          'sort':(-strength,-level,-int(same_retail),-int(balanced),-int(same_brand),-int(same_spec),-int(swap),-amount,y['商品条码'])}

    def peers(self,key,limit=3,offset=0,kind='all'):
        x=self.items[key]
        profile=(kind,tuple(x.get(f) for f in ('部类','大类','中类')),self.cost[key],self.diff[key],cents(x.get('零售价')),
                 self.suppliers.get(x['商品条码']),str(x.get('品牌') or ''),str(x.get('销售规格') or ''))
        cached=self._peer_cache.get(profile)
        if self._unique_barcodes and cached and cached[0]>=offset+limit:
            best=[self.pair(key,k) for k in cached[1][:offset+limit]]
        else:
            ids=self.neighbors(key,kind if kind in ('mix','swap') else 'all')
            best=heapq.nsmallest(offset+limit,(self.pair(key,k) for k in ids),key=lambda p:p['sort'])
            if self._unique_barcodes:self._peer_cache[profile]=(offset+limit,[p['b'] for p in best])
        result=[]
        for p in best[offset:]:
            other=self.items[p['b']]
            result.append({k:v for k,v in p.items() if k!='sort'}|{'id':p['b'],'name':other['商品名称'],
                'barcode':other['商品条码'],'diff':float(self.diff[p['b']]),'sequence':other['序号']})
        return result

def unit_hints(x,parameters=None):
    p={**DEFAULT_PARAMETERS,**(parameters or {})};hints=[]
    current=decimal_value(current_total(x));system=decimal_value(x.get('系统数'));diff=newest_diff(x)
    factor=decimal_value(x.get('包装系数'))
    if factor is None:
        spec=str(x.get('销售规格',''))+' '+str(x.get('件装单位',''))
        m=re.search(r'(\d+(?:\.\d+)?)\s*(?:瓶|支|袋|盒|罐|包|件)\s*[/／]\s*箱',spec)
        if m:factor=decimal_value(m.group(1))
    if factor is not None and factor>1 and diff not in (None,0) and abs(diff)%factor==0:
        hints.append(f'可能整箱/散支误差：差异是资料包装系数{factor}的{abs(diff)/factor:g}倍，需核单位')
    elif current is not None and system is not None and system>0 and current>system and current%system==0 and current/system>=2:
        hints.append(f'可能单位误录：实数为系统数{current/system:g}倍；包装系数未提供，仅作猜测')
    if decimal_value(x.get('原始调整'),D(0))!=0:hints.append('原始换算/子转母调整非零，核对单位说明')
    if current is not None and system is not None and abs(current)>max(D(str(p['quantity_large'])),abs(system)*D(str(p['quantity_multiple']))):
        hints.append('数量异常大，核对计量与录入')
    return hints

def priority(x,candidate_count=0,parameters=None):
    p={**DEFAULT_PARAMETERS,**(parameters or {})};amount=abs(current_amount(x) or 0);d=newest_diff(x)
    parts={'金额':min(60,int(amount//30))}
    if d is not None and d<0:parts['盘亏']=10
    if current_total(x)==0 and d is not None and d<0:parts['实物为零']=5
    if decimal_value(x.get('系统数'),D(0))<0:parts['负库存']=6
    if candidate_count:parts['候选']=min(15,5*candidate_count)
    if not valid_count(x.get('复盘实数')):parts['未复盘']=5
    if unit_hints(x,p):parts['单位/异常量']=5
    return sum(parts.values()),' + '.join(f'{k}{v}' for k,v in parts.items())+'（建议排序，非审核标准）'

FILTERS=('未填复盘','盘亏','盘盈','仍有差异','疑似串码','同供应商A换B','可能跨店调拨','高金额','负库存','缺成本','零成本','缺编码','重复条码','异常换算','缺文字原因','数据错误')

def row_models(items,state,engine=None,cross=None,enrich=()):
    engine=engine or CandidateEngine(items,state['vendors'],state['meta'].get('parameters'),state['meta'].get('main_suppliers'))
    params=engine.parameters;cross=cross or {};duplicate=Counter(x['商品条码'] for x in items)
    packing=defaultdict(set)
    for v in state['vendors']:
        factor=decimal_value(v.get('包装系数'))
        if factor is not None and factor>1:packing[str(v.get('商品条码',''))].add(factor)
    rows=[]
    for x in items:
        key=x['记录ID'];diff=engine.diff[key];amount=current_amount(x);cost=decimal_value(x.get('成本价'))
        mix=engine.count(key);swap=engine.count(key,'swap')
        info=x
        factors=packing[x['商品条码']]
        if not decimal_value(x.get('包装系数')) and len(factors)==1:info={**x,'包装系数':next(iter(factors))}
        hints=unit_hints(info,params)
        if len(factors)>1:hints.append('供应商目录包装系数有冲突，需人工核实，不自动换算')
        flags=[]
        if not valid_count(x.get('复盘实数')):flags.append('未填复盘')
        if diff is not None and diff<0:flags.append('盘亏')
        if diff is not None and diff>0:flags.append('盘盈')
        if diff not in (None,0):flags.append('仍有差异')
        if mix:flags.append('疑似串码')
        if swap:flags.append('同供应商A换B')
        if cross.get(key):flags.append('可能跨店调拨')
        if abs(amount or 0)>=D(str(params['high_amount'])):flags.append('高金额')
        if decimal_value(x.get('系统数'),D(0))<0:flags.append('负库存')
        if cost is None:flags.append('缺成本')
        elif cost==0:flags.append('零成本')
        if not x.get('商品编码') or not x.get('商品条码'):flags.append('缺编码')
        if duplicate[x['商品条码']]>1:flags.append('重复条码')
        if hints:flags.append('异常换算')
        risks=[]
        for flag,label in (('负库存','系统库存为负，核对来源'),('缺成本','缺成本，金额不可计算'),
                           ('零成本','成本为0，待核成本资料'),('缺编码','缺商品编码或条码，禁止正式导出'),
                           ('重复条码','条码重复，禁止静默合并或覆盖')):
            if flag in flags:risks.append(label)
        if valid_count(x.get('复盘实数')) and diff not in (None,0) and (not str(x.get('备注','')).strip() or decimal_value(x.get('备注')) is not None):
            flags.append('缺文字原因');risks.append('缺文字原因：已填实数仍有差异')
        source_errors=[p['说明'] for p in x.get('导入问题',[]) if p['等级']=='阻断']
        if source_errors:flags.append('数据错误');risks.extend(source_errors[:3])
        if engine.suppliers.get(x['商品条码'])=='多供货商·待核实':risks.append('多供应商冲突：可在供应商数据库选主或保留未知')
        score,why=priority(x,mix+swap,params)
        peers=engine.peers(key) if key in enrich else []
        rows.append({'id':key,'sequence':x['序号'],'name':x['商品名称'],'barcode':x['商品条码'],'code':x['商品编码'],
           'category':x.get('大类') or '未分类','department':x.get('部类',''),'middle':x.get('中类',''),
           'system':None if x['系统数'] is None else float(x['系统数']),
           'initial':None if x['初盘数'] is None else float(x['初盘数']),
           'recount':None if x.get('复盘实数') is None else float(x['复盘实数']),
           'total':None if current_total(x) is None else float(current_total(x)),
           'diff':None if diff is None else float(diff),'amount':None if amount is None else float(amount),
           'cost':None if cost is None else float(cost),'retail':None if decimal_value(x.get('零售价')) is None else float(decimal_value(x['零售价'])),
           'supplier':engine.suppliers.get(x['商品条码'],'未在目录'),'note':x.get('备注',''),
           'spec':x.get('销售规格',''),'unit':x.get('件装单位',''),
           'packing':str(info.get('包装系数') or '未提供，不自动推定'),
           'cost_basis':f"{x.get('原文件','')} / {x.get('工作表','')} / 第{x.get('原始行号','')}行；原件成本{x.get('原始字段',{}).get('成本价','未提供')}；当前成本{cost if cost is not None else '缺失'}",
           'mix_count':mix,'swap_count':swap,'peers':peers,'flags':flags,'unit_hints':hints,'risk_hints':risks,
           'score':score,'score_reason':why,'cross':cross.get(key,[])})
    return rows
