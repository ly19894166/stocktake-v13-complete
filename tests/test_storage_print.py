import copy
import hashlib
import io
import json
import sqlite3
from decimal import Decimal as D
import zipfile
import pytest
from core import patch_items,newest_diff
from storage import Store
from print_manager import printable_items,make_pdf,generate_print,reprint,selection_hash

def test_reopen_restores_without_upload_and_audits_zero(store,batch):
    items,notes,state,rev=store.load(batch)
    updated=patch_items(items,{items[0]['记录ID']:{'复盘实数':0,'备注':'实物为零'}})
    state['meta'].update(sales_cost='8000000',coverage=True)
    rev=store.save(batch,updated,state,rev,'测试操作员')
    root=store.root;store.close()
    reopened=Store(root)
    try:
        rows,_,s,v=reopened.load(batch)
        assert rows[0]['复盘实数']==0 and rows[0]['备注']=='实物为零'
        assert s['meta']['coverage'] is True and s['meta']['sales_cost']=='8000000'
        assert len(reopened.list_batches())==1
        assert reopened.history(batch)[0]['操作人']=='测试操作员'
        with pytest.raises(ValueError):reopened.save(batch,items,state,0,'另一窗口')
        # fixture关闭原连接需要可重复close；sqlite close天然幂等。
    finally:reopened.close()

def test_batch_separation_and_same_sources_dedup(store,sample,batch):
    same=store.create(*sample[:3],'测试门店','2026第三季度',sample[3])
    other=store.create(*sample[:3],'另一门店','2026第三季度',sample[3])
    later=store.create(*sample[:3],'测试门店','2026第四季度',sample[3])
    # 本轮明确要求相同原件恢复原批次，不以手填店名/季度复制批次。
    assert same==other==later==batch

def test_print_filter_latest_requirement_excludes_zero(items):
    initial=[x for x in items if newest_diff(x)==0]
    assert initial
    count=sum(newest_diff(x)!=0 for x in items)
    assert len(printable_items(items))==count
    assert all(x not in printable_items(items) for x in initial)
    assert len(printable_items(items,'all'))==len(items)
    x=items[0];x['备注']='已知位置'
    assert len(printable_items(items))==count
    x['复盘实数']=D(0)
    assert x not in printable_items(items)
    assert len(printable_items(items))==count-1
    x['复盘实数']=None
    assert len(printable_items(items))==count
    category=items[0]['大类'] or '未分类'
    assert all((x['大类'] or '未分类')==category for x in printable_items(items,categories=[category]))
    assert printable_items(items,categories=[])==[]

def test_pdf_archive_reprint_immutable_backup_and_incremental(store,batch,tmp_path):
    items,notes,state,rev=store.load(batch)
    group=items[:20]
    info,pdf=generate_print(store,batch,group,state['meta'],'remaining','category',['测试'],rev)
    assert pdf.startswith(b'%PDF-') and info['pages']>=1
    printed={x['记录ID'] for x in group}
    assert len(printable_items(items,'new',printed_ids=printed))==sum(x['记录ID'] not in printed and newest_diff(x)!=0 for x in items)
    # 打印不会把任何商品标成已复盘。
    assert all(x['复盘实数'] is None for x in store.load(batch)[0])
    changed=patch_items(items,{group[0]['记录ID']:{'复盘实数':0}})
    newrev=store.save(batch,changed,state,rev,'店长')
    again,original=reprint(store,batch,info['id'],newrev)
    assert again['parent']==info['id'] and again['id']!=info['id']
    assert original==pdf
    assert store.print_pdf(batch,info['id'])==store.print_pdf(batch,again['id'])
    assert again['rows']==info['rows']
    assert hashlib.sha256(pdf).hexdigest()==info['pdf_sha256']
    with pytest.raises(ValueError):generate_print(store,batch,group,state['meta'],'remaining','category',[],rev)
    archive=zipfile.ZipFile(io.BytesIO(store.audit_zip(batch)))
    assert len([p for p in archive.namelist() if p.startswith('原件/')])==2
    assert len([p for p in archive.namelist() if p.endswith('.pdf')])==2
    backup=tmp_path/'restored';backup.mkdir();(backup/'stocktake.sqlite').write_bytes(store.backup())
    restored=Store(backup)
    try:
        assert restored.load(batch)[0][0]['复盘实数']==0
        assert restored.print_pdf(batch,again['id'])==pdf
        assert len(restored.history(batch))==1
    finally:restored.close()

def test_preview_hash_changes_on_recount_and_empty_no_archive(store,batch):
    items,_,state,rev=store.load(batch)
    before=selection_hash(items[:2],state['meta'],'remaining','category',[])
    items[0]['复盘实数']=D(0)
    after=selection_hash(items[:2],state['meta'],'remaining','category',[])
    assert before!=after
    with pytest.raises(ValueError):generate_print(store,batch,[],state['meta'],'remaining','category',[],rev)
    assert not store.prints(batch)

def test_corrupt_pdf_detected(store,batch):
    items,_,state,rev=store.load(batch)
    info,pdf=generate_print(store,batch,items[:1],state['meta'],'remaining','category',[],rev)
    with store.db:store.db.execute('UPDATE prints SET pdf=? WHERE id=?',(b'corrupt',info['id']))
    with pytest.raises(ValueError):store.print_pdf(batch,info['id'])
