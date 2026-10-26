import copy,shutil,subprocess
from pathlib import Path
from decimal import Decimal as D
import pytest
from core import current_amount,patch_items
from reporting import financial_panel
from supplier_policy import SupplierDirectory,effective_vendors
from zbf_dashboard import dashboard
from test_sixth import sixth,confirm

def test_full_scope_exact_decimal_and_readonly(sixth):
    b,items,state,rev,a,z,svc=sixth;before=copy.deepcopy((items,state));panel=financial_panel(items,state['meta'])
    d=dashboard(items,state,rev);classes=SupplierDirectory(effective_vendors(state),state['meta']).classify_all(items);chosen=[x for x in items if classes[x['记录ID']]['status']=='zbf']
    assert d['total']==60 and d['unreviewed']==60 and d['reviewed']==0
    assert D(d['net'])==sum((current_amount(x) for x in chosen),D(0)) and D(d['distance'])==abs(D(d['net']))
    assert D(d['gain'])+D(d['loss'])==D(d['net']) and d['supplier_pending']>0
    assert not d['final_approved'] and not d['formal_balance_complete'] and (items,state)==before
    assert financial_panel(items,state['meta'])==panel

@pytest.mark.parametrize('sign,status',[(1,'gain'),(-1,'loss'),(0,'zero')])
def test_zero_positive_negative_and_no_false_completion(items,sign,status):
    rows=items[:3]
    for x in rows:x.update(系统数=D(10),初盘数=D(10)+sign,原始调整=D(0),成本价=D('.005'),复盘实数=None)
    state={'meta':{},'vendors':[{'商品条码':x['商品条码'],'供货商编码':'SIM-Z','供货商名称':'卓不凡'} for x in rows]};d=dashboard(rows,state,0)
    assert d['status']==status and d['unreviewed']==3 and not d['formal_balance_complete']
    assert D(d['net'])==D(sign)*D('.03') and D(d['distance'])==D(abs(sign))*D('.03')
    assert ('当前金额已平' if sign==0 else '当前净盘盈，多出0.03元' if sign>0 else '当前净盘亏，还差0.03元')==d['message']

def test_missing_cost_is_incomplete_even_when_difference_zero(sixth):
    _,items,state,rev,a,z,svc=sixth
    a['成本价']=None;a['复盘实数']=a['系统数']-a['原始调整'];d=dashboard(items,state,rev)
    assert d['missing_cost']==1 and d['missing_amount']==1 and all(d[k] is None for k in ['gain','loss','net','distance'])
    assert d['status']=='incomplete' and '金额不完整' in d['message']

def test_only_confirmations_change_formal_money_valid_relations_and_stale_guard(store,sixth):
    b,items,state,rev,a,z,svc=sixth;run=svc.generate(b,rev);original=dashboard(items,state,rev,run)
    assert original['pending_suggestions']==2 and original['verified_relations']==0
    run=svc.edit(b,run['id'],run['version'],rev,a['记录ID'],'13','模拟独立草稿');assert dashboard(store.load(b)[0],state,rev,run)['net']==original['net']
    run=confirm(sixth,run,a,'12');items,_,state,rev=store.load(b);one=dashboard(items,state,rev,run)
    assert one['net']!=original['net'] and one['pending_suggestions']==1 and one['verified_relations']==0
    run=confirm(sixth,run,z,'20');items,_,state,rev=store.load(b);two=dashboard(items,state,rev,run)
    assert two['pending_suggestions']==0 and two['verified_relations']==1
    assert D(two['net'])==D(one['net'])+24 # B成本按自身3元计入，不按A成本抵销。
    changed=patch_items(items,{a['记录ID']:{'复盘实数':11}});store.save(b,changed,state,rev)
    stale=dashboard(store.load(b)[0],state,rev+1,run);assert stale['verified_relations']==0 and not stale['plan_current'] and any('过期' in r for r in stale['risks'])

def test_supplier_conflict_not_silently_included(sixth):
    _,items,state,rev,a,z,svc=sixth
    state['vendors'].append({'商品条码':a['商品条码'],'供货商编码':'SIM-CONFLICT','供货商名称':'模拟其他供应商'})
    d=dashboard(items,state,rev);assert d['total']==59 and d['supplier_pending']>0

def test_drag_geometry_and_filters():
    if not shutil.which('node'):pytest.skip('Node unavailable')
    subprocess.run(['node',str(Path(__file__).with_name('zbf_geometry.mjs'))],check=True,capture_output=True)
