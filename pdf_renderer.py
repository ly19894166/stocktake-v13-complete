"""省纸A4现场数货单：只打印找货与实数，不打印任何配对算法线索。"""
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
    if isinstance(value,(int,float)):return format(value,'.4f').rstrip('0').rstrip('.')
    return str(value)

def render_pdf(pdf,rows,store,period,batch,pid,time,scope):
    font=Path(os.environ.get('STOCKTAKE_CJK_FONT','C:/Windows/Fonts/simhei.ttf'))
    if not font.exists():raise RuntimeError('缺少中文TrueType字体，请设置STOCKTAKE_CJK_FONT或安装黑体。')
    pdfmetrics.registerFont(TTFont('InventoryCN',str(font)))
    pdfmetrics.registerFontFamily('InventoryCN',normal='InventoryCN',bold='InventoryCN')
    base=ParagraphStyle('cell',fontName='InventoryCN',fontSize=9,leading=11,textColor=HexColor('#203646'))
    name_style=ParagraphStyle('product',parent=base,fontSize=10.5,leading=12)
    numeric=ParagraphStyle('number',parent=base,alignment=2)
    W,H=landscape(A4);usable=W-36
    widths=[28,75,305,112,58,58,62,usable-698]
    entries=[];capacity=H-102
    for row in rows:
        cells=[fmt(row['sequence']),row['category'],'<b>'+escape(row['name'])+'</b>',row['barcode'],fmt(row['system']),fmt(row['initial']),fmt(row['difference']),'']
        ps=[Paragraph(str(v) if i==2 else escape(str(v)),name_style if i==2 else numeric if i in (0,4,5,6) else base) for i,v in enumerate(cells)]
        height=max(28,max(p.wrap(widths[i]-8,10000)[1] for i,p in enumerate(ps))+6)
        if height>capacity:raise ValueError('商品名称过长，无法在A4单行完整打印，请核对商品资料')
        entries.append((row,ps,height))
    if not entries:raise ValueError('本次没有可打印商品，不生成空白单。')
    pages=[];page=[];used=0
    for entry in entries:
        if page and used+entry[2]>capacity:pages.append(page);page=[];used=0
        page.append(entry);used+=entry[2]
    if page:pages.append(page)
    c=canvas.Canvas(pdf if hasattr(pdf,'write') else str(pdf),pagesize=(W,H),pageCompression=1)
    c.setTitle(store+' '+period+' A4现场复核单');c.setAuthor('本地盘点客户端')
    headers=['序号','品类','商品名称','商品条码','系统数','初盘数','最新差异','现场复盘实数']
    for number,page in enumerate(pages,1):
        c.setFillColor(HexColor('#19364C'));c.setFont('InventoryCN',13);c.drawString(18,H-20,store+' 现场复核单')
        c.setFont('InventoryCN',9);c.drawRightString(W-18,H-19,f'{period} · 第{number}/{len(pages)}页')
        c.setFont('InventoryCN',8);c.drawString(18,H-34,f'{scope} · 共{len(rows)}条 · 实数填实物总数，0有效 · {pid} · {time}')
        y=H-42;c.setFillColor(HexColor('#244B65'));c.rect(18,y-22,usable,22,fill=1,stroke=0)
        c.setFillColor(HexColor('#FFFFFF'));c.setFont('InventoryCN',9);left=18
        for width,label in zip(widths,headers):c.drawCentredString(left+width/2,y-14,label);left+=width
        y-=22
        for index,(row,ps,height) in enumerate(page):
            c.setFillColor(HexColor('#F8FAFB') if index%2 else HexColor('#FFFFFF'));c.rect(18,y-height,usable,height,fill=1,stroke=0)
            left=18
            for i,p in enumerate(ps):
                if i==6:p.style=ParagraphStyle('difference',parent=numeric,textColor=HexColor('#B52E2E' if row['difference']<0 else '#00805E' if row['difference']>0 else '#203646'))
                _,ph=p.wrap(widths[i]-8,height);p.drawOn(c,left+4,y-(height-ph)/2-ph)
                if i==7:
                    c.setStrokeColor(HexColor('#6A858D'));c.setLineWidth(.65);c.rect(left+5,y-height+3,widths[i]-10,height-6,fill=0,stroke=1)
                left+=widths[i]
            c.setStrokeColor(HexColor('#CAD8DD'));c.setLineWidth(.35);c.line(18,y-height,W-18,y-height);left=18
            for width in widths:c.line(left,y,left,y-height);left+=width
            c.line(W-18,y,W-18,y-height);y-=height
        c.setFillColor(HexColor('#203646'));c.setFont('InventoryCN',8);c.drawString(18,14,'复盘人：____________   日期：____________   录入人：____________')
        c.drawRightString(W-18,14,batch);c.showPage()
    c.save();return len(pages)
