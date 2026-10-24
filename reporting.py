"""经营测算和季度文字：金额始终取当前批次，不改变V13数量和审核规则。"""
from datetime import date, datetime
from zoneinfo import ZoneInfo
from decimal import Decimal as D, ROUND_HALF_UP
import hashlib
from core import summary, decimal_value, json_bytes

FINANCE_FIELDS={'sales_amount':'实际销售金额','sales_cost':'同期含税销售成本'}
REPORT_FIELDS={'store','report_date','sales_start','sales_end','quarter','reason','reason_confirmed',
               'fresh_enabled','fresh_start','fresh_end','fresh_sales','fresh_cost','fresh_gain','fresh_loss','draft'}
MONEY_FIELDS={'fresh_sales','fresh_cost','fresh_gain','fresh_loss'}
DATE_FIELDS={'report_date','sales_start','sales_end','fresh_start','fresh_end'}

def money(value):
    number=decimal_value(value)
    if number is None:return '待填写'
    rounded=number.quantize(D('.01'),rounding=ROUND_HALF_UP)
    return format(abs(rounded) if rounded==0 else rounded,'.2f')

def financial_panel(items,meta):
    s=summary(items,meta.get('sales_cost'));net=s['净差异'];cost=decimal_value(meta.get('sales_cost'))
    loss=None if net is None else max(D(0),-net)
    allowance=None if cost is None or cost<=0 else cost*D('.002')
    remaining=None if allowance is None or loss is None else allowance-loss
    rate=None if net is None or cost is None or cost<=0 else net/cost*1000
    # 使用金额比较避免显示四舍五入到2.00‰时，误把实际超标认作达标。
    status='待计算' if remaining is None else '当前测算达标' if remaining>=0 else '当前测算超标'
    values={'gain':s['盘盈'],'loss':s['盘亏'],'net':net,'rate':rate,'allowance':allowance,
            'net_loss':loss,'remaining':remaining}
    return {**{key:None if value is None else money(value) for key,value in values.items()},
            'status':status,'over_limit':remaining is not None and remaining<0,'done':s['已复盘'],'remaining_rows':s['未复盘'],
            'final_approved':False,'note':'当前测算，仅供复盘；正式导出仍须完整检查'}

def report_defaults(meta,today=None):
    today=today or datetime.now(ZoneInfo('Asia/Shanghai')).date()
    return {'store':meta.get('store','门店未识别'),'report_date':today.isoformat(),
            'sales_start':'','sales_end':'','quarter':f'{today.year}年第{(today.month-1)//3+1}季度',
            'reason':'','reason_confirmed':False,'fresh_enabled':False,
            'fresh_start':'','fresh_end':'','fresh_sales':None,'fresh_cost':None,'fresh_gain':None,'fresh_loss':None,
            **meta.get('report',{})}

def validated_meta_value(scope,field,value):
    if scope=='finance':
        if field not in FINANCE_FIELDS:raise ValueError('不是可编辑的经营字段')
        if value is None or str(value).strip()=='':return None
        result=decimal_value(value)
        if result is None or result<0:raise ValueError(FINANCE_FIELDS[field]+'须为非负有限数字，空白表示未填写')
        return str(result)
    if scope!='report' or field not in REPORT_FIELDS:raise ValueError('不是可编辑的汇报字段')
    if field in ('fresh_enabled','reason_confirmed'):
        if not isinstance(value,bool):raise ValueError('汇报选项必须为布尔值')
        return value
    if field in MONEY_FIELDS:
        if value is None or str(value).strip()=='':return None
        result=decimal_value(value)
        if result is None or (result>0 if field=='fresh_loss' else result<0):
            raise ValueError('鲜食盘亏须为负数或0；其他鲜食金额须为非负有限数字')
        return str(result)
    text=str(value or '').strip()
    if len(text)>(20000 if field=='draft' else 6000 if field=='reason' else 120):raise ValueError('汇报内容过长')
    if field in DATE_FIELDS and text:
        try:date.fromisoformat(text)
        except ValueError as exc:raise ValueError('日期须为YYYY-MM-DD') from exc
    return text

def _period(start,end):
    return f'{start or "起日待填写"}至{end or "止日待填写"}'

def report_document(items,meta):
    config=report_defaults(meta);s=summary(items,meta.get('sales_cost'));panel=financial_panel(items,meta)
    missing=[]
    for field,label in [('sales_amount','实际销售金额'),('sales_cost','含税销售成本')]:
        value=decimal_value(meta.get(field))
        if value is None or field=='sales_cost' and value<=0:missing.append(label+'待填写')
    for start,end in [('sales_start','sales_end'),('fresh_start','fresh_end')]:
        if start.startswith('fresh') and not config['fresh_enabled']:continue
        if config[start] and config[end] and config[start]>config[end]:missing.append('统计起日不能晚于止日')
    label=lambda n:'合计差异' if n is None or n==0 else '合计盘盈' if n>0 else '合计盘亏'
    net=s['净差异']
    reason=config['reason'] if config['reason'].strip() and config['reason_confirmed'] else '待店长填写并确认'
    rate='待计算' if panel['rate'] is None else panel['rate']+'‰'
    text=(f"{config['store']}{config['report_date']}{config['quarter']}盘点：\n\n"
          f"{_period(config['sales_start'],config['sales_end'])}期间实际销售金额：{money(meta.get('sales_amount'))}元，"
          f"含税销售成本金额：{money(meta.get('sales_cost'))}元，盘盈金额：{money(s['盘盈'])}元，"
          f"盘亏金额：{money(s['盘亏'])}元，{label(net)}金额：{money(net)}元，净差异率{rate}。\n\n"
          f"主要原因：{reason}。\n\n"
          f"2‰损耗标准：允许净损耗{money(s['允许额度'])}元，当前净损耗{money(panel['net_loss'])}元，{panel['status']}。\n"
          f"（当前已填写复盘{s['已复盘']}项，剩余{s['未复盘']}项；当前测算不代表最终审核通过。）")
    if config['fresh_enabled']:
        gain=decimal_value(config['fresh_gain']);loss=decimal_value(config['fresh_loss'])
        fresh_net=None if gain is None or loss is None else gain+loss
        text+=(f"\n\n{config['store']}鲜食盘点：\n\n{_period(config['fresh_start'],config['fresh_end'])}期间销售额："
               f"{money(config['fresh_sales'])}元，含税销售成本：{money(config['fresh_cost'])}元，"
               f"盘盈金额：{money(gain)}元，盘亏金额：{money(loss)}元，{label(fresh_net)}：{money(fresh_net)}元。")
    text+='\n\n请领导审核。'
    signature=hashlib.sha256(json_bytes([text,{k:v for k,v in config.items() if k not in ('draft','draft_signature')}])).hexdigest()
    saved_draft=config.get('draft','');valid_draft=bool(saved_draft) and config.get('draft_signature')==signature
    return {'config':config,'generated':text,'text':saved_draft if valid_draft else text,
            'signature':signature,'stale_draft':saved_draft if saved_draft and not valid_draft else '',
            'warnings':missing,'edited':valid_draft}
