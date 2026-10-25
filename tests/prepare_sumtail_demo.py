"""427与2407条完全虚构商品，只写独立模拟目录。"""
import os,json
from pathlib import Path
from prepare_fourth_demo import fourth_rows,fourth_vendors
from synthetic_data import workbook
from core import import_pair,patch_items
from storage import Store

def prepare():
    root=Path(__file__).resolve().parents[1];folder=Path(os.environ.get('STOCKTAKE_SUMTAIL_DATA_DIR',root/'tests/runtime/sumtail_data')).resolve()
    assert folder.is_relative_to((root/'tests/runtime').resolve()),'只允许模拟目录'
    s=Store(folder);result={}
    try:
        for count in (427,2407):
            rows=fourth_rows(count)
            if count==427:
                rows[0].update(库存数量=1,初盘数量=1,件装单位='盒',差异数量=0,成本金额=0)
                rows[1].update(库存数量=24,初盘数量=24,件装单位='包',差异数量=0,成本金额=0)
                for i in (0,1):rows[i].update(大类名称='模拟AAA核对',中类名称='模拟数值',商品名称='模拟0'+str(i+1)+('盒装' if i==0 else '包装'))
                vendors=fourth_vendors(rows)
                for v in vendors:
                    if v['商品条码'].endswith('0059'):v.update(供货商编码='SIM-OTHER',供货商名称='模拟其他供货商')
            else:vendors=[{'商品条码':r['商品条码'],'供货商名称':'模拟大清单供应商','供货商编码':'SIM-LARGE'} for r in rows]
            g=('模拟盘盈.xls',workbook([r for r in rows if r['差异数量']>=0]));l=('模拟盘亏.xls',workbook([r for r in rows if r['差异数量']<0]));items,notes,fp=import_pair(g,l)
            batch=s.create(items,notes,fp,'模拟'+str(count)+'条','模拟数字核对',{'盘盈':g,'盘亏':l});items,_,state,rev=s.load(batch)
            state['vendors']=vendors;state['meta']['sales_cost']='10000000'
            zero=next(x for x in items if x['商品条码'].endswith('0002'));items=patch_items(items,{zero['记录ID']:{'复盘实数':0}})
            s.save(batch,items,state,rev);result[str(count)]=batch
        s.set_preference('last_batch',result['427'])
        (root/'tests/runtime/sumtail_batches.json').write_text(json.dumps(result),encoding='utf8');return result
    finally:s.close()

if __name__=='__main__':print(prepare())
