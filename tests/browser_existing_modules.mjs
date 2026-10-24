// 先运行browser_optimization.mjs，再执行此脚本验证保留功能及正式三列下载。
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.dirname(fileURLToPath(import.meta.url)),out=path.join(root,'runtime/module_demo');
const browser=await chromium.launch({channel:process.env.STOCKTAKE_BROWSER_CHANNEL||'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1920,height:1080}});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const check=(v,m)=>{if(!v)throw new Error(m)};
const expand=async label=>{const s=page.locator('summary').filter({hasText:label});if(await s.locator('..').getAttribute('open')===null)await s.click()};
const waitSaved=async()=>{await page.waitForTimeout(750);await page.locator('[data-testid="save-status"]').filter({hasText:'已保存'}).waitFor({timeout:30000})};
try{
  await page.goto(process.env.STOCKTAKE_TEST_URL||'http://127.0.0.1:18532',{waitUntil:'networkidle'});
  await page.getByText('01复盘与智能找差异',{exact:true}).first().click();
  const initialGrid=page.locator('#stocktake-workbench');await initialGrid.locator('tbody tr').first().waitFor({timeout:20000});
  const initialRows=await initialGrid.evaluate(el=>el.__inventory.data.rows);
  await initialGrid.getByRole('button',{name:'批量粘贴',exact:true}).click();
  await initialGrid.getByRole('textbox',{name:'批量粘贴复盘数据',exact:true}).fill(initialRows.map(x=>`${x.barcode}\t\t模拟验收初始化`).join('\n'));
  await initialGrid.getByRole('button',{name:'校验并保存全部粘贴行',exact:true}).click();await waitSaved();
  await page.getByText('打印历史',{exact:true}).first().click();
  await page.getByRole('button',{name:'生成当前 PDF 预览',exact:true}).click();
  await page.getByText(/未留档预览/).waitFor({timeout:20000});
  await page.getByRole('button',{name:'生成并留存打印批次',exact:true}).click();
  await page.getByRole('button',{name:'下载历史原单 PDF',exact:true}).waitFor({timeout:20000});
  await page.getByRole('button',{name:'原单重印并登记',exact:true}).click();
  await page.getByRole('button',{name:'按当前最新数据创建新打印批次',exact:true}).click();
  await page.getByRole('button',{name:'下载历史原单 PDF',exact:true}).waitFor({timeout:20000});
  await page.screenshot({path:path.join(out,'A4_preview_and_history.png'),fullPage:true});
  await page.getByText('供货商数据库',{exact:true}).first().click();
  await page.getByTestId('stFileUploader').filter({hasText:'批量导入任意供应商Excel'}).locator('input[type=file]').setInputFiles(path.join(out,'模拟供应商.xlsx'));
  await page.getByRole('button',{name:'校验并追加供应商目录',exact:true}).click();
  await page.waitForTimeout(1500);
  await page.getByText('高级异常明细',{exact:true}).first().click();
  await page.getByText('跨店与交易证据',{exact:true}).first().click();
  await page.getByTestId('stFileUploader').filter({hasText:'上传可选比对证据'}).locator('input[type=file]').setInputFiles(path.join(out,'模拟跨店.xlsx'));
  await page.getByRole('button',{name:'校验证据并留档',exact:true}).click();await page.waitForTimeout(500);
  await page.getByText('01复盘与智能找差异',{exact:true}).first().click();
  const grid=page.locator('#stocktake-workbench');await grid.locator('tbody tr').first().waitFor({timeout:20000});
  const search=grid.getByRole('textbox',{name:'搜索商品名、编码、完整条码或尾号'});
  await search.fill('0990000000000');
  check((await grid.locator('tbody tr .hint-summary').first().innerText()).includes('A换B'),'供应商A换B缺失');
  check((await grid.locator('tbody tr .risk-summary').first().innerText()).includes('跨店'),'跨店提示缺失');
  await search.fill('');
  const data=await grid.evaluate(el=>el.__inventory.data.rows);
  // 同时快速填写3行实数及备注，保留焦点期间等自动确认。
  for(const [index,row] of data.slice(0,3).entries()){
    await grid.getByRole('textbox',{name:`复盘实数 ${row.barcode}`,exact:true}).fill(String(index));
    await grid.getByRole('textbox',{name:`备注 ${row.barcode}`,exact:true}).fill('模拟快速录入'+index);
  }
  await waitSaved();
  const updated=await grid.evaluate(el=>el.__inventory.data.rows);
  for(const [index,row] of data.slice(0,3).entries())check(updated.find(x=>x.id===row.id).recount===index&&updated.find(x=>x.id===row.id).note==='模拟快速录入'+index,'连续录入丢失');
  const text=data.map(x=>`${x.barcode}\t${x.system}\t模拟核验`).join('\n');
  await grid.getByRole('button',{name:'批量粘贴',exact:true}).click();
  await grid.getByRole('textbox',{name:'批量粘贴复盘数据',exact:true}).fill(text);
  await grid.getByRole('button',{name:'校验并保存全部粘贴行',exact:true}).click();await waitSaved();
  await grid.getByRole('button',{name:'撤销上次输入',exact:true}).click();await waitSaved();
  await grid.getByRole('button',{name:'批量粘贴',exact:true}).click();
  await grid.getByRole('textbox',{name:'批量粘贴复盘数据',exact:true}).fill(text);
  await grid.getByRole('button',{name:'校验并保存全部粘贴行',exact:true}).click();await waitSaved();
  await page.getByText('02变化/导出',{exact:true}).first().click();
  await expand('正式导出检查 · 公司三列文件');
  for(const label of ['确认同门店、同期间且覆盖本次完整盘点范围','确认差异已核实、相关凭证齐备']){
    if(!await page.getByRole('checkbox',{name:label,exact:true}).isChecked()){
      const text=page.getByText(label,{exact:true});await text.evaluate(el=>el.scrollIntoView({block:'center'}));await text.click();
    }
  }
  await page.getByRole('button',{name:'保存审核参数',exact:true}).click();
  await expand('正式导出检查 · 公司三列文件');
  const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'下载公司最终三列 .xls 候选文件',exact:true}).click()]);
  await download.saveAs(path.join(out,'模拟正式三列.xls'));
  check(errors.length===0,errors.join('\n'));
  const result={pass:true,simulated_only:true,pdf_preview:true,archive_reprint_new_print:true,supplier_import_and_swap:true,cross_store_upload:true,rapid_rows_and_notes:true,bulk_and_undo:true,three_column_download_from_02:true,page_errors:errors};
  await fs.writeFile(path.join(out,'browser_module_results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}catch(e){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});throw e}
finally{await browser.close()}
