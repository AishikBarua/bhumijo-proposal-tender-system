/* Moving between screens and filtering by entity.
   Moved verbatim from Bhumijo_Proposal_Tracker_22Jul2026.html — 6 function(s), not rewritten.
   Loaded in a fixed order by index.html, sharing one scope, exactly as before. */

/* The sidebar is a permanent column on a wide screen and a drawer on a
   narrow one (see the RESPONSIVE section of components.css). Only the open
   and closed state lives here; the breakpoint that decides which behaviour
   applies stays in CSS, so there is one definition of "narrow", not two. */
function openSidebar() {
  const bar = document.getElementById('sidebar');
  const scrim = document.getElementById('sidebar-scrim');
  const toggle = document.getElementById('sidebar-toggle');
  if (!bar) return;
  bar.classList.add('open');
  if (scrim) scrim.classList.add('visible');
  if (toggle) toggle.setAttribute('aria-expanded', 'true');
}

function closeSidebar() {
  const bar = document.getElementById('sidebar');
  const scrim = document.getElementById('sidebar-scrim');
  const toggle = document.getElementById('sidebar-toggle');
  if (!bar) return;
  bar.classList.remove('open');
  if (scrim) scrim.classList.remove('visible');
  if (toggle) toggle.setAttribute('aria-expanded', 'false');
}

function toggleSidebar() {
  const bar = document.getElementById('sidebar');
  if (!bar) return;
  bar.classList.contains('open') ? closeSidebar() : openSidebar();
}

function switchModulePage(mod){
  if(mod==='hitlist'){ window.location.href='bhumijo-Hitlist-22Jul2026.html'; }
}

// Same pattern as switchModulePage() above - leaves the SPA shell for a
// separately-rendered set of screens. The AI Agent module now runs merged
// into this same server (see backend/main.py, mounted under /agent), rather
// than as a whole other file on this server or a different port.
function goToAiAgent(){
  window.location.href = '/agent/';
}

// ─── INIT ─────────────────────────────────────────────────────────────────────
function renderSidebarDate() {
  const now = new Date();
  document.getElementById('sidebar-date').textContent = now.toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
}

function showPage(name) {
  closeSidebar();   // no-op on the desktop layout
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-item[data-page]').forEach(n=>n.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  const nav = document.querySelector(`.nav-item[data-page="${name}"]`);
  if(nav) nav.classList.add('active');
  const titles = {dashboard:'Dashboard',proposals:'All Proposals',clients:'Client Records',reports:'Reports'};
  const subs = {dashboard:'All entities · Overview',proposals:'Browse, filter and manage',clients:'Auto-generated from accepted projects',reports:'Bi-weekly · Monthly · Yearly summaries'};
  document.getElementById('topbar-title').textContent = titles[name]||name;
  document.getElementById('topbar-sub').textContent = subs[name]||'';
  if(name==='reports') generateReport();
  if(name==='clients') renderClients();
  if(name==='proposals') {
    const ev = document.getElementById('filter-entity').value;
    renderEntitySummaryStrip(ev);
  }
}

function filterByEntity(entity) {
  document.getElementById('filter-entity').value = entity;
  showPage('proposals');
  filterTable();
  renderEntitySummaryStrip(entity);
}

function clearEntityFilter() {
  document.getElementById('filter-entity').value = '';
  const strip = document.getElementById('entity-summary-strip');
  if(strip) strip.style.display = 'none';
  filterTable();
  document.getElementById('proposals-table-title').textContent = 'All Proposals';
}

function renderEntitySummary(entity) {
  renderEntitySummaryStrip(entity); return; // redirected
  const panel = document.getElementById('entity-summary');
  const today = new Date(); today.setHours(0,0,0,0);
  const in7   = new Date(today); in7.setDate(today.getDate()+7);
  const in15  = new Date(today); in15.setDate(today.getDate()+15);
  const pendingStatuses = ['Yet to be submitted', 'Hold'];

  // Filter to entity (or all if empty)
  const ep = entity ? proposals.filter(p => p.entity === entity) : proposals;
  if(ep.length === 0 && entity) { panel.classList.remove('visible'); return; }

  const total    = ep.length;
  const yet      = ep.filter(p => p.status === 'Yet to be submitted').length;
  const hold     = ep.filter(p => p.status === 'Hold').length;
  const unable   = ep.filter(p => p.status === 'Unable to submit').length;
  const drop     = ep.filter(p => p.status === 'Drop').length;
  const submitted= ep.filter(p => p.status === 'Submitted').length;
  const waiting  = ep.filter(p => p.result === 'Waiting for Result').length;
  const accepted = ep.filter(p => p.result === 'Accepted').length;
  const rejected = ep.filter(p => p.result === 'Rejected').length;

  const dead7  = ep.filter(p => {
    if(!p.closeDate || !pendingStatuses.includes(p.status)) return false;
    const d = new Date(p.closeDate); return d >= today && d <= in7;
  }).length;
  const dead15 = ep.filter(p => {
    if(!p.closeDate || !pendingStatuses.includes(p.status)) return false;
    const d = new Date(p.closeDate); return d >= today && d <= in15;
  }).length;

  const nameMap  = {'P&D':'Planning & Design','FM':'Facility Management','WASH':'WASH / Toilets','Tech':'Technology',''  :'All Entities'};
  const colorMap = {'P&D':'var(--pd)','FM':'var(--fm)','WASH':'var(--wash)','Tech':'var(--tech)','':'var(--accent)'};
  const bgMap    = {'P&D':'59,127,245','FM':'24,176,160','WASH':'124,82,232','Tech':'224,144,10','':'59,127,245'};

  document.getElementById('es-title').textContent  = nameMap[entity||'']||entity;
  document.getElementById('es-badge').textContent  = entity||'All';
  document.getElementById('es-badge').style.background = `rgba(${bgMap[entity||'']},0.1)`;
  document.getElementById('es-badge').style.color  = colorMap[entity||'']||'var(--accent)';
  document.getElementById('es-total').textContent  = total;
  document.getElementById('es-yet').textContent    = yet;
  document.getElementById('es-hold').textContent   = hold;
  document.getElementById('es-unable').textContent = unable;
  document.getElementById('es-drop').textContent   = drop;
  document.getElementById('es-dead7').textContent  = dead7;
  document.getElementById('es-dead15').textContent = dead15;
  document.getElementById('es-submitted').textContent = submitted;
  document.getElementById('es-waiting').textContent   = waiting;
  document.getElementById('es-accepted').textContent  = accepted;
  document.getElementById('es-rejected').textContent  = rejected;

  panel.classList.add('visible');
}
