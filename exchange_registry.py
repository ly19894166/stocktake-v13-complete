"""本机可换货商品档案：完整条码、编码核验，原子批量写入和历史留存。"""
from datetime import date
from core import as_code,load_excel

HEADERS=('商品条码','商品编码','商品名称','供应商','换货资格来源','换货组','是否启用','生效日期','备注及依据')

def validate_records(records,items):
    bybarcode={};seen=set();result=[]
    for x in items:bybarcode.setdefault(x['商品条码'],[]).append(x)
    for record in records:
        r={k:record.get(k,'') for k in HEADERS};bc=as_code(r['商品条码']);r['商品条码']=bc
        if bc in seen:raise ValueError('导入条码重复，未保存任何行')
        seen.add(bc);matches=bybarcode.get(bc,[])
        if len(matches)!=1:raise ValueError('完整条码无法唯一匹配当前商品档案：'+bc)
        x=matches[0];r['商品编码']=as_code(r['商品编码'])
        if r['商品编码']!=x['商品编码'] or str(r['商品名称']).strip()!=x['商品名称']:raise ValueError('商品编码或名称与完整条码对应身份不一致：'+bc)
        if not str(r['供应商']).strip():raise ValueError('须填写经核实的供应商')
        if r['换货资格来源']!='人工加入':raise ValueError('人工档案来源只能为人工加入；卓不凡资格由供应商目录派生')
        if r['是否启用'] not in (True,False) or not isinstance(r['是否启用'],bool):raise ValueError('启用状态须明确为是或否')
        for k in ('商品名称','供应商','换货组','备注及依据'):r[k]=str(r[k]).strip()
        if not r['换货组'] or not r['备注及依据']:raise ValueError('须填写经确认的换货组和依据')
        try:r['生效日期']=date.fromisoformat(str(r['生效日期'])[:10]).isoformat()
        except ValueError:raise ValueError('生效日期必须为YYYY-MM-DD')
        r['_revision']=record.get('_revision',0);result.append(r)
    if not result:raise ValueError('没有可保存的商品')
    return result

def parse_registry(blob,name,items,existing):
    sheets=load_excel(blob,name);records=[];versions={r['商品条码']:r['_revision'] for r in existing}
    for _,rows in sheets:
        if not rows:continue
        header=[str(v or '').strip() for v in rows[0]]
        if not set(HEADERS)<=set(header):raise ValueError('可换货Excel须包含九列完整字段：'+'、'.join(HEADERS))
        for row in rows[1:]:
            if not any(v is not None and v!='' for v in row):continue
            r={h:row[header.index(h)] if header.index(h)<len(row) else '' for h in HEADERS}
            raw=r['是否启用']
            if raw in (True,1,'是','启用','true','True'):r['是否启用']=True
            elif raw in (False,0,'否','停用','false','False'):r['是否启用']=False
            else:raise ValueError('是否启用须明确为是/否，不能留空')
            r['_revision']=versions.get(as_code(r['商品条码']),0);records.append(r)
    return validate_records(records,items)

def registry_panel(db,batch,items,state):
    """旧档案只读留存，任何启用状态都不再赋予A换B资格。"""
    import streamlit as st
    with st.expander('历史人工换货档案（只读，不赋予资格）'):
        st.caption('本次起仅已确认卓不凡可A换B。旧人工档案、启用标记和修改日志仅用于追溯，不参与资格或自动建议。')
        st.dataframe([{k:r[k] for k in HEADERS} for r in db.exchange_list()],hide_index=True,placeholder='',alt='历史人工换货档案，只读无授权作用')
        st.dataframe(db.exchange_history(),hide_index=True,placeholder='',alt='原人工档案修改历史，未删除')
