export default function(component) {
  const {parentElement}=component;
  const data=typeof component.data==='string'?JSON.parse(component.data):component.data;
  // CCv2在触发与重跑间可能先调用一次无业务data的生命周期，保留原DOM和草稿。
  if(!data||!Array.isArray(data.rows))return;
  const root=parentElement.querySelector('#stocktake-workbench');
  if(!root)return;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=(v,n=4)=>v===null||v===undefined?'—':Number(v).toLocaleString('zh-CN',{minimumFractionDigits:n===2?2:0,maximumFractionDigits:n});
  const cls=v=>v<0?'red':v>0?'green':'zero';
  let S=root.__inventory;
  if(!S){
    let local={};try{local=JSON.parse(localStorage.getItem('stocktake:'+data.batch)||'{}')}catch{}
    S=root.__inventory={query:local.query||'',filters:local.filters||[],category:local.category||'',supplier:local.supplier||'',sort:local.sort||'amount',page:0,size:20,drafts:local.drafts||{},queue:[],inflight:null,rows:new Map(),dom:new Map(),focus:null,seenAck:null,viewKey:'',restore:!!Object.keys(local.drafts||{}).length,metaDrafts:local.metaDrafts||{},timers:{},reportOpen:false,detailOpen:false};
    root.innerHTML=`<div class="operating-panel">
      <div class="operating-inputs"><label>实际销售金额（元）<input data-meta="sales_amount" inputmode="decimal" aria-label="实际销售金额（元）" placeholder="待填写"></label><label>同期含税销售成本（元）<input data-meta="sales_cost" inputmode="decimal" aria-label="同期含税销售成本（元）" placeholder="待填写"></label><div class="calculation-status"></div><button class="report-open primary">生成盘点汇报</button></div>
      <div class="metrics" data-testid="metrics"></div><div class="audit muted">当前测算，仅供复盘；正式导出仍须在02完整检查。</div></div>
      <div class="toolbar primary-tools"><input class="search" aria-label="搜索商品名、编码、完整条码或尾号" placeholder="商品名称 / 编码 / 完整条码 / 尾号4–8位"><select class="category" aria-label="品类筛选"></select><button class="undo">撤销上次输入</button><button class="bulk-toggle">批量粘贴</button><button class="more-toggle" aria-expanded="false">更多筛选</button></div>
      <div class="more-filters hidden"><div class="toolbar"><select class="supplier" aria-label="供应商筛选"></select><select class="sort" aria-label="建议排序"><option value="amount">金额优先</option><option value="quantity">数量优先</option><option value="mix">同类串码优先</option><option value="category">按品类现场找货</option><option value="score">综合建议分</option></select><select class="size" aria-label="每页显示"><option value="20">每页20条</option><option value="50">每页50条</option><option value="100">每页100条</option></select><button class="refresh">刷新数据</button><button class="clear">清除筛选</button></div><div class="chips"></div><span class="muted">组合筛选同时满足；建议排序只供找差异，不改变审核标准。</span></div>
      <select class="locate hidden" aria-label="条码尾号匹配结果"></select><div class="message"></div>
      <div class="bulk hidden"><strong>批量粘贴复盘数</strong><p class="muted">每行：完整条码 Tab 复盘实数 Tab 人工备注（可省略）。全部校验通过后一次保存。</p><textarea aria-label="批量粘贴复盘数据"></textarea><button class="primary bulk-submit">校验并保存全部粘贴行</button></div>
      <div class="guide"><span class="result-count"></span><span class="saved" data-testid="save-status"></span></div>
      <div class="table-wrap"><table aria-label="01现场复盘表"><colgroup><col style="width:4%"><col style="width:32%"><col style="width:14%"><col style="width:12%"><col style="width:20%"><col style="width:18%"></colgroup><thead><tr><th>序号</th><th>商品 / 条码 / 系统与初盘</th><th>最新差异 / 成本</th><th>复盘实数</th><th>人工备注</th><th>智能找差异</th></tr></thead><tbody></tbody></table></div>
      <div class="pagination"><button class="prev">上一页</button><span class="page-info"></span><button class="next">下一页</button></div>
      <dialog class="panel" aria-label="商品详情与对应候选"></dialog>
      <dialog class="report-dialog" aria-label="季度盘点汇报"><div class="panel-title"><strong>季度盘点汇报</strong><button class="report-close">关闭</button></div><div class="report-fields"></div><p class="report-warnings muted"></p><label class="report-label">最终文稿（可直接编辑，自动保存）<textarea class="report-text" aria-label="最终盘点汇报文稿"></textarea></label><div class="toolbar"><button class="report-copy primary">一键复制文稿</button><button class="report-reset">按最新数据重新生成</button><button class="report-old hidden">查看上次人工稿</button><span class="copy-status" aria-live="polite"></span></div></dialog>`;
    const q=s=>root.querySelector(s);
    const remember=()=>{try{localStorage.setItem('stocktake:'+S.data.batch,JSON.stringify({query:S.query,filters:S.filters,category:S.category,supplier:S.supplier,sort:S.sort,drafts:S.drafts,metaDrafts:S.metaDrafts}))}catch{}};
    S.remember=remember;
    S.enqueue=(kind,extra={})=>{S.queue.push({kind,...extra,request_id:crypto.randomUUID()});S.pump()};
    S.pump=()=>{if(S.inflight||!S.queue.length)return;const event=S.queue.shift();S.inflight=event;S.comp.setTriggerValue('action',{...event,revision:S.data.revision});q('.saved').textContent='保存 / 载入中…'};
    S.commit=(id,field)=>{const draft=S.drafts[id]?.[field];if(!draft)return;const exists=[S.inflight,...S.queue].some(e=>e?.kind==='edit'&&e.id===id&&e.field===field&&e.value===draft.value);if(!exists)S.enqueue('edit',{id,field,value:draft.value,base:draft.base})};
    S.metaValue=key=>key.startsWith('report.')?S.data.report.config[key.slice(7)]:S.data.finance[key];
    S.commitMeta=key=>{const draft=S.metaDrafts[key];if(!draft)return;const queued=[S.inflight,...S.queue].some(e=>e?.kind==='meta'&&e.metaKey===key&&e.value===draft.value);if(!queued)S.enqueue('meta',{scope:key.startsWith('report.')?'report':'finance',field:key.split('.').at(-1),metaKey:key,value:draft.value,base:draft.base,signature:draft.signature})};
    S.bindMeta=(input,key)=>{input.oninput=()=>{const prior=S.metaDrafts[key];S.metaDrafts[key]={value:input.type==='checkbox'?input.checked:input.value,base:prior?prior.base:S.metaValue(key),signature:S.data.report.signature};S.remember();q('.saved').textContent='有未保存输入…';clearTimeout(S.timers[key]);if(input.type==='checkbox')S.commitMeta(key);else S.timers[key]=setTimeout(()=>S.commitMeta(key),650)};input.onblur=()=>S.commitMeta(key);input.onchange=()=>S.commitMeta(key)};
    for(const input of root.querySelectorAll('[data-meta]'))S.bindMeta(input,input.dataset.meta);
    const fields=[['store','门店（仅用于汇报）','text'],['report_date','汇报日期','date'],['sales_start','销售统计起日','date'],['sales_end','销售统计止日','date'],['quarter','季度','text'],['reason','主要原因（由店长确认）','textarea'],['reason_confirmed','我已核对并确认主要原因','checkbox'],['fresh_enabled','附加独立鲜食盘点数据','checkbox'],['fresh_start','鲜食统计起日','date'],['fresh_end','鲜食统计止日','date'],['fresh_sales','鲜食销售金额（元）','text'],['fresh_cost','鲜食含税成本（元）','text'],['fresh_gain','鲜食盘盈（正数或0）','text'],['fresh_loss','鲜食盘亏（负数或0）','text']];
    q('.report-fields').innerHTML=fields.map(([key,label,type])=>`<label class="${key.startsWith('fresh_')&&key!=='fresh_enabled'?'fresh-field ':''}${type==='textarea'?'wide':''}">${esc(label)}${type==='textarea'?`<textarea data-report="${key}" aria-label="${esc(label)}"></textarea>`:`<input type="${type}" data-report="${key}" aria-label="${esc(label)}">`}</label>`).join('');
    for(const input of q('.report-fields').querySelectorAll('[data-report]'))S.bindMeta(input,'report.'+input.dataset.report);
    S.bindMeta(q('.report-text'),'report.draft');
    S.flush=()=>{for(const [id,fields] of Object.entries(S.drafts))for(const field of Object.keys(fields))S.commit(id,field);for(const key of Object.keys(S.metaDrafts))S.commitMeta(key)};
    q('.report-open').onclick=()=>{S.flush();S.reportOpen=true;S.renderReport()};
    q('.report-close').onclick=()=>{S.flush();S.reportOpen=false;q('.report-dialog').close()};
    q('.report-dialog').oncancel=()=>{S.flush();S.reportOpen=false};
    q('.report-reset').onclick=()=>{const input=q('.report-text');input.value=S.data.report.generated;input.dispatchEvent(new Event('input'));S.commitMeta('report.draft');q('.copy-status').textContent='已按当前批次重新生成，正在保存'};
    q('.report-old').onclick=()=>{q('.report-text').value=S.data.report.stale_draft;q('.copy-status').textContent='这是旧人工稿，仅供对照；数字可能已过期，请核对后编辑或重新生成'};
    q('.report-copy').onclick=async()=>{S.flush();const output=q('.report-text');try{await navigator.clipboard.writeText(output.value);q('.copy-status').textContent='已复制，可粘贴到微信群或WPS'}catch{output.focus();output.select();q('.copy-status').textContent=document.execCommand('copy')?'已复制':'请按Ctrl+C复制已选文字'}};
    S.renderReport=()=>{const dialog=q('.report-dialog');if(!S.reportOpen)return;if(!dialog.open)dialog.showModal();const report=S.data.report;
      for(const input of dialog.querySelectorAll('[data-report]')){const key=input.dataset.report,value=S.metaDrafts['report.'+key]?.value??report.config[key]??'';if(input.type==='checkbox')input.checked=!!value;else if(parentElement.activeElement!==input&&input.value!==String(value))input.value=String(value)}
      const fresh=!!(S.metaDrafts['report.fresh_enabled']?.value??report.config.fresh_enabled);dialog.querySelectorAll('.fresh-field').forEach(el=>el.classList.toggle('hidden',!fresh));
      const editor=q('.report-text'),draft=S.metaDrafts['report.draft'];if(parentElement.activeElement!==editor){const next=draft?draft.value:report.text;if(editor.value!==next)editor.value=next}
      q('.report-warnings').textContent=[...report.warnings,report.stale_draft?'数据已变化，当前显示实时新稿；旧人工稿可对照查看':'',S.inflight||S.queue.length?'正在保存输入，请等待顶部显示已保存再关闭程序':''].filter(Boolean).join('；');
      q('.report-old').classList.toggle('hidden',!report.stale_draft);
    };
    q('.more-toggle').onclick=()=>{const hidden=q('.more-filters').classList.toggle('hidden');q('.more-toggle').setAttribute('aria-expanded',String(!hidden))};
    q('.search').value=S.query;
    q('.search').oninput=e=>{S.query=e.target.value;S.page=0;remember();S.render()};
    q('.category').onchange=e=>{S.category=e.target.value;S.page=0;remember();S.render()};
    q('.supplier').onchange=e=>{S.supplier=e.target.value;S.page=0;remember();S.render()};
    q('.sort').value=S.sort;q('.sort').onchange=e=>{S.sort=e.target.value;S.page=0;remember();S.render()};
    q('.size').onchange=e=>{S.size=Number(e.target.value);S.page=0;S.render()};
    q('.clear').onclick=()=>{S.query='';S.filters=[];S.category='';S.supplier='';S.page=0;S.focus=null;q('.search').value='';q('.category').value='';q('.supplier').value='';remember();S.render()};
    q('.undo').onclick=()=>S.enqueue('undo');q('.refresh').onclick=()=>S.enqueue('refresh');
    q('.bulk-toggle').onclick=()=>q('.bulk').classList.toggle('hidden');
    q('.bulk-submit').onclick=()=>S.enqueue('bulk',{text:q('.bulk textarea').value});
    q('.prev').onclick=()=>{S.page=Math.max(0,S.page-1);S.render();q('.table-wrap').scrollTop=0};
    q('.next').onclick=()=>{S.page++;S.render();q('.table-wrap').scrollTop=0};
    q('.locate').onchange=e=>{if(e.target.value)S.openDetail(e.target.value,null)};
    S.openDetail=(a,b)=>{S.detailOpen=true;S.requestedDetail={a,b:b||null};S.focus=b||a;S.enqueue('detail',{a,b});S.render()};
    S.render=()=>{
      const d=S.data,stats=d.stats;
      const p=d.panel;
      for(const input of root.querySelectorAll('[data-meta]')){const value=S.metaDrafts[input.dataset.meta]?.value??d.finance[input.dataset.meta]??'';if(parentElement.activeElement!==input&&input.value!==String(value))input.value=String(value)}
      q('.calculation-status').className='calculation-status '+(p.status==='当前测算达标'?'green':p.status==='当前测算超标'?'red':'zero');q('.calculation-status').textContent=p.status;
      const metrics=[['盘盈（元）',p.gain,'green'],['盘亏（元）',p.loss,'red'],['净差异（元）',p.net,cls(Number(p.net))],['净差异率',p.rate===null?'待计算':p.rate+'‰',p.rate===null?'zero':''],['2‰允许损耗（元）',p.allowance,p.allowance===null?'zero':''],[p.over_limit?'超标金额（元）':'剩余额度（元）',p.remaining===null?null:fmt(Math.abs(Number(p.remaining)),2),p.remaining===null?'zero':p.over_limit?'red':'green'],['已填 / 剩余',p.done+' / '+p.remaining_rows,'']];
      q('.metrics').innerHTML=metrics.map(([label,value,color])=>`<div class="metric"><small>${esc(label)}</small><strong class="${color}">${esc(value??'待计算')}</strong></div>`).join('');
      q('.audit').textContent=p.note;
      S.renderReport();
      const message=q('.message');message.innerHTML=d.error?`<div class="error">${esc(d.error)}</div>`:S.restore?'<div class="notice">已保留上次未确认草稿。检查黄色输入框，按Enter或离开单元格保存；不会把空白当作0。</div>':'';
      q('.chips').innerHTML=d.filters.map(f=>`<button class="chip ${S.filters.includes(f)?'active':''}" data-filter="${esc(f)}">${esc(f)}</button>`).join('');
      q('.chips').querySelectorAll('button').forEach(b=>b.onclick=()=>{S.filters=S.filters.includes(b.dataset.filter)?S.filters.filter(f=>f!==b.dataset.filter):[...S.filters,b.dataset.filter];S.page=0;remember();S.render()});
      let rows=[...S.rows.values()].filter(r=>(!S.query||[r.name,r.barcode,r.code].some(v=>String(v).toLowerCase().includes(S.query.toLowerCase())))&&(!S.category||r.category===S.category)&&(!S.supplier||r.supplier===S.supplier)&&S.filters.every(f=>r.flags.includes(f)));
      rows.sort((a,b)=>S.sort==='amount'?Math.abs(b.amount||0)-Math.abs(a.amount||0)||b.score-a.score:S.sort==='quantity'?Math.abs(b.diff||0)-Math.abs(a.diff||0):S.sort==='mix'?b.mix_count-a.mix_count||Math.abs(b.amount||0)-Math.abs(a.amount||0):S.sort==='score'?b.score-a.score:a.category.localeCompare(b.category,'zh-CN')||a.sequence-b.sequence);
      const found=rows.length,pages=Math.max(1,Math.ceil(found/S.size));S.page=Math.min(S.page,pages-1);let visible=rows.slice(S.page*S.size,(S.page+1)*S.size);
      if(S.focus&&S.rows.has(S.focus)&&!visible.some(r=>r.id===S.focus))visible=[S.rows.get(S.focus),...visible];
      S.visible=visible;
      const locate=q('.locate');if(/^\d{4,8}$/.test(S.query)&&rows.length>1){locate.classList.remove('hidden');locate.innerHTML='<option value="">尾号对应多个商品，请选择完整条码定位</option>'+rows.map(r=>`<option value="${esc(r.id)}">${esc(r.name+' / '+r.barcode)}</option>`).join('')}else locate.classList.add('hidden');
      q('.result-count').textContent=`当前 ${found} / ${S.rows.size} 条 · 点提示看对应商品`;
      q('.page-info').textContent=`${S.page+1} / ${pages} 页`;q('.prev').disabled=S.page===0;q('.next').disabled=S.page>=pages-1;
      q('.saved').textContent=S.inflight?'保存 / 载入中…':Object.keys(S.metaDrafts).length||Object.keys(S.drafts).length?'有未确认草稿':`已保存 · ${d.saved_at||d.imported_at} · 版本 ${d.revision}`;
      const tbody=q('tbody');const keep=new Set(visible.map(r=>r.id));
      for(const tr of [...tbody.children])if(!keep.has(tr.dataset.id))tr.remove();
      for(let i=0;i<visible.length;i++){
        const r=visible[i];let tr=S.dom.get(r.id);
        if(!tr){tr=document.createElement('tr');tr.dataset.id=r.id;tr.innerHTML='<td class="seq"></td><td class="product"></td><td class="difference num"></td><td><input class="edit-count" inputmode="decimal"></td><td><textarea class="edit-note" rows="1"></textarea></td><td class="hints"></td>';S.dom.set(r.id,tr);
          for(const [field,selector] of [['复盘实数','.edit-count'],['备注','.edit-note']]){
            const input=tr.querySelector(selector);input.dataset.field=field;input.setAttribute('aria-label',`${field} ${r.barcode}`);
            input.oninput=()=>{const prior=S.drafts[r.id]?.[field];S.drafts[r.id]??={};S.drafts[r.id][field]={value:input.value,base:prior?prior.base:(field==='复盘实数'?S.rows.get(r.id).recount:S.rows.get(r.id).note)};q('.saved').textContent='正在自动保存输入…';remember();const timerKey=r.id+'|'+field;clearTimeout(S.timers[timerKey]);S.timers[timerKey]=setTimeout(()=>S.commit(r.id,field),650)};
            input.onblur=()=>S.commit(r.id,field);
            input.onkeydown=e=>{if(e.key==='Enter'&&(field==='复盘实数'||!e.shiftKey)){e.preventDefault();S.commit(r.id,field);const idx=S.visible.findIndex(x=>x.id===r.id);const next=S.dom.get(S.visible[idx+1]?.id)?.querySelector(selector);if(next)next.focus()}};
          }
        }
        tr.className=r.id===S.focus?'selected':'';
        tr.querySelector('.seq').textContent=r.sequence;
        tr.querySelector('.product').innerHTML=`<button class="row-link name">${esc(r.name)}</button><span class="codes">${esc(r.barcode)}</span><span class="minor">系统 ${esc(fmt(r.system))} / 初盘 ${esc(fmt(r.initial))}</span>`;
        tr.querySelector('.row-link').onclick=()=>S.openDetail(r.id,null);
        tr.querySelector('.difference').innerHTML=`<strong class="${cls(r.diff)}">${r.diff>0?'+':''}${esc(fmt(r.diff))}</strong><span class="minor ${cls(r.amount)}">¥ ${esc(fmt(r.amount,2))}</span>`;
        for(const [field,selector,value] of [['复盘实数','.edit-count',r.recount],['备注','.edit-note',r.note]]){const input=tr.querySelector(selector);const draft=S.drafts[r.id]?.[field];const next=draft?draft.value:(value??'');if(parentElement.activeElement!==input&&input.value!==String(next))input.value=String(next)}
        const hints=tr.querySelector('.hints');
        const labels=[];if(r.mix_count)labels.push(`疑似串码 ${r.mix_count}项`);if(r.swap_count)labels.push(`A换B ${r.swap_count}项`);
        hints.innerHTML=labels.length?`<button class="hint-summary">${esc(labels.join(' · '))} ›</button>`:'';
        const summary=hints.querySelector('.hint-summary');if(summary)summary.onclick=()=>S.openDetail(r.id,null);
        const other=[];if(r.cross?.length)other.push(`跨店 ${r.cross.length}项`);if(r.unit_hints.length)other.push(`单位 ${r.unit_hints.length}项`);if(r.risk_hints?.length)other.push(`异常 ${r.risk_hints.length}项`);
        if(other.length){const b=document.createElement('button');b.className='risk-summary';b.textContent=other.join(' · ')+' ›';b.onclick=()=>S.openDetail(r.id,null);hints.appendChild(b)}
        if(tbody.children[i]!==tr)tbody.insertBefore(tr,tbody.children[i]||null);
      }
      const panel=q('.panel');const detail=d.detail;
      if(detail&&S.detailOpen&&(!S.requestedDetail||(detail.a.id===S.requestedDetail.a&&(detail.b?.id||null)===S.requestedDetail.b))){
        if(!panel.open)panel.showModal();
        const card=r=>`<div class="pair-card"><b>${esc(r.name)}</b><span class="codes">${esc(r.barcode)} / 编码 ${esc(r.code)}</span><dl>${[['系统数',r.system],['初盘数',r.initial],['复盘实数',r.recount===null?'空白':r.recount],['当前总数',r.total],['最新差异',r.diff],['成本',r.cost],['成本依据',r.cost_basis],['规格 / 件装单位',[r.spec,r.unit].filter(Boolean).join(' / ')||'未提供'],['包装系数',r.packing],['零售价',r.retail===null?'缺售价':r.retail],['部 / 大 / 中类',[r.department,r.category,r.middle].join(' / ')],['供货商',r.supplier],['人工原因',r.note||'未填']].map(([a,b])=>`<dt>${esc(a)}</dt><dd>${esc(b??'缺失')}</dd>`).join('')}</dl><button class="jump" data-id="${esc(r.id)}">定位此商品</button></div>`;
        panel.innerHTML=`<div class="panel-title"><span>商品对照 / 输入轨迹 · ${detail.pair?esc(detail.pair.kind+' · '+detail.pair.confidence):'疑似线索，未经确认；归零会自动撤销'}</span><button class="close-panel">收起</button></div><div class="pair-cards">${card(detail.a)}${detail.b?card(detail.b):''}</div>${detail.pair?`<p>${esc(detail.pair.evidence)} · 可解释数量 ${esc(detail.pair.overlap)} · 金额 ¥${esc(detail.pair.amount_overlap)}；疑似待核，不自动抵销。</p>`:''}<div class="detail-peers"></div><p class="risk">${esc([...detail.a.unit_hints,...(detail.a.risk_hints||[]),...(detail.a.cross||[]).map(c=>JSON.stringify(c))].join("；"))}</p><div class="history">${(detail.history||[]).map(h=>`<article>${esc(h.北京时间)} · ${esc(h.操作人)} · ${esc(h.修改来源)}<br>${esc(JSON.stringify(h.旧值))} → ${esc(JSON.stringify(h.新值))}${h.已撤销?'（已撤销）':''}</article>`).join('')||'<p class="muted">暂无升级后的逐商品编辑记录；旧保存日志保留在批次备份中。</p>'}</div>`;
        panel.querySelector('.close-panel').onclick=()=>{S.detailOpen=false;panel.close()};panel.oncancel=()=>{S.detailOpen=false};
        panel.querySelectorAll('.jump').forEach(b=>b.onclick=()=>{S.focus=b.dataset.id;S.detailOpen=false;panel.close();S.render();S.dom.get(S.focus)?.scrollIntoView({block:'center',behavior:'smooth'})});
        const more=panel.querySelector('.detail-peers');
        for(const p of detail.peers||[]){const b=document.createElement('button');b.className='peer';b.textContent=`${p.kind} ↔ ${p.name} / ${p.barcode} / 对方差异${p.diff>0?'+':''}${p.diff} / ${p.evidence} ›`;b.onclick=()=>S.openDetail(detail.a.id,p.id);more.appendChild(b)}
        if(detail.has_more){const b=document.createElement('button');b.textContent='再展开50条候选';b.onclick=()=>S.enqueue('more_peers');more.appendChild(b)}
      }else if(S.detailOpen){if(!panel.open)panel.showModal();panel.innerHTML='<p>正在载入对应商品…</p>'}else if(panel.open)panel.close();
      const ids=visible.map(r=>r.id);const viewKey=ids.join('|')+'@'+d.revision;
      if(viewKey!==S.viewKey&&ids.some(id=>!d.enriched.includes(id))){S.viewKey=viewKey;S.enqueue('view',{ids})}
    };
  }
  S.comp=component;S.data=data;S.rows=new Map(data.rows.map(r=>[r.id,r]));
  const q=s=>root.querySelector(s);
  for(const [selector,values,all] of [['.category',[...new Set(data.rows.map(r=>r.category))].sort(),'全部品类'],['.supplier',[...new Set(data.rows.map(r=>r.supplier))].sort(),'全部供应商']]){
    const select=q(selector),value=selector==='.category'?S.category:S.supplier;
    select.innerHTML=`<option value="">${all}</option>`+values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');select.value=value;
  }
  if(data.ack&&data.ack.id!==S.seenAck){
    S.seenAck=data.ack.id;
    if(S.inflight?.request_id===data.ack.id){const e=S.inflight;
      if(data.ack.ok&&e.kind==='edit'){
        if(S.drafts[e.id]?.[e.field]?.value===e.value){delete S.drafts[e.id][e.field];if(!Object.keys(S.drafts[e.id]).length)delete S.drafts[e.id]}
        else if(S.drafts[e.id]?.[e.field])S.drafts[e.id][e.field].base=e.value;
        for(const queued of S.queue)if(queued.kind==='edit'&&queued.id===e.id&&queued.field===e.field)queued.base=e.value;
      }
      if(data.ack.ok&&e.kind==='meta'){
        const draft=S.metaDrafts[e.metaKey];if(draft?.value===e.value)delete S.metaDrafts[e.metaKey];else if(draft)draft.base=e.value;
        for(const queued of S.queue)if(queued.kind==='meta'&&queued.metaKey===e.metaKey)queued.base=e.value;
      }
      if(!data.ack.ok){S.queue=[];S.restore=true}
      if(data.ack.ok&&e.kind==='bulk')q('.bulk').classList.add('hidden');
      if(data.ack.ok&&e.kind==='refresh'){
        for(const [id,fields] of Object.entries(S.drafts))for(const [field,draft] of Object.entries(fields)){
          const row=S.rows.get(id);if(row)draft.base=field==='复盘实数'?row.recount:row.note;
        }
        for(const [key,draft] of Object.entries(S.metaDrafts))draft.base=S.metaValue(key);
        S.restore=Object.keys(S.drafts).length>0||Object.keys(S.metaDrafts).length>0;
      }
      S.inflight=null;S.remember();
      if(!Object.keys(S.drafts).length&&!Object.keys(S.metaDrafts).length)S.restore=false;
    }
  }
  S.render();S.pump();
}
