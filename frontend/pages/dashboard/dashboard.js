/* The dashboard screen: figures, deadline strip, charts.
   Moved verbatim from Bhumijo_Proposal_Tracker_22Jul2026.html — 11 function(s), not rewritten.
   Loaded in a fixed order by index.html, sharing one scope, exactly as before. */

function initReportMonth() {
  // report-month input removed; quick select handles date range now
}

// ─── NAVIGATION ───────────────────────────────────────────────────────────────
function applyDashboardLast30Days(){
  const end=new Date();
  const start=new Date(); start.setDate(end.getDate()-30);
  const fmt=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  document.getElementById('dash-filter-start-date').value=fmt(start);
  document.getElementById('dash-filter-end-date').value=fmt(end);
  renderDashboard();
}
function clearDashboardDateFilter(){
  document.getElementById('dash-filter-start-date').value='';
  document.getElementById('dash-filter-end-date').value='';
  renderDashboard();
}
function matchesStatusFilter(p, statusFilter){
  if(!statusFilter) return true;
  if(COMPOUND_STATUS_RESULT_MAP.hasOwnProperty(statusFilter)){
    return p.status==='Submitted' && p.result===COMPOUND_STATUS_RESULT_MAP[statusFilter];
  }
  return p.status===statusFilter;
}
function getDashboardFilteredData(){
  const entity=(document.getElementById('dash-filter-entity')||{}).value||'';
  const status=(document.getElementById('dash-filter-status')||{}).value||'';
  const result=(document.getElementById('dash-filter-result')||{}).value||'';
  const startVal=(document.getElementById('dash-filter-start-date')||{}).value||'';
  const endVal=(document.getElementById('dash-filter-end-date')||{}).value||'';
  const dateFrom=startVal?new Date(startVal+'T00:00:00'):null;
  const dateTo=endVal?new Date(endVal+'T23:59:59'):null;
  return proposals.filter(p=>{
    if(entity&&p.entity!==entity)return false;
    if(!matchesStatusFilter(p,status))return false;
    if(result&&p.result!==result)return false;
    if(dateFrom||dateTo){
      const dRaw=p.closeDate||p.createdAt||'';
      if(!dRaw)return false;
      const d=new Date(dRaw+'T00:00:00');
      if(dateFrom&&d<dateFrom)return false;
      if(dateTo&&d>dateTo)return false;
    }
    return true;
  });
}
function renderDashboard() { const data=getDashboardFilteredData(); renderStats(data); renderDeadlineStrip(data); renderCharts(data); renderRecentTable(data); }

function renderStats(data) {
  data = data || proposals;
  const total    = data.length;
  const pipeline = data.filter(p=>['Yet to be submitted','Hold'].includes(p.status)).length;
  const submitted= data.filter(p=>p.status==='Submitted').length;
  const waiting  = data.filter(p=>p.result==='Waiting for Result').length;
  const won      = data.filter(p=>p.result==='Accepted').length;
  const lost     = data.filter(p=>p.result==='Rejected').length;
  const dropped  = data.filter(p=>p.status==='Drop').length;
  const unable   = data.filter(p=>p.status==='Unable to submit').length;
  const decided  = won+lost;
  const winRate  = decided>0?Math.round(won/decided*100):0;
  document.getElementById('stat-grid').innerHTML = `
    <div class="stat-card"><div class="stat-label">Total Proposals</div><div class="stat-value">${total}</div><div class="stat-sub">All time · all entities</div></div>
    <div class="stat-card accent-blue"><div class="stat-label">Active Pipeline</div><div class="stat-value">${pipeline}</div><div class="stat-sub">Yet to submit + Hold</div></div>
    <div class="stat-card accent-amber"><div class="stat-label">Submitted and Waiting for Result</div><div class="stat-value">${waiting}</div><div class="stat-sub">Of ${submitted} submitted</div></div>
    <div class="stat-card accent-green"><div class="stat-label">Submitted and Won</div><div class="stat-value">${won}</div><div class="stat-sub">Accepted · ${winRate}% win rate</div></div>
    <div class="stat-card accent-red"><div class="stat-label">Submitted and Lost</div><div class="stat-value">${lost}</div><div class="stat-sub">Of ${decided} decided</div></div>
    <div class="stat-card accent-purple"><div class="stat-label">Drop</div><div class="stat-value">${dropped}</div><div class="stat-sub">Dropped proposals</div></div>
    <div class="stat-card"><div class="stat-label">Unable to Submit</div><div class="stat-value">${unable}</div><div class="stat-sub">Could not be submitted</div></div>
  `;
}

function renderDeadlineStrip(data) {
  data = data || proposals;
  const today = new Date(); today.setHours(0,0,0,0);
  const in15  = new Date(today); in15.setDate(today.getDate()+15);
  const in30  = new Date(today); in30.setDate(today.getDate()+30);
  const pendingS = ['Yet to be submitted','Hold'];

  // Urgent: next 15 days
  const urgent = data.filter(p=>{
    if(!p.closeDate) return false;
    const d = new Date(p.closeDate+'T00:00:00');
    return d>=today && d<=in15 && pendingS.includes(p.status);
  }).sort((a,b)=>new Date(a.closeDate)-new Date(b.closeDate));

  // Soon: 15–30 days
  const soon = data.filter(p=>{
    if(!p.closeDate) return false;
    const d = new Date(p.closeDate+'T00:00:00');
    return d>in15 && d<=in30 && pendingS.includes(p.status);
  }).sort((a,b)=>new Date(a.closeDate)-new Date(b.closeDate));

  const strip = document.getElementById('deadline-strip');
  if(!urgent.length && !soon.length){ strip.style.display='none'; return; }
  strip.style.display = 'block';

  let html = '';

  if(urgent.length) {
    html += `<div class="deadline-strip-header" style="color:var(--red)">
      🔴 ${urgent.length} deadline${urgent.length>1?'s':''} in next 15 days
    </div>
    <div class="deadline-items" style="margin-bottom:${soon.length?'10px':'0'}">
      ${urgent.map(p=>{
        const d=new Date(p.closeDate+'T00:00:00');
        const diff=Math.ceil((d-today)/86400000);
        const urg=diff<=3;
        return `<span class="deadline-pill${urg?' urgent':''}" title="${p.entity} · ${p.responsible||'–'}">
          ${p.title.substring(0,36)}… · <strong>${diff===0?'Today!':diff+' day'+(diff===1?'':'s')}</strong> (${p.entity})
        </span>`;
      }).join('')}
    </div>`;
  }

  if(soon.length) {
    html += `<div class="deadline-strip-header" style="color:var(--amber);margin-top:${urgent.length?'4px':'0'}">
      🟡 ${soon.length} deadline${soon.length>1?'s':''} in next 15–30 days
    </div>
    <div class="deadline-items">
      ${soon.map(p=>{
        const d=new Date(p.closeDate+'T00:00:00');
        const diff=Math.ceil((d-today)/86400000);
        return `<span class="deadline-pill" style="background:rgba(224,144,10,0.07);border-color:rgba(224,144,10,0.22);color:var(--amber)" title="${p.entity} · ${p.responsible||'–'}">
          ${p.title.substring(0,36)}… · <strong>${diff} days</strong> (${p.entity})
        </span>`;
      }).join('')}
    </div>`;
  }

  strip.innerHTML = html;
}

function renderRecentTable(data) {
  data = data || proposals;
  const recent=[...data].filter(p=>p.closeDate).sort((a,b)=>b.closeDate.localeCompare(a.closeDate)).slice(0,10);
  const tbody=document.getElementById('recent-tbody');
  if(!recent.length){tbody.innerHTML='<tr><td colspan="6" class="no-data-msg">No proposals yet</td></tr>';return;}
  tbody.innerHTML=recent.map(p=>`
    <tr onclick="openDrawer('${p.id}')">
      <td class="td-title">
        <span class="td-title-text">${esc(p.title)}</span>
        <div class="td-meta">${esc(p.client||'–')}</div>
        ${p.value?`<div class="td-value">Value: ${esc(p.value)}</div>`:''}
      </td>
      <td><span class="entity-badge entity-${p.entity.replace('&','')}">${p.entity}</span></td>
      <td>${stageBadge(p.category)}</td>
      <td>${daysBadge(p.closeDate)}</td>
      <td style="font-size:12px;color:var(--text2);white-space:nowrap">${fmtDate(p.closeDate)}</td>
      <td>${statusBadge(p.status)}</td>
    </tr>`).join('');
}

// ─── PROPOSALS TABLE ──────────────────────────────────────────────────────────
function renderCharts(data) {
  data = data || proposals;
  Object.values(charts).forEach(c=>{try{c.destroy()}catch(e){}});
  charts={};
  const CD={plugins:{legend:{labels:{color:'#5a6080',font:{size:11}}}},scales:{}};
  const rColors={'Accepted':'#1faa65','Rejected':'#e04545','Waiting for Result':'#e0900a','No Result Yet':'#9299b0'};
  const entities=['P&D','FM','WASH','Tech'];
  const eBg=['rgba(59,127,245,0.7)','rgba(24,176,160,0.7)','rgba(124,82,232,0.7)','rgba(224,144,10,0.7)'];
  const eBorder=['#3b7ff5','#18b0a0','#7c52e8','#e0900a'];
  const eNames=['Planning & Design','Facility Mgmt','WASH / Toilets','Technology'];

  // ① Entity % Donut (replaces Status Breakdown)
  const eCounts = entities.map(e => data.filter(p=>p.entity===e).length);
  const total = data.length;
  const eLabels = eNames.map((n,i) => `${n} (${total>0?Math.round(eCounts[i]/total*100):0}%)`);
  const ctxPct = document.getElementById('chart-entity-pct');
  if(ctxPct) {
    charts.entityPct = new Chart(ctxPct.getContext('2d'),{
      type:'doughnut',
      data:{labels:eLabels, datasets:[{data:eCounts, backgroundColor:eBg, borderColor:eBorder, borderWidth:2}]},
      options:{
        ...CD,
        cutout:'60%',
        plugins:{
          legend:{position:'right',labels:{color:'#5a6080',font:{size:11},boxWidth:12,padding:8}},
          tooltip:{callbacks:{label:ctx=>{const pct=total>0?Math.round(ctx.parsed/total*100):0;return ` ${ctx.parsed} proposals (${pct}%)`;}}}
        }
      }
    });
  }

  // ② Win Rate by Entity
  const wr=entities.map(e=>{const w=data.filter(p=>p.entity===e&&p.result==='Accepted').length,l=data.filter(p=>p.entity===e&&p.result==='Rejected').length;return w+l>0?Math.round(w/(w+l)*100):0;});
  charts.entityWin=new Chart(document.getElementById('chart-entity-win').getContext('2d'),{type:'bar',data:{labels:entities,datasets:[{label:'Win Rate %',data:wr,backgroundColor:eBg,borderColor:eBorder,borderWidth:1,borderRadius:5}]},options:{...CD,plugins:{legend:{display:false}},scales:{y:{ticks:{color:'#5a6080',callback:v=>v+'%'},grid:{color:'#e8eaf0'},max:100},x:{ticks:{color:'#5a6080'},grid:{display:false}}}}});

  // ③ Submissions Over Time
  const monthly={};const now=new Date();
  for(let i=17;i>=0;i--){const d=new Date(now.getFullYear(),now.getMonth()-i,1);monthly[d.toISOString().substring(0,7)]={s:0,a:0};}
  data.forEach(p=>{if(!p.closeDate)return;const k=p.closeDate.substring(0,7);if(monthly[k]){monthly[k].s++;if(p.result==='Accepted')monthly[k].a++;}});
  const mL=Object.keys(monthly).map(k=>{const[y,m]=k.split('-');return['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][parseInt(m)-1]+' '+y.slice(2);});
  charts.timeline=new Chart(document.getElementById('chart-timeline').getContext('2d'),{type:'line',data:{labels:mL,datasets:[{label:'Submitted',data:Object.values(monthly).map(v=>v.s),borderColor:'#3b7ff5',backgroundColor:'rgba(59,127,245,0.08)',tension:0.4,fill:true,pointRadius:3},{label:'Won',data:Object.values(monthly).map(v=>v.a),borderColor:'#1faa65',backgroundColor:'rgba(31,170,101,0.08)',tension:0.4,fill:true,pointRadius:3}]},options:{...CD,scales:{y:{ticks:{color:'#5a6080'},grid:{color:'#e8eaf0'}},x:{ticks:{color:'#5a6080',maxTicksLimit:9},grid:{display:false}}}}});

  // ④ Outcome Distribution
  const rc={};data.forEach(p=>{const r=p.result||'No Result Yet';rc[r]=(rc[r]||0)+1;});
  charts.outcome=new Chart(document.getElementById('chart-outcome').getContext('2d'),{type:'pie',data:{labels:Object.keys(rc),datasets:[{data:Object.values(rc),backgroundColor:Object.keys(rc).map(k=>rColors[k]||'#9299b0'),borderWidth:0}]},options:{...CD}});

  // ⑤ Proposals by Entity (bar)
  charts.byEntity=new Chart(document.getElementById('chart-by-entity').getContext('2d'),{type:'bar',data:{labels:entities,datasets:[{label:'Total',data:eCounts,backgroundColor:eBg,borderColor:eBorder,borderWidth:1,borderRadius:5}]},options:{...CD,plugins:{legend:{display:false}},scales:{y:{ticks:{color:'#5a6080'},grid:{color:'#e8eaf0'}},x:{ticks:{color:'#5a6080'},grid:{display:false}}}}});

  // ⑥ Active Pipeline
  const ap={};entities.forEach(e=>{ap[e]=data.filter(p=>p.entity===e&&['Yet to be submitted','Hold'].includes(p.status)).length;});
  charts.pipeline=new Chart(document.getElementById('chart-pipeline').getContext('2d'),{type:'bar',data:{labels:entities,datasets:[{label:'Active',data:entities.map(e=>ap[e]),backgroundColor:eBg,borderColor:eBorder,borderWidth:1,borderRadius:5}]},options:{...CD,plugins:{legend:{display:false}},scales:{y:{ticks:{color:'#5a6080'},grid:{color:'#e8eaf0'}},x:{ticks:{color:'#5a6080'},grid:{display:false}}}}});
}

// ─── ENTITY SUMMARY STRIP ─────────────────────────────────────────────────────
function renderEntitySummaryStrip(entity) {
  const strip = document.getElementById('entity-summary-strip');
  if(!strip) return;
  if(!entity) { strip.style.display='none'; return; }

  const today = new Date(); today.setHours(0,0,0,0);
  const in7   = new Date(today); in7.setDate(today.getDate()+7);
  const in15  = new Date(today); in15.setDate(today.getDate()+15);
  const pendingStatuses = ['Yet to be submitted','Hold'];

  const ep = proposals.filter(p => p.entity === entity);
  const nameMap = {'P&D':'Planning & Design','FM':'Facility Management','WASH':'WASH / Toilets','Tech':'Technology'};
  const colorMap = {'P&D':'var(--pd)','FM':'var(--fm)','WASH':'var(--wash)','Tech':'var(--tech)'};

  const total     = ep.length;
  const hold      = ep.filter(p=>p.status==='Hold').length;
  const yet       = ep.filter(p=>p.status==='Yet to be submitted').length;
  const submitted = ep.filter(p=>p.status==='Submitted').length;
  const waiting   = ep.filter(p=>p.result==='Waiting for Result').length;
  const accepted  = ep.filter(p=>p.result==='Accepted').length;
  const rejected  = ep.filter(p=>p.result==='Rejected').length;
  const unable    = ep.filter(p=>p.status==='Unable to submit').length;
  const drop      = ep.filter(p=>p.status==='Drop').length;

  const dead7  = ep.filter(p=>{
    if(!p.closeDate || !pendingStatuses.includes(p.status)) return false;
    const d=new Date(p.closeDate+'T00:00:00'); return d>=today && d<=in7;
  }).length;
  const dead15 = ep.filter(p=>{
    if(!p.closeDate || !pendingStatuses.includes(p.status)) return false;
    const d=new Date(p.closeDate+'T00:00:00'); return d>=today && d<=in15;
  }).length;

  // Set entity label color
  const lbl = document.getElementById('ess-entity-label');
  if(lbl){ lbl.textContent = nameMap[entity]||entity; lbl.style.color = colorMap[entity]||'var(--accent)'; }

  // Set left border color on strip
  strip.style.borderLeftColor = colorMap[entity]||'var(--accent)';

  document.getElementById('ess-dead7').textContent    = dead7;
  document.getElementById('ess-dead15').textContent   = dead15;
  document.getElementById('ess-total').textContent    = total;
  document.getElementById('ess-hold').textContent     = hold;
  document.getElementById('ess-yet').textContent      = yet;
  document.getElementById('ess-submitted').textContent= submitted;
  document.getElementById('ess-waiting').textContent  = waiting;
  document.getElementById('ess-accepted').textContent = accepted;
  document.getElementById('ess-rejected').textContent = rejected;
  document.getElementById('ess-unable').textContent   = unable;
  document.getElementById('ess-drop').textContent     = drop;

  strip.style.display = 'block';
}

// filterByEntity updated inline above
// clearEntityFilter updated inline above

// ─── REPORT: Quick Select + Date Range ────────────────────────────────────────
let activeQS = 'alltime';
