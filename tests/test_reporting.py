"""手工构造的独立模拟金额和旧结构，不读取任何真实报告。"""
import copy,json
from decimal import Decimal as D
import pytest
from core import newest_diff,current_total,summary,export_blockers
from reporting import financial_panel,report_document,validated_meta_value,money

def amounts(items,gain='265.75',loss='-328.63'):
    rows=copy.deepcopy(items[:2])
    for x,system,initial,cost in [(rows[0],0,1,D(gain)),(rows[1],1,0,-D(loss))]:
        x.update(系统数=D(system),初盘数=D(initial),原始调整=D(0),成本价=cost,复盘实数=None,备注='')
    return rows

def test_exact_arithmetic_and_rate_uses_cost_only(items):
    rows=amounts(items);meta={'sales_amount':'80000','sales_cost':'31440','store':'模拟门店甲'}
    p=financial_panel(rows,meta)
    assert p['net']=='-62.88' and p['rate']=='-2.00' and p['allowance']=='62.88'
    assert p['status']=='当前测算达标' and p['remaining']=='0.00' and not p['final_approved']
    meta['sales_amount']='999999'
    assert financial_panel(rows,meta)['rate']=='-2.00'
    assert p['done']==0 and p['remaining_rows']==2
    assert any('待复盘' in b for b in export_blockers(rows,meta,[]))

@pytest.mark.parametrize('gain,loss,label,net',[('265.75','-328.63','合计盘亏','-62.88'),('100.01','-20.00','合计盘盈','80.01'),('105.55','-105.55','合计差异','0.00')])
def test_report_positive_negative_zero_and_two_decimals(items,gain,loss,label,net):
    doc=report_document(amounts(items,gain,loss),{'sales_amount':'1234.5','sales_cost':'50000','store':'模拟门店甲'})
    assert label+'金额：'+net+'元' in doc['generated']
    assert '1234.50元' in doc['generated'] and '当前测算' in doc['generated']
    assert '鲜食盘点' not in doc['generated'] and '请领导审核。' in doc['generated']

@pytest.mark.parametrize('cost',[None,'0',''])
def test_missing_sales_not_fabricated_and_missing_cost_waits(items,cost):
    meta={'sales_cost':cost};panel=financial_panel(items,meta);doc=report_document(items,meta)
    assert panel['status']=='待计算' and panel['rate'] is None
    assert '实际销售金额：待填写元' in doc['generated'] and '待计算' in doc['generated']

def test_raw_limit_does_not_round_away_overrun(items):
    rows=amounts(items,'0.01','-0.02');meta={'sales_cost':'4.9999'}
    p=financial_panel(rows,meta)
    assert p['status']=='当前测算超标' and p['over_limit']
    assert any('超过2' in b for b in export_blockers(rows,meta,[]))
    assert money('1.005')=='1.01' and money('-1.005')=='-1.01'
    assert money('-0.001')=='0.00'

def test_fresh_separate_and_reasons_require_confirmation(items):
    rows=amounts(items);meta={'sales_cost':'100000','report':{'reason':'经手工核对的模拟原因','fresh_enabled':True,
        'fresh_gain':'11.13','fresh_loss':'-14.24','fresh_sales':'100','fresh_cost':'80'}}
    before=summary(rows,meta['sales_cost']);doc=report_document(rows,meta)
    assert '鲜食盘点' in doc['generated'] and '合计盘亏：-3.11元' in doc['generated']
    assert '主要原因：待店长填写并确认' in doc['generated']
    meta['report']['reason_confirmed']=True
    assert '主要原因：经手工核对的模拟原因' in report_document(rows,meta)['generated']
    assert summary(rows,meta['sales_cost'])==before
    meta['report']['fresh_enabled']=False
    assert '鲜食盘点' not in report_document(rows,meta)['generated']

def test_stale_edited_draft_kept_but_latest_numbers_generated(items):
    meta={'sales_cost':'100000'};doc=report_document(items,meta)
    meta['report']={'draft':'模拟人工编辑稿','draft_signature':doc['signature']}
    assert report_document(items,meta)['text']=='模拟人工编辑稿'
    items[0]['复盘实数']=D(0)
    latest=report_document(items,meta)
    assert latest['stale_draft']=='模拟人工编辑稿' and latest['text']==latest['generated']

@pytest.mark.parametrize('scope,field,value',[('finance','sales_cost','NaN'),('finance','sales_amount','-1'),
    ('finance','unknown','1'),('report','fresh_loss','2'),('report','fresh_gain','-2'),
    ('report','report_date','bad-date'),('report','reason_confirmed','yes')])
def test_invalid_meta_rejected(scope,field,value):
    with pytest.raises(ValueError):validated_meta_value(scope,field,value)

def test_old_meta_defaults_and_batch_isolation_persist(store,batch,sample):
    # 模拟真正旧库：删去新键再读取，验证读取不重写任何原始业务行。
    raw=store.db.execute('SELECT state FROM batches WHERE id=?',(batch,)).fetchone()[0]
    old=json.loads(raw);old['meta'].pop('sales_amount',None);old['meta'].pop('report',None)
    with store.db:store.db.execute('UPDATE batches SET state=? WHERE id=?',(json.dumps(old),batch))
    before=store.db.execute('SELECT * FROM batches WHERE id=?',(batch,)).fetchone()
    items,_,state,rev=store.load(batch)
    assert state['meta']['sales_amount'] is None and state['meta']['report']=={}
    assert store.db.execute('SELECT * FROM batches WHERE id=?',(batch,)).fetchone()==before
    second=store.create(sample[0],sample[1],sample[2]+'second','模拟门店乙','模拟期间')
    state['meta'].update(sales_amount='12345.67',sales_cost='2345.67',report={'reason':'模拟原因'})
    store.save(batch,items,state,rev,'测试操作员','经营参数保存')
    from storage import Store
    reopened=Store(store.root)
    try:
        restored=reopened.load(batch)[2]['meta'];other=reopened.load(second)[2]['meta']
        assert restored['sales_amount']=='12345.67' and restored['sales_cost']=='2345.67'
        assert restored['report']['reason']=='模拟原因'
        assert other['sales_amount'] is None and other['sales_cost'] is None and other['report']=={}
        assert reopened.db.execute('SELECT original FROM batches WHERE id=?',(batch,)).fetchone()[0]==before[5]
    finally:reopened.close()
