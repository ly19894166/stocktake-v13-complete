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
    S=root.__inventory={query:local.query||'',filters:local.filters||[],category:local.category||'',supplier:local.supplier||'',sort:local.sort||'amount',page:0,size:20,drafts:local.drafts||{},queue:[],inflight:null,rows:new Map(),dom:new Map(),focus:null,seenAck:null,viewKey:'',restore:!!Object.keys(local.drafts||{}).length};
    root.innerHTML=`<div class="metrics" data-testid="metrics"></div><div class="audit"></div>
      <div class="toolbar main-toolbar"><input class="search" aria-label="搜索商品名、编码、完整条码或尾号" placeholder="商品名称 / 条码尾号4–8位 / 商品编码"><select class="category" aria-label="品类筛选"></select><button class="undo">撤销</button><button class="bulk-toggle">批量粘贴</button><details class="more-filters"><summary>更多筛选</summary><div class="filter-body"><select class="supplier" aria-label="供应商筛选"></select><select class="sort" aria-label="建议排序"><option value="amount">差异金额优先</option><option value="quantity">差异数量优先</option><option value="mix">同类串码优先</option><option value="category">按品类找货</option><option value="score">综合建议分</option></select><select class="size" aria-label="每页显示"><option value="20">每页20条</option><option value="50">每页50条</option><option value="100">每页100条</option></select><button class="clear">清除筛选</button><button class="refresh">刷新数据</button></div></details></div>
      <details class="quick-filters"><summary>快捷筛选 · 按需要展开</summary><div class="chips"></div></details>
      <select class="locate hidden" aria-label="条码尾号匹配结果"></select><div class="message"></div>
      <div class="bulk hidden"><strong>批量粘贴复盘数</strong><p class="muted">每行：完整商品条码 Tab 复盘实数 Tab 人工备注（备注可省略）。全部校验后一次保存。</p><textarea aria-label="批量粘贴复盘数据" placeholder="690…　12　现场找到库存"></textarea><div class="toolbar"><button class="primary bulk-submit">保存粘贴行</button></div></div>
      <div class="panel hidden" aria-live="polite"></div><div class="guide"><span class="result-count"></span><span class="saved" data-testid="save-status"></span></div>
      <div class="table-wrap"><table aria-label="01现场复盘表"><thead><tr><th>序号</th><th>商品名称 / 系统与初盘</th><th>最新差异 / 成本</th><th>复盘实数</th><th>人工备注</th><th>查找线索</th></tr></thead><tbody></tbody></table></div>
      <div class="pagination"><button class="prev">上一页</button><span class="page-info"></span><button class="next">下一页</button></div>`;
    const q=s=>root.querySelector(s);
    const remember=()=>{try{localStorage.setItem('stocktake:'+S.data.batch,JSON.stringify({query:S.query,filters:S.filters,category:S.category,supplier:S.supplier,sort:S.sort,drafts:S.drafts}))}catch{}};
    S.remember=remember;
    S.enqueue=(kind,extra={})=>{S.queue.push({kind,...extra,request_id:crypto.randomUUID()});S.pump()};
    S.pump=()=>{if(S.inflight||!S.queue.length)return;const event=S.queue.shift();S.inflight=event;S.comp.setTriggerValue('action',{...event,revision:S.data.revision});q('.saved').textContent='保存 / 载入中…'};
    S.commit=(id,field)=>{const draft=S.drafts[id]?.[field];if(!draft)return;const exists=[S.inflight,...S.queue].some(e=>e?.kind==='edit'&&e.id===id&&e.field===field&&e.value===draft.value);if(!exists)S.enqueue('edit',{id,field,value:draft.value,base:draft.base})};
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
    q('.locate').onchange=e=>{if(!e.target.value)return;S.focus=e.target.value;S.enqueue('detail',{a:e.target.value,b:null});S.render()};
    S.openDetail=(a,b)=>{S.focus=b||a;S.enqueue('detail',{a,b});S.render()};
    S.render=()=>{
      const d=S.data,stats=d.stats;
      const metrics=[['盘亏金额',stats.loss],['盘盈金额',stats.gain],['净差异',stats.net],['待填复盘',stats.pending]];
      q('.metrics').innerHTML=metrics.map(([label,value])=>`<div class="metric"><small>${esc(label)}</small><strong class="${label==='待填复盘'?'':cls(value)}">${esc(fmt(value,label==='待填复盘'?0:2))}</strong></div>`).join('');
      const status=stats.standard==='ok'?'ok':stats.standard==='bad'?'bad':'pending';
      const title=stats.standard==='ok'?'2‰当前测算达标':stats.standard==='bad'?'2‰当前测算超标':'2‰待填含税成本';
      q('.audit').innerHTML=`<span>销售额 <b>¥${esc(fmt(stats.sales_amount,2))}</b></span><span>含税成本 <b>¥${esc(fmt(stats.sales_cost,2))}</b></span><span>损耗率 <b>${stats.rate===null?'待计算':esc(fmt(stats.rate,2))+'‰'}</b></span><span class="status ${status}">${title}</span><span class="muted">${stats.allowed===null?'尚未计算2‰额度':'2‰额度 ¥'+esc(fmt(stats.allowed,2))+' · '+(stats.remaining>=0?'剩余':'超额')+' ¥'+esc(fmt(Math.abs(stats.remaining),2))}</span><span class="muted">${stats.pending?'尚有 '+stats.pending+' 条待填复盘':esc(d.audit)}</span>`;
      const message=q('.message');message.innerHTML=d.error?`<div class="error">${esc(d.error)}</div>`:S.restore?'<div class="notice">已保留上次未确认草稿。检查黄色输入框，按Enter或离开单元格保存；不会把空白当作0。</div>':'';
      q('.chips').innerHTML=d.filters.map(f=>`<button class="chip ${S.filters.includes(f)?'active':''}" data-filter="${esc(f)}">${esc(f)}</button>`).join('');
      q('.chips').querySelectorAll('button').forEach(b=>b.onclick=()=>{S.filters=S.filters.includes(b.dataset.filter)?S.filters.filter(f=>f!==b.dataset.filter):[...S.filters,b.dataset.filter];S.page=0;remember();S.render()});
      let rows=[...S.rows.values()].filter(r=>(!S.query||[r.name,r.barcode,r.code].some(v=>String(v).toLowerCase().includes(S.query.toLowerCase())))&&(!S.category||r.category===S.category)&&(!S.supplier||r.supplier===S.supplier)&&S.filters.every(f=>r.flags.includes(f)));
      rows.sort((a,b)=>S.sort==='amount'?Math.abs(b.amount||0)-Math.abs(a.amount||0)||b.score-a.score:S.sort==='quantity'?Math.abs(b.diff||0)-Math.abs(a.diff||0):S.sort==='mix'?b.mix_count-a.mix_count||Math.abs(b.amount||0)-Math.abs(a.amount||0):S.sort==='score'?b.score-a.score:a.category.localeCompare(b.category,'zh-CN')||a.sequence-b.sequence);
      const found=rows.length,pages=Math.max(1,Math.ceil(found/S.size));S.page=Math.min(S.page,pages-1);let visible=rows.slice(S.page*S.size,(S.page+1)*S.size);
      if(S.focus&&S.rows.has(S.focus)&&!visible.some(r=>r.id===S.focus))visible=[S.rows.get(S.focus),...visible];
      S.visible=visible;
      const locate=q('.locate');if(/^\d{4,8}$/.test(S.query)&&rows.length>1){locate.classList.remove('hidden');locate.innerHTML='<option value="">尾号对应多个商品，请选择完整条码定位</option>'+rows.map(r=>`<option value="${esc(r.id)}">${esc(r.name+' / '+r.barcode)}</option>`).join('')}else locate.classList.add('hidden');
      q('.result-count').textContent=`当前 ${found} / ${S.rows.size} 条 · 组合筛选须同时满足 · 点击候选可并排查对方`;
      q('.page-info').textContent=`${S.page+1} / ${pages} 页`;q('.prev').disabled=S.page===0;q('.next').disabled=S.page>=pages-1;
      q('.saved').textContent=S.inflight?'保存 / 载入中…':`已保存 · ${d.saved_at||d.imported_at} · 版本 ${d.revision}`;
      const tbody=q('tbody');const keep=new Set(visible.map(r=>r.id));
      for(const tr of [...tbody.children])if(!keep.has(tr.dataset.id))tr.remove();
      for(let i=0;i<visible.length;i++){
        const r=visible[i];let tr=S.dom.get(r.id);
        if(!tr){tr=document.createElement('tr');tr.dataset.id=r.id;tr.innerHTML='<td class="seq"></td><td class="product"></td><td class="difference num"></td><td><input class="edit-count" inputmode="decimal"></td><td><textarea class="edit-note" rows="1"></textarea></td><td class="hints"></td>';S.dom.set(r.id,tr);
          for(const [field,selector] of [['复盘实数','.edit-count'],['备注','.edit-note']]){
            const input=tr.querySelector(selector);input.dataset.field=field;input.setAttribute('aria-label',`${field} ${r.barcode}`);
            input.oninput=()=>{const prior=S.drafts[r.id]?.[field];S.drafts[r.id]??={};S.drafts[r.id][field]={value:input.value,base:prior?prior.base:(field==='复盘实数'?S.rows.get(r.id).recount:S.rows.get(r.id).note)};q('.saved').textContent='有未确认草稿 · Enter或离开单元格保存';remember()};
            input.onblur=()=>S.commit(r.id,field);
            input.onkeydown=e=>{if(e.key==='Enter'&&(field==='复盘实数'||!e.shiftKey)){e.preventDefault();S.commit(r.id,field);const idx=S.visible.findIndex(x=>x.id===r.id);const next=S.dom.get(S.visible[idx+1]?.id)?.querySelector(selector);if(next)next.focus()}};
          }
        }
        tr.className=r.id===S.focus?'selected':'';
        tr.querySelector('.seq').textContent=r.sequence;
        tr.querySelector('.product').innerHTML=`<span class="name">${esc(r.name)}</span><span class="codes">${esc(r.barcode)}</span><span class="minor">系统 ${esc(fmt(r.system))} · 初盘 ${esc(fmt(r.initial))}</span><button class="row-link" title="查看商品编码、供应商、对照和轨迹">详细信息 ›</button>`;
        tr.querySelector('.row-link').onclick=()=>S.openDetail(r.id,null);
        tr.querySelector('.difference').innerHTML=`<strong class="${cls(r.diff)}">${r.diff>0?'+':''}${esc(fmt(r.diff))}</strong><span class="minor ${cls(r.amount)}">¥ ${esc(fmt(r.amount,2))}</span>`;
        for(const [field,selector,value] of [['复盘实数','.edit-count',r.recount],['备注','.edit-note',r.note]]){const input=tr.querySelector(selector);const draft=S.drafts[r.id]?.[field];const next=draft?draft.value:(value??'');if(parentElement.activeElement!==input&&input.value!==String(next))input.value=String(next)}
        const hints=tr.querySelector('.hints');
        const counts=[];
        if(r.mix_count)counts.push('疑似串码 '+r.mix_count+'项');
        if(r.swap_count)counts.push('A换B '+r.swap_count+'项');
        const riskCount=(r.unit_hints||[]).length+(r.risk_hints||[]).length+(r.cross||[]).length;
        if(riskCount)counts.push('其他线索 '+riskCount+'项');
        hints.innerHTML=counts.length?`<button class="peer" title="点击查看对应商品及依据">${esc(counts.join(' · '))} ›</button>`:'<span class="minor">—</span>';
        const summaryBtn=hints.querySelector('button');if(summaryBtn)summaryBtn.onclick=()=>S.openDetail(r.id,null);
        if(tbody.children[i]!==tr)tbody.insertBefore(tr,tbody.children[i]||null);
      }
      const panel=q('.panel');const detail=d.detail;
      if(detail){
        panel.classList.remove('hidden');
        const card=r=>`<div class="pair-card"><b>${esc(r.name)}</b><span class="codes">${esc(r.barcode)} / 编码 ${esc(r.code)}</span><dl>${[['系统数',r.system],['初盘数',r.initial],['复盘实数',r.recount===null?'空白':r.recount],['当前总数',r.total],['最新差异',r.diff],['成本',r.cost],['零售价',r.retail===null?'缺售价':r.retail],['部 / 大 / 中类',[r.department,r.category,r.middle].join(' / ')],['供货商',r.supplier],['人工原因',r.note||'未填']].map(([a,b])=>`<dt>${esc(a)}</dt><dd>${esc(b??'缺失')}</dd>`).join('')}</dl><button class="jump" data-id="${esc(r.id)}">定位此商品</button></div>`;
        panel.innerHTML=`<div class="panel-title"><span>商品对照 / 输入轨迹 · ${detail.pair?esc(detail.pair.kind+' · '+detail.pair.confidence):'当前这对商品无有效候选（归零会自动撤销）'}</span><button class="close-panel">收起</button></div><div class="pair-cards">${card(detail.a)}${detail.b?card(detail.b):''}</div>${detail.pair?`<p>${esc(detail.pair.evidence)} · 可解释数量 ${esc(detail.pair.overlap)} · 金额 ¥${esc(detail.pair.amount_overlap)}；疑似待核，不自动抵销。</p>`:''}<div class="detail-peers"></div><div class="history">${(detail.history||[]).map(h=>`<article>${esc(h.北京时间)} · ${esc(h.操作人)} · ${esc(h.修改来源)}<br>${esc(JSON.stringify(h.旧值))} → ${esc(JSON.stringify(h.新值))}${h.已撤销?'（已撤销）':''}</article>`).join('')||'<p class="muted">暂无升级后的逐商品编辑记录；旧保存日志保留在批次备份中。</p>'}</div>`;
        panel.querySelector('.close-panel').onclick=()=>{panel.classList.add('hidden');S.data.detail=null};
        panel.querySelectorAll('.jump').forEach(b=>b.onclick=()=>{S.focus=b.dataset.id;S.render();S.dom.get(S.focus)?.scrollIntoView({block:'center',behavior:'smooth'})});
        const more=panel.querySelector('.detail-peers');
        for(const p of detail.peers||[]){const b=document.createElement('button');b.className='peer';b.textContent=`${p.kind} ↔ ${p.name} / ${p.barcode} / 差异${p.diff>0?'+':''}${p.diff} / ${p.confidence}`;b.onclick=()=>S.openDetail(detail.a.id,p.id);more.appendChild(b)}
        if(detail.has_more){const b=document.createElement('button');b.textContent='再展开50条候选';b.onclick=()=>S.enqueue('more_peers');more.appendChild(b)}
      }else panel.classList.add('hidden');
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
      if(!data.ack.ok){S.queue=[];S.restore=true}
      if(data.ack.ok&&e.kind==='bulk')q('.bulk').classList.add('hidden');
      if(data.ack.ok&&e.kind==='refresh'){
        for(const [id,fields] of Object.entries(S.drafts))for(const [field,draft] of Object.entries(fields)){
          const row=S.rows.get(id);if(row)draft.base=field==='复盘实数'?row.recount:row.note;
        }
        S.restore=Object.keys(S.drafts).length>0;
      }
      S.inflight=null;S.remember();
      if(!Object.keys(S.drafts).length)S.restore=false;
    }
  }
  S.render();S.pump();
}
