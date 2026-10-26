"""02本机母版审批报表。点击下载时重新读取完整批次，不使用01筛选数据。"""
import pandas as pd
import json
import streamlit as st
from storage import Store
from approval_reporting import template_path,read_template,save_template,generate,split_items,row_values,COMMON,FRESH
from reporting import financial_panel

def latest_report(root,batch):
    path=template_path(root);blob=path.read_bytes();sidecar=path.with_suffix('.style.json')
    profile=json.loads(sidecar.read_text('utf8')) if sidecar.exists() else None;db=Store(root)
    try:
        with db.db:
            db.db.execute('BEGIN');items,_,state,rev=db.load(batch)
            return generate(items,state['meta'],blob,rev,profile)
    finally:db.close()

def approval_page(root,batch):
    st.subheader('02 · 领导审批报表')
    st.caption('常规商品、鲜食两表。仅使用完整批次最新已保存记录；未复盘差异标记暂估，缺成本和原因不编造。返回01可继续处理未确认草稿。')
    path=template_path(root)
    with st.expander('本机季度母版设置',expanded=not path.exists()):
        upload=st.file_uploader('季度盘点盈亏母版（只保存在本机）',type=['xls'],key='approval_template_upload')
        if upload and st.button('核实并保存审批母版'):
            try:save_template(root,upload.getvalue(),capture=True);st.success('审批母版已在本机保存');st.rerun()
            except Exception as exc:st.error(str(exc))
        st.caption('原母版不会进入公开源码；仅继承表头、格式和完整条码核对后的分表依据，不复制旧盘点值、原因或签批。')
    if not path.exists():st.info('首次使用请在上方设置本机原始季度母版。');return
    try:book=read_template(path.read_bytes())
    except Exception as exc:st.error('母版无法使用：'+str(exc));return
    db=Store(root)
    try:items,_,state,rev=db.load(batch)
    finally:db.close()
    groups,uncertain=split_items(items,book);panel=financial_panel(items,state['meta'])
    st.info(f"全店{len(items)}条｜常规商品{len(groups['常规商品'])}条｜鲜食{len(groups['鲜食'])}条｜未复盘{panel['remaining_rows']}条。{panel['status']}，本报表未审批。")
    if uncertain:st.warning(f'{len(uncertain)}条分表依据待确认，保留在常规表并逐条注明，不隐藏或遗漏。')
    st.caption(f"整店盘盈{panel['gain'] or '待核实'}元｜盘亏{panel['loss'] or '待核实'}元｜净差异{panel['net'] or '待核实'}元｜2‰允许净损耗{panel['allowance'] or '待填写'}元｜预览版本{rev}")
    # Streamlit data callable在每次实际下载时执行，重新开只读快照，避免缓存旧revision。
    st.download_button('下载领导审批报表（常规商品＋鲜食）.xls',data=lambda:latest_report(root,batch)[0],file_name='领导审批报表_当前核对资料_未审批.xls',mime='application/vnd.ms-excel',on_click='ignore',type='primary')
    for name,headers in [('常规商品',COMMON),('鲜食',FRESH)]:
        with st.expander(name+'审批表预览'):
            data=[[str(v) if v is not None else '' for v in row_values(x,name=='鲜食',uncertain.get(x['记录ID'],''))] for x in groups[name]]
            st.dataframe(pd.DataFrame(data,columns=headers),hide_index=True,alt=name+'审批表全量预览')
