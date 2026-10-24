"""03只负责现场单：默认待复盘、关联联排、原单永久留档。"""
import streamlit as st
from core import num,newest_diff
from workflow import print_layout
from print_manager import MODES,printable_items,make_pdf,generate_print,reprint,selection_hash

def print_workbench(db,batch,items,state,rev):
    st.subheader('03 · 现场复核单打印')
    meta=state['meta'];cats=sorted({x.get('大类') or '未分类' for x in items})
    mode=st.segmented_control('打印范围',['remaining','loss','difference'],default='remaining',format_func=MODES.get,key='field_mode_'+batch) or 'remaining'
    selected=st.multiselect('品类（默认全部）',cats,default=cats,key='field_cats_'+batch)
    with st.expander('更多打印范围与排序'):
        extra=st.selectbox('附加范围',['normal','all','new'],format_func=lambda k:'使用上方范围' if k=='normal' else MODES[k],key='field_extra_'+batch)
        sort=st.selectbox('找货顺序',['field','amount','category','source'],format_func=lambda k:{'field':'盘亏优先 · 疑似商品就近联排','amount':'按差异金额','category':'按品类/固定序号','source':'按源报表'}[k],key='field_sort_'+batch)
    effective=mode if extra=='normal' else extra
    chosen=printable_items(items,effective,selected,'category' if sort=='field' else sort)
    arranged,hints=print_layout(chosen,items,state['vendors'],meta)
    if sort=='field':chosen=arranged
    st.write(f'本次待现场查找商品：{len(chosen)}条')
    st.caption('默认仅未填写实数且仍有差异；优先盘亏，保留需现场核实的盘盈。填写实数即退出默认范围，不增加核查状态。')
    fingerprint=selection_hash(chosen,meta,effective,sort,selected)+str(rev)
    a,b=st.columns(2)
    if a.button('预览A4',disabled=not chosen):
        try:
            pdf,pages=make_pdf(chosen,meta,batch,scope=MODES[effective],hints=hints)
            st.session_state['field_preview_'+batch]=(fingerprint,pdf,pages)
        except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
    if b.button('生成并保存PDF',type='primary',disabled=not chosen):
        try:generate_print(db,batch,chosen,meta,effective,sort,selected,rev,hints)
        except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
        else:st.rerun()
    preview=st.session_state.get('field_preview_'+batch)
    if preview:
        if preview[0]==fingerprint:
            st.caption(f'当前A4预览 · {preview[2]}页 · 未留档')
            st.pdf(preview[1],height=600,alt='现场复核单A4预览')
            st.download_button('下载当前预览PDF',preview[1],'未留档现场复核单.pdf','application/pdf')
        else:st.info('复盘或范围已变化，请重新预览最新现场单。')
    with st.expander('查看本次商品清单'):
        st.dataframe([{'序号':x['序号'],'商品名称':x['商品名称'],'商品条码':x['商品条码'],'品类':x.get('大类'),
            '系统数':num(x['系统数']),'初盘数':num(x['初盘数']),'最新差异':num(newest_diff(x)),
            '找货线索':hints.get(x['记录ID'],{}).get('related','')} for x in chosen],hide_index=True,alt='待现场查找清单，不改变实数')
    archives=db.prints(batch)
    with st.expander('历史打印记录与原单重印'):
        st.caption(f'共{len(archives)}份历史记录')
        if not archives:st.info('尚无历史打印记录。');return
        byid={p['id']:p for p in archives}
        ident=st.selectbox('历史打印批次',list(byid),format_func=lambda k:f"{byid[k]['time']} · {byid[k]['count']}条 · {k}",key='field_history_'+batch)
        try:old_pdf=db.print_pdf(batch,ident)
        except ValueError as exc:st.error(str(exc));return
        st.download_button('下载历史原单PDF',old_pdf,ident+'.pdf','application/pdf')
        if st.checkbox('预览历史原单',key='field_old_preview_'+batch):st.pdf(old_pdf,height=600,alt='不随当前实数改变的历史原始PDF')
        if st.button('原单重印并登记'):
            try:reprint(db,batch,ident,rev)
            except ValueError as exc:st.error(str(exc))
            else:st.rerun()
        st.caption('重印复用原PDF字节；使用新数据打印另建记录，不覆盖历史单。')
        if st.button('按历史范围使用最新数据生成新单'):
            ids={r['source_id'] for r in byid[ident]['rows']};current=[x for x in items if x['记录ID'] in ids]
            ordered,latest_hints=print_layout(current,items,state['vendors'],meta)
            try:generate_print(db,batch,ordered,meta,'all','field',byid[ident].get('categories',[]),rev,latest_hints)
            except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
            else:st.rerun()
