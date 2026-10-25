// 480条完全虚构样本；正式端口被禁止。可在Windows Edge或CI Chromium运行。
import {createRequire} from 'node:module';import fs from 'node:fs/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'playwright');
const here=path.dirname(fileURLToPath(import.meta.url)),out=path.join(here,'runtime/fifth_results'),demo=path.join(here,'runtime/fifth_demo');await fs.mkdir(out,{recursive:true});
const url=process.env.STOCKTAKE_TEST_URL||'http://127.0.0.1:18545';if(new URL(url).port==='8513'||!['127.0.0.1','localhost'].includes(new URL(url).hostname))throw Error('仅允许独立模拟环境');
const browser=await chromium.launch({...(process.env.CI?{}:{channel:'msedge'}),headless:true});const page=await browser.newPage({viewport:{width:1920,height:1080}}),g=page.locator('#stocktake-workbench'),errors=[],cases=[],resolutions=[];page.on('pageerror',e=>errors.push(String(e)));
const check=(v,m)=>{if(!v)throw Error(m)},record=m=>{cases.push({name:m,pass:true});console.log(m)},data=()=>g.evaluate(el=>el.__inventory.data);
const go=async text=>{await page.getByText(text,{exact:true}).first().click();await page.waitForTimeout(180)};
const expand=async text=>{const s=page.locator('summary').filter({hasText:text});if(await s.locator('..').getAttribute('open')===null)await s.click()};
const saved=()=>page.waitForFunction(()=>{const h=[...document.querySelectorAll('*')].find(e=>e.shadowRoot?.querySelector('#stocktake-workbench'));const s=h?.shadowRoot.querySelector('#stocktake-workbench').__inventory;return s&&!s.inflight&&!s.queue.length&&!Object.keys(s.drafts).length&&!Object.keys(s.metaDrafts).length},{},{timeout:90000});
const row=bc=>g.locator('tbody tr').filter({has:page.getByRole('textbox',{name:'备注 '+bc,exact:true})});
const scope=async v=>{await g.locator('.scope').selectOption(v);await saved()};
const column=async(label,options={})=>{
 await g.getByRole('button',{name:'筛选'+label,exact:true}).click();const pane=g.locator('.filter-dialog');
 for(const [key,v] of Object.entries(options)){const input=pane.getByLabel(key,{exact:true});if(await input.evaluate(el=>el.tagName)==='SELECT')await input.selectOption(v);else await input.fill(v)}
 await pane.getByRole('button',{name:'应用列筛选',exact:true}).click();
};
const clear=async()=>{await g.locator('.clear').click();await saved()};
const visibleIds=()=>g.locator('tbody tr').evaluateAll(rows=>rows.map(r=>r.dataset.id));
const exact=async(rows,message)=>{const ids=await visibleIds(),expected=rows.map(r=>r.id);check(JSON.stringify([...ids].sort())===JSON.stringify([...expected].sort()),message+' actual='+ids.length+' expected='+expected.length+' extras='+ids.filter(id=>!expected.includes(id)).join(','))};
const download=async(label,name)=>{const [d]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:label,exact:true}).click()]);await d.saveAs(path.join(out,name))};
try{
 await page.goto(url,{waitUntil:'networkidle'});
 if(process.argv.includes('--reopen')){
  await g.locator('tbody tr').first().waitFor();const d=await data();check(d.rows.length===480&&d.rows.every(r=>r.recount!==null),'重启复盘丢失');check(await g.locator('.scope').inputValue()==='exclude','重启默认范围错误');
  await scope('eligible');await expand('可A换B商品专项审计');await expand('历史专项说明与双方凭证');
  check(await page.getByText('已保存凭证：SIM-PAIR-FIFTH',{exact:true}).count()===1,'重启双方凭证丢失');
  await go('03 现场复核单打印');await expand('历史打印记录与原单重印');await page.getByText('预览历史原单',{exact:true}).click();await page.locator('canvas:visible').first().waitFor({timeout:30000});check(!errors.length,'重启页面报错');
  await fs.writeFile(path.join(out,'reopen_ui.json'),JSON.stringify({pass:true,simulated_only:true,rows:480,proof_persisted:true,historical_pdf_rendered:true}));console.log('实际进程重启后复盘、资格、双方凭证和历史PDF读取通过');
 }else{
  await page.getByRole('button',{name:'上传盘点报表',exact:true}).click();await page.getByTestId('stFileUploader').filter({hasText:'上传盘点报表'}).locator('input[type=file]').setInputFiles(['模拟480盘亏.xls','模拟480盘盈.xls'].map(n=>path.join(demo,n)));await g.locator('tbody tr').first().waitFor({timeout:60000});
  check((await data()).rows.length===480,'初盘导入行数错误');
  await go('更多工具');await page.getByTestId('stFileUploader').filter({hasText:'批量导入任意供应商Excel'}).locator('input[type=file]').setInputFiles(path.join(demo,'模拟供应商.xlsx'));await page.getByRole('button',{name:'校验并追加供应商目录',exact:true}).click();await page.getByText('供应商目录已校验并保存',{exact:true}).waitFor();await go('01 连续复盘找差异');await g.locator('tbody tr').first().waitFor();
  let d=await data();check(d.rows.filter(r=>r.supplier_status==='zbf').length===60&&d.rows.filter(r=>r.supplier_status==='pending').length===25,'供应商归属不准确');await exact(d.rows.filter(r=>r.supplier_status!=='zbf'),'首次默认未仅排除确认卓不凡');
  const draft=d.rows.find(r=>r.supplier_status!=='zbf');await page.evaluate(({batch,id})=>localStorage.setItem('stocktake:'+batch,JSON.stringify({flowVersion:4,sort:'amount',query:'旧筛选',drafts:{[id]:{'复盘实数':{value:'17',base:null}}},metaDrafts:{}})),{batch:d.batch,id:draft.id});
  await page.reload({waitUntil:'networkidle'});await g.locator('tbody tr').first().waitFor();check(await g.locator('.scope').inputValue()==='exclude'&&await g.locator('.view').inputValue()==='sequence'&&await row(draft.barcode).locator('.edit-count').inputValue()==='17','升级默认或草稿兼容失败');
  // 清除筛选不能清除输入草稿。
  await g.locator('.clear').click();await page.waitForTimeout(250);check(await row(draft.barcode).locator('.edit-count').inputValue()==='17','清除筛选误删草稿');await row(draft.barcode).locator('.edit-count').fill('');await saved();
  record('首次默认不含卓不凡；旧排序/筛选一次性迁移，草稿保留且清除筛选不删除输入');
  await scope('zbf');await exact(d.rows.filter(r=>r.supplier_status==='zbf'),'仅卓不凡不全');await scope('all');await exact(d.rows,'全部商品不全');await scope('exclude');
  await expand('可换货商品数据库（本机）');await page.getByTestId('stFileUploader').filter({hasText:'批量导入可换货商品Excel（九列）'}).locator('input[type=file]').setInputFiles(path.join(demo,'模拟可换货档案.xlsx'));await page.getByRole('button',{name:'保存全部可换货档案',exact:true}).click();await page.getByText('批量可换货档案已保存',{exact:true}).waitFor();
  await page.getByRole('textbox',{name:'输入完整条码精确查找',exact:true}).fill('0990000000110');await page.getByRole('textbox',{name:'输入完整条码精确查找',exact:true}).press('Enter');await page.getByRole('textbox',{name:'经确认的换货组',exact:true}).fill('SIM-G3');await page.getByText('启用换货资格',{exact:true}).click();await page.getByRole('button',{name:'保存可换货档案',exact:true}).click();await page.getByText('可换货档案已保存',{exact:true}).waitFor();
  await g.locator('tbody tr').first().waitFor();check((await data()).rows.filter(r=>r.eligible).length===81,'条码精确启用/修改换货组没有生效');await page.getByText('启用换货资格',{exact:true}).click();await page.getByRole('button',{name:'保存可换货档案',exact:true}).click();await page.waitForTimeout(400);
  await expand('可换货档案修改历史');await page.locator('summary').filter({hasText:'可换货商品数据库（本机）'}).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'01_可换货档案维护.png')});
  await page.locator('summary').filter({hasText:'可换货商品数据库（本机）'}).click();await g.locator('tbody tr').first().waitFor();d=await data();check(d.rows.filter(r=>r.eligible).length===80,'已启用同组资格未生效或停用/未来档案误生效');
  await scope('eligible');await exact(d.rows.filter(r=>r.eligible),'全部可A换B商品不全');await expand('可A换B商品专项审计');await page.getByRole('button',{name:'下载可A换B专项审计Excel',exact:true}).waitFor();
  check((await page.getByText(/可换货：80条/).count())===1,'01审计资格范围错误');
  await page.getByRole('textbox',{name:'专项核查说明（人工）',exact:true}).fill('模拟第五次人工核对说明');await page.getByRole('textbox',{name:'凭证编号',exact:true}).fill('SIM-ITEM-FIFTH');await page.getByRole('button',{name:'保存专项说明与凭证',exact:true}).click();await page.getByText('专项说明与凭证已保存',{exact:true}).waitFor();
  await expand('对应商品核对、查看更多及双方凭证');await page.getByRole('textbox',{name:'双方核查说明',exact:true}).fill('模拟双方实物核对，保留对应关系，不抵销');await page.getByRole('textbox',{name:'双方凭证编号',exact:true}).fill('SIM-PAIR-FIFTH');const proofRevision=(await data()).revision;await page.getByRole('button',{name:'保存双方核查凭证',exact:true}).click();await page.getByText('双方对应关系与凭证已保存',{exact:true}).waitFor();await page.waitForFunction(rev=>{const h=[...document.querySelectorAll('*')].find(e=>e.shadowRoot?.querySelector('#stocktake-workbench'));return h?.shadowRoot.querySelector('#stocktake-workbench').__inventory.data.revision>rev},proofRevision);
  await download('下载可A换B专项审计Excel','模拟可A换B专项审计.xlsx');await fs.writeFile(path.join(out,'audit_snapshot.json'),JSON.stringify(await data()));check(await page.locator('#stocktake-global-summary').evaluate(el=>{const r=el.getBoundingClientRect();return r.top>=60&&r.bottom<innerHeight&&el.querySelectorAll('.metric').length===7}),'打开专项审计后整店七项统计不可见');await page.locator('summary').filter({hasText:'可A换B商品专项审计'}).scrollIntoViewIfNeeded();await page.waitForTimeout(500);await page.screenshot({path:path.join(out,'01_可A换B专项审计.png')});
  await page.locator('summary').filter({hasText:'可A换B商品专项审计',exact:true}).click();await scope('all');
  d=await data();const stablePanel=JSON.stringify(d.panel),stableRevision=d.revision;
  for(const [mode,predicate] of [['loss',r=>r.diff<0],['gain',r=>r.diff>0],['nonzero',r=>r.diff!==null&&r.diff!==0],['unreviewed',r=>r.recount===null],['reviewed',r=>r.recount!==null]]){
    await column('最新差异',{'筛选状态':mode});await exact(d.rows.filter(predicate),'最新差异'+mode+'不正确');
  }
  await clear();await scope('all');await column('最新差异',{'筛选状态':'loss','最小值（含）':'-10','最大值（含）':'-7'});await column('品类',{'品类':'模拟饮料'});await column('备注／原因',{'人工备注':'no'});
  await exact(d.rows.filter(r=>r.diff>=-10&&r.diff<=-7&&r.category==='模拟饮料'&&!r.note.trim()),'组合数量范围/品类/备注错误');await page.screenshot({path:path.join(out,'01_组合表头筛选.png')});
  await clear();await scope('all');await column('差异金额（元）',{'筛选状态':'loss','最小值（含）':'-50','最大值（含）':'-20','排序方式':'amount'});await exact(d.rows.filter(r=>r.amount>=-50&&r.amount<=-20),'金额范围错误');
  const amounts=await g.locator('tbody tr').evaluateAll(rows=>rows.map(r=>Number(r.querySelector('.amount').textContent.replace(/,/g,''))));check(amounts.every((v,i)=>i===0||Math.abs(amounts[i-1])>=Math.abs(v)),'金额绝对值排序不正确');
  await clear();await scope('all');await column('系统数',{'最小值（含）':'20','最大值（含）':'20'});await column('初盘数',{'最小值（含）':'20'});await exact(d.rows.filter(r=>r.system===20&&r.initial>=20),'系统/初盘筛选错误');
  await clear();await scope('all');await column('核查标签',{'线索与资格':'mix'});await exact(d.rows.filter(r=>r.mix_count>0),'串码筛选错误');
  await clear();await scope('all');await column('核查标签',{'线索与资格':'eligible'});await exact(d.rows.filter(r=>r.eligible),'允许A换B筛选错误');
  await clear();await scope('all');await column('供货商',{'供货商':'供货商待确认'});await exact(d.rows.filter(r=>r.supplier_status==='pending'),'待确认筛选错误');
  await clear();await scope('all');const chosen=d.rows.find(r=>r.barcode.endsWith('0100'));await column('商品编码',{'列搜索内容':chosen.code});await exact([chosen],'编码列搜索错误');
  await clear();await scope('all');await g.locator('.search').fill(chosen.barcode.slice(-6));await exact([chosen],'尾号搜索错误');
  await clear();check((await data()).revision===stableRevision&&JSON.stringify((await data()).panel)===stablePanel,'筛选改变整店统计或业务记录');
  check(await g.locator('.view').inputValue()==='sequence'&&await g.locator('.scope').inputValue()==='exclude','清除筛选未恢复默认');
  record('商品范围、差异状态/区间、金额、品类、备注、系统/初盘、串码、资格、供应商、编码/尾号及组合筛选准确，整店统计不受影响');
  await g.getByRole('textbox',{name:'同期含税销售成本（元）',exact:true}).fill('10000000');await g.locator('.search').click();await saved();
  await scope('all');d=await data();const target=d.rows.find(r=>r.supplier_status==='zbf'&&r.diff>0),peerBefore=d.rows.filter(r=>r.swap_count>0).length;
  await row(target.barcode).locator('.edit-count').fill(String(target.system-target.adjustment));await saved();await scope('zbf');check(await g.locator('tbody tr').count()===60,'归零/已复盘卓不凡被筛掉');
  let updated=(await data()).rows.find(r=>r.id===target.id);check(updated.diff===0&&updated.amount===0&&updated.swap_count===0&&updated.mix_count===0&&await row(target.barcode).locator('.amount').textContent()==='0.00','归零候选未撤销/金额错误');
  await scope('all');await column('最新差异',{'筛选状态':'zero'});await exact((await data()).rows.filter(r=>r.diff===0),'归零筛选错误');
  await clear();await scope('all');await row(target.barcode).locator('.edit-count').fill('');await saved();check((await data()).rows.find(r=>r.id===target.id).swap_count>0,'恢复差异候选未重算');
  await column('最新差异',{'筛选状态':'unreviewed'});const deep=(await data()).rows[399];await row(deep.barcode).locator('.edit-count').scrollIntoViewIfNeeded();await row(deep.barcode).locator('.edit-count').fill('0');const y=await g.evaluate(el=>el.__inventory.scrollParent().scrollTop);await saved();
  check(await g.evaluate((el,yy)=>Math.abs(el.__inventory.scrollParent().scrollTop-yy)<70&&el.getRootNode().activeElement?.classList.contains('edit-count'),y),'连续输入失焦/回顶');updated=(await data()).rows.find(r=>r.id===deep.id);check(updated.recount===0&&updated.diff!==null&&Number((await row(deep.barcode).locator('.amount').textContent()).replace(/,/g,''))===updated.amount,'填写0未实时更新金额');check((await page.locator('#stocktake-global-summary strong').nth(2).innerText())===(await data()).panel.net,'整店悬浮净差异未实时更新');
  await column('最新差异',{'筛选状态':''});await column('复盘实数',{'筛选状态':'zero'});await exact((await data()).rows.filter(r=>r.recount===0),'复盘0筛选误把空白当0');await clear();await scope('all');
  record('逐行金额显示、归零撤销/恢复重算、全部卓不凡含已复盘归零、0与空白及深处连续输入通过');
  const allRows=(await data()).rows;const money=await g.locator('tbody tr').evaluateAll(rows=>rows.map(tr=>({id:tr.dataset.id,text:tr.querySelector('.amount').textContent})));await fs.writeFile(path.join(out,'browser_amounts.json'),JSON.stringify({rows:allRows,display:money},null,2));
  for(const [width,height] of [[1366,768],[1920,1080],[2560,1440]]){
   await page.setViewportSize({width,height});const positions=[];
   for(const index of [0,199,399,479]){
    await g.evaluate((el,i)=>{const s=el.__inventory;if(i===0)s.scrollParent().scrollTop=0;else s.dom.get(s.visible[i].id).scrollIntoView({block:'center'})},index);await page.waitForTimeout(120);
    const layout=await g.evaluate(el=>{const rail=document.querySelector('#stocktake-global-summary').getBoundingClientRect(),head=el.querySelector('th').getBoundingClientRect(),trs=[...el.querySelectorAll('tbody tr')];return {rail_top:rail.top,rail_bottom:rail.bottom,header_top:head.top,metrics:document.querySelectorAll('#stocktake-global-summary .metric').length,overflow:el.querySelector('table').scrollWidth>el.querySelector('.table-wrap').clientWidth+2,money_visible:trs.every(tr=>getComputedStyle(tr.querySelector('.amount')).display!=='none'&&tr.querySelector('.amount').getBoundingClientRect().right<=innerWidth),barcodes_fit:trs.every(tr=>tr.querySelector('.barcode').scrollWidth<=tr.querySelector('.barcode').clientWidth+1),inputs_fit:trs.every(tr=>tr.querySelector('.edit-count').clientWidth>=40),ordinary_heights:trs.filter(tr=>tr.querySelector('.name').textContent.length<20).slice(30,90).map(tr=>tr.getBoundingClientRect().height),visible_rows:trs.filter(tr=>{const r=tr.getBoundingClientRect();return r.top>=head.bottom&&r.bottom<=innerHeight}).length}});
    check(layout.metrics===7&&layout.rail_top>=60&&layout.header_top>=layout.rail_bottom-1&&!layout.overflow&&layout.money_visible&&layout.barcodes_fit&&layout.inputs_fit&&layout.ordinary_heights.every(v=>v<=42),'屏幕布局有遮挡/截断/行高回退 '+JSON.stringify({width,index,...layout}));positions.push({row:index+1,...layout});
    await page.screenshot({path:path.join(out,`01_${width}_第${index+1}条.png`)});
   }resolutions.push({width,height,positions});
  }
  await page.setViewportSize({width:1920,height:1080});await go('03 现场复核单打印');const expected=allRows.filter(r=>r.recount===null&&r.diff!==null&&r.diff!==0&&r.supplier_status!=='zbf').length;await page.getByText(new RegExp('本次待复核：'+expected+'条')).waitFor();
  await page.getByRole('button',{name:'生成并保存PDF',exact:true}).click();await page.getByText(/打印记录已保存/).waitFor();await expand('历史打印记录与原单重印');await page.getByText('共1份历史记录',{exact:true}).waitFor();await download('下载历史原单PDF','模拟现场单原件.pdf');await page.getByRole('button',{name:'原单重印并登记',exact:true}).click();await page.getByText('共2份历史记录',{exact:true}).waitFor();await download('下载历史原单PDF','模拟现场单重印.pdf');await page.screenshot({path:path.join(out,'03_打印规则保留.png')});
  await go('01 连续复盘找差异');await g.locator('tbody tr').first().waitFor();await scope('zbf');const rows=(await data()).rows;await g.locator('.bulk-toggle').click();await g.locator('.bulk textarea').fill(rows.map(r=>`${r.barcode}\t${r.system-r.adjustment}\t模拟最终核对\t模拟单位已核对`).join('\n'));await g.locator('.bulk-submit').click();await saved();
  await go('02 公司盘点结果导出');check(await page.locator('summary').filter({hasText:/专项审计|可换货/}).count()===0,'02仍显示专项审计');await expand('导出检查与剩余问题');
  for(const label of ['确认同门店、同期间且覆盖本次完整盘点范围','确认差异已核实、相关凭证齐备'])if(!await page.getByRole('checkbox',{name:label,exact:true}).isChecked())await page.getByText(label,{exact:true}).click();await page.getByRole('button',{name:'保存导出确认',exact:true}).click();await download('下载公司盘点表.xls','模拟全店480条公司三列.xls');await page.screenshot({path:path.join(out,'02_仅公司三列.png')});
  check(!errors.length&&!await page.getByTestId('stException').count(),'浏览器或页面报错');record('03只排除卓不凡且保留非卓不凡可换货商品；原单重印、全量批量录入和02全店480行独立真XLS通过');
  await fs.writeFile(path.join(out,'browser_fifth_results.json'),JSON.stringify({pass:true,simulated_only:true,rows:480,cases,resolutions,page_errors:errors},null,2));
 }
}finally{await browser.close()}
