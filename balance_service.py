"""卓不凡数量建议账本。草稿独立存放；逐条事实确认与实数/历史同事务提交。"""
import copy,hashlib,json,re,uuid
from decimal import Decimal as D
from core import decimal_value,current_total,newest_diff,patch_items,valid_count,json_bytes
from supplier_policy import effective_vendors
from exchange_rules import eligibility
from storage import now,dumps

def supplier_signature(state):
    rows=sorted(effective_vendors(state),key=lambda r:json.dumps(r,ensure_ascii=False,sort_keys=True,default=str))
    meta=state['meta'];basis={k:meta.get(k) for k in ('first_import_at','supplier_as_of','main_suppliers','supplier_codes','zbf_confirmed_codes')}
    return hashlib.sha256(json_bytes([rows,basis])).hexdigest()

def unit_key(x):
    unit=str(x.get('件装单位') or '').strip();packing=decimal_value(x.get('包装系数'))
    if not unit:return None,'缺少库存计量单位'
    if decimal_value(x.get('原始调整'),D(0)) and not str(x.get('单位说明') or '').strip():return None,'子转母/原始调整尚未核实单位说明'
    composite=unit in ('箱','提','组','套') or unit=='件' and (packing is not None and packing>1 or re.search(r'箱|件装|[/／]\s*件',str(x.get('销售规格') or '')))
    if unit=='件' and not str(x.get('销售规格') or '').strip():return None,'件装规格缺失，计量口径待核实'
    if composite:
        if packing is None or packing<=0 or not str(x.get('单位说明') or '').strip():return None,'整箱/件装计量口径依据不足，需核实包装系数及单位说明'
    # 包装资料有差异时不假定1:1。无箱装推断，不从商品名称猜换算。
    return (unit,str(packing.normalize()) if packing is not None else '1'),''

def identity(x):
    return hashlib.sha256(json_bytes({k:x.get(k) for k in ('记录ID','商品条码','商品编码','系统数','初盘数','原始调整','件装单位','销售规格','包装系数','单位说明','成本价')})).hexdigest()

def make_plan(items,state,old=None):
    allowed=eligibility(items,effective_vendors(state),state['meta']);byid={x['记录ID']:x for x in items};rows={};relations=[];reserved=set()
    for x in items:
        key=x['记录ID'];e=allowed[key]
        if not e['eligible']:continue
        unit,reason=unit_key(x);total=current_total(x);diff=newest_diff(x)
        rows[key]={'id':key,'peer':None,'group':e['group'],'unit':unit,'identity':identity(x),'base_total':str(total) if total is not None else None,
            'base_diff':str(diff) if diff is not None else None,'stage':'manual' if x.get('复盘实数') is not None else 'zero' if diff==0 else 'unmatched',
            'suggested':None,'draft':None,'q':'0','reason':reason or ('已有人工实盘，建议不覆盖' if x.get('复盘实数') is not None else '无可唯一确认的同范围反向商品'),'note':''}
    # 继续单方已经确认的关系：重新核实来源、数量、目录和对方未填状态，保留待完成转移。
    if old:
        for rel in old.get('relations',[]):
            a,b=rel['a'],rel['b']
            if a not in rows or b not in rows:continue
            legs=[old['rows'][a],old['rows'][b]];confirmed=[r for r in legs if r['stage']=='confirmed' and decimal_value(byid[r['id']].get('复盘实数'))==decimal_value(r.get('confirmed'))]
            valid=all(rows[k]['identity']==old['rows'][k]['identity'] and rows[k]['group']==old['rows'][k]['group'] for k in (a,b))
            if not valid:continue
            if len(confirmed)==2:
                for r in legs:rows[r['id']]=copy.deepcopy(r)
                relations.append(copy.deepcopy(rel));reserved.update((a,b))
            elif len(confirmed)==1:
                done=confirmed[0];pending=legs[1] if legs[0] is done else legs[0];x=byid[pending['id']]
                delta=D(done['confirmed'])-D(done['base_total'])
                if x.get('复盘实数') is not None or current_total(x)!=D(pending['base_total']):continue
                proposed=current_total(x)-delta;d=newest_diff(x)
                if not delta or not valid_count(proposed) or d is None or d*delta<=0 or abs(delta)>abs(d):continue
                rows[done['id']]=copy.deepcopy(done);rows[pending['id']]=copy.deepcopy(pending)
                rows[pending['id']].update(stage='pending',suggested=str(proposed),draft=str(proposed),q=str(abs(delta)),reason='另一端已确认；按实际已确认转移量重算，仍需现场核对')
                relations.append({**copy.deepcopy(rel),'status':'partial','q':str(abs(delta))});reserved.update((a,b))
    available=[x for x in items if x['记录ID'] in rows and x['记录ID'] not in reserved and x.get('复盘实数') is None and newest_diff(x) not in (None,0)]
    compatible={x['记录ID']:[] for x in available}
    for i,x in enumerate(available):
        a=x['记录ID'];ra=rows[a]
        for y in available[i+1:]:
            b=y['记录ID'];rb=rows[b]
            if x['商品条码']==y['商品条码'] or ra['group']!=rb['group'] or newest_diff(x)*newest_diff(y)>=0:continue
            if not ra['unit'] or not rb['unit']:continue
            if ra['unit']!=rb['unit']:
                ra['reason']=rb['reason']='计量单位或包装口径不同，不能按1:1平衡';continue
            compatible[a].append(b);compatible[b].append(a)
    for x in sorted(available,key=lambda x:(x['序号'],x['商品条码'])):
        a=x['记录ID'];candidates=compatible[a]
        if len(candidates)!=1:
            if len(candidates)>1:rows[a]['reason']='多个候选争抢同一数量，关联不唯一，仅作线索'
            continue
        b=candidates[0]
        if len(compatible[b])!=1:
            rows[a]['reason']='对应商品同时关联其他商品，不能重复分配';continue
        if a in reserved or b in reserved:continue
        gain=x if newest_diff(x)>0 else byid[b];loss=byid[b] if gain is x else x
        q=min(newest_diff(gain),-newest_diff(loss),current_total(gain))
        if q<=0:continue
        values={gain['记录ID']:current_total(gain)-q,loss['记录ID']:current_total(loss)+q}
        if any(v!=v.quantize(D('.0001')) or not valid_count(v) for v in values.values()):
            rows[a]['reason']=rows[b]['reason']='建议超出复盘四位小数精度或数量范围，需人工核实';continue
        for k,peer in ((a,b),(b,a)):
            value=str(values[k]);rows[k].update(peer=peer,stage='pending',suggested=value,original_suggested=value,draft=value,q=str(q),reason='同范围、同计量口径且唯一对应；保留未平衡差异，待现场核实')
        assert sum(values.values(),D(0))==current_total(gain)+current_total(loss)
        relations.append({'a':a,'b':b,'q':str(q),'status':'pending'});reserved.update((a,b))
    return {'rows':rows,'relations':relations}

class BalanceService:
    def __init__(self,store):self.store=store;self.db=store.db

    def latest(self,batch):
        r=self.db.execute('SELECT id,source_revision,current_revision,supplier_signature,version,payload FROM balance_runs WHERE batch=? AND active=1 ORDER BY rowid DESC LIMIT 1',(batch,)).fetchone()
        return None if not r else {'id':r[0],'source_revision':r[1],'revision':r[2],'signature':r[3],'version':r[4],'plan':json.loads(r[5])}

    def _guard(self,batch,run_id,version,revision,items,state):
        run=self.latest(batch)
        if not run or run['id']!=run_id or run['version']!=version:raise ValueError('建议已由另一窗口更新，请载入最新建议')
        if run['revision']!=revision or self.db.execute('SELECT revision FROM batches WHERE id=?',(batch,)).fetchone()[0]!=revision:raise ValueError('实盘数据版本已变化，请重新计算未确认建议')
        if run['signature']!=supplier_signature(state):raise ValueError('卓不凡目录版本已变化，请重新计算并核对')
        return run

    def _action(self,batch,run,item,kind,before,after,request,actor):
        self.db.execute('INSERT INTO balance_actions(batch,run_id,item_id,at,actor,kind,before_json,after_json,request_id) VALUES(?,?,?,?,?,?,?,?,?)',(batch,run,item,now(),actor,kind,dumps(before),dumps(after),request))

    def generate(self,batch,revision,request=None,actor='本机店长'):
        request=request or uuid.uuid4().hex;items,_,state,rev=self.store.load(batch)
        if rev!=revision:raise ValueError('数据已变化，请刷新后生成建议')
        previous=self.latest(batch);sig=supplier_signature(state);old=previous['plan'] if previous and previous['signature']==sig else None
        plan=make_plan(items,state,old)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            found=self.db.execute('SELECT id FROM balance_runs WHERE batch=? AND request_id=?',(batch,request)).fetchone()
            if found:return self.latest(batch)
            if self.db.execute('SELECT revision FROM batches WHERE id=?',(batch,)).fetchone()[0]!=rev:raise ValueError('生成期间数据已变化，未保存建议')
            ident='BAL'+uuid.uuid4().hex[:16];self.db.execute('UPDATE balance_runs SET active=0 WHERE batch=?',(batch,))
            self.db.execute('INSERT INTO balance_runs VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,batch,now(),rev,rev,sig,1,1,dumps(plan),request))
            self._action(batch,ident,None,'generate',previous or {},plan,request,actor)
        return self.latest(batch)

    def edit(self,batch,run_id,version,revision,item,value,note='',kind='draft',request=None,actor='本机店长'):
        if kind not in ('draft','reject'):raise ValueError('无效建议操作')
        request=request or uuid.uuid4().hex;items,_,state,rev=self.store.load(batch)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            if self.db.execute('SELECT 1 FROM balance_actions WHERE batch=? AND request_id=?',(batch,request)).fetchone():return self.latest(batch)
            run=self._guard(batch,run_id,version,revision,items,state);plan=copy.deepcopy(run['plan']);row=plan['rows'].get(item)
            if not row or row['stage']!='pending':raise ValueError('该商品没有可用的待核建议，已确认实盘不会被覆盖')
            before=copy.deepcopy(row)
            if kind=='reject':
                row.update(stage='rejected',reason='店长驳回，等待重新核对',note=note)
                peer=plan['rows'][row['peer']]
                if peer['stage']=='pending':peer.update(stage='unmatched',suggested=None,draft=None,reason='另一端已驳回，原分配不再有效')
                for rel in plan['relations']:
                    if item in (rel['a'],rel['b']):rel['status']='rejected'
            else:
                if not valid_count(value):raise ValueError('建议草稿须为非负有效数量，空白不是0')
                row.update(draft=str(current_total({'复盘实数':decimal_value(value),'初盘数':0})),note=note)
            self.db.execute('UPDATE balance_runs SET payload=?,version=version+1 WHERE id=?',(dumps(plan),run_id))
            self._action(batch,run_id,item,kind,before,row,request,actor)
        return self.latest(batch)

    def confirm(self,batch,run_id,version,revision,item,value,note,request=None,actor='本机店长'):
        request=request or uuid.uuid4().hex
        if self.db.execute('SELECT 1 FROM balance_actions WHERE batch=? AND request_id=?',(batch,request)).fetchone():return self.latest(batch)
        items,_,state,rev=self.store.load(batch);run=self._guard(batch,run_id,version,revision,items,state)
        plan=copy.deepcopy(run['plan']);row=plan['rows'].get(item);byid={x['记录ID']:x for x in items}
        if not row or row['stage']!='pending' or byid[item].get('复盘实数') is not None:raise ValueError('仅能确认尚未填写正式实盘的待核建议，已有人工实盘不覆盖')
        if not str(note).strip():raise ValueError('请填写本条现场核查说明，保留确认依据')
        if not valid_count(value):raise ValueError('现场实盘须为非负有效数，空白不是0')
        before=copy.deepcopy(row);value=current_total({'复盘实数':decimal_value(value),'初盘数':0});peer=plan['rows'][row['peer']]
        row.update(stage='confirmed',confirmed=str(value),confirmed_at=now(),note=note,draft=str(value))
        rel=next(r for r in plan['relations'] if item in (r['a'],r['b']));delta=value-D(row['base_total']);diff=D(row['base_diff'])
        if peer['stage']=='pending':
            proposed=D(peer['base_total'])-delta
            if delta and delta*diff<0 and abs(delta)<=D(rel['q']) and valid_count(proposed):
                row['q']=str(abs(delta))
                peer.update(suggested=str(proposed),draft=str(proposed),q=str(abs(delta)),reason='另一端已确认，按实际转移量重算；仍需现场确认');rel.update(status='partial',q=str(abs(delta)))
            else:
                row['q']='0';row['reason']='本条现场实数未支持原换货分配，仅保存实盘事实'
                peer.update(stage='unmatched',suggested=None,draft=None,reason='本条实盘未支持原平衡数量，另一端须重新核对');rel['status']='mismatch'
        elif peer['stage']=='confirmed':
            conserved=value+D(peer['confirmed'])==D(row['base_total'])+D(peer['base_total'])
            rel['status']='verified' if conserved and delta and delta*diff<0 else 'mismatch'
        else:rel['status']='mismatch'
        updated=patch_items(items,{item:{'复盘实数':value}})
        def commit(newrevision):
            current=self.latest(batch)
            if not current or current['id']!=run_id or current['version']!=version or current['signature']!=supplier_signature(state):raise ValueError('确认期间建议或目录已更新，实盘未写入')
            self.db.execute('UPDATE balance_runs SET payload=?,current_revision=?,version=version+1 WHERE id=?',(dumps(plan),newrevision,run_id))
            self._action(batch,run_id,item,'confirm',before,{'entry':row,'peer':peer,'relation':rel,'formal_before':byid[item].get('复盘实数'),'formal_after':value,'revision':newrevision},request,actor)
        self.store.save(batch,updated,state,revision,actor,'卓不凡逐条现场确认',request,transaction_hook=commit)
        return self.latest(batch)

    def history(self,batch):
        return [{'时间':t,'操作人':a,'操作':k,'商品记录':i,'修改前':json.loads(before),'修改后':json.loads(after)} for t,a,k,i,before,after in self.db.execute('SELECT at,actor,kind,item_id,before_json,after_json FROM balance_actions WHERE batch=? ORDER BY id DESC',(batch,))]
