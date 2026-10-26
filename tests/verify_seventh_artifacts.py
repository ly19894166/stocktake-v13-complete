"""独立核对真实浏览器复制出的TSV，严格仅使用模拟截图目录。"""
import json
from pathlib import Path
from decimal import Decimal

OUT=Path(__file__).resolve().parent/'runtime/seventh_results'
FIELDS=['name','barcode','code','system','initial','recount','total','diff','amount']

def verify():
    snapshots=json.loads((OUT/'clipboard_snapshots.json').read_text('utf8'))
    assert len(snapshots)>=7
    total=0
    for snap in snapshots:
        selected={tuple(json.loads(k)) for k in snap['keys']}
        fields=[f for f in FIELDS if any((r['id'],f) in selected for r in snap['rows'])]
        rows=[r for r in snap['rows'] if any((r['id'],f) in selected for f in fields)]
        actual=snap['plain'].replace('\r\n','\n').split('\n')
        expected=[]
        for row in rows:
            cells=[]
            for field in fields:
                raw=(row[field] if field in FIELDS[:3] else row['stats_raw'][field]) if (row['id'],field) in selected else ''
                value='' if raw is None else str(raw)
                if value and (field in ('barcode','code') or field=='name' and value[0] in '=+-@'):value="'"+value
                cells.append(value)
            expected.append('\t'.join(cells))
        assert actual==expected,snap['name']
        assert len(rows)==len(actual)
        if snap['name']=='大清单2407系统数':assert len(actual)==2407
        if snap['name']=='默认368系统数':assert len(actual)==368
        if snap['name']=='全部427完整条码':assert "'000123456789012345678901" in actual
        total+=len(rows)
    browser=json.loads((OUT/'browser_seventh_results.json').read_text('utf8'))
    assert browser['pass'] and browser['large_selection']==2407 and browser['large_initial_rendered']<2407
    result={'pass':True,'simulated_only':True,'clipboard_snapshots':len(snapshots),'rows_checked':total,'full_filtered_order_and_no_hidden_rows':True,'leading_zero_text':True,'tsv_structure':True,'browser_cases':len(browser['cases'])}
    (OUT/'clipboard_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result

if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False))
