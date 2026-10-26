"""03统一范围、供应商归属和排序；原单重印始终复用原字节。"""
import streamlit as st
from core import num,newest_diff
from supplier_policy import effective_vendors
from print_manager import MODES,select_field_items,make_pdf,generate_print,reprint,selection_hash

def print_action(root,batch,expected_revision,kind):
    from storage import Store
    live=Store(root)
    try:
        items,_,state,rev=live.load(batch)
        if rev!=expected_revision:raise ValueError('另一窗口已更新，请刷新后重新确认打印范围。')
        ident=st.session_state.get('field_history_'+batch)
        if kind=='reprint':
            snap,_=reprint(live,batch,ident,rev)
        else:
            cats=sorted({x.get('大类') or '未分类' for x in items})
            mode=st.session_state.get('field_mode_'+batch) or 'remaining';extra=st.session_state.get('field_extra_'+batch,'normal')
            if extra!='normal':mode=extra
            policy={'mode':mode,'categories':st.session_state.get('field_cats_'+batch,cats),'sort':st.session_state.get('field_sort_v4_'+batch,'category'),
                'include_zbf':st.session_state.get('field_zbf_'+batch,False),'only_zbf':st.session_state.get('field_only_zbf_'+batch,False),'include_pending':st.session_state.get('field_pending_'+batch,True)}
            ids=None
            if kind=='new':
                old=next(p for p in live.prints(batch) if p['id']==ident);ids={r['source_id'] for r in old['rows']}
            printed={r['source_id'] for p in live.prints(batch) for r in p['rows']}
            chosen,_=select_field_items(items,effective_vendors(state),state['meta'],ids=ids,printed_ids=printed,**policy)
            snap,_=generate_print(live,batch,chosen,state['meta'],mode,policy['sort'],policy['categories'],rev,policy=policy)
        st.session_state['field_result_'+batch]=(True,f"打印记录已保存 · {snap['count']}条 · {snap['id']}")
    except (ValueError,RuntimeError,OSError,StopIteration) as exc:st.session_state['field_result_'+batch]=(False,'未保存打印记录：'+str(exc))
    finally:live.close()

def print_workbench(db,batch,items,state,rev):
    st.subheader('03 · 现场复核单打印')
    result=st.session_state.get('field_result_'+batch)
    if result:(st.success if result[0] else st.error)(result[1])
    meta=state['meta'];vendors=effective_vendors(state);cats=sorted({x.get('大类') or '未分类' for x in items})
    mode=st.segmented_control('打印范围',['remaining','loss','difference'],default='remaining',format_func=MODES.get,key='field_mode_'+batch) or 'remaining'
    selected=st.multiselect('品类（默认全部）',cats,default=cats,key='field_cats_'+batch)
    a,b,c=st.columns(3)
    include=a.checkbox('包含卓不凡商品',value=False,key='field_zbf_'+batch)
    only=b.checkbox('仅打印卓不凡',value=False,key='field_only_zbf_'+batch)
    pending=c.checkbox('打印供货商待确认商品',value=True,key='field_pending_'+batch)
    sort=st.selectbox('找货顺序',['category','sequence','amount'],format_func=lambda k:{'category':'品类找货（默认）','sequence':'原始序号','amount':'差异金额优先'}[k],key='field_sort_v4_'+batch)
    with st.expander('更多打印范围与现场路线'):
        extra=st.selectbox('附加范围',['normal','all','new'],format_func=lambda k:'使用上方范围' if k=='normal' else MODES[k],key='field_extra_'+batch)
        route=st.multiselect('门店确认的品类路线（按选择顺序）',cats,default=[v for v in meta.get('print_route',[]) if v in cats],key='field_route_'+batch)
        st.caption('未设置路线时仅按商品档案大类、中类、原始序号排列；不推测货架位置。')
        if st.button('保存品类路线'):
            meta['print_route']=route
            try:db.save(batch,items,state,rev,'本机店长','现场品类路线确认')
            except ValueError as exc:st.error(str(exc))
            else:st.rerun()
    effective=mode if extra=='normal' else extra
    printed={r['source_id'] for p in db.prints(batch) for r in p['rows']}
    policy={'mode':effective,'categories':selected,'sort':sort,'include_zbf':include,'only_zbf':only,'include_pending':pending,'printed_ids':printed}
    chosen,stats=select_field_items(items,vendors,meta,**policy)
    st.write(f"本次待复核：{len(chosen)}条 · 其中已排除卓不凡：{stats['excluded_zbf']}条 · 供货商待确认：{stats['pending']}条")
    st.caption('默认未填实数且差异非零，排除已确认卓不凡；归属待确认默认保留，可选择不打印。填写实数即退出默认范围。')
    fingerprint=selection_hash(chosen,meta,effective,sort,[selected,include,only,pending])+str(rev)
    stored_policy={k:v for k,v in policy.items() if k!='printed_ids'}
    a,b=st.columns(2)
    if a.button('预览A4',disabled=not chosen):
        try:
            pdf,pages=make_pdf(chosen,meta,batch,scope=MODES[effective])
            st.session_state['field_preview_'+batch]=(fingerprint,pdf,pages)
        except (ValueError,RuntimeError,OSError) as exc:st.error(str(exc))
    b.button('生成并保存PDF',type='primary',disabled=not chosen,on_click=print_action,args=(db.root,batch,rev,'generate'))
    preview=st.session_state.get('field_preview_'+batch)
    if preview:
        if preview[0]==fingerprint:
            st.caption(f'当前A4预览 · {preview[2]}页 · 未留档');st.pdf(preview[1],height=600,alt='紧凑现场复核单A4预览')
            st.download_button('下载当前预览PDF',preview[1],'未留档现场复核单.pdf','application/pdf')
        else:st.info('复盘或筛选已变化，请重新预览最新现场单。')
    with st.expander('查看本次商品清单'):
        st.dataframe([{'序号':x['序号'],'商品名称':x['商品名称'],'商品条码':x['商品条码'],'品类':x.get('大类'),'中类':x.get('中类'),
            '系统数':num(x['系统数']),'初盘数':num(x['初盘数']),'最新差异':num(newest_diff(x))} for x in chosen],hide_index=True,alt='本次统一筛选和排序后的现场数货清单')
    archives=db.prints(batch)
    with st.expander('历史打印记录与原单重印'):
        st.caption(f'共{len(archives)}份历史记录')
        if not archives:st.info('尚无历史打印记录。');return
        byid={p['id']:p for p in archives}
        ident=st.selectbox('历史打印批次',list(byid),format_func=lambda k:f"{byid[k]['time']} · {byid[k]['count']}条 · {k}",key='field_history_'+batch)
        try:old_pdf=db.print_pdf(batch,ident)
        except ValueError as exc:st.error(str(exc));return
        st.download_button('下载历史原单PDF',old_pdf,ident+'.pdf','application/pdf')
        if st.checkbox('预览历史原单',key='field_old_preview_'+batch):st.pdf(old_pdf,height=600,alt='保存时的历史原单，内容不随新筛选改变')
        st.button('原单重印并登记',on_click=print_action,args=(db.root,batch,rev,'reprint'))
        ids={r['source_id'] for r in byid[ident]['rows']}
        current,_=select_field_items(items,vendors,meta,ids=ids,**policy)
        st.caption(f'新数据新单遵循上方范围、供应商选项和排序，当前历史范围符合{len(current)}条；旧PDF永不覆盖。')
        st.button('按历史范围使用最新数据生成新单',disabled=not current,on_click=print_action,args=(db.root,batch,rev,'new'))
