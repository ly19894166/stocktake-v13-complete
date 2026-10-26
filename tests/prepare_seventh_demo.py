"""第七次：427/2407条从零构造，包含缺项、已填0、长条码和前导零编码。"""
import os,json
from pathlib import Path
from prepare_fourth_demo import fourth_rows,fourth_vendors
from synthetic_data import workbook
from core import import_pair,patch_items
from storage import Store

def prepare():
    root=Path(__file__).resolve().parents[1];folder=Path(os.environ.get('STOCKTAKE_SEVENTH_DATA_DIR',root/'tests/runtime/seventh_data')).resolve()
    assert folder.is_relative_to((root/'tests/runtime').resolve()),'仅模拟目录'
    s=Store(folder);result={}
    try:
        for count in (427,2407):
            rows=fourth_rows(count)
            if count==427:
                rows[0].update(库存数量=1,初盘数量=1,件装单位='盒',差异数量=0,成本金额=0)
                rows[1].update(库存数量=24,初盘数量=24,件装单位='包',差异数量=0,成本金额=0)
                for i in (0,1,12):rows[i].update(大类名称='模拟AAA核对',中类名称='模拟数值',商品名称={0:'模拟01盒装',1:'模拟02包装',12:'模拟03长条码'}[i],商品=str(i+1).zfill(12))
                rows[12]['商品条码']='000123456789012345678901'
                rows[6].update(成本价=None,成本金额=None);rows[7]['商品']=''
                vendors=fourth_vendors(rows)
                for v in vendors:
                    if v['商品条码'].endswith('0059'):v.update(供货商编码='SIM-OTHER',供货商名称='模拟其他供货商')
            else:vendors=[{'商品条码':r['商品条码'],'供货商名称':'模拟大清单供应商','供货商编码':'SIM-LARGE'} for r in rows]
            g=('模拟盘盈.xls',workbook([r for r in rows if r['差异数量']>=0]));l=('模拟盘亏.xls',workbook([r for r in rows if r['差异数量']<0]));items,notes,fp=import_pair(g,l)
            b=s.create(items,notes,fp,'模拟第七次'+str(count)+'条','模拟效率验收',{'盘盈':g,'盘亏':l});items,_,state,rev=s.load(b);state['vendors']=vendors;state['meta']['sales_cost']='10000000'
            if count==427:
                bybc={x['商品条码']:x for x in items};patches={}
                for i,value in [(2,0),(4,20),(5,8),(10,55)]:patches[bybc[rows[i]['商品条码']]['记录ID']]={'复盘实数':value}
                items=patch_items(items,patches)
            s.save(b,items,state,rev);result[str(count)]=b
        s.set_preference('last_batch',result['427']);(root/'tests/runtime/seventh_batches.json').write_text(json.dumps(result),encoding='utf8');return result
    finally:s.close()

def select_large():
    root=Path(__file__).resolve().parents[1];folder=Path(os.environ.get('STOCKTAKE_SEVENTH_DATA_DIR',root/'tests/runtime/seventh_data')).resolve();assert folder.is_relative_to((root/'tests/runtime').resolve())
    ids=json.loads((root/'tests/runtime/seventh_batches.json').read_text('utf8'));s=Store(folder)
    try:assert ids['2407'] in {b['id'] for b in s.list_batches()};s.set_preference('last_batch',ids['2407'])
    finally:s.close()

if __name__=='__main__':
    import sys
    print(select_large() if '--select-large' in sys.argv else prepare())
