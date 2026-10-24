"""一次完整升级的本机客户端：01直达、可见候选、证据和原有完整功能。"""
from pathlib import Path
import copy,os,io,csv,json,hashlib
from decimal import Decimal as D
import pandas as pd
import streamlit as st
from core import (VERSION,import_pair,patch_items,decimal_value,num,summary,current_total,
    newest_diff,current_amount,changes,change_rows,validate_all,export_blockers,import_v13,
    VENDOR_HEADERS,json_bytes,load_excel)
from storage import Store,now
from intelligence import CandidateEngine,row_models,FILTERS,DEFAULT_PARAMETERS
from imports_exports import (identify_batch,supplier_import,generic_rows,cross_candidates,
    transactions_for,import_master,export_workbook)
from workbench_component import workbench
from reporting import financial_panel, report_document, validated_meta_value, report_defaults
import legacy_views as legacy

ROOT=Path(__file__).resolve().parent
PAGES=['01复盘与智能找差异','02变化/导出','供货商数据库','打印历史','高级异常明细']

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
        if kind in ('edit','bulk','undo','meta'):
            if event.get('revision')!=rev:raise ValueError('另一窗口已更新。输入草稿仍保留，请刷新并核对后重试')
        if kind=='edit':
            x=mapping.get(event.get('id'));field=event.get('field')
            if x is None or field not in ('复盘实数','备注'):raise ValueError('不是可编辑的01字段')
            current=x.get(field);base=event.get('base')
            if field=='复盘实数':
                if decimal_value(current)!=decimal_value(base):raise ValueError('该实数已被其他修改更新，草稿未覆盖现值')
                value=None if str(event.get('value','')).strip()=='' else event.get('value')
            else:
                if str(current or '')!=str(base or ''):raise ValueError('该原因已更新，草稿未覆盖现值')
                value=event.get('value','')
            updated=patch_items(items,{x['记录ID']:{field:value}})
            db.save(batch,updated,state,rev,actor(),'01单元格编辑',request)
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
        elif kind=='view':st.session_state['enrich_'+batch]=[k for k in event.get('ids',[])[:101] if k in mapping]
        elif kind=='detail':
            a,b=event.get('a'),event.get('b')
            if a not in mapping or b is not None and b not in mapping:raise ValueError('商品不存在')
            st.session_state['detail_'+batch]=(a,b);st.session_state['peer_limit_'+batch]=3
        elif kind=='more_peers':st.session_state['peer_limit_'+batch]=st.session_state.get('peer_limit_'+batch,50)+50
        elif kind!='refresh':raise ValueError('未识别操作')
        st.session_state[ackkey]={'id':request,'ok':True}
        if kind not in ('view','detail','more_peers'):st.session_state.pop('grid_error_'+batch,None)
    except (ValueError,KeyError) as exc:
        st.session_state[ackkey]={'id':request,'ok':False}
        st.session_state['grid_error_'+batch]=str(exc)
    finally:db.close()

def render_workbench(db,batch,items,state,rev):
    engine=CandidateEngine(items,state['vendors'],state['meta'].get('parameters'),state['meta'].get('main_suppliers'))
    cross=cross_candidates(items,db.evidence(batch))
    enrich=set(st.session_state.get('enrich_'+batch,[]))
    if not enrich:
        enrich={x['记录ID'] for x in sorted(items,key=lambda x:-abs(current_amount(x) or 0))[:20]}
    selected=st.session_state.get('detail_'+batch)
    if selected:enrich.update(k for k in selected if k)
    rows=row_models(items,state,engine,cross,enrich);mapping={r['id']:r for r in rows}
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
    payload={'batch':batch,'revision':rev,'rows':rows,'filters':FILTERS,'enriched':list(enrich),
        'saved_at':last[0] if last else '', 'imported_at':state['meta']['first_import_at'],
        'ack':st.session_state.get('ack_'+batch),'error':st.session_state.get('grid_error_'+batch),
        'detail':detail,'finance':{'sales_amount':state['meta'].get('sales_amount'),'sales_cost':state['meta'].get('sales_cost')},
        'panel':financial_panel(items,state['meta']),'report':report_document(items,state['meta']),
        'audit':('正式导出请在02完整检查' if not blockers else f'正式导出尚有{len(blockers)}项待办，详见02'),
        'stats':{'difference_count':sum(newest_diff(x) not in (None,0) for x in items),
           'done':stats['已复盘'],'pending':sum(x.get('复盘实数') is None and newest_diff(x) not in (None,0) for x in items),
           'loss':num(stats['盘亏']),'gain':num(stats['盘盈']),'net':num(stats['净差异']),
           'rate':num(stats['报损率']),'zero_count':sum(x.get('复盘实数') is not None and newest_diff(x)==0 for x in items)}}
    workbench(payload,lambda:component_action(batch),'workbench_'+batch)

def fast_blockers(items,state,engine):
    # 与正式导出同一门槛；大批次只展开尚未有凭证的商品集合。
    return export_blockers(items,state['meta'],state['vendors'],engine=engine)

def import_panel(db,batch):
    with st.expander('导入新的初盘 / 恢复已有批次',expanded=batch is None):
        st.caption('上传两表后直接进入01。系统记录首次导入北京时间和原件摘要；门店无法可靠识别时显示“门店未识别”，不影响使用。')
        a,b=st.columns(2)
        generation=st.session_state.get('import_generation',0)
        gn=a.file_uploader('公司初盘盘盈',type=['xls','xlsx'],key=f'gain_complete_{generation}')
        ln=b.file_uploader('公司初盘盘亏',type=['xls','xlsx'],key=f'loss_complete_{generation}')
        if gn is not None and ln is not None:
            blobs={'盘盈':(gn.name,gn.getvalue()),'盘亏':(ln.name,ln.getvalue())}
            signature=hashlib.sha256(gn.getvalue()+ln.getvalue()).hexdigest()
            try:
                with st.spinner('合并原件、校验条码和金额…'):
                    items,notes,fp=parse(gn.name,gn.getvalue(),ln.name,ln.getvalue())
                    meta=identify_batch(blobs)
                    created=db.create(items,notes,fp,meta.get('store',''),meta.get('period',''),blobs)
                st.session_state['next_batch']=created
                st.session_state['import_generation']=generation+1
                st.session_state['next_page']=PAGES[0];st.rerun()
            except (ValueError,OSError) as exc:st.error('导入失败：'+str(exc))
        with st.expander('可选：直接打开完整V13工作簿为独立批次'):
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
    st.subheader('02 · 变化清单 / 系统三列 / V13工作簿')
    engine=CandidateEngine(items,state['vendors'],state['meta'].get('parameters'),state['meta'].get('main_suppliers'))
    rows=change_rows(items,state['vendors'])
    for row,x in zip(rows,items):
        initial=x['初盘数']-x['系统数']+x['原始调整'] if x['初盘数'] is not None and x['系统数'] is not None else None
        latest=newest_diff(x)
        row.update({'盘亏扩大量':None if initial is None or latest is None else float(max(D(0),max(D(0),-latest)-max(D(0),-initial))),
            '跨正负变化':bool(initial is not None and latest is not None and initial*latest<0),
            '核查标签':'；'.join(p['kind']+' ↔ '+p['name']+' / '+p['barcode'] for p in engine.peers(x['记录ID'])),
            '原始行号':x['原始行号'],'原文件':x['原文件']})
    df=table(rows,alt='自动变化与当前实物数量')
    with st.expander('正式导出检查 · 公司三列文件'):
        legacy.review(db,batch,items,state,rev,actor())
    st.warning('以下核对资料为草稿，未批准，禁止作为公司库存调整提交。公司上传文件须使用上方正式导出检查后的三列XLS。')
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
    st.caption('完整条码匹配；导入的供应商均可单独筛选。供应商相同只形成A换B线索，不抵销数量。')
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
        if st.button('校验并追加供应商目录'):
            try:new=supplier_import(file.getvalue(),file.name,mapping)
            except ValueError as exc:st.error(str(exc))
            else:
                digest=hashlib.sha256(file.getvalue()).hexdigest()
                if digest in state['meta'].get('supplier_import_hashes',[]):st.info('同一供应商原件已导入，保留现有目录，不重复追加。')
                else:
                    state['vendors']+=new
                    state['meta'].setdefault('supplier_import_hashes',[]).append(digest)
                    try:
                        db.save(batch,items,state,rev,actor(),'供应商Excel导入')
                        db.add_evidence(batch,'供应商目录','',file.name,file.getvalue(),new)
                    except ValueError as exc:st.error(str(exc))
                    else:st.rerun()
    vendors=state['vendors'];names=sorted({str(v.get('供货商名称') or '') for v in vendors})
    selected=st.multiselect('仅分析指定供应商（不删除其他记录）',names)
    shown=[v for v in vendors if not selected or v.get('供货商名称') in selected]
    table(shown,alt='完整供应商目录')
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
    engine=CandidateEngine(items,state['vendors'],state['meta'].get('parameters'),state['meta'].get('main_suppliers'))
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
        st.caption('升级前日志完整保留，可在02的来源与备份中下载。')

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
    st.subheader('高速服务区智能盘点')
    db=Store(dbroot())
    try:
        batches=db.list_batches();byid={b['id']:b for b in batches}
        if 'selected_batch' not in st.session_state:
            last=db.preference('last_batch')
            st.session_state['selected_batch']=last if last in byid else max(batches,key=lambda b:(b['revision'],b['created']))['id'] if batches else 'new'
        if 'next_batch' in st.session_state:st.session_state['selected_batch']=st.session_state.pop('next_batch')
        if 'next_page' in st.session_state:st.session_state['navigation']=st.session_state.pop('next_page')
        current=st.session_state['selected_batch']
        label='当前批次 / 切换、导入与设置' if current=='new' else byid[current]['store']+' · 切换批次、导入与设置'
        with st.expander(label,expanded=current=='new'):
            a,b,c=st.columns([5,2,1])
            options=['new']+list(byid)
            selected=a.selectbox('本机批次',options,key='selected_batch',format_func=lambda k:'导入新批次' if k=='new' else
                f"{byid[k]['store']} · {byid[k]['created'][:16]} · {byid[k]['id'][-6:]}")
            b.text_input('操作人（可选）',key='operator',placeholder='本机店长')
            c.button('返回01',on_click=lambda:st.session_state.update(navigation=PAGES[0]))
            batch=None if selected=='new' else selected
            if batch:db.set_preference('last_batch',batch)
            import_panel(db,batch)
        if batch is None:
            st.info('只需上传盘盈、盘亏两张报表，自动进入01。无需填写店名、日期或时间。');return
        items,notes,state,rev=db.load(batch)
        meta=state['meta']
        if st.session_state.get('navigation') not in PAGES:st.session_state['navigation']=PAGES[0]
        page=st.segmented_control('业务入口',PAGES,key='navigation',width='stretch',label_visibility='collapsed') or PAGES[0]
        if page==PAGES[0]:render_workbench(db,batch,items,state,rev)
        elif page==PAGES[1]:changes_exports(db,batch,items,state,rev)
        elif page==PAGES[2]:supplier_page(db,batch,items,state,rev)
        elif page==PAGES[3]:print_page(db,batch,items,state,rev)
        else:advanced(db,batch,items,state,rev)
    finally:db.close()
