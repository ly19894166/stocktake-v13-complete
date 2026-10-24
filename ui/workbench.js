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
    S=root.__inventory={query:local.query||'',filters:local.filters||[],category:local.category||'',supplier:local.supplier||'',sort:local.flowVersion===3?(local.sort||'pair'):'pair',order:[],orderKey:'',loaded:200,editGeneration:0,copyIntent:null,drafts:local.drafts||{},queue:[],inflight:null,rows:new Map(),dom:new Map(),focus:null,seenAck:null,viewKey:'',rowSignatures:new Map(),restore:!!Object.keys(local.drafts||{}).length,metaDrafts:local.metaDrafts||{},timers:{},reportOpen:false,detailOpen:false};
    root.innerHTML=`<div class="operating-panel">
      <div class="operating-inputs"><label>实际销售金额（元）<input data-meta="sales_amount" inputmode="decimal" aria-label="实际销售金额（元）" placeholder="待填写"></label><label>同期含税销售成本（元）<input data-meta="sales_cost" inputmode="decimal" aria-label="同期含税销售成本（元）" placeholder="待填写"></label><div class="calculation-status"></div><button class="report-open primary">生成盘点汇报</button></div>
      <div class="metrics" data-testid="metrics"></div><div class="audit muted">当前测算，仅供复盘；正式导出仍须在02完整检查。</div></div>
      <div class="toolbar primary-tools"><input class="search" aria-label="搜索商品名、编码、完整条码或尾号" placeholder="商品名称 / 编码 / 完整条码 / 尾号4–8位"><select class="category" aria-label="品类筛选"></select><select class="view" aria-label="找货查看方式"><option value="pair">疑似串码联排</option><option value="amount">按差异金额找货</option></select><button class="regroup" title="按最新线索重新联排">重新联排</button><button class="undo">撤销上次输入</button><button class="bulk-toggle">批量粘贴</button><button class="more-toggle" aria-expanded="false">更多筛选</button></div>
      <div class="more-filters hidden"><div class="toolbar"><select class="supplier" aria-label="供应商筛选"></select><select class="sort" aria-label="建议排序"><option value="pair">疑似串码联排</option><option value="amount">金额优先</option><option value="quantity">数量优先</option><option value="mix">同类串码优先</option><option value="category">按品类现场找货</option><option value="score">综合建议分</option></select><button class="refresh">刷新数据</button><button class="clear">清除筛选</button></div><div class="chips"></div><span class="muted">组合筛选同时满足；建议排序只供找差异，不改变审核标准。</span></div>
      <select class="locate hidden" aria-label="条码尾号匹配结果"></select><div class="message"></div>
      <div class="bulk hidden"><strong>批量粘贴复盘数</strong><p class="muted">每行：完整条码 Tab 复盘实数 Tab 人工备注 Tab 单位说明（后两项可省略）。全部校验通过后一次保存。</p><textarea aria-label="批量粘贴复盘数据"></textarea><button class="primary bulk-submit">校验并保存全部粘贴行</button></div>
      <div class="guide"><span class="result-count"></span><span class="saved" data-testid="save-status"></span></div>
      <div class="table-wrap"><table aria-label="01现场复盘表"><colgroup><col style="width:4%"><col style="width:27%"><col style="width:22%"><col style="width:11%"><col style="width:17%"><col style="width:19%"></colgroup><thead><tr><th>序号</th><th>商品 / 条码 / 系统与初盘</th><th>初盘 → 最新差异 / 复盘变化</th><th>复盘实数</th><th>人工备注</th><th>智能找差异</th></tr></thead><tbody></tbody></table></div>
      <div class="load-sentinel" aria-label="连续浏览加载位置"></div><div class="scroll-status muted"></div>
      <dialog class="panel" aria-label="商品详情与对应候选"></dialog>
      <dialog class="report-dialog" aria-label="季度盘点汇报"><div class="panel-title"><strong>季度盘点汇报</strong><button class="report-close">关闭</button></div><div class="report-fields"></div><p class="report-warnings muted"></p><label class="report-label">最终文稿（可直接编辑，自动保存）<textarea class="report-text" aria-label="最终盘点汇报文稿"></textarea></label><div class="toolbar"><button class="report-copy primary">一键复制文稿</button><button class="report-reset">按最新数据重新生成</button><button class="report-old hidden">查看上次人工稿</button><span class="copy-status" aria-live="polite"></span></div></dialog>`;
    const q=s=>root.querySelector(s);
    const remember=()=>{try{localStorage.setItem('stocktake:'+S.data.batch,JSON.stringify({query:S.query,filters:S.filters,category:S.category,supplier:S.supplier,sort:S.sort,flowVersion:3,drafts:S.drafts,metaDrafts:S.metaDrafts}))}catch{}};
    S.remember=remember;
    S.enqueue=(kind,extra={})=>{const event={kind,...extra,request_id:crypto.randomUUID()};S.queue.push(event);S.pump();return event.request_id};
    S.pump=()=>{if(S.inflight||!S.queue.length)return;let event=S.queue.shift();if(event.kind==='edit'){
      const entries=[event];while(S.queue[0]?.kind==='edit'&&entries.length<100)entries.push(S.queue.shift());
      const latest=new Map();for(const edit of entries){const key=edit.id+'|'+edit.field,prior=latest.get(key);latest.set(key,prior?{...edit,base:prior.base}:edit)}
      if(latest.size>1)event={kind:'edits',entries:[...latest.values()],request_id:crypto.randomUUID()};else event=[...latest.values()][0];
    }S.inflight=event;S.comp.setTriggerValue('action',{...event,revision:S.data.revision});q('.saved').textContent='保存 / 载入中…'};
    S.commit=(id,field)=>{const draft=S.drafts[id]?.[field];if(!draft)return;const pending=[...S.queue,...(S.inflight?.kind==='edits'?S.inflight.entries:[S.inflight])];const exists=pending.some(e=>e?.kind==='edit'&&e.id===id&&e.field===field&&e.value===draft.value);if(!exists)S.enqueue('edit',{id,field,value:draft.value,base:draft.base})};
    S.metaValue=key=>key.startsWith('report.')?S.data.report.config[key.slice(7)]:S.data.finance[key];
    S.commitMeta=key=>{const draft=S.metaDrafts[key];if(!draft)return;const queued=[S.inflight,...S.queue].some(e=>e?.kind==='meta'&&e.metaKey===key&&e.value===draft.value);if(!queued)S.enqueue('meta',{scope:key.startsWith('report.')?'report':'finance',field:key.split('.').at(-1),metaKey:key,value:draft.value,base:draft.base,signature:draft.signature})};
    S.bindMeta=(input,key)=>{input.oninput=()=>{S.editGeneration++;const prior=S.metaDrafts[key];S.metaDrafts[key]={value:input.type==='checkbox'?input.checked:input.value,base:prior?prior.base:S.metaValue(key),signature:S.data.report.signature};S.remember();q('.saved').textContent='有未保存输入…';clearTimeout(S.timers[key]);if(input.type==='checkbox')S.commitMeta(key);else S.timers[key]=setTimeout(()=>S.commitMeta(key),650)};input.onblur=()=>S.commitMeta(key);input.onchange=()=>S.commitMeta(key)};
    for(const input of root.querySelectorAll('[data-meta]'))S.bindMeta(input,input.dataset.meta);
    const fields=[['store','门店（仅用于汇报）','text'],['report_date','汇报日期','date'],['sales_start','销售统计起日','date'],['sales_end','销售统计止日','date'],['quarter','季度','text'],['reason','主要原因（由店长确认）','textarea'],['reason_confirmed','我已核对并确认主要原因','checkbox'],['fresh_enabled','附加独立鲜食盘点数据','checkbox'],['fresh_start','鲜食统计起日','date'],['fresh_end','鲜食统计止日','date'],['fresh_sales','鲜食销售金额（元）','text'],['fresh_cost','鲜食含税成本（元）','text'],['fresh_gain','鲜食盘盈（正数或0）','text'],['fresh_loss','鲜食盘亏（负数或0）','text']];
    q('.report-fields').innerHTML=fields.map(([key,label,type])=>`<label class="${key.startsWith('fresh_')&&key!=='fresh_enabled'?'fresh-field ':''}${type==='textarea'?'wide':''}">${esc(label)}${type==='textarea'?`<textarea data-report="${key}" aria-label="${esc(label)}"></textarea>`:`<input type="${type}" data-report="${key}" aria-label="${esc(label)}">`}</label>`).join('');
    for(const input of q('.report-fields').querySelectorAll('[data-report]'))S.bindMeta(input,'report.'+input.dataset.report);
    S.bindMeta(q('.report-text'),'report.draft');
    S.flush=()=>{for(const [id,fields] of Object.entries(S.drafts))for(const field of Object.keys(fields))S.commit(id,field);for(const key of Object.keys(S.metaDrafts))S.commitMeta(key)};
    q('.report-open').onclick=()=>{S.reportOpen=true;S.requestReport('open')};
    q('.report-close').onclick=()=>{S.flush();S.reportOpen=false;if(S.copyIntent)S.abortCopy('已关闭汇报窗口，未复制');q('.report-dialog').close()};
    q('.report-dialog').oncancel=()=>{S.flush();S.reportOpen=false;if(S.copyIntent)S.abortCopy('已关闭汇报窗口，未复制')};
    q('.report-reset').onclick=()=>S.requestReport('reset');
    q('.report-old').onclick=()=>{q('.report-text').value=S.data.report.stale_draft;q('.copy-status').textContent='这是旧人工稿，仅供对照；数字可能已过期，请核对后编辑或重新生成'};
    S.abortCopy=message=>{S.copyIntent=null;q('.report-copy').disabled=false;q('.report-text').disabled=false;S.renderReport();q('.copy-status').textContent=message};
    S.requestReport=purpose=>{
      if(S.copyIntent?.purpose==='copy')return;
      S.queue=S.queue.filter(e=>e.kind!=='copy_snapshot'||e.purpose==='reset');
      S.flush();S.copyIntent={purpose,generation:S.editGeneration,id:crypto.randomUUID()};
      q('.report-copy').disabled=purpose==='copy';q('.copy-status').textContent='正在保存并更新金额，尚未生成或复制最新文稿';
      S.queue.push({kind:'copy_snapshot',purpose,request_id:S.copyIntent.id});S.pump();S.renderReport();
    };
    q('.report-copy').onclick=()=>S.requestReport('copy');
    S.finishCopy=async(snapshot,intent)=>{
      if(S.copyIntent!==intent)return;
      if(!intent||!S.reportOpen||intent.generation!==S.editGeneration||Object.keys(S.drafts).length||Object.keys(S.metaDrafts).length||S.queue.some(e=>e.kind!=='view')||!snapshot||snapshot.id!==intent.id||snapshot.revision!==S.data.revision||snapshot.signature!==S.data.report.signature){S.abortCopy('数据仍在变化，未生成或复制最新稿；请等待保存后重试');return}
      const editor=q('.report-text');editor.disabled=false;editor.value=snapshot.text;
      if(intent.purpose!=='copy'){S.copyIntent=null;q('.report-copy').disabled=false;q('.copy-status').textContent='已按最新已保存数据生成文稿，尚未复制';return}
      try{await navigator.clipboard.writeText(snapshot.text)}catch{
        editor.focus();editor.select();if(!document.execCommand('copy')){S.abortCopy('最新稿已核对；请再次点击复制，或按Ctrl+C复制选中文字');return}
      }
      if(intent.generation!==S.editGeneration){S.abortCopy('复制期间又有新输入，请保存后重新复制');return}
      S.copyIntent=null;q('.report-copy').disabled=false;q('.copy-status').textContent=snapshot.edited?'已复制当前已保存的人工编辑稿，请核对内容':'已复制最新已保存的计算文稿';
    };
    S.renderReport=()=>{const dialog=q('.report-dialog');if(!S.reportOpen)return;if(!dialog.open)dialog.showModal();const report=S.data.report;
      for(const input of dialog.querySelectorAll('[data-report]')){const key=input.dataset.report,value=S.metaDrafts['report.'+key]?.value??report.config[key]??'';if(input.type==='checkbox')input.checked=!!value;else if(parentElement.activeElement!==input&&input.value!==String(value))input.value=String(value)}
      const fresh=!!(S.metaDrafts['report.fresh_enabled']?.value??report.config.fresh_enabled);dialog.querySelectorAll('.fresh-field').forEach(el=>el.classList.toggle('hidden',!fresh));
      const editor=q('.report-text'),draft=S.metaDrafts['report.draft'];editor.disabled=!!S.copyIntent;
      if(S.copyIntent){editor.value='正在保存并更新金额，请稍候…'}else if(parentElement.activeElement!==editor){const next=draft?draft.value:report.text;if(editor.value!==next)editor.value=next}
      q('.report-warnings').textContent=[...report.warnings,report.stale_draft?'数据已变化，当前显示实时新稿；旧人工稿可对照查看':'',S.inflight||S.queue.length?'正在保存输入，请等待顶部显示已保存再关闭程序':''].filter(Boolean).join('；');
      q('.report-old').classList.toggle('hidden',!report.stale_draft);
    };
    q('.more-toggle').onclick=()=>{const hidden=q('.more-filters').classList.toggle('hidden');q('.more-toggle').setAttribute('aria-expanded',String(!hidden))};
    q('.search').value=S.query;
    q('.search').oninput=e=>{S.query=e.target.value;S.focus=null;remember();S.render()};
    q('.category').onchange=e=>{S.category=e.target.value;S.focus=null;remember();S.render()};
    q('.supplier').onchange=e=>{S.supplier=e.target.value;S.focus=null;remember();S.render()};
    q('.sort').value=S.sort;q('.sort').onchange=e=>{S.sort=e.target.value;S.focus=null;remember();S.render()};
    q('.clear').onclick=()=>{S.query='';S.filters=[];S.category='';S.supplier='';S.focus=null;S.focus=null;q('.search').value='';q('.category').value='';q('.supplier').value='';remember();S.render()};
    q('.undo').onclick=()=>S.enqueue('undo');q('.refresh').onclick=()=>S.enqueue('refresh');
    q('.bulk-toggle').onclick=()=>q('.bulk').classList.toggle('hidden');
    q('.bulk-submit').onclick=()=>S.enqueue('bulk',{text:q('.bulk textarea').value});
    q('.locate').onchange=e=>{if(e.target.value)S.openDetail(e.target.value,null)};
    S.openDetail=(a,b)=>{S.detailOpen=true;S.requestedDetail={a,b:b||null};S.enqueue('detail',{a,b});S.render()};
    S.locateTo=(id,from=null)=>{S.focus=id;S.locateFrom=from;S.render();S.dom.get(id)?.scrollIntoView({block:'center',behavior:'smooth'})};
    q('.view').value=S.sort==='pair'?'pair':'amount';
    q('.view').onchange=e=>{S.sort=e.target.value;q('.sort').value=S.sort;S.orderKey='';S.focus=null;remember();S.render()};
    q('.regroup').onclick=()=>{S.orderKey='';S.render()};
    S.scrollParent=()=>{for(let el=root.getRootNode().host;el;el=el.parentElement)if(/auto|scroll/.test(getComputedStyle(el).overflowY)&&el.scrollHeight>el.clientHeight+10)return el;return document.scrollingElement};
    S.requestVisible=()=>{if(S.inflight||S.queue.some(e=>e.kind==='view'))return;const ids=S.visible.filter(r=>{const el=S.dom.get(r.id);if(!el)return false;const box=el.getBoundingClientRect();return box.bottom>-500&&box.top<innerHeight+800}).map(r=>r.id).filter(id=>!S.data.enriched.includes(id)).slice(0,150);if(ids.length)S.enqueue('view',{ids})};
    S.onScroll=()=>{if(!root.isConnected)return;clearTimeout(S.scrollTimer);S.scrollTimer=setTimeout(S.requestVisible,160)};
    S.observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)&&S.loaded<S.filteredCount){S.loaded+=200;S.render()}},{rootMargin:'900px'});
    S.render=()=>{
      const d=S.data,stats=d.stats;const tbody=q('tbody'),scroller=S.scrollParent();const active=root.getRootNode().activeElement;const anchor=[...tbody.children].find(el=>el.getBoundingClientRect().bottom>90);const anchorTop=anchor?.getBoundingClientRect().top;const priorScroll=scroller.scrollTop;
      q('.regroup').textContent=S.sort==='pair'?'重新联排':'刷新排序';q('.regroup').title='按最新数据更新排列；保存时保留行位置，避免打断输入';
      const p=d.panel;
      for(const input of root.querySelectorAll('[data-meta]')){const value=S.metaDrafts[input.dataset.meta]?.value??d.finance[input.dataset.meta]??'';if(parentElement.activeElement!==input&&input.value!==String(value))input.value=String(value)}
      q('.calculation-status').className='calculation-status '+(p.status==='当前测算达标'?'green':p.status==='当前测算超标'?'red':'zero');q('.calculation-status').textContent=p.status;
      const metrics=[['盘盈（元）',p.gain,'green'],['盘亏（元）',p.loss,'red'],['净差异（元）',p.net,cls(Number(p.net))],['净差异率',p.rate===null?'待计算':p.rate+'‰',p.rate===null?'zero':''],['2‰允许损耗（元）',p.allowance,p.allowance===null?'zero':''],[p.over_limit?'超标金额（元）':'剩余额度（元）',p.remaining===null?null:fmt(Math.abs(Number(p.remaining)),2),p.remaining===null?'zero':p.over_limit?'red':'green'],['已填 / 剩余',p.done+' / '+p.remaining_rows,'']];
      q('.metrics').innerHTML=metrics.map(([label,value,color])=>`<div class="metric"><small>${esc(label)}</small><strong class="${color}">${esc(value??'待计算')}</strong></div>`).join('');
      q('.audit').textContent=p.note;
      S.renderReport();
      const message=q('.message');message.innerHTML=d.error?`<div class="error">${esc(d.error)}</div>`:S.restore?'<div class="notice">已保留上次未确认草稿。检查黄色输入框，按Enter或离开单元格保存；不会把空白当作0。</div>':'';
      q('.chips').innerHTML=d.filters.map(f=>`<button class="chip ${S.filters.includes(f)?'active':''}" data-filter="${esc(f)}">${esc(f)}</button>`).join('');
      q('.chips').querySelectorAll('button').forEach(b=>b.onclick=()=>{S.filters=S.filters.includes(b.dataset.filter)?S.filters.filter(f=>f!==b.dataset.filter):[...S.filters,b.dataset.filter];S.focus=null;remember();S.render()});
      let rows=[...S.rows.values()].filter(r=>(!S.query||[r.name,r.barcode,r.code].some(v=>String(v).toLowerCase().includes(S.query.toLowerCase())))&&(!S.category||r.category===S.category)&&(!S.supplier||r.supplier===S.supplier)&&S.filters.every(f=>r.flags.includes(f)));
      rows.sort((a,b)=>S.sort==='amount'?Math.abs(b.amount||0)-Math.abs(a.amount||0)||b.score-a.score:S.sort==='quantity'?Math.abs(b.diff||0)-Math.abs(a.diff||0):S.sort==='mix'?b.mix_count-a.mix_count||Math.abs(b.amount||0)-Math.abs(a.amount||0):S.sort==='score'?b.score-a.score:a.category.localeCompare(b.category,'zh-CN')||a.sequence-b.sequence);
      const found=rows.length,key=JSON.stringify([S.query,S.filters,S.category,S.supplier,S.sort]);
      const matches=new Set(rows.map(r=>r.id));
      const reset=key!==S.orderKey;
      if(reset){S.orderKey=key;S.order=S.sort==='pair'?d.pair_order.filter(id=>matches.has(id)):rows.map(r=>r.id);S.loaded=rows.length<=2000?rows.length:200}
      else{const old=new Set(S.order);S.order=S.order.filter(id=>matches.has(id));S.order.push(...rows.filter(r=>!old.has(r.id)).map(r=>r.id))}
      let ids=[...S.order];
      if(S.focus&&S.rows.has(S.focus)&&!ids.includes(S.focus)){const at=S.locateFrom?ids.indexOf(S.locateFrom):-1;ids.splice(at>=0?at+1:0,0,S.focus)}
      if(S.focus){const at=ids.indexOf(S.focus);if(at>=S.loaded)S.loaded=at+1}
      S.filteredCount=ids.length;const visible=ids.slice(0,S.loaded).map(id=>S.rows.get(id));S.visible=visible;
      const positions=new Map(visible.map((r,i)=>[r.id,i]));
      const locate=q('.locate');if(/^\d{4,8}$/.test(S.query)&&rows.length>1){locate.classList.remove('hidden');locate.innerHTML='<option value="">尾号对应多个商品，请选择完整条码定位</option>'+rows.map(r=>`<option value="${esc(r.id)}">${esc(r.name+' / '+r.barcode)}</option>`).join('')}else locate.classList.add('hidden');
      q('.result-count').textContent=`当前 ${found} / ${S.rows.size} 条 · 点提示看对应商品`;
      q('.scroll-status').textContent=`已显示 ${visible.length} / ${ids.length} 条 · ${visible.length<ids.length?'继续向下自动加载':'可连续滚轮浏览，无需翻页'}`;
      q('.saved').textContent=S.inflight?'保存 / 载入中…':Object.keys(S.metaDrafts).length||Object.keys(S.drafts).length?'有未确认草稿':`已保存 · ${d.saved_at||d.imported_at} · 版本 ${d.revision}`;
      const keep=new Set(visible.map(r=>r.id));
      for(const tr of [...tbody.children])if(!keep.has(tr.dataset.id))tr.remove();
      for(let i=0;i<visible.length;i++){
        const r=visible[i];let tr=S.dom.get(r.id);
        if(!tr){tr=document.createElement('tr');tr.dataset.id=r.id;tr.innerHTML='<td class="seq"></td><td class="product"></td><td class="difference num"></td><td><input class="edit-count" inputmode="decimal"></td><td><textarea class="edit-note" rows="1"></textarea></td><td class="hints"></td>';S.dom.set(r.id,tr);
          for(const [field,selector] of [['复盘实数','.edit-count'],['备注','.edit-note']]){
            const input=tr.querySelector(selector);input.dataset.field=field;input.setAttribute('aria-label',`${field} ${r.barcode}`);
            input.oninput=()=>{S.editGeneration++;const prior=S.drafts[r.id]?.[field];S.drafts[r.id]??={};S.drafts[r.id][field]={value:input.value,base:prior?prior.base:(field==='复盘实数'?S.rows.get(r.id).recount:S.rows.get(r.id).note)};q('.saved').textContent='正在自动保存输入…';remember();const timerKey=r.id+'|'+field;clearTimeout(S.timers[timerKey]);S.timers[timerKey]=setTimeout(()=>S.commit(r.id,field),650)};
            input.onblur=()=>S.commit(r.id,field);
            input.onkeydown=e=>{if(e.key==='Enter'&&(field==='复盘实数'||!e.shiftKey)){e.preventDefault();S.commit(r.id,field);const idx=S.visible.findIndex(x=>x.id===r.id);const next=S.dom.get(S.visible[idx+1]?.id)?.querySelector(selector);if(next)next.focus()}};
          }
        }
        const paired=S.sort==='pair'&&r.partner&&Math.abs((positions.get(r.partner)??-999)-i)===1;
        tr.className=(r.id===S.focus?'selected ':'')+(paired?'paired '+(positions.get(r.partner)>i?'group-start':'group-end'):'');
        const signature=JSON.stringify([r.name,r.barcode,r.system,r.initial,r.initial_diff,r.diff,r.amount,r.change,r.change_label,r.peers,r.mix_count,r.swap_count,r.unit_hints,r.flags,r.cross,paired,r.partner]);
        if(S.rowSignatures.get(r.id)!==signature){
          S.rowSignatures.set(r.id,signature);tr.querySelector('.seq').textContent=r.sequence;
          tr.querySelector('.product').innerHTML=`${paired&&positions.get(r.partner)>i?'<span class="group-label">疑似串码 / A换B对照组 · 待核实</span>':''}<button class="row-link name">${esc(r.name)}</button><span class="codes">${esc(r.barcode)}</span><span class="stockline">系统 <b>${esc(fmt(r.system))}</b>　初盘 <b>${esc(fmt(r.initial))}</b></span>`;
          tr.querySelector('.row-link').onclick=()=>S.openDetail(r.id,null);
          tr.querySelector('.difference').innerHTML=`<span class="minor">初盘差异 ${r.initial_diff>0?'+':''}${esc(fmt(r.initial_diff))}</span><strong class="${cls(r.diff)}">最新 ${r.diff>0?'+':''}${esc(fmt(r.diff))}</strong><span class="change ${r.change>0?'green':r.change<0?'red':''}">${esc(r.change_label)}${r.change===null?'':` · 变化${r.change>0?'+':''}${esc(fmt(r.change))}`}</span><span class="minor ${cls(r.amount)}">差异成本 ${esc(fmt(r.amount,2))}元</span>`;
          const hints=tr.querySelector('.hints');const peer=r.peers?.find(p=>p.id===r.partner)||r.peers?.[0];
          hints.innerHTML=peer?`<button class="peer-live" data-other="${esc(peer.id)}">${peer.mix?'疑似与':'A换B：与'}【${esc(peer.name)}】${peer.mix?'串码':''} ${paired?'↕':'↔'}<span class="minor">${esc(peer.barcode)} · 对方差异${peer.diff>0?'+':''}${esc(fmt(peer.diff))} · 待核实</span></button>`:'';
          if(peer)hints.querySelector('.peer-live').onclick=()=>S.locateTo(peer.id,r.id);
          const count=r.candidate_count;
          if(count>1){const more=document.createElement('button');more.className='more-peers';more.textContent=`另外${count-1}件疑似商品 ›`;more.onclick=()=>S.openDetail(r.id,null);hints.appendChild(more)}
          const risks=[];if(r.cross?.length)risks.push(`跨店调拨线索${r.cross.length}项`);if(r.unit_hints.length)risks.push(`单位换算${r.unit_hints.length}项`);
          risks.push(...r.flags.filter(f=>['负库存','缺成本','零成本','缺编码','重复条码','缺文字原因','数据错误'].includes(f)));
          if(risks.length){const b=document.createElement('button');b.className='risk-summary';b.textContent=risks.join(' · ')+' ›';b.onclick=()=>S.openDetail(r.id,null);hints.appendChild(b)}
        }
        for(const [field,selector,value] of [['复盘实数','.edit-count',r.recount],['备注','.edit-note',r.note]]){const input=tr.querySelector(selector),draft=S.drafts[r.id]?.[field],next=draft?draft.value:(value??'');if(root.getRootNode().activeElement!==input&&input.value!==String(next))input.value=String(next)}
        if(tbody.children[i]!==tr){if(tbody.moveBefore&&tr.isConnected)tbody.moveBefore(tr,tbody.children[i]||null);else tbody.insertBefore(tr,tbody.children[i]||null)}
      }
      const panel=q('.panel');const detail=d.detail;
      if(detail&&S.detailOpen&&(!S.requestedDetail||(detail.a.id===S.requestedDetail.a&&(detail.b?.id||null)===S.requestedDetail.b))){
        if(!panel.open)panel.showModal();
        const card=r=>`<div class="pair-card"><b>${esc(r.name)}</b><span class="codes">${esc(r.barcode)} / 编码 ${esc(r.code)}</span><dl>${[['系统数',r.system],['初盘数',r.initial],['复盘实数',r.recount===null?'空白':r.recount],['当前总数',r.total],['最新差异',r.diff],['成本',r.cost],['成本依据',r.cost_basis],['规格 / 件装单位',[r.spec,r.unit].filter(Boolean).join(' / ')||'未提供'],['包装系数',r.packing],['零售价',r.retail===null?'缺售价':r.retail],['部 / 大 / 中类',[r.department,r.category,r.middle].join(' / ')],['供货商',r.supplier],['人工原因',r.note||'未填']].map(([a,b])=>`<dt>${esc(a)}</dt><dd>${esc(b??'缺失')}</dd>`).join('')}</dl><button class="jump" data-id="${esc(r.id)}">定位此商品</button></div>`;
        panel.innerHTML=`<div class="panel-title"><span>商品对照 / 输入轨迹 · ${detail.pair?esc(detail.pair.kind+' · '+detail.pair.confidence):'疑似线索，未经确认；归零会自动撤销'}</span><button class="close-panel">收起</button></div><div class="pair-cards">${card(detail.a)}${detail.b?card(detail.b):''}</div>${detail.pair?`<p>${esc(detail.pair.evidence)} · 可解释数量 ${esc(detail.pair.overlap)} · 金额 ¥${esc(detail.pair.amount_overlap)}；疑似待核，不自动抵销。</p>`:''}<div class="detail-peers"></div><p class="risk">${esc([...detail.a.unit_hints,...(detail.a.risk_hints||[]),...(detail.a.cross||[]).map(c=>JSON.stringify(c))].join("；"))}</p><div class="history">${(detail.history||[]).map(h=>`<article>${esc(h.北京时间)} · ${esc(h.操作人)} · ${esc(h.修改来源)}<br>${esc(JSON.stringify(h.旧值))} → ${esc(JSON.stringify(h.新值))}${h.已撤销?'（已撤销）':''}</article>`).join('')||'<p class="muted">暂无升级后的逐商品编辑记录；旧保存日志保留在批次备份中。</p>'}</div>`;
        panel.querySelector('.close-panel').onclick=()=>{S.detailOpen=false;panel.close()};panel.oncancel=()=>{S.detailOpen=false};
        panel.querySelectorAll('.jump').forEach(b=>b.onclick=()=>{S.detailOpen=false;panel.close();S.locateTo(b.dataset.id,detail.a.id)});
        const more=panel.querySelector('.detail-peers');
        for(const p of detail.peers||[]){const b=document.createElement('button');b.className='peer';b.textContent=`${p.kind} ↔ ${p.name} / ${p.barcode} / 对方差异${p.diff>0?'+':''}${p.diff} / ${p.evidence} ›`;b.onclick=()=>S.openDetail(detail.a.id,p.id);more.appendChild(b)}
        if(detail.has_more){const b=document.createElement('button');b.textContent='再展开50条候选';b.onclick=()=>S.enqueue('more_peers');more.appendChild(b)}
      }else if(S.detailOpen){if(!panel.open)panel.showModal();panel.innerHTML='<p>正在载入对应商品…</p>'}else if(panel.open)panel.close();
      if(!reset){if(anchor?.isConnected){const delta=anchor.getBoundingClientRect().top-anchorTop;if(Math.abs(delta)>1)scroller.scrollTop=priorScroll+delta}else scroller.scrollTop=priorScroll}
      if(active?.isConnected&&root.getRootNode().activeElement!==active)active.focus({preventScroll:true});
      S.requestVisible();

    };
  }
  S.comp=component;S.data=data;if(S.sort==='mix')S.sort='pair';S.rows=new Map(data.rows.map(r=>[r.id,r]));
  const q=s=>root.querySelector(s);
  for(const [selector,values,all] of [['.category',[...new Set(data.rows.map(r=>r.category))].sort(),'全部品类'],['.supplier',[...new Set(data.rows.map(r=>r.supplier))].sort(),'全部供应商']]){
    const select=q(selector),value=selector==='.category'?S.category:S.supplier;
    select.innerHTML=`<option value="">${all}</option>`+values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');select.value=value;
  }
  if(data.ack&&data.ack.id!==S.seenAck){
    S.seenAck=data.ack.id;
    if(S.inflight?.request_id===data.ack.id){const e=S.inflight;
      if(data.ack.ok&&(e.kind==='edit'||e.kind==='edits')){
        for(const edit of e.kind==='edits'?e.entries:[e]){
          if(S.drafts[edit.id]?.[edit.field]?.value===edit.value){delete S.drafts[edit.id][edit.field];if(!Object.keys(S.drafts[edit.id]).length)delete S.drafts[edit.id]}
          else if(S.drafts[edit.id]?.[edit.field])S.drafts[edit.id][edit.field].base=edit.value;
          for(const queued of S.queue)if(queued.kind==='edit'&&queued.id===edit.id&&queued.field===edit.field)queued.base=edit.value;
        }
      }
      if(data.ack.ok&&e.kind==='meta'){
        const draft=S.metaDrafts[e.metaKey];if(draft?.value===e.value)delete S.metaDrafts[e.metaKey];else if(draft)draft.base=e.value;
        for(const queued of S.queue)if(queued.kind==='meta'&&queued.metaKey===e.metaKey)queued.base=e.value;
      }
      if(!data.ack.ok){S.queue=S.queue.filter(p=>p.kind!=='copy_snapshot');S.restore=true;if(S.copyIntent)S.abortCopy('保存失败，未复制任何文稿；请核对输入后重试')}
      if(data.ack.ok&&e.kind==='bulk')q('.bulk').classList.add('hidden');
      if(data.ack.ok&&e.kind==='refresh'){
        for(const [id,fields] of Object.entries(S.drafts))for(const [field,draft] of Object.entries(fields)){
          const row=S.rows.get(id);if(row)draft.base=field==='复盘实数'?row.recount:row.note;
        }
        for(const [key,draft] of Object.entries(S.metaDrafts))draft.base=S.metaValue(key);
        S.restore=Object.keys(S.drafts).length>0||Object.keys(S.metaDrafts).length>0;
      }
      S.inflight=null;S.remember();
      if(data.ack.ok&&e.kind==='copy_snapshot'&&S.copyIntent?.id===e.request_id){const intent=S.copyIntent;queueMicrotask(()=>S.finishCopy(data.copy_snapshot,intent))}
      if(!Object.keys(S.drafts).length&&!Object.keys(S.metaDrafts).length)S.restore=false;
    }
  }
  S.render();S.pump();
  document.addEventListener('scroll',S.onScroll,true);S.observer.observe(q('.load-sentinel'));
  return ()=>{document.removeEventListener('scroll',S.onScroll,true);S.observer.disconnect()};
}
