"""V13业务内核。金额逐行四舍五入，当前数量是实物总数。"""
from __future__ import annotations
import copy
import hashlib
import io
import json
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from source_core import read_source, decimal_value, as_code, load_excel

VERSION = 'V13 Complete · OneShot'
OUTPUT_HEADERS = ('商品编码', '商品条码', '数量')
EDIT_FIELDS = ('复盘实数', '备注', '单位说明', '零售价', '核实结论', '相关单号',
               '成本价','部类','大类','中类','小类','品牌','包装系数')
VENDOR_HEADERS = ('商品条码','供货商编码','供货商名称','商品编码','商家编码','供应商商品名称',
                  '品牌','部类','大类','中类','成本价','零售价','主条码','主供Y/N','生效日期','失效日期','备注')
D = Decimal
ZERO = D(0)

def json_bytes(value):
    return json.dumps(value,ensure_ascii=False,indent=2,default=str,allow_nan=False).encode('utf8')

def rounded(v, places=4):
    return v.quantize(D(1).scaleb(-places), rounding=ROUND_HALF_UP)

def num(v):
    return None if v is None else float(v)

def valid_count(v):
    d = decimal_value(v)
    return d is not None and d >= 0

def import_pair(gain, loss):
    """gain/loss=(文件名,bytes)。两份原件均保留；不按名称去重或求和。"""
    items, notes = [], []
    for role, (name, blob) in [('盘盈', gain), ('盘亏', loss)]:
        rows, warnings = read_source(blob, name, role, exclude_red=False)
        if not rows:
            raise ValueError(role + '文件没有商品明细')
        for x in rows:
            raw = x['原始字段']
            x['商品名称'] = str(raw.get('商品名称') or '')
            for key, header in [('商家编码','商品商家编码'),('部类','部类名称'),
                                ('大类','大类名称'),('中类','中类名称'),('小类','小类名称')]:
                x[key] = as_code(raw.get(header))
            x['原始调整'] = decimal_value(x['子转母'], ZERO)
            x['记录ID'] = x['文件SHA256'][:12]+':'+x['工作表']+':'+str(x['原始行号'])
            x.update({'单位说明':'', '零售价':None, '核实结论':'', '相关单号':''})
        items.extend(rows)
        notes.extend(warnings)
    items.sort(key=lambda x: tuple(str(x[k]).encode('gbk', errors='replace')
                                  for k in ('大类','中类','商品名称')) + (x['商品编码'],))
    for n, x in enumerate(items, 1):
        x['序号'] = n
    # 与V1.2保持原始文件批次指纹兼容，另有门店与期间分隔具体批次。
    fingerprint = hashlib.sha256(b'loss\0'+loss[1]+b'\0gain\0'+gain[1]).hexdigest()[:20]
    return items, notes, fingerprint

NUMERIC_SOURCE = ('系统数','初盘数','子转母','源复盘数','源报差异数','成本价',
                  '原始差异成本','公式残差','原始调整')

def hydrate(items):
    for x in items:
        for field in NUMERIC_SOURCE + ('复盘实数','零售价'):
            if field in x:
                x[field] = decimal_value(x[field])
    return items

def current_total(x):
    value = decimal_value(x.get('复盘实数'))
    return rounded(value) if value is not None else decimal_value(x['初盘数'])

def initial_diff(x):
    initial, system = decimal_value(x['初盘数']), decimal_value(x['系统数'])
    if initial is None or system is None:
        return None
    return rounded(initial-system+decimal_value(x.get('原始调整'),ZERO))

def newest_diff(x):
    total, system = current_total(x), decimal_value(x['系统数'])
    if total is None or system is None:
        return None
    return rounded(total-system+decimal_value(x.get('原始调整'),ZERO))

def current_amount(x):
    diff, cost = newest_diff(x), decimal_value(x['成本价'])
    return None if diff is None or cost is None else rounded(diff*cost, 2)

def validate_all(items):
    errors = []
    for x in items:
        prefix = f"序号{x['序号']} {x['商品名称']}："
        errors.extend(prefix+p['说明'] for p in x.get('导入问题',[]) if p['等级']=='阻断')
        for key in ('系统数','初盘数','成本价'):
            if decimal_value(x.get(key)) is None:
                errors.append(prefix+key+'缺失或无效')
        for key in ('初盘数','成本价'):
            if decimal_value(x.get(key),ZERO)<0:
                errors.append(prefix+key+'不能为负数')
        if x.get('复盘实数') is not None and not valid_count(x['复盘实数']):
            errors.append(prefix+'复盘实数须为非负有限数字，清空表示未复盘')
        if x.get('零售价') is not None and not valid_count(x['零售价']):
            errors.append(prefix+'零售价须为非负有限数字')
        for field in ('商品编码','商品条码'):
            if not x.get(field):
                errors.append(prefix+'缺'+field)
        if x.get('商品条码') and not str(x['商品条码']).isdigit():
            errors.append(prefix+'商品条码不是完整数字文本，请核实原件')
        if x.get('核实结论','') not in ('','已排除','确认并附单据','无需调整'):
            errors.append(prefix+'核实结论不在允许选项中')
    for key in ('记录ID','商品编码','商品条码'):
        for value, count in Counter(x.get(key) for x in items).items():
            if value and count>1:
                errors.append(f'{key} {value} 重复{count}条，须核实原表，不自动合并或覆盖')
    return list(dict.fromkeys(errors))

def patch_items(items, patches, fields=EDIT_FIELDS):
    result = copy.deepcopy(items)
    byid = {x['记录ID']:x for x in result}
    for ident, patch in patches.items():
        if ident not in byid:
            raise ValueError('更新含不属于本批次的商品')
        for key, value in patch.items():
            if key not in fields:
                raise ValueError('不可编辑字段：'+key)
            if key in ('复盘实数','零售价','成本价','包装系数'):
                if value is not None and not valid_count(value):
                    raise ValueError(key+'必须是非负有限数字')
                value = decimal_value(value)
            else:
                value = str(value or '').strip()
            byid[ident][key] = value
    # 导入阻断可以留档，但任何新增无效录入都不能写入。
    return result

def default_vendors():
    data = json.loads(Path(__file__).with_name('vendors.json').read_text('utf8'))
    return [dict(zip(VENDOR_HEADERS,row)) for row in data]

def supplier_map(vendors):
    grouped = defaultdict(list)
    for row in vendors:
        if row.get('商品条码'):
            grouped[str(row['商品条码'])].append(row)
    return {bc: ('多供货商·待核实' if len(rows)>1 else rows[0]['供货商名称'])
            for bc, rows in grouped.items()}

def legacy_candidate_counts(items, vendors, *, meta=None, exchange=()):
    """严格复刻V13 U/V条件：同部/大/中类、成本±.01、反向>=1；售价±.01或缺售价。"""
    from exchange_rules import eligibility
    allowed=eligibility(items,vendors,meta,exchange)
    suppliers = supplier_map(vendors)
    result = {x['记录ID']:{'串码':[], '换货':[]} for x in items}
    diffs = {x['记录ID']:newest_diff(x) for x in items}
    for a in items:
        da, ca = diffs[a['记录ID']], decimal_value(a['成本价'])
        if da is None or abs(da)<1:
            continue
        sa = suppliers.get(a['商品条码'],'未在目录')
        pa = decimal_value(a.get('零售价'))
        for b in items:
            db = diffs[b['记录ID']]
            if db is None or abs(db)<1 or da*db>=0:
                continue
            sb = suppliers.get(b['商品条码'],'未在目录')
            if allowed[a['记录ID']]['group'] and allowed[a['记录ID']]['group']==allowed[b['记录ID']]['group']:
                result[a['记录ID']]['换货'].append(b['序号'])
            cb = decimal_value(b['成本价'])
            if ca is None or cb is None or abs(ca-cb)>D('.01'):
                continue
            if not all(a.get(k) and a[k]==b.get(k) for k in ('部类','大类','中类')):
                continue
            pb = decimal_value(b.get('零售价'))
            if pa is None or pb is None or abs(pa-pb)<=D('.01'):
                result[a['记录ID']]['串码'].append(b['序号'])
    return result

def candidate_counts(items, vendors, parameters=None, main=None, *, meta=None, exchange=()):
    from intelligence import CandidateEngine
    engine=CandidateEngine(items,vendors,parameters,main,meta=meta,exchange=exchange)
    return {x['记录ID']:{'串码':[engine.items[k]['序号'] for k in engine.neighbors(x['记录ID'],'mix')],
                        '换货':[engine.items[k]['序号'] for k in engine.neighbors(x['记录ID'],'swap')]}
            for x in items}

def changes(x):
    reviewed = decimal_value(x.get('复盘实数'))
    before, after = initial_diff(x), newest_diff(x)
    delta = None if reviewed is None else rounded(reviewed-x['初盘数'])
    found = None if delta is None or before is None else min(max(ZERO,delta),-before) if before<0 else ZERO
    reduced = None if delta is None or before is None else min(max(ZERO,-delta),before) if before>0 else ZERO
    added = None if delta is None or after is None or before is None else max(ZERO,max(ZERO,after)-max(ZERO,before))
    kind = ('待复盘' if reviewed is None else '复盘归零' if after==0 else
            '找回盘亏' if found and found>0 else '盘盈减少' if reduced and reduced>0 else
            '盘盈增加' if added and added>0 else '数量未变' if delta==0 else '复盘变化')
    return {'复盘变化量':delta,'找回数量':found,'盘盈减少量':reduced,'盘盈增加量':added,'变化类型':kind}

def change_rows(items, vendors):
    suppliers = supplier_map(vendors)
    return [{'商品编码':x['商品编码'],'商品条码':x['商品条码'],'数量':num(current_total(x)),
             '商家编码':x['商家编码'],'商品名称':x['商品名称'],
             '供货商':suppliers.get(x['商品条码'],'未在目录'),
             '系统数':num(x['系统数']),'初盘数':num(x['初盘数']),'复盘实数':num(x['复盘实数']),
             **{k:num(v) if isinstance(v,D) else v for k,v in changes(x).items()},
             '最终总数':num(current_total(x)),'最新差异':num(newest_diff(x)),
             '差异成本':num(current_amount(x)),'源序号':x['序号']} for x in items]

def summary(items, sales_cost):
    amounts = [current_amount(x) for x in items]
    complete = all(v is not None for v in amounts)
    pos = sum((v for v in amounts if v is not None and v>0),ZERO) if complete else None
    neg = sum((v for v in amounts if v is not None and v<0),ZERO) if complete else None
    net = pos+neg if complete else None
    cost = decimal_value(sales_cost)
    rate = rounded(net/cost*1000) if net is not None and cost is not None and cost>0 else None
    return {'盘盈':pos,'盘亏':neg,'净差异':net,'报损率':rate,
            '净损耗率':None if rate is None else max(ZERO,-rate),
            '已复盘':sum(valid_count(x.get('复盘实数')) for x in items),
            '未复盘':sum(not valid_count(x.get('复盘实数')) for x in items),
            '允许额度':rounded(cost*D('.002'),2) if cost is not None and cost>0 else None}

def export_blockers(items, meta, vendors, counts=None, engine=None):
    errors = validate_all(items)
    if not items:
        errors.append('没有商品数据')
    for key, label in [('both_files','两份初盘文件'),('coverage','同门店同期完整盘点范围'),('evidence','核实凭证齐备')]:
        if meta.get(key) is not True:
            errors.append('尚未确认：'+label)
    if counts is None and engine is None:
        from intelligence import CandidateEngine
        engine=CandidateEngine(items,vendors,meta.get('parameters'),meta.get('main_suppliers'),meta=meta)
    for x in items:
        prefix = f"序号{x['序号']}："
        if not valid_count(x.get('复盘实数')):
            errors.append(prefix+'待复盘')
        elif newest_diff(x)!=0 and (not str(x.get('备注','')).strip() or decimal_value(x['备注']) is not None):
            errors.append(prefix+'差异原因待补（须文字说明）')
        if decimal_value(x.get('原始调整'),ZERO)!=0 and not str(x.get('单位说明','')).strip():
            errors.append(prefix+'特殊单位待说明')
        c = counts[x['记录ID']] if counts is not None else {'串码':engine.count(x['记录ID']),'换货':engine.count(x['记录ID'],'swap')}
        if c['串码'] or c['换货']:
            conclusion = x.get('核实结论','')
            pair_proofs=meta.get('pair_proofs',{})
            resolved=engine.resolved(x['记录ID'],pair_proofs) if counts is None else all(
                str(pair_proofs.get('|'.join(sorted((str(x['序号']),str(peer)))),{}).get('说明','')).strip()
                for peer in set(c['串码']+c['换货']))
            if not resolved and conclusion not in ('已排除','无需调整') and not (conclusion=='确认并附单据' and str(x.get('相关单号','')).strip()):
                errors.append(prefix+'串码或换货待核实')
    stats = summary(items,meta.get('sales_cost'))
    if stats['报损率'] is None:
        errors.append('缺含税销售成本或存在无法计算的商品')
    elif max(ZERO,-stats['净差异'])>decimal_value(meta.get('sales_cost'))*D('.002'):
        errors.append('超过2‰·继续复核')
    return list(dict.fromkeys(errors))

def create_company_xls(items, meta, vendors, engine=None):
    # 不信任界面按钮状态，内核再次验证所有条件。
    blockers = export_blockers(items,meta,vendors,engine=engine)
    if blockers:
        raise ValueError('不能正式导出：'+'；'.join(blockers[:8]))
    if len(items)>65535:raise ValueError('旧格式XLS最多65535条数据，请按公司批准的批次范围处理')
    import xlwt
    book = xlwt.Workbook(encoding='utf-8')
    sheet = book.add_sheet('Sheet1')
    text = xlwt.easyxf(num_format_str='@')
    for c,h in enumerate(OUTPUT_HEADERS):
        sheet.write(0,c,h)
    for r,x in enumerate(items,1):
        sheet.write(r,0,x['商品编码'],text)
        sheet.write(r,1,x['商品条码'],text)
        sheet.write(r,2,float(current_total(x)))
    for c,width in enumerate((18,23,16)):
        sheet.col(c).width=width*256
    out=io.BytesIO();book.save(out)
    return out.getvalue()

def import_v13(blob, name, items):
    sheets = [(n,rows) for n,rows in load_excel(blob,name) if n.startswith('01')]
    if len(sheets)!=1:
        raise ValueError('须有唯一的01现场复盘表')
    rows=sheets[0][1]; header=None
    for ix,row in enumerate(rows[:20]):
        cols=[str(v or '').replace('★','').strip() for v in row]
        if '商品条码' in cols and '复盘实数' in cols:
            header={k:c for c,k in enumerate(cols) if k};start=ix+1;break
    if header is None:
        raise ValueError('01表缺商品条码或复盘实数')
    groups=defaultdict(list)
    for x in items:groups[x['商品条码']].append(x)
    patches={};seen=set()
    for row in rows[start:]:
        def get(k):
            c=header.get(k)
            return row[c] if c is not None and c<len(row) else None
        bc=as_code(get('商品条码'))
        if not bc:continue
        if bc in seen:raise ValueError('外部01表条码重复：'+bc)
        seen.add(bc)
        raw=get('复盘实数')
        if raw is None or raw=='':continue
        if not valid_count(raw):raise ValueError('复盘实数无效：'+bc)
        if len(groups.get(bc,[]))!=1:raise ValueError('无法唯一匹配条码：'+bc)
        target=groups[bc][0]
        if get('商品编码') not in (None,'') and as_code(get('商品编码'))!=target['商品编码']:
            raise ValueError('商品编码与条码不一致：'+bc)
        patches[target['记录ID']]={'复盘实数':raw,'备注':as_code(get('备注／原因') or get('备注/原因'))}
    return patch_items(items,patches),len(patches)
