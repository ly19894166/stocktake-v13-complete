"""本机季度母版的两表审批资料。只读取格式及分表依据，不复制旧业务值。"""
import io,os,copy,hashlib,math,json,subprocess,tempfile
from pathlib import Path
from decimal import Decimal
import xlrd,xlwt
from core import as_code,decimal_value,current_amount,newest_diff,summary,valid_count
from reporting import financial_panel,report_document,money

SHEETS=('常规商品','鲜食')
COMMON=('商品商家编码','商品条码','商品名称','件装单位','销售规格','部类名称','大类名称','中类名称','小类名称','库存数量','初盘数量','复盘数量','差异数量','成本价','成本金额','初复盘差异原因解释')
FRESH=COMMON[:11]+('子转母商品数量',)+COMMON[11:]
TEMPLATE_NAME='季度盘点盈亏母版.xls'

def template_path(root):
    return Path(os.environ['STOCKTAKE_APPROVAL_TEMPLATE']) if os.environ.get('STOCKTAKE_APPROVAL_TEMPLATE') else Path(root)/'templates'/TEMPLATE_NAME

def read_template(blob):
    if len(blob)>20*1024*1024:raise ValueError('母版文件超过20MB')
    book=xlrd.open_workbook(file_contents=blob,formatting_info=True)
    if book.sheet_names()!=list(SHEETS):raise ValueError('母版须依次包含常规商品、鲜食两个工作表')
    for sheet,headers in zip(book.sheets(),(COMMON,FRESH)):
        actual=tuple(str(sheet.cell_value(0,c)).strip() for c in range(min(sheet.ncols,len(headers))))
        if actual!=headers:raise ValueError(sheet.name+'母版表头或顺序不符，请核实原文件')
        if sheet.nrows<2:raise ValueError(sheet.name+'缺少可参照的明细行格式')
    return book

def capture_style(path):
    script=Path(__file__).parent/'scripts/read_approval_style.ps1'
    blob=Path(path).read_bytes()
    # WPS即便只读打开，也可能更新OLE元数据。只打开可丢弃副本，母版字节保持原样。
    with tempfile.TemporaryDirectory(prefix='stocktake-style-',ignore_cleanup_errors=True) as folder:
        working=Path(folder)/'style-source.xls';working.write_bytes(blob)
        result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-TemplatePath',str(working)],capture_output=True,encoding='utf8',check=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    value=json.loads(result.stdout);value['template_sha256']=hashlib.sha256(blob).hexdigest();return value

def save_template(root,blob,capture=False):
    read_template(blob);folder=Path(root)/'templates';folder.mkdir(parents=True,exist_ok=True)
    target=folder/TEMPLATE_NAME;temp=target.with_suffix('.tmp');temp.write_bytes(blob);os.replace(temp,target)
    if capture and os.name=='nt':
        try:
            value=capture_style(target);sidecar=target.with_suffix('.style.json');tmp=sidecar.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False),encoding='utf8');os.replace(tmp,sidecar)
        except (OSError,ValueError,subprocess.SubprocessError):pass # 无WPS时保留文件内嵌基础样式；不修改环境。
    return target

def split_items(items,book):
    # 原母版的鲜食也可能含原料/耗材，仅看部类会误分。只使用完整条码及商家编码核对身份。
    memberships={}
    for sheet in book.sheets():
        for r in range(1,sheet.nrows):
            bc=as_code(sheet.cell_value(r,1));merchant=as_code(sheet.cell_value(r,0))
            if bc and bc.isdigit():memberships.setdefault(bc,set()).add((sheet.name,merchant))
    groups={name:[] for name in SHEETS};uncertain={}
    for item in items:
        bc=as_code(item.get('商品条码'));merchant=as_code(item.get('商家编码'));entries=memberships.get(bc,set())
        names={name for name,code in entries if not code or merchant and code==merchant}
        if len(names)==1 and len({n for n,c in entries})==1:name=next(iter(names))
        elif entries:
            name=SHEETS[0];uncertain[item['记录ID']]='分表待确认：母版条码身份或工作表归属冲突'
        elif item.get('部类')=='鲜食':name=SHEETS[1]
        else:
            name=SHEETS[0]
            if not item.get('部类'):uncertain[item['记录ID']]='分表待确认：缺少部类及可靠母版归属，暂列常规'
        groups[name].append(item)
    return groups,uncertain

def row_values(item,fresh=False,warning=''):
    recount=decimal_value(item.get('复盘实数'));diff=newest_diff(item);cost=decimal_value(item.get('成本价'))
    flags=[]
    if not valid_count(item.get('复盘实数')):flags.append('未复盘，差异暂估并沿用初盘数')
    if cost is None:flags.append('缺成本，金额待核实')
    if not item.get('商品编码') or not item.get('商品条码'):flags.append('缺编码或条码，待核实')
    if diff not in (None,0) and (not str(item.get('备注') or '').strip() or decimal_value(item.get('备注')) is not None):flags.append('差异原因待补')
    if not fresh and decimal_value(item.get('原始调整')):flags.append('V13原始调整'+str(item['原始调整'])+'已计入差异')
    if warning:flags.append(warning)
    note=str(item.get('备注') or '')
    if flags:note+=('；' if note else '')+'【系统提示：'+'；'.join(flags)+'】'
    values=[item.get('商家编码',''),item.get('商品条码',''),item.get('商品名称',''),item.get('件装单位',''),item.get('销售规格',''),item.get('部类',''),item.get('大类',''),item.get('中类',''),item.get('小类',''),decimal_value(item.get('系统数')),decimal_value(item.get('初盘数'))]
    if fresh:values.append(decimal_value(item.get('原始调整')))
    return values+[recount,diff,cost,current_amount(item),note]

def clone_style(book,index):
    xf=book.xf_list[index];f=book.font_list[xf.font_index];s=xlwt.XFStyle()
    for dest,src in [('name','name'),('height','height'),('bold','bold'),('italic','italic'),('struck_out','struck_out'),('outline','outline'),('shadow','shadow'),('colour_index','colour_index'),('escapement','escapement'),('underline','underline_type'),('family','family'),('charset','character_set')]:setattr(s.font,dest,getattr(f,src))
    a=xf.alignment
    for dest,src in [('horz','hor_align'),('vert','vert_align'),('dire','text_direction'),('rota','rotation'),('wrap','text_wrapped'),('shri','shrink_to_fit'),('inde','indent_level')]:setattr(s.alignment,dest,getattr(a,src))
    b=xf.border
    for side in ('left','right','top','bottom'):
        setattr(s.borders,side,getattr(b,side+'_line_style'));setattr(s.borders,side+'_colour',getattr(b,side+'_colour_index'))
    s.pattern.pattern=xf.background.fill_pattern;s.pattern.pattern_fore_colour=xf.background.pattern_colour_index;s.pattern.pattern_back_colour=xf.background.background_colour_index
    s.num_format_str=book.format_map[xf.format_key].format_str
    return s

def xls_value(value):
    if value is None:return ''
    if isinstance(value,Decimal):
        # BIFF数字使用双精度；异常超长数量保持文本而非悄悄损失有效位。
        return str(value) if len(value.as_tuple().digits)>15 else float(value)
    return str(value)

def generate(items,meta,blob,revision=None,style_profile=None):
    book=read_template(blob);groups,uncertain=split_items(items,book)
    if any(len(rows)>65490 for rows in groups.values()):raise ValueError('单表超出XLS行数限制，请核实批次范围')
    out=xlwt.Workbook(encoding='utf-8',style_compression=2)
    for ix,rgb in book.colour_map.items():
        if 8<=ix<=63 and rgb:out.set_colour_RGB(ix,*rgb)
    profile=style_profile if style_profile and style_profile.get('template_sha256')==hashlib.sha256(blob).hexdigest() else None
    palette={rgb:ix for ix,rgb in book.colour_map.items() if rgb and 8<=ix<=63};used=set()
    for xf in book.xf_list:
        used.update([book.font_list[xf.font_index].colour_index,xf.background.pattern_colour_index,xf.background.background_colour_index])
        used.update(getattr(xf.border,side+'_colour_index') for side in ('left','right','top','bottom'))
    available=[ix for ix in range(63,7,-1) if ix not in used]
    def apply_display(st,name,part,c):
        if not profile:return st
        cell=profile['sheets'][name][part][c]
        for prop,key in [('fill','fill'),('font','font')]:
            rgb=int(cell[key]);rgb=(rgb&255,(rgb>>8)&255,(rgb>>16)&255)
            if rgb not in palette:
                if not available:raise ValueError('母版实际样式颜色过多，请核实母版')
                index=available.pop(0);out.set_colour_RGB(index,*rgb);palette[rgb]=index
            if prop=='fill':st.pattern.pattern=1;st.pattern.pattern_fore_colour=palette[rgb]
            else:st.font.colour_index=palette[rgb]
        return st
    styles={}
    def style(ix):
        if ix not in styles:styles[ix]=clone_style(book,ix)
        return copy.deepcopy(styles[ix])
    panel=financial_panel(items,meta)
    report_meta=copy.deepcopy(meta);fresh_stats=summary(groups['鲜食'],meta.get('sales_cost'))
    report_meta.setdefault('report',{}).update(fresh_enabled=True,fresh_gain=None if fresh_stats['盘盈'] is None else str(fresh_stats['盘盈']),fresh_loss=None if fresh_stats['盘亏'] is None else str(fresh_stats['盘亏']))
    report_meta['report'].setdefault('quarter',meta.get('period') or '季度待填写')
    report=report_document(items,report_meta)
    text='全店口径（常规商品＋鲜食，不重复累加）：\n'+report['generated']+'\n鲜食盈亏取本次鲜食明细；鲜食销售额和含税成本沿用已保存的独立经营参数。'
    manifest={'revision':revision,'total':len(items),'template_sha256':hashlib.sha256(blob).hexdigest(),'sheets':{},'uncertain':len(uncertain),'panel':panel,'report_text':text}
    for source,headers in zip(book.sheets(),(COMMON,FRESH)):
        rows=groups[source.name];sheet=out.add_sheet(source.name);n=len(headers);fresh=source.name==SHEETS[1]
        sheet.panes_frozen=True;sheet.horz_split_pos=1;sheet.remove_splits=True
        sheet.portrait=False;sheet.paper_size_code=9;sheet.fit_width_to_pages=1;sheet.fit_height_to_pages=0;sheet.print_scaling=100;sheet.set_fit_num_pages(1)
        sheet.footer_str=b'Page &P / &N'
        for c in range(n):
            info=source.colinfo_map.get(c);sheet.col(c).width=info.width if info else 2560;sheet.col(c).hidden=info.hidden if info else False
            sheet.write(0,c,headers[c],apply_display(style(source.cell_xf_index(0,c)),source.name,'header',c))
        sheet.row(0).height=max(400,source.rowinfo_map.get(0).height if 0 in source.rowinfo_map else 400);sheet.row(0).height_mismatch=True
        for r,item in enumerate(rows,1):
            values=row_values(item,fresh,uncertain.get(item['记录ID'],''));lines=1
            for c,value in enumerate(values):
                st=apply_display(style(source.cell_xf_index(1,c)),source.name,'body',c)
                if c in (0,1):st.num_format_str='@';st.alignment.shri=True
                if c==n-2:st.num_format_str='0.00'
                if c in (2,n-1):
                    st.alignment.wrap=True;st.alignment.vert=1
                    chars=max(4,sheet.col(c).width/256/2);lines=max(lines,math.ceil(len(str(value))/chars))
                sheet.write(r,c,xls_value(value),st)
            sheet.row(r).height=min(6000,max(300,lines*260));sheet.row(r).height_mismatch=True
        stats=summary(rows,meta.get('sales_cost'));total_row=len(rows)+1
        for c in range(n):
            st=style(source.cell_xf_index(source.nrows-1,c));st.font.bold=True
            sheet.write(total_row,c,'本表合计' if c==0 else xls_value(stats['净差异']) if c==n-2 else '',st)
        end_style=style(source.cell_xf_index(0,0));end_style.font.bold=False;end_style.alignment.wrap=True;end_style.alignment.vert=1
        status=f"审批准备资料·未审批；本表{len(rows)}条，已复盘{stats['已复盘']}，未复盘{stats['未复盘']}（未复盘差异为暂估）；本表盘盈{money(stats['盘盈'])}、盘亏{money(stats['盘亏'])}、净差异{money(stats['净差异'])}元"
        if stats['净差异'] is None:status+='；缺成本或数量，合计金额待核实'
        sheet.write_merge(total_row+2,total_row+2,0,n-1,status,end_style);sheet.row(total_row+2).height=520;sheet.row(total_row+2).height_mismatch=True
        # 整店口径与01完全一致，两个分表不能替代或重复累加整店口径。
        pairs=[('整店实际销售额',money(meta.get('sales_amount'))),('整店含税销售成本',money(meta.get('sales_cost'))),('整店盘盈',panel['gain'] or '待核实'),('整店盘亏',panel['loss'] or '待核实'),('整店净差异',panel['net'] or '待核实'),('整店净差异率',('待核实' if panel['rate'] is None else panel['rate']+'‰')),('2‰允许净损耗',panel['allowance'] or '待核实'),('整店净损耗',panel['net_loss'] or '待核实'),('整店剩余额度',panel['remaining'] or '待核实'),('测算状态',panel['status'])]
        for i,(label,value) in enumerate(pairs):
            r=total_row+4+i//2;offset=0 if i%2==0 else 8
            sheet.write_merge(r,r,offset,offset+2,label,end_style)
            val=decimal_value(value);value_style=copy.deepcopy(end_style);value_style.num_format_str='0.00'
            sheet.write_merge(r,r,offset+3,(7 if offset==0 else n-1),xls_value(val) if val is not None else value,value_style);sheet.row(r).height=400;sheet.row(r).height_mismatch=True
        text_style=copy.deepcopy(end_style);text_style.alignment.horz=1
        r=total_row+10;sheet.write_merge(r,r,0,n-1,text,text_style);sheet.row(r).height=min(8000,(sum(max(1,math.ceil(len(line)/95)) for line in text.splitlines())+1)*260);sheet.row(r).height_mismatch=True
        manifest['sheets'][source.name]={'count':len(rows),'ids':[x['记录ID'] for x in rows],'headers':list(headers),'amount':None if stats['净差异'] is None else str(stats['净差异']),'data_rows':[1,len(rows)],'total_row':total_row}
    stream=io.BytesIO();out.save(stream);return stream.getvalue(),manifest
