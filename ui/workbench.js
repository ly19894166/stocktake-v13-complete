export default function(component) {
  const {parentElement}=component;
  const data=typeof component.data==='string'?JSON.parse(component.data):component.data;
  // CCv2在触发与重跑间可能先调用一次无业务data的生命周期，保留原DOM和草稿。
  if(!data||!Array.isArray(data.rows))return;
  const root=parentElement.querySelector('#stocktake-workbench');
  if(!root)return;
  root.classList.toggle('native-summary',!!data.native_summary);
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=(v,n=4)=>v===null||v===undefined?'—':Number(v).toLocaleString('zh-CN',{minimumFractionDigits:n===2?2:0,maximumFractionDigits:n});
  const cls=v=>v<0?'red':v>0?'green':'zero';
  // 只缩短已有引擎的变化文字；数量、调整和金额继续使用后端V13结果。
  const shortChange=r=>r.recount===null?'':r.diff===0?'✓归零':r.change===0?'':(r.change>0?'↑':'↓')+r.change_label.split(' · ')[0].replace(/件/g,'').replace('盘亏增加','亏增').replace('盘盈减少','盈减').replace('盘盈增加','盈增').replace('盘亏减少','亏减');
  let S=root.__inventory;
  if(S&&S.layoutVersion!==8){S.remember?.();S.observer?.disconnect();root.__inventory=null;S=null}
  if(!S){
    let local={};try{local=JSON.parse(localStorage.getItem('stocktake:'+data.batch)||'{}')}catch{}
    const migrated=local.flowVersion!==6;
    S=root.__inventory={query:migrated?'':local.query||'',filters:migrated?[]:local.filters||[],category:migrated?'':local.category||'',supplier:migrated?'':local.supplier||'',sort:migrated?'sequence':local.sort||'sequence',scope:migrated?'exclude':local.scope||'exclude',columns:migrated?{}:local.columns||{},order:[],orderKey:'',loaded:200,editGeneration:0,copyIntent:null,drafts:local.drafts||{},queue:[],inflight:null,rows:new Map(),dom:new Map(),focus:null,seenAck:null,viewKey:'',rowSignatures:new Map(),restore:!!Object.keys(local.drafts||{}).length,metaDrafts:local.metaDrafts||{},timers:{},reportOpen:false,detailOpen:false,exportOpen:false,exportIntent:null,exportSnapshot:null,selection:new Set(),selectionAnchor:null,dragSelection:null,balanceDrafts:{}};
    S.layoutVersion=8;
    root.innerHTML=`<div class="operating-panel">
      <div class="operating-inputs"><label>实际销售金额（元）<input data-meta="sales_amount" inputmode="decimal" aria-label="实际销售金额（元）" placeholder="待填写"></label><label>同期含税销售成本（元）<input data-meta="sales_cost" inputmode="decimal" aria-label="同期含税销售成本（元）" placeholder="待填写"></label><div class="calculation-status"></div><button class="export-open primary">下载盘点结果 ▾</button><button class="report-open">生成盘点汇报</button></div>
      <div class="audit muted">当前测算，仅供复盘；正式导出在顶部“下载盘点结果”中检查。</div></div><div class="metrics summary-rail" data-testid="metrics" aria-label="整店统计，包含全批次商品"></div>
      <div class="toolbar primary-tools"><select class="scope" aria-label="商品范围"><option value="exclude">不含卓不凡（默认）</option><option value="all">全部商品</option><option value="zbf">仅卓不凡</option></select><input class="search" aria-label="搜索商品名、编码、完整条码或尾号" placeholder="商品名称 / 编码 / 完整条码 / 尾号4–8位"><select class="category" aria-label="品类筛选"></select><select class="view" aria-label="找货查看方式"><option value="sequence">原始序号（默认）</option><option value="amount">差异金额优先</option><option value="pair">疑似串码联排</option><option value="category">按品类查找</option></select><button class="regroup" title="按最新数据更新排序">刷新排序</button><button class="jump-bottom" title="加载当前筛选的全部商品并跳到合计行；Ctrl+End">↓ 直达表尾</button><button class="undo">撤销上次输入</button><button class="bulk-toggle">批量粘贴</button><button class="clear">清除筛选</button><button class="more-toggle" aria-expanded="false">更多筛选</button></div>
      <div class="more-filters hidden"><div class="toolbar"><select class="supplier" aria-label="供应商筛选"></select><select class="sort" aria-label="建议排序"><option value="sequence">原始序号（默认）</option><option value="pair">疑似串码联排</option><option value="amount">差异金额优先</option><option value="quantity">数量优先</option><option value="category">按品类查找</option><option value="score">综合建议分</option></select><button class="refresh">刷新数据</button></div><div class="chips"></div><span class="muted">组合筛选同时满足；只改变显示顺序，不改变记录、实数和导出顺序。</span></div>
      <select class="locate hidden" aria-label="条码尾号匹配结果"></select><div class="message"></div>
      <div class="bulk hidden"><strong>批量粘贴复盘数</strong><p class="muted">每行：完整条码 Tab 复盘实数 Tab 人工备注 Tab 单位说明（后两项可省略）。全部校验通过后一次保存。</p><textarea aria-label="批量粘贴复盘数据"></textarea><button class="primary bulk-submit">校验并保存全部粘贴行</button></div>
      <div class="guide"><span class="result-count"></span><span class="saved" data-testid="save-status"></span></div>
      <section class="balance-section hidden" aria-label="卓不凡A换B专项核对"></section>
      <div class="table-wrap"><table aria-label="01现场复盘表"><colgroup>${['seq','category','product','barcode','code','system','initial','recount','total','difference','amount','note','supplier','hints'].map(c=>`<col class="col-${c}">`).join('')}</colgroup><thead><tr><th><button class="header-filter" data-column="sequence" aria-label="筛选序号">序号 ▾</button></th><th><button class="header-filter" data-column="category" aria-label="筛选品类">品类 ▾</button></th><th><button class="header-filter" data-column="name" aria-label="筛选商品名称">商品名称 ▾</button></th><th><button class="header-filter" data-column="barcode" aria-label="筛选商品条码">商品条码 ▾</button></th><th class="col-code"><button class="header-filter" data-column="code" aria-label="筛选商品编码">商品编码 ▾</button></th><th><button class="header-filter" data-column="system" aria-label="筛选系统数">系统数 ▾</button></th><th><button class="header-filter" data-column="initial" aria-label="筛选初盘数">初盘数 ▾</button></th><th><button class="header-filter" data-column="recount" aria-label="筛选复盘实数">复盘实数 ▾</button></th><th><button class="header-filter" data-column="total" aria-label="筛选当前实物总数">当前实物总数 ▾</button></th><th><button class="header-filter" data-column="diff" aria-label="筛选最新差异">最新差异 ▾</button></th><th><button class="header-filter" data-column="amount" aria-label="筛选差异金额（元）">差异金额（元） ▾</button></th><th><button class="header-filter" data-column="note" aria-label="筛选备注／原因">备注／原因 ▾</button></th><th class="col-supplier"><button class="header-filter" data-column="supplier" aria-label="筛选供货商">供货商 ▾</button></th><th><button class="header-filter" data-column="hints" aria-label="筛选核查标签">核查标签 ▾</button></th></tr></thead><tbody></tbody><tfoot class="column-totals" aria-label="当前筛选与全店数字合计"></tfoot></table></div>
      <div class="load-sentinel" aria-label="连续浏览加载位置"></div><div class="table-tail"><span class="totals-note">数字合计仅供核对，不换算商品单位，不替代实盘或正式损耗计算。</span><button class="jump-top">↑ 返回表头</button></div><div class="scroll-status muted"></div>
      <div class="selection-status" role="status" aria-label="单元格计数与求和"><span class="selection-text">选中：0格　数值计数：0　求和：—</span><button class="selection-clear">清除选择</button></div>
      <dialog class="export-dialog" aria-label="下载盘点结果"><div class="panel-title"><strong>下载盘点结果 · 全店三列</strong><button class="export-close">关闭</button></div><p class="export-status" aria-live="polite"></p><div class="export-info"></div><details class="export-check-details"><summary>完整性核查与剩余问题</summary><label><input type="checkbox" class="export-coverage">确认同门店、同期间且覆盖本次完整盘点范围</label><label><input type="checkbox" class="export-evidence">确认差异已核实、相关凭证齐备</label><button class="export-check-save">保存导出核查</button><div class="export-blockers"></div></details><details class="export-preview"><summary>公司三列文件预览（全店）</summary><div class="export-preview-table"></div></details><div class="toolbar"><button class="export-download primary" disabled>下载公司盘点表.xls</button><span class="muted">每次下载先保存输入并重新读取全店；不使用筛选结果或未确认建议。</span></div></dialog>
      <dialog class="filter-dialog" aria-label="列筛选面板"></dialog><dialog class="panel" aria-label="商品详情与对应候选"></dialog>
      <dialog class="note-dialog" aria-label="展开编辑人工备注"><div class="panel-title"><strong>人工备注／原因</strong><button class="note-close">保存并收起</button></div><textarea class="note-editor" aria-label="完整人工备注"></textarea><p class="muted">自动保存。系统线索不会覆盖人工备注。</p></dialog>
      <dialog class="calculation-dialog" aria-label="V13差异计算依据"><div class="panel-title"><strong>V13差异计算依据</strong><button class="calculation-close">关闭</button></div><div class="calculation-body"></div></dialog>
      <dialog class="report-dialog" aria-label="季度盘点汇报"><div class="panel-title"><strong>季度盘点汇报</strong><button class="report-close">关闭</button></div><div class="report-fields"></div><p class="report-warnings muted"></p><label class="report-label">最终文稿（可直接编辑，自动保存）<textarea class="report-text" aria-label="最终盘点汇报文稿"></textarea></label><div class="toolbar"><button class="report-copy primary">一键复制文稿</button><button class="report-reset">按最新数据重新生成</button><button class="report-old hidden">查看上次人工稿</button><span class="copy-status" aria-live="polite"></span></div></dialog>`;
    const q=s=>root.querySelector(s);
    const remember=()=>{try{localStorage.setItem('stocktake:'+S.data.batch,JSON.stringify({query:S.query,filters:S.filters,category:S.category,supplier:S.supplier,sort:S.sort,scope:S.scope,columns:S.columns,flowVersion:6,drafts:S.drafts,metaDrafts:S.metaDrafts}))}catch{}};
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
    S.editCell=(id,field,value)=>{S.editGeneration++;const prior=S.drafts[id]?.[field];S.drafts[id]??={};S.drafts[id][field]={value,base:prior?prior.base:(field==='复盘实数'?S.rows.get(id).recount:S.rows.get(id).note)};q('.saved').textContent='正在自动保存输入…';remember();S.renderSelection();const key=id+'|'+field;clearTimeout(S.timers[key]);S.timers[key]=setTimeout(()=>S.commit(id,field),650)};
    S.openNote=id=>{const dialog=q('.note-dialog'),editor=q('.note-editor');S.noteID=id;editor.value=S.drafts[id]?.备注?.value??S.rows.get(id).note;editor.oninput=()=>S.editCell(id,'备注',editor.value);dialog.showModal();editor.focus()};
    const closeNote=()=>{S.commit(S.noteID,'备注');q('.note-dialog').close();S.dom.get(S.noteID)?.querySelector('.edit-note').focus({preventScroll:true})};
    q('.note-close').onclick=closeNote;q('.note-dialog').oncancel=e=>{e.preventDefault();closeNote()};
    S.openCalculation=id=>{const r=S.rows.get(id);q('.calculation-body').innerHTML=`<p><b>${esc(r.name)}</b> · ${esc(r.barcode)}</p><dl>${[['系统数',r.system],['初盘数',r.initial],['原始调整',r.adjustment],['初盘差异',r.initial_diff],['复盘实数',r.recount===null?'空白，未复盘':r.recount],['当前实物总数',r.total],['最新差异',r.diff],['复盘变化',r.change],['变化说明',r.change_label],['差异成本金额（元）',r.amount]].map(([a,b])=>`<dt>${esc(a)}</dt><dd>${esc(b??'未知')}</dd>`).join('')}</dl><p>初盘差异＝初盘数−系统数＋原始调整<br>最新差异＝当前实物总数−系统数＋原始调整<br>未填复盘实数沿用初盘；0表示已确认实物为0。</p>`;q('.calculation-dialog').showModal()};
    q('.calculation-close').onclick=()=>q('.calculation-dialog').close();
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
    q('.scope').value=S.scope;q('.scope').onchange=e=>{S.scope=e.target.value;S.focus=null;S.filterChanged=true;remember();S.enqueue('scope',{scope:S.scope});S.render()};
    q('.search').value=S.query;
    q('.search').oninput=e=>{S.query=e.target.value;S.focus=null;S.filterChanged=true;remember();S.render()};
    q('.category').onchange=e=>{S.category=e.target.value;S.focus=null;S.filterChanged=true;remember();S.render()};
    q('.supplier').onchange=e=>{S.supplier=e.target.value;S.focus=null;S.filterChanged=true;remember();S.render()};
    q('.sort').value=S.sort;q('.sort').onchange=e=>{S.sort=e.target.value;q('.view').value=S.sort;S.focus=null;S.filterChanged=true;remember();S.render()};
    q('.clear').onclick=()=>{S.query='';S.filters=[];S.category='';S.supplier='';S.scope='exclude';S.sort='sequence';S.columns={};S.focus=null;S.filterChanged=true;S.orderKey='';q('.search').value='';q('.category').value='';q('.supplier').value='';q('.view').value='sequence';q('.sort').value='sequence';q('.scope').value='exclude';remember();S.enqueue('scope',{scope:S.scope});S.render()};
    const columns={sequence:'序号',category:'品类',name:'商品名称',barcode:'商品条码',code:'商品编码',system:'系统数',initial:'初盘数',recount:'复盘实数',total:'当前实物总数',diff:'最新差异',amount:'差异金额（元）',note:'备注／原因',supplier:'供货商',hints:'核查标签'};
    const select=(label,key,options,value)=>`<label>${esc(label)}<select data-filter-field="${key}" aria-label="${esc(label)}">${options.map(([v,t])=>`<option value="${v}" ${String(v)===String(value)?'selected':''}>${esc(t)}</option>`).join('')}</select></label>`;
    S.openFilter=column=>{
      const pane=q('.filter-dialog'),f=S.columns[column]||{};const numeric=['system','initial','recount','total','diff','amount'].includes(column);let body='';
      if(['name','barcode','code'].includes(column))body=`<label>包含文字或完整数字<input data-filter-field="text" aria-label="列搜索内容" value="${esc(f.text||'')}"></label>`;
      if(column==='category'||column==='supplier')body=select(columns[column],'value',[['','全部'],...[...new Set([...S.rows.values()].map(r=>r[column]))].sort().map(v=>[v,v])],column==='category'?S.category:S.supplier);
      if(numeric){
        const modes=column==='diff'?[['','全部'],['loss','盘亏'],['gain','盘盈'],['zero','差异归零'],['nonzero','仍有差异'],['unreviewed','未复盘'],['reviewed','已复盘']]:column==='amount'?[['','全部'],['loss','盘亏'],['gain','盘盈'],['zero','差异归零'],['missing','缺成本／待核实']]:[['','全部'],['blank','空白'],['filled','已填写'],['zero','等于0']];
        body=select('筛选状态','mode',modes,f.mode||'')+`<div class="range-fields"><label>最小值（含）<input data-filter-field="min" aria-label="最小值（含）" inputmode="decimal" value="${esc(f.min??'')}"></label><label>最大值（含）<input data-filter-field="max" aria-label="最大值（含）" inputmode="decimal" value="${esc(f.max??'')}"></label></div><p class="muted">按带正负号的实际数值筛选；盘亏为负数。空白不等于0。</p>`;
        if(['diff','amount'].includes(column))body+=select('排序方式','sort',[['sequence','原始序号'],['quantity','差异数量绝对值'],['amount','差异金额绝对值']],S.sort);
      }
      if(column==='note')body=select('人工备注','mode',[['','全部'],['yes','有人工备注'],['no','无人工备注']],f.mode||'');
      if(column==='hints')body=select('线索与资格','mode',[['','全部'],['mix','疑似串码'],['eligible','允许A换B'],['swap','存在A换B候选'],['pending','供货商待确认']],f.mode||'');
      if(column==='sequence')body=select('排序方式','sort',[['sequence','原始序号（默认）'],['amount','差异金额绝对值'],['quantity','差异数量绝对值'],['pair','疑似串码联排'],['category','按品类查找']],S.sort);
      pane.innerHTML=`<div class="panel-title"><strong>${esc(columns[column])}筛选</strong><button class="filter-close">关闭</button></div>${body}<p class="filter-error red"></p><div class="toolbar"><button class="filter-apply primary">应用列筛选</button><button class="filter-reset">清除此列</button></div>`;
      pane.querySelector('.filter-close').onclick=()=>pane.close();
      pane.querySelector('.filter-reset').onclick=()=>{delete S.columns[column];if(column==='category')S.category='';if(column==='supplier')S.supplier='';S.focus=null;S.filterChanged=true;S.orderKey='';remember();pane.close();S.render()};
      pane.querySelector('.filter-apply').onclick=()=>{const next={};for(const el of pane.querySelectorAll('[data-filter-field]')){const k=el.dataset.filterField,v=el.value.trim();if(k==='sort'){S.sort=v;continue}if(v!==''){if(['min','max'].includes(k)){if(!Number.isFinite(Number(v))){pane.querySelector('.filter-error').textContent='请输入有效数字';return}next[k]=Number(v)}else next[k]=v}}if(next.min!==undefined&&next.max!==undefined&&next.min>next.max){pane.querySelector('.filter-error').textContent='最小值不能大于最大值';return}if(column==='category')S.category=next.value||'';else if(column==='supplier')S.supplier=next.value||'';else S.columns[column]=next;S.focus=null;S.filterChanged=true;S.orderKey='';q('.view').value=S.sort;q('.sort').value=S.sort;remember();pane.close();S.render()};
      pane.showModal();
    };
    root.querySelectorAll('.header-filter').forEach(b=>b.onclick=()=>S.openFilter(b.dataset.column));
    q('.undo').onclick=()=>S.enqueue('undo');q('.refresh').onclick=()=>S.enqueue('refresh');
    q('.bulk-toggle').onclick=()=>q('.bulk').classList.toggle('hidden');
    q('.bulk-submit').onclick=()=>S.enqueue('bulk',{text:q('.bulk textarea').value});
    q('.locate').onchange=e=>{if(e.target.value)S.openDetail(e.target.value,null)};
    S.openDetail=(a,b)=>{S.detailOpen=true;S.requestedDetail={a,b:b||null};S.enqueue('detail',{a,b});S.render()};
    S.locateTo=(id,from=null)=>{S.focus=id;S.locateFrom=from;S.render();S.dom.get(id)?.scrollIntoView({block:'center',behavior:'smooth'})};
    q('.view').value=S.sort;
    q('.view').onchange=e=>{S.sort=e.target.value;q('.sort').value=S.sort;S.orderKey='';S.focus=null;S.filterChanged=true;remember();S.render()};
    q('.regroup').onclick=()=>{S.orderKey='';S.render()};
    S.scrollParent=()=>{for(let el=root.getRootNode().host;el;el=el.parentElement)if(/auto|scroll/.test(getComputedStyle(el).overflowY)&&el.scrollHeight>el.clientHeight+10)return el;return document.scrollingElement};
    S.requestVisible=()=>{if(S.inflight||S.queue.some(e=>e.kind==='view'))return;const ids=S.visible.filter(r=>{const el=S.dom.get(r.id);if(!el)return false;const box=el.getBoundingClientRect();return box.bottom>-500&&box.top<innerHeight+800}).map(r=>r.id).filter(id=>!S.data.enriched.includes(id)).slice(0,150);if(ids.length)S.enqueue('view',{ids})};
    S.onScroll=()=>{if(!root.isConnected)return;clearTimeout(S.scrollTimer);S.scrollTimer=setTimeout(S.requestVisible,160)};
    S.observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)&&S.loaded<S.filteredCount){S.loaded+=200;S.render()}},{rootMargin:'900px'});
    // 导出屏障：先提交实数/备注/经营草稿，等待逐次确认，再读全批次最新版本。
    S.abortExport=message=>{S.exportIntent=null;S.exportSnapshot=null;q('.export-status').textContent=message;q('.export-download').disabled=true};
    S.requestExport=purpose=>{
      if(S.exportIntent)return;
      S.exportOpen=true;S.exportSnapshot=null;S.flush();
      const intent={id:crypto.randomUUID(),purpose,generation:S.editGeneration};S.exportIntent=intent;
      const extra=purpose==='checks'?{coverage:q('.export-coverage').checked,evidence:q('.export-evidence').checked}:{};
      S.queue.push({kind:purpose==='checks'?'export_checks':'export_snapshot',...extra,request_id:intent.id});
      q('.export-status').textContent='正在提交输入并核对全店最新版本，尚未生成文件…';q('.export-download').disabled=true;S.pump();S.renderExport();
    };
    S.finishExport=(snapshot,intent)=>{
      if(S.exportIntent!==intent)return;
      if(!S.exportOpen||intent.generation!==S.editGeneration||Object.keys(S.drafts).length||Object.keys(S.metaDrafts).length||S.queue.some(e=>e.kind!=='view')||!snapshot||snapshot.id!==intent.id||snapshot.batch!==S.data.batch||snapshot.revision!==S.data.revision||snapshot.signature!==S.data.export_signature){S.abortExport('数据仍在变化或未保存，未下载旧文件；请核对并重试');return}
      S.exportIntent=null;S.exportSnapshot=snapshot;S.exportRendered=null;S.renderExport();
      if(intent.purpose==='download'){
        if(!snapshot.xls){q('.export-status').textContent='正式导出被阻断，请完成剩余问题；未下载文件';return}
        const bytes=Uint8Array.from(atob(snapshot.xls),c=>c.charCodeAt(0)),url=URL.createObjectURL(new Blob([bytes],{type:'application/vnd.ms-excel'}));const a=document.createElement('a');a.href=url;a.download='公司盘点表.xls';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);q('.export-status').textContent=`已按全店最新已保存版本 ${snapshot.revision} 生成公司三列文件`;
      }
    };
    S.renderExport=()=>{
      const dialog=q('.export-dialog');if(!S.exportOpen){if(dialog.open)dialog.close();return}if(!dialog.open)dialog.showModal();
      const snapshot=S.exportSnapshot;if(!snapshot)return;
      if(S.exportRendered!==snapshot.id){S.exportRendered=snapshot.id;
        q('.export-info').textContent=`当前批次：${snapshot.store} · ${snapshot.period} · ${snapshot.batch}｜全店${snapshot.count}条 · 已复盘${snapshot.done} / 待复盘${snapshot.remaining}｜数据检查${snapshot.errors.length}项 · 已保存版本${snapshot.revision}`;
        q('.export-status').textContent=snapshot.blockers.length?`核对草稿 · ${snapshot.blockers.length}项条件待完成`:'正式候选 · 当前本机检查通过，公司上传与审批仍由人工完成';
        q('.export-coverage').checked=snapshot.coverage;q('.export-evidence').checked=snapshot.evidence;
        q('.export-blockers').innerHTML=snapshot.blockers.length?'<ul>'+snapshot.blockers.map(b=>`<li>${esc(b)}</li>`).join('')+'</ul>':'<p>原有完整性及正式导出检查通过。</p>';
        q('.export-preview-table').innerHTML='<table><thead><tr>'+snapshot.headers.map(h=>`<th>${esc(h)}</th>`).join('')+'</tr></thead><tbody>'+snapshot.rows.map(row=>'<tr>'+row.map(v=>`<td>${esc(v??'待核实')}</td>`).join('')+'</tr>').join('')+'</tbody></table>';
      }
      q('.export-download').disabled=!!S.exportIntent||!snapshot.xls;
    };
    q('.export-open').onpointerdown=()=>{const el=root.getRootNode().activeElement,tr=el?.closest?.('.table-wrap tbody tr');S.exportReturnFocus=el;S.exportReturnScroll=S.scrollParent().scrollTop;S.exportAnchor=tr?{id:tr.dataset.id,index:[...q('.table-wrap tbody').children].indexOf(tr)}:null};
    q('.export-open').onclick=()=>{if(!S.exportReturnFocus){S.exportReturnFocus=root.getRootNode().activeElement;S.exportReturnScroll=S.scrollParent().scrollTop}S.requestExport('open')};
    S.closeExport=()=>{S.exportOpen=false;S.exportIntent=null;q('.export-dialog').close();S.exportReturnFocus?.focus?.({preventScroll:true});S.scrollParent().scrollTop=S.exportReturnScroll??S.scrollParent().scrollTop;S.exportAnchor=null;S.exportReturnFocus=null};
    q('.export-close').onclick=S.closeExport;q('.export-dialog').oncancel=e=>{e.preventDefault();S.closeExport()};q('.export-download').onclick=()=>S.requestExport('download');q('.export-check-save').onclick=()=>S.requestExport('checks');

    const statFields=['system','initial','recount','total','diff','amount'];
    S.renderSelection=()=>{
      const visible=new Set(S.visible?.map(r=>r.id)||[]);S.selection=new Set([...S.selection].filter(k=>{try{return visible.has(JSON.parse(k)[0])}catch{return false}}));
      root.querySelectorAll('.table-wrap tbody [data-stat-field]').forEach(td=>td.classList.toggle('cell-selected',S.selection.has(cellKey(td.closest('tr').dataset.id,td.dataset.statField))));
      const stats=selectionStats(S.rows,S.selection,S.drafts);
      q('.selection-text').textContent=`选中：${stats.selected}格　数值计数：${stats.numeric}　${stats.mixed?'数字求和':'求和'}：${stats.numeric?stats.sum:'—'}${Object.keys(S.drafts).length?' · 含未保存输入':''}`;
    };
    S.rangeSelection=(anchor,end,base=[])=>{
      const ids=S.visible.map(r=>r.id),a=ids.indexOf(anchor.id),b=ids.indexOf(end.id),c=statFields.indexOf(anchor.field),d=statFields.indexOf(end.field);if(Math.min(a,b,c,d)<0)return;
      S.selection=new Set(base);for(let i=Math.min(a,b);i<=Math.max(a,b);i++)for(let j=Math.min(c,d);j<=Math.max(c,d);j++)S.selection.add(cellKey(ids[i],statFields[j]));S.renderSelection();
    };
    q('.table-wrap').onpointerdown=e=>{
      if(e.button!==0)return;const td=e.target.closest('[data-stat-field]');if(!td||!td.closest('tbody'))return;
      const end={id:td.closest('tr').dataset.id,field:td.dataset.statField},key=cellKey(end.id,end.field),add=e.ctrlKey||e.metaKey,base=add?[...S.selection]:[];
      if(e.shiftKey&&S.selectionAnchor){S.rangeSelection(S.selectionAnchor,end,base);e.preventDefault();return}
      S.selection=add?new Set(S.selection):new Set();if(add&&S.selection.has(key))S.selection.delete(key);else S.selection.add(key);
      S.selectionAnchor=end;S.dragSelection={anchor:end,base,last:key};S.renderSelection();if(add||e.target.tagName!=='INPUT')e.preventDefault();
    };
    q('.table-wrap').onpointerover=e=>{
      if(!S.dragSelection||e.buttons!==1)return;const td=e.target.closest('[data-stat-field]');if(!td||!td.closest('tbody'))return;
      const end={id:td.closest('tr').dataset.id,field:td.dataset.statField},key=cellKey(end.id,end.field);if(key===S.dragSelection.last)return;
      S.dragSelection.last=key;S.rangeSelection(S.dragSelection.anchor,end,S.dragSelection.base);root.getRootNode().getSelection?.()?.removeAllRanges();
    };
    S.onPointerUp=()=>{S.dragSelection=null};q('.selection-clear').onclick=()=>{S.selection.clear();S.selectionAnchor=null;S.renderSelection()};

    S.renderBalance=()=>{
      const section=q('.balance-section');section.classList.toggle('hidden',S.scope!=='zbf');if(S.scope!=='zbf')return;
      const b=S.data.balance;if(!b){section.textContent='正在按已确认卓不凡目录分析建议…';return}
      const signature=JSON.stringify([b.id,b.version,b.stale,S.data.revision]);if(S.balanceRendered===signature)return;S.balanceRendered=signature;
      const entries=Object.values(b.plan.rows),pending=entries.filter(r=>r.stage==='pending'),done=entries.filter(r=>['confirmed','manual'].includes(r.stage)),unmatched=entries.filter(r=>['unmatched','rejected'].includes(r.stage)),display=entries.filter(r=>['pending','confirmed','rejected'].includes(r.stage));
      section.innerHTML=`<div class="balance-heading"><strong>卓不凡A换B专项核对</strong><button class="balance-generate">重新计算未确认建议</button><span>待复核 ${pending.length}条　已确认 ${done.length}条　无法匹配 ${unmatched.length}条</span></div><p class="muted">${b.stale?'数据或供应商目录已变化，原建议不可确认，请重新计算。':'已自动分析。浅黄色为独立建议草稿，确认前不进入整店盈亏、导出或打印完成状态。'} 来源版本${b.source_revision} / 当前版本${b.revision}</p><table class="balance-table"><thead><tr>${['商品名称','系统数','初盘数','原差异','建议复盘数','可解释换货数','对应商品','核对操作与说明'].map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody></tbody></table><details><summary>无法匹配/需重新核对 ${unmatched.length}条 · 查看原因</summary><ul>${unmatched.map(r=>`<li>${esc(S.rows.get(r.id)?.name)}：${esc(r.reason)}</li>`).join('')}</ul></details><div class="balance-relations">${b.plan.relations.map(r=>`<span>${esc(S.rows.get(r.a)?.name)} ↔ ${esc(S.rows.get(r.b)?.name)}：${b.stale?'旧关系已过期':({pending:'双方均待现场确认',partial:'仅单方已确认，另一端待核对',verified:'双方已确认且数量守恒，关系已核实',mismatch:'数量或方向不一致，仍待核对',rejected:'已驳回，待重新核对'}[r.status]||'待核对')}</span>`).join('')}</div><details><summary>建议、驳回与逐条确认历史</summary>${(b.history||[]).map(h=>`<p>${esc(h.at)} · ${esc({generate:'重新生成',draft:'保存建议草稿',confirm:'现场确认',reject:'驳回'}[h.kind]||h.kind)} · ${esc(S.rows.get(h.item)?.name||'本批次')} ${h.kind==='confirm'?esc('原实盘 '+(h.old??'空白')+' → '+h.new):''} ${esc(h.note)}</p>`).join('')}</details>`;
      section.querySelector('.balance-generate').onclick=()=>{if(S.inflight)return;S.flush();S.enqueue('balance_generate')};
      const body=section.querySelector('tbody');for(const entry of display){const r=S.rows.get(entry.id),peer=S.rows.get(entry.peer),token=b.id+'|'+entry.id,draft=S.balanceDrafts[token]||{value:entry.draft??'',note:entry.note||''};S.balanceDrafts[token]=draft;const tr=document.createElement('tr');tr.dataset.balanceId=entry.id;
        tr.innerHTML=`<td><b>${esc(r.name)}</b></td><td class="num">${esc(fmt(r.system))}</td><td class="num">${esc(fmt(r.initial))}</td><td class="num ${cls(Number(entry.base_diff))}">${esc(entry.base_diff)}</td><td><input class="balance-value" aria-label="建议复盘数 ${esc(r.barcode)}" value="${esc(draft.value)}" inputmode="decimal" ${b.stale||entry.stage!=='pending'?'disabled':''}></td><td class="num">${esc(entry.q)}</td><td><button class="balance-peer">${esc(peer?.name||'待确认')}</button></td><td>${entry.stage==='pending'?`<input class="balance-note" aria-label="现场核查说明 ${esc(r.barcode)}" placeholder="现场核查说明" value="${esc(draft.note)}"><button class="balance-confirm primary">确认本条实盘</button><button class="balance-save">保存建议草稿</button><button class="balance-reject">驳回/重新核对</button>`:`<span>${entry.stage==='confirmed'?'本条实盘已确认':'已驳回'}</span>`}</td>`;
        tr.querySelector('.balance-peer').onclick=()=>S.openDetail(entry.id,entry.peer);
        const value=tr.querySelector('.balance-value');value.oninput=()=>draft.value=value.value;
        if(entry.stage==='pending'){const note=tr.querySelector('.balance-note');note.oninput=()=>draft.note=note.value;
          for(const [selector,kind] of [['.balance-confirm','balance_confirm'],['.balance-save','balance_draft'],['.balance-reject','balance_reject']]){const button=tr.querySelector(selector);button.disabled=b.stale;button.onclick=()=>{if(S.inflight)return;S.flush();S.enqueue(kind,{run:b.id,version:b.version,id:entry.id,value:value.value,note:note.value});button.disabled=true}}}
        body.appendChild(tr);
      }
    };

    S.renderColumnTotals=filtered=>{
      const scopes=[['filtered','当前筛选合计',columnTotals(filtered)],['store','全店所有商品合计',columnTotals([...S.rows.values()])]];
      q('.column-totals').innerHTML=scopes.map(([scope,label,t])=>`<tr data-total-scope="${scope}"><th colspan="4" scope="row" class="totals-range">${label} · ${t.count}条<small>已填复盘 ${t.reviewed} / 未填 ${t.remaining}</small></th><td class="col-code"></td>${TOTAL_FIELDS.map(field=>{const c=t.columns[field],unknown=field!=='recount'&&c.missing;return `<td class="num total-${field}${field==='total'?' current-total-sum':''}" data-total-field="${field}" data-sum="${esc(c.sum)}" title="${esc(columns[field])}合计；有效数值${c.numeric}条${c.missing?'，'+c.missing+'条'+(field==='recount'?'复盘空白（不算已完成）':'待核实，合计仅含已知数字'):''}">${!c.numeric&&unknown?'待核实':esc(c.sum)}${unknown&&c.numeric?' *':''}</td>`}).join('')}<td class="totals-hint">已保存数字<br>合计不换算单位</td><td class="col-supplier"></td><td class="totals-hint">${t.columns.amount.missing?'* 有金额待核实，仅含已知金额':'差异金额合计（元）'}</td></tr>`).join('');
      q('.totals-note').textContent='数字合计仅供核对，不换算单位，不替代实盘或正式损耗计算。'+(Object.keys(S.drafts).length?'未保存输入尚未计入表尾，保存成功后自动更新。':'空白复盘不算已完成。');
    };
    S.jumpTable=edge=>{
      // 先渲染当前条件下的完整列表，不能停留在连续加载的200条末尾。
      if(edge==='end'){S.loaded=Math.max(S.filteredCount||0,S.order.length);S.render()}
      const generation=(S.jumpGeneration||0)+1;S.jumpGeneration=generation;
      const align=()=>{
        if(generation!==S.jumpGeneration||!root.isConnected)return;
        const scroller=S.scrollParent(),port=scroller===document.scrollingElement?{top:0,bottom:innerHeight}:scroller.getBoundingClientRect();
        const target=q(edge==='end'?'.table-tail':'.table-wrap'),box=target.getBoundingClientRect(),rail=document.querySelector('#stocktake-global-summary');
        const delta=edge==='end'?box.bottom-Math.min(innerHeight,port.bottom)+q('.selection-status').getBoundingClientRect().height+10:box.top-Math.max(port.top,rail?.getBoundingClientRect().bottom||104)-6;
        scroller.scrollTop+=delta;
      };
      // CCv2会根据内容重新测量高度；连续帧校准，避免跳到旧容器边界。
      requestAnimationFrame(()=>{align();requestAnimationFrame(()=>{align();requestAnimationFrame(align)})});
    };
    for(const selector of ['.jump-bottom','.jump-top'])q(selector).onpointerdown=e=>e.preventDefault();
    q('.jump-bottom').onclick=()=>S.jumpTable('end');q('.jump-top').onclick=()=>S.jumpTable('start');
    S.onTableKey=e=>{
      if(!root.isConnected||e.defaultPrevented||!e.ctrlKey||e.altKey||e.metaKey||!['End','Home'].includes(e.key))return;
      if(root.querySelector('dialog[open]')||e.composedPath().some(el=>el.matches?.('input,textarea,select,[contenteditable]:not([contenteditable="false"])')))return;
      e.preventDefault();S.jumpTable(e.key==='End'?'end':'start');
    };

    S.render=()=>{
      const pinEditing=!S.filterChanged;S.filterChanged=false;const d=S.data,stats=d.stats;const tbody=q('.table-wrap tbody'),scroller=S.scrollParent();const active=root.getRootNode().activeElement;const anchor=[...tbody.children].find(el=>el.getBoundingClientRect().bottom>90);const anchorTop=anchor?.getBoundingClientRect().top;const priorScroll=scroller.scrollTop;
      q('.regroup').textContent=S.sort==='pair'?'重新联排':'刷新排序';q('.regroup').title='按最新数据更新排列；保存时保留行位置，避免打断输入';
      const p=d.panel;
      for(const input of root.querySelectorAll('[data-meta]')){const value=S.metaDrafts[input.dataset.meta]?.value??d.finance[input.dataset.meta]??'';if(parentElement.activeElement!==input&&input.value!==String(value))input.value=String(value)}
      q('.calculation-status').className='calculation-status '+(p.status==='当前测算达标'?'green':p.status==='当前测算超标'?'red':'zero');q('.calculation-status').textContent=p.status;
      const metrics=[['整店盘盈（元）',p.gain,'green'],['整店盘亏（元）',p.loss,'red'],['净差异（元）',p.net,cls(Number(p.net))],['净差异率',p.rate===null?'待计算':p.rate+'‰',p.rate===null?'zero':''],['2‰允许损耗（元）',p.allowance,p.allowance===null?'zero':''],[p.over_limit?'超标金额（元）':'剩余额度（元）',p.remaining===null?null:fmt(Math.abs(Number(p.remaining)),2),p.remaining===null?'zero':p.over_limit?'red':'green'],['已填 / 剩余',p.done+' / '+p.remaining_rows,'']];
      q('.metrics').innerHTML=metrics.map(([label,value,color])=>`<div class="metric"><small>${esc(label)}</small><strong class="${color}">${esc(value??'待计算')}</strong></div>`).join('');
      q('.audit').textContent=p.note;
      S.renderReport();
      const message=q('.message');message.innerHTML=d.error?`<div class="error">${esc(d.error)}</div>`:S.restore?'<div class="notice">已保留上次未确认草稿。检查黄色输入框，按Enter或离开单元格保存；不会把空白当作0。</div>':'';
      q('.chips').innerHTML=d.filters.map(f=>`<button class="chip ${S.filters.includes(f)?'active':''}" data-filter="${esc(f)}">${esc(f)}</button>`).join('');
      q('.chips').querySelectorAll('button').forEach(b=>b.onclick=()=>{S.filters=S.filters.includes(b.dataset.filter)?S.filters.filter(f=>f!==b.dataset.filter):[...S.filters,b.dataset.filter];S.focus=null;S.filterChanged=true;remember();S.render()});
      let rows=filterRows([...S.rows.values()],S);
      S.filteredRows=rows;
      rows.sort((a,b)=>S.sort==='sequence'?a.sequence-b.sequence:S.sort==='amount'?Math.abs(b.amount||0)-Math.abs(a.amount||0)||a.sequence-b.sequence:S.sort==='quantity'?Math.abs(b.diff||0)-Math.abs(a.diff||0)||a.sequence-b.sequence:S.sort==='score'?b.score-a.score:a.category.localeCompare(b.category,'zh-CN')||a.sequence-b.sequence);
      const found=rows.length,key=JSON.stringify([S.query,S.filters,S.category,S.supplier,S.sort,S.scope,S.columns]);
      const matches=new Set(rows.map(r=>r.id));
      const reset=key!==S.orderKey;
      if(reset){S.orderKey=key;S.order=S.sort==='pair'?d.pair_order.filter(id=>matches.has(id)):rows.map(r=>r.id);S.loaded=rows.length<=2000?rows.length:200}
      else{const old=new Set(S.order);S.order=S.order.filter(id=>matches.has(id));S.order.push(...rows.filter(r=>!old.has(r.id)).map(r=>r.id))}
      let ids=[...S.order];
      // 条件变化不能在自动保存回执到达时移除正在输入的DOM；用户离开后再应用筛选。
      const editing=pinEditing&&active?.matches?.('.edit-count,.edit-note')?active.closest('tr'):null;
      if(editing&&S.rows.has(editing.dataset.id)&&!ids.includes(editing.dataset.id)){
        const oldAt=[...tbody.children].indexOf(editing);ids.splice(Math.min(Math.max(0,oldAt),ids.length),0,editing.dataset.id);
      }
      if(S.exportOpen&&S.exportAnchor&&S.rows.has(S.exportAnchor.id)&&!ids.includes(S.exportAnchor.id))ids.splice(Math.min(S.exportAnchor.index,ids.length),0,S.exportAnchor.id);
      if(S.focus&&S.rows.has(S.focus)&&!ids.includes(S.focus)){const at=S.locateFrom?ids.indexOf(S.locateFrom):-1;ids.splice(at>=0?at+1:0,0,S.focus)}
      if(S.focus){const at=ids.indexOf(S.focus);if(at>=S.loaded)S.loaded=at+1}
      S.filteredCount=ids.length;const visible=ids.slice(0,S.loaded).map(id=>S.rows.get(id));S.visible=visible;
      const positions=new Map(visible.map((r,i)=>[r.id,i]));
      const locate=q('.locate');if(/^\d{4,8}$/.test(S.query)&&rows.length>1){locate.classList.remove('hidden');locate.innerHTML='<option value="">尾号对应多个商品，请选择完整条码定位</option>'+rows.map(r=>`<option value="${esc(r.id)}">${esc(r.name+' / '+r.barcode)}</option>`).join('')}else locate.classList.add('hidden');
      const sums=rangeTotals(rows);const scopeNames={exclude:'不含卓不凡（待确认保留）',all:'全部商品',zbf:'仅卓不凡'};const conditions=[scopeNames[S.scope],S.query?'搜索:'+S.query:'',S.category?'品类:'+S.category:'',S.supplier?'供应商:'+S.supplier:'',...S.filters,...Object.entries(S.columns).filter(([,v])=>Object.keys(v).length).map(([k,v])=>columns[k]+':'+Object.entries(v).map(([a,b])=>({mode:'状态：',text:'包含：',min:'≥',max:'≤',value:'选择：'}[a]||a)+({loss:'盘亏',gain:'盘盈',zero:'归零',nonzero:'仍有差异',unreviewed:'未复盘',reviewed:'已复盘',missing:'缺成本／待核实',blank:'空白',filled:'已填写',yes:'有备注',no:'无备注',mix:'疑似串码',eligible:'允许A换B',swap:'有A换B线索',pending:'待确认'}[b]??b)).join('/'))].filter(Boolean);q('.result-count').textContent=`${conditions.join(' · ')}｜当前显示${found}条 / 全店${S.rows.size}条 · 筛选范围：盘盈${sums.gain}元　盘亏${sums.loss}元　净差异${sums.net}元${sums.missing?' · '+sums.missing+'条金额待核实':''}（仅找差异，整店统计不变）`;q('.category').value=S.category;q('.supplier').value=S.supplier;root.querySelectorAll('.header-filter').forEach(b=>b.classList.toggle('active',!!Object.keys(S.columns[b.dataset.column]||{}).length||(b.dataset.column==='category'&&!!S.category)||(b.dataset.column==='supplier'&&!!S.supplier)));
      q('.scroll-status').textContent=`已显示 ${visible.length} / ${ids.length} 条 · ${visible.length<ids.length?'继续向下自动加载':'可连续滚轮浏览，无需翻页'}`;
      q('.saved').textContent=S.inflight?'保存 / 载入中…':Object.keys(S.metaDrafts).length||Object.keys(S.drafts).length?'有未确认草稿':`已保存 · ${d.saved_at||d.imported_at} · 版本 ${d.revision}`;
      const keep=new Set(visible.map(r=>r.id));
      for(const tr of [...tbody.children])if(!keep.has(tr.dataset.id))tr.remove();
      for(let i=0;i<visible.length;i++){
        const r=visible[i];let tr=S.dom.get(r.id);
        if(!tr){tr=document.createElement('tr');tr.dataset.id=r.id;tr.innerHTML='<td class="seq num"></td><td class="category-cell"></td><td class="product"></td><td class="barcode"></td><td class="code col-code"></td><td class="system num" data-stat-field="system"></td><td class="initial num" data-stat-field="initial"></td><td data-stat-field="recount"><input class="edit-count" inputmode="decimal"></td><td class="total num" data-stat-field="total"></td><td class="difference num" data-stat-field="diff"></td><td class="amount num" data-stat-field="amount"></td><td class="note-cell"><div class="note-inline"><input class="edit-note" type="text"><button class="note-expand" title="展开编辑完整备注" aria-label="展开备注">↗</button></div></td><td class="supplier-cell col-supplier"></td><td class="hints"></td>';S.dom.set(r.id,tr);
          tr.querySelector('.note-expand').onclick=()=>S.openNote(r.id);tr.querySelector('.edit-note').ondblclick=()=>S.openNote(r.id);
          for(const [field,selector] of [['复盘实数','.edit-count'],['备注','.edit-note']]){
            const input=tr.querySelector(selector);input.dataset.field=field;input.setAttribute('aria-label',`${field} ${r.barcode}`);
            input.oninput=()=>S.editCell(r.id,field,input.value);
            input.onblur=()=>{S.commit(r.id,field);queueMicrotask(()=>{if(!root.getRootNode().activeElement?.closest?.('tr'))S.render()})};
            input.onfocus=()=>{const box=input.getBoundingClientRect(),head=q('.table-wrap thead').getBoundingClientRect();if(box.top<head.bottom)S.scrollParent().scrollTop+=box.top-head.bottom-6};
            input.onkeydown=e=>{if(e.key==='F2'&&field==='备注'){e.preventDefault();S.openNote(r.id)}if(e.key==='Enter'&&(field==='复盘实数'||!e.shiftKey)){e.preventDefault();S.commit(r.id,field);const idx=S.visible.findIndex(x=>x.id===r.id);const next=S.dom.get(S.visible[idx+1]?.id)?.querySelector(selector);if(next)next.focus()}};
          }
        }
        const paired=S.sort==='pair'&&r.partner&&Math.abs((positions.get(r.partner)??-999)-i)===1;
        tr.className=(r.id===S.focus?'selected ':'')+(paired?'paired '+(positions.get(r.partner)>i?'group-start':'group-end'):'');
        const signature=JSON.stringify([r.name,r.code,r.category,r.supplier,r.supplier_status,r.eligible,r.barcode,r.system,r.initial,r.total,r.initial_diff,r.diff,r.amount,r.change,r.change_label,r.peers,r.partner_peer,r.mix_count,r.swap_count,r.unit_hints,r.flags,r.cross,paired,r.partner]);
        if(S.rowSignatures.get(r.id)!==signature){
          S.rowSignatures.set(r.id,signature);tr.querySelector('.seq').textContent=r.sequence;
          tr.querySelector('.product').innerHTML=`<button class="row-link name">${esc(r.name)}</button>`;
          for(const [selector,value] of [['.category-cell',r.category],['.barcode',r.barcode],['.code',r.code],['.system',fmt(r.system)],['.initial',fmt(r.initial)],['.total',fmt(r.total)],['.supplier-cell',r.supplier]]){const cell=tr.querySelector(selector);cell.textContent=value;cell.title=String(value)}
          tr.querySelector('.row-link').onclick=()=>S.openDetail(r.id,null);
          const basis=`初盘差异 ${fmt(r.initial_diff)}；原始调整 ${fmt(r.adjustment)}；变化 ${fmt(r.change)}；${r.change_label}；差异成本 ${fmt(r.amount,2)}元。点击查看V13计算依据。`;
          tr.querySelector('.difference').innerHTML=`<button class="difference-details ${cls(r.diff)}" title="${esc(basis)}"><strong>${r.diff>0?'+':''}${esc(fmt(r.diff))}</strong><span class="change">${esc(shortChange(r))}</span></button>`;
          tr.querySelector('.difference-details').onclick=e=>e.preventDefault();tr.querySelector('.difference-details').ondblclick=()=>S.openCalculation(r.id);const money=tr.querySelector('.amount');money.className='amount num '+(r.amount===null?'missing-amount':cls(r.amount));money.textContent=r.amount===null?'缺成本／待核实':(r.amount>0?'+':'')+fmt(r.amount,2);money.title='复用V13 current_amount：最新差异×成本，逐商品两位小数';
          const hints=tr.querySelector('.hints');const peer=(paired?r.partner_peer:null)||r.peers?.[0];
          hints.innerHTML='<div class="hint-inline">'+(peer?`<button class="peer-live" data-other="${esc(peer.id)}" title="${esc(peer.name+' / '+peer.barcode+'；对方差异 '+fmt(peer.diff)+'；疑似待核实，点击定位')}">${peer.mix?'疑似串码':'可A换B'} ↔ ${esc(peer.name)}</button>`:'')+'</div>';
          const links=hints.querySelector('.hint-inline');
          if(peer)hints.querySelector('.peer-live').onclick=()=>S.locateTo(peer.id,r.id);
          const count=r.candidate_count;
          if(count>1){const more=document.createElement('button');more.className='more-peers';more.textContent=`另有${count-1}项`;more.onclick=()=>S.openDetail(r.id,null);links.appendChild(more)}
          const risks=[];if(r.supplier_status==='pending')risks.push('供货商待确认');if(r.cross?.length)risks.push(`跨店调拨线索${r.cross.length}项`);if(r.unit_hints.length)risks.push(`单位换算${r.unit_hints.length}项`);
          risks.push(...r.flags.filter(f=>['负库存','缺成本','零成本','缺编码','重复条码','缺文字原因','数据错误'].includes(f)));
          if(risks.length){const b=document.createElement('button');b.className='risk-summary';b.textContent=peer?'!':risks.join(' · ');b.title=risks.join('；');b.setAttribute('aria-label',risks.join('；'));b.onclick=()=>S.openDetail(r.id,null);links.appendChild(b)}
        }
        for(const [field,selector,value] of [['复盘实数','.edit-count',r.recount],['备注','.edit-note',r.note]]){const input=tr.querySelector(selector),draft=S.drafts[r.id]?.[field],next=draft?draft.value:(value??'');input.title=String(next);if(root.getRootNode().activeElement!==input&&input.value!==String(next))input.value=String(next)}
        if(tbody.children[i]!==tr){if(tbody.moveBefore&&tr.isConnected)tbody.moveBefore(tr,tbody.children[i]||null);else tbody.insertBefore(tr,tbody.children[i]||null)}
      }
      S.renderColumnTotals(rows);S.renderSelection();S.renderBalance();S.renderExport();
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
      if(!data.ack.ok){S.queue=S.queue.filter(p=>p.kind!=='copy_snapshot');S.restore=true;if(S.copyIntent)S.abortCopy('保存失败，未复制任何文稿；请核对输入后重试');if(S.exportIntent)S.abortExport('保存失败，未生成或下载文件；草稿保留，请核对后重试')}
      if(e.kind?.startsWith('balance_')){S.balanceRendered=null;if(data.ack.ok&&e.id)delete S.balanceDrafts[e.run+'|'+e.id]}
      if(data.ack.ok&&e.kind==='bulk')q('.bulk').classList.add('hidden');
      if(data.ack.ok&&e.kind==='refresh'){
        for(const [id,fields] of Object.entries(S.drafts))for(const [field,draft] of Object.entries(fields)){
          const row=S.rows.get(id);if(row)draft.base=field==='复盘实数'?row.recount:row.note;
        }
        for(const [key,draft] of Object.entries(S.metaDrafts))draft.base=S.metaValue(key);
        S.restore=Object.keys(S.drafts).length>0||Object.keys(S.metaDrafts).length>0;
      }
      S.inflight=null;S.remember();
      if(data.ack.ok&&['export_snapshot','export_checks'].includes(e.kind)&&S.exportIntent?.id===e.request_id){const intent=S.exportIntent;queueMicrotask(()=>S.finishExport(data.export_snapshot,intent))}
      if(data.ack.ok&&e.kind==='copy_snapshot'&&S.copyIntent?.id===e.request_id){const intent=S.copyIntent;queueMicrotask(()=>S.finishCopy(data.copy_snapshot,intent))}
      if(!Object.keys(S.drafts).length&&!Object.keys(S.metaDrafts).length)S.restore=false;
    }
  }
  S.render();S.remember();if(S.scope!==data.active_scope&&!S.inflight&&!S.queue.length)S.enqueue('scope',{scope:S.scope});S.pump();
  document.addEventListener('scroll',S.onScroll,true);document.addEventListener('pointerup',S.onPointerUp,true);document.addEventListener('keydown',S.onTableKey);S.observer.observe(q('.load-sentinel'));
  return ()=>{document.removeEventListener('scroll',S.onScroll,true);document.removeEventListener('pointerup',S.onPointerUp,true);document.removeEventListener('keydown',S.onTableKey);S.observer.disconnect()};
}

// 所有列条件只作用于可见集合；后端财务面板与正式导出始终接收整批原数据。
export function filterRows(rows,f){
  return rows.filter(r=>{
    if(f.scope==='exclude'&&r.supplier_status==='zbf'||f.scope==='zbf'&&r.supplier_status!=='zbf'||f.scope==='eligible'&&!r.eligible)return false;
    if(f.query&&![r.name,r.barcode,r.code].some(v=>String(v).toLowerCase().includes(f.query.toLowerCase())))return false;
    if(f.category&&r.category!==f.category||f.supplier&&r.supplier!==f.supplier||!(f.filters||[]).every(v=>r.flags.includes(v)))return false;
    for(const [key,c] of Object.entries(f.columns||{})){
      const v=r[key];
      if(c.text&&!String(v??'').toLowerCase().includes(c.text.toLowerCase()))return false;
      if(c.min!==undefined&&(v===null||v===undefined||v<c.min)||c.max!==undefined&&(v===null||v===undefined||v>c.max))return false;
      const m=c.mode;if(!m)continue;
      if(key==='diff'||key==='amount'){
        if(m==='loss'&&!(v<0)||m==='gain'&&!(v>0)||m==='zero'&&v!==0||m==='nonzero'&&(v===null||v===0)||m==='missing'&&v!==null||m==='unreviewed'&&r.recount!==null||m==='reviewed'&&r.recount===null)return false;
      }else if(key==='note'){
        const filled=!!String(r.note||'').trim();if(m==='yes'&&!filled||m==='no'&&filled)return false;
      }else if(key==='hints'){
        if(m==='mix'&&!r.mix_count||m==='eligible'&&!r.eligible||m==='swap'&&!r.swap_count||m==='pending'&&r.supplier_status!=='pending')return false;
      }else if(m==='blank'&&v!==null||m==='filled'&&v===null||m==='zero'&&v!==0)return false;
    }return true;
  });
}
