// 实际停止并重新启动18532测试进程后运行，只读取已有模拟批次。
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({channel:process.env.STOCKTAKE_BROWSER_CHANNEL||'msedge',headless:true});
try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(process.env.STOCKTAKE_TEST_URL||'http://127.0.0.1:18532',{waitUntil:'networkidle'});
  const grid=page.locator('#stocktake-workbench');await grid.locator('tbody tr').first().waitFor({timeout:20000});
  const data=await grid.evaluate(el=>el.__inventory.data);
  if(data.finance.sales_amount!=='54321.98'||data.finance.sales_cost!=='100000'||data.rows.some(x=>x.recount!==20||x.note!=='模拟核验'))throw new Error('进程重启后经营金额或复盘/备注未恢复');
  if(!data.report.config.fresh_enabled||!data.report.config.reason_confirmed||data.panel.net!=='0.00')throw new Error('汇报配置/最新计算未恢复');
  await grid.getByRole('button',{name:'生成盘点汇报',exact:true}).click();
  const report=grid.getByRole('dialog',{name:'季度盘点汇报'});
  if(!(await report.getByRole('textbox',{name:'最终盘点汇报文稿',exact:true}).inputValue()).includes('合计差异金额：0.00元'))throw new Error('旧稿冒充最新数字');
  await report.getByRole('button',{name:'关闭',exact:true}).click();
  for(const [width,height] of [[1366,768],[1920,1080],[2560,1440]]){
    await page.setViewportSize({width,height});
    const wraps=await grid.evaluate(el=>{const s=el.__inventory,row=s.rows.get(s.visible[0].id);row.name='模拟超长商品名称用于检验完整换行与显示'.repeat(6);s.render();const name=s.dom.get(row.id).querySelector('.name');return name.textContent===row.name&&name.scrollHeight<=name.clientHeight+1&&getComputedStyle(name).whiteSpace!=='nowrap'&&getComputedStyle(name).textOverflow!=='ellipsis'});
    if(!wraps)throw new Error('长商品名称被截断');
  }
  if(errors.length)throw new Error(errors.join('\n'));
  console.log(JSON.stringify({pass:true,real_process_restart_ui:true,finances_recounts_notes_report_config_restored:true,stale_draft_not_used_as_current:true,long_names_fully_wrap_at_three_resolutions:true,page_errors:errors}));
}finally{await browser.close()}
