"""450条从零构造的模拟数据，含明确一对一和多对多；无真实资料。"""
from pathlib import Path
import json
from decimal import Decimal as D,ROUND_HALF_UP
from synthetic_data import source_rows,workbook

def workflow_rows(count=450):
    rows=source_rows(count)
    rows[0].update(商品名称='模拟仓库商品甲',库存数量=2889,初盘数量=1,成本价=.63)
    rows[1].update(商品名称='模拟货架商品乙',库存数量=20,初盘数量=24,成本价=.63)
    for i in range(2,6):rows[i]['成本价']=1.19
    rows[6].update(库存数量=10,初盘数量=9.6,子转母商品数量=.4)
    for row in rows:
        diff=D(str(row['初盘数量']))-D(str(row['库存数量']))+D(str(row['子转母商品数量']))
        row['差异数量']=float(diff)
        row['成本金额']=float((diff*D(str(row['成本价']))).quantize(D('.01'),rounding=ROUND_HALF_UP))
    return rows

def write_workflow(directory=None,count=450):
    directory=Path(directory or Path(__file__).parent/'runtime/workflow_demo');directory.mkdir(parents=True,exist_ok=True)
    rows=workflow_rows(count)
    gain=[r for r in rows if r['差异数量']>=0];loss=[r for r in rows if r['差异数量']<0]
    for name,part in [('模拟450盘盈.xls',gain),('模拟450盘亏.xls',loss)]:
        (directory/name).write_bytes(workbook(part))
    (directory/'expected.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    return directory

if __name__=='__main__':print(write_workflow())
