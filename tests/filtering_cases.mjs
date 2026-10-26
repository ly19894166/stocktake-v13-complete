import fs from 'node:fs/promises';import assert from 'node:assert/strict';
const source=await fs.readFile(new URL('../ui/workbench.js',import.meta.url),'utf8');
const {filterRows}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const rows=[
 {id:1,name:'模拟甲',barcode:'0990000000001',code:'0001',category:'模拟饮料',supplier:'卓不凡',supplier_status:'zbf',eligible:true,diff:0,amount:0,recount:0,system:20,initial:25,note:'人工说明',mix_count:0,swap_count:0,flags:[]},
 {id:2,name:'模拟乙',barcode:'0990000000002',code:'0002',category:'模拟饮料',supplier:'供货商待确认',supplier_status:'pending',eligible:false,diff:-8,amount:-28,recount:null,system:20,initial:12,note:'',mix_count:2,swap_count:0,flags:['盘亏']},
 {id:3,name:'模拟丙',barcode:'0990000000003',code:'0003',category:'模拟零食',supplier:'模拟其他',supplier_status:'other',eligible:true,diff:4,amount:14,recount:24,system:20,initial:22,note:'',mix_count:1,swap_count:1,flags:['盘盈']},
 {id:4,name:'模拟缺成本',barcode:'0990000000004',code:'0004',category:'模拟零食',supplier:'供货商待确认',supplier_status:'pending',eligible:false,diff:-1,amount:null,recount:null,system:20,initial:19,note:' ',mix_count:0,swap_count:0,flags:['缺成本']},
];
const ids=f=>filterRows(rows,{scope:'all',columns:{},...f}).map(r=>r.id);
assert.deepEqual(ids({scope:'exclude'}),[2,3,4]);assert.deepEqual(ids({scope:'zbf'}),[1]);assert.deepEqual(ids({scope:'eligible'}),[1,3]);
for(const [mode,expected] of [['loss',[2,4]],['gain',[3]],['zero',[1]],['nonzero',[2,3,4]],['unreviewed',[2,4]],['reviewed',[1,3]]])assert.deepEqual(ids({columns:{diff:{mode}}}),expected);
assert.deepEqual(ids({columns:{recount:{mode:'zero'}}}),[1]);assert.deepEqual(ids({columns:{recount:{mode:'blank'}}}),[2,4]);assert.deepEqual(ids({columns:{amount:{mode:'missing'}}}),[4]);
assert.deepEqual(ids({columns:{amount:{min:-50,max:-20}}}),[2]);assert.deepEqual(ids({columns:{amount:{min:0,max:0}}}),[1]);
assert.deepEqual(ids({category:'模拟饮料',columns:{diff:{min:-10,max:-7},note:{mode:'no'}}}),[2]);
assert.deepEqual(ids({query:'000003'}),[3]);assert.deepEqual(ids({columns:{code:{text:'0002'}}}),[2]);assert.deepEqual(ids({columns:{name:{text:'缺成本'}}}),[4]);
for(const [mode,expected] of [['mix',[2,3]],['eligible',[1,3]],['swap',[3]],['pending',[2,4]]])assert.deepEqual(ids({columns:{hints:{mode}}}),expected);
assert.deepEqual(ids({supplier:'供货商待确认',columns:{system:{min:20,max:20},initial:{max:15}}}),[2]);
console.log('前端组合筛选独立边界测试通过：资格、待确认、0/空白、金额未知、区间和搜索');
