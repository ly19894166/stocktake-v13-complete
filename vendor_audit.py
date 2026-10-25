"""01可A换B专项核查；只读数量金额，旧人工说明、结论和凭证继续留存。"""
import io
from decimal import Decimal as D
from collections import defaultdict
from core import num,current_total,newest_diff,current_amount,valid_count,patch_items
from supplier_policy import SupplierDirectory,effective_vendors,CANONICAL

HEADERS=('序号','品类','商品名称','商品条码','商品编码','供应商','系统数','初盘数','复盘实数','当前总数','最新差异','差异成本','疑似A换B对应商品','人工备注','核查结论','凭证编号')

def audit_model(items,vendors,meta,catalog=()):
    from intelligence import CandidateEngine
    engine=CandidateEngine(items,vendors,meta.get('parameters'),meta.get('main_suppliers'),meta=meta,exchange=catalog)
    classes={k:v['supplier'] for k,v in engine.eligibility.items()};byid=engine.items
    peers={k:engine.peers(k,limit=3,kind='swap') for k in byid}
    def verified(x):return bool(str(x.get('核实结论') or '').strip() and str(x.get('相关单号') or '').strip())
    def proof(a,b):return meta.get('pair_proofs',{}).get('|'.join(sorted((str(a['序号']),str(b['序号'])))),{})
    eligible=[x for x in items if engine.eligibility[x['记录ID']]['eligible']]
    def amounts(rows):
        values=[current_amount(x) for x in rows];known=[v for v in values if v is not None]
        return {'盘盈':sum((v for v in known if v>0),D(0)),'盘亏':sum((v for v in known if v<0),D(0)),'净差异':sum(known,D(0)),'缺失金额':len(values)-len(known)}
    rows=[]
    for x in items:
        key=x['记录ID'];c=classes[key];allowed=engine.eligibility[key]['eligible']
        if not allowed and c['status']!='pending':continue
        proofs=[proof(x,byid[k]) for k in engine.neighbors(key,'swap')]
        conclusion='；'.join(v for v in [x.get('核实结论',''),meta.get('zbf_notes',{}).get(key,''),*[p.get('说明','') for p in proofs]] if v)
        documents='；'.join(dict.fromkeys(v for v in [x.get('相关单号',''),*[p.get('单号','') for p in proofs]] if v))
        rows.append(dict(zip(HEADERS,[x['序号'],x.get('大类') or '未分类',x['商品名称'],x['商品条码'],x['商品编码'],c['name'],num(x['系统数']),num(x['初盘数']),num(x.get('复盘实数')),num(current_total(x)),num(newest_diff(x)),num(current_amount(x)),
            '；'.join(y['name']+' / '+y['barcode'] for y in peers[key]),x.get('备注',''),conclusion,documents]))|{'_id':key,'_status':c['status'],'_eligible':allowed,'_verified':verified(x)})
    edges={tuple(sorted((a,b))) for a in byid for b in engine.neighbors(a,'swap')}
    unresolved=sum(not (verified(byid[a]) and verified(byid[b]) or proof(byid[a],byid[b]).get('说明') and proof(byid[a],byid[b]).get('单号')) for a,b in edges)
    top_edges={tuple(sorted((a,p['id']))) for a,ps in peers.items() for p in ps if p['confidence']=='较强线索'}
    zbf=sum(classes[x['记录ID']]['status']=='zbf' for x in eligible)
    stats={'商品总条数':len(eligible),'卓不凡商品':zbf,'其他可换货商品':len(eligible)-zbf,'已复盘':sum(valid_count(x.get('复盘实数')) for x in eligible),'未复盘':sum(not valid_count(x.get('复盘实数')) for x in eligible),**amounts(eligible),'疑似A换B对数':len(edges),'强疑似重点对数':len(top_edges),'未核实对数':unresolved,'供货商待确认':sum(c['status']=='pending' for c in classes.values())}
    comparisons={name:amounts(subset) for name,subset in [('整店全口径',items),('已确认卓不凡',[x for x in eligible if classes[x['记录ID']]['status']=='zbf']),('其他可换货内部分析',[x for x in eligible if classes[x['记录ID']]['status']!='zbf'])]}
    return {'rows':rows,'stats':stats,'comparisons':comparisons,'edges':edges,'classes':classes,'byid':byid,'engine':engine,'peers':peers,'meta':meta}

def filtered_rows(model,status='全部',category='全部',include_pending=False):
    rows=model['rows']
    return [r for r in rows if (r['_eligible'] or include_pending or status=='归属待确认') and (category=='全部' or r['品类']==category) and
        (status=='全部' or status=='归属待确认' and r['_status']=='pending' or status=='未复盘' and r['复盘实数'] is None or status=='已复盘' and r['复盘实数'] is not None or status=='仍有差异' and r['最新差异'] not in (None,0) or status=='疑似A换B' and r['疑似A换B对应商品'] or status=='待补凭证' and r['疑似A换B对应商品'] and not r['_verified'])]

def audit_excel(model,rows):
    import openpyxl
    w=openpyxl.Workbook();s=w.active;s.title='可A换B商品专项审计';s.append(HEADERS)
    for row in rows:
        s.append([row[k] for k in HEADERS])
        for col in (4,5):s.cell(s.max_row,col).data_type='s';s.cell(s.max_row,col).number_format='@'
        # 外部备注/名称按文本写入，不能成为Excel公式。
        for cell in s[s.max_row]:
            if isinstance(cell.value,str):cell.data_type='s'
    s.freeze_panes='F2';s.auto_filter.ref=s.dimensions
    for col,width in [('A',8),('B',18),('C',30),('D',21),('E',18),('F',18),('M',65),('N',35),('O',35),('P',24)]:s.column_dimensions[col].width=width
    stats=w.create_sheet('汇总与口径');stats.append(['项目','数值'])
    for k,v in model['stats'].items():stats.append([k,float(v) if isinstance(v,D) else v])
    stats.append(['说明','专项审计不抵销商品，不修改公司三列数量或整店2‰正式口径；未核实金额不等于已确认损耗。'])
    for name,values in model['comparisons'].items():stats.append([name,'；'.join(k+'='+str(v) for k,v in values.items())])
    pairs=w.create_sheet('A换B线索');pairs.append(['商品A条码','商品A名称','商品B条码','商品B名称','线索强度','排序分','依据','人工说明','凭证编号','提示'])
    shown={r['_id'] for r in rows}
    for a,b in sorted(model['edges']):
        if a not in shown and b not in shown:continue
        x,y=model['byid'][a],model['byid'][b];pair=model['engine'].pair(a,b);proof=model['meta'].get('pair_proofs',{}).get('|'.join(sorted((str(x['序号']),str(y['序号'])))),{});pairs.append([x['商品条码'],x['商品名称'],y['商品条码'],y['商品名称'],pair['confidence'],str(pair['strength']),pair['evidence'],proof.get('说明',''),proof.get('单号',''),'疑似待核实，不抵销、不删除'])
        for cell in pairs[pairs.max_row]:cell.data_type='s'
    history=w.create_sheet('历史专项凭证');history.append(['对应序号','人工说明','凭证编号','类型'])
    for key,p in model['meta'].get('pair_proofs',{}).items():
        history.append([key,p.get('说明',''),p.get('单号',''),p.get('类型','原有人工凭证')])
    for key,note in model['meta'].get('zbf_notes',{}).items():history.append([key,note,'','原有单商品专项说明'])
    for row in history:
        for cell in row:
            if isinstance(cell.value,str):cell.data_type='s'
    qualification=w.create_sheet('资格与来源');qualification.append(['商品条码','商品编码','商品名称','资格来源','换货组','资格依据'])
    for r in rows:
        e=model['engine'].eligibility[r['_id']]
        qualification.append([r['商品条码'],r['商品编码'],r['商品名称'],e['source'],e['group'],e['reason']])
        for cell in qualification[qualification.max_row]:cell.data_type='s'
    fp=io.BytesIO();w.save(fp);return fp.getvalue()

def audit_panel(db,batch,items,state,rev):
    import streamlit as st
    outcome=st.session_state.get('zbf_result_'+batch)
    pane=st.expander('可A换B商品专项审计',on_change='rerun',key='swap_audit_'+batch)
    if not pane.open:return
    with pane:
        model=audit_model(items,effective_vendors(state),state['meta'],state.get('exchange_catalog',[]));stats=model['stats']
        st.write(f"可换货：{stats['商品总条数']}条（卓不凡{stats['卓不凡商品']} / 其他{stats['其他可换货商品']}） · 已复盘{stats['已复盘']} / 未复盘{stats['未复盘']} · 供货商待确认{stats['供货商待确认']}条")
        st.write(f"盘盈{stats['盘盈']:.2f}元 · 盘亏{stats['盘亏']:.2f}元 · 净差异{stats['净差异']:.2f}元 · 强疑似重点 {stats['强疑似重点对数']}对 · 未核实{stats['未核实对数']}对；每件默认仅列最相关3项，完整候选在Excel")
        if stats['缺失金额']:st.warning(f"{stats['缺失金额']}条成本无法计算，汇总仅含已知金额。")
        a,b=st.columns(2)
        status=a.selectbox('专项审计状态',['全部','未复盘','已复盘','仍有差异','疑似A换B','待补凭证','归属待确认'],key='zbf_status_'+batch)
        cat=b.selectbox('专项审计品类',['全部']+sorted({r['品类'] for r in model['rows']}),key='zbf_cat_'+batch)
        pending=st.checkbox('专项表同时显示供货商待确认商品',key='zbf_pending_'+batch)
        rows=filtered_rows(model,status,cat,pending)
        st.dataframe([{k:r[k] for k in HEADERS} for r in rows],hide_index=True,alt='可A换B独立专项审计，不是公司上传表')
        st.download_button('下载可A换B专项审计Excel',audit_excel(model,rows),'可A换B专项审计_非公司上传.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',on_click='ignore')
        st.caption(f'专项审计数据版本：{rev} · 当前完整候选可在独立Excel查询，未自动抵销。')
        # 写入成功提示放在最新下载数据刷新之后，避免提示出现时仍下载上一版凭证。
        if outcome:(st.success if outcome[0] else st.error)(outcome[1])
        confirmed=[r for r in model['rows'] if r['_eligible']]
        if confirmed:
            selected=st.selectbox('保留人工核查结论及凭证的商品',[r['_id'] for r in confirmed],format_func=lambda k:model['byid'][k]['商品名称']+' / '+model['byid'][k]['商品条码'])
            x=model['byid'][selected]
            token=batch+'_'+selected
            def save_proof(selected=selected,token=token):
                from storage import Store
                live=Store(db.root)
                try:
                    fresh,_,latest,version=live.load(batch)
                    if version!=rev:raise ValueError('另一窗口已更新，请刷新后核对专项凭证，未覆盖原记录。')
                    latest['meta'].setdefault('zbf_notes',{})[selected]=st.session_state['zbf_note_'+token]
                    updated=patch_items(fresh,{selected:{'核实结论':st.session_state['zbf_conclusion_'+token],'相关单号':st.session_state['zbf_doc_'+token]}})
                    live.save(batch,updated,latest,version,'本机店长','可A换B专项说明与凭证')
                    st.session_state['zbf_result_'+batch]=(True,'专项说明与凭证已保存')
                except ValueError as exc:st.session_state['zbf_result_'+batch]=(False,str(exc))
                finally:live.close()
            with st.form('zbf_proof_'+batch):
                conclusions=['','已排除','无需调整','确认并附单据']
                st.selectbox('核查结论（沿用已有结论）',conclusions,index=conclusions.index(x.get('核实结论','')),key='zbf_conclusion_'+token)
                st.text_area('专项核查说明（人工）',value=state['meta'].get('zbf_notes',{}).get(selected,''),key='zbf_note_'+token)
                st.text_input('凭证编号',value=x.get('相关单号',''),key='zbf_doc_'+token)
                st.form_submit_button('保存专项说明与凭证',on_click=save_proof)
        with st.expander('对应商品核对、查看更多及双方凭证'):
            eligible_ids=[r['_id'] for r in model['rows'] if r['_eligible']]
            if eligible_ids:
                a=st.selectbox('商品A',eligible_ids,format_func=lambda k:model['byid'][k]['商品名称']+' / '+model['byid'][k]['商品条码'],key='swap_a_'+batch)
                count=model['engine'].count(a,'swap');limit=st.session_state.get('swap_limit_'+batch,3)
                ps=model['engine'].peers(a,limit=limit,kind='swap')
                st.caption(f'当前最相关{len(ps)}项 / 完整{count}项，按品类、成本、规格、数量吻合排序。')
                if len(ps)<count and st.button('查看更多A换B候选'):
                    st.session_state['swap_limit_'+batch]=limit+20;st.rerun()
                if ps:
                    b=st.selectbox('对应商品B',[p['id'] for p in ps],format_func=lambda k:model['byid'][k]['商品名称']+' / '+model['byid'][k]['商品条码'],key='swap_b_'+batch)
                    st.dataframe([{k:model['byid'][i].get(k) for k in ('序号','商品名称','商品条码','商品编码','系统数','初盘数','复盘实数','备注')}|{'最新差异':num(newest_diff(model['byid'][i])),'差异金额':num(current_amount(model['byid'][i]))} for i in (a,b)],hide_index=True,alt='A与B双方实数及金额对照')
                    pair=model['engine'].pair(a,b);st.caption(pair['evidence']+'；仅为线索，不自动抵销或确认换货。')
                    proofkey='|'.join(sorted(str(model['byid'][i]['序号']) for i in (a,b)));old=state['meta'].get('pair_proofs',{}).get(proofkey,{})
                    token=batch+'_'+proofkey
                    def save_pair(a=a,b=b,proofkey=proofkey,token=token):
                        from storage import Store
                        live=Store(db.root)
                        try:
                            fresh,_,latest,version=live.load(batch)
                            if version!=rev:raise ValueError('另一窗口已更新，请刷新后核对，未覆盖双方凭证。')
                            from intelligence import engine_for
                            current=engine_for(fresh,latest).pair(a,b)
                            if not current or not current['swap']:raise ValueError('最新差异或换货资格已变化，不能按旧线索保存。')
                            explanation=st.session_state['swap_explain_'+token].strip();doc=st.session_state['swap_doc_'+token].strip()
                            if not explanation or not doc:raise ValueError('双方核查须保留说明和凭证编号。')
                            latest['meta'].setdefault('pair_proofs',{})[proofkey]={'说明':explanation,'单号':doc,'商品A':a,'商品B':b,'类型':'可A换B人工核查'}
                            live.save(batch,fresh,latest,version,'本机店长','可A换B双方凭证');st.session_state['zbf_result_'+batch]=(True,'双方对应关系与凭证已保存')
                        except ValueError as exc:st.session_state['zbf_result_'+batch]=(False,str(exc))
                        finally:live.close()
                    with st.form('swap_pair_'+token):
                        st.text_input('双方核查说明',value=old.get('说明',''),key='swap_explain_'+token)
                        st.text_input('双方凭证编号',value=old.get('单号',''),key='swap_doc_'+token)
                        st.form_submit_button('保存双方核查凭证',on_click=save_pair)
        with st.expander('历史专项说明与双方凭证'):
            proofs=state['meta'].get('pair_proofs',{})
            if proofs:
                key=st.selectbox('历史双方对应关系',list(proofs),key='swap_history_'+batch)
                st.write(proofs[key].get('说明',''))
                st.caption('已保存凭证：'+proofs[key].get('单号','未提供'))
                st.caption('历史人工资料原样保留；当前差异归零或资格停用只撤销实时线索，不删除历史凭证。')
            else:st.caption('尚无双方凭证。原有单商品说明、结论及单号保留在上方专项记录中。')
        with st.expander('内部分析口径对照'):
            st.caption('非卓不凡口径仅供内部分析，不代表公司最终损耗结论。公司导出和顶部2‰始终包含整店商品。')
            st.dataframe([{'口径':n,**{k:num(v) if isinstance(v,D) else v for k,v in values.items()}} for n,values in model['comparisons'].items()],hide_index=True,alt='全口径与仅内部分析口径')
