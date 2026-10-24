// 仅在独立模拟环境执行；截图、导出与浏览器结果写到被忽略的tests/runtime。
// 设置STOCKTAKE_TEST_URL/PLAYWRIGHT_MODULE。--before只为main基线拍同一模拟数据。
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.dirname(fileURLToPath(import.meta.url));
const before=process.argv.includes('--before');
const out=process.env.STOCKTAKE_ACCEPTANCE_DIR||path.join(root,'runtime','optimization');await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:process.env.STOCKTAKE_BROWSER_CHANNEL||'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1366,height:768},permissions:['clipboard-read','clipboard-write']});
const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const url=process.env.STOCKTAKE_TEST_URL||'http://127.0.0.1:18532';
const assert=(ok,message)=>{if(!ok)throw new Error(message)};
try{
  await page.goto(url,{waitUntil:'networkidle'});
  const batchSettings=page.locator('summary').filter({hasText:/切换批次、导入与设置|当前批次 \/ 切换、导入与设置/});
  if(await batchSettings.count()&&await batchSettings.locator('..').getAttribute('open')===null)await batchSettings.click();
  const importer=page.locator('summary').filter({hasText:'导入新的初盘 / 恢复已有批次'});
  if(await importer.locator('..').getAttribute('open')===null)await importer.click();
  const fixture=process.env.STOCKTAKE_SIMULATED_DIR||path.join(root,'runtime','simulated');
  await page.locator('input[type=file]').nth(0).setInputFiles(path.join(fixture,'模拟盘盈.xls'));
  await page.getByText('模拟盘盈.xls',{exact:true}).waitFor();
  await page.locator('input[type=file]').nth(1).setInputFiles(path.join(fixture,'模拟盘亏.xls'));
  const grid=page.locator('#stocktake-workbench');await grid.locator('tbody tr').first().waitFor({timeout:30000});
  const result={pass:true,synthetic_only:true,resolutions:[],page_errors:errors};
  for(const [width,height] of [[1366,768],[1920,1080],[2560,1440]]){
    await page.setViewportSize({width,height});await page.waitForTimeout(300);
    await page.screenshot({path:path.join(out,`${before?'before':'after'}_${width}.png`),fullPage:true});
    if(!before){
      const layout=await grid.evaluate(el=>{const t=el.querySelector('table'),wrap=el.querySelector('.table-wrap');return {columns:t.querySelectorAll('thead th').length,tableWidth:t.getBoundingClientRect().width,wrapperWidth:wrap.clientWidth,scrollWidth:wrap.scrollWidth,overflow:getComputedStyle(wrap).overflowY,minWidth:getComputedStyle(t).minWidth,columnsWithinViewport:[...t.querySelectorAll('tbody tr:first-child td')].every(td=>td.getBoundingClientRect().left>=0&&td.getBoundingClientRect().right<=innerWidth),allInputWidths:[...t.querySelectorAll('.edit-count')].map(x=>x.getBoundingClientRect().width)}});
      assert(layout.columns===6&&layout.scrollWidth<=layout.wrapperWidth+2&&layout.columnsWithinViewport,'六列溢出或横向截断');
      assert(layout.overflow==='visible'&&Math.min(...layout.allInputWidths)>65,'出现表格内部滚动或输入框过窄');result.resolutions.push({width,height,...layout});
    }
  }
  if(before){await fs.writeFile(path.join(out,'before_capture.json'),JSON.stringify({pass:true,synthetic_only:true},null,2));console.log('main模拟界面基线已保存');}
  else{
    await page.setViewportSize({width:1366,height:768});
    assert(await page.getByText('03审核',{exact:true}).count()===0,'仍有独立03入口');
    assert(await grid.locator('.more-filters').isHidden(),'更多筛选没有默认折叠');
    assert(await grid.locator('tbody .peer').count()===0,'主行仍有冗长候选');
    const search=grid.getByRole('textbox',{name:'搜索商品名、编码、完整条码或尾号'});
    const waitSaved=async()=>{await page.waitForTimeout(750);await grid.locator('[data-testid="save-status"]').filter({hasText:'已保存'}).waitFor({timeout:30000})};
    // 连续输入两个经营值与两条复盘值，验证重跑不会丢掉下一个输入。
    await grid.getByRole('textbox',{name:'实际销售金额（元）',exact:true}).fill('54321.98');
    await grid.getByRole('textbox',{name:'同期含税销售成本（元）',exact:true}).fill('100000');
    await search.click();await waitSaved();
    await search.fill('0990000000000');
    const rowA=grid.locator('tbody tr').filter({has:page.getByRole('textbox',{name:'备注 0990000000000',exact:true})});
    await rowA.locator('.edit-note').fill('模拟人工备注永远保留');await search.click();await waitSaved();
    await rowA.locator('.hint-summary').click();
    const panel=grid.locator('.panel');await panel.locator('.peer').first().waitFor({timeout:20000});
    assert(await panel.locator('.peer').count()<=3,'初始候选超过3条');
    await panel.locator('.peer').filter({hasText:'0990000000003'}).click();
    await panel.locator('.pair-card').nth(1).waitFor({timeout:20000});
    await page.screenshot({path:path.join(out,'after_candidate_detail.png'),fullPage:true});
    await panel.getByRole('button',{name:'定位此商品',exact:true}).last().click();
    const rowB=grid.locator('tbody tr').filter({has:page.getByRole('textbox',{name:'备注 0990000000003',exact:true})});
    await rowB.locator('.edit-count').fill('20');await search.click();await waitSaved();
    assert(await rowB.locator('.hint-summary').count()===0,'归零后仍有候选');
    assert(await rowA.locator('.hint-summary').count()>0,'错误删除其他候选');
    assert(await rowA.locator('.edit-note').inputValue()==='模拟人工备注永远保留','人工原因被覆盖');
    await rowB.locator('.edit-count').fill('10');await search.click();await waitSaved();
    assert(await rowB.locator('.hint-summary').count()>0,'恢复差异后候选没有恢复');
    const amounts=await grid.evaluate(el=>el.__inventory.data.panel);
    assert(amounts.status==='当前测算达标'&&amounts.remaining_rows>0&&!amounts.final_approved,'当前测算被误标为最终通过');
    await grid.getByRole('button',{name:'生成盘点汇报',exact:true}).click();
    const report=grid.getByRole('dialog',{name:'季度盘点汇报'});await report.waitFor();
    await report.getByRole('textbox',{name:'主要原因（由店长确认）',exact:true}).fill('人工确认的模拟盘点原因');
    await report.getByRole('textbox',{name:'季度',exact:true}).fill('模拟季度');await waitSaved();
    await report.getByRole('checkbox',{name:'我已核对并确认主要原因',exact:true}).check();await waitSaved();
    const editor=report.getByRole('textbox',{name:'最终盘点汇报文稿',exact:true});
    await page.waitForFunction(()=>{const h=[...document.querySelectorAll('*')].find(el=>el.shadowRoot?.querySelector('#stocktake-workbench'));return h?.shadowRoot.querySelector('.report-text')?.value.includes('主要原因：人工确认的模拟盘点原因')});
    let doc=await editor.inputValue();assert(doc.includes('54321.98元')&&doc.includes('100000.00元')&&doc.includes(amounts.net+'元')&&!doc.includes('鲜食盘点'),'汇报数字或鲜食独立性不符');
    await editor.fill(doc+'\n模拟人工补充结尾');await report.locator('.panel-title').click();await waitSaved();
    await report.getByRole('button',{name:'一键复制文稿',exact:true}).click();
    assert((await page.evaluate(()=>navigator.clipboard.readText())).includes('模拟人工补充结尾'),'剪贴板复制失败');
    await report.getByRole('checkbox',{name:'附加独立鲜食盘点数据',exact:true}).check();await waitSaved();
    for(const [name,value] of [['鲜食销售金额（元）','1000'],['鲜食含税成本（元）','800'],['鲜食盘盈（正数或0）','11.13'],['鲜食盘亏（负数或0）','-14.24']]){
      await report.getByRole('textbox',{name,exact:true}).fill(value);
    }
    await report.locator('.panel-title').click();await waitSaved();
    await page.waitForFunction(()=>{const h=[...document.querySelectorAll('*')].find(el=>el.shadowRoot?.querySelector('#stocktake-workbench'));return h?.shadowRoot.querySelector('.report-text')?.value.includes('合计盘亏：-3.11元')});
    await page.screenshot({path:path.join(out,'after_quarterly_report.png'),fullPage:true});
    await report.getByRole('button',{name:'关闭',exact:true}).click();await waitSaved();
    const later=await grid.evaluate(el=>el.__inventory.data.panel.net);assert(later===amounts.net,'鲜食重复计入普通盘点');
    // 整个页面重载，验证持久化；真正进程重启由配套本机验收再执行。
    await page.reload({waitUntil:'networkidle'});await grid.locator('tbody tr').first().waitFor({timeout:30000});
    assert(await grid.getByRole('textbox',{name:'实际销售金额（元）',exact:true}).inputValue()==='54321.98','销售额没有保存');
    await search.fill('0990000000000');assert(await rowA.locator('.edit-note').inputValue()==='模拟人工备注永远保留','重开备注丢失');
    await page.getByText('02变化/导出',{exact:true}).first().click();
    await page.getByText('正式导出检查 · 公司三列文件',{exact:true}).click();
    assert(await page.getByRole('button',{name:'下载公司最终三列 .xls 候选文件',exact:true}).count()===0,'未完成复盘竟可正式导出');
    for(const label of ['供货商数据库','打印历史','高级异常明细']){await page.getByText(label,{exact:true}).first().click();await page.waitForTimeout(500);assert(await page.getByTestId('stException').count()===0,label+'异常');}
    result.compact_hints=true;result.dynamic_zero_and_restore=true;result.notes_preserved=true;result.financial_auto_save=true;result.current_estimate_only=true;result.report_live_numbers=true;result.edit_and_clipboard=true;result.fresh_independent=true;result.reload_persistence=true;result.export_blocked_when_incomplete=true;result.existing_pages_visible=true;
    assert(errors.length===0,errors.join('\n'));await fs.writeFile(path.join(out,'browser_results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }
}catch(error){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});throw error}
finally{await browser.close()}
