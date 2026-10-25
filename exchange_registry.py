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
    import streamlit as st
    pane=st.expander('可换货商品数据库（本机）',on_change='rerun')
    if not pane.open:return
    with pane:
        st.caption('完整条码精确加入；双方启用且同一经确认的换货组才可提示A换B。独立于03打印排除规则。资格按批次首次导入日生效；卓不凡资格由本机供应商目录自动派生。')
        records=db.exchange_list();bybc={r['商品条码']:r for r in records}
        st.dataframe([{k:r[k] for k in HEADERS} for r in records],hide_index=True,alt='本机可换货商品档案，非公司上传表')
        key='exchange_barcode_'+batch
        bc=st.text_input('输入完整条码精确查找',key=key).strip();matches=[x for x in items if x['商品条码']==bc]
        if bc and len(matches)!=1:st.warning('条码必须在当前批次唯一匹配，未匹配时不能加入。')
        if len(matches)==1:
            x=matches[0];old=bybc.get(bc,{})
            st.write(x['商品名称']+' · 商品编码 '+x['商品编码'])
            token=batch+'_'+bc
            def save_one():
                from storage import Store
                live=Store(db.root)
                try:
                    fresh,_,_,_=live.load(batch)
                    r={'商品条码':bc,'商品编码':x['商品编码'],'商品名称':x['商品名称'],'供应商':st.session_state['exchange_supplier_'+token],
                       '换货资格来源':'人工加入','换货组':st.session_state['exchange_group_'+token],'是否启用':st.session_state['exchange_enabled_'+token],
                       '生效日期':st.session_state['exchange_date_'+token].isoformat(),'备注及依据':st.session_state['exchange_reason_'+token],'_revision':old.get('_revision',0)}
                    live.save_exchange([r],fresh);st.session_state['exchange_result_'+batch]=(True,'可换货档案已保存')
                except ValueError as exc:st.session_state['exchange_result_'+batch]=(False,str(exc))
                finally:live.close()
            with st.form('exchange_one_'+token):
                st.text_input('经核实的供应商',value=old.get('供应商',''),key='exchange_supplier_'+token)
                st.text_input('经确认的换货组',value=old.get('换货组',''),key='exchange_group_'+token)
                st.checkbox('启用换货资格',value=old.get('是否启用',True),key='exchange_enabled_'+token)
                st.date_input('生效日期',value=date.fromisoformat(old.get('生效日期',state['meta']['first_import_at'][:10])),key='exchange_date_'+token)
                st.text_input('备注及依据',value=old.get('备注及依据',''),key='exchange_reason_'+token)
                st.form_submit_button('保存可换货档案',on_click=save_one)
        upload=st.file_uploader('批量导入可换货商品Excel（九列）',type=['xls','xlsx'],key='exchange_upload_'+batch)
        st.caption('九列：'+'｜'.join(HEADERS)+'。资格来源填“人工加入”，是否启用填“是/否”；仅接受当前批次完整身份，任一行不合法则全部不保存。')
        if upload:
            try:
                staged=parse_registry(upload.getvalue(),upload.name,items,records)
                st.caption(f'校验通过：{len(staged)}条，保存前未改变资格。')
                def save_bulk():
                    from storage import Store
                    live=Store(db.root)
                    try:
                        fresh,_,_,_=live.load(batch);live.save_exchange(staged,fresh);st.session_state['exchange_result_'+batch]=(True,'批量可换货档案已保存')
                    except ValueError as exc:st.session_state['exchange_result_'+batch]=(False,str(exc))
                    finally:live.close()
                st.button('保存全部可换货档案',on_click=save_bulk)
            except ValueError as exc:st.error(str(exc))
        result=st.session_state.get('exchange_result_'+batch)
        if result:(st.success if result[0] else st.error)(result[1])
        with st.expander('可换货档案修改历史'):
            st.dataframe(db.exchange_history(bc or None),hide_index=True,alt='可换货档案历次修改前后及时间')
