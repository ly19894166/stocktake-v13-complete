"""单入口严格识别两份原始报表；保留原字节和既有批次指纹。"""
import hashlib
from core import read_source,decimal_value

def resolve_reports(files):
    if len(files)!=2:raise ValueError('请一次选择两份原始Excel：一份盘盈、一份盘亏。')
    result={};digests=set()
    for name,blob in files:
        digest=hashlib.sha256(blob).hexdigest()
        if digest in digests:raise ValueError('两份文件内容相同，缺少另一类报表。')
        digests.add(digest)
        if not name.lower().endswith(('.xls','.xlsx')):raise ValueError('仅接收两份原始.xls/.xlsx文件。')
        rows,_=read_source(blob,name,'盘盈',exclude_red=False)
        if not rows:raise ValueError(name+'没有商品明细')
        signs=set()
        for x in rows:
            initial,system=decimal_value(x.get('初盘数')),decimal_value(x.get('系统数'))
            if initial is None or system is None:raise ValueError(name+'数量无法计算，请核对原件')
            diff=initial-system+decimal_value(x.get('子转母'),0)
            if diff:signs.add('盘盈' if diff>0 else '盘亏')
        hints={role for role in ('盘盈','盘亏') if role in name}
        if len(signs)>1 or len(hints)>1:raise ValueError(name+'同时包含两类方向，无法完整、唯一识别；请提供公司原始两份报表。')
        if hints and signs and hints!=signs:raise ValueError(name+'文件名与实际数量方向不一致，未导入。')
        roles=hints or signs
        if len(roles)!=1:raise ValueError(name+'没有可确认的盘盈/盘亏标识，未猜测归类。')
        role=next(iter(roles))
        if role in result:raise ValueError('识别到两份'+role+'，缺少另一类报表。')
        result[role]=(name,blob)
    if set(result)!={'盘盈','盘亏'}:raise ValueError('必须完整提供盘盈和盘亏两类数据。')
    return result
