"""第四次优化：450条从零构造商品、虚构供应商与多层品类。"""
from pathlib import Path
import json,io
from decimal import Decimal as D,ROUND_HALF_UP
import openpyxl
from synthetic_data import source_rows,workbook

def fourth_rows(count=450):
    rows=source_rows(count)
    for i,r in enumerate(rows):
        r['大类名称']=['模拟饮料','模拟零食','模拟日用'][i%3]
        r['中类名称']='模拟细分'+str(i%4)
        r['商品名称']=f'模拟商品{i:03d}' if i%31 else f'模拟完整长商品名称{i:03d}用于验证货架查找与清晰换行'+('加长规格说明'*5)
        if i==count-1:r['初盘数量']=r['库存数量']-3
        diff=D(str(r['初盘数量']))-D(str(r['库存数量']))+D(str(r['子转母商品数量']))
        r['差异数量']=float(diff);r['成本金额']=float((diff*D(str(r['成本价']))).quantize(D('.01'),rounding=ROUND_HALF_UP))
    return rows

def fourth_vendors(rows):
    vendors=[]
    for i,r in enumerate(rows):
        if i>=len(rows)-5:continue
        if i<60:code,name='SIM-ZBF','卓不凡' if i<45 else '桌不凡'
        elif 70<=i<80:code,name='SIM-UNCONFIRMED','桌不凡'
        else:code,name='SIM-OTHER','模拟其他供货商'
        vendors.append({'商品条码':r['商品条码'],'供货商编码':code,'供货商名称':name,'商品编码':r['商品'],'供应商商品名称':r['商品名称']})
        if 60<=i<70:vendors.append({'商品条码':r['商品条码'],'供货商编码':'SIM-ZBF','供货商名称':'卓不凡'})
    return vendors

def prepare(directory=None):
    out=Path(directory or Path(__file__).parent/'runtime/fourth_demo');out.mkdir(parents=True,exist_ok=True)
    rows=fourth_rows();vendors=fourth_vendors(rows)
    for name,part in [('模拟450初盘盘盈.xls',[r for r in rows if r['差异数量']>=0]),('模拟450初盘盘亏.xls',[r for r in rows if r['差异数量']<0])]:
        (out/name).write_bytes(workbook(part))
    w=openpyxl.Workbook();s=w.active;s.title='模拟供应商';headers=['商品条码','供货商编码','供货商名称','商品编码','供应商商品名称'];s.append(headers)
    for v in vendors:s.append([v.get(k,'') for k in headers])
    w.save(out/'模拟供应商目录.xlsx')
    (out/'expected.json').write_text(json.dumps({'rows':rows,'vendors':vendors},ensure_ascii=False),encoding='utf8')
    return out

if __name__=='__main__':print(prepare())
