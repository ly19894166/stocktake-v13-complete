"""V13按需打印；只读取业务单元格，打印日志以OOXML追加，不改业务数据。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal, ROUND_HALF_UP
import argparse, hashlib, json, math, shutil, uuid, zipfile, tempfile, os
import xml.etree.ElementTree as ET
import sys
if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
from openpyxl import load_workbook
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.colors import HexColor
from xml.sax.saxutils import escape

def fmt(v):
 if isinstance(v,(int,float)): return format(v,'.4f').rstrip('0').rstrip('.')
 return str(v or '')

def render_pdf(pdf, rows, store, period, batch, pid, time, scope):
 font=Path(os.environ.get('STOCKTAKE_CJK_FONT', 'C:/Windows/Fonts/simhei.ttf'))
 if not font.exists(): raise RuntimeError('缺少可嵌入的中文字体 simhei.ttf，请安装黑体或修改字体路径。')
 pdfmetrics.registerFont(TTFont('InventoryCN',str(font)))
 style=ParagraphStyle('body',fontName='InventoryCN',fontSize=9.5,leading=11.5,textColor=HexColor('#203646'))
 cw=[26,58,176,95,43,43,43,65,249]
 W,H=landscape(A4); usable=W-44; cw[-1]+=usable-sum(cw)
 paragraphs=[]
 for x in rows:
  cells=[fmt(x['sequence']),x['category'],x['name'],x['barcode'],fmt(x['system']),fmt(x['initial']),fmt(x['difference']),'','']
  ps=[Paragraph(escape(str(t)),style) for t in cells]
  heights=[p.wrap(cw[i]-8,1000)[1] for i,p in enumerate(ps)]
  paragraphs.append((x,ps,max(24,max(heights)+6)))
 pages=[]; current=[]; total=0
 for entry in paragraphs:
  if current and total+entry[2]>438: pages.append(current);current=[];total=0
  current.append(entry);total+=entry[2]
 if current: pages.append(current)
 if not pages: raise RuntimeError('没有符合本次范围的待现场复盘项目；不生成空白PDF。')
 c=canvas.Canvas(pdf if hasattr(pdf,'write') else str(pdf),pagesize=(W,H),pageCompression=1)
 c.setTitle(store+' '+period+' A4现场复盘单');c.setAuthor('门店盘点 V1.3 / V13规则')
 headers=['序号','品类','商品名称','商品条码','系统数','初盘数','当前差异','复盘实际总数','备注／原因']
 for page,entries in enumerate(pages,1):
  c.setFont('InventoryCN',15);c.setFillColor(HexColor('#19364C'));c.drawString(22,H-29,store+'  A4现场复盘单')
  c.setFont('InventoryCN',9);c.drawRightString(W-22,H-27,f'{period}   第 {page}/{len(pages)} 页')
  c.drawString(22,H-46,f'打印批次 {pid}    生成 {time}    项目 {len(rows)} 条')
  c.drawString(22,H-62,f'范围：{scope}｜序号与工作台一致；填写实际总数，0为有效值。')
  y=H-77;c.setFillColor(HexColor('#244B65'));c.rect(22,y-25,usable,25,fill=1,stroke=0)
  c.setFont('InventoryCN',9);c.setFillColor(HexColor('#FFFFFF'));xpos=22
  for i,h in enumerate(headers): c.drawCentredString(xpos+cw[i]/2,y-16,h);xpos+=cw[i]
  y-=25
  for item,ps,rh in entries:
   c.setFillColor(HexColor('#F4F7F9') if item['sequence']%2==0 else HexColor('#FFFFFF'));c.rect(22,y-rh,usable,rh,fill=1,stroke=0)
   xpos=22
   for i,p in enumerate(ps):
    _,ph=p.wrap(cw[i]-8,rh)
    if i==6:p.style=ParagraphStyle('delta',parent=style,textColor=HexColor('#B52E2E' if item['difference']<0 else '#00805E' if item['difference']>0 else '#203646'))
    p.drawOn(c,xpos+4,y-(rh-ph)/2-ph)
    xpos+=cw[i]
   c.setStrokeColor(HexColor('#CED7DD'));c.setLineWidth(.35);c.line(22,y-rh,W-22,y-rh)
   xpos=22
   for width in cw:c.line(xpos,y,xpos,y-rh);xpos+=width
   c.line(W-22,y,W-22,y-rh);y-=rh
  c.setFont('InventoryCN',9);c.setFillColor(HexColor('#203646'));c.drawString(22,31,'复盘人：________________   复盘日期：________________   录入人：________________')
  c.setFont('InventoryCN',8);c.drawRightString(W-22,16,batch+'   '+pid)
  c.showPage()
 c.save();return len(pages)
