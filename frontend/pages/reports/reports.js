/* The reports screen: period selection, narrative, exports.
   Moved verbatim from Bhumijo_Proposal_Tracker_22Jul2026.html — 11 function(s), not rewritten.
   Loaded in a fixed order by index.html, sharing one scope, exactly as before. */

function buildTreeDiagram(total, submitted, pipeline, dropped, won, lost, waiting, winRate, arcOffset, CIRC, decided) {
  const pctOf = (n) => total > 0 ? Math.round(n/total*100)+'%' : '0%';
  const pctOfSub = (n) => submitted > 0 ? Math.round(n/submitted*100)+'%' : '0%';

  return `
  <div class="tree-section">
    <div class="tree-section-header">
      <div>
        <div class="tree-section-title">Pipeline Funnel · Left → Right</div>
        <div class="tree-section-sub">How proposals flow from intake to outcome</div>
      </div>
    </div>
    <div class="tree-body" id="tree-body">

      <!-- SVG CONNECTOR LAYER (drawn by JS after render) -->
      <svg class="tree-svg-layer" id="tree-svg" xmlns="http://www.w3.org/2000/svg"></svg>

      <!-- NODE LAYOUT: 4 columns using flexbox rows -->
      <div style="display:flex;align-items:center;gap:0;min-width:680px;position:relative;z-index:1;">

        <!-- COL 1: ROOT -->
        <div style="flex-shrink:0;display:flex;align-items:center;justify-content:center;width:172px">
          <div class="tnode tnode-root" id="tnode-root">
            <div class="tnode-count">${total}</div>
            <div class="tnode-label">Total Proposals</div>
            <div class="tnode-sub">This period · All entities</div>
          </div>
        </div>

        <!-- COL 2: L1 branches -->
        <div style="flex:0 0 172px;display:flex;flex-direction:column;gap:14px;padding:0 20px;align-items:center">
          <div class="tnode tnode-submitted" id="tnode-submitted">
            <div class="tnode-count">${submitted}</div>
            <div class="tnode-label">Submitted</div>
            <div class="tnode-sub">${pctOf(submitted)} of total</div>
          </div>
          <div class="tnode tnode-pipeline" id="tnode-pipeline">
            <div class="tnode-count">${pipeline}</div>
            <div class="tnode-label">Pipeline</div>
            <div class="tnode-sub">Yet to submit · Hold</div>
          </div>
          <div class="tnode tnode-dropped" id="tnode-dropped">
            <div class="tnode-count">${dropped}</div>
            <div class="tnode-label">Dropped</div>
            <div class="tnode-sub">Drop · Unable to submit</div>
          </div>
        </div>

        <!-- COL 3: L2 outcomes (from Submitted) -->
        <div style="flex:0 0 180px;display:flex;flex-direction:column;gap:14px;padding:0 20px;align-items:center">
          <div class="tnode tnode-won" id="tnode-won">
            <div class="tnode-count">${won}</div>
            <div class="tnode-label">Accepted / Won</div>
            <div class="tnode-sub">${pctOfSub(won)} of submitted</div>
            <div class="tnode-pill">✓ ${winRate}% success rate</div>
          </div>
          <div class="tnode tnode-rejected" id="tnode-rejected">
            <div class="tnode-count">${lost}</div>
            <div class="tnode-label">Rejected</div>
            <div class="tnode-sub">${pctOfSub(lost)} of submitted</div>
          </div>
          <div class="tnode tnode-waiting" id="tnode-waiting">
            <div class="tnode-count">${waiting}</div>
            <div class="tnode-label">Waiting for Result</div>
            <div class="tnode-sub">${pctOfSub(waiting)} of submitted</div>
          </div>
        </div>

        <!-- COL 4: Win Rate callout -->
        <div style="flex:0 0 160px;display:flex;align-items:center;justify-content:center;padding-left:16px">
          <div class="win-rate-callout" id="tnode-winrate">
            <svg width="52" height="52" viewBox="0 0 52 52">
              <circle cx="26" cy="26" r="22" fill="none" stroke="rgba(52,199,123,0.15)" stroke-width="5"/>
              <circle cx="26" cy="26" r="22" fill="none" stroke="#34c77b" stroke-width="5"
                stroke-dasharray="${CIRC}" stroke-dashoffset="${arcOffset}"
                stroke-linecap="round" transform="rotate(-90 26 26)"
                style="transition:stroke-dashoffset 1s ease 0.4s"/>
            </svg>
            <div class="win-rate-rate">${winRate}%</div>
            <div class="win-rate-lbl">Win Rate</div>
            <div class="win-rate-sub">${won} won of<br>${decided > 0 ? won+lost : '–'} decided</div>
          </div>
        </div>

      </div><!-- /flex row -->

      <!-- SUMMARY STRIP -->
      <div class="tree-summary" style="margin-top:28px">
        <div class="tree-strip-card">
          <div class="tree-strip-dot" style="background:#6c8cff"></div>
          <div>
            <div class="tree-strip-val" style="color:#6c8cff">${total}</div>
            <div class="tree-strip-lbl">Total tracked</div>
          </div>
        </div>
        <div class="tree-strip-card">
          <div class="tree-strip-dot" style="background:var(--accent)"></div>
          <div>
            <div class="tree-strip-val" style="color:var(--accent)">${submitted}</div>
            <div class="tree-strip-lbl">Submitted</div>
          </div>
        </div>
        <div class="tree-strip-card">
          <div class="tree-strip-dot" style="background:var(--green)"></div>
          <div>
            <div class="tree-strip-val" style="color:var(--green)">${winRate}%</div>
            <div class="tree-strip-lbl">Win rate · ${won} won</div>
          </div>
        </div>
        <div class="tree-strip-card">
          <div class="tree-strip-dot" style="background:var(--amber)"></div>
          <div>
            <div class="tree-strip-val" style="color:var(--amber)">${waiting}</div>
            <div class="tree-strip-lbl">Awaiting result</div>
          </div>
        </div>
      </div>

    </div><!-- /tree-body -->
  </div><!-- /tree-section -->
  `;
}

// ─── SVG CONNECTOR DRAWER ─────────────────────────────────────────────────────
function drawTreeConnectors() {
  const svg = document.getElementById('tree-svg');
  if(!svg) return;
  const body = document.getElementById('tree-body');
  if(!body) return;

  svg.innerHTML = '';

  // Get bounding rects relative to tree-body
  function rel(el) {
    if(!el) return null;
    const er = el.getBoundingClientRect();
    const br = body.getBoundingClientRect();
    return {
      left:   er.left   - br.left,
      top:    er.top    - br.top,
      right:  er.right  - br.left,
      bottom: er.bottom - br.top,
      cx:     er.left   - br.left + er.width/2,
      cy:     er.top    - br.top  + er.height/2,
    };
  }

  const root      = rel(document.getElementById('tnode-root'));
  const submitted = rel(document.getElementById('tnode-submitted'));
  const pipeline  = rel(document.getElementById('tnode-pipeline'));
  const dropped   = rel(document.getElementById('tnode-dropped'));
  const won       = rel(document.getElementById('tnode-won'));
  const rejected  = rel(document.getElementById('tnode-rejected'));
  const waiting   = rel(document.getElementById('tnode-waiting'));
  const winrate   = rel(document.getElementById('tnode-winrate'));

  if(!root || !submitted) return;

  svg.setAttribute('width', body.offsetWidth);
  svg.setAttribute('height', body.offsetHeight);

  function bezier(x1,y1,x2,y2,color,opacity,dash) {
    const mx = (x1+x2)/2;
    const path = document.createElementNS('http://www.w3.org/2000/svg','path');
    path.setAttribute('d',`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`);
    path.setAttribute('fill','none');
    path.setAttribute('stroke',color);
    path.setAttribute('stroke-width','1.5');
    path.setAttribute('stroke-linecap','round');
    path.setAttribute('opacity', opacity||'0.5');
    if(dash) path.setAttribute('stroke-dasharray',dash);
    svg.appendChild(path);

    // Animate draw
    const len = path.getTotalLength ? path.getTotalLength() : 200;
    path.style.strokeDasharray = len;
    path.style.strokeDashoffset = len;
    path.style.transition = 'stroke-dashoffset 0.5s ease';
    requestAnimationFrame(()=>{ path.style.strokeDashoffset='0'; });
    return path;
  }

  // Root → L1 nodes (right edge of root → left edge of each L1)
  bezier(root.right,      root.cy,       submitted.left, submitted.cy, '#6c8cff', '0.55');
  bezier(root.right,      root.cy,       pipeline.left,  pipeline.cy,  '#f5a623', '0.45');
  bezier(root.right,      root.cy,       dropped.left,   dropped.cy,   '#5d6480', '0.35', '5,4');

  // Submitted → L2 nodes
  if(won)      bezier(submitted.right, submitted.cy, won.left,      won.cy,      '#34c77b', '0.55');
  if(rejected) bezier(submitted.right, submitted.cy, rejected.left, rejected.cy, '#f05a5a', '0.50');
  if(waiting)  bezier(submitted.right, submitted.cy, waiting.left,  waiting.cy,  '#f5a623', '0.50');

  // Won → Win-rate callout
  if(won && winrate) bezier(won.right, won.cy, winrate.left, winrate.cy, '#34c77b', '0.40', '4,3');
}

function buildStatusSummary(data) {
  const statuses = ['Submitted','Yet to be submitted','Hold','Drop','Unable to submit'];
  const labels = {'Submitted':'Submitted','Yet to be submitted':'Yet to Submit','Hold':'On Hold','Drop':'Dropped','Unable to submit':'Unable to Submit'};
  let html = '';
  statuses.forEach(s => {
    const count = data.filter(p=>p.status===s).length;
    if(!count) return;
    html += `<div class="mini-bar-wrap"><div class="mini-bar-label"><span class="lbl">${labels[s]||s}</span><span class="val">${count}</span></div><div class="mini-bar-track"><div class="mini-bar-fill" style="width:${data.length?Math.round(count/data.length*100):0}%;background:var(--accent)"></div></div></div>`;
  });
  return html || '<div class="no-data-msg">No data for this period</div>';
}

function buildNarrative({period,periodLabel,entityScope,total,submitted,won,lost,waiting,winRate,active,byEntity,dateFrom,dateTo,data}) {
  const periodName = {biweekly:'two-week',monthly:'month',yearly:'year'}[period]||'period';
  const top  = Object.entries(byEntity).sort((a,b)=>b[1].total-a[1].total)[0];
  const best = Object.entries(byEntity).filter(([,v])=>v.wr>0).sort((a,b)=>b[1].wr-a[1].wr)[0];

  let n = `<strong>Summary for ${periodLabel}</strong>\n\n`;
  if(!total) { n += 'No proposals found in this period. Consider broadening the date range or checking the entity filter.'; return n; }
  n += `Bhumijo tracked <strong>${total}</strong> proposal${total>1?'s':''} across ${entityScope} during this ${periodName}. `;
  if(submitted) n += `<strong>${submitted}</strong> ${submitted===1?'was':'were'} submitted for evaluation. `;
  if(won)  n += `The team secured <strong>${won}</strong> win${won>1?'s':''}, `;
  if(lost) n += `with <strong>${lost}</strong> rejection${lost>1?'s':''}${won?',':(waiting?' and':'')} `;
  if(waiting) n += `and <strong>${waiting}</strong> result${waiting>1?'s':''} still pending. `;
  n += '\n\n';
  if(won+lost>0) n += `<strong>Overall win rate: ${winRate}%</strong>. `;
  if(best) n += `Best-performing entity: <strong>${best[0]}</strong> at <strong>${best[1].wr}%</strong> win rate (${best[1].won} won of ${best[1].won+best[1].lost} decided). `;
  if(top && top[1].total>1) n += `Most active: <strong>${top[0]}</strong> with <strong>${top[1].total}</strong> proposals. `;
  n += '\n\n';
  if(active) n += `<strong>${active}</strong> proposal${active>1?'s remain':' remains'} in the pipeline awaiting action. `;
  const urgent = data.filter(p=>p.closeDate&&Math.ceil((new Date(p.closeDate)-new Date())/86400000)>=0&&Math.ceil((new Date(p.closeDate)-new Date())/86400000)<=7&&p.status==='Yet to be submitted');
  if(urgent.length) n += `⚠ <strong>${urgent.length}</strong> proposal${urgent.length>1?'s have':'has'} a deadline within the next 7 days and still need${urgent.length===1?'s':''} submission.`;
  return n;
}


function printReport() {
  // Make sure we're on the reports page and content is generated
  if(!document.getElementById('page-reports').classList.contains('active')) {
    showPage('reports');
  }
  // Give SVG connectors time to redraw after any page switch, then print
  setTimeout(() => { window.print(); }, 120);
}

function quickSelect(period) {
  activeQS = period;
  // Update button styles
  ['biweekly','monthly','quarterly','yearly','alltime'].forEach(p=>{
    const btn=document.getElementById('qs-'+p);
    if(!btn) return;
    if(p===period){btn.classList.add('active-qs','btn-primary');btn.classList.remove('btn-ghost');}
    else{btn.classList.remove('active-qs','btn-primary');btn.classList.add('btn-ghost');}
  });
  const now = new Date();
  let start, end;
  if(period==='biweekly'){
    end=new Date(); start=new Date(); start.setDate(end.getDate()-14);
  } else if(period==='monthly'){
    start=new Date(now.getFullYear(),now.getMonth(),1);
    end=new Date(now.getFullYear(),now.getMonth()+1,0);
  } else if(period==='quarterly'){
    const q=Math.floor(now.getMonth()/3);
    start=new Date(now.getFullYear(),q*3,1);
    end=new Date(now.getFullYear(),q*3+3,0);
  } else if(period==='yearly'){
    start=new Date(now.getFullYear(),0,1);
    end=new Date(now.getFullYear(),11,31);
  } else { // alltime
    start=null; end=null;
  }
  const fmt=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  document.getElementById('report-start-date').value = start ? fmt(start) : '';
  document.getElementById('report-end-date').value   = end   ? fmt(end)   : '';
  generateReport();
}

function onDateRangeChange() {
  // Clear QS active state when manually typing dates
  activeQS = null;
  ['biweekly','monthly','quarterly','yearly','alltime'].forEach(p=>{
    const btn=document.getElementById('qs-'+p);
    if(btn){btn.classList.remove('active-qs','btn-primary');btn.classList.add('btn-ghost');}
  });
  generateReport();
}

// Override generateReport to use date range
function generateReport() {
  const entity   = document.getElementById('report-entity').value;
  const startVal = (document.getElementById('report-start-date')||{}).value||'';
  const endVal   = (document.getElementById('report-end-date')||{}).value||'';

  let dateFrom=null, dateTo=null;
  if(startVal) { dateFrom=new Date(startVal+'T00:00:00'); }
  if(endVal)   { dateTo=new Date(endVal+'T23:59:59'); }

  // Determine period label
  let periodLabel='All Time Report';
  if(activeQS==='biweekly') periodLabel='Bi-Weekly Report';
  else if(activeQS==='monthly') {
    const now=new Date(); periodLabel='Monthly Report · '+now.toLocaleDateString('en-GB',{month:'long',year:'numeric'});
  } else if(activeQS==='quarterly') {
    const now=new Date(); const q=Math.floor(now.getMonth()/3)+1; periodLabel=`Q${q} ${now.getFullYear()} Report`;
  } else if(activeQS==='yearly') {
    periodLabel='Yearly Report · '+(new Date().getFullYear());
  } else if(startVal&&endVal) {
    periodLabel=`Report · ${fmtDate(startVal)} → ${fmtDate(endVal)}`;
  } else if(startVal) {
    periodLabel=`Report from ${fmtDate(startVal)}`;
  }

  let data = proposals.filter(p => {
    if(entity && p.entity!==entity) return false;
    if(!dateFrom && !dateTo) return true; // all time
    const d = p.closeDate ? new Date(p.closeDate+'T00:00:00') : (p.createdAt ? new Date(p.createdAt+'T00:00:00') : null);
    if(!d) return true; // include no-date entries in all-time
    if(dateFrom && d < dateFrom) return false;
    if(dateTo   && d > dateTo)   return false;
    return true;
  });

  const total    = data.length;
  const submitted= data.filter(p=>p.status==='Submitted').length;
  const won      = data.filter(p=>p.result==='Accepted').length;
  const lost     = data.filter(p=>p.result==='Rejected').length;
  const waiting  = data.filter(p=>p.result==='Waiting for Result').length;
  const decided  = won+lost;
  const winRate  = decided>0 ? Math.round(won/decided*100) : 0;
  const pipeline = data.filter(p=>['Yet to be submitted','Hold'].includes(p.status)).length;
  const dropped  = data.filter(p=>['Drop','Unable to submit'].includes(p.status)).length;

  const byEntity={};
  ['P&D','FM','WASH','Tech'].forEach(e=>{
    const ep=data.filter(p=>p.entity===e);
    const ew=ep.filter(p=>p.result==='Accepted').length;
    const el=ep.filter(p=>p.result==='Rejected').length;
    byEntity[e]={total:ep.length,won:ew,lost:el,wr:(ew+el)>0?Math.round(ew/(ew+el)*100):0};
  });

  const entityScope=entity||'all entities';
  const narrative=buildNarrative({period:activeQS||'custom',periodLabel,entityScope,total,submitted,won,lost,waiting,winRate,active:pipeline,byEntity,dateFrom,dateTo,data});
  const CIRC=138.2; const arcOffset=CIRC-(winRate/100)*CIRC;
  const rangeStr = dateFrom&&dateTo ? `${fmtDate(dateFrom.toISOString().substring(0,10))} → ${fmtDate(dateTo.toISOString().substring(0,10))}` : (dateFrom?`From ${fmtDate(dateFrom.toISOString().substring(0,10))}`: 'All Time');

  const output=document.getElementById('report-output');
  output.innerHTML=`
    <div class="report-block">
      <div class="report-block-header">
        <div>
          <div class="report-block-title">${periodLabel}</div>
          <div style="font-size:12px;color:var(--text3);margin-top:2px">${rangeStr} · ${entity||'All Entities'}</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <button class="btn btn-ghost" onclick="printReport()">🖨 Print</button>
          <button class="btn btn-ghost" onclick="downloadReportPDF()">↓ PDF</button>
          <button class="btn btn-primary" onclick="downloadReportDOC()">↓ DOC</button>
        </div>
      </div>
      <div class="report-body">
        <div class="report-metrics" style="grid-template-columns:repeat(5,1fr)">
          <div class="report-metric"><div class="report-metric-val" style="color:var(--accent)">${total}</div><div class="report-metric-lbl">Total Proposals</div></div>
          <div class="report-metric"><div class="report-metric-val" style="color:#7ab0f7">${submitted}</div><div class="report-metric-lbl">Submitted</div></div>
          <div class="report-metric"><div class="report-metric-val" style="color:var(--amber)">${waiting}</div><div class="report-metric-lbl">Waiting Result</div></div>
          <div class="report-metric"><div class="report-metric-val" style="color:var(--green)">${won}</div><div class="report-metric-lbl">Won · ${winRate}% rate</div></div>
          <div class="report-metric"><div class="report-metric-val" style="color:var(--red)">${lost}</div><div class="report-metric-lbl">Rejected</div></div>
        </div>
        <div class="narrative-box">${narrative}</div>
      </div>
    </div>
    ${total>0?buildTreeDiagram(total,submitted,pipeline,dropped,won,lost,waiting,winRate,arcOffset,CIRC,decided):''}
    <div class="report-2col">
      <div class="report-block">
        <div class="report-block-header"><div class="report-block-title">Entity Performance</div></div>
        <div class="report-body">
          ${['P&D','FM','WASH','Tech'].filter(e=>!entity||e===entity).map(e=>{
            const b=byEntity[e]; if(!b.total)return'';
            const colMap={'P&D':'var(--pd)','FM':'var(--fm)','WASH':'var(--wash)','Tech':'var(--tech)'};
            const color=colMap[e]||'var(--accent)';
            return `<div style="margin-bottom:14px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:7px">
                <span class="entity-badge entity-${e.replace('&','')}">${e}</span>
                <span style="font-size:13px;font-weight:600;color:${color}">${b.wr}% win rate</span>
              </div>
              <div class="mini-bar-wrap"><div class="mini-bar-label"><span class="lbl">Won</span><span class="val">${b.won}</span></div><div class="mini-bar-track"><div class="mini-bar-fill" style="width:${b.total?Math.round(b.won/b.total*100):0}%;background:var(--green)"></div></div></div>
              <div class="mini-bar-wrap"><div class="mini-bar-label"><span class="lbl">Rejected</span><span class="val">${b.lost}</span></div><div class="mini-bar-track"><div class="mini-bar-fill" style="width:${b.total?Math.round(b.lost/b.total*100):0}%;background:var(--red)"></div></div></div>
              <div class="mini-bar-wrap"><div class="mini-bar-label"><span class="lbl">Total</span><span class="val">${b.total}</span></div><div class="mini-bar-track"><div class="mini-bar-fill" style="width:100%;background:${color};opacity:0.35"></div></div></div>
            </div>`;
          }).join('')}
        </div>
      </div>
      <div class="report-block">
        <div class="report-block-header"><div class="report-block-title">Status Breakdown</div></div>
        <div class="report-body">${buildStatusSummary(data)}</div>
      </div>
    </div>
    ${data.filter(p=>p.result==='Waiting for Result').length?`
    <div class="report-block">
      <div class="report-block-header"><div class="report-block-title">⏳ Waiting for Result <span style="font-size:12px;font-weight:400;color:var(--text3);margin-left:8px">${data.filter(p=>p.result==='Waiting for Result').length} proposals</span></div></div>
      <div class="report-body"><table style="width:100%;border-collapse:collapse">
        <thead><tr>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Title</th>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Entity</th>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Client</th>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Submitted</th>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Latest Remark</th>
        </tr></thead>
        <tbody>${data.filter(p=>p.result==='Waiting for Result').map(p=>`
          <tr>
            <td style="padding:8px;font-size:13px;border-bottom:1px solid var(--border)">${esc(p.title.substring(0,55))}</td>
            <td style="padding:8px;font-size:12px;border-bottom:1px solid var(--border)"><span class="entity-badge entity-${p.entity.replace('&','')}">${p.entity}</span></td>
            <td style="padding:8px;font-size:12px;color:var(--text2);border-bottom:1px solid var(--border)">${esc(p.client||'–')}</td>
            <td style="padding:8px;font-size:12px;color:var(--text2);border-bottom:1px solid var(--border);white-space:nowrap">${fmtDate(p.closeDate)}</td>
            <td style="padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc((p.remark||'').split('|')[0].trim().substring(0,80)||'–')}</td>
          </tr>`).join('')}
        </tbody>
      </table></div>
    </div>`:''}
    ${data.filter(p=>p.result==='Accepted').length?`
    <div class="report-block">
      <div class="report-block-header"><div class="report-block-title">✓ Won <span style="font-size:12px;font-weight:400;color:var(--text3);margin-left:8px">${data.filter(p=>p.result==='Accepted').length}</span></div></div>
      <div class="report-body"><table style="width:100%;border-collapse:collapse">
        <thead><tr>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Title</th>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Entity</th>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Client</th>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Responsible</th>
        </tr></thead>
        <tbody>${data.filter(p=>p.result==='Accepted').map(p=>`
          <tr>
            <td style="padding:8px;font-size:13px;border-bottom:1px solid var(--border)">${esc(p.title.substring(0,55))}</td>
            <td style="padding:8px;font-size:12px;border-bottom:1px solid var(--border)"><span class="entity-badge entity-${p.entity.replace('&','')}">${p.entity}</span></td>
            <td style="padding:8px;font-size:12px;color:var(--text2);border-bottom:1px solid var(--border)">${esc(p.client||'–')}</td>
            <td style="padding:8px;font-size:12px;color:var(--text2);border-bottom:1px solid var(--border)">${esc(p.responsible||'–')}</td>
          </tr>`).join('')}
        </tbody>
      </table></div>
    </div>`:''}
    ${data.filter(p=>['Yet to be submitted','Hold'].includes(p.status)).length?`
    <div class="report-block">
      <div class="report-block-header"><div class="report-block-title">⏳ Pending Action</div></div>
      <div class="report-body"><table style="width:100%;border-collapse:collapse">
        <thead><tr>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Title</th>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Entity</th>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Status</th>
          <th style="text-align:left;padding:8px;font-size:11px;color:var(--text3);border-bottom:1px solid var(--border)">Deadline</th>
        </tr></thead>
        <tbody>${data.filter(p=>['Yet to be submitted','Hold'].includes(p.status)).map(p=>`
          <tr>
            <td style="padding:8px;font-size:13px;border-bottom:1px solid var(--border)">${esc(p.title.substring(0,60))}</td>
            <td style="padding:8px;font-size:12px;border-bottom:1px solid var(--border)"><span class="entity-badge entity-${p.entity.replace('&','')}">${p.entity}</span></td>
            <td style="padding:8px;font-size:12px;border-bottom:1px solid var(--border)">${statusBadge(p.status)}</td>
            <td style="padding:8px;font-size:12px;color:var(--amber);border-bottom:1px solid var(--border)">${fmtDate(p.closeDate)}</td>
          </tr>`).join('')}
        </tbody>
      </table></div>
    </div>`:''}
  `;
  requestAnimationFrame(()=>drawTreeConnectors());
}

// ─── DOWNLOAD AS PDF (Print dialog) ──────────────────────────────────────────
function downloadReportPDF() {
  if(!document.getElementById('page-reports').classList.contains('active')) showPage('reports');
  setTimeout(()=>window.print(), 120);
}

// ─── DOWNLOAD AS DOC (Word-compatible HTML) ───────────────────────────────────
function downloadReportDOC() {
  const entity   = (document.getElementById('report-entity')||{}).value||'';
  const startVal = (document.getElementById('report-start-date')||{}).value||'';
  const endVal   = (document.getElementById('report-end-date')||{}).value||'';
  const reportContent = document.getElementById('report-output').innerHTML;
  if(!reportContent||reportContent.trim()===''){toast('Generate a report first.','error');return;}

  const periodLabel = document.querySelector('#report-output .report-block-title')?.textContent||'Report';
  const rangeStr    = startVal&&endVal ? `${fmtDate(startVal)} to ${fmtDate(endVal)}` : 'All Time';
  const filename    = `Bhumijo_Report_${(periodLabel+' '+entity).replace(/[^a-zA-Z0-9]/g,'_').replace(/_+/g,'_')}_${new Date().toISOString().substring(0,10)}.doc`;

  const docHTML = `<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View><w:Zoom>90</w:Zoom></w:WordDocument></xml><![endif]-->
<title>Bhumijo · ${periodLabel}</title>
<style>
  @page { size: A4; margin: 2cm 2.5cm; }
  body { font-family: Calibri, Arial, sans-serif; font-size: 11pt; color: #111; line-height: 1.5; }
  h1 { font-size: 18pt; font-weight: bold; color: #1a3a6e; margin-bottom: 4pt; }
  h2 { font-size: 13pt; font-weight: bold; color: #1a3a6e; margin: 14pt 0 6pt; border-bottom: 1pt solid #ccc; padding-bottom: 3pt; }
  h3 { font-size: 11pt; font-weight: bold; color: #333; margin: 10pt 0 4pt; }
  .meta { font-size: 9pt; color: #666; margin-bottom: 14pt; }
  table { width: 100%; border-collapse: collapse; margin: 8pt 0; font-size: 10pt; }
  th { background: #e8eef8; border: 1pt solid #aaa; padding: 5pt 7pt; text-align: left; font-weight: bold; font-size: 9pt; color: #333; }
  td { border: 1pt solid #ccc; padding: 5pt 7pt; vertical-align: top; }
  tr:nth-child(even) td { background: #f8f8f8; }
  .metric-table td { text-align: center; font-size: 16pt; font-weight: bold; color: #1a3a6e; }
  .metric-table .lbl { font-size: 8pt; color: #666; font-weight: normal; }
  .section { margin-bottom: 16pt; }
  .narrative { background: #f5f7fa; border-left: 3pt solid #3b7ff5; padding: 8pt 12pt; margin: 8pt 0; font-size: 10pt; color: #333; line-height: 1.7; }
  .tag { display: inline-block; padding: 1pt 5pt; border-radius: 3pt; font-size: 8pt; font-weight: bold; border: 1pt solid #bbb; background: #eee; }
  .tag-pd { background: #ddeeff; color: #1a5cb8; border-color: #88b0e8; }
  .tag-fm { background: #ddf5f0; color: #0a6e60; border-color: #88d8cc; }
  .tag-wash { background: #ede8ff; color: #5a2ea8; border-color: #b8a0f0; }
  .tag-tech { background: #fff3d4; color: #7a4800; border-color: #e8c870; }
  .win { color: #1a8a4a; font-weight: bold; }
  .lost { color: #cc2222; font-weight: bold; }
  .wait { color: #cc7700; font-weight: bold; }
  hr { border: none; border-top: 1pt solid #ddd; margin: 12pt 0; }
</style>
</head>
<body>

<h1>Bhumijo Proposal Tracker</h1>
<h2>${periodLabel}</h2>
<div class="meta">
  Period: ${rangeStr} &nbsp;|&nbsp; Entity: ${entity||'All Entities'} &nbsp;|&nbsp;
  Generated: ${new Date().toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long',year:'numeric'})}
</div>

<div class="section">
${buildDOCReportContent(entity, startVal, endVal)}
</div>

<p style="font-size:8pt;color:#999;margin-top:24pt;border-top:1pt solid #eee;padding-top:6pt">
  Bhumijo Proposal Tracker &nbsp;·&nbsp; Generated ${new Date().toLocaleString('en-GB')}
</p>
</body>
</html>`;

  const blob = new Blob(['\ufeff'+docHTML],{type:'application/msword;charset=utf-8'});
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href=url; a.download=filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
  toast('DOC downloaded — open in Word or Google Docs','success');
}

function buildDOCReportContent(entity, startVal, endVal) {
  let dateFrom=null,dateTo=null;
  if(startVal) dateFrom=new Date(startVal+'T00:00:00');
  if(endVal)   dateTo=new Date(endVal+'T23:59:59');

  let data=proposals.filter(p=>{
    if(entity&&p.entity!==entity)return false;
    if(!dateFrom&&!dateTo)return true;
    const d=p.closeDate?new Date(p.closeDate+'T00:00:00'):(p.createdAt?new Date(p.createdAt+'T00:00:00'):null);
    if(!d)return true;
    if(dateFrom&&d<dateFrom)return false;
    if(dateTo&&d>dateTo)return false;
    return true;
  });

  const total=data.length, submitted=data.filter(p=>p.status==='Submitted').length;
  const won=data.filter(p=>p.result==='Accepted').length, lost=data.filter(p=>p.result==='Rejected').length;
  const waiting=data.filter(p=>p.result==='Waiting for Result').length;
  const decided=won+lost, winRate=decided>0?Math.round(won/decided*100):0;
  const pipeline=data.filter(p=>['Yet to be submitted','Hold'].includes(p.status)).length;

  const entityLabels={'P&D':'Planning & Design','FM':'Facility Management','WASH':'WASH / Toilets','Tech':'Technology'};
  const tagClass={'P&D':'pd','FM':'fm','WASH':'wash','Tech':'tech'};

  let html=`
  <h3>Summary Metrics</h3>
  <table class="metric-table">
    <tr>
      <td style="background:#f0f5ff"><div>${total}</div><div class="lbl">Total Proposals</div></td>
      <td style="background:#f0f8ff"><div>${submitted}</div><div class="lbl">Submitted</div></td>
      <td style="background:#fffbe6"><div class="wait">${waiting}</div><div class="lbl">Waiting Result</div></td>
      <td style="background:#f0fff5"><div class="win">${won}</div><div class="lbl">Won</div></td>
      <td style="background:#fff5f5"><div class="lost">${lost}</div><div class="lbl">Rejected</div></td>
      <td style="background:#f8f8f8"><div>${winRate}%</div><div class="lbl">Win Rate</div></td>
    </tr>
  </table>
  <hr>`;

  // Entity breakdown table
  html+=`<h3>Entity Breakdown</h3>
  <table>
    <thead><tr><th>Entity</th><th>Total</th><th>Submitted</th><th>Won</th><th>Rejected</th><th>Waiting</th><th>Pipeline</th><th>Win Rate</th></tr></thead>
    <tbody>`;
  ['P&D','FM','WASH','Tech'].filter(e=>!entity||e===entity).forEach(e=>{
    const ep=data.filter(p=>p.entity===e);
    const es=ep.filter(p=>p.status==='Submitted').length;
    const ew=ep.filter(p=>p.result==='Accepted').length;
    const el=ep.filter(p=>p.result==='Rejected').length;
    const ewt=ep.filter(p=>p.result==='Waiting for Result').length;
    const epp=ep.filter(p=>['Yet to be submitted','Hold'].includes(p.status)).length;
    const ewr=(ew+el)>0?Math.round(ew/(ew+el)*100):0;
    if(!ep.length)return;
    html+=`<tr><td><span class="tag tag-${tagClass[e]}">${entityLabels[e]||e}</span></td><td>${ep.length}</td><td>${es}</td><td class="win">${ew}</td><td class="lost">${el}</td><td class="wait">${ewt}</td><td>${epp}</td><td>${ewr>0?ewr+'%':'–'}</td></tr>`;
  });
  html+=`</tbody></table><hr>`;

  // Waiting for result
  const waitingData=data.filter(p=>p.result==='Waiting for Result');
  if(waitingData.length){
    html+=`<h3>⏳ Waiting for Result (${waitingData.length})</h3>
    <table>
      <thead><tr><th>Title</th><th>Entity</th><th>Client</th><th>Deadline</th><th>Responsible</th></tr></thead>
      <tbody>${waitingData.map(p=>`<tr>
        <td>${esc(p.title.substring(0,80))}</td>
        <td><span class="tag tag-${tagClass[p.entity]}">${p.entity}</span></td>
        <td>${esc(p.client||'–')}</td>
        <td>${fmtDate(p.closeDate)}</td>
        <td>${esc(p.responsible||'–')}</td>
      </tr>`).join('')}</tbody>
    </table><hr>`;
  }

  // Won
  const wonData=data.filter(p=>p.result==='Accepted');
  if(wonData.length){
    html+=`<h3>✓ Won / Accepted (${wonData.length})</h3>
    <table>
      <thead><tr><th>Title</th><th>Entity</th><th>Client</th><th>Responsible</th><th>Remark</th></tr></thead>
      <tbody>${wonData.map(p=>`<tr>
        <td>${esc(p.title.substring(0,80))}</td>
        <td><span class="tag tag-${tagClass[p.entity]}">${p.entity}</span></td>
        <td>${esc(p.client||'–')}</td>
        <td>${esc(p.responsible||'–')}</td>
        <td style="font-size:9pt;color:#555">${esc((p.remark||'').split('|')[0].trim().substring(0,100)||'–')}</td>
      </tr>`).join('')}</tbody>
    </table><hr>`;
  }

  // Pending pipeline
  const pendingData=data.filter(p=>['Yet to be submitted','Hold'].includes(p.status));
  if(pendingData.length){
    html+=`<h3>📋 Pending Action (${pendingData.length})</h3>
    <table>
      <thead><tr><th>Title</th><th>Entity</th><th>Status</th><th>Deadline</th><th>Responsible</th></tr></thead>
      <tbody>${pendingData.map(p=>`<tr>
        <td>${esc(p.title.substring(0,80))}</td>
        <td><span class="tag tag-${tagClass[p.entity]}">${p.entity}</span></td>
        <td>${esc(p.status)}</td>
        <td>${fmtDate(p.closeDate)}</td>
        <td>${esc(p.responsible||'–')}</td>
      </tr>`).join('')}</tbody>
    </table>`;
  }

  return html;
}

// showPage updated inline above
