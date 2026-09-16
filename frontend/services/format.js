/* Dates, badges, escaping, toasts — the small shared helpers.
   Moved verbatim from Bhumijo_Proposal_Tracker_22Jul2026.html — 7 function(s), not rewritten.
   Loaded in a fixed order by index.html, sharing one scope, exactly as before. */

function esc(str) {
  if(!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fmtDate(d) {
  if(!d) return '–';
  try {
    const dt = new Date(d+'T00:00:00');
    if(isNaN(dt)) return d;
    return dt.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
  } catch(e) { return d; }
}
function statusBadge(status) {
  const map = {'Submitted':'badge-submitted','Yet to be submitted':'badge-yet','Hold':'badge-hold','Drop':'badge-drop','Unable to submit':'badge-unable'};
  const labels = {'Submitted':'Submitted','Yet to be submitted':'Yet to Submit','Hold':'Hold','Drop':'Drop','Unable to submit':'Unable'};
  return `<span class="badge ${map[status]||'badge-drop'}">${esc(labels[status]||status||'–')}</span>`;
}
function resultBadge(result) {
  if(!result) return '<span style="font-size:11px;color:var(--text3)">–</span>';
  const map = {'Accepted':'badge-accepted','Rejected':'badge-rejected','Waiting for Result':'badge-waiting'};
  const icons = {'Accepted':'✓ ','Rejected':'✗ ','Waiting for Result':'⏳ '};
  return `<span class="badge ${map[result]||''}">${esc((icons[result]||'')+result)}</span>`;
}
function stageBadge(category) {
  if(!category) return '<span style="font-size:11px;color:var(--text3)">–</span>';
  const short = category.length > 22 ? category.substring(0,22)+'…' : category;
  return `<span style="font-size:11px;color:var(--text2);background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:2px 7px;white-space:nowrap">${esc(short)}</span>`;
}
function daysBadge(closeDate) {
  if(!closeDate) return '<span class="days-badge days-ok">–</span>';
  const today = new Date(); today.setHours(0,0,0,0);
  const close = new Date(closeDate+'T00:00:00');
  if(isNaN(close)) return '<span class="days-badge days-ok">–</span>';
  const diff = Math.ceil((close - today)/86400000);
  if(diff < 0) return `<span class="days-badge days-overdue">${Math.abs(diff)}d ago</span>`;
  if(diff === 0) return '<span class="days-badge days-urgent">Today!</span>';
  if(diff <= 3)  return `<span class="days-badge days-urgent">${diff}d</span>`;
  if(diff <= 14) return `<span class="days-badge days-soon">${diff}d</span>`;
  return `<span class="days-badge days-ok">${diff}d</span>`;
}
function toast(msg, type='success') {
  const wrap = document.getElementById('toast-wrap');
  if(!wrap) return;
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.textContent = msg;
  wrap.appendChild(t);
  setTimeout(() => { t.style.opacity='0'; t.style.transition='opacity 0.3s'; setTimeout(()=>t.remove(),300); }, 3200);
}

// ─── renderCharts OVERRIDE: Replace Status Breakdown with Entity % donut ──────
