// 实际停止重启模拟进程后只读检查；不会创建新打印记录或改变实数。
import {createRequire} from 'node:module';import fs from 'node:fs/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'playwright'),url=process.env.STOCKTAKE_TEST_URL||'http://127.0.0.1:18544';
if(new URL(url).port==='8513'||!['localhost','127.0.0.1'].includes(new URL(url).hostname))throw Error('仅允许模拟端口');
const b=await chromium.launch({channel:process.env.STOCKTAKE_BROWSER_CHANNEL||'msedge',headless:true});const check=(v,m)=>{if(!v)throw Error(m)};
try{
 const p=await b.newPage({viewport:{width:1920,height:1080}});await p.goto(url,{waitUntil:'networkidle'});const grid=p.locator('#stocktake-workbench');await grid.locator('tbody tr').first().waitFor();const d=await grid.evaluate(el=>el.__inventory.data);
 check(d.rows.length===450&&d.rows.every(r=>r.recount!==null&&r.note==='模拟最终核验'),'实数备注未恢复');
 check(d.rows.filter(r=>r.supplier_status==='zbf').length===60&&d.rows.filter(r=>r.supplier_status==='pending').length===25,'目录归属未恢复');
 await p.getByText('02 公司盘点结果导出',{exact:true}).click();await p.locator('summary').filter({hasText:'卓不凡专项审计'}).click();await p.getByRole('textbox',{name:'专项核查说明（人工）',exact:true}).waitFor();
 check(await p.getByRole('textbox',{name:'专项核查说明（人工）',exact:true}).inputValue()==='模拟换货人工核对说明','说明未持久化');check(await p.getByRole('textbox',{name:'凭证编号',exact:true}).inputValue()==='SIM-PROOF-FOURTH','凭证未恢复');
 await p.getByText('03 现场复核单打印',{exact:true}).click();await p.getByText(/本次待复核：0条/).waitFor();await p.locator('summary').filter({hasText:'历史打印记录与原单重印'}).click();await p.getByText('预览历史原单',{exact:true}).click();await p.locator('canvas:visible').first().waitFor({timeout:30000});check(await p.locator('canvas:visible').first().evaluate(el=>el.width>0&&el.height>0),'历史PDF未渲染');
 const result={pass:true,simulated_only:true,actual_process_restart_ui:true,recounts_notes_and_catalog_restored:true,proof_restored:true,historical_pdf_rendered:true,no_database_writes:true};
 await fs.writeFile(path.join(path.dirname(fileURLToPath(import.meta.url)),'runtime/fourth_results/reopen_ui.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await b.close()}
