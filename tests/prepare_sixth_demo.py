"""500条完全虚构数据；独立模拟目录，绝不读取正式资料。"""
import io,json,os
from pathlib import Path
import openpyxl
from prepare_fourth_demo import fourth_rows,fourth_vendors
from synthetic_data import workbook

def sixth_rows():
    rows=fourth_rows(500)
    for i,(system,initial,cost) in enumerate([(10,20,2),(20,12,3)]):
        rows[i].update(库存数量=system,初盘数量=initial,成本价=cost,差异数量=initial-system,成本金额=(initial-system)*cost,商品名称='模拟唯一平衡'+('A' if i==0 else 'B'))
    return rows

def sixth_vendors(rows):
    vs=fourth_vendors(rows)
    for v in vs:
        i=int(v['商品条码'][-4:])
        if i<2:v.update(供货商编码='SIM-UNIQUE',供货商名称='卓不凡')
    return vs

def prepare(directory=None):
    out=Path(directory or Path(__file__).parent/'runtime/sixth_demo');out.mkdir(parents=True,exist_ok=True)
    rows=sixth_rows();vs=sixth_vendors(rows)
    for role,part in [('盘盈',[r for r in rows if r['差异数量']>=0]),('盘亏',[r for r in rows if r['差异数量']<0])]:
        (out/('模拟500'+role+'.xls')).write_bytes(workbook(part))
    w=openpyxl.Workbook();s=w.active;s.append(['商品条码','供货商编码','供货商名称','商品编码','供应商商品名称'])
    for v in vs:s.append([v.get(k,'') for k in ['商品条码','供货商编码','供货商名称','商品编码','供应商商品名称']])
    w.save(out/'模拟供应商.xlsx')
    if os.environ.get('STOCKTAKE_SIXTH_DATA_DIR'):
        from core import import_pair
        from storage import Store
        data=Path(os.environ['STOCKTAKE_SIXTH_DATA_DIR']).resolve()
        assert data.is_relative_to((Path(__file__).resolve().parent/'runtime').resolve()),'只允许模拟历史档案'
        items,_,_=import_pair(('模拟盘盈.xls',(out/'模拟500盘盈.xls').read_bytes()),('模拟盘亏.xls',(out/'模拟500盘亏.xls').read_bytes()))
        s=Store(data)
        try:
            if not s.exchange_list():
                records=[{'商品条码':x['商品条码'],'商品编码':x['商品编码'],'商品名称':x['商品名称'],'供应商':'模拟其他供货商','换货资格来源':'人工加入','换货组':'SIM-OLD-GROUP','是否启用':True,'生效日期':'2020-01-01','备注及依据':'模拟旧人工授权，仅历史'} for x in items if 90<=int(x['商品条码'][-4:])<110]
                s.save_exchange(records,items)
        finally:s.close()
    return out

if __name__=='__main__':print(prepare())
