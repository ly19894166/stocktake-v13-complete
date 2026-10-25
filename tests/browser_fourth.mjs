// 第四次集中验收：只允许独立本机端口，全部数据从零构造。
import {createRequire} from 'node:module';import fs from 'node:fs/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.dirname(fileURLToPath(import.meta.url)),out=path.join(root,'runtime/fourth_results');await fs.mkdir(out,{recursive:true});
const url=process.env.STOCKTAKE_TEST_URL||'http://127.0.0.1:18544';if(new URL(url).port==='8513'||!['localhost','127.0.0.1'].includes(new URL(url).hostname))throw Error('禁止指向正式环境');
const browser=await chromium.launch({channel:process.env.STOCKTAKE_BROWSER_CHANNEL||'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1920,height:1080},permissions:['clipboard-read','clipboard-write']}),page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
const grid=page.locator('#stocktake-workbench'),check=(v,m)=>{if(!v)throw Error(m)},cases=[];
const data=()=>grid.evaluate(el=>el.__inventory.data);
const saved=async()=>{await page.waitForFunction(()=>{const h=[...document.querySelectorAll('*')].find(e=>e.shadowRoot?.querySelector('#stocktake-workbench'));const s=h?.shadowRoot.querySelector('#stocktake-workbench').__inventory;return s&&!s.inflight&&!s.queue.length&&!Object.keys(s.drafts).length&&!Object.keys(s.metaDrafts).length},{},{timeout:90000})};
const go=async label=>{await page.getByText(label,{exact:true}).first().click();await page.waitForTimeout(150)};
const expand=async text=>{const s=page.locator('summary').filter({hasText:text});if(await s.locator('..').getAttribute('open')===null)await s.click()};
const record=n=>{cases.push({name:n,pass:true});console.log(n)};
const upload=async()=>{await page.getByRole('button',{name:'上传盘点报表',exact:true}).click();await page.getByTestId('stFileUploader').filter({hasText:'上传盘点报表'}).locator('input[type=file]').setInputFiles(['模拟450初盘盘亏.xls','模拟450初盘盘盈.xls'].map(n=>path.join(root,'runtime/fourth_demo',n)));await grid.locator('tbody tr').first().waitFor({timeout:60000})};
const row=bc=>grid.locator('tbody tr').filter({has:page.getByRole('textbox',{name:'备注 '+bc,exact:true})});
const statCount=async()=>{const t=await page.getByText(/本次待复核：/).innerText();return Number(t.match(/本次待复核：(\d+)/)[1])};
const countIs=async n=>{await page.getByText(new RegExp('本次待复核：'+n+'条')).waitFor({timeout:30000});check(await statCount()===n,'打印数量错误')};
try{
 await page.goto(url,{waitUntil:'networkidle'});
 if(process.argv.includes('--final-export')){
   await grid.locator('tbody tr').first().waitFor();const rows=(await data()).rows;
   const paste=rows.map(r=>`${r.barcode}\t${r.barcode==='0990000000449'?0:r.system-r.adjustment}\t模拟最终核验\t模拟单位核对`).join('\n');
   await grid.locator('.bulk-toggle').click();await grid.locator('.bulk textarea').fill(paste);await grid.locator('.bulk-submit').click();await saved();
   await go('02 公司盘点结果导出');await expand('导出检查与剩余问题');
   for(const label of ['确认同门店、同期间且覆盖本次完整盘点范围','确认差异已核实、相关凭证齐备'])if(!await page.getByRole('checkbox',{name:label,exact:true}).isChecked())await page.getByText(label,{exact:true}).click();
   await page.getByRole('button',{name:'保存导出确认',exact:true}).click();
   const [d]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'下载公司盘点表.xls',exact:true}).click()]);await d.saveAs(path.join(out,'模拟公司最终450行.xls'));
   await go('03 现场复核单打印');check(await statCount()===0,'复盘完成后默认单未清空');
   record('450条含卓不凡仍全部进入公司三列真XLS，0有效，填写后退出默认单');
   await fs.writeFile(path.join(out,'company_browser.json'),JSON.stringify({pass:true,simulated_only:true,cases},null,2));
 }else{
   await page.getByRole('button',{name:'上传盘点报表',exact:true}).waitFor();await page.screenshot({path:path.join(out,'上传单入口.png')});
   await upload();let initial=await data();check(initial.rows.length===450,'没有导入450条');
   check(await page.getByRole('textbox',{name:/店名|日期|操作人/}).filter({visible:true}).count()===0,'仍要求元数据');
   const id=initial.batch,first=initial.rows[0];await row(first.barcode).locator('.edit-count').fill('0');await grid.locator('.search').click();await saved();
   await upload();check((await data()).batch===id&&(await data()).rows.find(r=>r.id===first.id).recount===0,'重复导入未恢复复盘');
   await row(first.barcode).locator('.edit-count').fill('');await grid.locator('.search').click();await saved();
   record('一个多文件控件同时上传两份并反向选择，直接进入450条；重复上传恢复实数和原批次');
   await go('更多工具');await page.getByTestId('stFileUploader').filter({hasText:'批量导入任意供应商Excel'}).locator('input[type=file]').setInputFiles(path.join(root,'runtime/fourth_demo/模拟供应商目录.xlsx'));
   await page.getByRole('button',{name:'校验并追加供应商目录',exact:true}).click();await page.getByText('供应商目录已校验并保存',{exact:true}).waitFor();await go('01 连续复盘找差异');await grid.locator('tbody tr').first().waitFor();
   const classified=(await data()).rows;check(classified.filter(r=>r.supplier_status==='zbf').length===60&&classified.filter(r=>r.supplier_status==='pending').length===25,'卓不凡或冲突分类错误');
   check(classified.filter(r=>r.supplier_status==='zbf').every(r=>r.supplier==='卓不凡'),'别名未规范显示');
   await grid.locator('.more-toggle').click();await grid.locator('.supplier').selectOption('卓不凡');check(await grid.locator('tbody tr').count()===60,'01供应商筛选未共用分类');await grid.locator('.clear').click();await grid.locator('.more-toggle').click();
   await grid.getByRole('textbox',{name:'实际销售金额（元）',exact:true}).fill('1234567.89');await grid.getByRole('textbox',{name:'同期含税销售成本（元）',exact:true}).fill('10000000');await grid.locator('.search').click();await saved();
   const resolutions=[];
   for(const [width,height] of [[1366,768],[1920,1080],[2560,1440]]){
     await page.setViewportSize({width,height});const positions=[];
     for(const index of [0,199,399]){
       await grid.evaluate((el,index)=>{const s=el.__inventory;if(index===0)s.scrollParent().scrollTop=0;else s.dom.get(s.visible[index].id).scrollIntoView({block:'center'})},index);await page.waitForTimeout(150);
       const measured=await grid.evaluate(el=>{const rail=el.querySelector('.summary-rail'),r=rail.getBoundingClientRect(),head=el.querySelector('th').getBoundingClientRect();return {top:r.top,bottom:r.bottom,metrics:rail.querySelectorAll('.metric').length,allReadable:[...rail.querySelectorAll('.metric')].every(e=>{const b=e.getBoundingClientRect();return b.left>=0&&b.right<=innerWidth&&e.scrollWidth<=e.clientWidth+2}),header_top:head.top,tableOverflow:el.querySelector('table').scrollWidth>el.querySelector('.table-wrap').clientWidth+2}});
       check(measured.metrics===7&&measured.top>=60&&measured.bottom<height&&measured.header_top>=measured.bottom-1&&!measured.tableOverflow&&measured.allReadable,'悬浮汇总遮挡或不可读');positions.push({row:index+1,...measured});
       await page.screenshot({path:path.join(out,`01_${width}_第${index+1}条.png`)});
     }
     resolutions.push({width,height,positions});
   }
   const target=(await data()).rows[399];await row(target.barcode).locator('.edit-count').fill('0');const pos=await grid.evaluate(el=>el.__inventory.scrollParent().scrollTop);await saved();
   check(await grid.evaluate((el,p)=>Math.abs(el.__inventory.scrollParent().scrollTop-p)<60&&el.getRootNode().activeElement===el.__inventory.dom.get(el.__inventory.visible[399].id).querySelector('.edit-count'),pos),'深处保存失焦/回顶');
   const updated=await data();check((await grid.locator('.summary-rail').textContent()).includes(updated.panel.net),'悬浮金额未更新');
   await row(target.barcode).locator('.edit-count').fill('');await grid.locator('.search').click();await saved();
   record('三种窗口第1/200/400条七项统计常驻可读、不遮表头；深处填0实时更新且不失焦、不回顶');
   const fullPanel=(await data()).panel;
   await go('02 公司盘点结果导出');await expand('卓不凡专项审计');await page.getByRole('button',{name:'下载卓不凡专项审计Excel',exact:true}).waitFor();
   check((await page.getByText(/卓不凡：60条/).innerText()).includes('供货商待确认25条'),'02数量摘要不一致');
   check((await page.getByText(/疑似A换B 900对/).count())===1,'A换B对数不是900');
   await page.getByRole('textbox',{name:'专项核查说明（人工）',exact:true}).fill('模拟换货人工核对说明');await page.getByRole('textbox',{name:'凭证编号',exact:true}).fill('SIM-PROOF-FOURTH');
   await page.getByRole('button',{name:'保存专项说明与凭证',exact:true}).click();await page.getByText('专项说明与凭证已保存',{exact:true}).waitFor();
   await page.reload({waitUntil:'networkidle'});await go('02 公司盘点结果导出');await expand('卓不凡专项审计');
   check(await page.getByRole('textbox',{name:'专项核查说明（人工）',exact:true}).inputValue()==='模拟换货人工核对说明','重载后人工说明未持久化');
   const [audit]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'下载卓不凡专项审计Excel',exact:true}).click()]);await audit.saveAs(path.join(out,'模拟卓不凡专项审计.xlsx'));await page.screenshot({path:path.join(out,'02_卓不凡专项审计.png')});
   record('02专项审计60条/25待确认/900线索对，人工说明及凭证保存，独立Excel实际下载');
   await go('03 现场复核单打印');check(await statCount()===390,'默认未排除60条卓不凡');
   await page.getByText('包含卓不凡商品',{exact:true}).click();await countIs(450);await page.getByText('包含卓不凡商品',{exact:true}).click();await countIs(390);
   await page.getByText('仅打印卓不凡',{exact:true}).click();await countIs(60);await page.getByText('仅打印卓不凡',{exact:true}).click();await countIs(390);
   await page.getByText('打印供货商待确认商品',{exact:true}).click();await countIs(365);await page.getByText('打印供货商待确认商品',{exact:true}).click();await countIs(390);
   await page.screenshot({path:path.join(out,'03_品类找货默认排除卓不凡.png')});
   await page.getByRole('button',{name:'预览A4',exact:true}).click();await page.getByText(/当前A4预览/).waitFor();const [pdf]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'下载当前预览PDF',exact:true}).click()]);await pdf.saveAs(path.join(out,'模拟默认现场单.pdf'));
   await page.getByRole('button',{name:'生成并保存PDF',exact:true}).click();await page.getByText(/打印记录已保存/).waitFor();await expand('历史打印记录与原单重印');
   const countText=page.getByText(/共\d+份历史记录/);const n=Number((await countText.innerText()).match(/共(\d+)/)[1]);
   await page.getByRole('button',{name:'原单重印并登记',exact:true}).click();await page.getByText('共'+(n+1)+'份历史记录',{exact:true}).waitFor();
   await page.getByRole('button',{name:'按历史范围使用最新数据生成新单',exact:true}).click();await page.getByText('共'+(n+2)+'份历史记录',{exact:true}).waitFor();
   record('03默认390/包含450/仅卓不凡60/不含待确认365，实际预览下载/留档/原单重印/按最新筛选新单');
   await go('01 连续复盘找差异');await grid.locator('tbody tr').first().waitFor();check(JSON.stringify((await data()).panel)===JSON.stringify(fullPanel),'打印排除改变整店2‰');
   await grid.locator('.report-open').click();await grid.locator('.copy-status').filter({hasText:'已按最新已保存数据生成'}).waitFor();await grid.locator('.report-copy').click();await grid.locator('.copy-status').filter({hasText:'已复制最新已保存'}).waitFor();
   check((await page.evaluate(()=>navigator.clipboard.readText())).includes(fullPanel.net+'元'),'汇报金额回退');await grid.locator('.report-close').click();
   record('03排除仅用于打印，不改变整店盈亏/2‰；季度汇报仍生成并复制最新值');
   check(!errors.length,errors.join('\n'));await fs.writeFile(path.join(out,'browser_fourth_results.json'),JSON.stringify({pass:true,simulated_only:true,cases,resolutions,page_errors:errors},null,2));
 }
}catch(e){await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});await fs.writeFile(path.join(out,'failure.json'),JSON.stringify({error:String(e),cases,page_errors:errors},null,2));throw e}
finally{await browser.close()}
