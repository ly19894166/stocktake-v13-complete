import fs from 'node:fs/promises';import assert from 'node:assert/strict';
const code=await fs.readFile(new URL('../ui/workbench.js',import.meta.url),'utf8'),{selectionScrollLimits,selectionRowAt,filterRows}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
assert.deepEqual(selectionScrollLimits(2000,5000,-400,2800,140,1000),{min:1460,max:3800});
assert.equal(selectionScrollLimits(1460,5000,140,3300,140,1000).min,1460);
assert.equal(selectionScrollLimits(0,5000,794,3000,140,730).min,0); // 首行还在自然位置时不能把页面向上拖走。
assert.equal(selectionScrollLimits(4000,5000,-1000,700,140,1000).max,4000); // 不反向跳回。
const boxes=[{top:140,bottom:178},{top:178,bottom:260},{top:260,bottom:298}];assert.equal(selectionRowAt(boxes,141),0);assert.equal(selectionRowAt(boxes,100),0);assert.equal(selectionRowAt(boxes,200),1);assert.equal(selectionRowAt(boxes,999),2);
const rows=[{id:'a',supplier_status:'zbf',diff:3,recount:null,zbf_pending:true,flags:[]},{id:'b',supplier_status:'zbf',diff:-2,recount:0,flags:[]},{id:'c',supplier_status:'other',diff:3,recount:null,flags:[]}];
assert.deepEqual(filterRows(rows,{scope:'zbf',quick:'zbf_gain'}).map(x=>x.id),['a']);assert.deepEqual(filterRows(rows,{scope:'zbf',quick:'zbf_pending'}).map(x=>x.id),['a']);assert.deepEqual(filterRows(rows,{scope:'zbf',quick:'zbf_loss'}).map(x=>x.id),['b']);
console.log('首行滚动下限、尾行上限、变高商品命中及卓不凡快捷范围通过');
