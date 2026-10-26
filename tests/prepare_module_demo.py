"""生成界面模块验收所需的纯虚构Excel，不读取业务文件。"""
from pathlib import Path
import openpyxl

def prepare():
    out=Path(__file__).parent/'runtime/module_demo';out.mkdir(parents=True,exist_ok=True)
    for name,headers,rows in [
        ('模拟供应商.xlsx',['商品条码','供应商','商品名称'],[['0990000000000','模拟供货商甲','模拟商品000'],['0990000000001','模拟供货商甲','模拟商品001']]),
        ('模拟跨店.xlsx',['商品条码','差异数量','日期','单号'],[['0990000000000',-2,'2026-01-01','SIM-CROSS-01']])]:
        w=openpyxl.Workbook();s=w.active;s.append(headers)
        for row in rows:s.append(row)
        w.save(out/name)
    print(out)

if __name__=='__main__':prepare()
