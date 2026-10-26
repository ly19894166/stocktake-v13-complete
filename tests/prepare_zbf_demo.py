"""卓不凡仪表及反向拖选：独立500条虚构商品。"""
import os,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from prepare_sixth_demo import sixth_rows,sixth_vendors
from prepare_fourth_demo import fourth_rows
from synthetic_data import workbook
from core import import_pair
from storage import Store
ROOT=Path(__file__).resolve().parents[1]

def data_folder():
    root=Path(os.environ.get('STOCKTAKE_ZBF_DATA_DIR',ROOT/'tests/runtime/zbf_data')).resolve();assert root.is_relative_to((ROOT/'tests/runtime').resolve())
    return root
def prepare():
    db=Store(data_folder());ids={}
    try:
        for kind in ['normal','zero','gain','missing','large']:
            raw=fourth_rows(2407) if kind=='large' else sixth_rows()
            for i,r in enumerate(raw):
                if kind=='large':
                    diff=1 if i==0 else -1 if i==len(raw)-1 else 0
                    r.update(初盘数量=r['库存数量']+diff,子转母商品数量=0,差异数量=diff,成本金额=diff*r['成本价'])
                if i<60 and kind in ('zero','gain'):
                    r['初盘数量']=r['库存数量']+(1 if kind=='gain' else 0);r['差异数量']=r['初盘数量']-r['库存数量']+r['子转母商品数量'];r['成本金额']=r['差异数量']*r['成本价']
                if i==3 and kind=='missing':r['成本价']=None;r['成本金额']=None
            g=('模拟盘盈.xls',workbook([r for r in raw if r['差异数量']>=0]));l=('模拟盘亏.xls',workbook([r for r in raw if r['差异数量']<0]));items,notes,fp=import_pair(g,l)
            batch=db.create(items,notes,fp,'模拟卓不凡门店_'+kind,'模拟专项期间',{'盘盈':g,'盘亏':l});items,_,state,rev=db.load(batch)
            state['vendors']=([{'商品条码':r['商品条码'],'商品编码':r['商品'],'供货商编码':'SIM-LARGE','供货商名称':'卓不凡'} for r in raw] if kind=='large' else sixth_vendors(raw))
            state['meta']['sales_cost']='10000000';db.save(batch,items,state,rev);ids[kind]=batch
        db.set_preference('last_batch',ids['normal'])
        (ROOT/'tests/runtime/zbf_batch.json').write_text(json.dumps(ids),encoding='utf8')
    finally:db.close()
    return ids
def select(kind):
    ids=json.loads((ROOT/'tests/runtime/zbf_batch.json').read_text('utf8'));db=Store(data_folder())
    try:assert ids[kind] in {b['id'] for b in db.list_batches()};db.set_preference('last_batch',ids[kind])
    finally:db.close()
if __name__=='__main__':print(select(sys.argv[2]) if len(sys.argv)>2 and sys.argv[1]=='--select' else prepare())
