"""用Python Decimal和V13内核独立核对浏览器六列合计。只读模拟截图目录。"""
import sys,json
from pathlib import Path
from decimal import Decimal as D,InvalidOperation
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from core import current_total,newest_diff,current_amount
OUT=ROOT/'tests/runtime/sumtail_results'
FIELDS=('system','initial','recount','total','diff','amount')

def decimal(raw):
    try:v=D(str(raw))
    except InvalidOperation:return None
    return v if v.is_finite() else None

def verify():
    files=sorted(OUT.glob('0*.json'));assert len(files)==9,'缺少分阶段合计样本'
    scopes=0;rows_checked=0
    for path in files:
        snap=json.loads(path.read_text('utf8'));rows=snap['rows'];byid={r['id']:r for r in rows};assert len(rows) in (427,2407)
        # 前端提供的总数/差异/金额逐行与原业务内核一致，空白与0原样传入。
        for r in rows:
            x={'初盘数':D(r['stats_raw']['initial']),'系统数':D(r['stats_raw']['system']),'复盘实数':None if r['stats_raw']['recount'] is None else D(r['stats_raw']['recount']),'原始调整':D(str(r['adjustment'])),'成本价':None if r['cost'] is None else D(str(r['cost']))}
            for field,fn in [('total',current_total),('diff',newest_diff),('amount',current_amount)]:assert decimal(r['stats_raw'][field])==fn(x),(path.name,r['sequence'],field)
            rows_checked+=1
        for footer in snap['footers']:
            selected=rows if footer['scope']=='store' else [byid[k] for k in snap['filtered']]
            for field in FIELDS:
                valid=[decimal(r['stats_raw'][field]) for r in selected];expected=sum((v for v in valid if v is not None),D(0))
                assert D(footer['columns'][field])==expected,(path.name,footer['scope'],field)
            done=sum(r['stats_raw']['recount'] is not None for r in selected)
            assert f'已填复盘 {done} / 未填 {len(selected)-done}' in footer['label']
            assert f'· {len(selected)}条' in footer['label'];scopes+=1
    before=json.loads((OUT/'02_全店427条合计.json').read_text('utf8'));zero=json.loads((OUT/'04_保存0后合计.json').read_text('utf8'));blank=json.loads((OUT/'05_清空复盘后合计.json').read_text('utf8'))
    assert before['footers'][1]['columns']['total']==blank['footers'][1]['columns']['total']
    assert D(zero['footers'][1]['columns']['total'])<D(blank['footers'][1]['columns']['total'])
    initial=json.loads((OUT/'08_大清单仅加载首批.json').read_text('utf8'));last=json.loads((OUT/'09_2407条全量合计.json').read_text('utf8'));assert initial['footers']==last['footers']
    result={'pass':True,'simulated_only':True,'snapshots':len(files),'scope_totals_verified':scopes,'fields_per_scope':6,'rows_verified_against_core':rows_checked,'raw_decimal_sums':True,'blank_and_zero_distinct':True,'saved_updates_verified':True,'full_totals_independent_of_rendered_rows':True}
    (OUT/'sumtail_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result

if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False))
