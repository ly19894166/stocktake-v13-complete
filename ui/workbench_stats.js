// 仅使用后端未格式化十进制值。BigInt对齐小数位，不经浮点或界面字符串求和。
function decimalParts(raw){
  if(raw===null||raw===undefined||String(raw).trim()==='')return null;
  const text=String(raw).trim().replace(/^([+-]?)\./,(_,sign)=>sign+'0.');const m=text.match(/^([+-]?)(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/);if(!m)return null;
  const exponent=Number(m[4]||0);if(!Number.isSafeInteger(exponent)||Math.abs(exponent)>10000)return null;
  let coefficient=BigInt(m[2]+(m[3]||''))*(m[1]==='-'?-1n:1n),scale=(m[3]||'').length-exponent;
  if(scale<0){coefficient*=10n**BigInt(-scale);scale=0}return {coefficient,scale};
}
export function sumDecimal(values,minDecimals=0){
  const parts=values.map(decimalParts).filter(Boolean);const scale=Math.max(minDecimals,...parts.map(p=>p.scale));
  let total=parts.reduce((sum,p)=>sum+p.coefficient*10n**BigInt(scale-p.scale),0n);const sign=total<0n?'-':'';if(total<0n)total=-total;
  let digits=String(total).padStart(scale+1,'0');let whole=scale?digits.slice(0,-scale):digits,fraction=scale?digits.slice(-scale):'';
  while(fraction.length>minDecimals&&fraction.endsWith('0'))fraction=fraction.slice(0,-1);
  return sign+whole+(fraction?'.'+fraction:'');
}
export const cellKey=(id,field)=>JSON.stringify([id,field]);
export function selectionStats(rows,selection,drafts={}){
  const byid=rows instanceof Map?rows:new Map(rows.map(r=>[r.id,r]));let selected=0,numeric=0;const groups=new Map();
  for(const key of selection){let id,field;try{[id,field]=JSON.parse(key)}catch{continue}const row=byid.get(id);if(!row)continue;selected++;
    const raw=field==='recount'&&drafts[id]?.['复盘实数']?drafts[id]['复盘实数'].value:row.stats_raw?.[field];if(!decimalParts(raw))continue;numeric++;
    const money=field==='amount',unit=money?'元':row.unit||`第${row.sequence}条·单位待确认`,group=(money?'金额:':'数量:')+unit;
    if(!groups.has(group))groups.set(group,{unit,money,values:[]});groups.get(group).values.push(raw);
  }
  return {selected,numeric,groups:[...groups.values()].map(g=>({unit:g.unit,money:g.money,sum:sumDecimal(g.values,g.money?2:0)}))};
}
export function rangeTotals(rows){
  const gain=[],loss=[];let missing=0;
  for(const row of rows){const raw=row.stats_raw?.amount,p=decimalParts(raw);if(!p){missing++;continue}(p.coefficient<0n?loss:gain).push(raw)}
  return {gain:sumDecimal(gain,2),loss:sumDecimal(loss,2),net:sumDecimal([...gain,...loss],2),missing};
}
