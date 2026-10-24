import copy,io
from decimal import Decimal as D
import pytest,xlrd
from core import import_pair,patch_items,newest_diff,initial_diff,current_total,summary,create_company_xls,export_blockers
from workflow import linked_order,change_description,print_layout
from intelligence import CandidateEngine,row_models
from print_manager import printable_items,snapshot_rows
from reporting import report_document
from prepare_workflow_demo import workflow_rows
from synthetic_data import workbook

@pytest.fixture
def workflow_items():
    rows=workflow_rows();gain=[r for r in rows if r['差异数量']>=0];loss=[r for r in rows if r['差异数量']<0]
    return import_pair(('模拟盘盈.xls',workbook(gain)),('模拟盘亏.xls',workbook(loss)))[0]

def test_450_linked_order_unique_and_explicit_pair(workflow_items):
    engine=CandidateEngine(workflow_items,[]);order,partners=linked_order(workflow_items,engine)
    assert len(order)==len(set(order))==450
    a,b=workflow_items[:2]
    assert partners[a['记录ID']]==b['记录ID'] and abs(order.index(a['记录ID'])-order.index(b['记录ID']))==1
    assert summary(workflow_items,None)==summary([engine.items[k] for k in order],None)
    models=row_models(workflow_items,{'vendors':[],'meta':{}},engine,enrich={a['记录ID']})
    assert models[0]['peers'][0]['name']=='模拟货架商品乙'
    assert models[0]['initial_diff']==-2888

def test_find_four_and_original_conversion(workflow_items):
    a=workflow_items[0];a['复盘实数']=D(5)
    assert initial_diff(a)==-2888 and newest_diff(a)==-2884
    assert '找回4件' in change_description(a)
    model=row_models([a],{'vendors':[],'meta':{}})[0]
    assert model['change']==4 and model['amount']==-1816.92
    conversion=workflow_items[6]
    assert conversion['原始调整']==D('.4') and initial_diff(conversion)==0
    conversion['复盘实数']=D(0)
    assert current_total(conversion)==0 and newest_diff(conversion)==D('-9.6')

@pytest.mark.parametrize('before,after,phrase',[(5,3,'盘盈减少2件'),(5,-2,'转为盘亏2件'),(-5,-7,'盘亏增加2件'),(-5,0,'差异归零'),(-5,2,'转为盘盈2件'),(0,0,'实数已确认')])
def test_short_change_labels(items,before,after,phrase):
    x=copy.deepcopy(items[0]);x.update(系统数=D(20),初盘数=D(20+before),原始调整=D(0),复盘实数=D(20+after))
    assert phrase in change_description(x)
    x['复盘实数']=None;assert change_description(x)=='未复盘'

def test_print_scopes_and_associated_order(workflow_items):
    selected=printable_items(workflow_items)
    assert any(newest_diff(x)>0 for x in selected) and any(newest_diff(x)<0 for x in selected)
    ordered,hints=print_layout(selected,workflow_items,[],{})
    assert len(ordered)==len({x['记录ID'] for x in ordered})==len(selected)
    a,b=workflow_items[:2];ids=[x['记录ID'] for x in ordered]
    assert abs(ids.index(a['记录ID'])-ids.index(b['记录ID']))==1
    assert '模拟货架商品乙' in hints[a['记录ID']]['related']
    assert all(newest_diff(x)<0 for x in printable_items(workflow_items,'loss'))
    a['复盘实数']=a['系统数'];assert a not in printable_items(workflow_items)
    assert len(snapshot_rows(ordered,hints))==len(selected)

def test_large_company_sheet1_true_xls_and_zero(workflow_items):
    for x in workflow_items:x['复盘实数']=x['系统数']-x['原始调整'];x['备注']='模拟核验';x['单位说明']='模拟单位已核对'
    workflow_items[-1]['复盘实数']=D(0);workflow_items[-1]['核实结论']='已排除'
    meta={'both_files':True,'coverage':True,'evidence':True,'sales_cost':'100000000'}
    blob=create_company_xls(workflow_items,meta,[])
    assert blob.startswith(bytes.fromhex('D0CF11E0A1B11AE1'))
    sheet=xlrd.open_workbook(file_contents=blob).sheet_by_name('Sheet1')
    assert sheet.ncols==3 and sheet.nrows==451
    assert sheet.row_values(0)==['商品编码','商品条码','数量']
    for i,x in enumerate(workflow_items,1):
        assert sheet.cell_type(i,0)==sheet.cell_type(i,1)==xlrd.XL_CELL_TEXT
        assert sheet.cell_type(i,2)==xlrd.XL_CELL_NUMBER
        assert sheet.row_values(i)==[x['商品编码'],x['商品条码'],float(current_total(x))]
    assert sheet.cell_value(450,2)==0
    workflow_items[0]['商品条码']='INVALID'
    assert any('完整数字文本' in e for e in export_blockers(workflow_items,meta,[]))
    with pytest.raises(ValueError):create_company_xls(workflow_items,meta,[])

def test_saved_report_signature_changes_with_committed_quantity(workflow_items):
    meta={'sales_cost':'10000000','sales_amount':'1234567.89'}
    old=report_document(workflow_items,meta)
    workflow_items[0]['复盘实数']=D(5)
    new=report_document(workflow_items,meta)
    assert old['signature']!=new['signature'] and old['generated']!=new['generated']

def test_coalesced_save_keeps_last_cell_undo(store,batch):
    items,_,state,rev=store.load(batch);a,b=items[:2]
    updated=patch_items(items,{a['记录ID']:{'复盘实数':1},b['记录ID']:{'复盘实数':2,'备注':'模拟最后输入'}})
    steps=[{'id':a['记录ID'],'field':'复盘实数','request_id':'logical-a'},
           {'id':b['记录ID'],'field':'复盘实数','request_id':'logical-b'},
           {'id':b['记录ID'],'field':'备注','request_id':'logical-note'}]
    rev=store.save(batch,updated,state,rev,'模拟操作员','01连续录入','coalesced',steps)
    assert store.item_history(batch)[0]['请求']=='logical-note'
    store.undo_last(batch,rev)
    restored=store.load(batch)[0]
    assert restored[0]['复盘实数']==1 and restored[1]['复盘实数']==2 and restored[1]['备注']==b['备注']
