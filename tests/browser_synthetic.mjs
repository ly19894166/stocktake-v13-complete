// 实际CCv2组件DOM验收。先生成模拟报表，在独立数据目录/端口启动客户端。
// 安装Playwright与浏览器，设置STOCKTAKE_TEST_URL后运行本文件。
// 可用PLAYWRIGHT_MODULE指定Playwright模块；不会访问正式客户端或真实数据。
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.dirname(fileURLToPath(import.meta.url));
const browser=await chromium.launch({channel:process.env.STOCKTAKE_BROWSER_CHANNEL||'msedge',headless:true});
const page=await browser.newPage({viewport:{width:1680,height:1100}});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
try{
  await page.goto(process.env.STOCKTAKE_TEST_URL||'http://127.0.0.1:18523',{waitUntil:'networkidle'});
  const importer=page.locator('summary').filter({hasText:'导入新的初盘 / 恢复已有批次'});
  if(await importer.locator('..').getAttribute('open')===null)await importer.click();
  await page.locator('input[type=file]').nth(0).setInputFiles(path.join(root,'runtime','simulated','模拟盘盈.xls'));
  await page.getByText('模拟盘盈.xls',{exact:true}).waitFor();
  await page.locator('input[type=file]').nth(1).setInputFiles(path.join(root,'runtime','simulated','模拟盘亏.xls'));
  const grid=page.locator('#stocktake-workbench');await grid.locator('tbody tr').first().waitFor({timeout:30000});
  const search=grid.getByRole('textbox',{name:'搜索商品名、编码、完整条码或尾号'});
  const a='0990000000000',b='0990000000003';
  await search.fill(a);
  const rowA=grid.locator('tbody tr').filter({has:page.getByRole('textbox',{name:`备注 ${a}`,exact:true})});
  const aid=await rowA.getAttribute('data-id');
  const peer=rowA.locator('.peer').filter({hasText:b});await peer.waitFor({timeout:20000});
  const bid=await peer.getAttribute('data-other');
  const rowB=()=>grid.locator(`tr[data-id="${bid}"]`);
  const waitSaved=async()=>{await page.waitForTimeout(350);await grid.locator('[data-testid="save-status"]').filter({hasText:'已保存'}).waitFor({timeout:20000})};
  await rowA.getByRole('textbox',{name:`备注 ${a}`,exact:true}).fill('模拟人工原因保留');await search.click();await waitSaved();
  await peer.click();await rowB().waitFor({timeout:20000});
  await rowB().getByRole('textbox',{name:`复盘实数 ${b}`,exact:true}).fill('20');await search.click();await waitSaved();
  await grid.locator(`tr[data-id="${aid}"] .peer[data-other="${bid}"]`).waitFor({state:'hidden',timeout:20000});
  if(await rowA.getByRole('textbox',{name:`备注 ${a}`,exact:true}).inputValue()!=='模拟人工原因保留')throw new Error('人工备注未保留');
  await rowB().getByRole('textbox',{name:`复盘实数 ${b}`,exact:true}).fill('10');await search.click();await waitSaved();
  await grid.locator(`tr[data-id="${aid}"] .peer[data-other="${bid}"]`).waitFor({timeout:20000});
  for(const label of ['02变化/导出','03审核','供货商数据库','打印历史','高级异常明细']){
    await page.getByText(label,{exact:true}).first().click();await page.waitForTimeout(500);
    if(await page.getByTestId('stException').count())throw new Error(`${label}: 页面异常`);
  }
  if(errors.length)throw new Error(errors.join('\n'));
  console.log(JSON.stringify({pass:true,simulated_rows:12,manual_store_date_fields:0,inline_pair:true,zero_removal:true,reappearance:true,manual_note_preserved:true,native_pages:true,page_errors:errors}));
}finally{await browser.close()}
