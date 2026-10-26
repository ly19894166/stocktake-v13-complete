import copy,base64,hashlib
from decimal import Decimal as D
import pytest,xlrd
from approval_fixture import template
from approval_reporting import generate,read_template,split_items,COMMON,FRESH,save_template,row_values,capture_style
from approval_page import latest_report
from core import current_amount,newest_diff,patch_items,current_total,summary
from company_export import snapshot,current_draft_xls
from reporting import financial_panel,report_document

def test_local_template_two_headers_formats_values_and_no_stale_content(items):
    items[0]['商家编码']='000123';items[-1]['商家编码']='000999';items[0]['复盘实数']=D(0)
    items[1]['成本价']=None;items[1]['复盘实数']=None
    blob=template(items);before=copy.deepcopy(items);meta={'sales_cost':'100000','sales_amount':'150000','store':'模拟门店','period':'模拟季度'}
    data,m=generate(items,meta,blob,7);b=xlrd.open_workbook(file_contents=data,formatting_info=True)
    assert b.sheet_names()==['常规商品','鲜食'] and m['total']==len(items) and m['revision']==7
    assert sum(s['count'] for s in m['sheets'].values())==len(items)
    assert m['panel']==financial_panel(items,meta) and '全店口径' in m['report_text'] and financial_panel(items,meta)['allowance'] in m['report_text']
    byid={x['记录ID']:x for x in items}
    for s,headers in zip(b.sheets(),(COMMON,FRESH)):
        assert s.row_values(0)==list(headers)
        assert s.colinfo_map[6].hidden and s.colinfo_map[2].width==32*256
        assert b.font_list[b.xf_list[s.cell_xf_index(0,0)].font_index].bold
        for r,ident in enumerate(m['sheets'][s.name]['ids'],1):
            x=byid[ident];assert s.cell(r,0).ctype in (xlrd.XL_CELL_TEXT,xlrd.XL_CELL_BLANK)
            assert s.cell_value(r,1)==x['商品条码'] and s.cell_value(r,len(headers)-4)==float(newest_diff(x))
            assert s.cell_value(r,len(headers)-2)==('' if current_amount(x) is None else float(current_amount(x)))
            if x.get('复盘实数') is None:assert s.cell_value(r,len(headers)-5)=='' and '暂估' in s.cell_value(r,len(headers)-1)
        assert all('模拟旧批次_禁止复制' not in str(v) for r in range(s.nrows) for v in s.row_values(r))
    assert items==before

def test_identity_conflict_and_explicit_fresh_are_not_name_guesses(items):
    items[0]['商家编码']='SIM-C';items[-1]['商家编码']='SIM-F';b=read_template(template(items));groups,pending=split_items(items,b)
    assert items[-1] in groups['鲜食']
    items[-1]['商家编码']='WRONG';groups,pending=split_items(items,b)
    assert items[-1] in groups['常规商品'] and items[-1]['记录ID'] in pending
    items[2]['部类']='鲜食';items[3]['商品名称']='模拟鲜食名称而非部类';groups,_=split_items(items,b)
    assert items[2] in groups['鲜食'] and items[3] in groups['常规商品']

@pytest.mark.parametrize('case',['unreviewed','over_limit','missing_cost','missing_code','missing_reason','invalid_quantity'])
def test_draft_always_available_but_formal_checks_remain(store,batch,case):
    items,_,state,rev=store.load(batch)
    if case=='over_limit':
        for x in items:x['复盘实数']=D(0);x['备注']='模拟核查说明'
        state['meta'].update(sales_cost='1',coverage=True,evidence=True)
    elif case=='missing_cost':items[0]['成本价']=None
    elif case=='missing_code':items[0]['商品编码']=''
    elif case=='missing_reason':items[0]['复盘实数']=D(0);items[0]['备注']=''
    elif case=='invalid_quantity':items[0]['初盘数']=None
    if case in ('missing_code','invalid_quantity'):
        # 编码和初盘是不可改原件字段，模拟导入时已有缺项，不能用编辑接口伪造。
        batch=store.create(items,[],case,'模拟缺项门店','模拟缺项期间',{})
    else:store.save(batch,items,state,rev)
    before={t:store.db.execute('SELECT * FROM '+t).fetchall() for t in ['batches','events','prints','item_events']}
    snap=snapshot(store,batch,'draft');assert snap['draft_xls'] and snap['xls'] is None and snap['blockers']
    sheet=xlrd.open_workbook(file_contents=base64.b64decode(snap['draft_xls'])).sheet_by_index(0)
    assert sheet.ncols==3 and sheet.nrows==len(items)+1 and sheet.row_values(0)==['商品编码','商品条码','数量']
    for r,x in enumerate(items,1):assert sheet.cell_value(r,2)==('' if current_total(x) is None else float(current_total(x)))
    if case=='missing_code':assert sheet.cell_value(1,0)==''
    assert before=={t:store.db.execute('SELECT * FROM '+t).fetchall() for t in before}

def test_approval_download_reads_new_revision_each_time(store,batch,monkeypatch):
    monkeypatch.delenv('STOCKTAKE_APPROVAL_TEMPLATE',raising=False)
    items,_,state,rev=store.load(batch);save_template(store.root,template(items))
    _,a=latest_report(store.root,batch);updated=patch_items(items,{items[0]['记录ID']:{'复盘实数':0}});store.save(batch,updated,state,rev)
    _,b=latest_report(store.root,batch);assert a['revision']+1==b['revision'] and a['panel']!=b['panel']

def test_malformed_template_is_rejected_without_replacing_saved_file(tmp_path):
    path=save_template(tmp_path,template());old=path.read_bytes()
    with pytest.raises(Exception):save_template(tmp_path,b'not Excel')
    assert path.read_bytes()==old

def test_wps_display_colour_profile_is_bound_to_exact_template(items):
    blob=template(items);profile={'template_sha256':hashlib.sha256(blob).hexdigest(),'sheets':{}}
    for name,headers in [('常规商品',COMMON),('鲜食',FRESH)]:profile['sheets'][name]={part:[{'fill':0x123456,'font':0} for _ in headers] for part in ['header','body']}
    data,_=generate(items,{},blob,1,profile);b=xlrd.open_workbook(file_contents=data,formatting_info=True);s=b.sheet_by_index(0);xf=b.xf_list[s.cell_xf_index(1,0)]
    assert b.colour_map[xf.background.pattern_colour_index]==(0x56,0x34,0x12)
    data,_=generate(items,{},blob,1,{'template_sha256':'other'})
    b=xlrd.open_workbook(file_contents=data,formatting_info=True);s=b.sheet_by_index(0);xf=b.xf_list[s.cell_xf_index(1,0)]
    assert b.colour_map[xf.background.pattern_colour_index]!=(0x56,0x34,0x12)

def test_fresh_approval_text_uses_current_rows_without_overwriting_independent_inputs(items):
    items[-1]['商家编码']='SIM-F';blob=template(items)
    meta={'sales_cost':'100000','report':{'fresh_enabled':True,'fresh_gain':'999999','fresh_loss':'-999999','fresh_sales':'2000','fresh_cost':'1000'}};old=copy.deepcopy(meta)
    _,m=generate(items,meta,blob,1)
    assert '999999' not in m['report_text'] and '2000.00' in m['report_text'] and '季度待填写' in m['report_text'] and meta==old
    assert m['panel']==financial_panel(items,meta)

def test_style_capture_never_opens_or_rewrites_the_original_template(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from pathlib import Path
    import approval_reporting
    source=tmp_path/'template.xls';blob=template();source.write_bytes(blob);opened=[]
    def wps(args,**kwargs):
        working=Path(args[-1]);opened.append(working);assert working!=source
        working.write_bytes(b'simulated WPS metadata rewrite')
        return SimpleNamespace(stdout='{"version":1,"sheets":{}}')
    monkeypatch.setattr(approval_reporting.subprocess,'run',wps)
    profile=capture_style(source)
    assert source.read_bytes()==blob and profile['template_sha256']==hashlib.sha256(blob).hexdigest()
    assert not opened[0].exists()
