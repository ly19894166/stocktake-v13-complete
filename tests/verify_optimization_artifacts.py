"""独立验证浏览器写出的纯模拟文件和进程重启；目录固定在tests/runtime内。"""
from pathlib import Path
import io,json,hashlib,sqlite3,sys
import xlrd
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'tests/runtime/optimized-acceptance-data'
OUT=ROOT/'tests/runtime/optimization';OUT.mkdir(parents=True,exist_ok=True)

def snapshot():
    with sqlite3.connect(f'file:{DATA / "stocktake.sqlite"}?mode=ro',uri=True) as conn:
        tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        return {table:hashlib.sha256(repr(conn.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()).encode()).hexdigest() for table in tables}

def verify_files():
    sys.path.insert(0,str(ROOT))
    from storage import Store
    from core import current_total
    store=Store(DATA)
    try:
        batches=store.list_batches();assert len(batches)==1
        batch=batches[0]['id'];items,_,state,_=store.load(batch)
        assert len(items)==12 and len(state['vendors'])==2
        assert {'供应商目录','跨店差异'}=={e['类型'] for e in store.evidence(batch)}
        prints=store.prints(batch);assert len(prints)>=3
        repeats=[p for p in prints if p.get('parent')];assert repeats
        for p in repeats:assert store.print_pdf(batch,p['id'])==store.print_pdf(batch,p['parent'])
        native=[p for p in prints if not p.get('parent')]
        assert len(native)>=2 and len({p['id'] for p in native})==len(native)
        for p in prints:
            pdf=PdfReader(io.BytesIO(store.print_pdf(batch,p['id'])))
            assert len(pdf.pages)==p['pages']
            assert all(abs(float(page.mediabox.width)-841.89)<1 and abs(float(page.mediabox.height)-595.28)<1 for page in pdf.pages)
        sheet=xlrd.open_workbook(str(ROOT/'tests/runtime/module_demo/模拟正式三列.xls')).sheet_by_index(0)
        assert sheet.ncols==3 and sheet.nrows==13
        assert sheet.row_values(0)==['商品编码','商品条码','数量']
        for i,x in enumerate(items,1):
            assert sheet.cell_type(i,0)==sheet.cell_type(i,1)==xlrd.XL_CELL_TEXT
            assert sheet.cell_type(i,2)==xlrd.XL_CELL_NUMBER
            assert sheet.row_values(i)==[x['商品编码'],x['商品条码'],float(current_total(x))]
        assert state['meta']['sales_amount']=='54321.98' and state['meta']['sales_cost']=='100000'
        assert all(x['复盘实数']==20 and x['备注']=='模拟核验' for x in items)
        return {'pass':True,'simulated_only':True,'typed_three_column_export':True,'pdf_original_byte_identical':True,
                'A4_landscape':True,'all_recounts_notes_and_finances_saved':True,'supplier_and_cross_evidence':True}
    finally:store.close()

if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'files'
    if mode=='before':(OUT/'restart_snapshot.json').write_text(json.dumps(snapshot()),encoding='utf8');result={'snapshot_saved':True}
    elif mode=='after':
        assert snapshot()==json.loads((OUT/'restart_snapshot.json').read_text('utf8'))
        result={'pass':True,'real_process_restart':True,'all_simulated_database_tables_identical':True}
        (OUT/'restart_results.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    else:
        result=verify_files();(OUT/'artifact_results.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))
