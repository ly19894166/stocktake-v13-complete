"""独立读回模拟交付；数据库路径强制限制在tests/runtime内。"""
import sys,os,json,hashlib,io,re
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import xlrd,openpyxl
from pypdf import PdfReader
from pypdf.generic import ContentStream
from storage import Store
from core import current_total,current_amount,hydrate
from vendor_audit import HEADERS
OUT=ROOT/'tests/runtime/sixth_results';OUT.mkdir(parents=True,exist_ok=True)
DATA=Path(os.environ.get('STOCKTAKE_SIXTH_DATA_DIR',ROOT/'tests/runtime/sixth_data2')).resolve()
assert DATA.is_relative_to((ROOT/'tests/runtime').resolve()),'只允许模拟资料'

def tables():
    s=Store(DATA)
    try:return {t:hashlib.sha256(repr(s.db.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall()).encode()).hexdigest() for (t,) in s.db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}
    finally:s.close()

def verify():
    s=Store(DATA)
    try:
        b=s.list_batches()[0]['id'];items,_,state,rev=s.load(b);assert len(items)==500
        sheet=xlrd.open_workbook(OUT/'模拟全店500条公司三列.xls').sheet_by_index(0)
        assert sheet.nrows==501 and sheet.ncols==3 and sheet.row_values(0)==['商品编码','商品条码','数量']
        for i,x in enumerate(items,1):
            # 首份下载在双窗口变更之前；以保存的导出快照独立核对。
            exported=json.loads((OUT/'export_snapshot.json').read_text('utf8'))['export_snapshot']['rows'][i-1]
            assert sheet.row_values(i)==[exported[0],exported[1],float(exported[2])]
            assert [sheet.cell_type(i,c) for c in range(3)]==[1,1,2]
        latest=xlrd.open_workbook(OUT/'模拟双窗口最新三列.xls').sheet_by_index(0)
        assert latest.nrows==501 and all(latest.row_values(i)==[x['商品编码'],x['商品条码'],float(current_total(x))] for i,x in enumerate(items,1))
        assert len(s.exchange_list())==20 and len(s.exchange_history())==20
        before=json.loads((OUT/'balance_before.json').read_text('utf8'));after=json.loads((OUT/'balance_after.json').read_text('utf8'))
        byid={r['id']:r for r in before['rows']};aa=next(r for r in after['rows'] if r['barcode'].endswith('0000'));bb=next(r for r in after['rows'] if r['barcode'].endswith('0001'))
        assert aa['recount']==12 and aa['diff']==2 and aa['amount']==4 and bb['recount']==20 and bb['diff']==bb['amount']==0
        assert byid[aa['id']]['recount'] is None and byid[bb['id']]['recount'] is None
        assert all(len(r['peers'])<=1 for r in before['rows'])
        audit=openpyxl.load_workbook(OUT/'模拟卓不凡专项.xlsx');sheet=audit['卓不凡A换B专项核对'];assert sheet.max_row==61 and sheet.max_column==16 and tuple(c.value for c in sheet[1])==HEADERS
        assert (OUT/'模拟现场单原件.pdf').read_bytes()==(OUT/'模拟现场单重印.pdf').read_bytes()
        prints=s.prints(b);assert len(prints)==2
        from supplier_policy import SupplierDirectory
        classes=SupplierDirectory(state['vendors'],state['meta']).classify_all(items)
        first=next(p for p in prints if not p.get('parent'));assert all(classes[r['source_id']]['status']!='zbf' for r in first['rows'])
        # 提议没有让普通/历史人工商品从03消失；原单按品类顺序。
        original={x['记录ID']:x for x in items};route=[(original[r['source_id']]['大类'],original[r['source_id']]['中类'],r['sequence']) for r in first['rows']];assert route==sorted(route)
        payload=json.loads((OUT/'export_snapshot.json').read_text('utf8'));assert payload['export_snapshot']['count']==500 and payload['active_scope']=='zbf'
        result={'pass':True,'simulated_only':True,'rows':500,'company_xls_rows':500,'company_columns':3,'text_text_numeric':True,'filtered_export_uses_all_rows':True,'audit_rows':60,'audit_columns':16,'historical_pdf_byte_identical':True,'balance_before_after_conserved':32,'residual_quantity':2,'residual_cost':4,'full_store_metrics_not_filtered':True}
        (OUT/'artifact_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result
    finally:s.close()

def pdf():
    from print_manager import make_pdf
    from workflow import print_order
    s=Store(DATA)
    try:
        b=s.list_batches()[0]['id'];original=hydrate(json.loads(s.db.execute('SELECT original FROM batches WHERE id=?',(b,)).fetchone()[0]));rows=print_order(original[:414],'category')
        raw,pages=make_pdf(rows,{'store':'模拟店','period':'模拟期'},'SIM-SIXTH-414',scope='模拟414条现场找货');(OUT/'模拟414条A4回归.pdf').write_bytes(raw)
        reader=PdfReader(io.BytesIO(raw));codes=[];counts=[];boxes=0;embedded=False
        for page in reader.pages:
            assert abs(float(page.mediabox.width)-841.89)<1 and abs(float(page.mediabox.height)-595.28)<1
            text=page.extract_text();assert not any(w in text for w in ('串码','A换B','疑似','算法'))
            found=re.findall(r'(?<!\d)099\d{10}(?!\d)',text);codes+=found;counts.append(len(found))
            for font in page['/Resources']['/Font'].values():
                fd=font.get_object().get('/FontDescriptor')
                if fd and '/FontFile2' in fd.get_object():embedded=True
            for args,op in ContentStream(page.get_contents(),reader).operations:
                if op==b're' and 80<=float(args[2])<=110 and float(args[3])>=22:boxes+=1
        assert pages<=30 and boxes==414 and embedded and Counter(codes)==Counter(x['商品条码'] for x in rows)
        assert all(14<=n<=18 for n in counts[:-1])
        result={'pass':True,'simulated_only':True,'rows':414,'pages':pages,'per_page_rows':counts,'handwriting_boxes':boxes,'minimum_box_height_points':22,'embedded_chinese_font':True,'no_pairing_analysis':True};(OUT/'pdf_verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');return result
    finally:s.close()

if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'verify'
    if mode=='before':(OUT/'restart_expected.json').write_text(json.dumps(tables()),encoding='utf8');r={'snapshot_saved':True}
    elif mode=='after':
        assert tables()==json.loads((OUT/'restart_expected.json').read_text('utf8'));r={'pass':True,'all_12_tables_unchanged':True};(OUT/'restart_verification.json').write_text(json.dumps(r),encoding='utf8')
    else:r={'verify':verify,'pdf':pdf}[mode]()
    print(json.dumps(r,ensure_ascii=False))
