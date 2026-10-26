import copy,json,subprocess,shutil
from decimal import Decimal as D
from pathlib import Path
import pytest
from supplier_policy import SupplierDirectory
from intelligence import engine_for
from workbench_efficiency import issue_model
from core import current_total,current_amount,newest_diff,export_blockers

@pytest.mark.parametrize('records,expected',[
    ([],False),([{'供货商名称':'模拟普通'}],False),([{'供货商名称':'桌不凡'}],True),
    ([{'供货商编码':'SIM-Z','供货商名称':'卓不凡','失效日期':'2020-01-01'}],True),
    ([{'供货商编码':'SIM-Z','供货商名称':'卓不凡','生效日期':'坏日期'}],True),
    ([{'供货商编码':'SIM-Z','供货商名称':'卓不凡'},{'供货商编码':'SIM-O','供货商名称':'模拟其他'}],True),
    ([{'供货商编码':'SIM-A','供货商名称':'模拟甲'},{'供货商编码':'SIM-B','供货商名称':'模拟乙'}],False)])
def test_only_zbf_related_pending_prompts(records,expected):
    rows=[{'商品条码':'0990',**r} for r in records];directory=SupplierDirectory(rows,{'first_import_at':'2026-10-26'})
    x={'商品条码':'0990'};assert directory.zbf_review(x) is expected
    assert directory.classify(x)['status']=='pending' # 没有提示仍保持未知，不授权也不认定普通。

def test_code_related_conflict_and_confirmed_selection():
    rows=[{'商品条码':'0991','供货商编码':'SIM-X','供货商名称':'卓不凡'},{'商品条码':'0992','供货商编码':'SIM-X','供货商名称':'模拟其他'}]
    d=SupplierDirectory(rows);assert d.classify({'商品条码':'0992'})['status']=='pending' and d.zbf_review({'商品条码':'0992'})
    rows.append({'商品条码':'0991','供货商编码':'SIM-OTHER','供货商名称':'模拟其他'})
    d=SupplierDirectory(rows,{'supplier_codes':{'0991':'SIM-OTHER'}});assert d.classify({'商品条码':'0991'})['status']=='other' and not d.zbf_review({'商品条码':'0991'})

def test_progress_is_readonly_full_store_and_same_export_basis(items):
    state={'meta':{'sales_cost':'1000000'},'vendors':[]};items=copy.deepcopy(items)
    items[0]['成本价']=None;items[1]['商品编码']='';items[2]['复盘实数']=D(0);items[3]['复盘实数']=items[3]['初盘数'];items[4]['复盘实数']=items[4]['系统数']-items[4]['原始调整']
    before=copy.deepcopy(items);engine=engine_for(items,state);issues,p=issue_model(items,state['meta'],engine)
    assert p['missing_cost']==1 and p['missing_code']==1 and p['pending']==len(items)-3 and p['net_loss_rate'] is None
    assert issues[items[2]['记录ID']]['significant_change'] and issues[items[2]['记录ID']]['missing_reason']
    assert not issues[items[4]['记录ID']]['missing_reason']
    assert all(issues[x['记录ID']]['export_issue'] for x in items if x['复盘实数'] is None)
    assert items==before

@pytest.mark.parametrize('cost,expected',[('100000','0.10'),('0',None),(None,None)])
def test_net_loss_rate_is_positive_and_full_precision(items,cost,expected):
    for x in items:x['成本价']=D(1);x['复盘实数']=x['系统数']-x['原始调整']
    items[0]['复盘实数']-=10
    state={'meta':{'sales_cost':cost},'vendors':[]};_,p=issue_model(items,state['meta'],engine_for(items,state));assert p['net_loss_rate']==expected

def test_seventh_js_contracts():
    if not shutil.which('node'):pytest.skip('Node unavailable')
    subprocess.run(['node',str(Path(__file__).with_name('seventh_cases.mjs'))],check=True,capture_output=True,text=True,encoding='utf8')
