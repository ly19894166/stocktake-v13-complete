"""一次完整升级的本机客户端：01直达、可见候选、证据和原有完整功能。"""
from pathlib import Path
import copy,os,io,csv,json,hashlib,html,sqlite3
from decimal import Decimal as D
import pandas as pd
import streamlit as st
from core import (VERSION,import_pair,patch_items,decimal_value,num,summary,current_total,
    newest_diff,current_amount,changes,change_rows,validate_all,export_blockers,import_v13,
    VENDOR_HEADERS,json_bytes,load_excel)
from storage import Store,now
from intelligence import CandidateEngine,engine_for,row_models,FILTERS,DEFAULT_PARAMETERS
from imports_exports import (identify_batch,supplier_import,generic_rows,cross_candidates,
    transactions_for,import_master,export_workbook)
from workbench_component import workbench
from reporting import financial_panel, report_document, validated_meta_value, report_defaults
from workflow import linked_order
from report_intake import resolve_reports
from supplier_policy import SupplierDirectory,effective_vendors
import legacy_views as legacy

ROOT=Path(__file__).resolve().parent
PAGES=['01 现场复盘与找差异','03 现场复核单打印','更多工具']

@st.cache_data(max_entries=5,show_spinner=False)
def parse(gn,gb,ln,lb):return import_pair((gn,gb),(ln,lb))

def dbroot():return Path(os.environ.get('STOCKTAKE_DATA_DIR',ROOT/'data'))
def actor():return st.session_state.get('operator','').strip() or '本机店长'
def table(rows,**kwargs):
    df=pd.DataFrame(rows)
    st.dataframe(df,hide_index=True,placeholder='',**kwargs)
    return df

def bulk_patches(text,items):
    bybarcode={}
    for x in items:bybarcode.setdefault(x['商品条码'],[]).append(x)
    patches={};seen=set()
    for n,row in enumerate(csv.reader(io.StringIO(text),delimiter='\t'),1):
        if not row or not any(v.strip() for v in row):continue
        if n==1 and row[0].strip() in ('商品条码','条码'):continue
        if len(row)<2:raise ValueError(f'第{n}行须有完整条码和实数，用Tab分隔')
        bc=row[0].strip()
        if bc in seen:raise ValueError('粘贴数据条码重复：'+bc)
        seen.add(bc)
        if len(bybarcode.get(bc,[]))!=1:raise ValueError('无法唯一匹配完整条码：'+bc)
        value=None if row[1].strip()=='' else row[1].strip()
        patch={'复盘实数':value}
        if len(row)>2:patch['备注']=row[2]
        if len(row)>3:patch['单位说明']=row[3]
        patches[bybarcode[bc][0]['记录ID']]=patch
    if not patches:raise ValueError('没有可保存的粘贴行')
    return patches

def component_action(batch):
    key='workbench_'+batch
    event=st.session_state.get(key,{}).get('action')
    if not event:return
    request=event.get('request_id','');ackkey='ack_'+batch
    if st.session_state.get(ackkey,{}).get('id')==request:return
    db=Store(dbroot())
    try:
        items,notes,state,rev=db.load(batch);kind=event.get('kind');mapping={x['记录ID']:x for x in items}
        if kind in ('edit','edits','bulk','undo','meta','export_checks'):
            if event.get('revision')!=rev:raise ValueError('另一窗口已更新。输入草稿仍保留，请刷新并核对后重试')
        if kind=='copy_snapshot' and event.get('purpose')=='reset' and event.get('revision')!=rev:
            raise ValueError('另一窗口已更新，请刷新后按最新数据生成汇报')
        if kind in ('edit','edits'):
            entries=event.get('entries',[]) if kind=='edits' else [event]
            if not entries or len(entries)>100:raise ValueError('连续录入范围无效')
            patches={};steps=[]
            for entry in entries:
                x=mapping.get(entry.get('id'));field=entry.get('field')
                if x is None or field not in ('复盘实数','备注'):raise ValueError('不是可编辑的01字段')
                current=x.get(field);base=entry.get('base')
                if field=='复盘实数':
                    if decimal_value(current)!=decimal_value(base):raise ValueError('该实数已被其他修改更新，草稿未覆盖现值')
                    value=None if str(entry.get('value','')).strip()=='' else entry.get('value')
                else:
                    if str(current or '')!=str(base or ''):raise ValueError('该原因已更新，草稿未覆盖现值')
                    value=entry.get('value','')
                patches.setdefault(x['记录ID'],{})[field]=value
                steps.append({'id':x['记录ID'],'field':field,'request_id':entry['request_id']})
            updated=patch_items(items,patches)
            db.save(batch,updated,state,rev,actor(),'01连续录入' if kind=='edits' else '01单元格编辑',request,steps)
        elif kind=='meta':
            scope,field=event.get('scope'),event.get('field')
            value=validated_meta_value(scope,field,event.get('value'))
            target=state['meta'] if scope=='finance' else state['meta'].setdefault('report',{})
            current=target.get(field)
            # 新汇报日期等默认值是视图默认值，旧批次无需预先写库。
            if scope=='report' and field not in target:current=report_defaults(state['meta']).get(field)
            numeric=scope=='finance' or field in ('fresh_sales','fresh_cost','fresh_gain','fresh_loss')
            changed_elsewhere=(decimal_value(current)!=decimal_value(event.get('base'))) if numeric else (current!=event.get('base'))
            if changed_elsewhere:
                raise ValueError('该经营或汇报字段已由另一窗口更新，草稿保留，请刷新核对')
            if field=='draft':
                signature=report_document(items,state['meta'])['signature']
                if event.get('signature')!=signature:raise ValueError('盘点数据已变化，人工文稿草稿保留；请核对最新生成文稿')
                target['draft_signature']=signature
            target[field]=value
            if scope=='report' and field=='reason' and value!=current:target['reason_confirmed']=False
            db.save(batch,items,state,rev,actor(),'01经营参数/汇报编辑',request)
        elif kind=='bulk':
            updated=patch_items(items,bulk_patches(event.get('text',''),items))
            db.save(batch,updated,state,rev,actor(),'01批量粘贴',request)
        elif kind=='undo':db.undo_last(batch,rev,actor())
        elif kind=='export_checks':
            if not all(isinstance(event.get(k),bool) for k in ('coverage','evidence')):raise ValueError('核查条件无效')
            state['meta'].update(coverage=event['coverage'],evidence=event['evidence'])
            db.save(batch,items,state,rev,actor(),'01导出完整性确认',request)
            from company_export import snapshot
            st.session_state['export_'+batch]=snapshot(db,batch,request)
        elif kind=='export_snapshot':
            from company_export import snapshot
            st.session_state['export_'+batch]=snapshot(db,batch,request)
        elif kind in ('balance_generate','balance_draft','balance_confirm','balance_reject'):
            from balance_service import BalanceService
            service=BalanceService(db)
            if kind=='balance_generate':service.generate(batch,event['revision'],request,actor())
            elif kind=='balance_confirm':service.confirm(batch,event['run'],event['version'],event['revision'],event['id'],event['value'],event.get('note',''),request,actor())
            else:service.edit(batch,event['run'],event['version'],event['revision'],event['id'],event.get('value'),event.get('note',''),'reject' if kind=='balance_reject' else 'draft',request,actor())
        elif kind=='scope':
            if event.get('scope') not in ('exclude','all','zbf'):raise ValueError('无效商品范围')
            st.session_state['exchange_scope_'+batch]=event['scope']
        elif kind=='view':
            prior=st.session_state.get('enrich_'+batch,[])
            st.session_state['enrich_'+batch]=list(dict.fromkeys(prior+[k for k in event.get('ids',[])[:201] if k in mapping]))[-4000:]
        elif kind=='copy_snapshot':
            if event.get('purpose')=='reset':
                state['meta'].setdefault('report',{}).pop('draft',None)
                state['meta']['report'].pop('draft_signature',None)
                db.save(batch,items,state,rev,actor(),'汇报按最新数据重新生成',request)
                items,notes,state,rev=db.load(batch)
            st.session_state['copy_'+batch]={'id':request,'revision':rev,**report_document(items,state['meta'])}
        elif kind=='detail':
            a,b=event.get('a'),event.get('b')
            if a not in mapping or b is not None and b not in mapping:raise ValueError('商品不存在')
            st.session_state['detail_'+batch]=(a,b);st.session_state['peer_limit_'+batch]=3
        elif kind=='more_peers':st.session_state['peer_limit_'+batch]=st.session_state.get('peer_limit_'+batch,50)+50
        elif kind!='refresh':raise ValueError('未识别操作')
        st.session_state[ackkey]={'id':request,'ok':True}
        if kind not in ('view','detail','more_peers'):st.session_state.pop('grid_error_'+batch,None)
    except (ValueError,KeyError,OSError,sqlite3.Error) as exc:
        st.session_state[ackkey]={'id':request,'ok':False}
        st.session_state['grid_error_'+batch]=str(exc)
    finally:db.close()

def render_workbench(db,batch,items,state,rev):
    engine=engine_for(items,state)
    cross=cross_candidates(items,db.evidence(batch))
    enrich=set(st.session_state.get('enrich_'+batch,[]))
    if not enrich:
        enrich={x['记录ID'] for x in sorted(items,key=lambda x:-abs(current_amount(x) or 0))[:20]}
    if len(items)<=1500:enrich={x['记录ID'] for x in items}
    selected=st.session_state.get('detail_'+batch)
    if selected:enrich.update(k for k in selected if k)
    rows=row_models(items,state,engine,cross,enrich)
    classes=SupplierDirectory(effective_vendors(state),state['meta']).classify_all(items)
    for row in rows:
        c=classes[row['id']];row['supplier']=c['name'];row['supplier_status']=c['status']
        if c['status']=='pending':row['risk_hints'].append('供货商待确认：'+c['reason'])
    byid={x['记录ID']:x for x in items}
    for row in rows:
        x=byid[row['id']]
        values={'system':decimal_value(x.get('系统数')),'initial':decimal_value(x.get('初盘数')),'recount':decimal_value(x.get('复盘实数')),'total':current_total(x),'diff':newest_diff(x),'amount':current_amount(x)}
        row['stats_raw']={k:format(v,'f') if v is not None else None for k,v in values.items()}
    mapping={r['id']:r for r in rows}
    stats=summary(items,state['meta'].get('sales_cost'))
    # 当前审核只计算计数和已核实凭证，不把所有候选边展开成永久记录。
    blockers=fast_blockers(items,state,engine)
    detail=None
    if selected and selected[0] in mapping:
        a,b=selected;limit=st.session_state.get('peer_limit_'+batch,3)
        peers=engine.peers(a,limit=limit)
        pair=engine.pair(a,b) if b and b in mapping else None
        if pair:pair={k:v for k,v in pair.items() if k!='sort'}
        detail={'a':mapping[a],'b':mapping.get(b),'pair':pair,
            'history':db.item_history(batch,b or a)[:50], 'peers':peers,
            'has_more':len(engine.neighbors(a)|engine.neighbors(a,'swap'))>limit}
    last=db.db.execute('SELECT at FROM events WHERE batch=? ORDER BY id DESC LIMIT 1',(batch,)).fetchone()
    order,partners=linked_order(items,engine) if len(items)<=1500 else ([x['记录ID'] for x in items],{})
    for row in rows:
        peer=partners.get(row['id']);row['partner']=peer
        # 原始序号视图显示引擎最优项；联排视图才使用相邻配对项。
        row['partner_peer']=None
        if peer and (not row['peers'] or row['peers'][0]['id']!=peer):
            p=engine.pair(row['id'],peer);other=engine.items[peer]
            row['partner_peer']={'id':peer,'name':other['商品名称'],'barcode':other['商品条码'],'diff':float(engine.diff[peer]),'kind':p['kind'],'mix':p['mix']}
        row['peers']=[{k:p[k] for k in ('id','name','barcode','diff','kind','mix')} for p in row['peers'][:1]]
    payload={'batch':batch,'native_summary':True,'active_scope':st.session_state.get('exchange_scope_'+batch,'exclude'),'revision':rev,'rows':rows,'pair_order':order,'filters':FILTERS,'enriched':list(enrich),
        'saved_at':last[0] if last else '', 'imported_at':state['meta']['first_import_at'],
        'ack':st.session_state.get('ack_'+batch),'error':st.session_state.get('grid_error_'+batch),
        'detail':detail,'finance':{'sales_amount':state['meta'].get('sales_amount'),'sales_cost':state['meta'].get('sales_cost')},
        'panel':financial_panel(items,state['meta']),'report':report_document(items,state['meta']),
        'copy_snapshot':st.session_state.get('copy_'+batch),
        'audit':('可在01顶部下载盘点结果' if not blockers else f'正式导出尚有{len(blockers)}项待办，点击下载盘点结果核查'),
        'stats':{'difference_count':sum(newest_diff(x) not in (None,0) for x in items),
           'done':stats['已复盘'],'pending':sum(x.get('复盘实数') is None and newest_diff(x) not in (None,0) for x in items),
           'loss':num(stats['盘亏']),'gain':num(stats['盘盈']),'net':num(stats['净差异']),
           'rate':num(stats['报损率']),'zero_count':sum(x.get('复盘实数') is not None and newest_diff(x)==0 for x in items)}}
    from company_export import export_signature
    payload['export_snapshot']=st.session_state.get('export_'+batch);payload['export_signature']=export_signature(rev,state)
    payload['balance']=None
    if st.session_state.get('exchange_scope_'+batch)=='zbf':
        from balance_service import BalanceService,supplier_signature
        service=BalanceService(db);run=service.latest(batch)
        if run is None:run=service.generate(batch,rev,'initial:'+batch+':'+str(rev)+':'+supplier_signature(state),actor())
        payload['balance']={**run,'stale':run['revision']!=rev or run['signature']!=supplier_signature(state)}
        payload['balance']['history']=[{'at':h['时间'],'kind':h['操作'],'item':h['商品记录'],
            'old':h['修改后'].get('formal_before'),'new':h['修改后'].get('formal_after'),
            'note':h['修改后'].get('entry',{}).get('note','')} for h in service.history(batch)[:100]]
    render_total_rail(payload['panel'])
    if st.session_state.get('exchange_scope_'+batch)=='zbf':
        from vendor_audit import audit_panel
        audit_panel(db,batch,items,state,rev)
    workbench(payload,lambda:component_action(batch),'workbench_'+batch)

def render_total_rail(p):
    # 外层整页容器足够长：打开专项审计时也常驻，不能只附着在商品组件内部。
    metrics=[('整店盘盈（元）',p['gain'],'green'),('整店盘亏（元）',p['loss'],'red'),('净差异（元）',p['net'],''),
        ('净差异率',str(p['rate'])+'‰' if p['rate'] is not None else '待计算',''),('2‰允许损耗（元）',p['allowance'],''),
        ('超标金额（元）' if p['over_limit'] else '剩余额度（元）',f"{abs(D(str(p['remaining']))):,.2f}" if p['remaining'] is not None else None,'red' if p['over_limit'] else 'green'),
        ('已填 / 剩余',str(p['done'])+' / '+str(p['remaining_rows']),'')]
    style='''<style>.stElementContainer:has(#stocktake-global-summary){position:sticky;top:60px;z-index:20}
    #stocktake-global-summary{height:44px;display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:7px;padding:4px 9px;background:#f3faf9;border:1px solid #c9dfdb;border-radius:4px;box-shadow:0 2px 4px #1734470d;font-family:"Microsoft YaHei",system-ui,sans-serif;color:#173447;box-sizing:border-box}
    #stocktake-global-summary .metric{padding-right:8px;border-right:1px solid #dce6e6;min-width:0;line-height:19px}#stocktake-global-summary .metric:last-child{border:0}
    #stocktake-global-summary small{display:block;font-size:10px;line-height:12px;white-space:nowrap;color:#5e7783}#stocktake-global-summary strong{font-size:16px;line-height:19px;white-space:nowrap;font-variant-numeric:tabular-nums}#stocktake-global-summary .red{color:#bb3434}#stocktake-global-summary .green{color:#007864}</style>'''
    st.html(style+'<div id="stocktake-global-summary" aria-label="整店统计，包含全批次商品">'+''.join('<div class="metric"><small>'+html.escape(label)+'</small><strong class="'+color+'">'+html.escape(str(value) if value is not None else '待计算')+'</strong></div>' for label,value,color in metrics)+'</div>')

def fast_blockers(items,state,engine):
    # 与正式导出同一门槛；大批次只展开尚未有凭证的商品集合。
    return export_blockers(items,state['meta'],state['vendors'],engine=engine)

def import_panel(db,batch):
    generation=st.session_state.get('import_generation',0)
    files=st.file_uploader('上传盘点报表',type=['xls','xlsx'],accept_multiple_files=True,key=f'reports_complete_{generation}',help='一次选择公司原始盘盈和盘亏两份Excel，自动识别；顺序不限。')
    if not files:return
    if len(files)==1:st.info('已选择1份，请同时选择另一份盘盈/盘亏报表。');return
    try:
        with st.spinner('识别两类原件、校验并恢复已有数据…'):
            blobs=resolve_reports([(f.name,f.getvalue()) for f in files])
            gn,ln=blobs['盘盈'],blobs['盘亏']
            items,notes,fp=parse(gn[0],gn[1],ln[0],ln[1]);meta=identify_batch(blobs)
            ident=db.create(items,notes,fp,meta.get('store',''),meta.get('period',''),blobs)
        st.session_state['next_batch']=ident;st.session_state['import_generation']=generation+1
        st.session_state['next_page']=PAGES[0];st.rerun()
    except (ValueError,OSError) as exc:st.error('导入失败：'+str(exc))

def advanced_master_import(db):
    with st.expander('高级V13母版导入'):
        master=st.file_uploader('完整V13工作簿',type=['xlsx'],key='master_complete')
        if st.button('打开V13独立批次',disabled=master is None):
            try:
                items,notes,fp,vendors=import_master(master.getvalue(),master.name)
                ident=db.create(items,notes,fp,'','',{'V13母版':(master.name,master.getvalue())})
                loaded,_,state,rev=db.load(ident)
                if vendors and rev==0:
                    state['vendors']=vendors;db.save(ident,loaded,state,rev,actor(),'母版供货商目录继承')
                st.session_state['next_batch']=ident;st.session_state['next_page']=PAGES[0];st.rerun()
            except ValueError as exc:st.error(str(exc))


def save_state(db,batch,items,state,rev,source):
    try:db.save(batch,items,state,rev,actor(),source)
    except ValueError as exc:st.error(str(exc));return
    st.rerun()

def changes_exports(db,batch,items,state,rev):
    st.subheader('变化清单与V13七表工作簿')
    engine=engine_for(items,state)
    rows=change_rows(items,state['vendors'])
    for row,x in zip(rows,items):
        initial=x['初盘数']-x['系统数']+x['原始调整'] if x['初盘数'] is not None and x['系统数'] is not None else None
        latest=newest_diff(x)
        row.update({'盘亏扩大量':None if initial is None or latest is None else float(max(D(0),max(D(0),-latest)-max(D(0),-initial))),
            '跨正负变化':bool(initial is not None and latest is not None and initial*latest<0),
            '核查标签':'；'.join(p['kind']+' ↔ '+p['name']+' / '+p['barcode'] for p in engine.peers(x['记录ID'])),
            '原始行号':x['原始行号'],'原文件':x['原文件']})
    df=table(rows,alt='自动变化与当前实物数量')
    st.warning('以下均为核对草稿。公司最终三列文件请在01顶部下载盘点结果中生成，禁止把草稿作为库存调整提交。')
    st.download_button('下载变化草稿 CSV（非系统上传）',('草稿·未批准·禁止库存调整提交\n'+df.to_csv(index=False)).encode('utf-8-sig'),'草稿_变化核对_禁止上传.csv','text/csv')
    candidate_scope=st.selectbox('工作簿异常候选范围',['all','summary'],format_func=lambda k:'完整成对候选' if k=='all' else '每商品前3条摘要（全量在软件分页查看）')
    if st.button('生成完整V13工作簿草稿（7表）'):
        try:
            with st.spinner('生成实时7表与候选明细…'):blob=export_workbook(items,state,engine,True,candidate_scope)
        except ValueError as exc:st.error(str(exc))
        else:st.download_button('下载带警示的完整V13草稿',blob,'草稿_未批准_V13完整工作簿.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    with st.expander('同步在WPS修改过的V13实数到当前批次'):
        ext=st.file_uploader('已填实数的V13',type=['xlsx','xls'],key='sync_master')
        if st.button('检查并同步有效实数',disabled=ext is None):
            try:updated,count=import_v13(ext.getvalue(),ext.name,items)
            except ValueError as exc:st.error(str(exc))
            else:
                if count:save_state(db,batch,updated,state,rev,'外部V13实数同步')
                else:st.info('没有已填写实数，未修改。')
    legacy.sources(db,batch,items,[],state)

def supplier_page(db,batch,items,state,rev):
    st.subheader('供货商数据库 · 批量导入 / 冲突选择')
    st.caption('完整条码匹配；供应商相同不等于具有换货资格。A换B仅限经确认的卓不凡范围或已启用的同组人工档案，不抵销数量。')
    file=st.file_uploader('批量导入任意供应商Excel',type=['xls','xlsx'],key='vendors_upload')
    mapping={}
    if file:
        with st.expander('列名不标准时，选择列映射'):
            heads=[]
            for _,rows in load_excel(file.getvalue(),file.name):
                for row in rows[:20]:
                    if sum(v not in (None,'') for v in row)>=2:heads=list(dict.fromkeys(str(v).strip() for v in row if v not in (None,'')));break
                if heads:break
            for key in ('商品条码','供货商名称','供货商编码'):
                chosen=st.selectbox(key+'对应列',['自动识别']+heads,key='mapping_'+key)
                if chosen!='自动识别':mapping[key]=chosen
        def import_suppliers():
            live=Store(db.root)
            try:
                fresh,_,latest,version=live.load(batch)
                if version!=rev:raise ValueError('另一窗口已更新，请刷新后重新导入供应商目录。')
                upload=st.session_state['vendors_upload'];blob=upload.getvalue();new=supplier_import(blob,upload.name,mapping)
                digest=hashlib.sha256(blob).hexdigest()
                if digest not in latest['meta'].get('supplier_import_hashes',[]):
                    latest['vendors']+=new;latest['meta'].setdefault('supplier_import_hashes',[]).append(digest)
                    live.save(batch,fresh,latest,version,actor(),'供应商Excel导入')
                    live.add_evidence(batch,'供应商目录','',upload.name,blob,new)
                st.session_state['supplier_result_'+batch]=(True,'供应商目录已校验并保存')
            except ValueError as exc:st.session_state['supplier_result_'+batch]=(False,str(exc))
            finally:live.close()
        st.button('校验并追加供应商目录',on_click=import_suppliers)
    outcome=st.session_state.get('supplier_result_'+batch)
    if outcome:(st.success if outcome[0] else st.error)(outcome[1])
    with st.expander('卓不凡供应商编码确认（仅本机）'):
        catalog=effective_vendors(state);directory=SupplierDirectory(catalog,state['meta'])
        available=sorted({str(v.get('供货商编码') or '') for v in catalog if str(v.get('供货商名称') or '').strip() in ('卓不凡','桌不凡') and v.get('供货商编码')})
        st.caption('只有已核实属于同一供应商的编码才确认；冲突条码仍需在下方逐条选择供应商。')
        chosen=st.multiselect('确认属于卓不凡的有效目录编码',available,default=[c for c in state['meta'].get('zbf_confirmed_codes',[]) if c in available])
        if st.button('保存已核实的卓不凡编码'):
            state['meta']['zbf_confirmed_codes']=chosen;save_state(db,batch,items,state,rev,'卓不凡供应商编码人工确认')
        conflicts_by_code={bc:rows for bc,rows in directory.groups.items() if len({c for c,n in rows})>1}
        if conflicts_by_code:
            bc=st.selectbox('按完整条码确认冲突供应商',sorted(conflicts_by_code))
            codes=['']+sorted({c for c,n in conflicts_by_code[bc] if c})
            selected_code=state['meta'].get('supplier_codes',{}).get(bc,'')
            code=st.selectbox('已核实的有效目录编码',codes,index=codes.index(selected_code) if selected_code in codes else 0,
                format_func=lambda c:'供货商待确认' if not c else c+' · '+('卓不凡' if c in directory.zbf_codes else ' / '.join(sorted({n for v,n in conflicts_by_code[bc] if v==c}))))
            if st.button('保存该条码供应商归属'):
                if code:state['meta'].setdefault('supplier_codes',{})[bc]=code
                else:state['meta'].setdefault('supplier_codes',{}).pop(bc,None)
                save_state(db,batch,items,state,rev,'冲突条码供应商编码人工确认')
    display_name=lambda n:'卓不凡' if n in ('卓不凡','桌不凡') else str(n or '')
    vendors=state['vendors'];names=sorted({display_name(v.get('供货商名称')) for v in vendors})
    selected=st.multiselect('仅分析指定供应商（不删除其他记录）',names)
    shown=[v for v in vendors if not selected or display_name(v.get('供货商名称')) in selected]
    table([{**v,'供货商名称':display_name(v.get('供货商名称')),'归属判定':directory.classify(v)['name']} for v in shown],alt='本地供应商目录，名称显示统一，归属另行核实，原始资料仍留档')
    groups={}
    for v in vendors:groups.setdefault(str(v.get('商品条码') or ''),[]).append(v)
    conflicts={bc:vs for bc,vs in groups.items() if bc and len(vs)>1}
    if conflicts:
        st.subheader(f'多供应商 / 重复条码冲突：{len(conflicts)}个')
        bc=st.selectbox('选择冲突条码',list(conflicts))
        table(conflicts[bc],alt='该条码的全部供应商记录')
        choices=['保留未知']+list(dict.fromkeys(str(v['供货商名称']) for v in conflicts[bc] if v.get('供货商名称')))
        current=state['meta']['main_suppliers'].get(bc,'保留未知')
        choice=st.selectbox('明确选择主供应商（可选）',choices,index=choices.index(current) if current in choices else 0)
        if st.button('保存此条码主供应商选择'):
            if choice=='保留未知':state['meta']['main_suppliers'].pop(bc,None)
            else:state['meta']['main_suppliers'][bc]=choice
            save_state(db,batch,items,state,rev,'供应商冲突人工选主')
    with st.expander('直接维护 / 追加17列目录'):
        df=pd.DataFrame(vendors,columns=VENDOR_HEADERS)
        for c in df:
            if c not in ('成本价','零售价'):df[c]=df[c].astype('string')
        with st.form('catalog_edit'):
            edit=st.data_editor(df,hide_index=True,num_rows='dynamic',placeholder='',alt='供应商目录维护')
            ok=st.form_submit_button('保存目录修改')
        if ok:
            new=[]
            for _,r in edit.iterrows():
                v={k:None if pd.isna(r[k]) else r[k] for k in df}
                if not any(v.values()):continue
                if not v.get('商品条码') or not v.get('供货商名称'):st.error('每条须有完整条码和供应商名称');st.stop()
                new.append(v)
            state['vendors']=new;save_state(db,batch,items,state,rev,'供应商目录维护')

def advanced(db,batch,items,state,rev):
    st.subheader('高级异常明细 · 配对证据 / 跨店 / 交易 / 商品档案')
    mode=st.segmented_control('明细类型',['成对候选','跨店与交易证据','商品档案','参数与批次设置','复盘变化轨迹'],default='成对候选',key='advanced_mode')
    engine=engine_for(items,state)
    if mode=='成对候选':
        selection=st.selectbox('查看商品及其所有候选',[x['记录ID'] for x in items],format_func=lambda k:f"{engine.items[k]['序号']} · {engine.items[k]['商品名称']} / {engine.items[k]['商品条码']}")
        total=engine.count(selection,'all')
        page=st.number_input('候选分页（每页100条，完整可查）',min_value=1,max_value=max(1,(total+99)//100),value=1,step=1)
        peers=engine.peers(selection,limit=100,offset=(page-1)*100)
        st.caption(f'当前商品候选共{total}条；这里显示第{page}页。')
        table([{k:v for k,v in p.items() if k not in ('sort','a','b','id')} for p in peers],alt='成对候选明细，均为疑似待核')
        if peers:
            peer=st.selectbox('为对应商品对附核实证据（可选）',[p['id'] for p in peers],format_func=lambda k:engine.items[k]['商品名称']+' / '+engine.items[k]['商品条码'])
            pairkey='|'.join(sorted((str(engine.items[selection]['序号']),str(engine.items[peer]['序号']))))
            old=state['meta']['pair_proofs'].get(pairkey,{})
            with st.form('proof'):
                note=st.text_area('核实说明（后台附加记录，不是人工核查状态）',value=old.get('说明',''))
                document=st.text_input('相关凭证 / 单号',value=old.get('单号',''))
                if st.form_submit_button('保存这对商品的凭证记录'):
                    state['meta']['pair_proofs'][pairkey]={'说明':note.strip(),'单号':document.strip(),'时间':now(),'操作人':actor()}
                    save_state(db,batch,items,state,rev,'成对核实凭证')
    elif mode=='跨店与交易证据':
        evidence_ui(db,batch,items,state)
    elif mode=='商品档案':
        st.caption('原件保持不变。这里可补充已核实的分类、成本、零售价和包装系数；保存后实时重算线索。')
        cols=['记录ID','序号','商品编码','商家编码','商品条码','商品名称','部类','大类','中类','小类','成本价','零售价','品牌','包装系数','原始调整','单位说明']
        rows=[{k:num(x.get(k)) if k in ('成本价','零售价','包装系数','原始调整') else x.get(k,'') for k in cols} for x in items]
        df=pd.DataFrame(rows)
        for c in ('成本价','零售价','包装系数'):df[c]=pd.array(df[c],dtype='Float64')
        fields=('部类','大类','中类','小类','成本价','零售价','品牌','包装系数','单位说明')
        with st.form('item_master'):
            edit=st.data_editor(df,hide_index=True,disabled=[c for c in df if c not in fields],
                column_config={'记录ID':None},placeholder='',alt='可核实维护的商品档案')
            ok=st.form_submit_button('保存核实后的商品资料')
        if ok:
            patches={}
            for x,(_,r) in zip(items,edit.iterrows()):
                patch={k:None if pd.isna(r[k]) else r[k] for k in fields}
                if any(str(patch[k] or '')!=str(x.get(k) or '') for k in fields):patches[x['记录ID']]=patch
            try:updated=patch_items(items,patches)
            except ValueError as exc:st.error(str(exc))
            else:save_state(db,batch,updated,state,rev,'商品档案核实维护')
        table([{'序号':x['序号'],'商品条码':x['商品条码'],'初盘差异':num(x['初盘数']-x['系统数']+x['原始调整']) if x['初盘数'] is not None and x['系统数'] is not None else None,
            '最新差异':num(newest_diff(x)),'差异成本':num(current_amount(x)),'串码候选数':len(engine.neighbors(x['记录ID'])),
            'A换B候选数':len(engine.neighbors(x['记录ID'],'swap'))} for x in items],alt='商品档案计算与候选数量')
        errors=validate_all(items)
        if errors:table([{'错误':e} for e in errors],alt='档案输入错误')
    elif mode=='参数与批次设置':
        st.caption('店名和期间仅作可选标识，不是导入条件；首次导入时间及原件不可覆盖。')
        params={**DEFAULT_PARAMETERS,**state['meta'].get('parameters',{})}
        with st.form('settings'):
            store=st.text_input('门店标识（可选）',value=state['meta']['store'])
            period=st.text_input('期间标识（可选，不自动推定季度）',value=state['meta']['period'])
            tolerance=st.checkbox('显式启用成本±0.01元容差（默认关闭，按分严格相等）',value=bool(params['cost_tolerance']))
            multiple=st.number_input('异常数量倍数提示',min_value=2,value=int(params['quantity_multiple']))
            large=st.number_input('异常数量下限提示',min_value=1,value=int(params['quantity_large']))
            high=st.number_input('高金额差异筛选阈值（元）',min_value=0.01,value=float(params['high_amount']))
            if st.form_submit_button('保存可选设置'):
                state['meta'].update(store=store.strip() or '门店未识别',period=period.strip() or '期间未识别',
                    parameters={**params,'cost_tolerance':tolerance,'quantity_multiple':multiple,'quantity_large':large,'high_amount':high})
                save_state(db,batch,items,state,rev,'可选参数设置')
        table([{'参数':'允许净损耗标准','值':'2‰（沿用业务标准）'},
               {'参数':'成本规则','值':'按分相同；仅显式开关允许±0.01元'},
               {'参数':'售价','值':'用于证据和排序，不作疑似匹配硬门槛'},
               {'参数':'优先级','值':'中类、售价、反向数量解释程度、金额；仅建议'},
               {'参数':'首次导入北京时间','值':state['meta']['first_import_at']},
               {'参数':'版本','值':VERSION},{'参数':'原件','值':'；'.join(state['meta'].get('source_files',[]))}],alt='参数来源说明')
    elif mode=='复盘变化轨迹':
        logs=db.item_history(batch)
        table([{'时间':e['北京时间'],'商品条码':e['商品条码'],'旧值':json.dumps(e['旧值'],ensure_ascii=False),
                '新值':json.dumps(e['新值'],ensure_ascii=False),'操作人':e['操作人'],'修改来源':e['修改来源'],'已撤销':e['已撤销']} for e in logs],alt='逐商品变化轨迹')
        if st.button('撤销上一次输入（保留日志）'):
            try:db.undo_last(batch,rev,actor());st.rerun()
            except ValueError as exc:st.error(str(exc))
        st.caption('升级前日志完整保留，可在更多工具的来源与备份中下载。')

def evidence_ui(db,batch,items,state):
    st.caption('可选证据不改变本店实数、系统库存或原始调整。未上传时正常使用01；未提供日期的行只提示核实同期。')
    kind=st.selectbox('证据类型',['跨店差异','跨店库存','销售明细204','调拨/入库/报损单','最新库存'])
    label=st.selectbox('对方门店（仅跨店比对）',['模拟门店甲','模拟门店乙','其他/未识别']) if kind.startswith('跨店') else ''
    file=st.file_uploader('上传可选比对证据',type=['xls','xlsx'],key='evidence_file')
    if st.button('校验证据并留档',disabled=file is None):
        try:
            required=('商品条码','差异数量') if kind=='跨店差异' else ('商品条码','系统数') if kind=='跨店库存' else ('商品条码',)
            rows=generic_rows(file.getvalue(),file.name,required)
            db.add_evidence(batch,kind,label,file.name,file.getvalue(),rows);st.rerun()
        except ValueError as exc:st.error(str(exc))
    evidence=db.evidence(batch)
    if kind=='跨店库存':st.info('仅有对方系统库存时不能推断对方盘盈盘亏。可按条码查看库存证据；上传对方差异表后才生成反向差异线索。')
    table([{k:v for k,v in e.items() if k!='rows'}|{'记录数':len(e['rows'])} for e in evidence],alt='已上传证据，带哈希')
    cross=cross_candidates(items,evidence)
    table([r for values in cross.values() for r in values],alt='跨店同条码反向差异，待核调拨记录')
    bc=st.text_input('按完整条码查看销售 / 收退货 / 库存证据')
    a,b=st.columns(2);start=a.text_input('比对起始日期（可选 YYYY-MM-DD）');end=b.text_input('比对结束日期（可选 YYYY-MM-DD）')
    if bc:table(transactions_for(bc,evidence,start,end),alt='条码和期间筛选的交易证据')


def tools_page(db,batch,items,state,rev):
    mode=st.selectbox('更多工具',['供货商数据库','商品档案与异常分析','变化清单/七表母版','来源与本地备份','历史人工换货档案（只读）'],key='tools_mode')
    if mode=='供货商数据库':supplier_page(db,batch,items,state,rev)
    elif mode=='商品档案与异常分析':advanced(db,batch,items,state,rev)
    elif mode=='变化清单/七表母版':changes_exports(db,batch,items,state,rev)
    elif mode=='历史人工换货档案（只读）':
        from exchange_registry import registry_panel
        registry_panel(db,batch,items,state)
    else:legacy.sources(db,batch,items,[],state)

def print_page(db,batch,items,state,rev):
    legacy.printing(db,batch,items,state,rev)
    archives=db.prints(batch)
    if archives:
        st.subheader('按历史商品范围，使用最新数据重新生成')
        old=st.selectbox('选择要重新生成的历史范围',[p['id'] for p in archives],key='new_from_history')
        snap=next(p for p in archives if p['id']==old)
        ids={r['source_id'] for r in snap['rows']};chosen=[x for x in items if x['记录ID'] in ids]
        if st.button('按当前最新数据创建新打印批次',disabled=not chosen):
            from print_manager import generate_print
            generate_print(db,batch,chosen,state['meta'],'all','category',snap.get('categories',[]),rev);st.rerun()

def main():
    st.set_page_config(page_title='高速服务区智能盘点 · V13完整客户端',layout='wide',initial_sidebar_state='collapsed')
    if st.session_state.get('navigation',PAGES[0])==PAGES[0]:
        st.html('''<style>[data-testid="stMainBlockContainer"]{padding:3.8rem 1.5rem 1rem;max-width:none}
        [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"]{gap:.55rem}
        [data-testid="stMainBlockContainer"] h3{font-size:1.25rem;padding:.1rem 0 .35rem}
        [data-testid="stMainBlockContainer"] [data-testid="stExpander"] summary{padding:.35rem .65rem;min-height:32px}
        </style>''')
    db=Store(dbroot())
    try:
        batches=db.list_batches();byid={b['id']:b for b in batches}
        if 'selected_batch' not in st.session_state:
            last=db.preference('last_batch')
            st.session_state['selected_batch']=last if last in byid else max(batches,key=lambda b:(b['revision'],b['created']))['id'] if batches else 'new'
        if 'next_batch' in st.session_state:st.session_state['selected_batch']=st.session_state.pop('next_batch')
        if 'next_page' in st.session_state:st.session_state['navigation']=st.session_state.pop('next_page')
        current=st.session_state['selected_batch'];batch=None if current=='new' else current
        with st.container(horizontal=True,vertical_alignment='center'):
            st.subheader('高速服务区智能盘点')
            with st.popover('上传盘点报表'):import_panel(db,batch)
        with st.expander('历史批次与高级设置'):
            a,b=st.columns([5,2])
            selected=a.selectbox('本机批次',['new']+list(byid),key='selected_batch',format_func=lambda k:'导入新批次' if k=='new' else
                f"{byid[k]['store']} · {byid[k]['created'][:16]} · {byid[k]['id'][-6:]}")
            b.text_input('操作人（可选）',key='operator',placeholder='本机店长')
            batch=None if selected=='new' else selected
            if batch:db.set_preference('last_batch',batch)
            advanced_master_import(db)
        if batch is None:
            st.info('点击“上传盘点报表”，一次选择盘盈、盘亏两份原始Excel。无需填写店名、日期或操作人。');return
        items,notes,state,rev=db.load(batch)
        meta=state['meta']
        if st.session_state.get('navigation') not in PAGES:st.session_state['navigation']=PAGES[0]
        page=st.segmented_control('业务入口',PAGES,key='navigation',width='stretch',label_visibility='collapsed') or PAGES[0]
        if page==PAGES[0]:render_workbench(db,batch,items,state,rev)
        elif page==PAGES[1]:
            from field_printing import print_workbench
            print_workbench(db,batch,items,state,rev)
        else:tools_page(db,batch,items,state,rev)
    finally:db.close()
