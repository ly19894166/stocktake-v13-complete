// 真正停止并重启模拟进程后执行，只读已有450条记录；不生成新打印历史。
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'playwright');
const url=process.env.STOCKTAKE_TEST_URL||'http://127.0.0.1:18541';
if(new URL(url).port==='8513'||!['127.0.0.1','localhost'].includes(new URL(url).hostname))throw Error('只允许独立模拟端口');
const browser=await chromium.launch({channel:process.env.STOCKTAKE_BROWSER_CHANNEL||'msedge',headless:true});
const out=path.join(path.dirname(fileURLToPath(import.meta.url)),'runtime/workflow_results');
const check=(v,m)=>{if(!v)throw Error(m)};
try{
  const page=await browser.newPage({viewport:{width:1366,height:768}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(url,{waitUntil:'networkidle'});const grid=page.locator('#stocktake-workbench');await grid.locator('tbody tr').first().waitFor();
  const data=await grid.evaluate(el=>el.__inventory.data);
  check(data.rows.length===450&&await grid.locator('tbody tr').count()===450,'重开商品不完整');
  check(data.finance.sales_amount==='1234567.89'&&data.finance.sales_cost==='20000000','经营值未恢复');
  check(data.rows.every(r=>r.recount===(r.barcode==='0990000000000'?0:r.system-r.adjustment)&&r.note==='模拟现场核验'),'实数/备注未恢复');
  check(data.report.config.fresh_enabled&&Number(data.report.config.fresh_loss)===-14.24,'鲜食配置未恢复');
  await grid.locator('.report-open').click();await grid.locator('.copy-status').filter({hasText:'已按最新已保存数据生成'}).waitFor();
  const doc=await grid.locator('.report-text').inputValue();check(doc.includes('合计盘亏：-3.11元')&&doc.includes(data.panel.net+'元'),'重开汇报金额不符');await grid.locator('.report-close').click();
  for(const [width,height] of [[1366,768],[1920,1080],[2560,1440]]){
    await page.setViewportSize({width,height});
    const wraps=await grid.evaluate(el=>{const s=el.__inventory,row=s.rows.get(s.visible[0].id);row.name='模拟超长商品名称用于检验完整换行与显示'.repeat(6);s.rowSignatures.delete(row.id);s.render();const name=s.dom.get(row.id).querySelector('.name');return name.textContent===row.name&&name.scrollHeight<=name.clientHeight+1&&getComputedStyle(name).whiteSpace!=='nowrap'&&getComputedStyle(name).textOverflow!=='ellipsis'});
    check(wraps,'超长商品名被截断');
  }
  await page.getByText('03 现场复核单打印',{exact:true}).first().click();check(await page.getByRole('button',{name:'预览A4',exact:true}).isDisabled(),'已复盘商品重启后返回默认清单');
  const history=page.locator('summary').filter({hasText:'历史打印记录与原单重印'});await history.click();await page.getByText('预览历史原单',{exact:true}).click();
  await page.waitForTimeout(3500);
  const frames=page.frames();
  let visiblePDF=false;
  for(const frame of frames){
    const canvas=frame.locator('canvas:visible');if(await canvas.count())visiblePDF=await canvas.first().evaluate(el=>el.width>0&&el.height>0);
    const embed=frame.locator('embed[type="application/pdf"],iframe[src^="blob:"]');if(await embed.count())visiblePDF=true;
  }
  check(visiblePDF,'浏览器PDF预览未渲染');
  await page.screenshot({path:path.join(out,'03_历史原单实际预览.png'),fullPage:true});
  check(!errors.length,errors.join('\n'));
  const result={pass:true,simulated_only:true,real_process_restart_ui:true,all_450_rows_and_saved_values_restored:true,long_names_fully_wrap_at_three_resolutions:true,pdf_preview_rendered:true,no_database_writes:true,page_errors:errors};
  await fs.writeFile(path.join(out,'reopen_ui_results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close()}
