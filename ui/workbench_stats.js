// 仅使用后端未格式化十进制值。BigInt对齐小数位，不经浮点或界面字符串求和。
function decimalParts(raw){
  if(raw===null||raw===undefined||String(raw).trim()==='')return null;
  const text=String(raw).trim().replace(/^([+-]?)\./,(_,sign)=>sign+'0.');const m=text.match(/^([+-]?)(\d+)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/);if(!m)return null;
  const exponent=Number(m[4]||0);if(!Number.isSafeInteger(exponent)||Math.abs(exponent)>10000)return null;
  let coefficient=BigInt(m[2]+(m[3]||''))*(m[1]==='-'?-1n:1n),scale=(m[3]||'').length-exponent;
  if(scale<0){coefficient*=10n**BigInt(-scale);scale=0}return {coefficient,scale};
}
export function sumDecimal(values,minDecimals=0){
  const parts=values.map(decimalParts).filter(Boolean);const scale=parts.reduce((n,p)=>Math.max(n,p.scale),minDecimals);
  let total=parts.reduce((sum,p)=>sum+p.coefficient*10n**BigInt(scale-p.scale),0n);const sign=total<0n?'-':'';if(total<0n)total=-total;
  let digits=String(total).padStart(scale+1,'0');let whole=scale?digits.slice(0,-scale):digits,fraction=scale?digits.slice(-scale):'';
  while(fraction.length>minDecimals&&fraction.endsWith('0'))fraction=fraction.slice(0,-1);
  return sign+whole+(fraction?'.'+fraction:'');
}
export const cellKey=(id,field)=>JSON.stringify([id,field]);
export function selectionStats(rows,selection,drafts={}){
  const byid=rows instanceof Map?rows:new Map(rows.map(r=>[r.id,r]));let selected=0,numeric=0;const values=[],kinds=new Set();
  for(const key of selection){let id,field;try{[id,field]=JSON.parse(key)}catch{continue}const row=byid.get(id);if(!row)continue;selected++;
    const raw=field==='recount'&&drafts[id]?.['复盘实数']?drafts[id]['复盘实数'].value:row.stats_raw?.[field];if(!decimalParts(raw))continue;numeric++;
    values.push(raw);kinds.add(field==='amount'?'amount':'quantity');
  }
  // Excel式数字核对：不读商品单位或包装系数，也不作库存/金额口径推断。
  return {selected,numeric,sum:sumDecimal(values),mixed:kinds.size>1};
}
export const TOTAL_FIELDS=['system','initial','recount','total','diff','amount'];
export const SELECT_FIELDS=['name','barcode','code',...TOTAL_FIELDS];
export function selectedTable(rows,selection,drafts={}){
  const fields=SELECT_FIELDS.filter(field=>rows.some(r=>selection.has(cellKey(r.id,field))));
  const selected=rows.filter(r=>fields.some(field=>selection.has(cellKey(r.id,field))));
  const matrix=selected.map(r=>fields.map(field=>{
    if(!selection.has(cellKey(r.id,field)))return '';
    const raw=field==='recount'&&drafts[r.id]?.['复盘实数']?drafts[r.id]['复盘实数'].value:TOTAL_FIELDS.includes(field)?r.stats_raw?.[field]:r[field];
    return String(raw??'').replace(/[\t\r\n]+/g,' ');
  }));
  return {fields,ids:selected.map(r=>r.id),matrix};
}
export function clipboardTable(table,safe=true){
  const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const textField=field=>['name','barcode','code'].includes(field);
  const plain=table.matrix.map(row=>row.map((value,i)=>safe&&value&&(table.fields[i]==='barcode'||table.fields[i]==='code'||textField(table.fields[i])&&/^[=+\-@]/.test(value))?"'"+value:value).join('\t')).join('\r\n');
  const html='<html xmlns:x="urn:schemas-microsoft-com:office:excel"><meta charset="utf-8"><body><table>'+table.matrix.map(row=>'<tr>'+row.map((value,i)=>'<td'+(safe&&textField(table.fields[i])?' style="mso-number-format:\'\\@\'" x:str="'+esc(value)+'"':'')+'>'+esc(value)+'</td>').join('')+'</tr>').join('')+'</table></body></html>';
  return {plain,html};
}
export function columnTotals(rows){
  const columns={};
  for(const field of TOTAL_FIELDS){
    const values=rows.map(row=>row.stats_raw?.[field]).filter(raw=>decimalParts(raw)!==null);
    columns[field]={sum:sumDecimal(values,field==='amount'?2:0),numeric:values.length,missing:rows.length-values.length};
  }
  return {count:rows.length,reviewed:columns.recount.numeric,remaining:columns.recount.missing,columns};
}
export function rangeTotals(rows){
  const gain=[],loss=[];let missing=0;
  for(const row of rows){const raw=row.stats_raw?.amount,p=decimalParts(raw);if(!p){missing++;continue}(p.coefficient<0n?loss:gain).push(raw)}
  return {gain:sumDecimal(gain,2),loss:sumDecimal(loss,2),net:sumDecimal([...gain,...loss],2),missing};
}
