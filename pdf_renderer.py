"""A4现场找货单：醒目名称、关联线索、大尺寸实数填写框。"""
from pathlib import Path
import os
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.colors import HexColor

def fmt(value):
    if value is None:return ''
    if isinstance(value,(int,float)):return format(value,'.4f').rstrip('0').rstrip('.') if '.' in format(value,'.4f') else str(value)
    return str(value)

def render_pdf(pdf,rows,store,period,batch,pid,time,scope):
    font=Path(os.environ.get('STOCKTAKE_CJK_FONT','C:/Windows/Fonts/simhei.ttf'))
    if not font.exists():raise RuntimeError('缺少中文TrueType字体，请设置STOCKTAKE_CJK_FONT或安装黑体。')
    pdfmetrics.registerFont(TTFont('InventoryCN',str(font)))
    pdfmetrics.registerFontFamily('InventoryCN',normal='InventoryCN',bold='InventoryCN')
    base=ParagraphStyle('cell',fontName='InventoryCN',fontSize=9,leading=12,textColor=HexColor('#203646'))
    name_style=ParagraphStyle('product',parent=base,fontSize=11,leading=14)
    W,H=landscape(A4);usable=W-44
    widths=[26,50,180,100,46,46,50,110,usable-708]
    entries=[]
    for row in rows:
        product='<b>'+escape(row['name'])+'</b>'
        if row.get('related'):product+='<br/><font size="8" color="#47756C">'+escape(row['related'])+'</font>'
        cells=[fmt(row['sequence']),row['category'],product,row['barcode'],fmt(row['system']),fmt(row['initial']),fmt(row['difference']),'','']
        paragraphs=[Paragraph(str(v) if i==2 else escape(str(v)),name_style if i==2 else base) for i,v in enumerate(cells)]
        height=max(44,max(p.wrap(widths[i]-8,10000)[1] for i,p in enumerate(paragraphs))+10)
        if height>438:raise ValueError('商品名称或关联线索过长，无法在A4单行中清晰显示，请先核对商品资料')
        entries.append((row,paragraphs,height))
    if not entries:raise ValueError('本次没有可打印商品，不生成空白单。')
    # 相邻同组尽量不跨页；大尺寸填写框至少34pt高。
    blocks=[];i=0
    while i<len(entries):
        entry=entries[i];block=[entry]
        if i+1<len(entries) and entry[0].get('group') and entries[i+1][0].get('group')==entry[0]['group'] and entry[2]+entries[i+1][2]<=438:
            block.append(entries[i+1]);i+=1
        blocks.append(block);i+=1
    pages=[];page=[];height=0
    for block in blocks:
        needed=sum(x[2] for x in block)
        if page and height+needed>438:pages.append(page);page=[];height=0
        page.extend(block);height+=needed
    if page:pages.append(page)
    c=canvas.Canvas(pdf if hasattr(pdf,'write') else str(pdf),pagesize=(W,H),pageCompression=1)
    c.setTitle(store+' '+period+' A4现场复核单');c.setAuthor('本地盘点客户端')
    headers=['序号','品类','商品名称 / 疑似关联','商品条码','系统数','初盘数','最新差异','现场复盘实数','备注']
    for number,page in enumerate(pages,1):
        c.setFillColor(HexColor('#19364C'));c.setFont('InventoryCN',15);c.drawString(22,H-28,store+' 现场复核单')
        c.setFont('InventoryCN',9);c.drawRightString(W-22,H-26,f'{period} · 第{number}/{len(pages)}页')
        c.drawString(22,H-45,f'打印批次 {pid} · {time} · 共{len(rows)}条')
        c.drawString(22,H-61,f'{scope} · 疑似线索待核实，不自动抵销；现场填写实物总数，0为有效值。')
        y=H-77;c.setFillColor(HexColor('#244B65'));c.rect(22,y-25,usable,25,fill=1,stroke=0)
        c.setFont('InventoryCN',9);c.setFillColor(HexColor('#FFFFFF'));left=22
        for width,label in zip(widths,headers):c.drawCentredString(left+width/2,y-16,label);left+=width
        y-=25
        for row,paragraphs,rh in page:
            c.setFillColor(HexColor('#F1F8F5') if row.get('group') else HexColor('#FFFFFF'));c.rect(22,y-rh,usable,rh,fill=1,stroke=0)
            left=22
            for i,p in enumerate(paragraphs):
                if i==6:p.style=ParagraphStyle('difference',parent=base,textColor=HexColor('#B52E2E' if row['difference']<0 else '#00805E'))
                _,ph=p.wrap(widths[i]-8,rh);p.drawOn(c,left+4,y-(rh-ph)/2-ph)
                if i==7:
                    c.setLineWidth(.8);c.setStrokeColor(HexColor('#6A858D'));c.rect(left+5,y-rh+5,widths[i]-10,rh-10,fill=0,stroke=1)
                left+=widths[i]
            c.setStrokeColor(HexColor('#CAD8DD'));c.setLineWidth(.35);c.line(22,y-rh,W-22,y-rh);left=22
            for width in widths:c.line(left,y,left,y-rh);left+=width
            c.line(W-22,y,W-22,y-rh);y-=rh
        c.setFillColor(HexColor('#203646'));c.setFont('InventoryCN',9);c.drawString(22,30,'复盘人：____________   日期：____________   录入人：____________')
        c.setFont('InventoryCN',8);c.drawRightString(W-22,15,batch+' · '+pid);c.showPage()
    c.save();return len(pages)
