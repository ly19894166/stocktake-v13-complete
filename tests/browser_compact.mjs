// 450条虚构数据：Excel式密度、默认排序迁移、连续输入与三分辨率新旧对照。
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'playwright');
const here=path.dirname(fileURLToPath(import.meta.url)),out=path.join(here,'runtime/compact_results');await fs.mkdir(out,{recursive:true});
const url=process.env.STOCKTAKE_TEST_URL||'http://127.0.0.1:18543';
if(new URL(url).port==='8513'||!['127.0.0.1','localhost'].includes(new URL(url).hostname))throw Error('只允许独立模拟端口');
const before=process.argv.includes('--before');
const browser=await chromium.launch({channel:process.env.STOCKTAKE_BROWSER_CHANNEL||'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
const grid=page.locator('#stocktake-workbench'),check=(v,m)=>{if(!v)throw Error(m)},results={pass:false,simulated_only:true,resolutions:[],cases:[]};
const data=()=>grid.evaluate(el=>el.__inventory.data);
const row=bc=>grid.locator('tbody tr').filter({has:page.getByRole('textbox',{name:`备注 ${bc}`,exact:true})});
const saved=async()=>{await page.waitForFunction(()=>{const h=[...document.querySelectorAll('*')].find(e=>e.shadowRoot?.querySelector('#stocktake-workbench'));const s=h?.shadowRoot.querySelector('#stocktake-workbench').__inventory;return s&&!s.inflight&&!s.queue.length&&!Object.keys(s.drafts).length&&!Object.keys(s.metaDrafts).length},{},{timeout:90000})};
const record=n=>{results.cases.push({name:n,pass:true});console.log(n)};
const top=()=>grid.evaluate(el=>el.__inventory.scrollParent().scrollTop=0);
try{
  await page.goto(url,{waitUntil:'networkidle'});
  const needsImport=await Promise.race([
    grid.waitFor({timeout:30000}).then(()=>false),
    page.getByText('只需上传盘盈、盘亏两张报表，自动进入01。无需填写店名、日期或时间。',{exact:true}).waitFor({timeout:30000}).then(()=>true)
  ]);
  if(needsImport){
    const importer=page.locator('summary').filter({hasText:'导入新的初盘 / 恢复已有批次'});if(await importer.locator('..').getAttribute('open')===null)await importer.click();
    await page.locator('input[type=file]').nth(0).setInputFiles(path.join(here,'runtime/workflow_demo/模拟450盘盈.xls'));await page.getByText('模拟450盘盈.xls',{exact:true}).waitFor();
    await page.locator('input[type=file]').nth(1).setInputFiles(path.join(here,'runtime/workflow_demo/模拟450盘亏.xls'));
  }
  await grid.locator('tbody tr').first().waitFor({timeout:30000});check((await data()).rows.length===450,'非450条模拟批次');
  if(before){
    await grid.getByRole('textbox',{name:'实际销售金额（元）',exact:true}).fill('1234567.89');await grid.getByRole('textbox',{name:'同期含税销售成本（元）',exact:true}).fill('10000000');await grid.locator('.search').click();await saved();
  }else{
    const batch=(await data()).batch;
    for(const oldSort of ['pair','amount']){
      await page.evaluate(({batch,oldSort})=>localStorage.setItem('stocktake:'+batch,JSON.stringify({flowVersion:3,sort:oldSort,query:'',filters:[],drafts:{},metaDrafts:{}})),{batch,oldSort});
      await page.reload({waitUntil:'networkidle'});await grid.locator('tbody tr').first().waitFor();
      check(await grid.locator('.view').inputValue()==='sequence','旧localStorage排序未迁移');
    }
    const seq=await grid.locator('tbody .seq').allTextContents();check(seq.every((s,i)=>Number(s)===i+1),'默认不是1到450升序');
    record('旧flowVersion3串码/金额排序一次性迁移为原始序号，1至450完整升序');
  }
  for(const [width,height] of [[1366,768],[1920,1080],[2560,1440]]){
    await page.setViewportSize({width,height});await top();await page.waitForTimeout(250);
    const layout=await grid.evaluate(el=>{const t=el.querySelector('table'),trs=[...el.querySelectorAll('tbody tr')],shown=trs.filter(tr=>{const r=tr.getBoundingClientRect();return r.top>=t.querySelector('thead').getBoundingClientRect().bottom-1&&r.bottom<=innerHeight});return {columns:[...t.querySelectorAll('th')].filter(x=>getComputedStyle(x).display!=='none').map(x=>x.textContent),ordinary_heights:trs.slice(20,80).map(x=>x.getBoundingClientRect().height),visible_rows:shown.length,table_top:t.getBoundingClientRect().top,overflow:t.scrollWidth>el.querySelector('.table-wrap').clientWidth+2,input_height:trs[20].querySelector('.edit-count').getBoundingClientRect().height,note_tag:trs[20].querySelector('.edit-note').tagName,all_codes_fit:trs.every(tr=>[...tr.querySelectorAll('.barcode,.code')].every(e=>getComputedStyle(e).display==='none'||e.scrollWidth<=e.clientWidth+1)),core_cells_fit:trs.slice(0,80).every(tr=>[...tr.querySelectorAll('.edit-count,.edit-note')].every(e=>e.getBoundingClientRect().right<=innerWidth&&e.clientWidth>=40))}});
    if(!before){check(!layout.overflow&&layout.core_cells_fit&&layout.all_codes_fit,'核心列或条码被截断');check(layout.columns.length===(width<=1500?11:13),'响应列数错误');check(layout.ordinary_heights.every(h=>h>=34&&h<=42),'普通行高度超标');check(layout.input_height>=28&&layout.input_height<=32&&layout.note_tag==='INPUT','行内输入未紧凑化');check(layout.visible_rows>=(width===1366?10:width===1920?18:27),'一屏商品不足');}
    results.resolutions.push({width,height,...layout});await page.screenshot({path:path.join(out,`${before?'before':'after'}_${width}.png`),fullPage:false});
  }
  if(before){results.pass=true;await fs.writeFile(path.join(out,'before_results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));}
  else{
    await page.setViewportSize({width:1920,height:1080});await top();
    const original=await data(),a=original.rows.find(r=>r.barcode==='0990000000000'),b=original.rows.find(r=>r.barcode==='0990000000001');
    await row(a.barcode).locator('.edit-count').fill('5');await row(a.barcode).locator('.edit-count').press('Enter');await saved();
    const changed=(await data()).rows.find(r=>r.id===a.id);
    check(changed.initial_diff===-2888&&changed.diff===-2884&&changed.change===4&&changed.amount===-1816.92&&changed.total===5,'V13计算回退');
    check((await row(a.barcode).locator('.difference').textContent()).includes('找回4'),'简短找回提示缺失');
    for(const [sel,value] of [['.system','2,889'],['.initial','1'],['.total','5']])check((await row(a.barcode).locator(sel).textContent())===value,'横向数量缺失');
    await row(a.barcode).locator('.difference-details').click();check((await grid.locator('.calculation-dialog').textContent()).includes('原始调整'),'计算依据未展示');await grid.locator('.calculation-close').click();
    record('系统/初盘/复盘/当前总数/差异横向可见，找回4和-1816.92按原引擎更新，点击可查看计算依据');
    const unitRow=row('0990000000006');await unitRow.locator('.edit-count').fill('0');await grid.locator('.search').click();await saved();
    const unit=(await data()).rows.find(r=>r.barcode==='0990000000006');check(unit.adjustment===.4&&unit.total===0&&unit.diff===-9.6,'原始特殊单位调整在横向界面中丢失');
    await unitRow.locator('.edit-count').fill('');await grid.locator('.search').click();await saved();check((await data()).rows.find(r=>r.id===unit.id).recount===null,'恢复空白被当作0');
    record('原始调整0.4保留：实数0时差异-9.6；清空实数恢复未复盘，与0严格区分');
    await row(a.barcode).locator('.edit-note').fill('模拟单行备注保留');await grid.locator('.search').click();await saved();
    await row(a.barcode).locator('.note-expand').click();await grid.locator('.note-editor').fill('模拟长备注第一行\n模拟第二行：人工核查说明'.repeat(4));await grid.locator('.note-close').click();await saved();
    const longNote=(await data()).rows.find(r=>r.id===a.id).note;check(longNote.includes('\n')&&longNote.includes('模拟第二行'),'长备注展开编辑丢失内容');
    const height=await row(a.barcode).evaluate(el=>el.getBoundingClientRect().height);check(height<=42,'长备注或串码提示撑高行');
    await row(a.barcode).locator('.peer-live').click();await page.waitForTimeout(300);check(await row(b.barcode).evaluate(el=>{const r=el.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight}),'对应商品无法定位');
    await row(b.barcode).locator('.edit-count').fill('20');await grid.locator('.search').click();await saved();check(await row(a.barcode).locator('.peer-live').count()===0,'对方归零提示仍在');
    check((await data()).rows.find(r=>r.id===a.id).note===longNote,'系统提示覆盖人工备注');
    await row(b.barcode).locator('.edit-count').fill('24');await grid.locator('.search').click();await saved();await row(a.barcode).locator('.peer-live').waitFor();
    record('单行备注可展开编辑多行；串码提示不撑高，点击定位，归零撤销/恢复重现且备注保留');
    await grid.locator('.view').selectOption('pair');
    let order=await grid.evaluate(el=>el.__inventory.visible.map(r=>r.id));check(Math.abs(order.indexOf(a.id)-order.indexOf(b.id))===1,'主动串码联排未相邻');
    await grid.locator('.view').selectOption('amount');await grid.locator('.view').selectOption('category');await grid.locator('.view').selectOption('sequence');
    const seq=await grid.locator('tbody .seq').allTextContents();check(seq.every((s,i)=>Number(s)===i+1),'切回原始序号失败');
    const latest=await data();check(latest.rows.map(r=>r.id).join('|')===original.rows.map(r=>r.id).join('|'),'视觉排序修改后端ID/导出顺序');
    record('四种排序可切换，串码主动联排后可恢复1至450，后台记录及导出顺序未变');
    await top();await page.mouse.move(1700,650);let bottom=false;
    for(let i=0;i<60;i++){await page.mouse.wheel(0,1400);await page.waitForTimeout(35);const s=await grid.evaluate(el=>{const sc=el.__inventory.scrollParent();return {bottom:sc.scrollTop+sc.clientHeight>=sc.scrollHeight-3,head:el.querySelector('th').getBoundingClientRect().top,visible:[...el.querySelectorAll('tbody tr')].some(tr=>{const r=tr.getBoundingClientRect();return r.bottom>90&&r.top<innerHeight})}});check(s.visible,'滚轮出现大片空白');if(i>0)check(s.head>=60&&s.head<90,'固定表头被顶部栏遮挡');if(s.bottom){bottom=true;break}}
    check(bottom&&!await grid.getByRole('button',{name:/上一页|下一页/}).count(),'未连续滚到底或仍有分页');
    const target=await grid.evaluate(el=>{const sc=el.__inventory.scrollParent();sc.scrollTop=sc.scrollHeight*.6;return el.__inventory.visible[280].barcode});
    await row(target).locator('.edit-count').scrollIntoViewIfNeeded();const input=row(target).locator('.edit-count');await input.fill('0');const position=await grid.evaluate(el=>el.__inventory.scrollParent().scrollTop);await saved();
    check(await grid.evaluate((el,pos)=>Math.abs(el.__inventory.scrollParent().scrollTop-pos)<50&&el.getRootNode().activeElement?.className==='edit-count',position),'自动保存回顶或失焦');
    check((await data()).rows.find(r=>r.barcode===target).recount===0,'0与空白混淆');
    record('450条鼠标滚轮到底无分页/白屏，表头固定，深处填0自动保存不回顶不失焦');
    await grid.locator('.search').fill('');await top();
    for(const [width,height] of [[1366,768],[1920,1080],[2560,1440]]){await page.setViewportSize({width,height});await top();await page.screenshot({path:path.join(out,`after_${width}.png`),fullPage:false});}
    check(!errors.length,errors.join('\n'));results.pass=true;results.page_errors=errors;await fs.writeFile(path.join(out,'compact_results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
  }
}catch(e){await page.screenshot({path:path.join(out,'failure.png'),fullPage:false}).catch(()=>{});await fs.writeFile(path.join(out,'failure.json'),JSON.stringify({...results,error:String(e)},null,2));throw e}
finally{await browser.close()}
