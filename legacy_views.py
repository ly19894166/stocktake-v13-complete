import copy
import os
from pathlib import Path
import pandas as pd
import streamlit as st
from core import decimal_value, num, import_pair, validate_all, current_total, newest_diff, current_amount, summary, patch_items, change_rows, supplier_map, candidate_counts, export_blockers, create_company_xls, import_v13, VENDOR_HEADERS
from storage import Store
from print_manager import MODES, printable_items, make_pdf, generate_print, reprint, selection_hash

def frame(rows, numeric=()):
    df = pd.DataFrame(rows)
    for c in numeric:
        if c in df:
            df[c] = pd.array(df[c], dtype='Float64')
    return df

def clean(v):
    return None if pd.isna(v) else v

def save(db, batch, items, state, rev, actor):
    try:
        db.save(batch, items, state, rev, actor)
    except (ValueError, OSError) as exc:
        st.error('未保存：' + str(exc))
        st.stop()
    st.rerun()

def printing(db, batch, items, state, rev):
    st.subheader('A4 · 按需复盘单')
    st.caption('先在01录入已知实数，再选品类打印其余商品。打印不改变复盘数量，不增加核查状态。')
    mode = st.selectbox('打印范围', list(MODES), format_func=MODES.get, key='mode_' + batch)
    cats = sorted({x['大类'] or '未分类' for x in items})
    cats = st.multiselect('品类（默认全部）', cats, default=cats, key='printcat_' + batch)
    sort = st.selectbox('排序', ['category', 'amount', 'source'], format_func=lambda x: {'category': '按品类和固定序号', 'amount': '按差异金额', 'source': '按源报表顺序'}[x], key='sort_' + batch)
    archives = db.prints(batch)
    printed = {r['source_id'] for p in archives for r in p['rows']}
    possible = printable_items(items, mode, cats, sort, printed)
    chosen = []
    if possible:
        all_rows = st.checkbox('本次默认全选', value=True, key='all_' + batch)
        df = frame([{'选择': all_rows, '序号': x['序号'], '品类': x['大类'], '商品名称': x['商品名称'], '商品条码': x['商品条码'], '当前总数': num(current_total(x)), '最新差异': num(newest_diff(x))} for x in possible])
        key = selection_hash(possible, state['meta'], mode, sort, [cats, all_rows])
        pick = st.data_editor(df, hide_index=True, key='pick_' + key, disabled=[c for c in df if c != '选择'], alt='本次选择打印的商品')
        chosen = [x for x, flag in zip(possible, pick['选择']) if flag]
        st.write(f'当前筛选 {len(possible)} 条，已选 {len(chosen)} 条。')
    else:
        st.info('当前范围没有商品，不生成空白 PDF。')
    fingerprint = selection_hash(chosen, state['meta'], mode, sort, cats)
    a, b = st.columns(2)
    if a.button('生成当前 PDF 预览', disabled=not chosen, key='preview_btn'):
        try:
            pdf, pages = make_pdf(chosen, state['meta'], batch, scope=MODES[mode])
            st.session_state['preview_' + batch] = (fingerprint, pdf, pages)
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(str(exc))
    if b.button('生成并留存打印批次', type='primary', disabled=not chosen, key='generate'):
        try:
            generate_print(db, batch, chosen, state['meta'], mode, sort, cats, rev)
            st.rerun()
        except (ValueError, RuntimeError, OSError) as exc:
            st.error(str(exc))
    preview = st.session_state.get('preview_' + batch)
    if preview:
        if preview[0] == fingerprint:
            st.caption(f'未留档预览 · {preview[2]} 页 · A4 横向')
            st.pdf(preview[1], height=600, alt='当前所选商品的A4复盘单预览')
            st.download_button('下载预览 PDF', preview[1], '未留档复盘预览.pdf', 'application/pdf')
        else:
            st.info('实数或范围已变化，请重新生成预览。')
    archives = db.prints(batch)
    if archives:
        st.subheader('打印历史与原单重印')
        byid = {p['id']: p for p in archives}
        ident = st.selectbox('历史打印批次', list(byid), key='history_' + batch, format_func=lambda k: f"{byid[k]['time']} · {byid[k]['count']}条 / {byid[k]['pages']}页 · {k}")
        try:
            pdf = db.print_pdf(batch, ident)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.caption('历史单保留当时的 PDF 和商品快照。原单重印使用相同 PDF 字节，另登记重印记录。')
        st.download_button('下载历史原单 PDF', pdf, ident + '.pdf', 'application/pdf')
        if st.checkbox('预览所选历史原单', key='histpreview_' + batch):
            st.pdf(pdf, height=600, alt='历史原始打印单')
        if st.button('原单重印并登记', key='repeat'):
            try:
                reprint(db, batch, ident, rev)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        st.dataframe(frame([{'批次': p['id'], '时间': p['time'], '商品数': p['count'], '页数': p['pages'], '原批次': p.get('parent') or '', 'PDF校验': p['pdf_sha256']} for p in archives]), hide_index=True, alt='打印历史')
    st.caption('在 PDF 阅读器中选 A4 横向、实际大小打印。软件不直接向打印机发送任务。')

def review(db, batch, items, state, rev, actor):
    st.subheader('正式导出检查 · 公司三列')
    meta = state['meta']
    st.caption('经营金额在01填写并自动保存。此处仅在准备正式导出时确认完整范围和凭证，不自动提交审批。')
    with st.form('audit_' + batch):
        coverage = st.checkbox('确认同门店、同期间且覆盖本次完整盘点范围', value=meta.get('coverage', False))
        evidence = st.checkbox('确认差异已核实、相关凭证齐备', value=meta.get('evidence', False))
        submit = st.form_submit_button('保存审核参数')
    if submit:
        updated = copy.deepcopy(state)
        updated['meta'].update(coverage=coverage, evidence=evidence)
        save(db, batch, items, updated, rev, actor)
    s = summary(items, meta.get('sales_cost'))
    if s['报损率'] is not None:
        a, b, c = st.columns(3)
        a.metric('当前测算净差异率（‰）', f"{s['报损率']:.2f}")
        b.metric('当前净损耗率 / 标准（‰）', f"{s['净损耗率']:.2f} / 2")
        c.metric('允许净损耗额度（元）', f"{s['允许额度']:,.2f}")
        if not meta.get('coverage'):
            st.warning('完整范围尚未确认，当前仅供暂估，不能判断整店达标。')
    else:
        st.info('请填写有效的同期含税销售成本。')
    st.caption(f"已填写{s['已复盘']}项 / 剩余{s['未复盘']}项；当前测算不代表最终审核通过。")
    blockers = export_blockers(items, meta, state['vendors'])
    if blockers:
        st.warning(f'待审核：{len(blockers)}项条件未满足。')
        st.dataframe(frame([{'待办': v} for v in blockers]), hide_index=True, alt='V13审核待办')
    else:
        st.success('符合条件·可准备审批')
        st.download_button('下载公司最终三列 .xls 候选文件', create_company_xls(items, meta, state['vendors']), '公司系统三列候选.xls', 'application/vnd.ms-excel')
    st.dataframe(frame([{'商品编码': x['商品编码'], '商品条码': x['商品条码'], '数量': num(current_total(x))} for x in items]), hide_index=True, alt='公司三列候选，数量为实物总数')
    st.caption('公司文件严格三列。由人工走审批及系统上传流程。')

def sources(db, batch, items, notes, state):
    st.subheader('来源核对与本地备份')
    errors = validate_all(items)
    if errors:
        st.dataframe(frame([{'阻断说明': v} for v in errors]), alt='数据阻断明细')
    rows = [{'序号': x['序号'], '原文件': x['原文件'], '工作表': x['工作表'], '源行': x['原始行号'], '商品条码': x['商品条码'], '源差异': num(x['源报差异数']), '原始子转母': num(x['原始调整']), '源成本金额': num(x['原始差异成本']), '最新差异': num(newest_diff(x)), '最新差异成本': num(current_amount(x)), '源表备注': str(x.get('源表备注') or '')} for x in items]
    st.dataframe(frame(rows), hide_index=True, alt='源值与V13重算值对照')
    with st.expander('导入校验提示与原始19列'):
        messages = notes + [p for x in items for p in x.get('导入问题', [])]
        if messages:
            st.dataframe(frame(messages), hide_index=True, alt='导入校验提示')
        st.dataframe(frame([x['原始字段'] for x in items]).astype('string'), hide_index=True, alt='只读原始19列')
    if st.button('生成本批审计包'):
        st.download_button('下载审计包（原件、复盘、日志、打印快照）', db.audit_zip(batch), '本批盘点审计.zip', 'application/zip')
    if st.button('生成全部批次数据库备份'):
        st.download_button('下载 SQLite 完整备份', db.backup(), 'stocktake.sqlite', 'application/vnd.sqlite3')
    st.dataframe(frame([{'序号': x['序号'], '时间': x['北京时间'], '操作人': x['操作人']} for x in db.history(batch)]), hide_index=True, alt='保存日志')
    st.caption('可在关闭程序后备份整个 data 文件夹。恢复前先备份现有data；关闭程序后用备份数据库替换，勿保留旧-wal/-shm文件。')
