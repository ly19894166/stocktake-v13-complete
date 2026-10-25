import copy,io
from datetime import date
from decimal import Decimal as D
import pytest,openpyxl,xlrd
from core import import_pair,summary,patch_items,current_total,newest_diff,create_company_xls
from report_intake import resolve_reports
from supplier_policy import SupplierDirectory
from vendor_audit import audit_model,filtered_rows,audit_excel,HEADERS
from print_manager import select_field_items,make_pdf,generate_print,reprint,snapshot_rows
from workflow import print_order
from reporting import financial_panel
from prepare_fourth_demo import fourth_rows,fourth_vendors
from synthetic_data import workbook,simulated_pair

@pytest.fixture
def fourth():
    raw=fourth_rows();g=('模拟盘盈.xls',workbook([r for r in raw if r['差异数量']>=0]));l=('模拟盘亏.xls',workbook([r for r in raw if r['差异数量']<0]))
    return import_pair(g,l)[0],fourth_vendors(raw),g,l

def test_one_control_intake_recovers_committed_batch(store,fourth):
    items,vs,g,l=fourth;roles=resolve_reports([l,g]);assert roles=={'盘亏':l,'盘盈':g}
    rows,notes,fp=import_pair(roles['盘盈'],roles['盘亏']);b=store.create(rows,notes,fp,sources=roles)
    original,_,state,rev=store.load(b);updated=patch_items(original,{original[0]['记录ID']:{'复盘实数':0,'备注':'模拟已保存复盘'}})
    store.save(b,updated,state,rev)
    roles=resolve_reports([g,l]);rows,notes,fp=import_pair(roles['盘盈'],roles['盘亏']);assert store.create(rows,notes,fp,sources=roles)==b
    assert store.load(b)[0][0]['复盘实数']==0 and len(store.list_batches())==1

@pytest.mark.parametrize('kind',['one','three','duplicate','same_role','wrong_name','mixed','empty'])
def test_strict_two_report_recognition(kind):
    g,l=simulated_pair()
    files={'one':[g],'three':[g,l,g],'duplicate':[g,g],'same_role':[g,('另一盘盈.xls',g[1]+b' ')],'wrong_name':[('盘亏.xls',g[1]),l],
        'mixed':[('不明.xls',workbook(fourth_rows(12))),l],'empty':[('空.xls',workbook([])),l]}[kind]
    with pytest.raises(ValueError):resolve_reports(files)

def test_role_from_actual_structure_when_neutral_names():
    g,l=simulated_pair();assert set(resolve_reports([('A.xls',l[1]),('B.xls',g[1])]))=={'盘盈','盘亏'}

def test_supplier_codes_alias_conflicts_and_dates(fourth):
    items,vs,*_=fourth;directory=SupplierDirectory(vs);classes=directory.classify_all(items)
    assert sum(c['status']=='zbf' for c in classes.values())==60
    assert sum(c['status']=='pending' for c in classes.values())==25
    assert all(c['name']=='卓不凡' for c in classes.values() if c['status']=='zbf')
    bc='0990000000060';x=next(x for x in items if x['商品条码']==bc)
    assert directory.classify(x)['status']=='pending'
    assert SupplierDirectory(vs,{'supplier_codes':{bc:'SIM-ZBF'}}).classify(x)['status']=='zbf'
    assert SupplierDirectory(vs,{'supplier_codes':{bc:'SIM-OTHER'}}).classify(x)['status']=='other'
    expired=[{'商品条码':'0990','供货商编码':'SIM-ZBF','供货商名称':'卓不凡','失效日期':'2020-01-01'}]
    assert SupplierDirectory(expired,today=date(2026,1,1)).classify({'商品条码':'0990'})['status']=='pending'
    duplicate=vs+[vs[0].copy()];assert SupplierDirectory(duplicate).classify({'商品条码':vs[0]['商品条码']})['status']=='zbf'
    ambiguous=[{'商品条码':'0991','供货商编码':'SIM-X','供货商名称':'卓不凡'},{'商品条码':'0992','供货商编码':'SIM-X','供货商名称':'模拟不同公司'}]
    assert all(SupplierDirectory(ambiguous).classify({'商品条码':bc})['status']=='pending' for bc in ('0991','0992'))

def test_audit_amounts_schema_and_manual_evidence(store,fourth):
    items,vs,*_=fourth;meta={'store':'模拟店','period':'模拟期','sales_cost':'10000000'}
    before=financial_panel(items,meta);m=audit_model(items,vs,meta);assert m['stats']['商品总条数']==60 and m['stats']['供货商待确认']==25
    assert m['stats']['已复盘']==0 and m['stats']['未复盘']==60 and m['stats']['疑似A换B对数']==900
    assert m['stats']['净差异']==sum((x['差异成本'] for x in m['rows'] if x['_status']=='zbf'),0)
    rows=filtered_rows(m);blob=audit_excel(m,rows);w=openpyxl.load_workbook(io.BytesIO(blob),data_only=False);s=w['卓不凡专项审计']
    assert tuple(c.value for c in s[1])==HEADERS and s.max_column==16 and s.max_row==61
    assert all(s.cell(r,4).data_type=='s' and s.cell(r,4).value.startswith('099') for r in range(2,62))
    assert len(filtered_rows(m,'归属待确认'))==25 and len(filtered_rows(m,include_pending=True))==85
    x=next(x for x in items if m['classes'][x['记录ID']]['status']=='zbf');b=store.create(items,[],'simulated-proof')
    loaded,_,state,rev=store.load(b);state['vendors']=vs
    state['meta'].setdefault('zbf_notes',{})[x['记录ID']]='模拟核对说明'
    updated=patch_items(loaded,{x['记录ID']:{'核实结论':'确认并附单据','相关单号':'SIM-PROOF-001'}});store.save(b,updated,state,rev)
    reread,_,saved,_=store.load(b);row=next(r for r in audit_model(reread,vs,saved['meta'])['rows'] if r['_id']==x['记录ID'])
    assert row['核查结论']=='确认并附单据；模拟核对说明' and row['凭证编号']=='SIM-PROOF-001'
    assert financial_panel(items,meta)==before

def test_shared_print_policy_and_company_scope(fourth):
    items,vs,*_=fourth;meta={'store':'模拟店','period':'模拟期','sales_cost':'10000000'}
    a,stats=select_field_items(items,vs,meta);b,_=select_field_items(items,vs,meta,include_zbf=True);c,_=select_field_items(items,vs,meta,only_zbf=True);d,_=select_field_items(items,vs,meta,include_pending=False)
    assert (len(a),len(b),len(c),len(d))==(390,450,60,365) and stats=={'excluded_zbf':60,'pending':25}
    assert [(x['大类'],x['中类'],x['序号']) for x in a]==sorted((x['大类'],x['中类'],x['序号']) for x in a)
    route=['模拟零食','模拟日用','模拟饮料'];assert print_order(a,'category',route)[0]['大类']=='模拟零食'
    assert [x['序号'] for x in print_order(a,'sequence')]==sorted(x['序号'] for x in a)
    for x in items:x['复盘实数']=x['系统数']-x['原始调整'];x['单位说明']='模拟单位核对'
    meta.update(both_files=True,coverage=True,evidence=True)
    blob=create_company_xls(items,meta,vs);s=xlrd.open_workbook(file_contents=blob).sheet_by_index(0)
    assert s.nrows==451 and s.ncols==3 and s.row_values(0)==['商品编码','商品条码','数量']
    assert {s.cell_value(r,1) for r in range(1,451)}=={x['商品条码'] for x in items}
    assert len(select_field_items(items,vs,meta)[0])==0

def test_414_compact_pdf_and_immutable_legacy_reprint(store,fourth):
    from pypdf import PdfReader
    items,vs,*_=fourth;items=print_order(items[:414]);meta={'store':'模拟店','period':'模拟期'}
    blob,pages=make_pdf(items,meta,'SIM-BATCH',hints={x['记录ID']:{'related':'禁止显示A换B串码','group':'SIM-GROUP'} for x in items})
    reader=PdfReader(io.BytesIO(blob));text=''.join(p.extract_text() for p in reader.pages)
    assert pages==len(reader.pages)<=30 and all(x['商品条码'] in text for x in items)
    assert not any(word in text for word in ('A换B','串码','疑似','算法'))
    assert all('related' not in r and 'group' not in r for r in snapshot_rows(items))
    b=store.create(items,[],'simulated-legacy');rev=store.load(b)[3]
    # 旧PDF即使使用不同版式，重印仍必须逐字节复用，不能重渲染。
    snap,old=generate_print(store,b,items,meta,'all','category',[],rev)
    repeated,again=reprint(store,b,snap['id'],rev)
    assert again==old and repeated['parent']==snap['id'] and repeated['id']!=snap['id']
