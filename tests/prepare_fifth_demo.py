"""第五次：480条完全虚构商品；不读取正式资料。"""
from pathlib import Path
import io,json,sys
import openpyxl
from prepare_fourth_demo import fourth_rows,fourth_vendors
from synthetic_data import workbook
from exchange_registry import HEADERS

def prepare():
    out=Path(__file__).parent/'runtime/fifth_demo';out.mkdir(parents=True,exist_ok=True)
    rows=fourth_rows(480);vendors=fourth_vendors(rows)
    for name,part in [('模拟480盘盈.xls',[r for r in rows if r['差异数量']>=0]),('模拟480盘亏.xls',[r for r in rows if r['差异数量']<0])]:
        (out/name).write_bytes(workbook(part))
    w=openpyxl.Workbook();s=w.active;cols=['商品条码','供货商编码','供货商名称','商品编码','供应商商品名称'];s.append(cols)
    for v in vendors:s.append([v.get(k,'') for k in cols])
    w.save(out/'模拟供应商.xlsx')
    w=openpyxl.Workbook();s=w.active;s.append(HEADERS)
    for i in range(90,118):
        r=rows[i];s.append([r['商品条码'],r['商品'],r['商品名称'],'模拟其他供货商','人工加入','SIM-G1' if i<100 else 'SIM-G2','否' if 110<=i<114 else '是','2099-01-01' if i>=114 else '2020-01-01','模拟经核实的换货组授权'])
    w.save(out/'模拟可换货档案.xlsx')
    (out/'expected.json').write_text(json.dumps({'total':480,'zbf':60,'pending':25,'manual_eligible':20,'eligible':80,'registry':28,'default_scope':420}),encoding='utf8')
    print(out)

if __name__=='__main__':
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]));prepare()
