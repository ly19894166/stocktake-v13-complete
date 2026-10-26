"""审批/草稿独立模拟环境，严禁接入正式目录。"""
import os,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from prepare_fourth_demo import fourth_rows,fourth_vendors
from synthetic_data import workbook
from approval_fixture import template
from approval_reporting import save_template
from core import import_pair
from storage import Store

ROOT=Path(__file__).resolve().parents[1]
def folder():
    value=Path(os.environ.get('STOCKTAKE_APPROVAL_DATA_DIR',ROOT/'tests/runtime/approval_data')).resolve()
    assert value.is_relative_to((ROOT/'tests/runtime').resolve()),'只能使用模拟目录'
    return value
def prepare():
    db=Store(folder());result={}
    try:
        for kind in ['normal','missing']:
            rows=fourth_rows(500)
            for i,r in enumerate(rows):
                r['商品商家编码']=str(i+1).zfill(8)
                if i%10==0:r['部类名称']='鲜食'
            rows[9]['子转母商品数量']=4;rows[9]['差异数量']+=4;rows[9]['成本金额']=rows[9]['差异数量']*rows[9]['成本价']
            rows[1]['商品条码']='000123456789012345678901'
            if kind=='missing':rows[6]['成本价']=None;rows[6]['成本金额']=None;rows[7]['商品']='';rows[8]['初盘数量']=None
            g=('模拟盘盈.xls',workbook([r for r in rows if r['差异数量']>=0]));l=('模拟盘亏.xls',workbook([r for r in rows if r['差异数量']<0]));items,notes,fp=import_pair(g,l)
            batch=db.create(items,notes,fp,'模拟审批门店_'+kind,'模拟季度盘点',{'盘盈':g,'盘亏':l});items,_,state,rev=db.load(batch)
            state['vendors']=fourth_vendors(rows);state['meta'].update(sales_amount='1500000',sales_cost='1')
            state['meta']['report']={'store':'模拟审批门店','quarter':'模拟季度','reason':'','reason_confirmed':False,'fresh_enabled':True,'fresh_sales':'2000','fresh_cost':'1000','fresh_gain':'5','fresh_loss':'-10'}
            db.save(batch,items,state,rev);result[kind]=batch
            if kind=='normal':save_template(db.root,template(items))
        db.set_preference('last_batch',result['normal']);(ROOT/'tests/runtime/approval_batches.json').write_text(json.dumps(result),encoding='utf8')
    finally:db.close()
    return result
def select_missing():
    ids=json.loads((ROOT/'tests/runtime/approval_batches.json').read_text('utf8'));db=Store(folder())
    try:assert ids['missing'] in {b['id'] for b in db.list_batches()};db.set_preference('last_batch',ids['missing'])
    finally:db.close()
if __name__=='__main__':print(select_missing() if '--select-missing' in sys.argv else prepare())
