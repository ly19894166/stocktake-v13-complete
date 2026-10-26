"""从零构造的审批母版，不含公司真实资料。"""
import io
import xlwt
from approval_reporting import COMMON,FRESH

def template(items=()):
    book=xlwt.Workbook();head=xlwt.easyxf('font: name 宋体,bold on; alignment: horiz center; borders: left thin,right thin,top thin,bottom thin;')
    body=xlwt.easyxf('font: name 宋体; pattern: pattern solid,fore_colour light_yellow; alignment: horiz center; borders: left thin,right thin,top thin,bottom thin;',num_format_str='0.00')
    for name,headers in [('常规商品',COMMON),('鲜食',FRESH)]:
        sheet=book.add_sheet(name)
        for c,label in enumerate(headers):
            sheet.write(0,c,label,head);sheet.col(c).width=(32 if c in (2,len(headers)-1) else 18 if c==1 else 12)*256
            sheet.write(1,c,'模拟旧批次_禁止复制' if c in (2,len(headers)-1) else '',body)
        sheet.col(6).hidden=True
        if items:
            item=items[0 if name=='常规商品' else -1]
            sheet.write(2,0,item.get('商家编码',''));sheet.write(2,1,item['商品条码']);sheet.write(2,2,'模拟旧批次_禁止复制')
        sheet.row(0).height=420;sheet.row(1).height=300
    stream=io.BytesIO();book.save(stream);return stream.getvalue()
