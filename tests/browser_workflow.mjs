// 全部样本和截图仅为模拟；在18541独立数据目录执行，绝不能指向正式库。
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'playwright');
const here=path.dirname(fileURLToPath(import.meta.url)),out=path.join(here,'runtime/workflow_results');await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:process.env.STOCKTAKE_BROWSER_CHANNEL||'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1366,height:768},permissions:['clipboard-read','clipboard-write']});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const testURL=process.env.STOCKTAKE_TEST_URL||'http://127.0.0.1:18541';
if(new URL(testURL).port==='8513'||!['127.0.0.1','localhost'].includes(new URL(testURL).hostname))throw new Error('模拟验收只允许独立本机端口，禁止正式8513');
const check=(v,message)=>{if(!v)throw new Error(message)};
const resume=process.argv.includes('--resume-output');
let results={simulated_only:true,pass:false,cases:[],resolutions:[]};
if(resume){results=JSON.parse(await fs.readFile(path.join(out,'browser_failure.json'),'utf8'));delete results.error;delete results.debug;}
const record=(name,detail=true)=>{results.cases.push({name,pass:true,detail});console.log(name)};
const grid=page.locator('#stocktake-workbench');
const data=()=>grid.evaluate(el=>el.__inventory.data);
const saved=async()=>{await page.waitForTimeout(80);await page.waitForFunction(()=>{const host=[...document.querySelectorAll('*')].find(e=>e.shadowRoot?.querySelector('#stocktake-workbench'));const s=host?.shadowRoot.querySelector('#stocktake-workbench').__inventory;return s&&!s.inflight&&!s.queue.length&&!Object.keys(s.drafts).length&&!Object.keys(s.metaDrafts).length},{},{timeout:90000})};
const row=bc=>grid.locator('tbody tr').filter({has:page.getByRole('textbox',{name:`备注 ${bc}`,exact:true})});
const search=()=>grid.getByRole('textbox',{name:'搜索商品名、编码、完整条码或尾号'});
const go=async label=>{await page.getByText(label,{exact:true}).first().click();await page.waitForTimeout(250)};
const expand=async text=>{const s=page.locator('summary').filter({hasText:text});if(await s.locator('..').getAttribute('open')===null)await s.click()};
try{
  await page.goto(testURL,{waitUntil:'networkidle'});
  if(!resume){
  const settings=page.locator('summary').filter({hasText:/切换批次、导入与设置|当前批次 \/ 切换、导入与设置/});
  if(await settings.count()&&await settings.locator('..').getAttribute('open')===null)await settings.click();
  await expand('导入新的初盘 / 恢复已有批次');
  await page.locator('input[type=file]').nth(0).setInputFiles(path.join(here,'runtime/workflow_demo/模拟450盘盈.xls'));
  await page.getByText('模拟450盘盈.xls',{exact:true}).waitFor();
  await page.locator('input[type=file]').nth(1).setInputFiles(path.join(here,'runtime/workflow_demo/模拟450盘亏.xls'));
  await grid.locator('tbody tr').first().waitFor({timeout:60000});
  await page.waitForFunction(()=>{const h=[...document.querySelectorAll('*')].find(e=>e.shadowRoot?.querySelector('#stocktake-workbench'));return h?.shadowRoot.querySelector('#stocktake-workbench').__inventory.visible.length===450});
  check(await grid.locator('tbody tr').count()===450,'未连续加载全部450条');
  check(await grid.getByRole('button',{name:/上一页|下一页/}).count()===0,'仍存在分页');
  record('两表导入450条直接进入连续工作台，无分页');
  for(const [width,height] of [[1366,768],[1920,1080],[2560,1440]]){
    await page.setViewportSize({width,height});await page.waitForTimeout(200);
    const layout=await grid.evaluate(el=>{const t=el.querySelector('table'),w=el.querySelector('.table-wrap');return {columns:t.querySelectorAll('th').length,table_width:t.getBoundingClientRect().width,overflow:w.scrollWidth>w.clientWidth+2,inside:[...t.querySelectorAll('tr:first-child td')].every(x=>x.getBoundingClientRect().right<=innerWidth),internalScroll:getComputedStyle(w).overflowY!=='visible'}});
    check(!layout.overflow&&layout.inside&&!layout.internalScroll,'关键数据截断或表格内部滚动');results.resolutions.push({width,height,...layout});
  }
  await page.setViewportSize({width:1366,height:768});
  const initial=await data(),a=initial.rows.find(x=>x.barcode==='0990000000000'),b=initial.rows.find(x=>x.barcode==='0990000000001');
  const domIDs=await grid.locator('tbody tr').evaluateAll(xs=>xs.map(x=>x.dataset.id));
  check(Math.abs(domIDs.indexOf(a.id)-domIDs.indexOf(b.id))===1,'明确一对一没有联排');
  check((await row(a.barcode).innerText()).includes(b.name)&&(await row(b.barcode).innerText()).includes(a.name),'主行没有直接显示对应名称');
  check(new Set(domIDs).size===450&&initial.rows.length===450,'关联商品重复计数');
  await row(a.barcode).locator('.edit-count').fill('5');await search().click();await saved();
  const current=(await data()).rows.find(x=>x.id===a.id);
  check(current.initial_diff===-2888&&current.diff===-2884&&current.change===4&&current.amount===-1816.92,'找回4件算错');
  check((await row(a.barcode).innerText()).includes('找回4件'),'变化结果未显示');
  await row(a.barcode).locator('.edit-note').fill('模拟人工备注保持独立');await search().click();await saved();
  record('系统2889、初盘1、复盘5：-2888→-2884，找回4件，成本-1816.92');
  await row(b.barcode).locator('.edit-count').fill('20');await search().click();await saved();
  check(await row(a.barcode).locator('.peer-live').count()===0&&await row(b.barcode).locator('.peer-live').count()===0,'归零关联未撤销');
  check((await row(a.barcode).locator('.edit-note').inputValue())==='模拟人工备注保持独立','备注被提示覆盖');
  await row(b.barcode).locator('.edit-count').fill('24');await search().click();await saved();
  check(await row(a.barcode).locator('.peer-live').count()>0,'恢复差异未重新识别');
  const beforeMulti=(await data()).rows.find(x=>x.barcode==='0990000000002').candidate_count;
  await row('0990000000003').locator('.edit-count').fill('20');await search().click();await saved();
  check((await data()).rows.find(x=>x.barcode==='0990000000002').candidate_count===beforeMulti-1,'误删多对多其他候选');
  await row('0990000000003').locator('.edit-count').fill('10');await search().click();await saved();
  record('一对一和多对多归零/恢复，其他候选及人工备注保留');
  await grid.getByRole('textbox',{name:'实际销售金额（元）',exact:true}).fill('1234567.89');
  await grid.getByRole('textbox',{name:'同期含税销售成本（元）',exact:true}).fill('10000000');await search().click();await saved();
  await row(a.barcode).locator('.row-link').click();await grid.locator('.panel .pair-card').first().waitFor();
  await grid.locator('.panel .close-panel').click();
  await grid.evaluate(el=>{el.__inventory.scrollParent().scrollTop=0});
  await page.screenshot({path:path.join(out,'01_连续找差异_1366.png'),fullPage:true});
  // 真实鼠标滚轮连续到底，所有商品行一直存在，不靠下一页。
  await page.mouse.move(1150,650);const scrolls=[];let bottom=false;
  for(let i=0;i<90;i++){
    await page.mouse.wheel(0,2200);await page.waitForTimeout(30);
    const s=await grid.evaluate(el=>{const sc=el.__inventory.scrollParent();return {top:sc.scrollTop,bottom:sc.scrollTop+sc.clientHeight>=sc.scrollHeight-3,visible:[...el.querySelectorAll('tbody tr')].some(x=>{const r=x.getBoundingClientRect();return r.bottom>80&&r.top<innerHeight})}});
    scrolls.push(s.top);check(s.visible,'连续滚动出现大片空白');if(s.bottom){bottom=true;break}
  }
  check(bottom&&scrolls.every((v,i)=>i===0||v>=scrolls[i-1]-3),'未滚动到底或发生回顶');
  record('鼠标滚轮从第一条连续到底，450条始终无空白和回顶',{wheel_steps:scrolls.length,last_scroll:scrolls.at(-1)});
  // 在深处保留焦点并自动保存，验证DOM和滚动锚点稳定。
  const middle=await grid.evaluate(el=>{const sc=el.__inventory.scrollParent();sc.scrollTop=sc.scrollHeight*.5;return true});await page.waitForTimeout(200);
  const target=await grid.evaluate(el=>{for(const r of el.__inventory.visible){const tr=el.__inventory.dom.get(r.id),box=tr.getBoundingClientRect();if(box.top>160&&box.bottom<innerHeight-20)return r}return el.__inventory.visible[220]});
  const input=row(target.barcode).locator('.edit-note');await input.fill('模拟深处连续输入');
  const position=await grid.evaluate(el=>el.__inventory.scrollParent().scrollTop);await saved();
  const continuity=await grid.evaluate((el,id)=>({scroll:el.__inventory.scrollParent().scrollTop,focused:el.getRootNode().activeElement===el.__inventory.dom.get(id).querySelector('.edit-note')}),target.id);
  check(Math.abs(continuity.scroll-position)<80&&continuity.focused,'保存后跳动或失焦');
  await row(target.barcode).locator('.row-link').click();await grid.locator('.panel .pair-card').first().waitFor();await grid.locator('.panel .close-panel').click();
  check(Math.abs((await grid.evaluate(el=>el.__inventory.scrollParent().scrollTop))-position)<80,'打开关闭详情回顶');
  record('深处输入自动保存及详情开关保持滚动位置和输入焦点');
  const stress=(await grid.evaluate(el=>el.__inventory.visible)).slice(25,225);
  const start=Date.now();
  for(const [index,item] of stress.entries()){
    await row(item.barcode).locator('.edit-count').fill(String(item.initial));await row(item.barcode).locator('.edit-count').press('Enter');
    if(index%20===0)await row(item.barcode).locator('.edit-note').fill('模拟连续输入'+index);
    if(index%50===49)console.log('连续实数输入已完成',index+1);
  }
  await search().click();await saved();const afterStress=await data();
  check(stress.every(r=>afterStress.rows.find(x=>x.id===r.id).recount===r.initial),'连续200条有丢失');
  record('连续200条实数及穿插备注全部保存',{rows:200,elapsed_ms:Date.now()-start});
  await grid.getByRole('combobox',{name:'找货查看方式',exact:true}).selectOption('amount');
  check((await grid.locator('tbody tr').count())===450,'按金额找货漏记录');
  await grid.getByRole('combobox',{name:'找货查看方式',exact:true}).selectOption('pair');
  record('按金额找货与疑似联排两种视图保留450条唯一记录');
  // 人为延迟发出保存请求，必须等快照屏障后才能复制新成本和最新金额。
  await grid.evaluate(el=>{const s=el.__inventory,original=s.pump,until=performance.now()+1000;s.pump=()=>{const remaining=until-performance.now();if(remaining>0){clearTimeout(s.testDelay);s.testDelay=setTimeout(()=>{s.pump=original;original()},remaining)}else{s.pump=original;original()}}});
  await page.evaluate(()=>navigator.clipboard.writeText('SIMULATED_CLIPBOARD_SENTINEL'));
  await grid.getByRole('textbox',{name:'同期含税销售成本（元）',exact:true}).fill('20000000');
  await grid.getByRole('button',{name:'生成盘点汇报',exact:true}).click();
  const report=grid.getByRole('dialog',{name:'季度盘点汇报'});
  await report.getByRole('button',{name:'一键复制文稿',exact:true}).click();
  check((await page.evaluate(()=>navigator.clipboard.readText()))==='SIMULATED_CLIPBOARD_SENTINEL','保存未完成已复制旧稿');
  await report.locator('.copy-status').filter({hasText:'已复制最新已保存'}).waitFor({timeout:90000});
  let copied=await page.evaluate(()=>navigator.clipboard.readText());
  check(copied.includes('20000000.00元')&&copied.includes((await data()).panel.net+'元'),'复制稿金额不是最新');
  record('刚改成本立即复制：等待保存与最新快照，未复制旧金额');
  await report.getByRole('button',{name:'关闭',exact:true}).click();await saved();
  await page.evaluate(()=>navigator.clipboard.writeText('SIMULATED_SAVE_FAILURE_SENTINEL'));
  await grid.getByRole('textbox',{name:'同期含税销售成本（元）',exact:true}).fill('-1');
  await grid.getByRole('button',{name:'生成盘点汇报',exact:true}).click();await report.getByRole('button',{name:'一键复制文稿',exact:true}).click();
  await report.locator('.copy-status').filter({hasText:'保存失败，未复制'}).waitFor({timeout:30000});
  check((await page.evaluate(()=>navigator.clipboard.readText()))==='SIMULATED_SAVE_FAILURE_SENTINEL','保存失败仍覆盖剪贴板');
  await report.getByRole('button',{name:'关闭',exact:true}).click();
  await grid.getByRole('textbox',{name:'同期含税销售成本（元）',exact:true}).fill('20000000');await search().click();await saved();
  record('保存失败明确提示未复制，剪贴板保持原样');
  await grid.getByRole('button',{name:'生成盘点汇报',exact:true}).click();
  await report.getByRole('checkbox',{name:'附加独立鲜食盘点数据',exact:true}).check();await saved();
  const netBefore=(await data()).panel.net;
  for(const [name,value] of [['鲜食销售金额（元）','1000'],['鲜食含税成本（元）','800'],['鲜食盘盈（正数或0）','11.13'],['鲜食盘亏（负数或0）','-14.24']])await report.getByRole('textbox',{name,exact:true}).fill(value);
  await report.locator('.panel-title').click();await saved();
  check((await report.getByRole('textbox',{name:'最终盘点汇报文稿',exact:true}).inputValue()).includes('合计盘亏：-3.11元'),'鲜食汇报异常');
  check((await data()).panel.net===netBefore,'鲜食重复加总');await report.getByRole('button',{name:'关闭',exact:true}).click();await saved();
  record('季度汇报、鲜食独立、同期成本与2‰功能保留');
  }
  await go('03 现场复核单打印');
  await page.screenshot({path:path.join(out,'03_现场复核单打印.png'),fullPage:true});
  await page.getByRole('button',{name:'预览A4',exact:true}).click();await page.getByText(/当前A4预览/).waitFor({timeout:30000});
  const [preview]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'下载当前预览PDF',exact:true}).click()]);await preview.saveAs(path.join(out,'模拟现场复核单.pdf'));
  await page.getByRole('button',{name:'生成并保存PDF',exact:true}).click();await page.waitForTimeout(600);
  const history=page.locator('summary').filter({hasText:'历史打印记录与原单重印'});if(await history.locator('..').getAttribute('open')===null)await history.click();
  await page.getByRole('button',{name:'原单重印并登记',exact:true}).click();await page.waitForTimeout(500);
  await expand('历史打印记录与原单重印');await page.getByRole('button',{name:'按历史范围使用最新数据生成新单',exact:true}).click();await page.waitForTimeout(500);
  record('03默认按最新状态打印，实际A4预览、留档、原单重印、新数据新单');
  await go('02 公司盘点结果导出');
  check(await page.getByRole('button',{name:'下载公司盘点表.xls',exact:true}).isDisabled(),'未完成复盘可正式下载');
  check(await page.getByText('生成完整V13工作簿草稿（7表）',{exact:true}).count()===0,'02仍混入七表能力');
  await page.screenshot({path:path.join(out,'02_待完成核对.png'),fullPage:true});
  record('02仅最终模板，未完成核实阻断下载');
  await go('01 连续复盘找差异');await grid.locator('tbody tr').first().waitFor();
  const all=await data();
  const paste=all.rows.map(r=>`${r.barcode}\t${r.barcode==='0990000000000'?0:r.system-r.adjustment}\t模拟现场核验\t模拟单位已核对`).join('\n');
  await grid.getByRole('button',{name:'批量粘贴',exact:true}).click();await grid.getByRole('textbox',{name:'批量粘贴复盘数据',exact:true}).fill(paste);
  await grid.getByRole('button',{name:'校验并保存全部粘贴行',exact:true}).click();await saved();
  await grid.getByRole('button',{name:'撤销上次输入',exact:true}).click();await saved();
  await grid.getByRole('button',{name:'批量粘贴',exact:true}).click();await grid.getByRole('textbox',{name:'批量粘贴复盘数据',exact:true}).fill(paste);await grid.getByRole('button',{name:'校验并保存全部粘贴行',exact:true}).click();await saved();
  await go('02 公司盘点结果导出');await expand('导出检查与剩余问题');
  for(const label of ['确认同门店、同期间且覆盖本次完整盘点范围','确认差异已核实、相关凭证齐备']){
    if(!await page.getByRole('checkbox',{name:label,exact:true}).isChecked()){const t=page.getByText(label,{exact:true});await t.evaluate(e=>e.scrollIntoView({block:'center'}));await t.click()}
  }
  await page.getByRole('button',{name:'保存导出确认',exact:true}).click();await page.waitForTimeout(700);
  await page.getByRole('button',{name:'预览最终三列',exact:true}).click();
  await page.getByTestId('stDataFrame').first().waitFor({timeout:30000});
  const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'下载公司盘点表.xls',exact:true}).click()]);await download.saveAs(path.join(out,'模拟公司盘点表.xls'));
  await page.setViewportSize({width:1920,height:1080});await page.getByTestId('stMain').evaluate(el=>el.scrollTop=0);
  await page.screenshot({path:path.join(out,'02_公司最终三列.png'),fullPage:true});
  record('450条批量/撤销后，02实际生成并下载公司三列真XLS，保留0和前导零');
  await go('03 现场复核单打印');check(await page.getByRole('button',{name:'预览A4',exact:true}).isDisabled(),'已完成复盘仍在默认现场清单');
  record('01实数完成后，03默认清单即时退出');
  await go('更多工具');
  const tools=page.getByRole('combobox',{name:'更多工具',exact:true});await tools.click();await page.keyboard.press('ArrowDown');await page.getByRole('option',{name:'变化清单/七表母版',exact:true}).click();
  await page.getByRole('button',{name:'生成完整V13工作簿草稿（7表）',exact:true}).waitFor();
  record('供应商、变化、七表及备份仍有更多工具入口');
  check(errors.length===0,errors.join('\n'));results.pass=true;results.page_errors=errors;
  await fs.writeFile(path.join(out,'browser_workflow_results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
}catch(e){results.error=String(e);results.page_errors=errors;results.debug=await grid.evaluate(el=>{const s=el.__inventory;return {inflight:s.inflight?.kind,queue:s.queue.length,draft_rows:Object.keys(s.drafts).length,meta_drafts:Object.keys(s.metaDrafts),error:s.data.error,revision:s.data.revision}}).catch(()=>null);await fs.writeFile(path.join(out,'browser_failure.json'),JSON.stringify(results,null,2));await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});throw e}
finally{await browser.close()}
