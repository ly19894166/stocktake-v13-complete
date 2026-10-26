import fs from 'node:fs/promises';import assert from 'node:assert/strict';
const code=await fs.readFile(new URL('../ui/workbench_stats.js',import.meta.url),'utf8');const {cellKey,selectedTable,clipboardTable,selectionStats}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const ui=await fs.readFile(new URL('../ui/workbench.js',import.meta.url),'utf8');const {filterRows}=await import('data:text/javascript;base64,'+Buffer.from(ui).toString('base64'));
const rows=Array.from({length:2407},(_,i)=>({id:'SIM'+i,name:i===0?'=模拟文本':'模拟'+i,barcode:'000123456789012345678901',code:'000000001',supplier_status:'other',recount:null,diff:i%2?-3:2,amount:i%2?-6:4,mix_count:i%2,flags:[],stats_raw:{system:'0.1',initial:'24',amount:i%2?'-6':'4'},issues:{pending:true,significant_change:i===1,export_issue:true,missing_cost:i===3}}));
const selected=new Set(rows.map(r=>cellKey(r.id,'system')));assert.equal(selectionStats(rows,selected).selected,2407);assert.equal(selectionStats(rows,selected).sum,'240.7');assert.equal(selectedTable(rows,selected).matrix.length,2407);
const only=rows.filter((r,i)=>i%2);assert.equal(selectedTable(only,selected).matrix.length,1203);
let s=new Set([cellKey(rows[1].id,'code'),cellKey(rows[0].id,'name'),cellKey(rows[0].id,'barcode'),cellKey(rows[0].id,'code')]);
const t=selectedTable(rows,s);assert.deepEqual(t.fields,['name','barcode','code']);assert.deepEqual(t.ids,['SIM0','SIM1']);assert.equal(t.matrix[1][0],'');
const c=clipboardTable(t,true);assert(c.plain.startsWith("'=模拟文本\t'000123456789012345678901\t'000000001"));assert(c.html.includes('mso-number-format'));assert(c.html.includes('000123456789012345678901'));assert(!clipboardTable(t,false).plain.includes("'000"));
assert(c.html.includes('x:str="000123456789012345678901"')); // WPS要求文本属性包含实际值，不能只写空属性。
assert.equal(filterRows(rows,{scope:'all',quick:'large_loss'}).length,1203);assert.equal(filterRows(rows,{scope:'all',quick:'changed'}).length,1);assert.equal(filterRows(rows,{scope:'all',quick:'missing_cost'}).length,1);assert.equal(filterRows(rows,{scope:'all',quick:'unreviewed_diff'}).length,2407);
console.log('2407条全量选区/筛选复制、顺序、Tab矩阵、前导零安全文本和问题快捷筛选通过');
