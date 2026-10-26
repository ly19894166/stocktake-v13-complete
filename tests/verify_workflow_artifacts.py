"""重新读入浏览器下载的模拟XLS/PDF并验证；仅允许tests/runtime数据目录。"""
from pathlib import Path
import sys,os,json,io,hashlib,re,sqlite3
from collections import Counter,defaultdict
import xlrd
from pypdf import PdfReader
from pypdf.generic import ContentStream
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from storage import Store
from core import current_total
DATA=Path(os.environ.get('STOCKTAKE_WORKFLOW_DATA_DIR',ROOT/'tests/runtime/workflow_final_data')).resolve()
OUT=ROOT/'tests/runtime/workflow_results'
assert DATA.is_relative_to((ROOT/'tests/runtime').resolve()),'禁止读取正式库'

def database_snapshot():
    with sqlite3.connect(f'file:{DATA / "stocktake.sqlite"}?mode=ro',uri=True) as c:
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        return {t:hashlib.sha256(repr(c.execute('SELECT * FROM '+t+' ORDER BY rowid').fetchall()).encode()).hexdigest() for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}

def verify():
    s=Store(DATA)
    try:
        batches=s.list_batches();assert len(batches)==1
        batch=batches[0]['id'];items,_,state,_=s.load(batch)
        assert len(items)==450
        assert all(name.startswith('模拟') for name in state['meta']['source_files'])
        blob=(OUT/'模拟公司盘点表.xls').read_bytes();assert blob[:8]==bytes.fromhex('D0CF11E0A1B11AE1')
        book=xlrd.open_workbook(file_contents=blob);assert book.sheet_names()==['Sheet1']
        sh=book.sheet_by_index(0);assert sh.ncols==3 and sh.nrows==451
        assert sh.row_values(0)==['商品编码','商品条码','数量']
        for i,x in enumerate(items,1):
            assert sh.cell_type(i,0)==sh.cell_type(i,1)==xlrd.XL_CELL_TEXT
            assert sh.cell_type(i,2)==xlrd.XL_CELL_NUMBER
            assert sh.row_values(i)==[x['商品编码'],x['商品条码'],float(current_total(x))]
            assert x['商品条码'].startswith('099')
        assert sh.cell_value(1,2)==0
        archives=s.prints(batch);assert len(archives)>=3
        repeated=[p for p in archives if p.get('parent')];assert repeated
        for p in repeated:assert s.print_pdf(batch,p['id'])==s.print_pdf(batch,p['parent'])
        native=[p for p in archives if not p.get('parent')]
        assert len(native)>=2 and len({p['id'] for p in native})==len(native)
        # 同一真实商品只在主条码列出现一次；大填写框与联排组均核对。
        first=min(native,key=lambda p:p['time']);rows=first['rows'];ids=[r['source_id'] for r in rows]
        assert len(ids)==len(set(ids))==first['count']
        assert all(r['recount'] is None and r['difference']!=0 for r in rows)
        assert any(r['difference']>0 for r in rows) and any(r['difference']<0 for r in rows)
        raw=s.print_pdf(batch,first['id']);reader=PdfReader(io.BytesIO(raw));barcodes=[];page_of={};boxes=0;embedded=False
        for page_index,page in enumerate(reader.pages):
            assert abs(float(page.mediabox.width)-841.89)<1 and abs(float(page.mediabox.height)-595.28)<1
            for font in page['/Resources'].get('/Font',{}).values():
                obj=font.get_object();fd=obj.get('/FontDescriptor')
                if fd and '/FontFile2' in fd.get_object():embedded=True
            def visit(text,cm,tm,font,size):
                for code in re.findall(r'(?<!\d)099\d{10}(?!\d)',text):barcodes.append(code);page_of[code]=page_index
            page.extract_text(visitor_text=visit)
            for operands,operator in ContentStream(page.get_contents(),reader).operations:
                if operator==b're' and 80<=float(operands[2])<=110 and float(operands[3])>=22:boxes+=1
        assert Counter(barcodes)==Counter(r['barcode'] for r in rows)
        assert embedded and boxes==len(rows)
        groups=defaultdict(list)
        for row in rows:
            if row.get('group'):groups[row['group']].append(row['barcode'])
        assert all(len(codes)!=2 or page_of[codes[0]]==page_of[codes[1]] for codes in groups.values())
        (OUT/'验证留档现场单.pdf').write_bytes(raw)
        result={'pass':True,'simulated_only':True,'xlsx_not_misnamed':True,'true_xls_ole':True,'sheet':'Sheet1',
                'headers':['商品编码','商品条码','数量'],'rows':450,'typed_columns':['text','text','number'],
                'leading_zero_and_zero_preserved':True,'all_rows_match_latest_saved_totals':True,
                'print_rows':len(rows),'print_pages':len(reader.pages),'print_unique_records':True,
                'each_barcode_once':True,'large_blank_boxes':boxes,'embedded_chinese_font':True,
                'linked_pairs_not_split_across_pages':True,'original_reprint_byte_identical':True,'new_print_id_distinct':True}
        return result
    finally:s.close()

if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'files'
    if mode=='before':result=database_snapshot();(OUT/'restart_expected.json').write_text(json.dumps(result),encoding='utf8');print('模拟重启前快照已保存')
    elif mode=='after':
        assert database_snapshot()==json.loads((OUT/'restart_expected.json').read_text('utf8'))
        result={'pass':True,'simulated_only':True,'real_process_restart':True,'all_tables_identical':True}
        (OUT/'restart_results.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))
    else:
        result=verify();(OUT/'artifact_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))
