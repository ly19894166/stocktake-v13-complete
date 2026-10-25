// 更多工具补充回归：独立18542端口，12条模拟文件；主流程由browser_workflow验收。
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.dirname(fileURLToPath(import.meta.url)),out=path.join(root,'runtime/module_demo');
const url=process.env.STOCKTAKE_TEST_URL||'http://127.0.0.1:18542';
if(new URL(url).port==='8513'||!['127.0.0.1','localhost'].includes(new URL(url).hostname))throw Error('只允许独立模拟端口');
const browser=await chromium.launch({channel:process.env.STOCKTAKE_BROWSER_CHANNEL||'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
const check=(v,m)=>{if(!v)throw Error(m)};
const expand=async label=>{const s=page.locator('summary').filter({hasText:label});if(await s.locator('..').getAttribute('open')===null)await s.click()};
const tool=async name=>{await page.getByRole('combobox',{name:'更多工具',exact:true}).click();await page.getByRole('option',{name,exact:true}).click()};
try{
  await page.goto(url,{waitUntil:'networkidle'});
  await page.getByRole('button',{name:'上传盘点报表',exact:true}).click();
  await page.getByTestId('stFileUploader').filter({hasText:'上传盘点报表'}).locator('input[type=file]').setInputFiles(['模拟盘亏.xls','模拟盘盈.xls'].map(n=>path.join(root,'runtime/simulated',n)));
  const grid=page.locator('#stocktake-workbench');await grid.locator('tbody tr').first().waitFor();
  check((await grid.evaluate(el=>el.__inventory.data.rows)).length===12,'非12条模拟批次');
  await page.getByText('更多工具',{exact:true}).first().click();
  await page.getByTestId('stFileUploader').filter({hasText:'批量导入任意供应商Excel'}).locator('input[type=file]').setInputFiles(path.join(out,'模拟供应商.xlsx'));
  await page.getByRole('button',{name:'校验并追加供应商目录',exact:true}).click();await page.getByText('供应商目录已校验并保存',{exact:true}).waitFor();
  await tool('商品档案与异常分析');await page.getByText('跨店与交易证据',{exact:true}).first().click();
  await page.getByTestId('stFileUploader').filter({hasText:'上传可选比对证据'}).locator('input[type=file]').setInputFiles(path.join(out,'模拟跨店.xlsx'));
  await page.getByRole('button',{name:'校验证据并留档',exact:true}).click();await page.waitForTimeout(500);
  await page.getByText('01 连续复盘找差异',{exact:true}).first().click();await grid.locator('tbody tr').first().waitFor();
  const d=await grid.evaluate(el=>el.__inventory.data.rows),a=d.find(r=>r.barcode==='0990000000000');
  check(a.swap_count>0&&a.cross.length>0,'供应商A换B或跨店线索缺失');
  await grid.locator('.search').fill(a.barcode);await grid.locator('.row-link').click();
  await grid.locator('.panel .pair-card').first().waitFor();check((await grid.locator('.panel').textContent()).includes('A换B'),'详情缺少A换B');await grid.locator('.panel .close-panel').click();
  await page.getByText('更多工具',{exact:true}).first().click();await tool('商品档案与异常分析');
  for(const label of ['商品档案','参数与批次设置','复盘变化轨迹','成对候选']){await page.getByText(label,{exact:true}).first().click();await page.waitForTimeout(150);check(!await page.getByTestId('stException').count(),label+'异常')}
  await tool('变化清单/七表母版');await page.getByRole('button',{name:'生成完整V13工作簿草稿（7表）',exact:true}).waitFor();
  await tool('来源与本地备份');check(!await page.getByTestId('stException').count(),'来源备份入口异常');
  check(!errors.length,errors.join('\n'));
  const result={pass:true,simulated_only:true,supplier_import_and_swap:true,cross_store_upload:true,archives_parameters_trajectory_seven_tables_backup:true,page_errors:errors};
  await fs.writeFile(path.join(out,'browser_module_results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}catch(e){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e}
finally{await browser.close()}
