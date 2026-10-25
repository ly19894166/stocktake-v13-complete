import copy,io,json,zipfile,subprocess,shutil
from decimal import Decimal as D
from pathlib import Path
import pytest,xlrd
from core import import_pair,current_total,newest_diff,current_amount,patch_items
from intelligence import CandidateEngine
from reporting import financial_panel
from balance_service import BalanceService,make_plan,supplier_signature
from company_export import snapshot
from prepare_sixth_demo import sixth_rows,sixth_vendors
from synthetic_data import workbook
from test_fifth import catalog_record

@pytest.fixture
def sixth(store):
    raw=sixth_rows();g=('模拟盘盈.xls',workbook([r for r in raw if r['差异数量']>=0]));l=('模拟盘亏.xls',workbook([r for r in raw if r['差异数量']<0]))
    items,notes,fp=import_pair(g,l);b=store.create(items,notes,fp,sources={'盘盈':g,'盘亏':l})
    items,_,state,rev=store.load(b);state['vendors']=sixth_vendors(raw);state['meta']['sales_cost']='10000000';store.save(b,items,state,rev)
    items,_,state,rev=store.load(b);a=next(x for x in items if x['商品条码'].endswith('0000'));z=next(x for x in items if x['商品条码'].endswith('0001'))
    return b,items,state,rev,a,z,BalanceService(store)

def confirm(sixth,run,x,value,note='模拟货架实数已逐条核查',request=None):
    b,_,_,_,_,_,svc=sixth
    return svc.confirm(b,run['id'],run['version'],run['revision'],x['记录ID'],value,note,request)

def test_unique_quantity_conserved_costs_independent_and_no_formal_write(store,sixth):
    b,items,state,rev,a,z,svc=sixth;before=store.db.execute('SELECT * FROM batches').fetchall();panel=financial_panel(items,state['meta'])
    run=svc.generate(b,rev,'unique');p=run['plan'];assert len(items)==500
    assert [D(p['rows'][x['记录ID']]['suggested']) for x in (a,z)]==[D(12),D(20)]
    assert D(p['rows'][a['记录ID']]['q'])==8
    assert sum(D(p['rows'][x['记录ID']]['suggested']) for x in (a,z))==32
    assert store.db.execute('SELECT * FROM batches').fetchall()==before and financial_panel(store.load(b)[0],state['meta'])==panel
    assert a['复盘实数'] is None and z['复盘实数'] is None
    run=confirm(sixth,run,a,'12',request='one');loaded=store.load(b)[0];aa=next(x for x in loaded if x['记录ID']==a['记录ID']);zz=next(x for x in loaded if x['记录ID']==z['记录ID'])
    assert newest_diff(aa)==2 and current_amount(aa)==4 and zz['复盘实数'] is None
    assert run['plan']['relations'][0]['status']=='partial'
    assert svc.confirm(b,'old',0,0,a['记录ID'],'999','',request='one')==run # 幂等不重复写实数
    run=svc.generate(b,run['revision']);assert run['plan']['rows'][a['记录ID']]['stage']=='confirmed'
    run=confirm(sixth,run,z,'20');assert run['plan']['relations'][0]['status']=='verified'
    assert sum(current_amount(x) for x in store.load(b)[0] if x['记录ID'] in (a['记录ID'],z['记录ID']))==4
    assert all(not x.get('备注') for x in store.load(b)[0] if x['记录ID'] in (a['记录ID'],z['记录ID']))
    assert len([h for h in svc.history(b) if h['操作']=='confirm'])==2

@pytest.mark.parametrize('change,reason',[
    ('unit','计量'),('packing','口径'),('missing','计量'),('adjust','调整'),('box','整箱'),('competing','争抢'),('supplier',''),('conflict',''),('precision','精度')])
def test_uncertain_basis_never_forces_proposals(sixth,change,reason):
    b,_,state,rev,a,z,_=sixth;items=copy.deepcopy([a,z]);a,z=items;state=copy.deepcopy(state)
    if change=='unit':z['件装单位']='瓶'
    elif change=='packing':z['包装系数']=D(2)
    elif change=='missing':z['件装单位']=''
    elif change=='adjust':z['原始调整']=D(1)
    elif change=='box':
        for x in items:x['件装单位']='箱'
    elif change=='competing':
        third=copy.deepcopy(z);third.update(记录ID='SIM-THIRD',商品条码='0999999999999',序号=501);items.append(third)
        state['vendors'].append({'商品条码':third['商品条码'],'供货商名称':'卓不凡','供货商编码':'SIM-UNIQUE'})
    elif change=='supplier':state['vendors']=[{**v,'供货商编码':'SIM-DIFFERENT'} if v['商品条码']==z['商品条码'] else v for v in state['vendors']]
    elif change=='conflict':state['vendors'].append({'商品条码':z['商品条码'],'供货商名称':'模拟其他','供货商编码':'SIM-CONFLICT'})
    else:a['初盘数']=D('20.000001')
    p=make_plan(items,state);assert not p['relations'] and all(r['stage']!='pending' for r in p['rows'].values())
    if reason:assert any(reason in r['reason'] for r in p['rows'].values())

def test_special_adjustment_uses_core_and_preserves_initials(sixth):
    _,_,state,_,a,z,_=sixth;a,z=copy.deepcopy([a,z]);a.update(原始调整=D(2),单位说明='模拟原始子转母已核实')
    p=make_plan([a,z],state);proposed=p['rows'][a['记录ID']]['suggested'];assert D(proposed)==12
    a['复盘实数']=D(proposed);assert newest_diff(a)==4 and a['初盘数']==20

def test_partial_confirmation_rebases_then_undo_regenerate(store,sixth):
    b,_,_,rev,a,z,svc=sixth;run=svc.generate(b,rev);run=confirm(sixth,run,a,'14')
    assert D(run['plan']['rows'][z['记录ID']]['suggested'])==18 and D(run['plan']['rows'][z['记录ID']]['q'])==6
    run=svc.generate(b,run['revision']);assert D(run['plan']['rows'][z['记录ID']]['suggested'])==18
    store.undo_last(b,run['revision']);fresh=store.load(b);run=svc.generate(b,fresh[3]);assert D(run['plan']['rows'][a['记录ID']]['suggested'])==12
    assert len([h for h in svc.history(b) if h['操作']=='confirm'])==1

def test_changed_other_side_stales_plan_and_manual_priority(store,sixth):
    b,items,state,rev,a,z,svc=sixth;run=svc.generate(b,rev);store.save(b,patch_items(items,{z['记录ID']:{'复盘实数':15}}),state,rev)
    with pytest.raises(ValueError,match='版本'):confirm(sixth,run,a,12)
    run=svc.generate(b,rev+1);assert run['plan']['rows'][z['记录ID']]['stage']=='manual' and not run['plan']['relations']

def test_draft_reject_concurrency_restart_and_readonly_legacy(store,sixth):
    b,items,state,rev,a,z,svc=sixth;other=next(x for x in items if x['商品条码'].endswith('0090'));store.save_exchange([catalog_record(other)],items)
    before=store.exchange_history();run=svc.generate(b,rev);old=copy.deepcopy(run)
    run=svc.edit(b,run['id'],run['version'],rev,a['记录ID'],'13','模拟独立草稿')
    assert store.load(b)[0][[x['记录ID'] for x in items].index(a['记录ID'])]['复盘实数'] is None
    with pytest.raises(ValueError,match='另一窗口'):confirm(sixth,old,a,12)
    store.close();store.__init__(store.root);svc=BalanceService(store);assert svc.latest(b)['plan']['rows'][a['记录ID']]['draft']=='13.0000'
    run=svc.edit(b,run['id'],run['version'],rev,a['记录ID'],'','模拟不符合',kind='reject');assert all(r['stage']!='pending' for r in run['plan']['rows'].values())
    run=svc.generate(b,rev);assert run['plan']['rows'][a['记录ID']]['stage']=='pending'
    assert store.exchange_history()==before and not CandidateEngine(items,state['vendors'],exchange=store.exchange_list()).eligibility[other['记录ID']]['eligible']
    with zipfile.ZipFile(io.BytesIO(store.audit_zip(b))) as archive:assert '卓不凡平衡建议历史.json' in archive.namelist()

def test_directory_version_and_atomic_failure(store,sixth,monkeypatch):
    b,items,state,rev,a,z,svc=sixth;run=svc.generate(b,rev)
    original=svc._action
    def fail(*args,**kwargs):
        if args[3]=='confirm':raise ValueError('模拟写入失败')
        return original(*args,**kwargs)
    monkeypatch.setattr(svc,'_action',fail)
    with pytest.raises(ValueError,match='失败'):confirm(sixth,run,a,12,request='atomic')
    assert store.load(b)[3]==rev and svc.latest(b)==run and not store.db.execute('SELECT 1 FROM requests WHERE request_id=?',('atomic',)).fetchone()
    assert all(x['复盘实数'] is None for x in store.load(b)[0])
    # 不更改批次revision也会核查全局供应商目录版本。
    import balance_service
    monkeypatch.setattr(balance_service,'supplier_signature',lambda s:'changed')
    with pytest.raises(ValueError,match='目录'):confirm(sixth,run,a,12)

def test_export_latest_full_batch_blockers_types_and_proposal_isolation(store,sixth):
    b,items,state,rev,a,z,svc=sixth;svc.generate(b,rev);s=snapshot(store,b,'preview')
    assert s['count']==500 and s['remaining']==500 and s['xls'] is None and s['blockers']
    # 原有审核条件/人工凭证沿用；不会让草稿绕过阻断。
    updated=patch_items(items,{x['记录ID']:{'复盘实数':x['系统数']-x['原始调整'],'单位说明':'模拟单位已核查'} for x in items})
    state['meta'].update(coverage=True,evidence=True);store.save(b,updated,state,rev)
    import base64
    s=snapshot(store,b,'download');assert s['revision']==rev+1 and s['count']==500 and not s['blockers']
    sheet=xlrd.open_workbook(file_contents=base64.b64decode(s['xls'])).sheet_by_index(0)
    assert sheet.nrows==501 and sheet.ncols==3 and sheet.row_values(0)==['商品编码','商品条码','数量']
    assert all(sheet.cell(r,0).ctype==1 and sheet.cell(r,1).ctype==1 and sheet.cell(r,2).ctype==2 for r in range(1,501))
    newitems,_,newstate,newrev=store.load(b);store.save(b,patch_items(newitems,{a['记录ID']:{'复盘实数':0}}),newstate,newrev)
    s=snapshot(store,b,'new');assert s['revision']==newrev+1 and next(r for r in s['rows'] if r[1]==a['商品条码'])[2]=='0.0000'

def test_js_exact_selection_cases():
    if not shutil.which('node'):pytest.skip('Node unavailable')
    subprocess.run(['node',str(Path(__file__).with_name('selection_cases.mjs'))],check=True,capture_output=True,text=True,encoding='utf8')

def test_existing_ten_table_schema_and_every_value_unchanged(store,sixth):
    from print_manager import generate_print
    b,items,state,rev,a,z,svc=sixth
    store.save_exchange([catalog_record(items[-1])],items)
    generate_print(store,b,items,state['meta'],'all','category',[],rev)
    names=['batches','events','evidence_files','exchange_history','exchange_products','item_events','preferences','prints','requests','sources']
    before={t:(store.db.execute('SELECT sql FROM sqlite_master WHERE name=?',(t,)).fetchone(),store.db.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall()) for t in names}
    store.db.executescript('DROP TABLE balance_actions;DROP TABLE balance_runs;PRAGMA user_version=15;')
    store.close();store.__init__(store.root)
    assert before=={t:(store.db.execute('SELECT sql FROM sqlite_master WHERE name=?',(t,)).fetchone(),store.db.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall()) for t in names}
    assert store.db.execute('PRAGMA user_version').fetchone()[0]==16

def test_confirm_zero_empty_and_deviation_remain_factual(store,sixth):
    b,_,_,rev,a,z,svc=sixth;run=svc.generate(b,rev)
    for value,note in [('', '模拟说明'),('12',''),('-1','模拟说明')]:
        with pytest.raises(ValueError):confirm(sixth,run,a,value,note)
    run=confirm(sixth,run,a,'0');assert run['plan']['rows'][a['记录ID']]['confirmed']=='0.0000'
    assert run['plan']['rows'][z['记录ID']]['stage']=='unmatched' and run['plan']['relations'][0]['status']=='mismatch'
    assert run['plan']['rows'][a['记录ID']]['q']=='0'
