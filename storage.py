"""原件、业务状态、修改日志、PDF与打印快照均在同一SQLite事务体系中。"""
from __future__ import annotations
import hashlib
import io
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from core import (json_bytes, hydrate, patch_items, EDIT_FIELDS, valid_count,
                  decimal_value, default_vendors)

def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')

def dumps(v):
    return json_bytes(v).decode('utf8')

class Store:
    def __init__(self, root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.root/'stocktake.sqlite',timeout=20)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS batches(
            id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, store TEXT NOT NULL,
            period TEXT NOT NULL, created TEXT NOT NULL, original TEXT NOT NULL,
            notes TEXT NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
            UNIQUE(fingerprint,store,period));
        CREATE TABLE IF NOT EXISTS sources(
            batch TEXT NOT NULL REFERENCES batches(id), role TEXT NOT NULL,
            filename TEXT NOT NULL, sha256 TEXT NOT NULL, content BLOB NOT NULL,
            PRIMARY KEY(batch,role));
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY, batch TEXT NOT NULL REFERENCES batches(id),
            at TEXT NOT NULL, actor TEXT NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS prints(
            id TEXT PRIMARY KEY, batch TEXT NOT NULL REFERENCES batches(id),
            at TEXT NOT NULL, parent TEXT REFERENCES prints(id),
            snapshot TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL,
            pdf BLOB NOT NULL, pdf_sha256 TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS item_events(
            id INTEGER PRIMARY KEY, batch TEXT NOT NULL REFERENCES batches(id),
            record_id TEXT NOT NULL, barcode TEXT NOT NULL, at TEXT NOT NULL,
            actor TEXT NOT NULL, source TEXT NOT NULL, old_json TEXT NOT NULL,new_json TEXT NOT NULL,
            request_id TEXT NOT NULL, undone INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS requests(
            batch TEXT NOT NULL,request_id TEXT NOT NULL,revision INTEGER NOT NULL,PRIMARY KEY(batch,request_id));
        CREATE TABLE IF NOT EXISTS evidence_files(
            id TEXT PRIMARY KEY,batch TEXT NOT NULL REFERENCES batches(id),kind TEXT NOT NULL,
            store_label TEXT NOT NULL,filename TEXT NOT NULL,sha256 TEXT NOT NULL,
            content BLOB NOT NULL,rows_json TEXT NOT NULL,created TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS item_events_batch ON item_events(batch,id);
        CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        PRAGMA user_version=14;
        ''')

    def close(self):self.db.close()

    def preference(self,key):
        r=self.db.execute('SELECT value FROM preferences WHERE key=?',(key,)).fetchone()
        return r[0] if r else None

    def set_preference(self,key,value):
        if self.preference(key)==value:return
        with self.db:self.db.execute('INSERT INTO preferences VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,value))

    def list_batches(self):
        return [dict(zip(('id','store','period','created','revision'),r)) for r in
                self.db.execute('SELECT id,store,period,created,revision FROM batches ORDER BY created DESC,id DESC')]

    def create(self, items, notes, fingerprint, store='', period='', sources=None):
        sources=sources or {}
        # 同一原件重复上传优先恢复已经保存过复盘的批次，保留所有历史重复批次。
        hashes=sorted(hashlib.sha256(blob).hexdigest() for _,blob in sources.values())
        if hashes:
            matches=[]
            for oldid,rev,created in self.db.execute('SELECT id,revision,created FROM batches'):
                oldhashes=sorted(r[0] for r in self.db.execute('SELECT sha256 FROM sources WHERE batch=?',(oldid,)))
                if oldhashes==hashes:matches.append((rev,created,oldid))
            if matches:return sorted(matches,key=lambda x:(-x[0],x[1]))[0][2]
        store,period=store.strip() or '门店未识别',period.strip() or '期间未识别'
        if len(items)!=len({x['记录ID'] for x in items}):raise ValueError('同一原件记录重复，不能创建批次')
        existing=self.db.execute('SELECT id FROM batches WHERE fingerprint=? AND store=? AND period=?',
                                 (fingerprint,store,period)).fetchone()
        if existing:return existing[0]
        ident='B'+uuid.uuid4().hex[:16]
        state={'edits':{},'meta':{'store':store,'period':period,'both_files':True,
               'coverage':False,'evidence':False,'sales_cost':None,'first_import_at':now(),
               'source_files':[name for name,_ in sources.values()], 'parameters':{},'main_suppliers':{},
               'pair_proofs':{}},'vendors':default_vendors()}
        with self.db:
            self.db.execute('INSERT INTO batches VALUES(?,?,?,?,?,?,?,?,?)',
                (ident,fingerprint,store,period,now(),dumps(items),dumps(notes),dumps(state),0))
            for role,(name,blob) in sources.items():
                self.db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',
                    (ident,role,Path(name).name,hashlib.sha256(blob).hexdigest(),blob))
        return ident

    def load(self, batch):
        row=self.db.execute('SELECT original,notes,state,revision FROM batches WHERE id=?',(batch,)).fetchone()
        if row is None:raise ValueError('批次不存在')
        items=hydrate(json.loads(row[0]));state=json.loads(row[2])
        items=patch_items(items,state['edits'])
        state['meta'].setdefault('parameters',{})
        state['meta'].setdefault('main_suppliers',{})
        state['meta'].setdefault('pair_proofs',{})
        # 旧批次只在内存补默认值，不改原始行，不清空旧复盘或日志。
        state['meta'].setdefault('sales_amount',None)
        state['meta'].setdefault('report',{})
        info=self.db.execute('SELECT created FROM batches WHERE id=?',(batch,)).fetchone()
        state['meta'].setdefault('first_import_at',info[0])
        state['meta'].setdefault('source_files',[r[0] for r in self.db.execute('SELECT filename FROM sources WHERE batch=?',(batch,))])
        return items,json.loads(row[1]),state,row[3]

    def save(self, batch, items, state, revision, actor='本机店长', source='工作台编辑', request_id=None):
        actor=actor.strip() or '本机店长'
        request_id=request_id or uuid.uuid4().hex
        # 只保存允许编辑的字段；来源与固定序号不接受客户端修改。
        payload={'edits':{x['记录ID']:{k:x.get(k) for k in EDIT_FIELDS} for x in items},
                 'meta':state['meta'],'vendors':state['vendors']}
        for x in items:
            for k in ('复盘实数','零售价','成本价','包装系数'):
                if x.get(k) is not None and not valid_count(x[k]):raise ValueError(k+'无效，未保存')
            if x.get('核实结论','') not in ('','已排除','无需调整','确认并附单据'):
                raise ValueError('核实结论无效')
        cost=payload['meta'].get('sales_cost')
        if cost is not None and (decimal_value(cost) is None or decimal_value(cost)<0):
            raise ValueError('销售成本须为非负有限数字')
        amount=payload['meta'].get('sales_amount')
        if amount is not None and (decimal_value(amount) is None or decimal_value(amount)<0):
            raise ValueError('实际销售金额须为非负有限数字')
        text=dumps(payload)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            seen=self.db.execute('SELECT revision FROM requests WHERE batch=? AND request_id=?',(batch,request_id)).fetchone()
            if seen:return seen[0]
            row=self.db.execute('SELECT state,revision,original FROM batches WHERE id=?',(batch,)).fetchone()
            if row is None:raise ValueError('批次不存在')
            if row[1]!=revision:raise ValueError('另一窗口已修改本批次，请点击“刷新本批次”后重试')
            if {x['记录ID'] for x in json.loads(row[2])}!=set(payload['edits']):
                raise ValueError('商品集合与原始批次不一致')
            if json.loads(row[0])==json.loads(text):return revision
            oldpayload=json.loads(row[0]);original=hydrate(json.loads(row[2]))
            previous=patch_items(original,oldpayload.get('edits',{}));byid={x['记录ID']:x for x in previous}
            for x in items:
                olditem=byid[x['记录ID']]
                changed=[k for k in EDIT_FIELDS if dumps(olditem.get(k))!=dumps(x.get(k))]
                if changed:
                    self.db.execute('INSERT INTO item_events(batch,record_id,barcode,at,actor,source,old_json,new_json,request_id) VALUES(?,?,?,?,?,?,?,?,?)',
                        (batch,x['记录ID'],x['商品条码'],now(),actor,source,
                         dumps({k:olditem.get(k) for k in changed}),dumps({k:x.get(k) for k in changed}),request_id))
            self.db.execute('INSERT INTO events(batch,at,actor,before_json,after_json) VALUES(?,?,?,?,?)',
                            (batch,now(),actor.strip(),row[0],text))
            self.db.execute('UPDATE batches SET state=?,revision=revision+1 WHERE id=?',(text,batch))
            self.db.execute('INSERT INTO requests VALUES(?,?,?)',(batch,request_id,revision+1))
        return revision+1

    def item_history(self,batch,record_id=None):
        sql='SELECT id,record_id,barcode,at,actor,source,old_json,new_json,request_id,undone FROM item_events WHERE batch=?'
        args=[batch]
        if record_id:sql+=' AND record_id=?';args.append(record_id)
        return [{'id':r[0],'记录ID':r[1],'商品条码':r[2],'北京时间':r[3],'操作人':r[4],'修改来源':r[5],
                 '旧值':json.loads(r[6]),'新值':json.loads(r[7]),'请求':r[8],'已撤销':bool(r[9])}
                for r in self.db.execute(sql+' ORDER BY id DESC',args)]

    def undo_last(self,batch,revision,actor='本机店长'):
        events=[x for x in self.item_history(batch) if not x['已撤销'] and x['修改来源']!='撤销输入']
        if not events:raise ValueError('没有可撤销的本次升级后输入；旧版完整保存记录仍留档')
        last=events[0];group=[e for e in events if e['请求']==last['请求']]
        items,_,state,rev=self.load(batch)
        if rev!=revision:raise ValueError('版本已更新，请刷新')
        mapping={x['记录ID']:x for x in items};patches={}
        for event in group:
            x=mapping[event['记录ID']]
            for k,value in event['新值'].items():
                if str(x.get(k))!=str(value):raise ValueError('该字段已有后续修改，不能覆盖，请查看轨迹')
            patches[event['记录ID']]=event['旧值']
        result=patch_items(items,patches)
        newrev=self.save(batch,result,state,revision,actor,'撤销输入')
        with self.db:
            self.db.executemany('UPDATE item_events SET undone=1 WHERE id=?',[(e['id'],) for e in group])
        return newrev

    def add_evidence(self,batch,kind,label,name,blob,rows):
        sha=hashlib.sha256(blob).hexdigest()
        found=self.db.execute('SELECT id FROM evidence_files WHERE batch=? AND kind=? AND store_label=? AND sha256=?',
                             (batch,kind,label,sha)).fetchone()
        if found:return found[0]
        ident='E'+uuid.uuid4().hex[:16]
        with self.db:self.db.execute('INSERT INTO evidence_files VALUES(?,?,?,?,?,?,?,?,?)',
              (ident,batch,kind,label,Path(name).name,sha,blob,dumps(rows),now()))
        return ident

    def evidence(self,batch):
        return [{'id':r[0],'类型':r[1],'门店':r[2],'文件':r[3],'SHA256':r[4],
                 'rows':json.loads(r[5]),'导入时间':r[6]} for r in self.db.execute(
            'SELECT id,kind,store_label,filename,sha256,rows_json,created FROM evidence_files WHERE batch=? ORDER BY created DESC',(batch,))]

    def history(self,batch):
        return [{'序号':r[0],'北京时间':r[1],'操作人':r[2],
                 '保存前':json.loads(r[3]),'保存后':json.loads(r[4])} for r in self.db.execute(
            'SELECT id,at,actor,before_json,after_json FROM events WHERE batch=? ORDER BY id',(batch,))]

    def prints(self,batch):
        return [json.loads(r[0]) for r in self.db.execute('SELECT snapshot FROM prints WHERE batch=? ORDER BY at DESC,rowid DESC',(batch,))]

    def print_pdf(self,batch,ident):
        r=self.db.execute('SELECT pdf,pdf_sha256,snapshot,snapshot_sha256 FROM prints WHERE batch=? AND id=?',(batch,ident)).fetchone()
        if r is None:raise ValueError('历史打印批次不存在')
        if hashlib.sha256(r[0]).hexdigest()!=r[1] or hashlib.sha256(r[2].encode()).hexdigest()!=r[3]:
            raise ValueError('历史打印快照或PDF哈希不符，停止使用')
        return r[0]

    def add_print(self,batch,snapshot,pdf,revision):
        text=dumps(snapshot)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            current=self.db.execute('SELECT revision FROM batches WHERE id=?',(batch,)).fetchone()
            if current is None or current[0]!=revision:
                raise ValueError('复盘数据已变化，请刷新后重新生成打印单')
            self.db.execute('INSERT INTO prints VALUES(?,?,?,?,?,?,?,?)',
                (snapshot['id'],batch,snapshot['time'],snapshot.get('parent'),text,
                 hashlib.sha256(text.encode()).hexdigest(),pdf,hashlib.sha256(pdf).hexdigest()))

    def backup(self):
        # sqlite backup API包含WAL已提交数据，备份文件可直接替换恢复。
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'stocktake.sqlite'
            dest=sqlite3.connect(path)
            try:self.db.backup(dest)
            finally:dest.close()
            return path.read_bytes()

    def audit_zip(self,batch):
        import zipfile
        items,notes,state,revision=self.load(batch)
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('业务状态.json',dumps({'items':items,'notes':notes,'state':state,'revision':revision}))
            z.writestr('修改日志.json',dumps(self.history(batch)))
            z.writestr('逐商品修改轨迹.json',dumps(self.item_history(batch)))
            z.writestr('可选证据目录.json',dumps(self.evidence(batch)))
            for ident,filename,sha,blob in self.db.execute('SELECT id,filename,sha256,content FROM evidence_files WHERE batch=?',(batch,)):
                if hashlib.sha256(blob).hexdigest()!=sha:raise ValueError('证据原件哈希校验失败')
                z.writestr('可选证据/'+ident+'_'+filename,blob)
            prints=self.prints(batch);z.writestr('打印历史.json',dumps(prints))
            for p in prints:z.writestr('打印批次/'+p['id']+'.pdf',self.print_pdf(batch,p['id']))
            for role,name,sha,blob in self.db.execute('SELECT role,filename,sha256,content FROM sources WHERE batch=?',(batch,)):
                if hashlib.sha256(blob).hexdigest()!=sha:raise ValueError('原件哈希校验失败')
                z.writestr('原件/'+role+'_'+name,blob)
        return out.getvalue()
