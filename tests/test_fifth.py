import copy,io,json,sqlite3,subprocess,shutil
from pathlib import Path
from datetime import date
from decimal import Decimal as D
import pytest,openpyxl
from core import current_amount,patch_items,newest_diff,current_total,import_pair
from intelligence import CandidateEngine,engine_for,row_models
from supplier_policy import SupplierDirectory
from exchange_registry import validate_records,parse_registry,HEADERS as CATALOG_HEADERS
from vendor_audit import audit_model,audit_excel,filtered_rows
from reporting import financial_panel
from prepare_fourth_demo import fourth_rows,fourth_vendors
from synthetic_data import workbook

def catalog_record(x,group='SIM-G1',**extra):
    return {'商品条码':x['商品条码'],'商品编码':x['商品编码'],'商品名称':x['商品名称'],'供应商':'模拟其他供货商','换货资格来源':'人工加入','换货组':group,'是否启用':True,'生效日期':'2020-01-01','备注及依据':'模拟店长已核实的换货授权',**extra}

@pytest.fixture
def fifth():
    raw=fourth_rows(480);vs=fourth_vendors(raw)
    items,notes,fp=import_pair(('模拟盘盈.xls',workbook([r for r in raw if r['差异数量']>=0])),('模拟盘亏.xls',workbook([r for r in raw if r['差异数量']<0])))
    return items,vs,notes,fp

def test_strict_both_ends_group_zero_and_mix_independence(fifth):
    items,vs,*_=fifth;others=[x for x in items if int(x['商品条码'][-4:]) in range(90,110)]
    a=next(x for x in others if newest_diff(x)>0);b=next(x for x in others if newest_diff(x)<0)
    # 普通同供应商，即使同成本反向也无A换B；串码仍存在。
    a.update(大类='模拟同类',中类='模拟同细类',成本价=D('2'));b.update(大类='模拟同类',中类='模拟同细类',成本价=D('2'))
    e=CandidateEngine([a,b],vs);assert e.count(a['记录ID'])==1 and e.count(a['记录ID'],'swap')==0
    c=[catalog_record(a),catalog_record(b)];e=CandidateEngine([a,b],vs,exchange=c)
    assert not e.pair(a['记录ID'],b['记录ID'])['swap'] and e.pair(a['记录ID'],b['记录ID'])['mix']
    for replacement in [catalog_record(b,'SIM-G2'),catalog_record(b,是否启用=False),catalog_record(b,生效日期='2099-01-01'),catalog_record(b,商品编码='wrong')]:
        e=CandidateEngine([a,b],vs,exchange=[c[0],replacement]);assert not e.neighbors(a['记录ID'],'swap') and e.neighbors(a['记录ID'])
    original=copy.deepcopy([a,b]);a['复盘实数']=a['系统数']-a['原始调整']
    assert not CandidateEngine([a,b],vs,exchange=c).neighbors(b['记录ID'],'swap')
    assert CandidateEngine(original,vs,exchange=c).count(b['记录ID'],'swap')==0

def test_confirmed_zbf_only_same_supplier_and_no_cross_group(fifth):
    items,vs,*_=fifth;e=CandidateEngine(items,vs)
    zbf=[k for k,v in e.eligibility.items() if v['eligible']]
    assert len(zbf)==60 and all(e.eligibility[p]['group']==e.eligibility[k]['group'] for k in zbf for p in e.neighbors(k,'swap'))
    other=next(x for x in items if int(x['商品条码'][-4:])==90)
    e=CandidateEngine(items,vs,exchange=[catalog_record(other)])
    assert not e.neighbors(other['记录ID'],'swap')
    # 独立已确认卓不凡供应商编码不得跨有效范围。
    test=copy.deepcopy(items[:2]);test[0]['复盘实数']=test[0]['系统数']+1;test[1]['复盘实数']=0
    vv=[{'商品条码':x['商品条码'],'供货商编码':f'SIM-Z{i}','供货商名称':'卓不凡'} for i,x in enumerate(test)]
    assert not CandidateEngine(test,vv).neighbors(test[0]['记录ID'],'swap')

def test_batch_supplier_effective_date_stable():
    v=[{'商品条码':'0990000000001','供货商编码':'SIM-Z','供货商名称':'卓不凡','生效日期':'2020-01-01','失效日期':'2025-12-31'}]
    assert SupplierDirectory(v,{'first_import_at':'2025-10-01T12:00:00+08:00'}).classify(v[0])['status']=='zbf'
    assert SupplierDirectory(v,{'first_import_at':'2026-10-01T12:00:00+08:00'}).classify(v[0])['status']=='pending'

def test_registry_persistence_history_atomic_identity_and_reuse(store,fifth):
    items,vs,notes,fp=fifth;b=store.create(items,notes,fp);record=catalog_record(items[-1])
    store.save_exchange([record],items);saved=store.exchange_list()[0]
    assert saved['_revision']==1 and len(store.exchange_history())==1
    with pytest.raises(ValueError):store.save_exchange([{**saved,'换货组':'changed'},{**catalog_record(items[0]),'商品编码':'wrong'}],items)
    assert store.exchange_list()==[saved]
    store.save_exchange([{**saved,'是否启用':False,'换货组':'SIM-G2'}],items)
    assert len(store.exchange_history(record['商品条码']))==2
    with pytest.raises(ValueError):store.save_exchange([saved],items)
    loaded,_,state,_=store.load(b);assert state['exchange_catalog'][0]['是否启用'] is False
    store.close();store.__init__(store.root)
    another=store.create(items,notes,fp+'another');assert store.load(another)[2]['exchange_catalog']==store.exchange_list()

@pytest.mark.parametrize('field,value',[('商品条码','999'),('商品编码','wrong'),('商品名称','模糊名称'),('供应商',''),('换货组',''),('备注及依据',''),('是否启用','是'),('生效日期','错误'),('换货资格来源','卓不凡规则')])
def test_registry_rejects_unsafe_identity_or_authority(items,field,value):
    r=catalog_record(items[0]);r[field]=value
    with pytest.raises(ValueError):validate_records([r],items)

def test_registry_bulk_excel_and_duplicate(items):
    r=catalog_record(items[0]);w=openpyxl.Workbook();s=w.active;s.append(CATALOG_HEADERS);s.append([r[k] for k in CATALOG_HEADERS]);b=io.BytesIO();w.save(b)
    parsed=parse_registry(b.getvalue(),'模拟资格.xlsx',items,[]);assert parsed[0]['商品条码']==r['商品条码'] and parsed[0]['是否启用'] is True
    with pytest.raises(ValueError):validate_records([r,r],items)

def test_migration_keeps_every_old_table_row(tmp_path,items):
    from storage import Store
    root=tmp_path/'migration';root.mkdir();db=sqlite3.connect(root/'stocktake.sqlite')
    db.executescript('CREATE TABLE preserved(id INTEGER PRIMARY KEY,value BLOB);INSERT INTO preserved VALUES(1,X\'000102\');PRAGMA user_version=14;');db.close()
    s=Store(root);assert s.db.execute('SELECT * FROM preserved').fetchall()==[(1,b'\0\1\2')]
    assert s.db.execute('PRAGMA user_version').fetchone()[0]==16 and s.exchange_list()==[];s.close()

def test_full_legacy_eight_tables_migrate_without_rewrite(store,batch):
    from print_manager import generate_print
    items,_,state,revision=store.load(batch)
    generate_print(store,batch,items,state['meta'],'all','category',[],revision)
    names=['batches','events','evidence_files','item_events','preferences','prints','requests','sources']
    before={t:store.db.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall() for t in names}
    store.db.executescript('DROP TABLE exchange_products;DROP TABLE exchange_history;PRAGMA user_version=14;')
    store.close();store.__init__(store.root)
    assert before=={t:store.db.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall() for t in names}
    assert store.exchange_list()==[]

def test_audit_scope_amounts_top_candidates_and_legacy_proofs(fifth):
    items,vs,*_=fifth;manual=[catalog_record(x,'SIM-G'+str(int(x['商品条码'][-4:])%2)) for x in items if 90<=int(x['商品条码'][-4:])<110]
    meta={'first_import_at':'2026-10-25','sales_cost':'10000000'};before=financial_panel(items,meta)
    m=audit_model(items,vs,meta,manual);assert m['stats']['商品总条数']==60 and m['stats']['卓不凡商品']==60 and m['stats']['其他可换货商品']==0
    assert all(len(ps)<=3 for ps in m['peers'].values())
    assert m['stats']['净差异']==sum((current_amount(x) for x in items if m['engine'].eligibility[x['记录ID']]['eligible']),D(0))
    a,b=next(iter(m['edges']));key='|'.join(sorted(str(m['byid'][k]['序号']) for k in (a,b)))
    meta['pair_proofs']={key:{'说明':'模拟旧双方核查','单号':'SIM-OLD'}};meta['zbf_notes']={a:'模拟旧专项说明'}
    m=audit_model(items,vs,meta,manual);row=next(r for r in m['rows'] if r['_id']==a)
    assert '模拟旧双方核查' in row['核查结论'] and '模拟旧专项说明' in row['核查结论'] and 'SIM-OLD' in row['凭证编号']
    w=openpyxl.load_workbook(io.BytesIO(audit_excel(m,filtered_rows(m))))
    assert w['卓不凡A换B专项核对'].max_row==61 and w['A换B线索'].max_row==len(m['edges'])+1
    assert financial_panel(items,meta)==before

def test_amount_per_row_reuses_core_and_missing_cost(fifth):
    items,vs,*_=fifth;state={'meta':{},'vendors':vs};items[0]['成本价']=None;items[1]['复盘实数']=D(0)
    models=row_models(items,state)
    assert len(models)==480
    for x,r in zip(items,models):assert r['amount']==(None if current_amount(x) is None else float(current_amount(x)))
    assert models[0]['amount'] is None and models[1]['recount']==0

def test_native_audit_only_in_01(store,batch,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('STOCKTAKE_DATA_DIR',str(store.root));app=Path(__file__).resolve().parents[1]/'app.py'
    at=AppTest.from_file(str(app),default_timeout=30).run();at.session_state['exchange_scope_'+batch]='zbf';at.run()
    assert any(x.label=='卓不凡A换B专项核对' for x in at.expander)
    at.session_state['navigation']='03 现场复核单打印';at.run();assert not at.exception
    assert not any('专项审计' in x.label or '可换货' in x.label for x in at.expander)

def test_native_single_and_pair_proof_callbacks_keep_distinct_keys(store,fifth,monkeypatch):
    from streamlit.testing.v1 import AppTest
    items,vs,notes,fp=fifth;b=store.create(items,notes,fp)
    loaded,_,state,rev=store.load(b);state['vendors']=vs;store.save(b,loaded,state,rev)
    monkeypatch.setenv('STOCKTAKE_DATA_DIR',str(store.root));at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
    at.session_state['exchange_scope_'+b]='zbf';at.run()
    # 可展开区域需要真实打开，展开后两个表单同时存在，不能共享后定义的token。
    at.session_state['swap_audit_'+b]=True;at.run()
    next(x for x in at.text_area if x.label=='专项核查说明（人工）').set_value('模拟独立单商品说明')
    next(x for x in at.text_input if x.label=='凭证编号').set_value('SIM-SINGLE')
    next(x for x in at.button if x.label=='保存专项说明与凭证').click().run()
    assert not at.exception
    loaded,_,state,_=store.load(b)
    assert '模拟独立单商品说明' in state['meta']['zbf_notes'].values() and any(x['相关单号']=='SIM-SINGLE' for x in loaded)
    next(x for x in at.text_input if x.label=='双方核查说明').set_value('模拟独立双方说明')
    next(x for x in at.text_input if x.label=='双方凭证编号').set_value('SIM-BOTH')
    next(x for x in at.button if x.label=='保存双方核查凭证').click().run()
    assert not at.exception and any(p['单号']=='SIM-BOTH' for p in store.load(b)[2]['meta']['pair_proofs'].values())

def test_frontend_filter_boundaries():
    node=shutil.which('node')
    if not node:pytest.skip('浏览器CI另行覆盖；本机未提供Node')
    subprocess.run([node,str(Path(__file__).with_name('filtering_cases.mjs'))],check=True,capture_output=True,text=True,encoding='utf8')
