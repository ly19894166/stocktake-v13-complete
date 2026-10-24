"""盘点汇报文本生成：独立于UI，只读取当前批次的实时计算结果。"""
from decimal import Decimal
from core import decimal_value, rounded, summary


def money(value):
    value = decimal_value(value)
    return '待填写' if value is None else f'{rounded(value, 2):,.2f}'


def report_text(items, meta, *, report_date='', quarter='第三季度', sales_period='', reasons='', fresh=None):
    """生成可复制文本。未填写值不推测；鲜食只按另行提供的数据生成。"""
    stats = summary(items, meta.get('sales_cost'))
    net = stats['净差异']
    store = (meta.get('store') or '门店未识别').strip()
    suffix = '合计盘亏金额' if net is not None and net < 0 else '合计盘盈金额' if net is not None and net > 0 else '合计差异金额'
    period = f'{sales_period.strip()}期间' if sales_period and sales_period.strip() else '统计期间'
    title = f'{store}{report_date.strip() if report_date else ""}{quarter.strip() if quarter else ""}盘点：'
    rate = '待填含税销售成本' if stats['报损率'] is None else f"{rounded(stats['报损率'], 2):.2f}‰"
    text = [
        title,
        f"{period}实际销售金额：{money(meta.get('sales_amount'))}元，"
        f"含税销售成本金额：{money(meta.get('sales_cost'))}元，"
        f"盘盈金额：{money(stats['盘盈'])}元，盘亏金额：{money(stats['盘亏'])}元，"
        f"{suffix}：{money(net)}元，损耗率：{rate}。",
        f"主要原因：{reasons.strip() if reasons and reasons.strip() else '待根据实际复盘情况填写'}。"
    ]
    if stats['允许额度'] is None or net is None:
        text.append('2‰损耗标准：待填写有效含税销售成本并确认完整盘点范围。')
    else:
        cost = decimal_value(meta['sales_cost'])
        net_loss = max(Decimal(0), -net)
        allowance = rounded(cost * Decimal('0.002'), 2)
        delta = rounded(allowance-net_loss, 2)
        conclusion = '当前测算在2‰范围内' if delta >= 0 else '当前测算超出2‰标准'
        text.append(
            f"2‰损耗标准：允许净损耗{money(allowance)}元，"
            f"当前净损耗{money(net_loss)}元，"
            f"{'剩余额度' if delta>=0 else '超出额度'}{money(abs(delta))}元；"
            f"{conclusion}（非最终审批结论）。"
        )
    if fresh:
        required = ('sales', 'cost', 'gain', 'loss')
        if not all(decimal_value(fresh.get(k)) is not None for k in required):
            raise ValueError('鲜食盘点的销售额、含税成本、盘盈、盘亏必须全部填写后才可生成。')
        if decimal_value(fresh['gain']) < 0 or decimal_value(fresh['loss']) > 0:
            raise ValueError('鲜食盘盈必须非负，盘亏必须非正。')
        fresh_net = decimal_value(fresh['gain']) + decimal_value(fresh['loss'])
        fresh_period = (fresh.get('period') or '').strip()
        text.extend([
            f'{store}鲜食盘点：',
            f"{fresh_period+'期间' if fresh_period else '统计期间'}销售额：{money(fresh['sales'])}元，"
            f"含税销售成本：{money(fresh['cost'])}元，"
            f"盘盈金额：{money(fresh['gain'])}元，盘亏金额：{money(fresh['loss'])}元，"
            f"{'合计盘亏' if fresh_net < 0 else '合计盘盈' if fresh_net > 0 else '合计差异'}：{money(fresh_net)}元。"
        ])
    text.append('请领导审核。')
    return '\n'.join(text)
