"""独立读回模拟XLS：逐行与V13内核核对，禁读真实资料。"""
import os,sys,json,copy
from pathlib import Path
from decimal import Decimal as D
import xlrd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from storage import Store
from core import current_total,current_amount,newest_diff,summary
from approval_reporting import read_template,split_items,COMMON,FRESH,TEMPLATE_NAME
from reporting import financial_panel
OUT=ROOT/'tests/runtime/approval_results'

def verify():
    folder=Path(os.environ.get('STOCKTAKE_APPROVAL_DATA_DIR',ROOT/'tests/runtime/approval_data')).resolve();assert folder.is_relative_to((ROOT/'tests/runtime').resolve())
    ids=json.loads((ROOT/'tests/runtime/approval_batches.json').read_text('utf8'));target=json.loads((OUT/'browser_target.json').read_text('utf8'));db=Store(folder)
    try:normal,_,state,_=db.load(ids['normal']);missing,_,badstate,_=db.load(ids['missing'])
    finally:db.close()
    zero=copy.deepcopy(normal);next(x for x in zero if x['记录ID']==target['id'])['复盘实数']=D(0)
    before_template=read_template((folder/'templates'/TEMPLATE_NAME).read_bytes());verified=0
    for name,items in [('模拟超标未复盘草稿.xls',zero),('模拟缺项完整草稿.xls',missing)]:
        blob=(OUT/name).read_bytes();assert blob.startswith(bytes.fromhex('D0CF11E0A1B11AE1'))
        b=xlrd.open_workbook(file_contents=blob);s=b.sheet_by_index(0)
        assert b.nsheets==1 and s.ncols==3 and s.nrows==501 and '草稿' in s.name
        assert s.row_values(0)==['商品编码','商品条码','数量']
        for r,item in enumerate(items,1):
            assert s.cell_value(r,0)==item['商品编码'] and s.cell_value(r,1)==item['商品条码']
            assert s.cell_value(r,2)==('' if current_total(item) is None else float(current_total(item)))
            if item['商品编码']:assert s.cell(r,0).ctype==xlrd.XL_CELL_TEXT
            if item['商品条码']:assert s.cell(r,1).ctype==xlrd.XL_CELL_TEXT
            verified+=1
    results=[]
    for name,items,meta in [('模拟审批母版两表.xls',zero,state['meta']),('模拟审批最新版本.xls',normal,state['meta']),('模拟缺项审批两表.xls',missing,badstate['meta'])]:
        b=xlrd.open_workbook(OUT/name,formatting_info=True);assert b.sheet_names()==['常规商品','鲜食'];groups,_=split_items(items,before_template);count=0;panel=financial_panel(items,meta)
        for s,headers in zip(b.sheets(),(COMMON,FRESH)):
            assert s.row_values(0)==list(headers);rows=groups[s.name]
            for r,item in enumerate(rows,1):
                assert s.cell_value(r,0)==item['商家编码'] and s.cell_value(r,1)==item['商品条码'] and s.cell_value(r,2)==item['商品名称']
                for c,v in [(len(headers)-5,item.get('复盘实数')),(len(headers)-4,newest_diff(item)),(len(headers)-3,item['成本价']),(len(headers)-2,current_amount(item))]:assert s.cell_value(r,c)==('' if v is None else float(v)),(name,s.name,r,c)
                if item.get('复盘实数') is None:assert '暂估' in s.cell_value(r,len(headers)-1)
                if item['成本价'] is None:assert '缺成本' in s.cell_value(r,len(headers)-1)
                if s.name=='鲜食':assert s.cell_value(r,11)==float(item['原始调整'])
                count+=1;verified+=1
            total=s.cell_value(len(rows)+1,len(headers)-2);expected=summary(rows,meta.get('sales_cost'))['净差异'];assert total==('' if expected is None else float(expected))
            all_text='\n'.join(str(v) for r in range(len(rows)+2,s.nrows) for v in s.row_values(r));assert '未审批' in all_text and '全店口径' in all_text
            for field in ['gain','loss','net','allowance','remaining']:
                if panel[field] is not None:assert any(s.cell_value(r,c)==float(D(panel[field])) for r in range(len(rows)+2,s.nrows) for c in range(s.ncols))
            assert not any('模拟旧批次_禁止复制' in str(v) for r in range(s.nrows) for v in s.row_values(r))
        assert count==500;results.append({'file':name,'pass':True,'sheets':2,'rows':count})
    result={'pass':True,'simulated_only':True,'rows_verified':verified,'drafts_true_three_column_xls':True,'blank_and_zero_distinct':True,'latest_revision_and_whole_store':True,'no_template_old_business_values':True,'two_sheet_reports':results}
    (OUT/'approval_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result

if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False))
